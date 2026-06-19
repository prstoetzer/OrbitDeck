"""planning.py - goal-directed planning analytics over passes.

Two capabilities:

* best_passes_for_target: given a target location (lat/lon, derived from a grid
  square, US state centroid, or DXCC entity), find upcoming passes during which
  BOTH the operator and the target are inside the satellite footprint at the
  same time -- i.e. a two-way contact through the bird is geometrically possible
  -- and rank them.

* sky_coverage_grid: aggregate many passes into an azimuth x elevation density
  grid (a sky heatmap) showing where in the operator's sky a satellite spends
  its time, useful for antenna-pattern and obstruction planning.

Pure functions that take a Predictor; no GUI imports.
"""

import math

DEG = math.pi / 180.0
RE_KM = 6378.135


def _angular_sep_deg(lat1, lon1, lat2, lon2):
    a = lat1 * DEG
    b = lat2 * DEG
    dl = (lon2 - lon1) * DEG
    c = math.sin(a) * math.sin(b) + math.cos(a) * math.cos(b) * math.cos(dl)
    return math.acos(max(-1.0, min(1.0, c))) / DEG


def footprint_radius_deg(alt_km):
    r = RE_KM + alt_km
    if r <= RE_KM:
        return 0.0
    return math.acos(RE_KM / r) / DEG


def both_in_footprint(pred, t, obs_lat, obs_lon, tgt_lat, tgt_lon):
    """True if at time t both the operator and the target lie within the
    satellite's footprint (so a contact through the satellite is possible)."""
    sub = pred.subpoint_at(t)
    sub_lat, sub_lon, alt = sub[0], sub[1], sub[2]
    radius = footprint_radius_deg(alt)
    if radius <= 0:
        return False
    return (_angular_sep_deg(sub_lat, sub_lon, obs_lat, obs_lon) <= radius
            and _angular_sep_deg(sub_lat, sub_lon, tgt_lat, tgt_lon) <= radius)


def best_passes_for_target(pred, obs, tgt_lat, tgt_lon, frm, hours=72.0,
                           min_el=0.0, step_s=30.0, max_results=20):
    """Find windows in [frm, frm+hours] when both the operator and the target
    are simultaneously inside the footprint. Returns a list of dicts:
    {start, end, duration_s, mid, max_common} sorted by start time.

    ``max_common`` is the maximum (over the window) of the smaller of the two
    elevation-equivalent margins -- a rough "quality" proxy: a window where both
    stations are near the centre of the footprint is better than one where both
    are near the edge.
    """
    end = frm + hours * 3600.0
    t = frm
    windows = []
    cur = None
    while t <= end:
        ok = both_in_footprint(pred, t, obs.lat, obs.lon, tgt_lat, tgt_lon)
        if ok and cur is None:
            cur = {"start": t, "end": t}
        elif ok and cur is not None:
            cur["end"] = t
        elif not ok and cur is not None:
            windows.append(cur)
            cur = None
        t += step_s
    if cur is not None:
        windows.append(cur)
    out = []
    for w in windows:
        dur = w["end"] - w["start"]
        mid = 0.5 * (w["start"] + w["end"])
        # margin proxy at mid: how deep inside the footprint the worse station is
        sub = pred.subpoint_at(mid)
        radius = footprint_radius_deg(sub[2])
        d_obs = _angular_sep_deg(sub[0], sub[1], obs.lat, obs.lon)
        d_tgt = _angular_sep_deg(sub[0], sub[1], tgt_lat, tgt_lon)
        margin = radius - max(d_obs, d_tgt)
        out.append({
            "start": w["start"], "end": w["end"], "duration_s": dur,
            "mid": mid, "margin_deg": round(margin, 1),
        })
    out.sort(key=lambda x: x["start"])
    return out[:max_results]


def rove_stop_passes(pred, stop_lat, stop_lon, frm, to, min_el=5.0,
                     step_s=60.0, max_passes=20):
    """For a single rove stop (lat/lon) and a time-window HINT [frm, to], return
    the satellite's passes whose footprint covers the stop, each annotated with
    the workable Maidenhead grids, US states, and DXCC entities reachable while
    the stop is inside the footprint (the mutual coverage during the pass).

    The window is a hint, not a hard filter: passes straddling the edges are
    still included (we search a padded range and keep any pass that covers the
    stop). Each result is a dict:
        {aos, los, max_el, grids:set, states:set, dxcc:set}
    """
    from .analysis import make_footprint_test, workable_grids
    try:
        from ..data.us_states import workable_states
    except Exception:
        workable_states = None
    try:
        from ..data.dxcc import workable_dxcc
    except Exception:
        workable_dxcc = None

    pad = 3600.0
    passes = pred.predict_passes(frm - pad, min_el, max_passes, to + pad)
    out = []
    for p in passes:
        steps = max(8, int((p.los - p.aos) / step_s))
        grids, states, dxcc = set(), set(), set()
        covered = False
        for i in range(steps + 1):
            tt = p.aos + (p.los - p.aos) * i / steps
            sub_lat, sub_lon, alt = pred.subpoint_at(tt)
            inside = make_footprint_test(sub_lat, sub_lon, alt)
            if not inside(stop_lat, stop_lon):
                continue
            covered = True
            grids.update(workable_grids(sub_lat, sub_lon, alt))
            if workable_states is not None:
                states.update(workable_states(inside))
            if workable_dxcc is not None:
                dxcc.update("%s %s" % (pfx, nm)
                            for pfx, nm in workable_dxcc(inside))
        if not covered:
            continue
        out.append({
            "aos": p.aos, "los": p.los, "max_el": p.max_el,
            "grids": grids, "states": states, "dxcc": dxcc,
        })
    return out


def sky_coverage_grid(pred, obs, passes, az_bins=36, el_bins=9, step_s=20.0):
    """Aggregate passes into an azimuth x elevation occupancy grid.

    Returns a 2D list grid[el_bin][az_bin] of dwell seconds, with az in
    [0,360) split into ``az_bins`` columns and el in [0,90] split into
    ``el_bins`` rows. Sampling each pass every ``step_s`` seconds.
    """
    grid = [[0.0 for _ in range(az_bins)] for _ in range(el_bins)]
    az_w = 360.0 / az_bins
    el_w = 90.0 / el_bins
    for p in passes:
        if not (p.aos and p.los):
            continue
        t = p.aos
        while t <= p.los:
            az, el = pred.azel_at(t)
            if el >= 0:
                ai = int(az / az_w) % az_bins
                ei = min(el_bins - 1, int(el / el_w))
                grid[ei][ai] += step_s
            t += step_s
    return grid


def horizon_mask_apply(pred, p, mask_func, step_s=10.0):
    """Given a pass and a horizon-mask function mask_func(az_deg) -> min_el_deg,
    return the effective (aos, los) trimmed to where the satellite clears the
    local horizon profile, or None if the pass never clears the mask.

    Lets a user account for trees/buildings: a pass technically above 0 deg may
    be blocked by a 20 deg treeline to the north.
    """
    if not (p.aos and p.los):
        return None
    t = p.aos
    eff_aos = None
    eff_los = None
    while t <= p.los:
        az, el = pred.azel_at(t)
        if el >= mask_func(az):
            if eff_aos is None:
                eff_aos = t
            eff_los = t
        t += step_s
    if eff_aos is None:
        return None
    return (eff_aos, eff_los)
