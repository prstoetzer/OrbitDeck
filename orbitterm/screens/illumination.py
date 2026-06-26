"""orbitterm/screens/illumination.py - sunlit/eclipse illumination view.

Mirrors the desktop Illumination screen for the selected satellite:

  * Raster view  - an ASCII sunlit-vs-eclipse raster over an N-day window, days
    along the x-axis and minutes-into-orbit up the y-axis (bright = sunlit, dark
    = eclipse), with the mean eclipse fraction per orbit. Scroll the window
    forward/back in time.
  * Eclipse table - an umbral-eclipse ephemeris: per-orbit enter/exit/duration/
    interval/beta, or a per-UTC-day summary (count, total, longest, percent of
    day, sun angle). Useful for power-budget reasoning.

All numbers come straight from the OrbitDeck engine (sunlit_at, predict_eclipses,
eclipse_daily_summary), so they match the GUI.
"""

import time

from ..ui import Screen, ScrollList, addstr, hline, cp, ljust
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_OK, CLR_WARN, CLR_DIM,
                  CLR_ACCENT, CLR_ROW_SEL)
from .. import fmt

WINDOW_DAYS = 30          # raster window, matching the GUI
ECLIPSE_DAYS = 7          # default eclipse-table span


class IlluminationScreen(Screen):
    title = "Illumination"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.view = "raster"        # "raster" | "table"
        self.table_mode = "orbit"   # "orbit" | "daily"
        self.day0 = 0               # raster scroll offset, in days
        self.ecl_days = ECLIPSE_DAYS
        self.sl = ScrollList()
        self._page = 10
        # caches
        self._ecl = None
        self._daily = None
        self._key = None

    def on_enter(self):
        self._key = None

    # ---- engine data (cached per sat/day/span) ----
    def _ensure_eclipses(self):
        st = self.state
        sat = st.sat
        if sat is None:
            self._ecl, self._daily = [], []
            return
        key = (sat.norad, self.ecl_days, int(time.time() // 3600))
        if key == self._key and self._ecl is not None:
            return
        pred = st.pred_for(sat)
        t0 = time.time()
        self._ecl = pred.predict_eclipses(t0, max_n=10000,
                                          horizon_days=float(self.ecl_days))
        self._daily = pred.eclipse_daily_summary(t0, days=self.ecl_days)
        self._key = key

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        if sat is None:
            addstr(win, y0, x0, "No satellite selected (press 2).", cp(CLR_WARN))
            return
        addstr(win, y0, x0, sat.name, cp(CLR_TITLE) | _bold())
        tag = "raster" if self.view == "raster" else (
            "eclipse table \u00b7 %s" % self.table_mode)
        addstr(win, y0, x0 + len(sat.name) + 2,
               "Illumination \u2014 %s   (v to switch)" % tag, cp(CLR_DIM))
        if st.pred_for(sat).deepspace_approximate():
            addstr(win, y0 + 1, x0, "deep-space orbit: illumination approximate",
                   cp(CLR_WARN))
        if self.view == "raster":
            self._draw_raster(win, sat, x0, y0 + 2, w, h - 2)
        else:
            self._draw_table(win, sat, x0, y0 + 2, w, h - 2)

    # ---- raster view ----
    def _draw_raster(self, win, sat, x0, y0, w, h):
        st = self.state
        pred = st.pred_for(sat)
        period = sat.period_min or 95.0
        t0 = time.time() + self.day0 * 86400

        label_w = 6                      # "90m " y labels
        gx = x0 + label_w
        gw = min(w - label_w - 1, WINDOW_DAYS)   # 1 column per day
        gh = h - 3
        if gw < 8 or gh < 6:
            addstr(win, y0, x0, "(terminal too small for raster)", cp(CLR_DIM))
            return
        ndays = gw

        addstr(win, y0, x0, "min", cp(CLR_DIM))
        # sample sunlit/eclipse into a gh x ndays grid; row 0 = top = full period
        lit_total = 0
        cell_total = 0
        rows = []
        for r in range(gh):
            # top row is the largest minutes-into-orbit value
            frac_orbit = 1.0 - (r / max(1, gh - 1))
            line = []
            for d in range(ndays):
                tt = t0 + d * 86400 + frac_orbit * period * 60.0
                lit = pred.sunlit_at(tt)
                line.append(lit)
                lit_total += 1 if lit else 0
                cell_total += 1
            rows.append(line)
        # draw, with a couple of y-axis tick labels
        for r in range(gh):
            yy = y0 + 1 + r
            frac_orbit = 1.0 - (r / max(1, gh - 1))
            if r == 0 or r == gh - 1 or r == gh // 2:
                addstr(win, yy, x0, "%3.0fm" % (frac_orbit * period),
                       cp(CLR_DIM))
            cells = []
            for lit in rows[r]:
                cells.append("\u2588" if lit else " ")
            # sunlit bright (yellow), eclipse dark (blank on default bg)
            addstr(win, yy, gx, "".join(cells), cp(CLR_WARN))
        # x axis
        base = y0 + 1 + gh
        hline(win, base, gx, ndays, "\u2500", cp(CLR_DIM))
        addstr(win, base + 1, gx, "+%dd" % self.day0, cp(CLR_DIM))
        addstr(win, base + 1, gx + ndays - 5, "+%dd" % (self.day0 + ndays),
               cp(CLR_DIM))
        addstr(win, base + 1, x0, "day", cp(CLR_DIM))

        frac_ecl = 1.0 - (lit_total / cell_total) if cell_total else 0.0
        addstr(win, y0, gx + ndays - 26 if ndays > 30 else gx,
               "\u2588 sunlit   (blank) eclipse", cp(CLR_DIM))
        msg = "mean eclipse %.0f%% / orbit   window %s \u2192 %s" % (
            frac_ecl * 100,
            fmt.fmt_date(t0), fmt.fmt_date(t0 + ndays * 86400))
        addstr(win, y0 + h - 1, x0, msg, cp(CLR_ACCENT))

    # ---- eclipse table view ----
    def _draw_table(self, win, sat, x0, y0, w, h):
        self._ensure_eclipses()
        if self.table_mode == "orbit":
            self._draw_orbit_table(win, x0, y0, w, h)
        else:
            self._draw_daily_table(win, x0, y0, w, h)
        addstr(win, y0 + h - 1, x0,
               "span %dd   s: orbit/daily   [ ]: prev/next sat   +/- span"
               % self.ecl_days, cp(CLR_DIM))

    def _draw_orbit_table(self, win, x0, y0, w, h):
        ecl = self._ecl or []
        head = "%-12s %-9s %-9s %-8s %-8s %6s" % (
            "DATE", "ENTER", "EXIT", "DUR", "SUN-INT", "BETA")
        addstr(win, y0, x0, head, cp(CLR_HEADER) | _bold())
        hline(win, y0 + 1, x0, min(w, len(head)), "\u2500", cp(CLR_DIM))
        page = h - 3
        self._page = page
        if not ecl:
            addstr(win, y0 + 2, x0,
                   "no umbral eclipses in the next %dd "
                   "(continuous sunlight / high beta)" % self.ecl_days,
                   cp(CLR_OK))
            return
        self.sl.clamp(len(ecl), page)
        for i in range(self.sl.top, min(len(ecl), self.sl.top + page)):
            e = ecl[i]
            yy = y0 + 2 + (i - self.sl.top)
            # sunlight interval to the next eclipse
            if i + 1 < len(ecl):
                intvl = fmt.fmt_dur(ecl[i + 1].enter - e.exit)
            else:
                intvl = "--"
            line = "%-12s %-9s %-9s %-8s %-8s %5.1f\u00b0" % (
                fmt.fmt_date(e.enter), fmt.fmt_clock(e.enter),
                fmt.fmt_clock(e.exit), fmt.fmt_dur(e.duration_s),
                intvl, e.sun_angle)
            attr = cp(CLR_ROW_SEL) | _bold() if i == self.sl.sel else 0
            addstr(win, yy, x0, ljust(line, w - x0), attr)

    def _draw_daily_table(self, win, x0, y0, w, h):
        rows = self._daily or []
        head = "%-15s %4s %-9s %-9s %7s %6s" % (
            "DATE", "N", "TOTAL", "LONGEST", "%DAY", "BETA")
        addstr(win, y0, x0, head, cp(CLR_HEADER) | _bold())
        hline(win, y0 + 1, x0, min(w, len(head)), "\u2500", cp(CLR_DIM))
        page = h - 3
        self._page = page
        if not rows:
            addstr(win, y0 + 2, x0, "no eclipse data", cp(CLR_DIM))
            return
        self.sl.clamp(len(rows), page)
        for i in range(self.sl.top, min(len(rows), self.sl.top + page)):
            r = rows[i]
            yy = y0 + 2 + (i - self.sl.top)
            n = r["count"]
            total = fmt.fmt_dur(r["total_s"]) if r["total_s"] else "--"
            longest = fmt.fmt_dur(r["longest_s"]) if r["longest_s"] else "--"
            pct = r["percent"]
            line = "%-15s %4d %-9s %-9s %6.1f%% %5.1f\u00b0" % (
                fmt.fmt_date(r["date"]), n, total, longest, pct, r["sun_angle"])
            if n == 0:
                attr = cp(CLR_OK)        # a fully sunlit day
            elif pct >= 30:
                attr = cp(CLR_WARN)
            else:
                attr = 0
            if i == self.sl.sel:
                attr = cp(CLR_ROW_SEL) | _bold()
            addstr(win, yy, x0, ljust(line, w - x0), attr)

    # ---- input ----
    def help_keys(self):
        if self.view == "raster":
            return [("v", "table"), ("\u2190\u2192", "scroll"),
                    ("[ ]", "prev/next sat")]
        return [("v", "raster"), ("s", "orbit/daily"), ("\u2191\u2193", "row")]

    def handle_key(self, ch):
        import curses
        if ch in (ord("v"), ord("V")):
            self.view = "table" if self.view == "raster" else "raster"
            return True
        if ch in (ord("["), ord("]")):
            self.app.cycle_sat(-1 if ch == ord("[") else 1)
            self._key = None
            return True
        if self.view == "raster":
            if ch in (curses.KEY_RIGHT, ord("l")):
                self.day0 += 7
                return True
            if ch in (curses.KEY_LEFT, ord("h")):
                self.day0 = max(0, self.day0 - 7)
                return True
            if ch in (ord("0"),):
                self.day0 = 0
                return True
            return False
        # table view
        if ch in (ord("s"), ord("S")):
            self.table_mode = "daily" if self.table_mode == "orbit" else "orbit"
            self.sl.sel = 0
            self.sl.top = 0
            return True
        if ch in (ord("+"), ord("=")):
            self.ecl_days = min(14, self.ecl_days + 1)
            self._key = None
            return True
        if ch in (ord("-"), ord("_")):
            self.ecl_days = max(1, self.ecl_days - 1)
            self._key = None
            return True
        n = len(self._ecl if self.table_mode == "orbit" else self._daily or [])
        if ch in (curses.KEY_DOWN, ord("j")):
            self.sl.move(1, n, self._page)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.sl.move(-1, n, self._page)
            return True
        if ch == curses.KEY_NPAGE:
            self.sl.page_move(1, n, self._page)
            return True
        if ch == curses.KEY_PPAGE:
            self.sl.page_move(-1, n, self._page)
            return True
        return False


def _bold():
    import curses
    return curses.A_BOLD
