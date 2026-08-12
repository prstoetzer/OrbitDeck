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
        # CelesTrak search: the desktop app could add a satellite that is not
        # in the local catalog and OrbitTerm could not, which meant opening the
        # desktop app just to get an object.
        self.searching = False
        self.sbuf = ""
        self.hits = []
        self.hit_sel = 0
        self.msg = ""

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
        if self.searching or self.hits or self.msg:
            self._draw_search(win, y0, x0, h, w)
            if self.searching or self.hits:
                return
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
            # Reserve the last two columns for the active-satellite marker and
            # highlight only up to there. ljust(..., w - x0) assumed w was the
            # screen width when it is already the content width, so the row ran
            # under the marker and the period/altitude were overwritten.
            marker = (s.norad == st.selected_norad)
            avail = max(1, w - (2 if marker else 0))
            if i == self.sl.sel:
                addstr(win, yy, x0, ljust(clip(line + "  " + stat, avail),
                                          avail),
                       cp(CLR_ROW_SEL) | _bold())
            else:
                addstr(win, yy, x0, clip(line, avail))
                if len(line) + 2 + len(stat) <= avail:
                    addstr(win, yy, x0 + len(line) + 2, stat, sattr)
            if marker:
                addstr(win, yy, x0 + w - 2, "\u25c0", cp(CLR_ACCENT) | _bold())

    def help_keys(self):
        if self.searching:
            return [("ENTER", "search"), ("ESC", "cancel")]
        if self.hits:
            return [("ENTER", "add"), ("up/dn", "pick"), ("ESC", "close")]
        if self.filtering:
            return [("type", "filter"), ("\u21b5", "apply"), ("esc", "cancel")]
        # "/" filters the LOCAL list; "s" searches CelesTrak's whole catalog.
        # Labelling "/" as "search" made those look like the same action.
        return [("\u2191\u2193", "move"), ("\u21b5", "select"),
                ("/", "filter"), ("s", "CelesTrak"), ("f", "favorite")]

    def _draw_search(self, win, y0, x0, h, w):
        """The CelesTrak search prompt and its results."""
        if self.searching:
            addstr(win, y0, x0, clip(
                "CelesTrak search: %s_" % self.sbuf, w), cp(CLR_ACCENT))
            addstr(win, y0 + 1, x0, clip(self.msg, w), cp(CLR_DIM))
            return
        if self.hits:
            addstr(win, y0, x0, clip(
                "CelesTrak results for \u201c%s\u201d" % self.sbuf, w),
                cp(CLR_TITLE))
            addstr(win, y0 + 1, x0, clip(self.msg, w), cp(CLR_DIM))
            addstr(win, y0 + 3, x0, clip("%-24s %8s %-12s %s" % (
                "NAME", "NORAD", "DESIG", "SOURCE"), w), cp(CLR_HEADER))
            for i, hit in enumerate(self.hits):
                y = y0 + 4 + i
                if y >= y0 + h - 1:
                    break
                attr = cp(CLR_ROW_SEL) | _bold() if i == self.hit_sel else 0
                addstr(win, y, x0, clip("%-24s %8s %-12s %s" % (
                    str(hit.get("name", ""))[:24], hit.get("norad", ""),
                    str(hit.get("intl_des", "") or "")[:12],
                    str(hit.get("group", "") or "")[:14]), w), attr)
            return
        addstr(win, y0 + h - 1, x0, clip(self.msg, w), cp(CLR_DIM))

    def _do_search(self):
        """Search CelesTrak's whole catalog, as the desktop app does."""
        q = self.sbuf.strip()
        self.searching = False
        if not q:
            self.msg = ""
            return
        self.msg = "searching CelesTrak for %s\u2026" % q
        try:
            self.hits = self.state.store.search_celestrak(q) or []
        except ValueError as exc:
            self.hits = []
            self.msg = str(exc)[:70]        # rate limit / too soon
            return
        except Exception as exc:
            self.hits = []
            self.msg = "search failed: %s" % str(exc)[:60]
            return
        self.hit_sel = 0
        self.msg = ("%d match(es) \u2014 up/down, ENTER adds" % len(self.hits)
                    if self.hits else
                    "no CelesTrak object matches \u201c%s\u201d" % q)

    def _add_hit(self):
        """Add the selected search result to the catalog and favorite it."""
        if not self.hits:
            return
        hit = self.hits[self.hit_sel % len(self.hits)]
        store = self.state.store
        norad = hit.get("norad")
        existing = store.db.get(norad) if norad else None
        if existing is not None:
            store.favorites.add(existing.norad)
            store.save_config()
            self.msg = "%s (NORAD %d) was already in the catalog \u2014 starred" % (
                existing.name, existing.norad)
        else:
            try:
                store.add_extra_sat(hit, make_favorite=True)
                self.msg = "added %s (NORAD %s)" % (hit.get("name"), norad)
            except Exception as exc:
                self.msg = "could not add: %s" % str(exc)[:60]
                return
        self.hits = []
        self._cache = None

    def handle_key(self, ch):
        import curses
        if self.searching:
            if ch in (ord("\n"), curses.KEY_ENTER):
                self._do_search()
            elif ch == 27:
                self.searching = False
                self.hits = []
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                self.sbuf = self.sbuf[:-1]
            elif 32 <= ch < 127:
                self.sbuf += chr(ch)
            return True
        if self.hits:
            # results are showing: pick one to add, or dismiss
            if ch in (curses.KEY_DOWN, ord("j")):
                self.hit_sel = (self.hit_sel + 1) % len(self.hits)
                return True
            if ch in (curses.KEY_UP, ord("k")):
                self.hit_sel = (self.hit_sel - 1) % len(self.hits)
                return True
            if ch in (ord("\n"), curses.KEY_ENTER, ord("a")):
                self._add_hit()
                return True
            if ch == 27:
                self.hits = []
                self.msg = ""
                return True
        if ch in (ord("s"), ord("S")):
            self.searching = True
            self.sbuf = ""
            self.hits = []
            self.msg = "type a name or NORAD number, ENTER to search"
            return True
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

        # Sub-satellite point of the ACTIVE satellite - CardSat's radar shows
        # where the bird actually is, not just where to point.
        if ly < y0 + h - 1 and st.sat is not None:
            try:
                p2 = st.pred_for(st.sat)
                slat, slon, salt = p2.subpoint_at(now)
                ly += 1
                avail = max(8, x0 + w - lx)
                addstr(win, ly, lx, clip("%s over" % clip(st.sat.name, 10),
                                         avail), cp(CLR_ACCENT))
                if ly + 1 < y0 + h - 1:
                    # Two lines: the lat/lon pair plus a name does not fit the
                    # radar's right-hand column, and clipping lost the
                    # longitude - the half that says where it actually is.
                    addstr(win, ly + 1, lx, clip(
                        fmt.fmt_latlon(slat, slon), avail), cp(CLR_ACCENT))
                if ly + 2 < y0 + h - 1:
                    addstr(win, ly + 2, lx, clip("alt %.0f km" % salt, avail),
                           cp(CLR_DIM))
            except Exception:
                pass

    def _draw_grid(self, win, cx, cy, radius):
        """Polar grid drawn on the braille canvas.

        Character-cell rings were visibly polygonal at terminal sizes; braille
        gives 2x4 dots per cell so the 30/60-degree elevation rings and the
        cardinal spokes come out round.
        """
        from ..canvas import Canvas, blit
        # The grid must span the same area the SATELLITE MARKERS use, or the
        # rings mean nothing. A marker at the horizon sits at +/-2*radius cells
        # and +/-radius rows, i.e. 4*radius dots either way (2 dots per cell
        # across, 4 per row down). The canvas was half that, so every object
        # below about 60 degrees fell outside the drawn horizon ring.
        cols = radius * 4 + 1
        rows = max(2, radius * 2 + 1)
        cv = Canvas(cols, rows)
        ccx, ccy = cv.width // 2, cv.height // 2
        rr = min(ccx, ccy) - 1
        if rr < 2:
            return
        for frac in (1.0, 2.0 / 3.0, 1.0 / 3.0):      # el 0, 30, 60
            cv.circle(ccx, ccy, max(1, int(rr * frac)), cp(CLR_DIM))
        for ang in (0, 90, 180, 270):
            a = math.radians(ang)
            cv.line(ccx, ccy, ccx + rr * math.sin(a), ccy - rr * math.cos(a),
                    cp(CLR_DIM))
        blit(win, cv, cy - rows // 2, cx - cols // 2)
        for lab, ang in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
            a = math.radians(ang)
            px = cx + int(round((radius + 1) * math.sin(a) * 2))
            py = cy - int(round((radius + 1) * math.cos(a)))
            addstr(win, py, px, lab, cp(CLR_ACCENT))

    def help_keys(self):
        return [("a-z", "= sat in list")]


def _bold():
    import curses
    return curses.A_BOLD
