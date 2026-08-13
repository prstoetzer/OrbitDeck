"""orbitterm/screens/analysis3.py - a third batch of TUI screens.

Six more text-native screens reusing the desktop engines:

  * Mutual Windows - co-visibility with a remote grid
  * Sun/Moon Transits - the satellite crossing the solar or lunar disk
  * Conjunctions - close approaches against another catalog object
  * AO-7 Mode - illumination verdict and the fitted mode phase
  * Space Wx - solar and geomagnetic indices from the cache
  * Sites - the saved station list, with a key to make one active
"""

import curses
import time

from ..ui import Screen, ScrollList, addstr, cp, clip, hline
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_DIM, CLR_OK, CLR_WARN,
                  CLR_ACCENT, CLR_ROW_SEL)
from ..fmt import fmt_dur, fmt_clock

from orbitdeck.engine.predict import Predictor, Observer, grid_to_latlon
from orbitdeck.engine.transits import find_transits
from orbitdeck.engine.conjunction import screen_conjunctions, orbital_neighborhood
from orbitdeck.engine import skyglance as SG
from orbitdeck.engine import ao7 as A7


def _kv(win, y, x, w, label, value, attr=0):
    addstr(win, y, x, clip("%-20s" % label, 20), cp(CLR_DIM))
    addstr(win, y, x + 21, clip(str(value), max(1, w - 21)), attr)


class MutualScreen(Screen):
    sat_scoped = ("windows",)
    title = "Mutual Windows"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.grid = "FN31"
        self.windows = []
        self.editing = False
        self.buf = ""
        self.list = ScrollList()
        self.status = "press g to scan"

    def _scan(self):
        sat = self.state.sat
        if sat is None:
            self.status = "no satellite selected"
            return
        try:
            lat, lon = grid_to_latlon(self.grid)
        except Exception:
            self.status = "bad grid"
            return
        pred = Predictor()
        pred.set_site(self.state.store.obs)
        if not pred.set_sat(sat):
            self.status = "cannot propagate"
            return
        dx = Observer(lat=lat, lon=lon, alt_m=0.0, valid=True)
        self.windows = pred.mutual_windows(time.time(), dx, 5.0, 20)
        self.status = "%d window(s) with %s" % (len(self.windows), self.grid)

    def draw(self, win, y0, x0, h, w):
        sat = self.state.sat
        addstr(win, y0, x0, clip("%s \u2194 %s" % (
            sat.name if sat else "-",
            ("%s_" % self.buf) if self.editing else self.grid), w),
            cp(CLR_ACCENT) if self.editing else cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, self.status, cp(CLR_DIM))
        addstr(win, y0 + 3, x0, clip("%-20s %-10s %8s %8s" % (
            "START", "DURATION", "MY EL", "DX EL"), w), cp(CLR_HEADER))
        page = max(1, h - 5)
        self.list.clamp(len(self.windows), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(self.windows):
                break
            mw = self.windows[idx]
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else 0
            start = getattr(mw, "start", 0)
            end = getattr(mw, "end", start)
            addstr(win, y0 + 4 + i, x0, clip("%-20s %-10s %7.0f %7.0f" % (
                fmt_clock(start, True), fmt_dur(end - start),
                getattr(mw, "my_max_el", 0.0),
                getattr(mw, "dx_max_el", 0.0)), w), attr)

    def handle_key(self, ch):
        # 'e' edits a value here as it does on EME, Orbital History and Tools.
        # The DX grid was fixed at FN31 with no way to change it.
        if self.editing:
            if ch in (ord("\n"), curses.KEY_ENTER):
                cand = self.buf.strip().upper()
                from orbitdeck.engine.activations import valid_grid
                if valid_grid(cand):
                    self.grid = cand
                    self.windows = []
                    self.status = "grid %s \u2014 press g to scan" % cand
                else:
                    self.status = "%s is not a Maidenhead locator" % cand
                self.editing = False
            elif ch == 27:
                self.editing = False
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                self.buf = self.buf[:-1]
            elif 32 <= ch < 127:
                self.buf += chr(ch)
            return True
        if ch in (ord("e"), ord("E")):
            self.editing = True
            self.buf = ""
            return True
        if ch == ord("g"):
            self._scan()
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, len(self.windows), 8)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, len(self.windows), 8)
            return True
        return False

    def help_keys(self):
        if self.editing:
            return [("ENTER", "apply grid"), ("ESC", "cancel")]
        return [("e", "DX grid"), ("g", "scan"), ("up/dn", "scroll")]



class TransitsScreen(Screen):
    sat_scoped = ("events",)
    title = "Sun/Moon Transits"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.body = "both"
        self.sep = 1.0
        self.events = []
        self.list = ScrollList()

    def on_enter(self):
        self._scan()

    def _scan(self):
        sat = self.state.sat
        if sat is None:
            self.events = []
            return
        pred = Predictor()
        self.events = find_transits(pred, self.state.store.obs, sat,
                                    time.time(), hours=7 * 24,
                                    body=self.body, max_sep_deg=self.sep)

    def draw(self, win, y0, x0, h, w):
        sat = self.state.sat
        if sat is None:
            addstr(win, y0, x0, "No satellite selected.", cp(CLR_WARN))
            return
        addstr(win, y0, x0, clip("%s \u2014 within %.1f deg of %s (7 d)"
                                 % (sat.name, self.sep, self.body), w),
               cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, "b body   s separation   r rescan",
               cp(CLR_DIM))
        addstr(win, y0 + 3, x0, clip("%-20s %-6s %7s %8s %6s" % (
            "WHEN", "BODY", "SEP", "TYPE", "EL"), w), cp(CLR_HEADER))
        page = max(1, h - 5)
        self.list.clamp(len(self.events), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(self.events):
                break
            e = self.events[idx]
            attr = cp(CLR_OK) if e["transit"] else 0
            if idx == self.list.sel:
                attr = cp(CLR_ROW_SEL)
            addstr(win, y0 + 4 + i, x0, clip("%-20s %-6s %6.2f %8s %5.0f" % (
                fmt_clock(e["time"], True), e["body"][:5], e["sep_deg"],
                "TRANSIT" if e["transit"] else "near", e["sat_el"]), w), attr)

    def handle_key(self, ch):
        if ch == ord("b"):
            self.body = {"both": "sun", "sun": "moon",
                         "moon": "both"}[self.body]
            self._scan()
            return True
        if ch == ord("s"):
            self.sep = {0.5: 1.0, 1.0: 2.0, 2.0: 5.0, 5.0: 0.5}.get(self.sep,
                                                                    1.0)
            self._scan()
            return True
        if ch == ord("r"):
            self._scan()
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, len(self.events), 8)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, len(self.events), 8)
            return True
        return False

    def help_keys(self):
        return [("b", "body"), ("s", "sep"), ("r", "rescan")]


class ConjunctionScreen(Screen):
    sat_scoped = ("rows",)
    title = "Conjunctions"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.mode = 0            # 0 = neighborhood, 1 = pair scan
        self.rows = []
        self.other = 0
        self.list = ScrollList()
        self.status = "n neighborhood   p pair scan"

    def _neighborhood(self):
        sat = self.state.sat
        if sat is None:
            return
        pred = Predictor()
        self.rows = orbital_neighborhood(pred, sat, self.state.store.db.sats,
                                         time.time(), max_results=15)
        self.mode = 0
        self.status = "%d nearest objects now" % len(self.rows)

    def _pair(self):
        sat = self.state.sat
        sats = [s for s in self.state.store.db.sats
                if getattr(s, "norad", 0) != getattr(sat, "norad", -1)]
        if sat is None or not sats:
            return
        other = sats[self.other % len(sats)]
        res = screen_conjunctions(Predictor(), Predictor(), sat, other,
                                  time.time(), hours=6)
        self.rows = [{"name": other.name, "norad": other.norad,
                      "range_km": r["miss_km"],
                      "rel_vel_kms": r["rel_vel_kms"],
                      "time": r["time"]} for r in res]
        self.mode = 1
        if self.rows:
            _closest = min(r["range_km"] for r in self.rows)
            self.closest = "%.0f km" % _closest
        self.status = "%s vs %s: %d approach(es) <800 km/6h" % (
            sat.name, other.name, len(self.rows))

    def draw(self, win, y0, x0, h, w):
        sat = self.state.sat
        if sat is None:
            addstr(win, y0, x0, "No satellite selected.", cp(CLR_WARN))
            return
        addstr(win, y0, x0, clip(sat.name, w), cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        head = ("%-18s %8s %10s %10s" %
                ("OBJECT", "NORAD", "MISS km" if self.mode else "RANGE km",
                 "REL km/s"))
        addstr(win, y0 + 3, x0, clip(head, w), cp(CLR_HEADER))
        page = max(1, h - 5)
        self.list.clamp(len(self.rows), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(self.rows):
                break
            r = self.rows[idx]
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else (
                cp(CLR_WARN) if r["range_km"] < 100 else 0)
            addstr(win, y0 + 4 + i, x0, clip("%-18s %8d %10.1f %10.2f" % (
                r["name"][:18], r["norad"], r["range_km"],
                r["rel_vel_kms"]), w), attr)
        addstr(win, y0 + h - 1, x0,
               "awareness only \u2014 GP elements are km-class", cp(CLR_DIM))

    def handle_key(self, ch):
        if ch == ord("n"):
            self._neighborhood()
            return True
        if ch == ord("p"):
            self._pair()
            return True
        if ch == ord("]"):
            self.other += 1
            self._pair()
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, len(self.rows), 8)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, len(self.rows), 8)
            return True
        return False

    def help_keys(self):
        return [("n", "neighborhood"), ("p", "pair"), ("]", "next object")]


class Ao7Screen(Screen):
    sat_scoped = ("res",)
    title = "AO-7 Mode"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.res = None
        self.status = "i illumination   f fetch reports & fit"

    def _sat(self):
        s = self.state.store.db.get(A7.AO7_NORAD)
        if s:
            return s
        for c in self.state.store.db.sats:
            if "AO-7" in getattr(c, "name", "").upper():
                return c
        return None

    def _illum(self):
        sat = self._sat()
        if sat is None:
            self.status = "AO-7 not in catalog (NORAD 7530)"
            return
        pred = Predictor()
        pred.set_site(self.state.store.obs)
        self.res = SG.ao7_illumination(pred, sat, time.time())
        self.status = "illumination only \u2014 f fits the mode phase"

    def _fit(self):
        sat = self._sat()
        if sat is None:
            self.status = "AO-7 not in catalog (NORAD 7530)"
            return
        from orbitdeck.netio import http_get as _http_get
        pred = Predictor()
        pred.set_site(self.state.store.obs)
        self.status = "fetching AMSAT reports..."
        try:
            self.res = A7.fetch_and_fit(lambda u: _http_get(u, 30),
                                        pred=pred, sat=sat, now=time.time())
            self.status = self.res.get("note", "")
        except Exception as exc:
            self.status = "fetch failed: %s" % str(exc)[:40]

    def draw(self, win, y0, x0, h, w):
        addstr(win, y0, x0, "AO-7 (OSCAR 7) mode timer", cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        r = self.res
        if not r:
            addstr(win, y0 + 3, x0, "press i for the illumination verdict",
                   cp(CLR_DIM))
            return
        y = y0 + 3
        cont = r.get("continuous_sun")
        _kv(win, y, x0, w, "Illumination",
            "continuous sunlight" if cont else "eclipsing each orbit",
            cp(CLR_OK) if cont else cp(CLR_WARN))
        y += 1
        if "eclipse_frac" in r:
            _kv(win, y, x0, w, "Eclipse fraction",
                "%.0f %%" % (r["eclipse_frac"] * 100))
            y += 1
        if "beta_deg" in r:
            _kv(win, y, x0, w, "Beta angle", "%+.1f deg" % r["beta_deg"])
            y += 1
        if "period_s" in r:
            y += 1
            _kv(win, y, x0, w, "Mode now", r["mode_now_name"], cp(CLR_ACCENT))
            y += 1
            _kv(win, y, x0, w, "Next switch",
                fmt_clock(r["next_switch"], True))
            y += 1
            _kv(win, y, x0, w, "Time to switch", fmt_dur(r["to_switch_s"]))
            y += 1
            _kv(win, y, x0, w, "Fitted period",
                "%.2f h" % (r["period_s"] / 3600.0))
            y += 1
            _kv(win, y, x0, w, "Phase uncertainty",
                "+/-%.0f min" % (r["phase_rms_s"] / 60.0))
            y += 1
            _kv(win, y, x0, w, "Agreement", "%.0f %%" % r["agree_pct"],
                cp(CLR_OK) if r["agree_pct"] >= 75 else cp(CLR_WARN))
            y += 1
            _kv(win, y, x0, w, "Reports used", "%d (%d heard, %d not)"
                % (r["n_obs"], r["n_pos"], r["n_neg"]))
            y += 1
            # Fit diagnostics the desktop shows: without them the phase looks
            # authoritative even when it rests on three reports.
            _kv(win, y, x0, w, "Report agreement", "%.0f %%" % r["agree_pct"],
                cp(CLR_OK) if r["agree_pct"] >= 75 else cp(CLR_WARN))
            y += 1
            _kv(win, y, x0, w, "Mode changes seen", "%d" % r["n_switch"])
            y += 1
            if r.get("since"):
                _kv(win, y, x0, w, "Timer running since",
                    fmt_clock(r["since"], True))
                y += 1
            _kv(win, y, x0, w, "Confidence", r["note"],
                cp(CLR_WARN) if r.get("near_boundary") or
                r["agree_pct"] < 75 else 0)
            y += 1
        if r.get("note"):
            y += 1
            addstr(win, y, x0, clip(r["note"], w), cp(CLR_DIM))

    def handle_key(self, ch):
        if ch == ord("i"):
            self._illum()
            return True
        if ch == ord("f"):
            self._fit()
            return True
        return False

    def help_keys(self):
        return [("i", "illumination"), ("f", "fetch & fit")]


class SpaceWxScreen(Screen):
    title = "Space Wx"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.data = None
        self.status = "u updates from NOAA"

    def on_enter(self):
        if self.data is None:
            self.data = self.state.store.load_spacewx_cache()

    def _update(self):
        self.status = "fetching..."
        try:
            self.data = self.state.store.update_spacewx()
            self.status = "updated"
        except Exception as exc:
            self.status = "fetch failed: %s" % str(exc)[:40]

    def draw(self, win, y0, x0, h, w):
        addstr(win, y0, x0, "Solar & geomagnetic indices", cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        d = self.data
        if not d:
            addstr(win, y0 + 3, x0, "No cached data \u2014 press u.",
                   cp(CLR_WARN))
            return
        from orbitdeck.engine import spacewx_interp as SI
        colors = {0: cp(CLR_DIM), 1: 0, 2: cp(CLR_OK), 3: cp(CLR_WARN),
                   4: cp(CLR_WARN)}
        y = y0 + 3
        for label, value, sev in SI.rows(d):
            if y >= y0 + h - 4:
                break
            _kv(win, y, x0, w, label, value, colors.get(sev, 0))
            y += 1
        y += 1
        if y < y0 + h - 1:
            hline(win, y, x0, min(w, 60), attr=cp(CLR_DIM))
            y += 1
        addstr(win, y, x0, "OPERATING OUTLOOK", cp(CLR_HEADER))
        y += 1
        note = SI.outlook(d.get("flux"), d.get("kp"))
        # wrap the note to the pane
        words, line = note.split(), ""
        for word in words:
            if len(line) + len(word) + 1 > w - 1:
                addstr(win, y, x0, line, 0)
                y += 1
                line = word
            else:
                line = (line + " " + word).strip()
        if line and y < y0 + h:
            addstr(win, y, x0, line, 0)

    def handle_key(self, ch):
        if ch in (ord("u"), ord("r")):
            self._update()
            return True
        return False

    def help_keys(self):
        return [("u", "update")]


class SitesScreen(Screen):
    title = "Sites"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.list = ScrollList()
        self.status = "ENTER makes a site active"

    def _rows(self):
        st = self.state.store
        rows = [("* " + getattr(st, "obs_name", "Home"), st.obs.lat,
                 st.obs.lon, getattr(st.obs, "alt_m", 0.0))]
        for s in getattr(st, "sites", []) or []:
            rows.append(("  " + s.get("name", "?"), s.get("lat", 0.0),
                         s.get("lon", 0.0), s.get("alt_m", 0.0)))
        return rows

    def draw(self, win, y0, x0, h, w):
        rows = self._rows()
        addstr(win, y0, x0, "Saved stations (* = active)", cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        addstr(win, y0 + 3, x0, clip("%-22s %10s %11s %8s" % (
            "NAME", "LAT", "LON", "ALT m"), w), cp(CLR_HEADER))
        page = max(1, h - 5)
        self.list.clamp(len(rows), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(rows):
                break
            name, lat, lon, alt = rows[idx]
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else 0
            addstr(win, y0 + 4 + i, x0, clip("%-22s %10.4f %11.4f %8.0f" % (
                name[:22], lat, lon, alt), w), attr)

    def handle_key(self, ch):
        rows = self._rows()
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, len(rows), 8)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, len(rows), 8)
            return True
        if ch in (ord("\n"), curses.KEY_ENTER):
            idx = self.list.sel
            if idx == 0:
                self.status = "already the active site"
                return True
            sites = getattr(self.state.store, "sites", []) or []
            if idx - 1 < len(sites):
                s = sites[idx - 1]
                try:
                    self.state.store.set_site(s["lat"], s["lon"],
                                              s.get("alt_m", 0.0))
                    self.state.store.save_config()
                    self.status = "active site: %s" % s.get("name", "?")
                except Exception as exc:
                    self.status = "could not switch: %s" % str(exc)[:40]
            return True
        return False

    def help_keys(self):
        return [("up/dn", "select"), ("ENTER", "make active")]
