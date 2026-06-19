"""rovesheet.py - printable rove plan sheet.

Lays out a rover's planned grid stops and, for each covering pass of the chosen
satellite, the workable US states, DXCC entities, and grids. Pure-matplotlib
PdfPages output to match the rest of OrbitDeck's printables, and carries the
OrbitDeck + author credit on every page.
"""

import datetime as dt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages   # noqa: E402


PAGE_W_IN = 8.5
PAGE_H_IN = 11.0
ROWS_PER_PAGE = 11


def _utc(unix):
    return dt.datetime.fromtimestamp(unix, dt.timezone.utc).strftime("%H:%M")


def _date(unix):
    return dt.datetime.fromtimestamp(unix, dt.timezone.utc).strftime("%Y-%m-%d")


def _brand(fig):
    try:
        from .. import __version__ as _ver
    except Exception:
        _ver = ""
    fig.text(0.5, 0.045,
             "OrbitDeck%s \u2022 Paul Stoetzer, N8HM"
             % (" v%s" % _ver if _ver else ""),
             ha="center", va="bottom", fontsize=6.5, color="#9a9a9a")


def generate_rove_sheet_pdf(path, sat_name, store, rove_rows):
    """rove_rows is a list of (grid, sat_name, result|None) as produced by the
    Rove tab, where result is a dict {aos, los, max_el, grids, states, dxcc}."""
    # flatten into printable entries, tolerating the older 2-tuple shape
    entries = []
    for row in rove_rows:
        if len(row) == 3:
            grid, rsat, r = row
        else:
            grid, r = row
            rsat = ""
        entries.append((grid, rsat, r))

    title = ("%s \u2014 Rove Plan" % sat_name) if sat_name else "Rove Plan"
    with PdfPages(path) as pdf:
        for pg in range(0, max(1, len(entries)), ROWS_PER_PAGE):
            chunk = entries[pg:pg + ROWS_PER_PAGE]
            fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
            fig.text(0.5, 0.955, title,
                     ha="center", fontsize=15, fontweight="bold")
            fig.text(0.5, 0.928,
                     "Planned grid stops and the states / DXCC / grids workable "
                     "through each covering pass", ha="center", fontsize=9.5,
                     color="#444444")
            y = 0.89
            for grid, rsat, r in chunk:
                if r is None:
                    fig.text(0.07, y, "%s" % grid, fontsize=12,
                             fontweight="bold", color="#0b3d91")
                    fig.text(0.20, y, "no covering passes in the window",
                             fontsize=9.5, color="#999999")
                    y -= 0.06
                    continue
                satpart = ("%s   " % rsat) if rsat else ""
                header = ("%s   %s%s  %s\u2013%s UTC   max el %.0f\u00b0"
                          % (grid, satpart, _date(r["aos"]), _utc(r["aos"]),
                             _utc(r["los"]), r["max_el"]))
                fig.text(0.07, y, header, fontsize=11, fontweight="bold",
                         color="#0b3d91")
                y -= 0.022
                states = ", ".join(sorted(r["states"])) or "\u2014"
                dxcc = ", ".join(sorted(d.split()[0] for d in r["dxcc"])) \
                    or "\u2014"
                # The user asked to list DXCC/states. Grids under a satellite
                # footprint number in the thousands, so we summarise them as a
                # count rather than dumping an unreadable list onto the sheet.
                ngrids = len(r["grids"])
                for label, val in (("States", states), ("DXCC", dxcc),
                                   ("Grids", "%d grids in footprint" % ngrids)):
                    wrapped = _wrap(val, 88)
                    fig.text(0.09, y, "%s:" % label, fontsize=8.5,
                             fontweight="bold", color="#333333")
                    fig.text(0.19, y, wrapped, fontsize=8.5, color="#111111",
                             va="top")
                    y -= 0.016 * (wrapped.count("\n") + 1) + 0.006
                y -= 0.014
            _brand(fig)
            pdf.savefig(fig)
            plt.close(fig)
    return path


def _wrap(text, width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)
