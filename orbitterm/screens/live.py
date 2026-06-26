"""orbitterm/screens/live.py - Home dashboard and live Track screens."""

import time

from ..ui import Screen, addstr, cp, clip, ljust
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_OK, CLR_WARN, CLR_BAD, CLR_DIM,
                  CLR_ACCENT, CLR_VIS)
from .. import fmt


class HomeScreen(Screen):
    title = "Home"
    refresh_secs = 1.0

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        now = time.time()
        addstr(win, y0, x0, "OrbitTerm", cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + 11, "\u2014 terminal companion to OrbitDeck",
               cp(CLR_DIM))
        y = y0 + 2
        # station
        addstr(win, y, x0, "Station", cp(CLR_HEADER) | _bold())
        addstr(win, y, x0 + 12, "%s   %s" % (
            st.store.obs_name, fmt.fmt_latlon(st.obs.lat, st.obs.lon)))
        addstr(win, y, x0 + 12 + 40, "grid %s" % st.grid(), cp(CLR_DIM))
        y += 1
        addstr(win, y, x0, "Catalog", cp(CLR_HEADER) | _bold())
        age = st.catalog_age_days()
        if st.using_sample():
            cinfo = "sample data (offline) \u2014 press R to fetch AMSAT"
            cattr = cp(CLR_WARN)
        else:
            cinfo = "%d satellites" % st.store.db.count()
            if age is not None:
                cinfo += "  (elements %.1f days old)" % age
            cattr = cp(CLR_OK) if (age or 0) < 7 else cp(CLR_WARN)
        addstr(win, y, x0 + 12, cinfo, cattr)
        y += 2

        if sat is None:
            addstr(win, y, x0, "No satellite selected. Press 2 for Satellites.",
                   cp(CLR_WARN))
            return

        # selected satellite live look
        pred = st.pred_for(sat)
        L = pred.look(now)
        addstr(win, y, x0, "Selected", cp(CLR_HEADER) | _bold())
        addstr(win, y, x0 + 12, sat.name, cp(CLR_ACCENT) | _bold())
        addstr(win, y, x0 + 12 + len(sat.name) + 2,
               "#%d  incl %.1f\u00b0  %.1f min" % (
                   sat.norad, sat.incl, sat.period_min), cp(CLR_DIM))
        y += 1
        if L.visible:
            addstr(win, y, x0 + 12, "UP NOW  ", cp(CLR_VIS) | _bold())
            addstr(win, y, x0 + 12 + 8, "az %s   el %s   %s" % (
                fmt.fmt_az(L.az), fmt.fmt_el(L.el),
                fmt.el_bar(L.el)), cp(CLR_OK))
        else:
            addstr(win, y, x0 + 12, "below horizon", cp(CLR_DIM))
        y += 2

        # next pass for the selected sat
        addstr(win, y, x0, "Next pass", cp(CLR_HEADER) | _bold())
        passes = pred.predict_passes(now, st.min_el, 1)
        if passes:
            p = passes[0]
            addstr(win, y, x0 + 12, "%s  in %s   max el %.0f\u00b0   dur %s" % (
                fmt.fmt_clock(p.aos, with_date=True),
                fmt.fmt_dur(p.aos - now), p.max_el,
                fmt.fmt_dur(p.los - p.aos)))
            y += 1
            addstr(win, y, x0 + 12, "AOS az %s  \u2192  LOS az %s" % (
                fmt.fmt_az(p.az_aos), fmt.fmt_az(p.az_los)), cp(CLR_DIM))
        else:
            addstr(win, y, x0 + 12, "no pass above %.0f\u00b0 in 10 days"
                   % st.min_el, cp(CLR_DIM))
        y += 2

        # who's up right now across the catalog
        addstr(win, y, x0, "Up now", cp(CLR_HEADER) | _bold())
        y += 1
        ups = self._whos_up(now)
        if not ups:
            addstr(win, y, x0 + 2, "nothing above the horizon right now",
                   cp(CLR_DIM))
        else:
            addstr(win, y, x0 + 2, "%-16s %9s %8s  %s" % (
                "SAT", "AZ", "EL", ""), cp(CLR_DIM))
            y += 1
            for name, az, el in ups[:max(0, (y0 + h) - y - 1)]:
                addstr(win, y, x0 + 2, "%-16s %9s %7s  %s" % (
                    clip(name, 16), fmt.fmt_az(az), fmt.fmt_el(el),
                    fmt.el_bar(el, 12)), cp(CLR_OK))
                y += 1

    def _whos_up(self, now):
        st = self.state
        out = []
        pred = st.store.pred
        pred.set_site(st.obs)
        # scan a bounded slice for responsiveness on big catalogs
        for s in st.sats[:300]:
            if not pred.set_sat(s):
                continue
            az, el = pred.azel_at(now)
            if el > 0.0:
                out.append((s.name, az, el))
        out.sort(key=lambda r: -r[2])
        return out

    def help_keys(self):
        return [("R", "refresh catalog"), ("2", "satellites")]

    def handle_key(self, ch):
        if ch in (ord("r"), ord("R")):
            self.app.do_refresh_catalog()
            return True
        return False


class TrackScreen(Screen):
    title = "Track"
    refresh_secs = 1.0

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        now = time.time()
        if sat is None:
            addstr(win, y0, x0, "No satellite selected (press 2).",
                   cp(CLR_WARN))
            return
        pred = st.pred_for(sat)
        L = pred.look(now)

        addstr(win, y0, x0, sat.name, cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + len(sat.name) + 2,
               "#%d" % sat.norad, cp(CLR_DIM))
        if pred.deepspace_approximate():
            addstr(win, y0, x0 + len(sat.name) + 10,
                   "[deep-space: approximate]", cp(CLR_WARN))

        col2 = x0 + max(34, w // 2)
        y = y0 + 2
        # left column: look angles
        def row(label, value, attr=0, c=x0):
            nonlocal y
            addstr(win, y, c, ljust(label, 11), cp(CLR_HEADER))
            addstr(win, y, c + 11, value, attr)
            y += 1

        if L.visible:
            row("Status", "UP \u2014 above horizon", cp(CLR_OK) | _bold())
        else:
            row("Status", "below horizon", cp(CLR_DIM))
        row("Azimuth", fmt.fmt_az(L.az))
        row("Elevation", "%s  %s" % (fmt.fmt_el(L.el), fmt.el_bar(L.el, 14)),
            cp(CLR_OK) if L.visible else cp(CLR_DIM))
        row("Range", "%.0f km" % L.range_km)
        row("Range rate", fmt.fmt_rate(L.range_rate),
            cp(CLR_BAD) if L.range_rate > 0 else cp(CLR_OK))
        row("Sub-point", fmt.fmt_latlon(L.sub_lat, L.sub_lon))
        row("Altitude", "%.0f km" % L.alt_km)
        row("Sunlit", "yes" if L.sunlit else "no (eclipse)",
            cp(CLR_OK) if L.sunlit else cp(CLR_DIM))

        # right column: pass context + sky
        y = y0 + 2
        addstr(win, y, col2, "Sun", cp(CLR_HEADER) | _bold())
        addstr(win, y, col2 + 11, "az %s  el %s" % (
            fmt.fmt_az(L.sun_az), fmt.fmt_el(L.sun_el)))
        y += 1
        # is this a visible (sunlit sat, dark observer) opportunity?
        vis_chance = L.visible and L.sunlit and L.sun_el < -6.0
        addstr(win, y, col2, "Visible?", cp(CLR_HEADER) | _bold())
        if vis_chance:
            addstr(win, y, col2 + 11, "YES \u2014 naked-eye possible",
                   cp(CLR_OK) | _bold())
        else:
            why = "sat in shadow" if not L.sunlit else (
                "sat below horizon" if not L.visible else "sky too bright")
            addstr(win, y, col2 + 11, why, cp(CLR_DIM))
        y += 2

        # current pass progress, or next pass
        addstr(win, y, col2, "Pass", cp(CLR_HEADER) | _bold())
        y += 1
        if L.visible:
            # find LOS by scanning forward
            los = self._find_los(pred, now)
            addstr(win, y, col2 + 2, "LOS in %s  at az %s" % (
                fmt.fmt_dur(los - now), fmt.fmt_az(pred.azel_at(los)[0])),
                cp(CLR_OK))
        else:
            ps = pred.predict_passes(now, st.min_el, 1)
            if ps:
                p = ps[0]
                addstr(win, y, col2 + 2, "AOS in %s (%s)" % (
                    fmt.fmt_dur(p.aos - now), fmt.fmt_clock(p.aos)))
                addstr(win, y + 1, col2 + 2, "max el %.0f\u00b0  dur %s" % (
                    p.max_el, fmt.fmt_dur(p.los - p.aos)), cp(CLR_DIM))
            else:
                addstr(win, y, col2 + 2, "no pass above %.0f\u00b0 soon"
                       % st.min_el, cp(CLR_DIM))

        # footer clock
        addstr(win, y0 + h - 1, x0, "Local %s   UTC %s" % (
            fmt.fmt_clock(now, with_date=True),
            time.strftime("%H:%M:%S", time.gmtime(now))), cp(CLR_DIM))

    def _find_los(self, pred, now):
        t = now
        for _ in range(4000):
            if pred.azel_at(t)[1] < 0:
                break
            t += 10
        return t

    def help_keys(self):
        return [("[ ]", "prev/next sat"), ("p", "pass detail")]

    def handle_key(self, ch):
        if ch in (ord("["), ord("]")):
            self.app.cycle_sat(-1 if ch == ord("[") else 1)
            return True
        if ch in (ord("p"), ord("P")):
            self.app.goto("passdetail")
            return True
        return False


def _bold():
    import curses
    return curses.A_BOLD
