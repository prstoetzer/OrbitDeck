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
    global PAGE_W_IN, PAGE_H_IN
    from .pagesize import page_dims
    PAGE_W_IN, PAGE_H_IN = page_dims(store)
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
    BRAND_FLOOR = 0.10        # content must stay above the footer credit
    TOP = 0.89

    # Pre-flatten each entry into the lines it will draw, so we can paginate by
    # measured height (an entry never splits across a page, and no entry is ever
    # pushed into the footer branding).
    def entry_lines(grid, rsat, r):
        """Return a list of ('header'|'kv'|'note', ...) tuples for one stop."""
        if r is None:
            return [("note", grid, "no covering passes in the window")]
        satpart = ("%s   " % rsat) if rsat else ""
        header = ("%s   %s%s  %s\u2013%s UTC   max el %.0f\u00b0"
                  % (grid, satpart, _date(r["aos"]), _utc(r["aos"]),
                     _utc(r["los"]), r["max_el"]))
        states = ", ".join(sorted(r["states"])) or "\u2014"
        # keep the full DXCC entity name (e.g. "United States"); only de-dupe
        dxcc = ", ".join(sorted(set(r["dxcc"]))) or "\u2014"
        ngrids = len(r["grids"])
        out = [("header", header)]
        for label, val in (("States", states), ("DXCC", dxcc),
                           ("Grids", "%d grids in footprint" % ngrids)):
            out.append(("kv", label, _wrap(val, 80)))
        return out

    def lines_height(lines):
        h = 0.0
        for ln in lines:
            if ln[0] == "header":
                h += 0.034
            elif ln[0] == "note":
                h += 0.040
            else:  # kv
                h += 0.018 * (ln[2].count("\n") + 1) + 0.008
        return h + 0.016     # trailing gap between entries

    flat = [entry_lines(g, s, r) for (g, s, r) in entries]

    with PdfPages(path) as pdf:
        i = 0
        n = len(flat)
        first = True
        while i < n or first:
            first = False
            fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
            fig.text(0.5, 0.955, title,
                     ha="center", fontsize=15, fontweight="bold")
            fig.text(0.5, 0.928,
                     "Planned grid stops and the states / DXCC / grids workable "
                     "through each covering pass", ha="center", fontsize=9.5,
                     color="#444444")
            y = TOP
            # place as many whole entries as fit above the branding floor
            placed_any = False
            while i < n:
                lines = flat[i]
                need = lines_height(lines)
                if y - need < BRAND_FLOOR and placed_any:
                    break          # defer to next page
                for ln in lines:
                    if ln[0] == "header":
                        fig.text(0.07, y, ln[1], fontsize=11,
                                 fontweight="bold", color="#0b3d91", va="top")
                        y -= 0.034
                    elif ln[0] == "note":
                        fig.text(0.07, y, ln[1], fontsize=12,
                                 fontweight="bold", color="#0b3d91", va="top")
                        fig.text(0.22, y, ln[2], fontsize=9.5,
                                 color="#999999", va="top")
                        y -= 0.040
                    else:  # kv: label and value share the SAME top, so they line up
                        label, wrapped = ln[1], ln[2]
                        fig.text(0.09, y, "%s:" % label, fontsize=8.5,
                                 fontweight="bold", color="#333333", va="top")
                        fig.text(0.20, y, wrapped, fontsize=8.5,
                                 color="#111111", va="top")
                        y -= 0.018 * (wrapped.count("\n") + 1) + 0.008
                y -= 0.016
                placed_any = True
                i += 1
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
