"""
predict.py - the orbital engine (faithful port of CardSat's predict.cpp).

Conventions are preserved from the device:
  * range rate is taken from the SGP4 velocity vector (exact), not by
    differencing slant range
  * eclipse is the cylindrical Earth-shadow test
  * beta angle is orbit-plane vs Sun
  * mutual windows are co-visibility of two ground stations
WGS72 geometry is used throughout to match the element set.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .propagator import make_satrec
from .satdb import SatEntry, Transponder

DEG = math.pi / 180.0
RE_KM = 6378.135
E2 = 6.694318e-3            # WGS72 first eccentricity^2
C_LIGHT = 299792458.0
WE = 7.2921150e-5          # Earth rotation rate, rad/s
MU = 398600.8


@dataclass
class Observer:
    lat: float = 0.0    # deg +N
    lon: float = 0.0    # deg +E
    alt_m: float = 0.0
    valid: bool = False


@dataclass
class Elements:
    """Lightweight bundle the propagator backend consumes."""
    jdsatepoch: float
    bstar: float
    ndot: float
    nddot: float
    ecco: float
    argpo_deg: float
    inclo_deg: float
    mo_deg: float
    no_kozai_revperday: float
    nodeo_deg: float
    satnum: int


@dataclass
class LiveLook:
    az: float = 0.0
    el: float = 0.0
    range_km: float = 0.0
    range_rate: float = 0.0    # km/s, +receding
    sub_lat: float = 0.0
    sub_lon: float = 0.0
    alt_km: float = 0.0
    visible: bool = False
    sunlit: bool = True
    sun_az: float = 0.0
    sun_el: float = 0.0


@dataclass
class PassPredict:
    aos: float = 0.0      # unix UTC
    los: float = 0.0
    tca: float = 0.0
    max_el: float = 0.0
    az_aos: float = 0.0
    az_los: float = 0.0


@dataclass
class MutualWindow:
    start: float = 0.0
    end: float = 0.0
    my_max_el: float = 0.0
    dx_max_el: float = 0.0


@dataclass
class EclipsePeriod:
    """One umbral eclipse: the satellite passes through the Earth's shadow.

    ``enter`` / ``exit`` are unix times; ``sun_angle`` is the angle between the
    orbital plane and the Sun (the beta angle) at mid-eclipse, which sets how
    deep and long the eclipse season runs.
    """
    enter: float = 0.0
    exit: float = 0.0
    sun_angle: float = 0.0          # beta angle at mid-eclipse (deg)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.exit - self.enter)


def jd_of(unix: float) -> float:
    return unix / 86400.0 + 2440587.5


def _sun_eci_unit(jd: float) -> Tuple[float, float, float]:
    n = jd - 2451545.0
    L = math.fmod(280.460 + 0.9856474 * n, 360.0)
    g = math.fmod(357.528 + 0.9856003 * n, 360.0) * DEG
    lam = (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) * DEG
    eps = (23.439 - 0.0000004 * n) * DEG
    return math.cos(lam), math.cos(eps) * math.sin(lam), math.sin(eps) * math.sin(lam)


def _gmst_rad(jd: float) -> float:
    T = (jd - 2451545.0) / 36525.0
    g = (280.46061837 + 360.98564736629 * (jd - 2451545.0) +
         0.000387933 * T * T - T * T * T / 38710000.0)
    g = math.fmod(g, 360.0)
    if g < 0:
        g += 360.0
    return g * DEG


def _geodetic_to_ecef(lat_deg, lon_deg, h_km):
    phi = lat_deg * DEG
    lam = lon_deg * DEG
    s, c = math.sin(phi), math.cos(phi)
    N = RE_KM / math.sqrt(1.0 - E2 * s * s)
    x = (N + h_km) * c * math.cos(lam)
    y = (N + h_km) * c * math.sin(lam)
    z = (N * (1.0 - E2) + h_km) * s
    return x, y, z


def _teme_to_ecef_lla(r, jd):
    """TEME position (km) -> geodetic lat/lon/alt using GMST rotation."""
    th = _gmst_rad(jd)
    ct, st = math.cos(th), math.sin(th)
    # ECEF = Rz(-theta) * TEME  (rotate by -GMST)
    xe = r[0] * ct + r[1] * st
    ye = -r[0] * st + r[1] * ct
    ze = r[2]
    lon = math.atan2(ye, xe)
    # iterate for geodetic latitude
    p = math.hypot(xe, ye)
    if p < 1e-6:
        # essentially over a pole: latitude is +/-90, altitude is |ze| - polar N
        lat = math.copysign(math.pi / 2.0, ze)
        N = RE_KM / math.sqrt(1.0 - E2)
        alt = abs(ze) - RE_KM * (1.0 - E2) / math.sqrt(1.0 - E2)
        return lat / DEG, lon / DEG, alt
    lat = math.atan2(ze, p * (1.0 - E2))
    for _ in range(5):
        s = math.sin(lat)
        N = RE_KM / math.sqrt(1.0 - E2 * s * s)
        alt = p / math.cos(lat) - N
        denom = N + alt
        if abs(denom) < 1e-9:
            break
        lat = math.atan2(ze, p * (1.0 - E2 * N / denom))
    s = math.sin(lat)
    N = RE_KM / math.sqrt(1.0 - E2 * s * s)
    alt = p / math.cos(lat) - N
    return lat / DEG, lon / DEG, alt


class Predictor:
    def __init__(self):
        self._sat = None
        self._epoch_unix = 0.0
        self._have = False
        self._incl = 0.0
        self._raan = 0.0
        # memoised SGP4 states keyed on rounded unix time (see _eci_state)
        self._eci_cache = {}
        self._eci_cache_max = 4096
        self.set_site(Observer())    # also primes the observer-geometry cache

    def set_site(self, o: Observer):
        self._o = o
        # Precompute the parts of the observer geometry that do NOT change with
        # time: its ECEF position and the trig of its latitude. These were being
        # recomputed (sin/cos/sqrt) on every look()/azel call -- tens of
        # thousands of times during a pass scan -- even though a fixed site's
        # ECEF coordinates are constant. Only the Earth-rotation (GMST) part
        # varies per timestamp.
        self._obs_ecef = _geodetic_to_ecef(o.lat, o.lon, o.alt_m / 1000.0)
        _latr = o.lat * DEG
        self._obs_slat = math.sin(_latr)
        self._obs_clat = math.cos(_latr)
        self._obs_lon_rad = o.lon * DEG

    def set_sat(self, s: SatEntry) -> bool:
        el = Elements(
            jdsatepoch=s.jdsatepoch, bstar=s.bstar, ndot=s.ndot,
            nddot=s.nddot, ecco=s.ecc, argpo_deg=s.argp, inclo_deg=s.incl,
            mo_deg=s.ma, no_kozai_revperday=s.mean_motion, nodeo_deg=s.raan,
            satnum=s.norad)
        self._sat = make_satrec(el)
        self._epoch_unix = s.epoch_unix
        self._incl = s.incl
        self._raan = s.raan
        self._have = (self._sat.error == 0)
        self._eci_cache.clear()      # new orbit -> previous states are invalid
        return self._have

    def deepspace_approximate(self) -> bool:
        """True when the current satellite is a deep-space (period >= 225 min,
        e.g. geostationary / Molniya) orbit AND we're propagating it with the
        vendored approximate backend rather than the full reference SDP4. In that
        state, positions (and therefore visibility) can be significantly off, so
        callers should warn the user."""
        if self._sat is None:
            return False
        try:
            from .propagator import have_full_sdp4
            if have_full_sdp4():
                return False
            return bool(getattr(self._sat, "is_deep", False))
        except Exception:
            return False

    # ---- propagation helpers ----
    def _propagate(self, unix: float):
        tsince = (unix - self._epoch_unix) / 60.0
        return self._sat.sgp4(tsince)

    def _eci_state(self, unix: float):
        # SGP4 propagation is the dominant cost on every screen: the node-finder
        # bisects ~40x per crossing and a single render asks for the same instant
        # through subpoint_at / azel_at / look. Memoise on the unix time (rounded
        # to 1 ms so float jitter still hits) with a small bounded dict, cleared
        # whenever the satellite or epoch changes. This turns repeated lookups of
        # the same instant into a dict hit and roughly halves node-finding time.
        key = round(unix, 3)
        cache = getattr(self, "_eci_cache", None)
        if cache is None:
            # object built without __init__ (e.g. some test paths): no caching
            return self._propagate(unix)
        hit = cache.get(key)
        if hit is not None:
            return hit
        rv = self._propagate(unix)
        if len(cache) >= self._eci_cache_max:
            cache.clear()           # cheap bounded eviction (whole-cache reset)
        cache[key] = rv
        return rv

    # ---- live look ----
    def look(self, unix: float) -> LiveLook:
        L = LiveLook()
        if not self._have:
            return L
        r, v = self._eci_state(unix)
        jd = jd_of(unix)
        lat, lon, alt = _teme_to_ecef_lla(r, jd)
        L.sub_lat, L.sub_lon, L.alt_km = lat, lon, alt

        az, el, rng = self._azel_range(r, unix)
        L.az, L.el, L.range_km = az, el, rng
        L.visible = el > 0.0
        L.range_rate = self._range_rate(r, v, unix)

        # sun geometry
        sunlit, sun_az, sun_el = self._sun_geometry(r, unix)
        L.sunlit = sunlit
        L.sun_az = sun_az
        L.sun_el = sun_el
        return L

    def _observer_teme(self, unix: float):
        jd = jd_of(unix)
        th = _gmst_rad(jd)
        ct, st = math.cos(th), math.sin(th)
        xe, ye, ze = self._obs_ecef       # constant for a fixed site
        ox = xe * ct - ye * st
        oy = xe * st + ye * ct
        oz = ze
        return ox, oy, oz, th

    def _azel_range(self, r, unix: float):
        ox, oy, oz, th = self._observer_teme(unix)
        rx, ry, rz = r[0] - ox, r[1] - oy, r[2] - oz
        rng = math.sqrt(rx * rx + ry * ry + rz * rz)
        # topocentric ENU at observer (use GMST-rotated longitude)
        lst = th + self._obs_lon_rad
        slat, clat = self._obs_slat, self._obs_clat     # constant for the site
        ss, cs = math.sin(lst), math.cos(lst)
        # East, North, Up unit vectors in TEME
        e = -ss * rx + cs * ry
        n = -slat * cs * rx - slat * ss * ry + clat * rz
        u = clat * cs * rx + clat * ss * ry + slat * rz
        el = math.atan2(u, math.sqrt(e * e + n * n)) / DEG
        az = math.atan2(e, n) / DEG
        if az < 0:
            az += 360.0
        return az, el, rng

    def _range_rate(self, r, v, unix: float):
        ox, oy, oz, th = self._observer_teme(unix)
        ovx, ovy, ovz = -WE * oy, WE * ox, 0.0
        rx, ry, rz = r[0] - ox, r[1] - oy, r[2] - oz
        vx, vy, vz = v[0] - ovx, v[1] - ovy, v[2] - ovz
        rmag = math.sqrt(rx * rx + ry * ry + rz * rz)
        if rmag <= 0:
            return 0.0
        return (rx * vx + ry * vy + rz * vz) / rmag

    def _sun_geometry(self, r, unix: float):
        jd = jd_of(unix)
        sx, sy, sz = _sun_eci_unit(jd)
        th = _gmst_rad(jd)
        # cylindrical shadow test on the satellite TEME position
        proj = r[0] * sx + r[1] * sy + r[2] * sz
        rmag2 = r[0] * r[0] + r[1] * r[1] + r[2] * r[2]
        perp = math.sqrt(max(0.0, rmag2 - proj * proj))
        sunlit = not (proj < 0.0 and perp < RE_KM)
        # sun az/el for the observer
        olat = self._o.lat * DEG
        lst = th + self._o.lon * DEG
        ss, cs = math.sin(lst), math.cos(lst)
        slat, clat = math.sin(olat), math.cos(olat)
        e = -ss * sx + cs * sy
        n = -slat * cs * sx - slat * ss * sy + clat * sz
        u = clat * cs * sx + clat * ss * sy + slat * sz
        sun_el = math.atan2(u, math.sqrt(e * e + n * n)) / DEG
        sun_az = math.atan2(e, n) / DEG
        if sun_az < 0:
            sun_az += 360.0
        return sunlit, sun_az, sun_el

    def sunlit_at(self, unix: float) -> bool:
        if not self._have:
            return True
        r, _ = self._eci_state(unix)
        jd = jd_of(unix)
        sx, sy, sz = _sun_eci_unit(jd)
        proj = r[0] * sx + r[1] * sy + r[2] * sz
        rmag2 = sum(c * c for c in r)
        perp = math.sqrt(max(0.0, rmag2 - proj * proj))
        return not (proj < 0.0 and perp < RE_KM)

    def eclipse_depth_deg(self, unix: float) -> float:
        if not self._have:
            return -90.0
        r, _ = self._eci_state(unix)
        jd = jd_of(unix)
        sx, sy, sz = _sun_eci_unit(jd)
        proj = r[0] * sx + r[1] * sy + r[2] * sz
        rmag2 = sum(c * c for c in r)
        rr = math.sqrt(rmag2)
        perp = math.sqrt(max(0.0, rmag2 - proj * proj))
        sd_earth = math.asin(min(1.0, RE_KM / rr)) / DEG
        delta = math.asin(min(1.0, perp / rr)) / DEG
        if proj < 0.0:
            return sd_earth - delta
        return sd_earth - (180.0 - delta)

    def beta_angle_deg(self, unix: float, incl_deg=None, raan_deg=None) -> float:
        if incl_deg is None:
            incl_deg = self._incl
        if raan_deg is None:
            raan_deg = self._raan
        jd = jd_of(unix)
        sx, sy, sz = _sun_eci_unit(jd)
        i = incl_deg * DEG
        O = raan_deg * DEG
        nx = math.sin(i) * math.sin(O)
        ny = -math.sin(i) * math.cos(O)
        nz = math.cos(i)
        d = max(-1.0, min(1.0, nx * sx + ny * sy + nz * sz))
        return math.asin(d) / DEG

    def footprint_radius_km(self, alt_km: float) -> float:
        """Ground-coverage radius (great-circle) for a sat at altitude."""
        ratio = RE_KM / (RE_KM + alt_km)
        return RE_KM * math.acos(max(-1.0, min(1.0, ratio)))

    def azel_at(self, unix: float):
        if not self._have:
            return 0.0, 0.0
        r, _ = self._eci_state(unix)
        az, el, _rng = self._azel_range(r, unix)
        return az, el

    def subpoint_at(self, unix: float):
        r, _ = self._eci_state(unix)
        return _teme_to_ecef_lla(r, jd_of(unix))

    def ascending_nodes(self, frm: float, to: float, max_n: int = 200):
        """Ascending equator crossings (sub-latitude going - to +). See
        _equator_crossings."""
        return self._equator_crossings(frm, to, ascending=True, max_n=max_n)

    def descending_nodes(self, frm: float, to: float, max_n: int = 200):
        """Descending equator crossings (sub-latitude going + to -). These are
        the relevant EQX events for southern-hemisphere OSCARLOCATOR sheets."""
        return self._equator_crossings(frm, to, ascending=False, max_n=max_n)

    def _equator_crossings(self, frm: float, to: float, ascending: bool = True,
                           max_n: int = 200):
        """Find equator crossings between unix times `frm` and `to`. Returns a
        list of (unix_time, longitude) tuples. With ``ascending`` True the sub-
        latitude crosses - to + (northbound node); with False it crosses + to -
        (southbound node). Longitude is the geographic sub-longitude.

        Coarse scan (a fraction of the period) brackets each sign change, then
        bisection refines the time to half-second precision."""
        if not self._have:
            return []
        period_s = 0.0
        try:
            period_s = (2.0 * math.pi / self._sat.no_kozai) * 60.0
        except Exception:
            period_s = 95.0 * 60.0
        if period_s <= 0:
            period_s = 95.0 * 60.0
        step = max(30.0, period_s / 12.0)

        out = []
        t = frm
        prev_t = t
        prev_lat = self.subpoint_at(t)[0]
        t += step
        while t <= to and len(out) < max_n:
            lat = self.subpoint_at(t)[0]
            crossing = (prev_lat < 0.0 <= lat) if ascending \
                else (prev_lat >= 0.0 > lat)
            if crossing:
                a, b = prev_t, t
                la = prev_lat
                for _ in range(40):
                    m = 0.5 * (a + b)
                    lm = self.subpoint_at(m)[0]
                    if (la < 0.0) == (lm < 0.0):
                        a, la = m, lm
                    else:
                        b = m
                    if abs(b - a) < 0.5:
                        break
                tc = 0.5 * (a + b)
                lon = self.subpoint_at(tc)[1]
                out.append((tc, lon))
            prev_t, prev_lat = t, lat
            t += step
        return out

    @staticmethod
    def elevation_from_subpoint(obs_lat, obs_lon, obs_alt_m,
                                sat_lat, sat_lon, sat_alt_km) -> float:
        ox, oy, oz = _geodetic_to_ecef(obs_lat, obs_lon, obs_alt_m / 1000.0)
        sx, sy, sz = _geodetic_to_ecef(sat_lat, sat_lon, sat_alt_km)
        dx, dy, dz = sx - ox, sy - oy, sz - oz
        dn = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dn <= 0:
            return -90.0
        phi = obs_lat * DEG
        lam = obs_lon * DEG
        ux = math.cos(phi) * math.cos(lam)
        uy = math.cos(phi) * math.sin(lam)
        uz = math.sin(phi)
        return math.asin((dx * ux + dy * uy + dz * uz) / dn) / DEG

    # ---- Doppler ----
    @staticmethod
    def doppler_freqs(dl_nominal, ul_nominal, range_rate_kms,
                      cal_dl_hz=0, cal_ul_hz=0):
        rr = range_rate_kms * 1000.0
        beta = rr / C_LIGHT
        rx = dl_nominal * (1.0 - beta) + cal_dl_hz
        tx = (ul_nominal / (1.0 - beta) + cal_ul_hz) if ul_nominal else 0.0
        return int(round(rx)), int(round(tx))

    @staticmethod
    def passband_freqs(t: Transponder, pb_offset_hz: int):
        dl_bw = t.bandwidth()
        if not t.is_linear or dl_bw == 0:
            return t.downlink, t.uplink
        off = max(0, min(pb_offset_hz, dl_bw))
        dl_op = t.downlink + off
        if t.uplink == 0:
            return dl_op, 0
        ul_bw = (t.uplink_high - t.uplink) if t.uplink_high > t.uplink else dl_bw
        if t.invert:
            ul_op = t.uplink + ul_bw - off
        else:
            ul_op = t.uplink + off
        return dl_op, ul_op

    # ---- pass prediction (root-find on elevation) ----
    def predict_passes(self, frm: float, min_el: float, max_n: int,
                       horizon_end: float = 0.0,
                       coarse_step: float = 30.0) -> List[PassPredict]:
        if not self._have:
            return []
        out: List[PassPredict] = []
        t = frm
        end = horizon_end if horizon_end else frm + 10 * 86400
        prev_el = self.azel_at(t)[1]
        while t < end and len(out) < max_n:
            t2 = t + coarse_step
            el2 = self.azel_at(t2)[1]
            if prev_el < 0.0 <= el2:
                # rising crossing between t and t2 -> refine AOS
                aos = self._bisect_rise(t, t2)
                p = self._build_pass(aos, min_el, end)
                if p and (horizon_end == 0 or p.aos <= end):
                    if p.max_el >= min_el:
                        out.append(p)
                    # jump to just past LOS
                    t = p.los + coarse_step
                    prev_el = self.azel_at(t)[1]
                    continue
            prev_el = el2
            t = t2
        return out

    def _bisect_rise(self, t_lo, t_hi):
        for _ in range(40):
            mid = 0.5 * (t_lo + t_hi)
            if self.azel_at(mid)[1] < 0.0:
                t_lo = mid
            else:
                t_hi = mid
            if t_hi - t_lo < 0.5:
                break
        return t_hi

    def _bisect_set(self, t_lo, t_hi):
        for _ in range(40):
            mid = 0.5 * (t_lo + t_hi)
            if self.azel_at(mid)[1] >= 0.0:
                t_lo = mid
            else:
                t_hi = mid
            if t_hi - t_lo < 0.5:
                break
        return t_lo

    def _build_pass(self, aos, min_el, end) -> Optional[PassPredict]:
        # find LOS: step until elevation drops below 0
        step = 20.0
        t = aos
        el_prev = self.azel_at(t)[1]
        los = None
        max_el = el_prev
        tca = aos
        while t < end + 2400:
            t2 = t + step
            el2 = self.azel_at(t2)[1]
            if el2 > max_el:
                max_el = el2
                tca = t2
            if el_prev >= 0.0 > el2:
                los = self._bisect_set(t, t2)
                break
            el_prev = el2
            t = t2
        if los is None:
            return None
        # refine TCA around the coarse maximum with a golden-ish search
        tca = self._refine_tca(max(aos, tca - step), min(los, tca + step))
        max_el = self.azel_at(tca)[1]
        p = PassPredict()
        p.aos = aos
        p.los = los
        p.tca = tca
        p.max_el = max_el
        p.az_aos = self.azel_at(aos)[0]
        p.az_los = self.azel_at(los)[0]
        return p

    def _refine_tca(self, a, b):
        gr = (math.sqrt(5) - 1) / 2
        c = b - gr * (b - a)
        d = a + gr * (b - a)
        for _ in range(30):
            if self.azel_at(c)[1] < self.azel_at(d)[1]:
                a = c
            else:
                b = d
            c = b - gr * (b - a)
            d = a + gr * (b - a)
            if b - a < 1.0:
                break
        return 0.5 * (a + b)

    # ---- stepped position listing (one observer) ----
    def listing_rows(self, frm: float, step_s: float, count: int,
                     visible_only: bool = False):
        """A time-stepped ephemeris from one observer: az/el/range/sub-point/
        altitude/range-rate/sunlit at ``count`` samples every ``step_s`` seconds
        from ``frm``. Mirrors Nova's One-Observer listing. Returns a list of
        dicts. With ``visible_only`` set, samples below the horizon are skipped.
        """
        if not self._have:
            return []
        out = []
        for i in range(count):
            t = frm + i * step_s
            L = self.look(t)
            if visible_only and L.el < 0.0:
                continue
            out.append({
                "t": t, "az": L.az, "el": L.el, "range_km": L.range_km,
                "range_rate": L.range_rate, "sub_lat": L.sub_lat,
                "sub_lon": L.sub_lon, "alt_km": L.alt_km, "sunlit": L.sunlit,
            })
        return out

    def listing_rows_two(self, frm: float, step_s: float, count: int,
                         dx: "Observer", visible_only: bool = False):
        """Two-observer stepped listing: for each sample, this station's az/el/
        range plus the second station's az/el/range to the same satellite, from
        a single ephemeris evaluation. Mirrors Nova's Two-Observers listing."""
        if not self._have:
            return []
        out = []
        for i in range(count):
            t = frm + i * step_s
            r, v = self._eci_state(t)
            az1, el1, rng1 = self._azel_range(r, t)
            lat, lon, alt = _teme_to_ecef_lla(r, jd_of(t))
            az2, el2, rng2 = self._azel_range_from(dx, r, t)
            if visible_only and el1 < 0.0 and el2 < 0.0:
                continue
            out.append({
                "t": t,
                "az1": az1, "el1": el1, "range1_km": rng1,
                "az2": az2, "el2": el2, "range2_km": rng2,
                "sub_lat": lat, "sub_lon": lon, "alt_km": alt,
            })
        return out

    def _azel_range_from(self, obs: "Observer", r, unix: float):
        """az/el/range to ECI position ``r`` from an arbitrary observer (used by
        the two-observer listing so both columns come from one ephemeris)."""
        jd = jd_of(unix)
        th = _gmst_rad(jd)
        ct, st = math.cos(th), math.sin(th)
        xe, ye, ze = _geodetic_to_ecef(obs.lat, obs.lon, obs.alt_m / 1000.0)
        ox = xe * ct - ye * st
        oy = xe * st + ye * ct
        oz = ze
        rx, ry, rz = r[0] - ox, r[1] - oy, r[2] - oz
        rng = math.sqrt(rx * rx + ry * ry + rz * rz)
        lat = obs.lat * DEG
        lst = th + obs.lon * DEG
        slat, clat = math.sin(lat), math.cos(lat)
        ss, cs = math.sin(lst), math.cos(lst)
        e = -ss * rx + cs * ry
        n = -slat * cs * rx - slat * ss * ry + clat * rz
        u = clat * cs * rx + clat * ss * ry + slat * rz
        el = math.asin(max(-1.0, min(1.0, u / rng))) / DEG
        az = math.atan2(e, n) / DEG
        if az < 0:
            az += 360.0
        return az, el, rng

    # ---- eclipse (umbral shadow) ephemeris ----
    def predict_eclipses(self, frm: float, max_n: int = 64,
                         horizon_days: float = 1.0,
                         coarse_step: float = 30.0):
        """Umbral eclipse periods (enter/exit) starting at ``frm``.

        Mirrors ``predict_passes``: step coarsely watching the sunlit flag,
        then bisect the sunlit->shadow (enter) and shadow->sunlit (exit)
        crossings. Returns a list of EclipsePeriod.
        """
        if not self._have:
            return []
        out = []
        t = frm
        end = frm + horizon_days * 86400.0
        prev_lit = self.sunlit_at(t)
        # if we start already in shadow, find this eclipse's exit first so we
        # don't emit a truncated period with a bogus enter time
        while t < end and len(out) < max_n:
            t2 = t + coarse_step
            lit2 = self.sunlit_at(t2)
            if prev_lit and not lit2:
                enter = self._bisect_eclipse(t, t2, want_shadow=True)
                # find the matching exit
                te = enter
                while te < end + 7200.0:
                    te2 = te + coarse_step
                    if not self.sunlit_at(te) and self.sunlit_at(te2):
                        ex = self._bisect_eclipse(te, te2, want_shadow=False)
                        mid = 0.5 * (enter + ex)
                        out.append(EclipsePeriod(
                            enter=enter, exit=ex,
                            sun_angle=self.beta_angle_deg(mid)))
                        t = ex + coarse_step
                        prev_lit = self.sunlit_at(t)
                        break
                    te = te2
                else:
                    break
                continue
            prev_lit = lit2
            t = t2
        return out

    def _bisect_eclipse(self, t_lo, t_hi, want_shadow):
        """Refine a sunlit/shadow crossing. want_shadow=True finds the instant
        the satellite enters shadow (sunlit just before t_hi); False finds the
        instant it re-emerges into sunlight."""
        for _ in range(40):
            mid = 0.5 * (t_lo + t_hi)
            lit = self.sunlit_at(mid)
            # we want the boundary where lit transitions; arrange so t_hi is the
            # "after" side. For enter: before=lit, after=shadow.
            if want_shadow:
                if lit:
                    t_lo = mid
                else:
                    t_hi = mid
            else:
                if not lit:
                    t_lo = mid
                else:
                    t_hi = mid
            if t_hi - t_lo < 0.5:
                break
        return 0.5 * (t_lo + t_hi)

    def eclipse_daily_summary(self, frm: float, days: int = 7):
        """Aggregate eclipse periods into per-UTC-day rows.

        Each row is a dict: date (unix at 00:00 of the day), total_s (sum of all
        eclipse durations that day), longest_s, count, percent (of 24 h),
        sun_angle (beta at local noon of that day).
        """
        if not self._have:
            return []
        # gather all eclipses across the window in one sweep
        ecl = self.predict_eclipses(frm, max_n=10000,
                                    horizon_days=float(days))
        # bucket by UTC day of the eclipse-enter time
        day0 = math.floor(frm / 86400.0) * 86400.0
        buckets = {}
        for e in ecl:
            d = math.floor(e.enter / 86400.0) * 86400.0
            buckets.setdefault(d, []).append(e)
        rows = []
        for i in range(days):
            d = day0 + i * 86400.0
            es = buckets.get(d, [])
            total = sum(e.duration_s for e in es)
            longest = max((e.duration_s for e in es), default=0.0)
            rows.append({
                "date": d,
                "total_s": total,
                "longest_s": longest,
                "count": len(es),
                "percent": 100.0 * total / 86400.0,
                "sun_angle": self.beta_angle_deg(d + 43200.0),
            })
        return rows

    # ---- mutual (co-visibility) windows ----
    def mutual_windows(self, frm: float, dx: Observer, min_el: float,
                       max_n: int, horizon_days: int = 10) -> List[MutualWindow]:
        if not self._have:
            return []
        mine = self.predict_passes(frm, min_el, 64,
                                   frm + horizon_days * 86400)
        out: List[MutualWindow] = []
        dt = 10.0
        for p in mine:
            if len(out) >= max_n:
                break
            in_win = False
            w = None
            t = p.aos
            while t <= p.los:
                lat, lon, alt = self.subpoint_at(t)
                my_el = self.azel_at(t)[1]
                dx_el = self.elevation_from_subpoint(dx.lat, dx.lon, dx.alt_m,
                                                     lat, lon, alt)
                both = my_el >= min_el and dx_el >= min_el
                if both:
                    if not in_win:
                        in_win = True
                        w = MutualWindow(start=t, end=t,
                                         my_max_el=my_el, dx_max_el=dx_el)
                    else:
                        w.end = t
                        w.my_max_el = max(w.my_max_el, my_el)
                        w.dx_max_el = max(w.dx_max_el, dx_el)
                elif in_win:
                    out.append(w)
                    in_win = False
                    if len(out) >= max_n:
                        break
                t += dt
            if in_win and len(out) < max_n:
                out.append(w)
        return out


# ---- Maidenhead grid helpers (port of location.cpp) ----
def latlon_to_grid(lat: float, lon: float) -> str:
    lon += 180.0
    lat += 90.0
    g = []
    g.append(chr(ord('A') + int(lon / 20)))
    g.append(chr(ord('A') + int(lat / 10)))
    g.append(chr(ord('0') + int((lon % 20) / 2)))
    g.append(chr(ord('0') + int(lat % 10)))
    g.append(chr(ord('a') + int((lon % 2) * 12)))
    g.append(chr(ord('a') + int((lat % 1) * 24)))
    return ''.join(g)


def grid_to_latlon(grid: str):
    g = grid.strip().upper()
    if len(g) < 4:
        return None
    lon = (ord(g[0]) - ord('A')) * 20 - 180
    lat = (ord(g[1]) - ord('A')) * 10 - 90
    lon += (ord(g[2]) - ord('0')) * 2
    lat += (ord(g[3]) - ord('0')) * 1
    if len(g) >= 6:
        lon += (ord(g[4]) - ord('A')) * (2.0 / 24.0) + 1.0 / 24.0
        lat += (ord(g[5]) - ord('A')) * (1.0 / 24.0) + 0.5 / 24.0
    else:
        lon += 1.0
        lat += 0.5
    return lat, lon


def whos_up(site: Observer, sats, unix: float, min_el: float = 0.0):
    """Scan a list of satellites and return those currently above ``min_el``
    from ``site``, sorted by descending elevation. Mirrors Nova's Quick
    Visibility Check / Who's Up. Each result is a dict with name, norad, az,
    el, range_km, sub_lat, sub_lon, alt_km. A single Predictor is reused across
    the catalog so a full scan stays cheap."""
    out = []
    pred = Predictor()
    pred.set_site(site)
    for s in sats:
        try:
            if not pred.set_sat(s):
                continue
            L = pred.look(unix)
        except Exception:
            continue
        if L.el >= min_el:
            out.append({
                "name": getattr(s, "name", "?"),
                "norad": getattr(s, "norad", 0),
                "az": L.az, "el": L.el, "range_km": L.range_km,
                "sub_lat": L.sub_lat, "sub_lon": L.sub_lon,
                "alt_km": L.alt_km, "sunlit": L.sunlit,
            })
    out.sort(key=lambda d: d["el"], reverse=True)
    return out
