"""orbitdeck.engine.zones - orbital environment zones for a satellite.

Answers "where is this bird spending its time": the South Atlantic Anomaly, the
inner and outer radiation belts, the polar caps and eclipse. Reports whether the
satellite is in a zone now, finds the upcoming entry/exit windows, and totals the
dwell time per day.

Ported from CardSat 0.9.75's SCR_SAA ("Orbital zones") with one **deliberate
difference, stated plainly**: CardSat classifies the belts from a real IGRF-14
field with field-line tracing. This uses a *tilted centred-dipole* model for the
McIlwain L shell and B/B0. That is the standard analytic approximation and is
fine for "is this orbit belt-exposed"-class questions, but it will disagree with
IGRF near the belt horns and inside the SAA, where the real field is markedly
non-dipolar. Treat the belt verdicts as indicative, not dosimetry.

The SAA, polar and eclipse zones are geometric and carry no such caveat.
"""

import math

RE_KM = 6371.0

# Geomagnetic (IGRF epoch ~2025) north dipole pole, degrees.
POLE_LAT = 80.7
POLE_LON = -72.7

# Belt shells in McIlwain L, and the B/B0 cutoff that keeps a point near the
# shell's magnetic equator rather than out on its high-latitude horn.
INNER_L = (1.2, 2.5)
OUTER_L = (3.0, 7.0)
BRATIO_MAX = 3.0
BELT_MIN_ALT_KM = 300.0          # below this the atmosphere depletes the flux

ZONES = ["South Atlantic Anomaly", "Inner belt", "Outer belt", "Polar caps",
         "Eclipse"]
ZONE_SAA, ZONE_INNER, ZONE_OUTER, ZONE_POLAR, ZONE_ECLIPSE = range(5)


def magnetic_latitude(lat_deg, lon_deg):
    """Geomagnetic latitude (deg) for a geographic point, tilted-dipole model."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    pl = math.radians(POLE_LAT)
    po = math.radians(POLE_LON)
    sin_mlat = (math.sin(lat) * math.sin(pl)
                + math.cos(lat) * math.cos(pl) * math.cos(lon - po))
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_mlat))))


def shell_l(lat_deg, lon_deg, alt_km):
    """McIlwain L shell (dipole): L = (r/RE) / cos^2(magnetic latitude)."""
    mlat = math.radians(magnetic_latitude(lat_deg, lon_deg))
    r = (RE_KM + alt_km) / RE_KM
    c = math.cos(mlat)
    if abs(c) < 1e-6:
        return 999.0
    return r / (c * c)


def b_ratio(lat_deg, lon_deg, alt_km):
    """B/B0: field strength relative to the minimum on the same field line.

    Dipole form: B/B0 = sqrt(1 + 3 sin^2(mlat)) / cos^6(mlat) * (RE/r)^3 * L^3,
    which reduces to sqrt(1+3sin^2 m)/cos^6 m evaluated on the shell.
    """
    mlat = math.radians(magnetic_latitude(lat_deg, lon_deg))
    c = math.cos(mlat)
    if abs(c) < 1e-6:
        return 1e6
    s = math.sin(mlat)
    return math.sqrt(1.0 + 3.0 * s * s) / (c ** 6)


def saa_centre(unix_t):
    """SAA ellipse centre, drifting ~0.3 deg/yr west from the 2025.0 epoch."""
    import time as _t
    yrs = 0.0
    if unix_t:
        tm = _t.gmtime(unix_t)
        yrs = (tm.tm_year + tm.tm_yday / 365.0) - 2025.0
    return -27.0, -53.0 - 0.30 * yrs


def in_zone(zone, lat_deg, lon_deg, alt_km, sunlit, unix_t=0):
    """True if the sub-satellite point is inside ``zone``."""
    lon = ((lon_deg + 180.0) % 360.0) - 180.0
    if zone == ZONE_SAA:
        c_lat, c_lon = saa_centre(unix_t)
        d_lon = ((lon - c_lon + 180.0) % 360.0) - 180.0
        u = (lat_deg - c_lat) / 25.0
        v = d_lon / 55.0
        return u * u + v * v <= 1.0
    if zone == ZONE_ECLIPSE:
        return not sunlit
    if zone == ZONE_POLAR:
        return abs(lat_deg) >= 60.0
    if zone in (ZONE_INNER, ZONE_OUTER):
        if alt_km < BELT_MIN_ALT_KM:
            return False
        if b_ratio(lat_deg, lon, alt_km) > BRATIO_MAX:
            return False
        shell = shell_l(lat_deg, lon, alt_km)
        lo, hi = INNER_L if zone == ZONE_INNER else OUTER_L
        return lo <= shell <= hi
    return False


def scan_zone(pred, sat, zone, frm, hours=None, step_s=None, max_windows=16):
    """Find upcoming entry/exit windows for ``zone`` and total the dwell.

    Scans roughly four orbits (clamped to 3-36 h), stepping at ~1/200 of an
    orbit, and bisects each boundary crossing to ~2 s. Returns a dict with
    in_now, current L and B/B0, the windows, and dwell minutes per day.
    """
    if not pred.set_sat(sat):
        return {"in_now": False, "windows": [], "dwell_min_day": 0.0,
                "shell_l": 0.0, "b_ratio": 1.0, "scanned_h": 0.0}
    mm = getattr(sat, "mean_motion", 0.0) or 0.0
    period_s = 86400.0 / mm if mm > 0 else 5700.0
    if hours is None:
        window_s = max(3 * 3600.0, min(36 * 3600.0, 4.0 * period_s))
    else:
        window_s = hours * 3600.0
    if step_s is None:
        step_s = max(30.0, min(300.0, period_s / 200.0))

    def at(t):
        lat, lon, alt = pred.subpoint_at(t)
        try:
            sun = pred.sunlit_at(t)
        except Exception:
            sun = True
        return in_zone(zone, lat, lon, alt, sun, t)

    def refine(ta, tb):
        sa = at(ta)
        while tb - ta > 2:
            tm = ta + (tb - ta) / 2.0
            if at(tm) == sa:
                ta = tm
            else:
                tb = tm
        return tb

    lat0, lon0, alt0 = pred.subpoint_at(frm)
    result = {
        "in_now": at(frm),
        "shell_l": shell_l(lat0, lon0, alt0),
        "b_ratio": b_ratio(lat0, lon0, alt0),
        "windows": [],
        "scanned_h": window_s / 3600.0,
    }
    prev = result["in_now"]
    enter = frm if prev else None
    prev_t = frm
    t = frm + step_s
    total = 0.0
    while t <= frm + window_s and len(result["windows"]) < max_windows:
        cur = at(t)
        if cur != prev:
            cross = refine(prev_t, t)
            if cur:
                enter = cross
            elif enter is not None:
                result["windows"].append((enter, cross))
                total += cross - enter
                enter = None
            prev = cur
        prev_t = t
        t += step_s
    if enter is not None:                       # still inside at window end
        result["windows"].append((enter, frm + window_s))
        total += (frm + window_s) - enter
    days = window_s / 86400.0
    result["dwell_min_day"] = (total / 60.0 / days) if days > 0 else 0.0
    return result
