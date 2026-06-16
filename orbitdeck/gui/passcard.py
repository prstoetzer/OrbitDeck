"""passcard.py - a shareable single-image summary of one pass.

Produces a compact PNG: a sky-track polar plot, a Doppler curve, and the key
pass facts, suitable for sharing in a club chat or attaching to a log entry.
"""

import math
import datetime as _dt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ..engine.predict import Predictor
from ..engine import linkbudget as LB

DEG = math.pi / 180.0
BG = "#0d1117"
PANEL = "#161b22"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#2f81f7"
ACCENT2 = "#3fb950"


def _utc(unix, fmt="%Y-%m-%d %H:%M UTC"):
    return _dt.datetime.fromtimestamp(
        unix, _dt.timezone.utc).strftime(fmt)


def draw_pass_card(fig, store, sat, p):
    """Draw the pass card onto an existing matplotlib Figure (used both for the
    saved PNG and the on-screen preview)."""
    pred = Predictor()
    pred.set_site(store.obs)
    pred.set_sat(sat)

    fig.set_facecolor(BG)
    title = "%s \u2014 %s UTC" % (sat.name, _utc(p.aos, "%a %Y-%m-%d %H:%M"))
    # scale the title down for long names so it never runs off the card
    t_fs = 15 if len(title) <= 36 else (13 if len(title) <= 46 else 11)
    fig.suptitle(title, color=TEXT, fontsize=t_fs, fontweight="bold",
                 x=0.5, y=0.97)

    # --- sky track (left, polar) ---
    axp = fig.add_axes([0.04, 0.08, 0.40, 0.78], projection="polar")
    axp.set_facecolor(PANEL)
    axp.set_theta_zero_location("N")
    axp.set_theta_direction(-1)
    axp.set_rlim(0, 90)
    axp.set_rgrids([0, 30, 60, 90], labels=["90", "60", "30", "0"],
                   color=MUTED, fontsize=6)
    axp.set_thetagrids(range(0, 360, 45),
                       labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                       color=MUTED, fontsize=7)
    ths, rs = [], []
    t = p.aos
    while t <= p.los:
        az, el = pred.azel_at(t)
        if el >= 0:
            ths.append(az * DEG)
            rs.append(90 - el)
        t += 15.0
    axp.plot(ths, rs, color=ACCENT2, lw=2.0)
    if ths:
        axp.plot([ths[0]], [rs[0]], marker="o", color=ACCENT2, markersize=5)
        axp.plot([ths[-1]], [rs[-1]], marker="s", color="#d29922",
                 markersize=5)

    # --- Doppler curve (right top) ---
    axd = fig.add_axes([0.54, 0.55, 0.42, 0.32])
    axd.set_facecolor(PANEL)
    store.ensure_transponders(sat)
    tp = (store.selected_transponder(sat)
          if hasattr(store, "selected_transponder")
          else (sat.transponders[0] if getattr(sat, "transponders", None)
                else None))
    dl = tp.downlink_center() if tp and tp.downlink_center() else 145_800_000
    ts, dop = [], []
    t = p.aos
    while t <= p.los:
        look = pred.look(t)
        ts.append((t - p.aos) / 60.0)
        dop.append(LB.doppler_shift_hz(dl, look.range_rate) / 1000.0)
        t += 15.0
    axd.plot(ts, dop, color=ACCENT, lw=1.8)
    axd.axhline(0, color=MUTED, lw=0.6, ls="--")
    axd.set_title("Doppler @ %.3f MHz (kHz)" % (dl / 1e6), color=TEXT,
                  fontsize=8)
    axd.tick_params(colors=MUTED, labelsize=6)
    for sp in axd.spines.values():
        sp.set_color("#30363d")
    axd.set_xlabel("min after AOS", color=MUTED, fontsize=7)

    # --- facts (right bottom) ---
    axt = fig.add_axes([0.54, 0.06, 0.42, 0.40])
    axt.axis("off")
    dur = (p.los - p.aos) / 60.0
    score = LB.pass_quality_score(p.max_el, p.los - p.aos)
    lines = [
        ("AOS", _utc(p.aos)),
        ("TCA", _utc(p.tca) + ("   max el %.0f\u00b0" % p.max_el)),
        ("LOS", _utc(p.los)),
        ("Duration", "%.1f min" % dur),
        ("AOS\u2192LOS az", "%.0f\u00b0 \u2192 %.0f\u00b0"
         % (p.az_aos, p.az_los)),
        ("Quality", "%.0f / 100" % score),
    ]
    y = 0.95
    for k, v in lines:
        axt.text(0.0, y, k, color=MUTED, fontsize=8, fontweight="bold",
                 transform=axt.transAxes, va="top")
        axt.text(0.34, y, v, color=TEXT, fontsize=8, transform=axt.transAxes,
                 va="top")
        y -= 0.16
    fig.text(0.98, 0.02, "OrbitDeck", color=MUTED, fontsize=7, ha="right")


def generate_pass_card(path, store, sat, p):
    fig = plt.figure(figsize=(8, 4.2), dpi=130, facecolor=BG)
    draw_pass_card(fig, store, sat, p)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path
