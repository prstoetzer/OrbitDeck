"""orbitdeck.engine.conjunction - close-approach screening and neighborhood.

Two catalog-analysis tools ported from CardSat:

  * ``screen_conjunctions`` steps a satellite pair through a time window, finds
    local minima of their 3-D (TEME) separation below a threshold, and refines
    each minimum to 1-second resolution, returning miss distance and relative
    velocity - the same method CardSat uses.
  * ``orbital_neighborhood`` ranks the rest of the catalog by how close each
    object's orbit is to a chosen satellite right now (instantaneous 3-D range),
    a quick "what else is up here" view.

Both are **awareness** tools, not collision-avoidance: public GP elements are
only km-class accurate, so a small miss distance means "look closer", never a
guaranteed conjunction. That caveat travels with the numbers.
"""

import math


def _state(pred, sat, unix):
    """Return (r, v) TEME vectors (km, km/s) for a sat, or None on failure."""
    try:
        if not pred.set_sat(sat):
            return None
        return pred._eci_state(unix)
    except Exception:
        return None


def _sep_km(ra, rb):
    return math.sqrt((ra[0] - rb[0]) ** 2 + (ra[1] - rb[1]) ** 2
                     + (ra[2] - rb[2]) ** 2)


def _relvel(va, vb):
    return math.sqrt((va[0] - vb[0]) ** 2 + (va[1] - vb[1]) ** 2
                     + (va[2] - vb[2]) ** 2)


def screen_conjunctions(pred_a, pred_b, sat_a, sat_b, frm, hours=6.0,
                        step_s=30.0, threshold_km=800.0, max_results=8):
    """Screen a satellite pair for close approaches over a window.

    Steps at ``step_s`` looking for local minima of the 3-D separation below
    ``threshold_km``; each candidate minimum is refined at 1-second resolution
    +/- one coarse step. Returns a list of dicts sorted by miss distance:
        {time, miss_km, rel_vel_kms}
    ``pred_a``/``pred_b`` are two independent Predictor instances (so each keeps
    its own SGP4 state); ``sat_a``/``sat_b`` are the SatEntry objects.
    """
    pred_a.set_sat(sat_a)
    pred_b.set_sat(sat_b)
    end = frm + hours * 3600.0
    results = []
    pd = ppd = 1e12
    pt = None
    n_steps = int((end - frm) / step_s) + 1
    for k in range(n_steps + 1):
        t = frm + k * step_s
        sa = _state(pred_a, sat_a, t)
        sb = _state(pred_b, sat_b, t)
        if sa is None or sb is None:
            continue
        d = _sep_km(sa[0], sb[0])
        # local minimum one coarse step back, below threshold?
        if pt is not None and pd < ppd and pd <= d and pd < threshold_km:
            best_t, best_d, best_rv = pt, pd, 0.0
            rt = pt - step_s
            while rt <= pt + step_s:
                r1 = _state(pred_a, sat_a, rt)
                r2 = _state(pred_b, sat_b, rt)
                if r1 and r2:
                    rd = _sep_km(r1[0], r2[0])
                    if rd < best_d:
                        best_d = rd
                        best_t = rt
                        best_rv = _relvel(r1[1], r2[1])
                rt += 1.0
            results.append({"time": best_t, "miss_km": best_d,
                            "rel_vel_kms": best_rv})
        ppd, pd, pt = pd, d, t
    results.sort(key=lambda r: r["miss_km"])
    return results[:max_results]


def orbital_neighborhood(pred, sat, others, frm, max_results=12,
                         max_range_km=None):
    """Rank catalog objects by instantaneous 3-D range to ``sat`` now.

    ``others`` is an iterable of SatEntry to compare against (the caller passes
    the catalog minus ``sat``). Returns a list of dicts sorted by range:
        {norad, name, range_km, rel_vel_kms}
    """
    base = _state(pred, sat, frm)
    if base is None:
        return []
    ra, va = base
    out = []
    scratch = pred          # reuse; set_sat swaps state cheaply
    for o in others:
        if getattr(o, "norad", None) == getattr(sat, "norad", object()):
            continue
        st = _state(scratch, o, frm)
        if st is None:
            continue
        rng = _sep_km(ra, st[0])
        if max_range_km is not None and rng > max_range_km:
            continue
        out.append({
            "norad": getattr(o, "norad", 0),
            "name": getattr(o, "name", "?"),
            "range_km": rng,
            "rel_vel_kms": _relvel(va, st[1]),
        })
    # restore the base sat as the predictor's active object for the caller
    pred.set_sat(sat)
    out.sort(key=lambda r: r["range_km"])
    return out[:max_results]
