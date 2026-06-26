"""orbitterm/screens/passes.py - upcoming passes and per-pass detail."""

import time

from ..ui import Screen, ScrollList, addstr, hline, cp, ljust
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_OK, CLR_WARN, CLR_BAD, CLR_DIM,
                  CLR_ACCENT, CLR_ROW_SEL)
from .. import fmt


class PassesScreen(Screen):
    title = "Next Passes"
    refresh_secs = 2.0

    def __init__(self, app):
        super().__init__(app)
        self.sl = ScrollList()
        self._passes = []
        self._scanned_for = None
        self._scanned_at = 0.0

    def on_enter(self):
        self._scanned_for = None   # force a rescan

    def _ensure(self):
        st = self.state
        sat = st.sat
        if sat is None:
            self._passes = []
            return
        now = time.time()
        key = (sat.norad, round(st.min_el))
        # rescan when sat/min_el changes or every 60 s
        if key != self._scanned_for or now - self._scanned_at > 60:
            pred = st.pred_for(sat)
            self._passes = pred.predict_passes(now, st.min_el, 30)
            self._scanned_for = key
            self._scanned_at = now

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        self._ensure()
        now = time.time()
        if sat is None:
            addstr(win, y0, x0, "No satellite selected (press 2).", cp(CLR_WARN))
            return
        addstr(win, y0, x0, "Passes for ", cp(CLR_HEADER))
        addstr(win, y0, x0 + 11, sat.name, cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + 11 + len(sat.name) + 2,
               "min el %.0f\u00b0  (e/E to change)" % st.min_el, cp(CLR_DIM))

        head = "%-3s %-13s %-6s %-7s %-6s %5s  %-8s %-8s" % (
            "#", "DATE", "AOS", "TCA", "LOS", "MAXEL", "AOS-AZ", "LOS-AZ")
        addstr(win, y0 + 2, x0, head, cp(CLR_DIM) | _bold())
        hline(win, y0 + 3, x0, min(w, len(head)), "\u2500", cp(CLR_DIM))

        rows_y0 = y0 + 4
        page = h - 5
        self.sl.clamp(len(self._passes), page)
        if not self._passes:
            addstr(win, rows_y0, x0, "no passes above %.0f\u00b0 in next 10 days"
                   % st.min_el, cp(CLR_DIM))
            return
        for i in range(self.sl.top, min(len(self._passes), self.sl.top + page)):
            p = self._passes[i]
            yy = rows_y0 + (i - self.sl.top)
            soon = p.aos - now
            line = "%-3d %-13s %-6s %-7s %-6s %4.0f\u00b0  %-8s %-8s" % (
                i + 1, fmt.fmt_date(p.aos), fmt.fmt_hm(p.aos),
                fmt.fmt_hm(p.tca), fmt.fmt_hm(p.los), p.max_el,
                _az_compact(p.az_aos), _az_compact(p.az_los))
            attr = 0
            if p.max_el >= 45:
                attr = cp(CLR_OK)
            elif p.max_el >= 20:
                attr = cp(CLR_WARN)
            else:
                attr = cp(CLR_DIM)
            if i == self.sl.sel:
                attr = cp(CLR_ROW_SEL) | _bold()
            addstr(win, yy, x0, ljust(line, w - x0), attr)
            if 0 < soon < 3600 and i != self.sl.sel:
                addstr(win, yy, x0 + min(w - 10, len(line) + 1),
                       "in %s" % fmt.fmt_dur(soon), cp(CLR_ACCENT))

    def help_keys(self):
        return [("\u2191\u2193", "select"), ("\u21b5", "detail"),
                ("e/E", "min-el -/+")]

    def handle_key(self, ch):
        import curses
        n = len(self._passes)
        if ch in (curses.KEY_DOWN, ord("j")):
            self.sl.move(1, n, max(1, self._page))
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.sl.move(-1, n, max(1, self._page))
            return True
        if ch == curses.KEY_NPAGE:
            self.sl.page_move(1, n, max(1, self._page))
            return True
        if ch == curses.KEY_PPAGE:
            self.sl.page_move(-1, n, max(1, self._page))
            return True
        if ch in (curses.KEY_ENTER, 10, 13):
            if self._passes:
                self.app.show_pass_detail(self._passes[self.sl.sel])
            return True
        if ch == ord("e"):
            self.state.set_min_el(max(0, self.state.min_el - 5))
            self._scanned_for = None
            return True
        if ch == ord("E"):
            self.state.set_min_el(self.state.min_el + 5)
            self._scanned_for = None
            return True
        return False

    _page = 20  # updated each draw via property below

    @property
    def _page(self):
        return getattr(self, "_page_val", 20)

    @_page.setter
    def _page(self, v):
        self._page_val = v


class PassDetailScreen(Screen):
    title = "Pass Detail"
    refresh_secs = 1.0

    def __init__(self, app):
        super().__init__(app)
        self.pass_ = None     # the PassPredict to detail, or None for next

    def on_enter(self):
        # if no explicit pass set, use the next one for the selected sat
        if self.pass_ is None:
            st = self.state
            sat = st.sat
            if sat is not None:
                ps = st.pred_for(sat).predict_passes(time.time(), st.min_el, 1)
                self.pass_ = ps[0] if ps else None

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        now = time.time()
        if sat is None or self.pass_ is None:
            addstr(win, y0, x0, "No pass to detail. Pick one in Passes (4).",
                   cp(CLR_WARN))
            return
        p = self.pass_
        pred = st.pred_for(sat)
        addstr(win, y0, x0, sat.name, cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + len(sat.name) + 2, fmt.fmt_clock(p.aos, True),
               cp(CLR_DIM))

        # summary line
        y = y0 + 2
        dur = p.los - p.aos
        if now < p.aos:
            cd = "AOS in " + fmt.fmt_dur(p.aos - now)
            cattr = cp(CLR_ACCENT)
        elif now < p.los:
            cd = "IN PROGRESS \u2014 LOS in " + fmt.fmt_dur(p.los - now)
            cattr = cp(CLR_OK) | _bold()
        else:
            cd = "completed"
            cattr = cp(CLR_DIM)
        addstr(win, y, x0, cd, cattr)
        addstr(win, y, x0 + 30, "max el %.1f\u00b0   duration %s" % (
            p.max_el, fmt.fmt_dur(dur)))
        y += 2

        # event table: AOS / TCA / LOS
        addstr(win, y, x0, "%-6s %-10s %-9s %-7s" % ("EVENT", "TIME", "AZ", "EL"),
               cp(CLR_HEADER) | _bold())
        y += 1
        for name, t in [("AOS", p.aos), ("TCA", p.tca), ("LOS", p.los)]:
            az, el = pred.azel_at(t)
            addstr(win, y, x0, "%-6s %-10s %-9s %5.1f\u00b0" % (
                name, fmt.fmt_clock(t), fmt.fmt_az(az), el))
            y += 1
        y += 1

        # ASCII sky track for the pass: elevation profile over time
        self._draw_sky(win, x0, y, w - x0, (y0 + h) - y - 1, pred, p)

    def _draw_sky(self, win, x0, y0, w, h, pred, p):
        if h < 6 or w < 30:
            return
        addstr(win, y0, x0, "Elevation profile", cp(CLR_HEADER) | _bold())
        gy0 = y0 + 1
        gh = h - 2
        gw = min(w - 8, 60)
        # sample elevation across the pass
        n = gw
        els = []
        for i in range(n):
            t = p.aos + (p.los - p.aos) * i / max(1, n - 1)
            els.append(pred.azel_at(t)[1])
        # y axis labels: 0,30,60,90
        for el_lab in (90, 60, 30, 0):
            row = gy0 + int((1 - el_lab / 90.0) * (gh - 1))
            addstr(win, row, x0, "%2d\u00b0" % el_lab, cp(CLR_DIM))
        # plot
        now = time.time()
        for i, el in enumerate(els):
            if el < 0:
                continue
            row = gy0 + int((1 - min(el, 90) / 90.0) * (gh - 1))
            col = x0 + 5 + i
            ch = "\u2588"
            attr = cp(CLR_OK) if el >= 30 else cp(CLR_WARN)
            # mark current time position
            t_i = p.aos + (p.los - p.aos) * i / max(1, n - 1)
            if abs(t_i - now) < (p.los - p.aos) / (2 * n):
                attr = cp(CLR_BAD) | _bold()
                ch = "\u2502"
            addstr(win, row, col, ch, attr)
        # baseline
        base = gy0 + gh - 1
        hline(win, base, x0 + 5, gw, "\u2500", cp(CLR_DIM))
        addstr(win, base + 1, x0 + 5, fmt.fmt_hm(p.aos), cp(CLR_DIM))
        addstr(win, base + 1, x0 + 5 + gw - 5, fmt.fmt_hm(p.los), cp(CLR_DIM))

    def help_keys(self):
        return [("n", "next pass"), ("4", "passes list")]

    def handle_key(self, ch):
        if ch in (ord("n"), ord("N")):
            st = self.state
            sat = st.sat
            if sat and self.pass_:
                ps = st.pred_for(sat).predict_passes(
                    self.pass_.los + 60, st.min_el, 1)
                if ps:
                    self.pass_ = ps[0]
            return True
        return False


def _az_compact(az):
    return "%3.0f\u00b0%s" % (az % 360, fmt.compass(az))


def _bold():
    import curses
    return curses.A_BOLD
