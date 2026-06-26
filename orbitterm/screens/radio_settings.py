"""orbitterm/screens/radio_settings.py - Radio/Doppler tuning and Settings."""

import time

from ..ui import Screen, addstr, hline, cp, ljust
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_OK, CLR_WARN, CLR_BAD, CLR_DIM,
                  CLR_ACCENT, CLR_ROW_SEL)
from .. import fmt
from orbitdeck.engine.dxdoppler import doppler_dials


class RadioScreen(Screen):
    title = "Radio"
    refresh_secs = 1.0

    def __init__(self, app):
        super().__init__(app)
        self.tp_idx = 0

    def on_enter(self):
        self.tp_idx = 0

    def _transponders(self, sat):
        try:
            self.state.store.ensure_transponders(sat)
        except Exception:
            pass
        return getattr(sat, "transponders", []) or []

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        now = time.time()
        if sat is None:
            addstr(win, y0, x0, "No satellite selected (press 2).", cp(CLR_WARN))
            return
        addstr(win, y0, x0, sat.name, cp(CLR_TITLE) | _bold())
        tps = self._transponders(sat)
        if not tps:
            addstr(win, y0 + 2, x0, "No transponder/frequency data for this "
                   "satellite.", cp(CLR_DIM))
            addstr(win, y0 + 3, x0, "Fetch a fuller catalog (R on Home) or add "
                   "frequencies in OrbitDeck.", cp(CLR_DIM))
            return
        self.tp_idx %= len(tps)
        tp = tps[self.tp_idx]
        addstr(win, y0, x0 + len(sat.name) + 2, "%s  [%d/%d]  (t to cycle)" % (
            tp.kind(), self.tp_idx + 1, len(tps)), cp(CLR_DIM))

        pred = st.pred_for(sat)
        L = pred.look(now)
        rr = L.range_rate

        dl = tp.downlink_center()
        ul = tp.uplink_center()

        y = y0 + 2
        addstr(win, y, x0, ljust("Transponder", 14), cp(CLR_HEADER))
        addstr(win, y, x0 + 14, tp.desc or tp.kind())
        y += 1
        addstr(win, y, x0, ljust("Mode", 14), cp(CLR_HEADER))
        addstr(win, y, x0 + 14, tp.mode or "--")
        if tp.is_linear:
            addstr(win, y, x0 + 30, "inverting" if tp.invert else "non-inverting",
                   cp(CLR_DIM))
        y += 2

        # nominal vs Doppler-corrected dials
        rx, tx = doppler_dials(dl, ul, rr)
        addstr(win, y, x0, "%-10s %-18s %-18s %s" % (
            "", "NOMINAL", "TUNE NOW", "SHIFT"), cp(CLR_DIM) | _bold())
        y += 1
        addstr(win, y, x0, "%-10s %-18s %-18s %s" % (
            "Downlink", fmt.fmt_freq(dl), fmt.fmt_freq(rx),
            fmt.fmt_doppler(rx - dl) if dl else "--"),
            cp(CLR_OK) | _bold())
        y += 1
        if ul:
            addstr(win, y, x0, "%-10s %-18s %-18s %s" % (
                "Uplink", fmt.fmt_freq(ul), fmt.fmt_freq(tx),
                fmt.fmt_doppler(tx - ul)), cp(CLR_ACCENT) | _bold())
            y += 1
        else:
            addstr(win, y, x0, "Uplink     (receive-only)", cp(CLR_DIM))
            y += 1
        y += 1

        # live geometry context
        addstr(win, y, x0, "Range rate", cp(CLR_HEADER))
        addstr(win, y, x0 + 14, fmt.fmt_rate(rr),
               cp(CLR_BAD) if rr > 0 else cp(CLR_OK))
        addstr(win, y, x0 + 32, "(receding)" if rr > 0 else "(approaching)",
               cp(CLR_DIM))
        y += 1
        addstr(win, y, x0, "Look", cp(CLR_HEADER))
        if L.visible:
            addstr(win, y, x0 + 14, "az %s  el %s" % (
                fmt.fmt_az(L.az), fmt.fmt_el(L.el)), cp(CLR_OK))
        else:
            addstr(win, y, x0 + 14, "below horizon \u2014 dials shown for "
                   "current geometry", cp(CLR_DIM))
        y += 2

        # mini Doppler curve across the next pass (downlink shift)
        self._draw_curve(win, x0, y, w - x0, (y0 + h) - y - 1, pred, dl, now)

    def _draw_curve(self, win, x0, y0, w, h, pred, dl, now):
        if h < 5 or w < 30 or not dl:
            return
        st = self.state
        ps = pred.predict_passes(now, st.min_el, 1)
        if not ps:
            return
        p = ps[0]
        addstr(win, y0, x0, "Downlink Doppler across next pass (%s)" %
               fmt.fmt_clock(p.aos), cp(CLR_HEADER) | _bold())
        gy0 = y0 + 1
        gh = h - 2
        gw = min(w - 10, 60)
        n = gw
        shifts = []
        for i in range(n):
            t = p.aos + (p.los - p.aos) * i / max(1, n - 1)
            rr = pred.look(t).range_rate
            beta = (rr * 1000.0) / 299792458.0
            shifts.append(dl * (-beta))   # rx - dl
        smax = max(abs(s) for s in shifts) if shifts else 1.0
        smax = max(smax, 1.0)
        mid = gy0 + gh // 2
        hline(win, mid, x0 + 8, gw, "\u2500", cp(CLR_DIM))
        addstr(win, mid, x0, "0 Hz", cp(CLR_DIM))
        addstr(win, gy0, x0, "+%dHz" % int(smax), cp(CLR_DIM))
        addstr(win, gy0 + gh - 1, x0, "-%dHz" % int(smax), cp(CLR_DIM))
        for i, s in enumerate(shifts):
            frac = s / smax
            row = mid - int(round(frac * (gh // 2 - 1)))
            row = max(gy0, min(gy0 + gh - 1, row))
            attr = cp(CLR_BAD) if s < 0 else cp(CLR_OK)
            addstr(win, row, x0 + 8 + i, "\u2588", attr)

    def help_keys(self):
        return [("t", "cycle transponder"), ("[ ]", "prev/next sat")]

    def handle_key(self, ch):
        if ch in (ord("t"), ord("T")):
            self.tp_idx += 1
            return True
        if ch in (ord("["), ord("]")):
            self.app.cycle_sat(-1 if ch == ord("[") else 1)
            self.tp_idx = 0
            return True
        return False


class SettingsScreen(Screen):
    title = "Settings"
    refresh_secs = 0.0

    FIELDS = ["lat", "lon", "alt", "name", "min_el"]

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0
        self.editing = False
        self.buf = ""

    def on_enter(self):
        self.editing = False

    def _value(self, f):
        st = self.state
        return {
            "lat": "%.4f" % st.obs.lat,
            "lon": "%.4f" % st.obs.lon,
            "alt": "%.0f" % st.obs.alt_m,
            "name": st.store.obs_name,
            "min_el": "%.0f" % st.min_el,
        }[f]

    def _label(self, f):
        return {"lat": "Latitude (\u00b0N)", "lon": "Longitude (\u00b0E)",
                "alt": "Altitude (m)", "name": "Station name",
                "min_el": "Min elevation (\u00b0)"}[f]

    def draw(self, win, y0, x0, h, w):
        st = self.state
        addstr(win, y0, x0, "Settings", cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + 11, "shared with OrbitDeck (~/.orbitdeck/config.json)",
               cp(CLR_DIM))
        addstr(win, y0 + 1, x0, "Maidenhead grid: ", cp(CLR_HEADER))
        addstr(win, y0 + 1, x0 + 17, st.grid(), cp(CLR_ACCENT) | _bold())

        y = y0 + 3
        for i, f in enumerate(self.FIELDS):
            sel = (i == self.sel)
            addstr(win, y, x0, ljust(self._label(f), 20),
                   cp(CLR_HEADER) if not sel else cp(CLR_ROW_SEL) | _bold())
            if sel and self.editing:
                addstr(win, y, x0 + 21, ljust(self.buf + "_", 20),
                       cp(CLR_ROW_SEL))
            else:
                addstr(win, y, x0 + 21, self._value(f),
                       cp(CLR_ACCENT) if sel else 0)
            y += 1

        y += 1
        addstr(win, y, x0, "Catalog", cp(CLR_HEADER) | _bold())
        if st.using_sample():
            addstr(win, y, x0 + 12, "sample/offline data", cp(CLR_WARN))
        else:
            age = st.catalog_age_days()
            addstr(win, y, x0 + 12, "%d sats, %.1f days old" % (
                st.store.db.count(), age or 0))
        addstr(win, y + 1, x0 + 12, "press R to fetch fresh AMSAT elements",
               cp(CLR_DIM))

        addstr(win, y0 + h - 1, x0,
               "\u2191\u2193 field   \u21b5 edit   R refresh catalog",
               cp(CLR_DIM))

    def help_keys(self):
        if self.editing:
            return [("type", "value"), ("\u21b5", "save"), ("esc", "cancel")]
        return [("\u2191\u2193", "field"), ("\u21b5", "edit"),
                ("R", "refresh catalog")]

    def handle_key(self, ch):
        import curses
        if self.editing:
            if ch == 27:
                self.editing = False
                return True
            if ch in (curses.KEY_ENTER, 10, 13):
                self._commit()
                self.editing = False
                return True
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                self.buf = self.buf[:-1]
                return True
            if 32 <= ch < 127:
                self.buf += chr(ch)
                return True
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.sel = (self.sel + 1) % len(self.FIELDS)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.sel = (self.sel - 1) % len(self.FIELDS)
            return True
        if ch in (curses.KEY_ENTER, 10, 13):
            self.editing = True
            self.buf = self._value(self.FIELDS[self.sel])
            return True
        if ch in (ord("r"), ord("R")):
            self.app.do_refresh_catalog()
            return True
        return False

    def _commit(self):
        st = self.state
        f = self.FIELDS[self.sel]
        v = self.buf.strip()
        try:
            if f == "lat":
                st.set_site(float(v), st.obs.lon, st.obs.alt_m)
            elif f == "lon":
                st.set_site(st.obs.lat, float(v), st.obs.alt_m)
            elif f == "alt":
                st.set_site(st.obs.lat, st.obs.lon, float(v))
            elif f == "name":
                st.set_site(st.obs.lat, st.obs.lon, st.obs.alt_m, name=v)
            elif f == "min_el":
                st.set_min_el(float(v))
            st.flash("Saved %s" % self._label(f))
        except ValueError:
            st.flash("Invalid value")


def _bold():
    import curses
    return curses.A_BOLD
