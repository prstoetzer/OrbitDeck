"""DX Doppler -- four-dial frequency prediction for two stations on a transponder.

Given a satellite, a transponder, and two ground stations (you and a DX station),
predict the four radio dial frequencies -- your RX, your TX, the DX's RX, the DX's
TX -- across a mutual-visibility window, under three operating policies:

  * TRUE_RULE  -- both work the same point in the satellite passband; each applies
                  its own Doppler, so all four dials move.
  * FIXED_DL   -- one station's RX dial is locked to a single real-RF value for the
                  whole window; the other three drift.
  * FIXED_UL   -- one station's TX dial is locked; the other three drift.

First-order Doppler throughout, with beta = range_rate / c and the dial
conventions ``rx = dl*(1-beta) + cal_dl`` and ``tx = ul/(1-beta) + cal_ul`` (beta
positive when the satellite is receding). This matches the convention used
elsewhere in OrbitDeck (engine.linkbudget.doppler_shift_hz).

The range rate comes from a Predictor positioned at the relevant site -- it is
taken from the SGP4 velocity vector (exact), not by differencing slant range.

This module is GUI-independent and unit-tested on its own.
"""

from .predict import C_LIGHT, Observer, Predictor
from .satdb import Transponder

# operating modes
TRUE_RULE = "true_rule"
FIXED_DL = "fixed_dl"
FIXED_UL = "fixed_ul"

# anchor stations (which dial is locked, for the fixed modes)
ME_RX = "me_rx"
ME_TX = "me_tx"
DX_RX = "dx_rx"
DX_TX = "dx_tx"

_ANCHOR_IS_DX = (DX_RX, DX_TX)


def passband_freqs(tp: Transponder, pb_offset_hz: int):
    """Satellite-frame (dl_op, ul_op) for the chosen point in the passband.

    Thin wrapper over Predictor.passband_freqs so callers only need this module.
    ``pb_offset_hz`` is a non-negative offset up from the downlink low edge;
    ignored for FM / single-channel transponders.
    """
    return Predictor.passband_freqs(tp, pb_offset_hz)


def doppler_dials(dl, ul, rr_kms, cal_dl=0, cal_ul=0):
    """One station's (rx, tx) dials from a satellite-frame (dl, ul) pair and that
    station's range rate (km/s, +receding). ``tx`` is 0 when ``ul`` is 0
    (receive-only). Rounded to the nearest Hz at the dial only."""
    beta = (rr_kms * 1000.0) / C_LIGHT
    rx = round(dl * (1.0 - beta) + cal_dl)
    tx = round(ul / (1.0 - beta) + cal_ul) if ul else 0
    return rx, tx


def _range_rate_kms(pred: Predictor, site: Observer, sat, t: float) -> float:
    """Range rate (km/s, +receding) of ``sat`` seen from ``site`` at time ``t``.

    ``pred`` is reused (its satellite is assumed already set to ``sat``); only the
    site is swapped, which is cheap and leaves the SGP4 state cache intact.
    """
    pred.set_site(site)
    return pred.look(t).range_rate


def dx_doppler(t, t_ref, sat, me, dx, tp, pb_offset,
               mode=TRUE_RULE, anchor=ME_TX, cal_dl=0, cal_ul=0,
               my_pred=None, dx_pred=None):
    """Four dial frequencies (my_rx, my_tx, dx_rx, dx_tx) in Hz at time ``t``.

    Parameters mirror the algorithm memo:

      t        -- evaluation time (unix seconds)
      t_ref    -- reference instant at which a fixed dial is locked (window start)
      sat      -- the satellite (SatEntry)
      me, dx   -- the two Observer sites
      tp       -- the Transponder
      pb_offset-- passband operating offset in Hz (0 for FM/single channel)
      mode     -- TRUE_RULE | FIXED_DL | FIXED_UL
      anchor   -- ME_RX | ME_TX | DX_RX | DX_TX  (which dial is locked, fixed modes)
      cal_dl,  -- calibration offsets added at the RX / TX dial (Hz)
      cal_ul
      my_pred, -- optional pre-built Predictors with ``sat`` already set, so a
      dx_pred     table loop doesn't rebuild SGP4 state every step. Their site is
                  reset internally as needed.

    A ``0`` TX field means "no uplink" (receive-only transponder).
    """
    if my_pred is None:
        my_pred = Predictor()
        my_pred.set_sat(sat)
    if dx_pred is None:
        dx_pred = Predictor()
        dx_pred.set_sat(sat)

    dl_op, ul_op = passband_freqs(tp, pb_offset)

    rr_me = _range_rate_kms(my_pred, me, sat, t)
    rr_dx = _range_rate_kms(dx_pred, dx, sat, t)
    beta_me = (rr_me * 1000.0) / C_LIGHT
    beta_dx = (rr_dx * 1000.0) / C_LIGHT

    # ---- Mode 0: True Rule -- both work the same passband point ----
    if mode == TRUE_RULE:
        my_rx, my_tx = doppler_dials(dl_op, ul_op, rr_me, cal_dl, cal_ul)
        dx_rx, dx_tx = doppler_dials(dl_op, ul_op, rr_dx, cal_dl, cal_ul)
        return my_rx, my_tx, dx_rx, dx_tx

    # ---- Modes 1 & 2: one dial of the anchor station is locked ----
    anchor_is_dx = anchor in _ANCHOR_IS_DX
    a_site = dx if anchor_is_dx else me
    a_pred = dx_pred if anchor_is_dx else my_pred

    # crux: the lock is captured from the anchor's beta at the REFERENCE instant
    # (constant for the window), and solved against its beta at THIS step. Using
    # the live beta to recompute the lock each step cancels algebraically -> zero
    # drift -> the "fixed" dial silently swings with Doppler.
    rr_ref = _range_rate_kms(a_pred, a_site, sat, t_ref)
    a_beta_ref = (rr_ref * 1000.0) / C_LIGHT
    a_beta = beta_dx if anchor_is_dx else beta_me

    if mode == FIXED_DL:
        denom = (1.0 - a_beta) or 1e-12
        dl_sat = dl_op * (1.0 - a_beta_ref) / denom
        delta = dl_sat - dl_op
        ul_sat = (ul_op - delta) if tp.invert else (ul_op + delta)
    else:   # FIXED_UL
        denom = (1.0 - a_beta_ref) or 1e-12
        ul_sat = (ul_op * (1.0 - a_beta) / denom) if ul_op else 0
        delta = (ul_sat - ul_op) if ul_op else 0
        dl_sat = (dl_op - delta) if tp.invert else (dl_op + delta)

    my_rx = round(dl_sat * (1.0 - beta_me) + cal_dl)
    my_tx = round(ul_sat / (1.0 - beta_me) + cal_ul) if ul_op else 0
    dx_rx = round(dl_sat * (1.0 - beta_dx) + cal_dl)
    dx_tx = round(ul_sat / (1.0 - beta_dx) + cal_ul) if ul_op else 0
    return my_rx, my_tx, dx_rx, dx_tx


def dx_doppler_table(start, end, sat, me, dx, tp, pb_offset,
                     mode=TRUE_RULE, anchor=ME_TX, cal_dl=0, cal_ul=0,
                     step_s=30.0):
    """Build a list of (t, my_rx, my_tx, dx_rx, dx_tx) rows across [start, end].

    The reference instant for the fixed modes is the window ``start`` -- so the
    table reads as "the anchor sits still; watch the other three drift away from
    the start of the window." Predictors are built once and reused across steps.
    """
    my_pred = Predictor()
    my_pred.set_sat(sat)
    dx_pred = Predictor()
    dx_pred.set_sat(sat)

    rows = []
    t = start
    # guard against pathological inputs producing a huge loop
    n_max = 100000
    while t <= end + 1e-6 and len(rows) < n_max:
        dials = dx_doppler(t, start, sat, me, dx, tp, pb_offset,
                           mode=mode, anchor=anchor, cal_dl=cal_dl,
                           cal_ul=cal_ul, my_pred=my_pred, dx_pred=dx_pred)
        rows.append((t,) + dials)
        t += step_s
    return rows
