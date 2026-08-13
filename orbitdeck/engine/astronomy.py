"""orbitdeck.engine.astronomy - the observing-astronomy set from CardSat 0.9.76.

Meteor showers, Jupiter decametric windows, aurora likelihood, twilight, lunar
occultations and planetary appulses, plus a comet ephemeris. Everything here
runs on the Sun/Moon/planet models already in :mod:`celestial`, so these agree
with the rest of OrbitDeck rather than forming a second opinion.

These are **planning tools, not an almanac**. Contacts land within a few
minutes and magnitudes within a few hundredths, which is enough to decide
whether to set an alarm and not enough to time a grazing occultation.
"""

import math
import time

from .celestial import (jd_of, moon_azel, moon_distance_km, moon_dec_deg,
                        planet_azel, planet_radec, radec_to_azel)

D2R = math.pi / 180.0
R2D = 180.0 / math.pi

# ---------------------------------------------------------------------------
# 1) Meteor showers
# ---------------------------------------------------------------------------
# The eleven major annual showers. A fixed peak date is accurate enough at this
# precision. The radio question is answered per shower: how high the radiant
# sits at 02:00 local - meteor-scatter prime time - and how much the Moon will
# interfere.
SHOWERS = [
    # code, name, month, day, radiant RA deg, radiant Dec deg, ZHR
    ("QUA", "Quadrantids", 1, 3, 230, 49, 110),
    ("LYR", "Lyrids", 4, 22, 271, 34, 18),
    ("ETA", "Eta Aquariids", 5, 6, 338, -1, 50),
    ("SDA", "S d-Aquariids", 7, 30, 339, -16, 25),
    ("PER", "Perseids", 8, 13, 48, 58, 100),
    ("DRA", "Draconids", 10, 8, 262, 54, 10),
    ("ORI", "Orionids", 10, 21, 95, 16, 20),
    ("STA", "S Taurids", 11, 5, 52, 13, 7),
    ("LEO", "Leonids", 11, 17, 152, 22, 15),
    ("GEM", "Geminids", 12, 14, 112, 33, 150),
    ("URS", "Ursids", 12, 22, 217, 76, 10),
]


def moon_illumination(t):
    """Illuminated fraction of the Moon, 0 (new) to 1 (full)."""
    from .celestial import moon_illumination as _mi
    return _mi(t)


def _next_peak(month, day, now):
    """Unix time of the next 02:00 UTC on the shower's peak date."""
    year = time.gmtime(now).tm_year
    for y in (year, year + 1):
        try:
            t = calendar_timegm(y, month, day, 2)
        except ValueError:
            continue
        if t >= now - 12 * 3600:
            return t
    return None


def calendar_timegm(year, month, day, hour=0):
    import calendar
    return float(calendar.timegm((year, month, day, hour, 0, 0, 0, 0, 0)))


def meteor_showers(lat, lon, now=None, limit=None):
    """Every major shower, soonest peak first.

    Each row carries the radiant's elevation at 02:00 on peak night and the
    Moon's illumination, because a 150-ZHR shower under a full Moon with the
    radiant below the horizon is not an opportunity.
    """
    now = now if now is not None else time.time()
    out = []
    for code, name, mon, day, ra, dec, zhr in SHOWERS:
        peak = _next_peak(mon, day, now)
        if peak is None:
            continue
        az, el = radec_to_azel(ra, dec, lat, lon, peak)
        illum = moon_illumination(peak)
        _maz, mel = moon_azel(lat, lon, peak)
        out.append({
            "code": code, "name": name, "peak": peak,
            "days": (peak - now) / 86400.0,
            "ra_deg": float(ra), "dec_deg": float(dec), "zhr": zhr,
            "radiant_az": az, "radiant_el": el,
            "moon_illum": illum, "moon_el": mel,
            "verdict": _meteor_verdict(el, zhr, illum, mel),
        })
    out.sort(key=lambda r: r["days"])
    return out[:limit] if limit else out


def _meteor_verdict(el, zhr, illum, moon_el):
    """What the geometry means for meteor scatter, in words."""
    if el < 0:
        return "radiant below horizon at 02:00 - little scatter here"
    # For MSK144 the useful geometry is a radiant well up but not overhead:
    # forward scatter wants the trails between you and the far station.
    if el > 15 and zhr >= 50:
        base = "strong - high rate with the radiant well up"
    elif el > 15:
        base = "workable - radiant up, modest rate"
    elif zhr >= 50:
        base = "marginal - high rate but the radiant is low"
    else:
        base = "weak - low rate and a low radiant"
    if illum > 0.7 and moon_el > 0:
        base += "; bright Moon up (visual only, radio unaffected)"
    return base


# ---------------------------------------------------------------------------
# 2) Jupiter decametric emission
# ---------------------------------------------------------------------------
# Central meridian longitude (System III) and Io's phase, in the Radio JOVE
# convention. The rates are the physical rotation periods.
def jupiter_cml_io(t):
    """(CML III degrees, Io phase degrees) at time ``t``."""
    d = jd_of(t) - 2451545.0
    cml = (284.95 + 870.5360000 * d) % 360.0
    io = (342.86 + 203.4889538 * d) % 360.0
    return cml, io


# The classic Io-controlled storm sources, as (CML range, Io-phase range).
JOVE_SOURCES = [
    ("Io-A", (200, 270), (200, 270)),
    ("Io-B", (105, 190), (75, 105)),
    ("Io-C", (300, 20), (225, 260)),
]


def _in_range(value, lo, hi):
    if lo <= hi:
        return lo <= value <= hi
    return value >= lo or value <= hi          # wraps through 360


def jupiter_status(lat, lon, t=None):
    """Current CML/Io phase, which source is active, and whether Jupiter is up."""
    t = t if t is not None else time.time()
    cml, io = jupiter_cml_io(t)
    az, el = planet_azel("Jupiter", lat, lon, t)
    active = [n for n, c, i in JOVE_SOURCES
              if _in_range(cml, *c) and _in_range(io, *i)]
    return {
        "cml_deg": cml, "io_phase_deg": io,
        "az": az, "el": el, "up": el > 0,
        "active": active,
        "verdict": ("%s active%s" % (", ".join(active),
                                     "" if el > 0 else " but Jupiter is down"))
        if active else ("no Io source active"
                        + ("" if el > 0 else "; Jupiter is down")),
    }


def jupiter_windows(lat, lon, t=None, hours=48, step_min=10):
    """Io-source windows in the next ``hours`` with Jupiter above the horizon.

    A storm you cannot hear is not a window, so a source is only reported when
    Jupiter is actually up.
    """
    t = t if t is not None else time.time()
    out = []
    cur = None
    steps = int(hours * 60 / step_min)
    for i in range(steps + 1):
        tt = t + i * step_min * 60
        cml, io = jupiter_cml_io(tt)
        _az, el = planet_azel("Jupiter", lat, lon, tt)
        names = [n for n, c, ip in JOVE_SOURCES
                 if _in_range(cml, *c) and _in_range(io, *ip)] if el > 0 else []
        name = names[0] if names else None
        if name and cur and cur["source"] == name:
            cur["end"] = tt
            cur["max_el"] = max(cur["max_el"], el)
        elif name:
            if cur:
                out.append(cur)
            cur = {"source": name, "start": tt, "end": tt, "max_el": el}
        elif cur:
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return [w for w in out if w["end"] > w["start"]]


# ---------------------------------------------------------------------------
# 3) Aurora
# ---------------------------------------------------------------------------
# Geomagnetic dipole pole, so magnetic latitude is what the boundary is
# actually measured against - geographic latitude would put the UK and
# Labrador in the same place, which they are not for aurora.
MAG_POLE_LAT = 80.65
MAG_POLE_LON = -72.68


def magnetic_latitude(lat, lon):
    """Dipole magnetic latitude in degrees."""
    la, lo = lat * D2R, lon * D2R
    pla, plo = MAG_POLE_LAT * D2R, MAG_POLE_LON * D2R
    ca = (math.sin(pla) * math.sin(la)
          + math.cos(pla) * math.cos(la) * math.cos(lo - plo))
    return math.degrees(math.asin(max(-1.0, min(1.0, ca))))


def aurora_outlook(lat, lon, kp=None):
    """Whether the auroral oval is likely to reach this location.

    The oval's equatorward boundary sits near 66.5 - 2*Kp degrees magnetic.
    """
    mlat = magnetic_latitude(lat, lon)
    if kp is None:
        return {"mag_lat": mlat, "kp": None, "boundary": None,
                "visual": "no Kp available", "radio": "no Kp available"}
    boundary = 66.5 - 2.0 * float(kp)
    margin = abs(mlat) - boundary
    if margin >= 3:
        visual = "likely overhead"
    elif margin >= 0:
        visual = "likely on the poleward horizon"
    elif margin >= -5:
        visual = "possible low on the horizon under a strong substorm"
    else:
        visual = "unlikely at this latitude"
    # Auroral-E propagation reaches further equatorward than the visual oval.
    radio = ("auroral scatter likely on 6 m and 2 m" if margin >= -8
             else "auroral scatter unlikely")
    return {"mag_lat": mlat, "kp": float(kp), "boundary": boundary,
            "margin": margin, "visual": visual, "radio": radio}


# ---------------------------------------------------------------------------
# 4) Twilight
# ---------------------------------------------------------------------------
TWILIGHTS = [("Sunrise/sunset", -0.833), ("Civil", -6.0),
             ("Nautical", -12.0), ("Astronomical", -18.0)]


def _sun_el(lat, lon, t):
    from .transits import _sun_azel
    return _sun_azel(lat, lon, t)[1]


def twilight_times(lat, lon, day_start=None, step_min=5):
    """Sun-elevation crossings over 24 hours, refined by interpolation.

    Returns rows of (label, altitude, morning unix or None, evening or None).
    A polar day or night simply has no crossing, which is reported rather than
    hidden.
    """
    t0 = day_start if day_start is not None else _utc_midnight(time.time())
    n = int(24 * 60 / step_min)
    samples = [(t0 + i * step_min * 60,
                _sun_el(lat, lon, t0 + i * step_min * 60)) for i in range(n + 1)]
    out = []
    for label, alt in TWILIGHTS:
        morning = evening = None
        for i in range(len(samples) - 1):
            (ta, ea), (tb, eb) = samples[i], samples[i + 1]
            if (ea - alt) == 0 or (ea - alt) * (eb - alt) < 0:
                frac = (alt - ea) / (eb - ea) if eb != ea else 0.0
                cross = ta + frac * (tb - ta)
                if eb > ea and morning is None:
                    morning = cross
                elif eb < ea:
                    evening = cross
        out.append({"label": label, "altitude": alt,
                    "morning": morning, "evening": evening})
    return out


def _utc_midnight(t):
    tm = time.gmtime(t)
    return calendar_timegm(tm.tm_year, tm.tm_mon, tm.tm_mday, 0)


# ---------------------------------------------------------------------------
# 5) EME conditions
# ---------------------------------------------------------------------------
def eme_conditions(t=None, days=30, step_h=6):
    """Moon distance now against its perigee and apogee over the coming month.

    Path loss goes as the fourth power of range for a two-way path, so the
    perigee-to-apogee swing is worth about 2 dB - the difference between a
    marginal schedule and a comfortable one.
    """
    t = t if t is not None else time.time()
    now_km = moon_distance_km(t)
    steps = int(days * 24 / step_h)
    dists = [(t + i * step_h * 3600, moon_distance_km(t + i * step_h * 3600))
             for i in range(steps + 1)]
    tp, per = min(dists, key=lambda r: r[1])
    ta, apo = max(dists, key=lambda r: r[1])
    return {
        "distance_km": now_km,
        "perigee_km": per, "perigee_time": tp,
        "apogee_km": apo, "apogee_time": ta,
        # 40 log10 because the path is traversed twice.
        "degradation_db": 40.0 * math.log10(now_km / per),
        "swing_db": 40.0 * math.log10(apo / per),
        "declination_deg": moon_dec_deg(t),
    }


# ---------------------------------------------------------------------------
# 6) Lunar occultations
# ---------------------------------------------------------------------------
# Bright stars near the ecliptic - the only ones the Moon can occult.
ZODIACAL_STARS = [
    ("Aldebaran", 68.98, 16.51, 0.85),
    ("Regulus", 152.09, 11.97, 1.35),
    ("Spica", 201.30, -11.16, 0.97),
    ("Antares", 247.35, -26.43, 1.09),
    ("Pollux", 116.33, 28.03, 1.14),
    ("Beta Scorpii", 241.36, -19.81, 2.56),
    ("Delta Scorpii", 240.08, -22.62, 2.29),
    ("Zubenelgenubi", 222.72, -16.04, 2.75),
]
OCCULT_PLANETS = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]


def _moon_semidiameter_deg(t):
    """Apparent lunar radius - the occultation threshold."""
    return math.degrees(math.asin(1737.4 / max(1.0, moon_distance_km(t))))


def _ang_sep(ra1, dec1, ra2, dec2):
    a1, d1 = ra1 * D2R, dec1 * D2R
    a2, d2 = ra2 * D2R, dec2 * D2R
    c = (math.sin(d1) * math.sin(d2)
         + math.cos(d1) * math.cos(d2) * math.cos(a1 - a2))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def _moon_radec(t):
    from .celestial import _moon_eci_unit
    x, y, z = _moon_eci_unit(jd_of(t))
    ra = math.degrees(math.atan2(y, x)) % 360.0
    dec = math.degrees(math.asin(max(-1.0, min(1.0, z))))
    return ra, dec


def occultations(lat, lon, t=None, days=365, step_h=3):
    """Lunar occultations of bright zodiacal stars and planets.

    Reported only when the Moon is above the horizon: an occultation below
    your horizon is someone else's event.
    """
    t = t if t is not None else time.time()
    hits = []
    steps = int(days * 24 / step_h)
    targets = [(n, ra, dec, mag, None) for n, ra, dec, mag in ZODIACAL_STARS]
    for i in range(steps):
        tt = t + i * step_h * 3600
        mra, mdec = _moon_radec(tt)
        sd = _moon_semidiameter_deg(tt)
        for name, ra, dec, mag, _p in targets:
            if _ang_sep(mra, mdec, ra, dec) < sd + 1.0:
                _az, el = moon_azel(lat, lon, tt)
                if el > 0:
                    hits.append({"target": name, "kind": "star", "mag": mag,
                                 "time": tt, "moon_el": el,
                                 "separation_deg": _ang_sep(mra, mdec, ra, dec),
                                 "semidiameter_deg": sd})
        for pname in OCCULT_PLANETS:
            pra, pdec = planet_radec(pname, tt)
            if pra is None:
                continue
            sep = _ang_sep(mra, mdec, pra, pdec)
            if sep < sd + 1.0:
                _az, el = moon_azel(lat, lon, tt)
                if el > 0:
                    hits.append({"target": pname, "kind": "planet", "mag": None,
                                 "time": tt, "moon_el": el,
                                 "separation_deg": sep,
                                 "semidiameter_deg": sd})
    # Collapse runs into one approach, then REFINE it. A 3-hour step lands
    # wherever it lands: the coarse scan reported 1.05 deg against a 0.27 deg
    # limb and called it an occultation, when the true minimum was hours away.
    coarse = []
    for h in sorted(hits, key=lambda r: r["time"]):
        if coarse and h["target"] == coarse[-1]["target"] and \
                h["time"] - coarse[-1]["time"] < 12 * 3600:
            if h["separation_deg"] < coarse[-1]["separation_deg"]:
                coarse[-1] = h
            continue
        coarse.append(h)

    out = []
    for h in coarse:
        best = _refine_approach(h["target"], h["kind"], h["time"],
                                step_h * 3600, lat, lon)
        if best is None:
            continue
        # Only a separation inside the lunar limb is an occultation; the rest
        # are close approaches, which are worth seeing but are not the same
        # event and must not be labeled as one.
        best["occultation"] = best["separation_deg"] < best["semidiameter_deg"]
        if best["occultation"] or best["separation_deg"] < 1.0:
            out.append(best)
    out.sort(key=lambda r: r["time"])
    return out


def _refine_approach(target, kind, t_mid, half_window, lat, lon):
    """Find the true minimum separation near a coarse hit."""
    best = None
    span = max(3600.0, half_window)
    step = 120.0
    n = int(2 * span / step)
    for i in range(n + 1):
        tt = t_mid - span + i * step
        mra, mdec = _moon_radec(tt)
        if kind == "star":
            row = next((r for r in ZODIACAL_STARS if r[0] == target), None)
            if row is None:
                return None
            ra, dec, mag = row[1], row[2], row[3]
        else:
            ra, dec = planet_radec(target, tt)
            mag = None
            if ra is None:
                return None
        sep = _ang_sep(mra, mdec, ra, dec)
        if best is None or sep < best["separation_deg"]:
            _az, el = moon_azel(lat, lon, tt)
            best = {"target": target, "kind": kind, "mag": mag, "time": tt,
                    "moon_el": el, "separation_deg": sep,
                    "semidiameter_deg": _moon_semidiameter_deg(tt)}
    # An event below the horizon is someone else's.
    if best is not None and best["moon_el"] <= 0:
        return None
    return best


# ---------------------------------------------------------------------------
# 7) Planetary appulses (close pairings)
# ---------------------------------------------------------------------------
APPULSE_BODIES = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]


def appulses(t=None, days=365, step_h=12, max_sep=2.0):
    """Close pairings of the planets and the Moon, within ``max_sep`` degrees.

    Named appulse rather than conjunction to keep it clear of the satellite
    conjunction screener, which answers a different question entirely.
    """
    t = t if t is not None else time.time()
    steps = int(days * 24 / step_h)
    pairs = []
    names = APPULSE_BODIES + ["Moon"]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            pairs.append((names[i], names[j]))
    events = {}
    for s in range(steps):
        tt = t + s * step_h * 3600
        pos = {}
        for n in APPULSE_BODIES:
            ra, dec = planet_radec(n, tt)
            if ra is not None:
                pos[n] = (ra, dec)
        pos["Moon"] = _moon_radec(tt)
        for a, b in pairs:
            if a not in pos or b not in pos:
                continue
            sep = _ang_sep(pos[a][0], pos[a][1], pos[b][0], pos[b][1])
            if sep >= max_sep:
                continue
            key = (a, b)
            prev = events.get(key)
            if prev is None or tt - prev["time"] > 20 * 86400:
                events[key + (s,)] = {"a": a, "b": b, "time": tt,
                                      "separation_deg": sep}
                events[key] = events[key + (s,)]
            elif sep < prev["separation_deg"]:
                prev["time"] = tt
                prev["separation_deg"] = sep
    out = [v for k, v in events.items() if len(k) == 3]
    out.sort(key=lambda r: r["time"])
    return out


# ---------------------------------------------------------------------------
# 8) Comet position
# ---------------------------------------------------------------------------
def comet_position(q_au, ecc, incl_deg, node_deg, argp_deg, tp_days,
                   lat=None, lon=None, t=None):
    """Position of a comet from its orbital elements.

    ``tp_days`` is days since perihelion (negative before). Elliptical orbits
    solve Kepler's equation; parabolic ones use Barker's closed form, because
    Kepler's equation degenerates at e = 1 and a comet at e = 0.9999 is common.
    """
    t = t if t is not None else time.time()
    k = 0.01720209895                      # Gaussian gravitational constant
    if abs(ecc - 1.0) < 1e-8:
        # Barker's equation: parabolic, closed form.
        w = 3.0 * k * tp_days / (math.sqrt(2.0) * q_au ** 1.5)
        y = (w + math.sqrt(w * w + 1.0)) ** (1.0 / 3.0)
        tan_half = y - 1.0 / y
        nu = 2.0 * math.atan(tan_half)
        r = q_au * (1.0 + tan_half * tan_half)
    elif ecc < 1.0:
        a = q_au / (1.0 - ecc)
        n = k / a ** 1.5
        M = n * tp_days
        E = M if ecc < 0.8 else math.pi
        for _ in range(60):
            dE = (E - ecc * math.sin(E) - M) / (1.0 - ecc * math.cos(E))
            E -= dE
            if abs(dE) < 1e-12:
                break
        nu = 2.0 * math.atan2(math.sqrt(1 + ecc) * math.sin(E / 2),
                              math.sqrt(1 - ecc) * math.cos(E / 2))
        r = a * (1.0 - ecc * math.cos(E))
    else:
        a = q_au / (ecc - 1.0)
        n = k / a ** 1.5
        M = n * tp_days
        H = math.asinh(M / max(1e-9, ecc))
        for _ in range(80):
            dH = (ecc * math.sinh(H) - H - M) / (ecc * math.cosh(H) - 1.0)
            H -= dH
            if abs(dH) < 1e-12:
                break
        nu = 2.0 * math.atan2(math.sqrt(ecc + 1) * math.sinh(H / 2),
                              math.sqrt(ecc - 1) * math.cosh(H / 2))
        r = a * (ecc * math.cosh(H) - 1.0)

    u = nu + argp_deg * D2R
    i = incl_deg * D2R
    om = node_deg * D2R
    xh = r * (math.cos(om) * math.cos(u)
              - math.sin(om) * math.sin(u) * math.cos(i))
    yh = r * (math.sin(om) * math.cos(u)
              + math.cos(om) * math.sin(u) * math.cos(i))
    zh = r * (math.sin(u) * math.sin(i))

    # Earth's heliocentric position, from the same model the planets use.
    from .celestial import _helio_xyz, _PLANETS
    ex, ey, ez = _helio_xyz(_PLANETS["Earth"], t) if "Earth" in _PLANETS \
        else _earth_xyz(t)
    gx, gy, gz = xh - ex, yh - ey, zh - ez
    delta = math.sqrt(gx * gx + gy * gy + gz * gz)

    eps = 23.4393 * D2R
    xq = gx
    yq = gy * math.cos(eps) - gz * math.sin(eps)
    zq = gy * math.sin(eps) + gz * math.cos(eps)
    ra = math.degrees(math.atan2(yq, xq)) % 360.0
    dec = math.degrees(math.asin(max(-1.0, min(1.0, zq / max(1e-9, delta)))))

    sun_dist = math.sqrt(ex * ex + ey * ey + ez * ez)
    cos_elong = ((sun_dist ** 2 + delta ** 2 - r ** 2)
                 / max(1e-9, 2 * sun_dist * delta))
    elong = math.degrees(math.acos(max(-1.0, min(1.0, cos_elong))))

    out = {"r_au": r, "delta_au": delta, "ra_deg": ra, "dec_deg": dec,
           "elongation_deg": elong, "true_anomaly_deg": math.degrees(nu)}
    if lat is not None and lon is not None:
        az, el = radec_to_azel(ra, dec, lat, lon, t)
        out["az"] = az
        out["el"] = el
    return out


def _earth_xyz(t):
    """Earth's heliocentric position, if the planet table lacks it."""
    d = jd_of(t) - 2451545.0
    L = (280.461 + 0.9856474 * d) % 360.0
    g = (357.528 + 0.9856003 * d) % 360.0
    lam = (L + 1.915 * math.sin(g * D2R)
           + 0.020 * math.sin(2 * g * D2R)) % 360.0
    r = 1.00014 - 0.01671 * math.cos(g * D2R) - 0.00014 * math.cos(2 * g * D2R)
    # Sun as seen from Earth, negated: Earth as seen from the Sun.
    return (-r * math.cos(lam * D2R), -r * math.sin(lam * D2R), 0.0)


# ---------------------------------------------------------------------------
# 9) Eclipses
# ---------------------------------------------------------------------------
# Solar and lunar eclipses for one location, on the same Sun and Moon models
# the Sun/Moon screen uses. Method, following CardSat 0.9.76:
#
#   * a coarse elongation scan finds syzygies, refined to about a minute;
#   * SOLAR candidates get a TOPOCENTRIC scan - the Moon's ~1 degree parallax
#     IS the locality of a solar eclipse - and are recorded only when the Sun
#     is actually up;
#   * LUNAR candidates use geocentric shadow geometry with Danjon's 2%
#     enlarged umbra, and are recorded always with a visibility flag, because a
#     lunar eclipse is the same event for everyone who can see the Moon.
#
# Accuracy is the model's: contacts to a few minutes, magnitudes to about
# 0.05. A planning tool, not an almanac.
ECL_PENUMBRAL, ECL_PARTIAL, ECL_TOTAL = 0, 1, 2
ECL_CLASS_NAMES = {0: "penumbral", 1: "partial", 2: "total"}
_RE_KM = 6378.137
_R_SUN_KM = 696000.0
_R_MOON_KM = 1737.4


def _sun_eq_km(t):
    """Geocentric equatorial vector to the Sun, km."""
    d = jd_of(t) - 2451545.0
    L = (280.461 + 0.9856474 * d) % 360.0
    g = (357.528 + 0.9856003 * d) % 360.0
    lam = (L + 1.915 * math.sin(g * D2R) + 0.020 * math.sin(2 * g * D2R))
    r_au = 1.00014 - 0.01671 * math.cos(g * D2R) \
        - 0.00014 * math.cos(2 * g * D2R)
    r = r_au * 149597870.7
    eps = 23.4393 * D2R
    return (r * math.cos(lam * D2R),
            r * math.sin(lam * D2R) * math.cos(eps),
            r * math.sin(lam * D2R) * math.sin(eps))


def _moon_eq_km(t):
    """Geocentric equatorial vector to the Moon, km."""
    from .celestial import _moon_eci_unit
    x, y, z = _moon_eci_unit(jd_of(t))
    d = moon_distance_km(t)
    return (x * d, y * d, z * d)


def _vec_angle(ax, ay, az, bx, by, bz):
    na = math.sqrt(ax * ax + ay * ay + az * az)
    nb = math.sqrt(bx * bx + by * by + bz * bz)
    if na <= 0 or nb <= 0:
        return math.pi
    c = (ax * bx + ay * by + az * bz) / (na * nb)
    return math.acos(max(-1.0, min(1.0, c)))


def _elongation(t):
    sx, sy, sz = _sun_eq_km(t)
    mx, my, mz = _moon_eq_km(t)
    return _vec_angle(sx, sy, sz, mx, my, mz)


def eclipses(lat, lon, t=None, days=730, step_h=3):
    """Solar and lunar eclipses for this location over the coming ~2 years."""
    t = t if t is not None else time.time()
    out = []
    step = step_h * 3600
    # Start two steps in the past: a syzygy within the first few hours cannot
    # be bracketed otherwise, and CardSat's harness caught exactly that. Fully
    # past events are dropped at the end.
    n = int(days * 24 / step_h) + 2
    prev = _elongation(t - 2 * step)
    cur = _elongation(t - step)
    for i in range(n):
        tt = t + i * step
        nxt = _elongation(tt + step)
        is_min = cur < prev and cur < nxt          # new moon: solar candidate
        is_max = cur > prev and cur > nxt          # full moon: lunar candidate
        # `cur` is the elongation at tt - step, so the extremum must be
        # bracketed by [tt - 2*step, tt]. Bracketing [tt-step, tt+step] put the
        # extremum on the window edge and the refinement then walked to the
        # wrong minute - the Aug 2026 lunar eclipse came out 39 hours late.
        syz = _refine_syzygy(tt - 2 * step, step, minimum=is_min) \
            if (is_min or is_max) else None
        if syz is not None and is_min and cur < 1.6 * D2R:
            ev = _solar_eclipse(lat, lon, syz)
            if ev:
                out.append(ev)
        elif syz is not None and is_max and (math.pi - cur) < 1.6 * D2R:
            ev = _lunar_eclipse(lat, lon, syz)
            if ev:
                out.append(ev)
        prev, cur = cur, nxt
    # Drop what is entirely over: the past-bracket start can legitimately find
    # yesterday's eclipse.
    out = [e for e in out if e.get("end", e["max_time"]) >= t]
    out.sort(key=lambda e: e["max_time"])
    return out


def _refine_syzygy(t0, step, minimum=True, iters=40):
    """Ternary search for the elongation extremum, to about a minute."""
    lo, hi = t0, t0 + 2 * step
    for _ in range(iters):
        if hi - lo < 60:
            break
        a = lo + (hi - lo) / 3.0
        b = hi - (hi - lo) / 3.0
        ea, eb = _elongation(a), _elongation(b)
        if (ea < eb) == minimum:
            hi = b
        else:
            lo = a
    return (lo + hi) / 2.0


def _solar_eclipse(lat, lon, syz):
    """Topocentric solar eclipse test around a new moon.

    Topocentric because the Moon's roughly one-degree parallax is precisely
    what makes a solar eclipse local: geocentric geometry would report the
    same eclipse for everyone on Earth, which is the opposite of the truth.
    """
    from .transits import _sun_azel
    best = None
    t1 = t4 = None
    for k in range(-150, 151):                       # +/-5 h at 2 min
        u = syz + k * 120
        sx, sy, sz = _sun_eq_km(u)
        mx, my, mz = _moon_eq_km(u)
        ox, oy, oz = _observer_eq_km(lat, lon, u)
        # from the observer, not the geocenter
        sep = _vec_angle(sx - ox, sy - oy, sz - oz,
                         mx - ox, my - oy, mz - oz)
        dS = math.sqrt((sx - ox) ** 2 + (sy - oy) ** 2 + (sz - oz) ** 2)
        dM = math.sqrt((mx - ox) ** 2 + (my - oy) ** 2 + (mz - oz) ** 2)
        s_sun = math.asin(min(1.0, _R_SUN_KM / dS))
        s_moon = math.asin(min(1.0, _R_MOON_KM / dM))
        if sep < s_sun + s_moon:
            _az, el = _sun_azel(lat, lon, u)
            if el < -0.5:
                continue                             # below the horizon here
            if t1 is None:
                t1 = u
            t4 = u
            # Magnitude: fraction of the solar diameter covered.
            mag = (s_sun + s_moon - sep) / (2.0 * s_sun)
            if best is None or mag > best["magnitude"]:
                cls = ECL_TOTAL if sep < abs(s_moon - s_sun) else ECL_PARTIAL
                best = {"kind": "solar", "max_time": u, "magnitude": mag,
                        "class": cls, "elevation": el}
    if best is None:
        return None
    best.update({"start": t1, "end": t4, "visible": True,
                 "class_name": ECL_CLASS_NAMES[best["class"]]})
    return best


def _lunar_eclipse(lat, lon, syz):
    """Geocentric shadow geometry with Danjon's 2% enlarged umbra."""
    best = None
    t1 = t4 = None
    any_up = False
    cls = None
    for k in range(-120, 121):                       # +/-4 h at 2 min
        u = syz + k * 120
        sx, sy, sz = _sun_eq_km(u)
        mx, my, mz = _moon_eq_km(u)
        dM = math.sqrt(mx * mx + my * my + mz * mz)
        dS = math.sqrt(sx * sx + sy * sy + sz * sz)
        sep = _vec_angle(-sx, -sy, -sz, mx, my, mz)  # Moon vs the anti-Sun
        pm = math.asin(min(1.0, _RE_KM / dM))        # lunar parallax
        ps = math.asin(min(1.0, _RE_KM / dS))        # solar parallax
        s_sun = math.asin(min(1.0, _R_SUN_KM / dS))
        s_moon = math.asin(min(1.0, _R_MOON_KM / dM))
        # Danjon's empirical 2% enlargement of the Earth's shadow.
        r_u = 1.02 * (0.998340 * pm - s_sun + ps)
        r_p = 1.02 * (0.998340 * pm + s_sun + ps)
        if sep < r_u - s_moon:
            c = ECL_TOTAL
        elif sep < r_u + s_moon:
            c = ECL_PARTIAL
        elif sep < r_p + s_moon:
            c = ECL_PENUMBRAL
        else:
            continue
        if t1 is None:
            t1 = u
        t4 = u
        _maz, mel = moon_azel(lat, lon, u)
        if mel > 0:
            any_up = True
        # Umbral magnitude, the figure almanacs quote.
        mag = (r_u + s_moon - sep) / (2.0 * s_moon)
        if best is None or mag > best["magnitude"]:
            best = {"kind": "lunar", "max_time": u, "magnitude": mag,
                    "elevation": mel}
        # Keep the DEEPEST class seen. CardSat's harness caught the old form
        # keeping the shallowest, which called a total eclipse penumbral.
        if cls is None or c > cls:
            cls = c
    if best is None:
        return None
    best.update({"start": t1, "end": t4, "visible": any_up,
                 "class": cls if cls is not None else ECL_PENUMBRAL})
    best["class_name"] = ECL_CLASS_NAMES[best["class"]]
    return best


def _observer_eq_km(lat, lon, t):
    """Observer's geocentric equatorial position, km."""
    from .celestial import _gmst_rad
    la = lat * D2R
    theta = _gmst_rad(jd_of(t)) + lon * D2R
    # spherical Earth is plenty at this precision
    r = _RE_KM
    return (r * math.cos(la) * math.cos(theta),
            r * math.cos(la) * math.sin(theta),
            r * math.sin(la))


def eclipse_axis_ground(t):
    """Where the Moon's shadow axis meets the Earth, or None.

    The axis runs from the Sun through the Moon; the near root of its
    intersection with the Earth sphere is the point of greatest eclipse at that
    instant. No intersection means the axis misses the Earth entirely - which
    is exactly what a partial-only eclipse is, and must be reported as "no
    central line" rather than as an empty map.
    """
    sx, sy, sz = _sun_eq_km(t)
    mx, my, mz = _moon_eq_km(t)
    dx, dy, dz = mx - sx, my - sy, mz - sz
    dm = math.sqrt(dx * dx + dy * dy + dz * dz)
    if dm <= 0:
        return None
    dx, dy, dz = dx / dm, dy / dm, dz / dm
    re = 6371.0
    b = mx * dx + my * dy + mz * dz
    c = mx * mx + my * my + mz * mz - re * re
    disc = b * b - c
    if disc < 0:
        return None                       # the axis misses the Earth
    s = -b - math.sqrt(disc)              # near root
    px, py, pz = mx + s * dx, my + s * dy, mz + s * dz
    from .celestial import _gmst_rad
    gmst = math.degrees(_gmst_rad(jd_of(t)))
    lat = math.degrees(math.asin(max(-1.0, min(1.0, pz / re))))
    lon = math.degrees(math.atan2(py, px)) - gmst
    lon = ((lon + 180.0) % 360.0) - 180.0
    return lat, lon


def eclipse_ground_track(event, hours=3.0, step_s=180):
    """The central line of a solar eclipse, as (lat, lon) segments.

    Segments, not one polyline: the track crosses the date line and joining
    those points would draw a stripe straight across the map. Empty when the
    shadow axis never touches the Earth - a partial-only eclipse has no
    central line, and drawing nothing with no explanation looks like a bug.
    """
    if not event or event.get("kind") != "solar":
        return []
    t_max = event["max_time"]
    pts = []
    for k in range(int(-hours * 3600 / step_s), int(hours * 3600 / step_s) + 1):
        g = eclipse_axis_ground(t_max + k * step_s)
        pts.append((t_max + k * step_s, g))
    segments = []
    cur = []
    prev_lon = None
    for _t, g in pts:
        if g is None:
            if len(cur) > 1:
                segments.append(cur)
            cur = []
            prev_lon = None
            continue
        lat, lon = g
        if prev_lon is not None and abs(lon - prev_lon) > 180.0:
            if len(cur) > 1:
                segments.append(cur)
            cur = []
        cur.append((lat, lon))
        prev_lon = lon
    if len(cur) > 1:
        segments.append(cur)
    return segments


def eclipse_track_summary(event):
    """One honest line about what the track shows."""
    if not event or event.get("kind") != "solar":
        return "Lunar eclipses have no ground track: the Earth's shadow " \
               "falls on the Moon, not the other way round."
    segs = eclipse_ground_track(event)
    if not segs:
        return "Partial-only from Earth: the shadow axis misses the planet, " \
               "so there is no central line to draw."
    n = sum(len(s) for s in segs)
    first = segs[0][0]
    last = segs[-1][-1]
    return ("Central line %d pts: %.0f%s %.0f%s \u2192 %.0f%s %.0f%s" % (
        n, abs(first[0]), "N" if first[0] >= 0 else "S",
        abs(first[1]), "E" if first[1] >= 0 else "W",
        abs(last[0]), "N" if last[0] >= 0 else "S",
        abs(last[1]), "E" if last[1] >= 0 else "W"))
