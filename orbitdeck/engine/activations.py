"""orbitdeck.engine.activations - helpers for the hams.at activation feed.

Two jobs the screen needs and that belong out of the UI:

  * resolving an activation's satellite against the **local catalog first**, so
    a satellite you already have is not re-fetched from CelesTrak and added a
    second time;
  * working out whether you and the activator can actually see the satellite at
    the listed time - the question the entry exists to answer.
"""

import re

# What went wrong, kept distinct because CardSat's notes record that collapsing
# them sent operators hunting for a satellite that was in the catalog all along.
FP_OK = 0            # mutual window found
FP_NO_WINDOW = 1     # both known, but no common visibility near the listed time
FP_NO_SAT = 2        # the satellite is genuinely not in the catalog
FP_BAD_TIME = 3      # the feed's date/time could not be parsed
FP_BAD_GRID = 4      # the activator grid could not be parsed
FP_NO_CLOCK = 5      # no usable clock

FP_TEXT = {
    FP_OK: "mutual window found",
    FP_NO_WINDOW: "no mutual window near the listed time",
    FP_NO_SAT: "satellite not in your catalog",
    FP_BAD_TIME: "feed date/time unusable",
    FP_BAD_GRID: "activator grid unusable",
    FP_NO_CLOCK: "clock not set",
}


def first_grid(text):
    """The first grid of a grid-line activation.

    Entries list two grids for a line activation ("EM12/EM13", "EM12, EM13").
    The whole string fails to parse, and CardSat's notes record that this
    failure used to be reported as a *satellite* problem for a perfectly
    ordinary rove. The two grids are adjacent by definition, so either places
    the activator inside the same mutual-visibility footprint.
    """
    s = (text or "").strip()
    if not s:
        return ""
    return re.split(r"[/,;\s]", s, 1)[0].strip()


def find_local(db, name):
    """Find an activation's satellite in the local catalog.

    Tries the AMSAT name matcher first - the feed uses operating names like
    "AO-91" or "RS-44" while the catalog carries "AO-91 (RADFXSAT)" - then a
    plain normalised compare. Returns the SatEntry or None.

    This is what stops the screen re-adding satellites you already have.
    """
    sats = list(getattr(db, "sats", []) or [])
    if not sats or not name:
        return None
    names = [getattr(s, "name", "") for s in sats]
    try:
        from . import amsatnames as _an
        idx = _an.match_api_name(name, names)
        if idx is not None:
            return sats[idx]
        want = _an.norm(name)
        for i, nm in enumerate(names):
            if _an.norm(nm) == want:
                return sats[i]
        coll = _an.collapse(name)
        for i, nm in enumerate(names):
            if coll and _an.collapse(nm) == coll:
                return sats[i]
    except Exception:
        pass
    return None


def parse_listed_utc(date_text, time_text):
    """Combine the feed's date and start time into a unix epoch, or None."""
    import calendar
    d = (date_text or "").strip()
    t = (time_text or "").strip()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", d)
    if not m:
        return None
    hm = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", t)
    if not hm:
        return None
    try:
        return float(calendar.timegm((
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(hm.group(1)), int(hm.group(2)), int(hm.group(3) or 0),
            0, 0, 0)))
    except (ValueError, OverflowError):
        return None


def check_activation(store, act, now=None, search_min=60, min_el=0.0):
    """Can you work this activation? Returns (state, detail-dict).

    Searches +/-``search_min`` minutes around the listed start for a window in
    which the satellite is above the horizon at both your station and the
    activator's grid.
    """
    import time as _t
    from .predict import Predictor, Observer, grid_to_latlon
    now = now if now is not None else _t.time()
    info = {"sat": None, "listed": None, "grid": "", "window": None}

    grid = first_grid(act.get("grid", ""))
    info["grid"] = grid
    if not grid:
        return FP_BAD_GRID, info
    try:
        dx_lat, dx_lon = grid_to_latlon(grid)
    except Exception:
        return FP_BAD_GRID, info

    sat = find_local(store.db, act.get("sat", ""))
    info["sat"] = sat
    if sat is None:
        return FP_NO_SAT, info

    listed = parse_listed_utc(act.get("date", ""), act.get("start", ""))
    if listed is None:
        listed = parse_listed_utc(act.get("start", "")[:10],
                                  act.get("start", "")[11:])
    info["listed"] = listed
    if listed is None:
        return FP_BAD_TIME, info

    pred = Predictor()
    pred.set_site(store.obs)
    if not pred.set_sat(sat):
        return FP_NO_SAT, info
    dx = Observer(lat=dx_lat, lon=dx_lon, alt_m=0.0, valid=True)
    try:
        wins = pred.mutual_windows(listed - search_min * 60.0, dx, min_el, 12)
    except Exception:
        return FP_NO_WINDOW, info
    limit = listed + search_min * 60.0
    lo = listed - search_min * 60.0
    near = []
    for wmm in wins:
        start = getattr(wmm, "start", 0)
        end = getattr(wmm, "end", start)
        if start <= limit and end >= lo:
            near.append({
                "start": start, "end": end,
                "my_max_el": getattr(wmm, "my_max_el", 0.0),
                "dx_max_el": getattr(wmm, "dx_max_el", 0.0),
                "obj": wmm,
            })
    info["windows"] = near
    info["dx"] = dx
    if near:
        # the window closest to the listed start is the one being advertised
        best = min(near, key=lambda wm: abs(wm["start"] - listed))
        info["window"] = (best["start"], best["end"])
        info["best"] = best
        return FP_OK, info
    return FP_NO_WINDOW, info


# ---------------------------------------------------------------------------
# Seeding the Doppler view from the activation record
# ---------------------------------------------------------------------------
FREQ_TOL_HZ = 20000        # +/-20 kHz, for single-channel matches


def scan_freq_hz(text):
    """First plausible frequency in a free-text field, in Hz.

    Feed entries write frequencies every which way: "145.990", "437.800 MHz",
    "145990 kHz". Anything between 20 MHz and 25 GHz is taken as a real radio
    frequency; a bare "50" is more likely an elevation than 50 MHz, so values
    without a decimal point or unit are ignored.
    """
    import re as _re
    if not text:
        return 0
    for m in _re.finditer(r"(\d+(?:\.\d+)?)\s*(ghz|mhz|khz|hz)?", str(text),
                          _re.I):
        num = float(m.group(1))
        unit = (m.group(2) or "").lower()
        if unit == "ghz":
            hz = num * 1e9
        elif unit == "mhz":
            hz = num * 1e6
        elif unit == "khz":
            hz = num * 1e3
        elif unit == "hz":
            hz = num
        elif "." in m.group(1):
            hz = num * 1e6            # bare decimal - conventionally MHz
        else:
            continue                  # bare integer: too ambiguous to trust
        if 20e6 <= hz <= 25e9:
            return int(hz)
    return 0


def _leg(lo, hi):
    lo = lo or 0
    hi = hi or lo
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi


def match_transponder(sat, act):
    """Which transponder (and which leg) the activation's frequency names.

    Returns ``(index, leg, hz)`` where leg is "downlink" or "uplink", or
    ``(None, None, 0)``. Only two-way transponders are considered - a beacon
    has no leg to fix against. Falling back to "first transponder" is what made
    the Doppler table show the wrong passband when an operator had said exactly
    which frequency they would be on.
    """
    tps = list(getattr(sat, "transponders", []) or [])
    if not tps:
        return (None, None, 0)
    hz = scan_freq_hz(act.get("freq")) or scan_freq_hz(act.get("comment"))
    if not hz:
        return (None, None, 0)
    for i, t in enumerate(tps):
        dl = getattr(t, "downlink", 0) or 0
        ul = getattr(t, "uplink", 0) or 0
        if not (dl and ul):
            continue                  # not two-way
        d_lo, d_hi = _leg(dl, getattr(t, "downlink_high", 0))
        if max(0, d_lo - FREQ_TOL_HZ) <= hz <= d_hi + FREQ_TOL_HZ:
            return (i, "downlink", hz)
        u_lo, u_hi = _leg(ul, getattr(t, "uplink_high", 0))
        if max(0, u_lo - FREQ_TOL_HZ) <= hz <= u_hi + FREQ_TOL_HZ:
            return (i, "uplink", hz)
    return (None, None, hz)


def max_elevation(store, act, window=None):
    """Peak elevation of the activation's pass from YOUR station.

    The feed's own "Max elevation" is the activator's, and is often absent -
    the column read "None" for every row. This computes yours, which is the
    number that decides whether you can work the activation at all.
    """
    from .predict import Predictor
    sat = find_local(store.db, act.get("sat", ""))
    if sat is None:
        return None
    listed = parse_listed_utc(act.get("date", ""), act.get("start", ""))
    if listed is None:
        return None
    pred = Predictor()
    pred.set_site(store.obs)
    if not pred.set_sat(sat):
        return None
    try:
        passes = pred.predict_passes(listed - 3600.0, 0.0, 6,
                                     listed + 3600.0)
    except Exception:
        return None
    best = None
    for p in passes:
        if p.los < listed - 3600 or p.aos > listed + 3600:
            continue
        if best is None or abs(p.aos - listed) < abs(best.aos - listed):
            best = p
    return round(best.max_el) if best else None


def valid_grid(text):
    """True if ``text`` is a well-formed Maidenhead locator.

    ``grid_to_latlon`` does not validate: it happily turns "ZZZZ" into
    (202.5, 405.0) and "nonsense" into a real-looking pair, so any caller that
    trusted it would silently plot a station off the planet. Field letters are
    A-R, squares 0-9, and the optional subsquare letters a-x.
    """
    import re as _re
    s = (text or "").strip().upper()
    if not _re.fullmatch(r"[A-R]{2}[0-9]{2}([A-X]{2}([0-9]{2})?)?", s):
        return False
    return True
