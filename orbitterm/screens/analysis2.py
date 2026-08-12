"""orbitterm/screens/analysis2.py - further analysis screens for the TUI.

Five text-native screens that reuse engines the desktop app already drives:

  * Orbital Zones - SAA / belts / polar / eclipse transits for the active sat
  * MUF - HF maximum usable frequency to world regions
  * Sun / Moon - solar and lunar position and illumination for the QTH
  * EME - moonbounce path loss, Doppler and common-Moon windows
  * Workable - grids / US states / DXCC entities under the footprint now

All of these are tables or key/value readouts, which is what a terminal does
best
the graphical desktop screens (globe, sky map, plots) are a separate job.
"""

import curses
import time

from ..ui import Screen, ScrollList, addstr, cp, clip, hline
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_DIM, CLR_OK, CLR_WARN,
                  CLR_ACCENT, CLR_ROW_SEL)
from ..fmt import fmt_dur, fmt_clock

from orbitdeck.engine import zones as Z
from orbitdeck.engine import muf as MUF
from orbitdeck.engine import celestial as CE
from orbitdeck.engine import analysis as AN
from orbitdeck.engine.predict import Predictor, grid_to_latlon
from orbitdeck.data.us_states import workable_states
from orbitdeck.data.dxcc import workable_dxcc


def _kv(win, y, x, w, label, value, attr=0):
    addstr(win, y, x, clip("%-20s" % label, 20), cp(CLR_DIM))
    addstr(win, y, x + 21, clip(str(value), max(1, w - 21)), attr)


class ZonesScreen(Screen):
    sat_scoped = ("res",)
    title = "Orbital Zones"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.zone = 0
        self.res = None
        self.list = ScrollList()

    def on_enter(self):
        self._scan()

    def _scan(self):
        sat = self.state.sat
        if sat is None:
            self.res = None
            return
        pred = Predictor()
        pred.set_site(self.state.store.obs)
        self.res = Z.scan_zone(pred, sat, self.zone, time.time(), hours=24)

    def draw(self, win, y0, x0, h, w):
        sat = self.state.sat
        if sat is None:
            addstr(win, y0, x0, "No satellite selected.", cp(CLR_WARN))
            return
        addstr(win, y0, x0, clip(sat.name, w), cp(CLR_TITLE))
        addstr(win, y0, x0 + len(sat.name) + 2, Z.ZONES[self.zone],
               cp(CLR_ACCENT))
        r = self.res
        if not r:
            addstr(win, y0 + 2, x0, "Press r to scan.", cp(CLR_DIM))
            return
        y = y0 + 2
        _kv(win, y, x0, w, "Now",
            "IN ZONE" if r["in_now"] else "outside",
            cp(CLR_OK) if r["in_now"] else 0)
        y += 1
        if self.zone in (Z.ZONE_INNER, Z.ZONE_OUTER):
            _kv(win, y, x0, w, "L shell", "%.2f" % r["shell_l"])
            y += 1
            _kv(win, y, x0, w, "B/B0", "%.1f" % r["b_ratio"])
            y += 1
        _kv(win, y, x0, w, "Dwell", "%.1f min/day" % r["dwell_min_day"])
        y += 1
        _kv(win, y, x0, w, "Scanned", "%.1f h" % r["scanned_h"])
        y += 2
        addstr(win, y, x0, clip("%-20s %-20s %s" % ("ENTER", "EXIT",
                                                    "DURATION"), w),
               cp(CLR_HEADER))
        y += 1
        page = max(1, y0 + h - y)
        wins = r["windows"]
        self.list.clamp(len(wins), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(wins):
                break
            a, b = wins[idx]
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else 0
            addstr(win, y + i, x0, clip("%-20s %-20s %s" % (
                fmt_clock(a, True), fmt_clock(b),
                fmt_dur(b - a)), w), attr)

    def handle_key(self, ch):
        if ch in (ord("z"), ord("\t")):
            self.zone = (self.zone + 1) % len(Z.ZONES)
            self._scan()
            return True
        if ch == ord("r"):
            self._scan()
            return True
        n = len(self.res["windows"]) if self.res else 0
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, n, 8)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, n, 8)
            return True
        return False

    def help_keys(self):
        return [("z", "zone"), ("r", "rescan"), ("up/dn", "scroll")]


class MufScreen(Screen):
    title = "MUF / HF Prop"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        # Seeded from the Space Wx cache on first entry rather than pinned at
        # a made-up 100 - MINIMUF is driven by SSN, so the value the operator
        # already fetched should be the one it uses.
        self.ssn = 100.0
        self.ssn_src = "not seeded yet"
        self.dxq = ""
        self.editing = False
        self.buf = ""
        self.rows = []
        self.list = ScrollList()

    def on_enter(self):
        self._seed()
        self._compute()

    def _seed(self):
        """Take SSN (and its provenance) from the shared space-weather seed."""
        from orbitdeck.engine.spacewx_interp import seed_ssn
        try:
            cache = self.state.store.load_spacewx_cache()
        except Exception:
            cache = None
        self.ssn, self.ssn_src = seed_ssn(cache)

    def _compute(self):
        o = self.state.store.obs
        if self.dxq:
            hits = MUF.muf_to_dxcc(o.lat, o.lon, time.time(), self.ssn,
                                   self.dxq)
            self.rows = [dict(h, name="%s %s" % (h["prefix"], h["name"]))
                         for h in hits]
            return
        self.rows = MUF.muf_to_regions(o.lat, o.lon, time.time(), self.ssn)

    def draw(self, win, y0, x0, h, w):
        addstr(win, y0, x0, clip("SSN %d \u2014 %s  (+/- s r)" % (
            self.ssn, self.ssn_src), w),
               cp(CLR_ACCENT))
        addstr(win, y0 + 1, x0,
               clip("%-15s %9s %9s %6s %9s %6s" % (
                   "REGION", "MUF", "WORKABLE", "BAND", "DISTANCE", "BRG"), w),
               cp(CLR_HEADER))
        page = max(1, h - 3)
        self.list.clamp(len(self.rows), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(self.rows):
                break
            r = self.rows[idx]
            q = r["quality"]
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else (
                cp(CLR_OK) if q in ("good", "high") else
                cp(CLR_WARN) if q == "low" else 0)
            addstr(win, y0 + 2 + i, x0, clip("%-15s %7.1fM %7.1fM %6s %7.0fkm %5.0f" % (
                r["name"], r["muf_mhz"], r["workable_mhz"], r["band"],
                r["distance_km"], r["bearing_deg"]), w), attr)

    def handle_key(self, ch):
        if ch in (ord("+"), ord("=")):
            self.ssn = min(300.0, self.ssn + 10)
            self.ssn_src = "manual"
            self._compute()
            return True
        if ch in (ord("-"), ord("_")):
            self.ssn = max(0.0, self.ssn - 10)
            self.ssn_src = "manual"
            self._compute()
            return True
        if ch == ord("s"):
            self._seed()
            self._compute()
            return True
        if ch == ord("r"):
            self._compute()
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, len(self.rows), 10)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, len(self.rows), 10)
            return True
        return False

    def help_keys(self):
        return [("+/-", "SSN"), ("s", "reseed"), ("r", "recompute"),
                ("up/dn", "scroll")]


class SunMoonScreen(Screen):
    title = "Sun / Moon"
    refresh_secs = 5.0

    def draw(self, win, y0, x0, h, w):
        o = self.state.store.obs
        t = time.time()
        from orbitdeck.engine.transits import _sun_azel
        saz, sel = _sun_azel(o.lat, o.lon, t)
        maz, mel = CE.moon_azel(o.lat, o.lon, t)
        dist = CE.moon_distance_km(t)
        y = y0
        addstr(win, y, x0, "SUN", cp(CLR_HEADER))
        y += 1
        _kv(win, y, x0, w, "Azimuth", "%.1f deg" % saz)
        y += 1
        _kv(win, y, x0, w, "Elevation", "%.1f deg" % sel,
            cp(CLR_OK) if sel > 0 else cp(CLR_DIM))
        y += 1
        _kv(win, y, x0, w, "State",
            "up" if sel > 0 else ("civil twilight" if sel > -6 else "night"))
        y += 2
        addstr(win, y, x0, "MOON", cp(CLR_HEADER))
        y += 1
        _kv(win, y, x0, w, "Azimuth", "%.1f deg" % maz)
        y += 1
        _kv(win, y, x0, w, "Elevation", "%.1f deg" % mel,
            cp(CLR_OK) if mel > 0 else cp(CLR_DIM))
        y += 1
        _kv(win, y, x0, w, "Distance", "%.0f km" % dist)
        y += 1
        _kv(win, y, x0, w, "Echo delay", "%.2f s" % (2 * dist / 299792.458))
        y += 2
        hline(win, y, x0, min(w, 50), attr=cp(CLR_DIM))
        y += 1
        addstr(win, y, x0, "Sky temperature %.0f K at 144 MHz"
               % CE.sky_temperature_k(freq_mhz=144.0), cp(CLR_DIM))


class EmeScreen(Screen):
    title = "EME"
    refresh_secs = 5.0

    BANDS = [("50 MHz", 50.2e6), ("144 MHz", 144.1e6), ("432 MHz", 432.1e6),
             ("1296 MHz", 1296.0e6), ("10368 MHz", 10368.1e6)]

    VIEWS = ["live", "bands", "plan"]

    def __init__(self, app):
        super().__init__(app)
        self.band = 1
        self.grid = "JO65"
        self.windows = []
        self.view = 0
        self.plan = []
        self.plan_scroll = 0
        self.editing = False
        self.buf = ""

    def draw(self, win, y0, x0, h, w):
        if self.VIEWS[self.view] == "bands":
            return self._draw_bands(win, y0, x0, h, w)
        if self.VIEWS[self.view] == "plan":
            return self._draw_plan(win, y0, x0, h, w)
        o = self.state.store.obs
        t = time.time()
        name, f = self.BANDS[self.band]
        maz, mel = CE.moon_azel(o.lat, o.lon, t)
        y = y0
        _kv(win, y, x0, w, "Band", "%s  (b cycles)" % name, cp(CLR_ACCENT))
        y += 1
        _kv(win, y, x0, w, "Moon az / el", "%.1f / %.1f deg" % (maz, mel),
            cp(CLR_OK) if mel > 0 else cp(CLR_WARN))
        y += 1
        # Illuminated fraction: how much sky glare to expect, and the same
        # figure the desktop Sun/Moon screen reports.
        _kv(win, y, x0, w, "Illuminated",
            "%.0f%%" % (CE.moon_illumination(t) * 100.0))
        y += 1
        _kv(win, y, x0, w, "Path loss (2-way)",
            "%.1f dB" % CE.eme_path_loss_db(f, t))
        y += 1
        _kv(win, y, x0, w, "Self Doppler",
            "%+.0f Hz" % CE.eme_doppler_hz(f, o.lat, o.lon, t))
        y += 1
        _kv(win, y, x0, w, "Remote grid",
            ("%s_  (ENTER apply, ESC cancel)" % self.buf) if self.editing
            else "%s  (e edit, g scan)" % self.grid,
            cp(CLR_ACCENT) if self.editing else 0)
        y += 1
        # Fields the desktop screen shows and the terminal did not.
        _kv(win, y, x0, w, "Moon distance", "%.0f km" % CE.moon_distance_km(t))
        y += 1
        _kv(win, y, x0, w, "Declination", "%+.1f deg" % CE.moon_dec_deg(t))
        y += 1
        _kv(win, y, x0, w, "Path degradation",
            "%.2f dB vs perigee" % CE.eme_path_degradation_db(t))
        y += 1
        _kv(win, y, x0, w, "Libration spread",
            "%.1f Hz" % CE.eme_libration_spread_hz(f / 1e6))
        y += 1
        _kv(win, y, x0, w, "Sky temperature",
            "%.0f K" % CE.eme_sky_temp_k(t, f / 1e6))
        y += 1
        _kv(win, y, x0, w, "Echo delay",
            "%.2f s" % (2.0 * CE.moon_distance_km(t) / 299792.458))
        y += 1
        _sep = CE.eme_sun_separation_deg(o.lat, o.lon, t)
        _kv(win, y, x0, w, "Sun separation", "%.0f deg" % _sep,
            cp(CLR_WARN) if (_sep < 10 and mel > 0) else 0)
        y += 1
        _kv(win, y, x0, w, "Ground gain", CE.eme_ground_gain(mel)[1],
            cp(CLR_OK) if CE.eme_ground_gain(mel)[0] else 0)
        y += 2
        addstr(win, y, x0, "COMMON-MOON WINDOWS", cp(CLR_HEADER))
        y += 1
        if not self.windows:
            addstr(win, y, x0, "press g to scan 48 h", cp(CLR_DIM))
            return
        for i, (a, b) in enumerate(self.windows):
            if y + i >= y0 + h:
                break
            addstr(win, y + i, x0, clip("%-18s %-18s %s" % (
                fmt_clock(a, True), fmt_clock(b, True),
                fmt_dur(b - a)), w))

    def _draw_bands(self, win, y0, x0, h, w):
        o = self.state.store.obs
        t = time.time()
        try:
            flux = (self.state.store.load_spacewx_cache() or {}).get("flux")
        except Exception:
            flux = None
        addstr(win, y0, x0, "EME per-band analysis  (a next view)",
               cp(CLR_TITLE))
        addstr(win, y0 + 2, x0, clip("%-9s %8s %6s %7s %7s %8s" % (
            "BAND", "DOPPLER", "FARAD", "SKY T", "SPREAD", "LOSS dB"), w),
            cp(CLR_HEADER))
        rows = CE.eme_band_analysis(t, o.lat, o.lon, solar_flux=flux)
        for i, b in enumerate(rows):
            addstr(win, y0 + 3 + i, x0, clip(
                "%-9s %+8.0f %5.0f\u00b0 %6.0fK %7.1f %8.1f" % (
                    b["band"], b["doppler_hz"], b["faraday_deg"],
                    b["sky_temp_k"], b["spread_hz"], b["path_loss_db"]), w))
        y = y0 + 4 + len(rows)
        _az, el = CE.moon_azel(o.lat, o.lon, t)
        sep = CE.eme_sun_separation_deg(o.lat, o.lon, t)
        _kv(win, y, x0, w, "Degradation",
            "%.2f dB vs perigee" % CE.eme_path_degradation_db(t))
        y += 1
        _kv(win, y, x0, w, "Ground gain", CE.eme_ground_gain(el)[1],
            cp(CLR_OK) if CE.eme_ground_gain(el)[0] else 0)
        y += 1
        _kv(win, y, x0, w, "Sun separation", "%.0f deg" % sep,
            cp(CLR_WARN) if (sep < 10 and el > 0) else 0)

    def _draw_plan(self, win, y0, x0, h, w):
        if not self.plan:
            self.plan = CE.eme_plan(time.time(), days=90)
        addstr(win, y0, x0, "EME 90-day plan (12:00 UTC daily)  (a next view)",
               cp(CLR_TITLE))
        addstr(win, y0 + 2, x0, clip("%-12s %9s %13s %11s" % (
            "DATE", "MOON DEC", "DEGRADATION", "DISTANCE"), w),
            cp(CLR_HEADER))
        page = max(1, h - 4)
        self.plan_scroll = max(0, min(self.plan_scroll,
                                      max(0, len(self.plan) - page)))
        for i in range(page):
            idx = self.plan_scroll + i
            if idx >= len(self.plan):
                break
            r = self.plan[idx]
            attr = cp(CLR_OK) if r["good"] else 0
            addstr(win, y0 + 3 + i, x0, clip(
                "%-12s %+8.1f %10.2f dB %9.0f km%s" % (
                    r["date"], r["dec_deg"], r["degradation_db"],
                    r["distance_km"], "  * good" if r["good"] else ""), w),
                attr)

    def handle_key(self, ch):
        if self.editing:
            if ch in (ord("\n"), curses.KEY_ENTER):
                cand = self.buf.strip().upper()
                # grid_to_latlon() does not validate - "ZZZZ" yields
                # (202.5, 405.0) - so check the form before accepting it.
                from orbitdeck.engine.activations import valid_grid
                if valid_grid(cand):
                    self.grid = cand
                    self.windows = []
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
        if ch == ord("a"):
            self.view = (self.view + 1) % len(self.VIEWS)
            return True
        if self.VIEWS[self.view] == "plan":
            if ch in (curses.KEY_DOWN, ord("j")):
                self.plan_scroll += 1
                return True
            if ch in (curses.KEY_UP, ord("k")):
                self.plan_scroll = max(0, self.plan_scroll - 1)
                return True
            if ch == curses.KEY_NPAGE:
                self.plan_scroll += 9
                return True
            if ch == curses.KEY_PPAGE:
                self.plan_scroll = max(0, self.plan_scroll - 9)
                return True
        if ch == ord("b"):
            self.band = (self.band + 1) % len(self.BANDS)
            return True
        if ch == ord("g"):
            o = self.state.store.obs
            try:
                lat2, lon2 = grid_to_latlon(self.grid)
            except Exception:
                return True
            self.windows = CE.eme_window(o.lat, o.lon, lat2, lon2, time.time(),
                                         hours=48)
            return True
        return False

    def help_keys(self):
        if self.editing:
            return [("ENTER", "apply grid"), ("ESC", "cancel")]
        return [("a", "view"), ("b", "band"), ("e", "grid"),
                ("g", "scan windows")]


class WorkableScreen(Screen):
    title = "Workable"
    refresh_secs = 5.0

    KINDS = ["Grids", "US states", "DXCC"]

    def __init__(self, app):
        super().__init__(app)
        self.kind = 0
        self.list = ScrollList()
        self.filter = ""
        self.editing = False

    def _items(self):
        sat = self.state.sat
        if sat is None:
            return []
        pred = Predictor()
        pred.set_site(self.state.store.obs)
        if not pred.set_sat(sat):
            return []
        lat, lon, alt = pred.subpoint_at(time.time())
        if self.kind == 0:
            items = sorted(AN.workable_grids(lat, lon, alt))
        else:
            inside = AN.make_footprint_test(lat, lon, alt)
            if self.kind == 1:
                items = sorted(workable_states(inside))
            else:
                items = ["%s  %s" % (p, n)
                         for p, n in workable_dxcc(inside)]
        # A footprint holds ~1700 grids; the list is unusable without a filter.
        if self.filter:
            up = self.filter.upper()
            items = [i for i in items if i.upper().startswith(up)]
        return items

    def draw(self, win, y0, x0, h, w):
        sat = self.state.sat
        if sat is None:
            addstr(win, y0, x0, "No satellite selected.", cp(CLR_WARN))
            return
        items = self._items()
        addstr(win, y0, x0, clip("%s \u2014 %s under the footprint now (%d)"
                                 % (sat.name, self.KINDS[self.kind],
                                    len(items)), w), cp(CLR_TITLE))
        hint = ("filter: %s_  (ENTER apply, ESC cancel)" % self.filter
                if self.editing else
                "w type   f filter%s" % ("  [%s]" % self.filter
                                         if self.filter else ""))
        addstr(win, y0 + 1, x0, clip(hint, w),
               cp(CLR_ACCENT) if self.editing else cp(CLR_DIM))
        page = max(1, h - 3)
        self.list.clamp(len(items), page)
        # multi-column for short entries (grids/states)
        colw = 26 if self.kind == 2 else 10
        percol = max(1, w // colw)
        for i in range(page * percol):
            idx = self.list.top + i
            if idx >= len(items):
                break
            r, c = divmod(i, percol)
            if y0 + 3 + r >= y0 + h:
                break
            addstr(win, y0 + 3 + r, x0 + c * colw,
                   clip(items[idx], colw - 1))

    def handle_key(self, ch):
        if self.editing:
            if ch in (ord("\n"), curses.KEY_ENTER):
                self.editing = False
            elif ch == 27:
                self.editing = False
                self.filter = ""
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                self.filter = self.filter[:-1]
            elif 32 <= ch < 127:
                self.filter += chr(ch)
            self.list = ScrollList()
            return True
        if ch == ord("f"):
            self.editing = True
            self.filter = ""
            return True
        if ch == ord("c"):
            self.filter = ""
            self.list = ScrollList()
            return True
        if ch == ord("w"):
            self.kind = (self.kind + 1) % len(self.KINDS)
            self.list = ScrollList()
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, 999, 8)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, 999, 8)
            return True
        return False

    def help_keys(self):
        return [("w", "type"), ("f", "filter"), ("c", "clear"),
                ("up/dn", "scroll")]
