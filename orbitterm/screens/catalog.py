"""orbitterm/screens/catalog.py - satellite picker and ASCII sky radar."""

import time
import math

from ..ui import Screen, ScrollList, addstr, hline, cp, clip, ljust
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_OK, CLR_WARN, CLR_DIM,
                  CLR_ACCENT, CLR_ROW_SEL)
from .. import fmt


class SatellitesScreen(Screen):
    title = "Satellites"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.sl = ScrollList()
        self.filter = ""
        self.filtering = False
        self._page = 20
        self._cache = None
        self._cache_key = None

    def on_enter(self):
        self._cache = None
        # position selection on the current sat
        sats = self._filtered()
        cur = self.state.selected_norad
        for i, s in enumerate(sats):
            if s.norad == cur:
                self.sl.sel = i
                break

    def _filtered(self):
        st = self.state
        key = (self.filter.lower(), st.store.db.count())
        if key == self._cache_key and self._cache is not None:
            return self._cache
        f = self.filter.lower()
        out = []
        for s in st.sats:
            if not f or f in s.name.lower() or f in str(s.norad):
                out.append(s)
        # favorites first, then by name
        out.sort(key=lambda s: (0 if st.is_favorite(s.norad) else 1,
                                s.name.lower()))
        self._cache = out
        self._cache_key = key
        return out

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sats = self._filtered()
        addstr(win, y0, x0, "Satellites", cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + 12, "%d shown / %d total" % (
            len(sats), st.store.db.count()), cp(CLR_DIM))
        # filter line
        if self.filtering or self.filter:
            addstr(win, y0, x0 + w - 34, "filter: ", cp(CLR_HEADER))
            fattr = cp(CLR_ROW_SEL) if self.filtering else cp(CLR_ACCENT)
            addstr(win, y0, x0 + w - 26, ljust(self.filter + (
                "_" if self.filtering else ""), 24), fattr)

        head = "%-1s %-18s %-7s %-7s %-7s %-8s %s" % (
            "", "NAME", "NORAD", "INCL", "PERIOD", "ALT", "STATUS")
        addstr(win, y0 + 2, x0, head, cp(CLR_DIM) | _bold())
        hline(win, y0 + 3, x0, min(w, len(head) + 6), "\u2500", cp(CLR_DIM))

        rows_y0 = y0 + 4
        page = h - 5
        self._page = page
        self.sl.clamp(len(sats), page)
        now = time.time()
        pred = st.store.pred
        pred.set_site(st.obs)
        for i in range(self.sl.top, min(len(sats), self.sl.top + page)):
            s = sats[i]
            yy = rows_y0 + (i - self.sl.top)
            fav = "\u2605" if st.is_favorite(s.norad) else " "
            # quick up/down status (cheap azel)
            stat = ""
            sattr = cp(CLR_DIM)
            if pred.set_sat(s):
                el = pred.azel_at(now)[1]
                if el > 0:
                    stat = "UP el %.0f\u00b0" % el
                    sattr = cp(CLR_OK)
                else:
                    stat = "down"
            alt = s.apogee_km
            line = "%-1s %-18s %-7d %5.1f\u00b0 %5.1fm %6.0fkm" % (
                fav, clip(s.name, 18), s.norad, s.incl, s.period_min, alt)
            if i == self.sl.sel:
                addstr(win, yy, x0, ljust(line + "  " + stat, w - x0),
                       cp(CLR_ROW_SEL) | _bold())
            else:
                addstr(win, yy, x0, line)
                addstr(win, yy, x0 + len(line) + 2, stat, sattr)
            if s.norad == st.selected_norad:
                addstr(win, yy, x0 + w - 3, "\u25c0", cp(CLR_ACCENT) | _bold())

    def help_keys(self):
        if self.filtering:
            return [("type", "filter"), ("\u21b5", "apply"), ("esc", "cancel")]
        return [("\u2191\u2193", "move"), ("\u21b5", "select"),
                ("/", "search"), ("f", "favorite")]

    def handle_key(self, ch):
        import curses
        if self.filtering:
            if ch in (27,):  # esc
                self.filtering = False
                self.filter = ""
                self._cache = None
                return True
            if ch in (curses.KEY_ENTER, 10, 13):
                self.filtering = False
                return True
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                self.filter = self.filter[:-1]
                self._cache = None
                return True
            if 32 <= ch < 127:
                self.filter += chr(ch)
                self._cache = None
                self.sl.sel = 0
                return True
            return True
        sats = self._filtered()
        n = len(sats)
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
        if ch == curses.KEY_HOME:
            self.sl.home(n, self._page)
            return True
        if ch == curses.KEY_END:
            self.sl.end(n, self._page)
            return True
        if ch in (curses.KEY_ENTER, 10, 13):
            if sats:
                self.state.select(sats[self.sl.sel].norad)
                self.state.flash("Selected %s" % sats[self.sl.sel].name)
            return True
        if ch == ord("/"):
            self.filtering = True
            return True
        if ch in (ord("f"), ord("F")):
            if sats:
                self.state.toggle_favorite(sats[self.sl.sel].norad)
                self._cache = None
            return True
        return False


class RadarScreen(Screen):
    title = "Sky Radar"
    refresh_secs = 2.0

    def draw(self, win, y0, x0, h, w):
        st = self.state
        now = time.time()
        addstr(win, y0, x0, "Sky Radar", cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + 11, "everything currently above the horizon",
               cp(CLR_DIM))

        # find all sats up now
        ups = []
        pred = st.store.pred
        pred.set_site(st.obs)
        for s in st.sats[:400]:
            if not pred.set_sat(s):
                continue
            az, el = pred.azel_at(now)
            if el > 0:
                ups.append((s, az, el))
        ups.sort(key=lambda r: -r[2])

        # radar geometry: a circle in the left area
        plot_h = h - 2
        radius = min((plot_h - 1) // 2, (w // 2 - 2) // 2)
        if radius < 4:
            radius = 4
        cy = y0 + 2 + radius
        cx = x0 + radius * 2 + 2     # 2:1 char aspect
        self._draw_grid(win, cx, cy, radius)

        # plot sats (N up, E right, az clockwise; el: rim=0, centre=90)
        for idx, (s, az, el) in enumerate(ups):
            r = (1 - el / 90.0) * radius
            a = math.radians(az)
            px = cx + int(round(r * math.sin(a) * 2))   # 2x for char aspect
            py = cy - int(round(r * math.cos(a)))
            mk = chr(ord("a") + idx) if idx < 26 else "*"
            attr = cp(CLR_OK) if el >= 30 else cp(CLR_WARN)
            addstr(win, py, px, mk, attr | _bold())

        # legend on the right
        lx = cx + radius * 2 + 4
        ly = y0 + 2
        addstr(win, ly, lx, "%-3s %-15s %8s %6s" % ("", "SAT", "AZ", "EL"),
               cp(CLR_DIM) | _bold())
        ly += 1
        if not ups:
            addstr(win, ly, lx, "nothing up right now", cp(CLR_DIM))
        for idx, (s, az, el) in enumerate(ups):
            if ly >= y0 + h - 1:
                break
            mk = chr(ord("a") + idx) if idx < 26 else "*"
            attr = cp(CLR_OK) if el >= 30 else cp(CLR_WARN)
            sel = " \u25c0" if s.norad == st.selected_norad else ""
            addstr(win, ly, lx, "%-3s %-15s %7s %5.0f\u00b0%s" % (
                mk, clip(s.name, 15), fmt.fmt_az(az), el, sel), attr)
            ly += 1

    def _draw_grid(self, win, cx, cy, radius):
        # elevation rings at 0 (rim), 30, 60
        for ring_el, ch in [(0, "\u00b7"), (30, "\u00b7"), (60, "\u00b7")]:
            rr = (1 - ring_el / 90.0) * radius
            steps = max(24, int(rr * 8))
            for k in range(steps):
                a = 2 * math.pi * k / steps
                px = cx + int(round(rr * math.sin(a) * 2))
                py = cy - int(round(rr * math.cos(a)))
                addstr(win, py, px, ch, cp(CLR_DIM))
        # cardinal labels
        addstr(win, cy - radius - 1, cx, "N", cp(CLR_HEADER) | _bold())
        addstr(win, cy + radius + 1, cx, "S", cp(CLR_HEADER) | _bold())
        addstr(win, cy, cx + radius * 2 + 1, "E", cp(CLR_HEADER) | _bold())
        addstr(win, cy, cx - radius * 2 - 1, "W", cp(CLR_HEADER) | _bold())
        addstr(win, cy, cx, "+", cp(CLR_ACCENT) | _bold())

    def help_keys(self):
        return [("a-z", "= sat in list")]


def _bold():
    import curses
    return curses.A_BOLD
