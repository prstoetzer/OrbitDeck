"""orbitdeck.engine.transits - find satellite transits of the Sun and Moon.

A "transit" is when a satellite passes across (or very near) the Sun's or Moon's
disk as seen from the observer - the money shot for satellite astrophotography.
This scans a satellite's visible passes and flags the moments its apparent
position comes within a small angular distance of the Sun or Moon center.

Positions come from the existing propagator (az/el of the satellite) and the
celestial module (az/el of the Sun and Moon), so this needs no new ephemeris.
"""

import math

from .celestial import moon_azel
from .predict import _sun_eci_unit, _gmst_rad, jd_of, DEG

# Apparent angular radius of the disks (degrees); both average ~0.25 deg.
SUN_RADIUS_DEG = 0.266
MOON_RADIUS_DEG = 0.259


def _sun_azel(lat, lon, t):
    """Sun apparent az/el for the observer (matches the Sun/Moon screen)."""
    jd = jd_of(t)
    sx, sy, sz = _sun_eci_unit(jd)
    th = _gmst_rad(jd)
    lst = th + lon * DEG
    ss, cs = math.sin(lst), math.cos(lst)
    slat, clat = math.sin(lat * DEG), math.cos(lat * DEG)
    e = -ss * sx + cs * sy
    n = -slat * cs * sx - slat * ss * sy + clat * sz
    u = clat * cs * sx + clat * ss * sy + slat * sz
    el = math.degrees(math.atan2(u, math.hypot(e, n)))
    az = math.degrees(math.atan2(e, n)) % 360
    return az, el


def _ang_sep_deg(az1, el1, az2, el2):
    """Angular separation between two az/el directions, in degrees."""
    a1, e1 = math.radians(az1), math.radians(el1)
    a2, e2 = math.radians(az2), math.radians(el2)
    cosd = (math.sin(e1) * math.sin(e2)
            + math.cos(e1) * math.cos(e2) * math.cos(a1 - a2))
    cosd = max(-1.0, min(1.0, cosd))
    return math.degrees(math.acos(cosd))


def find_transits(pred, site, sat, frm, hours=72.0, body="both",
                  max_sep_deg=1.0, coarse_s=20.0):
    """Scan for Sun/Moon transits/close approaches over a time window.

    pred  - a Predictor already able to look() the satellite (set_site/set_sat
            are (re)applied here).
    site  - Observer (for the Sun/Moon az/el).
    frm   - start unix time; scans ``hours`` forward.
    body  - "sun", "moon" or "both".
    max_sep_deg - report approaches within this angular distance of a disk center.
    Returns a list of dicts sorted by time:
        {body, time, sep_deg, sat_az, sat_el, body_az, body_el,
         transit (bool, within the disk), sat_range_km}
    Only moments where the satellite is above the horizon and the body is up are
    considered. The closest approach of each distinct encounter is returned (one
    row per approach, not one per sample).
    """
    pred.set_site(site)
    if not pred.set_sat(sat):
        return []
    bodies = ("sun", "moon") if body == "both" else (body,)
    end = frm + hours * 3600.0
    out = {}                                   # body -> current best in an event
    events = []

    t = frm
    prev = {b: None for b in bodies}
    while t <= end:
        try:
            look = pred.look(t)
        except Exception:
            t += coarse_s
            continue
        if look.el < 0:
            # close any open events when the sat sets
            for b in bodies:
                if out.get(b):
                    events.append(out[b])
                    out[b] = None
            prev = {b: None for b in bodies}
            t += coarse_s
            continue
        for b in bodies:
            if b == "sun":
                baz, bel = _sun_azel(site.lat, site.lon, t)
                radius = SUN_RADIUS_DEG
            else:
                baz, bel = moon_azel(site.lat, site.lon, t)
                radius = MOON_RADIUS_DEG
            if bel < 0:                        # body below horizon
                if out.get(b):
                    events.append(out[b])
                    out[b] = None
                prev[b] = None
                continue
            sep = _ang_sep_deg(look.az, look.el, baz, bel)
            if sep <= max_sep_deg:
                rec = {
                    "body": b, "time": t, "sep_deg": sep,
                    "sat_az": look.az, "sat_el": look.el,
                    "body_az": baz, "body_el": bel,
                    "transit": sep <= radius,
                    "sat_range_km": look.range_km,
                }
                cur = out.get(b)
                if cur is None or sep < cur["sep_deg"]:
                    out[b] = rec
            else:
                if out.get(b):
                    events.append(out[b])
                    out[b] = None
            prev[b] = sep
        t += coarse_s
    for b in bodies:                            # flush open events at window end
        if out.get(b):
            events.append(out[b])
    events.sort(key=lambda r: r["time"])
    return events
