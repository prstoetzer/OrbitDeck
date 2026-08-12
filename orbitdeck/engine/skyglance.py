"""orbitdeck.engine.skyglance - all-favorites pass timeline, and AO-7 status.

Two small pass-derived features from CardSat 0.9.75:

  * ``sky_glance`` - one row per favorite satellite, each carrying its upcoming
    passes over the next N hours as (start, end, max elevation) bars. That is the
    "what is my sky doing this evening" view: a timeline rather than a list.
  * ``ao7_illumination`` - AO-7 has no batteries, so it runs directly off its
    solar panels and its 24-hour timer only alternates Mode A/B while the
    spacecraft is in **continuous sunlight**; when it eclipses, the mode instead
    follows power and resets each orbit. This reports beta angle, the eclipse
    fraction over one orbit, and that verdict.

    Note: CardSat additionally *estimates the current mode phase* by fetching a
    month of AMSAT status reports. That crowd-sourced estimate is **not**
    included here - this is the offline illumination determination only, which
    is what tells you whether the timer is running at all.
"""

import math


def sky_glance(pred, site, sats, frm, hours=12.0, min_el=5.0, max_sats=20):
    """Upcoming passes for each satellite, as timeline rows.

    Returns a list of dicts sorted by first AOS:
        {name, norad, passes: [(aos, los, max_el), ...]}
    Satellites with no pass in the window are included with an empty list so the
    timeline shows them as quiet rather than dropping them.
    """
    pred.set_site(site)
    end = frm + hours * 3600.0
    rows = []
    for s in list(sats)[:max_sats]:
        try:
            if not pred.set_sat(s):
                continue
            passes = pred.predict_passes(frm, min_el, 60, end)
        except Exception:
            continue
        bars = []
        for p in passes:
            if p.aos > end:
                break
            bars.append((max(p.aos, frm), min(p.los, end),
                         getattr(p, "max_el", 0.0)))
        rows.append({"name": getattr(s, "name", "?"),
                     "norad": getattr(s, "norad", 0),
                     "passes": bars})
    rows.sort(key=lambda r: (r["passes"][0][0] if r["passes"] else float("inf")))
    return rows


def busiest_gap(rows, frm, hours=12.0):
    """Longest stretch in the window with no pass from any satellite.

    Returns (start, end) or None. Useful for "when can I go to dinner".
    """
    spans = sorted((a, b) for r in rows for a, b, _e in r["passes"])
    if not spans:
        return (frm, frm + hours * 3600.0)
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    end = frm + hours * 3600.0
    best = None
    prev = frm
    for a, b in merged:
        if a - prev > (0 if best is None else best[1] - best[0]):
            best = (prev, a)
        prev = max(prev, b)
    if end - prev > (0 if best is None else best[1] - best[0]):
        best = (prev, end)
    return best


def ao7_illumination(pred, sat, frm, samples=64):
    """Beta angle, eclipse fraction over one orbit, and the timer verdict.

    ``continuous_sun`` True means AO-7's 24-hour timer is running and the mode
    alternates on it; False means the spacecraft eclipses each orbit, power
    cycles, and the mode instead resets rather than following a daily schedule.
    """
    if not pred.set_sat(sat):
        return None
    mm = getattr(sat, "mean_motion", 0.0) or 0.0
    period_s = 86400.0 / mm if mm > 0 else 5700.0
    try:
        beta = pred.beta_angle_deg(frm)
    except Exception:
        beta = float("nan")
    eclipsed = 0
    for i in range(samples):
        t = frm + period_s * i / samples
        try:
            if not pred.sunlit_at(t):
                eclipsed += 1
        except Exception:
            pass
    frac = eclipsed / float(samples)
    return {
        "beta_deg": beta,
        "eclipse_frac": frac,
        "continuous_sun": eclipsed == 0,
        "period_min": period_s / 60.0,
        "sunlit_min": period_s * (1.0 - frac) / 60.0,
        "note": ("Continuous sunlight: the 24 h timer runs and the mode "
                 "alternates on it."
                 if eclipsed == 0 else
                 "Eclipsing each orbit: power cycles, so the mode follows "
                 "power rather than a daily schedule."),
    }


def beta_star_for_altitude(alt_km, re_km=6378.137):
    """Beta angle above which a circular orbit is in continuous sunlight."""
    r = re_km / (re_km + alt_km)
    return math.degrees(math.acos(max(-1.0, min(1.0, r))))
