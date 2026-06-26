"""orbitterm/screens/progression.py - Pass Progression (10-day timeline).

Mirrors the desktop "Pass Progression" screen: the selected satellite's passes
over N days drawn as one 24-hour timeline per day, each pass placed at its time
of day with a width set by its duration and a shade keyed to maximum elevation.
"""

import time

from ..ui import Screen, ScrollList, addstr, hline, cp, ljust
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_OK, CLR_WARN, CLR_DIM, CLR_ACCENT)


def _el_attr(el):
    # match the desktop shading: high passes bright/green, mid yellow, low dim
    if el >= 45:
        return cp(CLR_OK), "\u2588"
    if el >= 20:
        return cp(CLR_WARN), "\u2593"
    return cp(CLR_DIM), "\u2592"


class ProgressionScreen(Screen):
    title = "Pass Progression"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.ndays = 10
        self._passes = None
        self._key = None
        self.sl = ScrollList()
        self._page = 10

    def on_enter(self):
        self._key = None     # force reload

    def _ensure(self):
        st = self.state
        sat = st.sat
        if sat is None:
            self._passes = []
            return
        key = (sat.norad, round(st.min_el), self.ndays,
               int(time.time() // 3600))    # refresh hourly
        if key == self._key and self._passes is not None:
            return
        t0 = time.time()
        pred = st.pred_for(sat)
        self._passes = pred.predict_passes(
            t0, st.min_el, 2000, t0 + self.ndays * 86400)
        self._key = key
        self._t0 = t0

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        self._ensure()
        if sat is None:
            addstr(win, y0, x0, "No satellite selected (press 2).", cp(CLR_WARN))
            return
        addstr(win, y0, x0, sat.name, cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + len(sat.name) + 2,
               "%d passes over %d days  (min el %.0f\u00b0)" % (
                   len(self._passes), self.ndays, st.min_el), cp(CLR_DIM))

        # hour axis: scale 24h across the available timeline width
        label_w = 11           # "Mon 30 Jun "
        axis_x = x0 + label_w
        tl_w = w - label_w - 1
        if tl_w < 24:
            addstr(win, y0 + 2, x0, "(terminal too narrow)", cp(CLR_DIM))
            return
        # top hour ruler: mark 00 06 12 18 24
        ruler = [" "] * tl_w
        for hh in (0, 6, 12, 18, 24):
            col = min(tl_w - 2, int(hh / 24 * tl_w))
            lab = "%02d" % (hh % 24)
            for k, cch in enumerate(lab):
                if col + k < tl_w:
                    ruler[col + k] = cch
        addstr(win, y0 + 2, x0, "local h", cp(CLR_DIM))
        addstr(win, y0 + 2, axis_x, "".join(ruler), cp(CLR_DIM))
        hline(win, y0 + 3, axis_x, tl_w, "\u2500", cp(CLR_DIM))

        # group passes by local day
        import datetime as dt
        start_day = dt.date.fromtimestamp(self._t0)
        rows_y0 = y0 + 4
        page = h - 5
        self._page = page
        self.sl.clamp(self.ndays, page)

        for di in range(self.sl.top, min(self.ndays, self.sl.top + page)):
            day = start_day + dt.timedelta(days=di)
            yy = rows_y0 + (di - self.sl.top)
            day_label = day.strftime("%a %d %b")
            sel = (di == self.sl.sel)
            addstr(win, yy, x0, ljust(day_label, label_w),
                   cp(CLR_HEADER) if not sel else cp(CLR_ACCENT) | _bold())
            # day background dots every 6h
            for hh in (6, 12, 18):
                col = int(hh / 24 * tl_w)
                addstr(win, yy, axis_x + col, "\u00b7", cp(CLR_DIM))
            # passes that fall on this day (by AOS local date)
            day_passes = [p for p in self._passes
                          if dt.date.fromtimestamp(p.aos) == day]
            for p in day_passes:
                lt = time.localtime(p.aos)
                frac = (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec) / 86400.0
                col = int(frac * tl_w)
                dur = max(1, int((p.los - p.aos) / 86400.0 * tl_w))
                attr, chh = _el_attr(p.max_el)
                for k in range(dur):
                    if col + k < tl_w:
                        addstr(win, yy, axis_x + col + k, chh, attr)
                # mark peak with elevation number if room
                if dur >= 3:
                    addstr(win, yy, axis_x + col, "%d" % int(p.max_el),
                           attr | _bold())

        # legend
        ly = y0 + h - 1
        addstr(win, ly, x0, "shade = max el:", cp(CLR_DIM))
        addstr(win, ly, x0 + 15, "\u2588 \u226545\u00b0", cp(CLR_OK))
        addstr(win, ly, x0 + 22, "\u2593 \u226520\u00b0", cp(CLR_WARN))
        addstr(win, ly, x0 + 29, "\u2592 <20\u00b0", cp(CLR_DIM))
        addstr(win, ly, x0 + 38, "+/- more/fewer days", cp(CLR_DIM))

    def help_keys(self):
        return [("\u2191\u2193", "day"), ("+/-", "days"), ("[ ]", "prev/next sat")]

    def handle_key(self, ch):
        import curses
        if ch in (curses.KEY_DOWN, ord("j")):
            self.sl.move(1, self.ndays, self._page)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.sl.move(-1, self.ndays, self._page)
            return True
        if ch in (ord("+"), ord("=")):
            self.ndays += 7
            self._key = None
            return True
        if ch in (ord("-"), ord("_")):
            self.ndays = max(1, self.ndays - 7)
            self._key = None
            return True
        if ch in (ord("["), ord("]")):
            self.app.cycle_sat(-1 if ch == ord("[") else 1)
            self._key = None
            return True
        return False


def _bold():
    import curses
    return curses.A_BOLD
