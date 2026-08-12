"""orbitdeck.engine.ao7 - the AO-7 mode-switch calculator.

AO-7 (OSCAR 7, 1974) has no working batteries: it runs directly off its solar
panels. Its 24-hour-ish mode timer therefore only alternates Mode A / Mode B
while the spacecraft is in **continuous sunlight**; once it starts eclipsing
each orbit the power cycles and the phase is meaningless.

When the timer *is* running, this estimates where in the cycle it currently is by
fitting a square wave to crowd-sourced AMSAT status reports:

  1. fetch Mode A and Mode B reports separately (the API's record cap applies per
     request, so asking per mode spends the whole budget on AO-7);
  2. discard reports from before continuous illumination began - before that the
     phase carries no information;
  3. score a candidate (period, phase, parity) by weighted agreement: a "heard"
     report of mode m says the mode *was* m (weight 1.0); a "not heard" says it
     was *not* m, which is weaker evidence (weight 0.35) because a station can
     miss an active transponder for local reasons while the converse doesn't
     hold;
  4. coarse-search period 12-30 h and phase over one period, both parities, then
     refine locally to remove grid quantization;
  5. measure the phase uncertainty by sweeping the phase until the score drops by
     one positive report's worth.

Ported from CardSat 0.9.75. The period range matters: an earlier fixed ~24 h
assumption aliased badly against real data, which turned out to be nearer 19.5 h.
"""

import json
import math
import time
from urllib.parse import quote

REPORTS_URL = "https://www.amsat.org/status/api/v1/reports.php?name="
AO7_NORAD = 7530
WINDOW_DAYS = 30
LIMIT = 500

MODE_A, MODE_B = 0, 1
MODE_NAMES = {MODE_A: "Mode A (145 up / 29 down)",
              MODE_B: "Mode B (432 up / 145 down)"}
# Fallback API names. These carry the transponder mode, not an "A"/"B" letter:
# Mode A is the 2 m up / 10 m down transponder (V/a) and Mode B is 70 cm up /
# 2 m down (U/v). They are only a default - hardcoding API names is what made
# the earlier "AO-7[A]"/"AO-7[B]" guesses 404 - so prefer resolve_api_names(),
# which asks the API's own catalog which names it actually publishes today.
API_NAMES = {MODE_A: "AO-7_[V/a]", MODE_B: "AO-7_[U/v]"}

# Which transponder mode an API name denotes. The tag is the mode: uplink band
# letter over downlink band letter, e.g. V/a = 2 m up / 10 m down (Mode A),
# U/v = 70 cm up / 2 m down (Mode B).
MODE_TAGS = {MODE_A: ("V/A",), MODE_B: ("U/V",)}


def mode_of_api_name(api_name):
    """MODE_A / MODE_B for an API name, or None if its tag says neither."""
    import re as _re
    m = _re.search(r"\[([^\]]*)\]", api_name or "")
    tag = (m.group(1) if m else "").upper().replace(" ", "")
    for mode, tags in MODE_TAGS.items():
        if tag in tags:
            return mode
    return None


def resolve_api_names(http_get, sat_names, fallback=True):
    """Ask the API's catalog which names it publishes for AO-7.

    Returns {MODE_A: name, MODE_B: name}. Falls back to API_NAMES for any mode
    the catalog does not resolve, so a catalog fetch failure degrades to the
    previous behaviour rather than breaking the fit.
    """
    from . import amsatnames as _an
    from . import amsatstatus as _as
    out = {}
    try:
        names = _an.parse_catalog_names(http_get(_as.CATALOG_URL))
        idx = None
        for i, nm in enumerate(sat_names):
            if _an.match_api_name("AO-7", [nm]) == 0:
                idx = i
                break
        if idx is not None:
            mapping = _an.build_map(names, sat_names)
            for api in _an.names_for(mapping, idx):
                mode = mode_of_api_name(api)
                if mode is not None:
                    out[mode] = api
    except Exception:
        pass
    if fallback:
        for mode, name in API_NAMES.items():
            out.setdefault(mode, name)
    return out

W_POS = 1.0          # a "heard" report
W_NEG = 0.35         # a "not heard" report: weaker evidence

PMIN = 12.0 * 3600.0
PMAX = 30.0 * 3600.0
PSTEP_C, TSTEP_C = 300.0, 1800.0     # coarse: 5 min period, 30 min phase
PSTEP_F, TSTEP_F = 30.0, 60.0        # fine: 30 s period, 1 min phase


def reports_url(mode, hours=WINDOW_DAYS * 24, limit=LIMIT, name=None):
    api = name or API_NAMES[mode]
    return "%s%s&hours=%d&limit=%d" % (REPORTS_URL, quote(api, safe=""),
                                       int(hours), int(limit))


def parse_reports(text, mode):
    """Parse an AMSAT status API response into observations.

    Each observation is a dict {t, mode, negative}. "Heard" reports are
    positive; "Not Heard" are negative. Returns [] for an unusable body.
    """
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("reports") or data.get("data") or []
    out = []
    for rec in data if isinstance(data, list) else []:
        if not isinstance(rec, dict):
            continue
        stamp = (rec.get("reported_time") or rec.get("time")
                 or rec.get("timestamp") or rec.get("date"))
        t = _parse_time(stamp)
        if t is None:
            continue
        report = str(rec.get("report") or rec.get("status") or "").strip()
        low = report.lower()
        if not low:
            continue
        # "Heard", "Telemetry Only" etc. count as heard; "Not Heard" is negative
        negative = low.startswith("not")
        out.append({"t": t, "mode": mode, "negative": negative})
    out.sort(key=lambda r: r["t"])
    return out


def _parse_time(stamp):
    if stamp is None:
        return None
    if isinstance(stamp, (int, float)):
        return float(stamp)
    s = str(stamp).strip().replace("T", " ")
    if not s:
        return None
    if "." in s:
        s = s.split(".")[0]
    s = s.replace("Z", "").strip()
    import calendar
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return float(calendar.timegm(time.strptime(s, fmt)))
        except ValueError:
            continue
    return None


def score(obs, period, t0, flip):
    """Weighted agreement of a square wave with the observations."""
    sc = 0.0
    for o in obs:
        k = math.floor((o["t"] - t0) / period)
        pred = (int(k) & 1) ^ flip
        if o["negative"]:
            if pred != o["mode"]:
                sc += W_NEG
        elif pred == o["mode"]:
            sc += W_POS
    return sc


def fit(obs, now=None):
    """Fit period/phase/parity to the observations.

    Returns a dict with period_s, t0, flip, agree_pct, phase_rms_s, mode_now,
    next_switch, to_switch_s, counts and a plain-language confidence note, or
    None when there is nothing positive to fit.
    """
    if not obs:
        return None
    n_pos = sum(1 for o in obs if not o["negative"])
    if n_pos == 0:
        return {"error": "No positive reports to fit"}
    now = now if now is not None else time.time()
    t_ref = obs[0]["t"]
    w_total = sum(W_NEG if o["negative"] else W_POS for o in obs)

    best = (-1.0, PMIN, t_ref, 0)
    p = PMIN
    while p <= PMAX:
        off = 0.0
        while off < p:
            t0 = t_ref + off
            for flip in (0, 1):
                sc = score(obs, p, t0, flip)
                if sc > best[0]:
                    best = (sc, p, t0, flip)
            off += TSTEP_C
        p += PSTEP_C

    best_sc, best_p, best_t0, best_flip = best
    p0, s0 = best_p, best_t0
    p = p0 - PSTEP_C
    while p <= p0 + PSTEP_C:
        if PMIN <= p <= PMAX:
            t0 = s0 - TSTEP_C
            while t0 <= s0 + TSTEP_C:
                sc = score(obs, p, t0, best_flip)
                if sc > best_sc:
                    best_sc, best_p, best_t0 = sc, p, t0
                t0 += TSTEP_F
        p += PSTEP_F

    # phase uncertainty: how far can the phase move before the fit degrades by
    # one positive report's worth?
    lo = hi = 0.0
    d = TSTEP_F
    while d <= best_p / 2:
        if score(obs, best_p, best_t0 - d, best_flip) < best_sc - W_POS:
            break
        lo = d
        d += TSTEP_F
    d = TSTEP_F
    while d <= best_p / 2:
        if score(obs, best_p, best_t0 + d, best_flip) < best_sc - W_POS:
            break
        hi = d
        d += TSTEP_F
    phase_rms = 0.5 * (lo + hi)

    k_now = math.floor((now - best_t0) / best_p)
    next_switch = best_t0 + (k_now + 1.0) * best_p
    prev_switch = best_t0 + k_now * best_p
    mode_now = (int(k_now) & 1) ^ best_flip
    to_switch = max(0.0, next_switch - now)

    # count observed mode changes among positives - evidence about the fit
    switches = 0
    last = None
    for o in obs:
        if o["negative"]:
            continue
        if last is not None and o["mode"] != last:
            switches += 1
        last = o["mode"]

    agree = (100.0 * best_sc / w_total) if w_total > 0 else 0.0
    margin = max(phase_rms, 900.0)          # reports carry ~15 min resolution
    near = (to_switch < margin) or ((now - prev_switch) < margin)
    if near:
        note = "Near a switch: mode uncertain right now"
    elif switches < 2 or n_pos < 6:
        note = "Low confidence (few reports)"
    elif agree < 75.0:
        note = "Reports disagree; estimate approximate"
    elif phase_rms > 0.10 * best_p:
        note = "Phase loosely constrained"
    else:
        note = "Estimate from report timestamps"

    return {
        "period_s": best_p, "t0": best_t0, "flip": best_flip,
        "agree_pct": agree, "phase_rms_s": phase_rms,
        "mode_now": mode_now, "mode_now_name": MODE_NAMES[mode_now],
        "next_switch": next_switch, "to_switch_s": to_switch,
        "prev_switch": prev_switch,
        "n_obs": len(obs), "n_pos": n_pos, "n_neg": len(obs) - n_pos,
        "n_switch": switches, "note": note, "near_boundary": near,
    }


# A single grazing sample should not count as an eclipse season: near the
# boundary one of 24 samples can dip into shadow and back out again on
# successive orbits. Require at least this many of them.
ECLIPSE_SAMPLES = 24
ECLIPSE_MIN_SAMPLES = 2


def orbit_eclipse_samples(pred, sat, t, n=ECLIPSE_SAMPLES):
    """How many of ``n`` samples across one orbit starting at ``t`` are shadowed.

    Returns None if the state cannot be evaluated, so callers can tell "could
    not tell" from "not eclipsing" - the old code treated an exception as
    eclipsing, which silently truncated the search.
    """
    mm = getattr(sat, "mean_motion", 0.0) or 0.0
    period_s = 86400.0 / mm if mm > 0 else 5700.0
    shadowed = 0
    ok = 0
    for i in range(n):
        try:
            if not pred.sunlit_at(t + period_s * i / n):
                shadowed += 1
            ok += 1
        except Exception:
            continue
    return shadowed if ok else None


def _eclipsing_at(pred, sat, t):
    n = orbit_eclipse_samples(pred, sat, t)
    if n is None:
        return None
    return n >= ECLIPSE_MIN_SAMPLES


def illumination_since(pred, sat, now, back_days=120, coarse_hours=12.0,
                       resolution_s=1800.0):
    """When the current run of continuous sunlight began, or None if eclipsing.

    Searched coarsely backwards a day at a time and then bisected, rather than
    stepped at a fixed fine interval: an eclipse season boundary is weeks away,
    so a 30-minute walk both took thousands of propagations and quantised the
    answer. It also required a real eclipse (>= ECLIPSE_MIN_SAMPLES shadowed
    samples), because a single grazing sample near the boundary would otherwise
    flip the verdict and report the season as starting *now*.

    Returns (start_unix, exact) where ``exact`` is False if the search hit the
    ``back_days`` limit without finding an eclipse - i.e. the run began at least
    that long ago.
    """
    if not pred.set_sat(sat):
        return None
    if _eclipsing_at(pred, sat, now) is not False:
        return None                       # eclipsing now (or undeterminable)

    step = coarse_hours * 3600.0
    limit = now - back_days * 86400.0
    lit_t = now                            # known sunlit
    ecl_t = None                           # first eclipsing time found
    t = now - step
    while t > limit:
        state = _eclipsing_at(pred, sat, t)
        if state is True:
            ecl_t = t
            break
        if state is False:
            lit_t = t
        t -= step
    if ecl_t is None:
        return (limit, False)              # continuous for the whole window

    # bisect the boundary between ecl_t (eclipsing) and lit_t (sunlit)
    lo, hi = ecl_t, lit_t
    while hi - lo > resolution_s:
        mid = 0.5 * (lo + hi)
        if _eclipsing_at(pred, sat, mid):
            lo = mid
        else:
            hi = mid
    return (hi, True)


def fetch_and_fit(http_get, pred=None, sat=None, now=None,
                  hours=WINDOW_DAYS * 24, api_names=None):
    """Full calculator: fetch both modes, gate on illumination, fit.

    ``http_get`` is a callable(url) -> text so the transport can be injected.
    When ``pred``/``sat`` are supplied, reports from before continuous
    illumination began are discarded (and the fit is skipped entirely if the
    spacecraft is currently eclipsing, because the timer isn't running).
    """
    now = now if now is not None else time.time()
    obs = []
    names = api_names or API_NAMES
    for mode in (MODE_A, MODE_B):
        try:
            body = http_get(reports_url(mode, hours, name=names.get(mode)))
        except Exception:
            continue
        obs.extend(parse_reports(body, mode))
    obs.sort(key=lambda r: r["t"])

    since = None
    if pred is not None and sat is not None:
        found = illumination_since(pred, sat, now)
        since = found[0] if found else None
        if found is None:
            return {"continuous_sun": False, "n_obs": len(obs),
                    "note": ("Eclipsing each orbit: the 24 h timer is not "
                             "running, so the mode follows power.")}
        obs = [o for o in obs if o["t"] >= since]
        if not obs:
            return {"continuous_sun": True, "since": since, "n_obs": 0,
                    "note": "No reports since illumination began"}
    res = fit(obs, now=now)
    if res is None:
        return {"continuous_sun": True, "since": since, "n_obs": 0,
                "note": "No reports returned"}
    res["continuous_sun"] = True
    res["since"] = since
    return res
