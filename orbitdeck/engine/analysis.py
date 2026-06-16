"""
analysis.py - derived orbital-analysis quantities (J2 secular rates, LTAN,
repeat ground-track, decay estimate, anomaly conversions, beta* threshold).

These mirror the formulas CardSat uses on its Orbital-analysis pages so the
desktop app reports the same numbers. They operate on a SatEntry plus a unix
time; nothing here needs the SGP4 propagator except where noted by the caller.
"""

import math

DEG = math.pi / 180.0
TWO_PI = 2.0 * math.pi
MU = 398600.8                 # km^3/s^2 (WGS72, matches predict.py)
RE_KM = 6378.135
J2 = 0.00108262998905
# rad/s -> deg/day
DPD = 57.29577951308232 * 86400.0


def semi_major_axis_km(mean_motion_revday):
    if mean_motion_revday <= 0:
        return 0.0
    n = mean_motion_revday * TWO_PI / 86400.0      # rad/s
    return (MU / (n * n)) ** (1.0 / 3.0)


def period_min(mean_motion_revday):
    return 1440.0 / mean_motion_revday if mean_motion_revday else 0.0


def footprint_diameter_km(alt_km):
    """Great-circle diameter of the visibility cap for a satellite at alt_km."""
    r = RE_KM + alt_km
    if r <= RE_KM:
        return 0.0
    return 2.0 * RE_KM * math.acos(RE_KM / r)


def beta_star_deg(alt_km):
    """Analytic full-sun threshold beta*: |beta| >= beta* => continuous sun."""
    r = RE_KM + alt_km
    if r <= RE_KM:
        return 0.0
    return math.acos(RE_KM / r) / DEG


def j2_rates(mean_motion_revday, incl_deg, ecc):
    """Return (node_drift, perigee_drift) in deg/day from the J2 secular model."""
    n = mean_motion_revday * TWO_PI / 86400.0          # rad/s
    a = semi_major_axis_km(mean_motion_revday)
    ci = math.cos(incl_deg * DEG)
    p = a * (1.0 - ecc * ecc)
    if p <= 0:
        return 0.0, 0.0
    re_p2 = (RE_KM / p) ** 2
    node = -1.5 * n * J2 * re_p2 * ci * DPD
    perigee = 0.75 * n * J2 * re_p2 * (5 * ci * ci - 1.0) * DPD
    return node, perigee


def is_sun_synchronous(node_drift_degday):
    return abs(node_drift_degday - 0.98565) < 0.05


def ltan_hours(raan_deg, unix_t):
    """Local time of ascending node (hours, 0-24) at unix_t."""
    d = (unix_t - 946728000.0) / 86400.0               # days since J2000
    Ls = 280.460 + 0.9856474 * d
    g = (357.528 + 0.9856003 * d) * DEG
    lam = (Ls + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) * DEG
    eps = 23.439 * DEG
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)) / DEG
    return math.fmod((raan_deg - ra) / 15.0 + 12.0 + 48.0, 24.0)


def repeat_ground_track(mean_motion_revday, max_days=30, tol=0.015):
    """Find a small (revs, days) repeat cycle, or None."""
    best = 1e9
    bp = bq = 0
    for P in range(1, max_days + 1):
        Q = round(mean_motion_revday * P)
        err = abs(mean_motion_revday - Q / P)
        if err < best:
            best = err
            bp, bq = P, Q
    if bp and best < tol:
        return bq, bp
    return None


def longest_possible_pass_min(mean_motion_revday, ecc):
    """Duration (min) of an overhead pass at apogee — the best case."""
    a = semi_major_axis_km(mean_motion_revday)
    r_apo = a * (1.0 + ecc)
    if r_apo <= RE_KM:
        return 0.0
    lam = math.acos(RE_KM / r_apo)
    p = a * (1.0 - ecc * ecc)
    w_apo = math.sqrt(MU * p) / (r_apo * r_apo)        # rad/s at apogee
    if w_apo <= 0:
        return 0.0
    return 2.0 * lam / w_apo / 60.0


def mean_anomaly_now_deg(ma_epoch_deg, mean_motion_revday, unix_t, epoch_unix):
    ma = math.fmod(ma_epoch_deg + 360.0 * mean_motion_revday *
                   (unix_t - epoch_unix) / 86400.0, 360.0)
    return ma + 360.0 if ma < 0 else ma


def true_anomaly_deg(mean_anom_deg, ecc):
    """Equation-of-centre expansion (3 terms) — matches CardSat."""
    M = mean_anom_deg * DEG
    e = ecc
    nu = (M + (2 * e - 0.25 * e ** 3) * math.sin(M)
          + 1.25 * e * e * math.sin(2 * M)
          + (13.0 / 12.0) * e ** 3 * math.sin(3 * M))
    return nu / DEG


def arg_of_latitude_deg(argp_deg, true_anom_deg):
    u = math.fmod(argp_deg + true_anom_deg, 360.0)
    return u + 360.0 if u < 0 else u


def time_to_perigee_apogee_s(mean_anom_now_deg, mean_motion_revday):
    period_s = 86400.0 / mean_motion_revday if mean_motion_revday else 0.0
    to_peri = (360.0 - mean_anom_now_deg) / 360.0 * period_s
    to_apo = math.fmod(180.0 - mean_anom_now_deg + 360.0, 360.0) / 360.0 * period_s
    return to_peri, to_apo


# ---- atmospheric decay (King-Hele style), order-of-magnitude ----
# A compact exponential-atmosphere density table (kg/m^3) by altitude (km).
_ATM = [
    (0, 1.225), (100, 5.6e-7), (150, 2.0e-9), (200, 2.5e-10),
    (250, 6.0e-11), (300, 1.9e-11), (350, 7.0e-12), (400, 2.8e-12),
    (450, 1.2e-12), (500, 5.8e-13), (550, 2.9e-13), (600, 1.6e-13),
    (650, 9.0e-14), (700, 5.2e-14), (800, 1.9e-14), (900, 8.0e-15),
    (1000, 3.6e-15),
]


def _exp_atmosphere(alt_km):
    if alt_km <= 0:
        return _ATM[0][1]
    if alt_km >= _ATM[-1][0]:
        return 0.0
    for i in range(len(_ATM) - 1):
        a0, d0 = _ATM[i]
        a1, d1 = _ATM[i + 1]
        if a0 <= alt_km <= a1:
            # log-linear interpolation
            f = (alt_km - a0) / (a1 - a0)
            return math.exp(math.log(d0) + f * (math.log(d1) - math.log(d0)))
    return 0.0


def estimate_decay_days(bstar, mean_motion_revday, ecc, dens_scale=1.0):
    """King-Hele style reentry estimate. Returns -1 (n/a), 1e9 (stable), or days."""
    if bstar <= 0 or mean_motion_revday <= 0 or dens_scale <= 0:
        return -1.0
    MU_M = 3.986004418e14
    RE_M = 6.378137e6
    TP = TWO_PI
    cd_am = 38.0 * bstar                               # m^2/kg (calibrated)
    nn = mean_motion_revday * TP / 86400.0
    a = (MU_M / (nn * nn)) ** (1.0 / 3.0)
    e = min(max(ecc, 0.0), 0.95)
    rp = a * (1.0 - e)
    ra = a * (1.0 + e)
    t_days = 0.0
    for _ in range(200000):
        hp = rp - RE_M
        if hp < 120e3:
            return t_days
        rho = _exp_atmosphere(hp / 1000.0) * dens_scale
        if rho <= 0:
            return 1e9
        a = 0.5 * (rp + ra)
        T = TP * math.sqrt(a * a * a / MU_M)
        dadt = -2.0 * TP * cd_am * rho * a * a / T
        if dadt >= 0:
            return 1e9
        margin = hp - 120e3
        dt = -(margin * 0.25 + 1000.0) / dadt
        cap = 0.25 if hp < 200e3 else (5.0 if hp < 350e3 else 30.0)
        if dt > cap * 86400.0:
            dt = cap * 86400.0
        if dt < 1.0:
            dt = 1.0
        da = dadt * dt
        ecur = (ra - rp) / (ra + rp)
        if ecur > 1e-3:
            ratio = ra / rp
            ra += 2.0 * da * ratio / (1.0 + ratio)
            rp += 2.0 * da / (1.0 + ratio)
            if ra < rp:
                ra = rp
        else:
            ra += da
            rp += da
        t_days += dt / 86400.0
        if t_days > 36500.0:
            return 1e9
    return t_days


def fmt_decay(days):
    if days < 0:
        return "n/a"
    if days >= 36500:
        return "stable"
    if days < 1:
        return "<1 d"
    if days < 100:
        return "~%d d" % round(days)
    if days < 730:
        return "~%d mo" % round(days / 30.0)
    return "~%.1f yr" % (days / 365.0)


# ---- workable grids: Maidenhead squares inside a footprint ----
def _latlon_to_grid4(lat, lon):
    lon += 180.0
    lat += 90.0
    A_ = ord('A')
    Z0 = ord('0')
    return (chr(A_ + int(lon / 20)) + chr(A_ + int(lat / 10)) +
            chr(Z0 + int((lon % 20) / 2)) + chr(Z0 + int((lat % 10))))


def _angular_sep_deg(lat1, lon1, lat2, lon2):
    p1 = lat1 * DEG
    p2 = lat2 * DEG
    dl = (lon2 - lon1) * DEG
    c = (math.sin(p1) * math.sin(p2) +
         math.cos(p1) * math.cos(p2) * math.cos(dl))
    c = max(-1.0, min(1.0, c))
    return math.acos(c) / DEG


def footprint_radius_deg(alt_km):
    """Angular radius (degrees) of the footprint cap for a satellite altitude."""
    r = RE_KM + alt_km
    if r <= RE_KM:
        return 0.0
    return math.acos(RE_KM / r) / DEG


def elevation_for_central_angle_deg(gamma_deg, alt_km):
    """Elevation angle (degrees) of a satellite at altitude ``alt_km`` as seen
    from a ground station, when the great-circle central angle between the
    station and the sub-satellite point is ``gamma_deg``.

    This is the geometry that turns a QTH-centred OSCARLOCATOR's range rings
    into elevation rings: a ring at ground central angle gamma is the locus
    where the satellite appears at this elevation. Elevation is +90 deg directly
    overhead (gamma=0), 0 deg at the footprint edge, and negative (below the
    horizon) beyond it.
    """
    g = gamma_deg * DEG
    r = RE_KM + alt_km
    if r <= RE_KM:
        return 0.0
    return math.atan2(math.cos(g) - RE_KM / r, math.sin(g)) / DEG


def central_angle_for_elevation_deg(el_deg, alt_km):
    """Inverse of :func:`elevation_for_central_angle_deg`: the great-circle
    central angle (degrees) from the station to the sub-satellite point at which
    a satellite of altitude ``alt_km`` appears at elevation ``el_deg``. Returns
    None if the elevation is unreachable for this altitude.
    """
    r = RE_KM + alt_km
    if r <= RE_KM:
        return None
    e = el_deg * DEG
    # from the law of sines in the station-Earthcentre-satellite triangle:
    #   the spacecraft's nadir/centre angle eta satisfies
    #   sin(eta) = (RE/r) * cos(el); the central angle is gamma = 90-el-eta
    s = (RE_KM / r) * math.cos(e)
    if s < -1.0 or s > 1.0:
        return None
    eta = math.asin(s)
    gamma = math.pi / 2.0 - e - eta
    if gamma < 0:
        return None
    return gamma / DEG


def make_footprint_test(sub_lat, sub_lon, alt_km):
    """Return a predicate in_footprint(lat, lon) -> bool for this footprint."""
    radius = footprint_radius_deg(alt_km)

    def inside(lat, lon):
        return _angular_sep_deg(sub_lat, sub_lon, lat, lon) <= radius
    return inside


def workable_grids(sub_lat, sub_lon, alt_km):
    """Return the sorted set of 4-char Maidenhead grids whose centre lies inside
    the satellite footprint (sub-point + great-circle radius for that altitude).
    Pure geometry; no bundled data. A ~2500 km bird floods a few thousand grids.
    """
    r = RE_KM + alt_km
    if r <= RE_KM:
        return []
    radius_deg = math.acos(RE_KM / r) / DEG     # angular footprint radius
    grids = set()
    # iterate grid-cell centres: 2deg lon x 1deg lat. Bound the lat band to the
    # footprint to keep the scan cheap.
    lat_lo = max(-90.0, sub_lat - radius_deg - 1)
    lat_hi = min(90.0, sub_lat + radius_deg + 1)
    lat = math.floor(lat_lo) + 0.5
    while lat <= lat_hi:
        # longitude half-width of the cap at this latitude (rough bound)
        lon = -179.0
        while lon <= 180.0:
            if _angular_sep_deg(sub_lat, sub_lon, lat, lon) <= radius_deg:
                grids.add(_latlon_to_grid4(lat, lon))
            lon += 2.0
        lat += 1.0
    return sorted(grids)
