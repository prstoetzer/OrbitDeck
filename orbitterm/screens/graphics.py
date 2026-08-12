"""orbitterm/screens/graphics.py - the graphical TUI screens.

These use the braille sub-cell canvas (``orbitterm.canvas``) rather than plain
character blocks, so a plot gets 2x4 addressable dots per cell - roughly 8x the
resolution of a block-character chart in the same space.

  * Sky at a Glance - pass timeline across all favorites
  * Graphing Calculator - plot expressions of x
  * Sky Map - star field with satellite overlay, zenith-centred
  * Orbital History - element series from the Space-Track archive cache
"""

import curses
import json
import math
import os
import time

from ..ui import Screen, addstr, cp, clip
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_DIM, CLR_OK, CLR_WARN,
                  CLR_ACCENT, CLR_ROW_SEL)
from ..fmt import fmt_clock
from ..canvas import Canvas, blit, scale

from orbitdeck.engine.predict import Predictor
from orbitdeck.engine import skyglance as SG
from orbitdeck.engine import skymap as SM
from orbitdeck.engine import calc as C
from orbitdeck.engine import spacetrack as ST


class SkyGlanceScreen(Screen):
    title = "Sky at a Glance"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.hours = 12
        self.rows = []
        self.status = "r refresh   w window"

    def on_enter(self):
        if not self.rows:
            self._reload()

    def _reload(self):
        favs = [s for s in self.state.store.db.sats
                if s.norad in self.state.store.favorites]
        if not favs:
            self.status = "no favorites - star some in Satellites"
            self.rows = []
            return
        pred = Predictor()
        self.rows = SG.sky_glance(pred, self.state.store.obs, favs,
                                  time.time(), hours=self.hours)
        n = sum(len(r["passes"]) for r in self.rows)
        gap = SG.busiest_gap(self.rows, time.time(), self.hours)
        self.status = "%d pass(es) / %dh" % (n, self.hours)
        if gap and gap[1] - gap[0] > 600:
            self.status += "   longest quiet gap %.1f h" % (
                (gap[1] - gap[0]) / 3600.0)

    def draw(self, win, y0, x0, h, w):
        addstr(win, y0, x0, "Sky at a Glance \u2014 next %dh" % self.hours,
               cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        if not self.rows:
            return
        label_w = 11
        chart_cols = max(10, w - label_w - 1)
        t0 = time.time()
        t1 = t0 + self.hours * 3600.0
        avail = max(1, h - 4)
        per = max(1, avail // max(1, len(self.rows)))
        y = y0 + 3
        for r in self.rows:
            if y >= y0 + h:
                break
            addstr(win, y, x0, clip("%-10s" % r["name"][:10], label_w))
            cv = Canvas(chart_cols, max(1, per))
            for a, b, el in r["passes"]:
                xa = int(scale(a, t0, t1, 0, cv.width - 1))
                xb = int(scale(b, t0, t1, 0, cv.width - 1))
                colour = (cp(CLR_OK) if el >= 45 else
                          cp(CLR_ACCENT) if el >= 20 else cp(CLR_WARN))
                for x in range(min(xa, xb), max(xa, xb) + 1):
                    cv.fill_column(x, 0, cv.height - 1, colour)
            blit(win, cv, y, x0 + label_w)
            y += per
        # time axis
        if y < y0 + h:
            marks = []
            for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
                marks.append((int(frac * (chart_cols - 5)),
                              fmt_clock(t0 + frac * self.hours * 3600.0)[-5:]))
            line = [" "] * chart_cols
            for col, txt in marks:
                for i, ch in enumerate(txt):
                    if col + i < chart_cols:
                        line[col + i] = ch
            addstr(win, y, x0 + label_w, "".join(line), cp(CLR_DIM))

    def handle_key(self, ch):
        if ch == ord("r"):
            self._reload()
            return True
        if ch == ord("w"):
            self.hours = {6: 12, 12: 24, 24: 6}.get(self.hours, 12)
            self._reload()
            return True
        return False

    def help_keys(self):
        return [("r", "refresh"), ("w", "window")]


class GraphCalcScreen(Screen):
    title = "Graphing Calc"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.expr = "sin(x)"
        self.xmin, self.xmax = -6.283, 6.283
        self.editing = False
        self.buf = ""
        self.status = "e edit expression   [ ] zoom"

    def _samples(self, npx):
        xs, ys = [], []
        for i in range(npx):
            x = self.xmin + (self.xmax - self.xmin) * i / max(1, npx - 1)
            xs.append(x)
            try:
                v = C.evaluate_with(self.expr, {"x": x})
                ys.append(float(v) if abs(float(v)) < 1e12 else None)
            except Exception:
                ys.append(None)
        return xs, ys

    def draw(self, win, y0, x0, h, w):
        title = "y = " + (self.buf if self.editing else self.expr)
        addstr(win, y0, x0, clip(title, w),
               cp(CLR_ACCENT) if self.editing else cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip("x in [%.3g, %.3g]   %s"
                                     % (self.xmin, self.xmax, self.status), w),
               cp(CLR_DIM))
        rows = max(2, h - 3)
        cv = Canvas(max(10, w - 1), rows)
        xs, ys = self._samples(cv.width)
        good = [v for v in ys if v is not None]
        if not good:
            addstr(win, y0 + 3, x0, "expression did not evaluate",
                   cp(CLR_WARN))
            return
        vmin, vmax = min(good), max(good)
        if vmax - vmin < 1e-9:
            vmin, vmax = vmin - 1, vmax + 1
        # zero axis
        if vmin <= 0 <= vmax:
            zy = int(scale(0.0, vmin, vmax, 0, cv.height - 1, invert=True))
            for x in range(cv.width):
                cv.plot(x, zy, cp(CLR_DIM))
        prev = None
        for i, v in enumerate(ys):
            if v is None:
                prev = None
                continue
            py = int(scale(v, vmin, vmax, 0, cv.height - 1, invert=True))
            if prev is not None:
                cv.line(prev[0], prev[1], i, py, cp(CLR_OK))
            else:
                cv.plot(i, py, cp(CLR_OK))
            prev = (i, py)
        blit(win, cv, y0 + 2, x0)
        addstr(win, y0 + 2, x0, clip("%.3g" % vmax, 8), cp(CLR_DIM))
        addstr(win, y0 + 2 + rows - 1, x0, clip("%.3g" % vmin, 8),
               cp(CLR_DIM))

    def handle_key(self, ch):
        if self.editing:
            if ch in (ord("\n"), curses.KEY_ENTER):
                self.expr = self.buf or self.expr
                self.editing = False
            elif ch == 27:
                self.editing = False
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                self.buf = self.buf[:-1]
            elif 32 <= ch < 127:
                self.buf += chr(ch)
            return True
        if ch == ord("e"):
            self.editing = True
            self.buf = self.expr
            return True
        if ch == ord("]"):
            self.xmin *= 0.5
            self.xmax *= 0.5
            return True
        if ch == ord("["):
            self.xmin *= 2.0
            self.xmax *= 2.0
            return True
        return False

    def help_keys(self):
        if self.editing:
            return [("ENTER", "apply"), ("ESC", "cancel")]
        return [("e", "edit"), ("[ ]", "zoom")]


class SkyMapScreen(Screen):
    title = "Sky Map"
    refresh_secs = 10.0

    def __init__(self, app):
        super().__init__(app)
        self.max_mag = 4.0
        self.show_lines = True

    def draw(self, win, y0, x0, h, w):
        o = self.state.store.obs
        t = time.time()
        addstr(win, y0, x0, "Sky Map \u2014 zenith centred, N up", cp(CLR_TITLE))
        rows = max(3, h - 2)
        cols = min(max(10, w - 1), rows * 2)      # keep the disk round-ish
        cv = Canvas(cols, rows)
        size = min(cv.width, cv.height)
        cx, cy = cv.width // 2, cv.height // 2
        r = size // 2 - 1
        cv.circle(cx, cy, r, cp(CLR_DIM))

        def to_xy(az, el):
            rr = (90.0 - el) / 90.0 * r
            a = math.radians(az)
            return cx + rr * math.sin(a), cy - rr * math.cos(a)

        if self.show_lines:
            for a1, e1, a2, e2 in SM.constellation_segments(o.lat, o.lon, t):
                if e1 < 0 and e2 < 0:
                    continue
                x1, y1 = to_xy(a1, max(0, e1))
                x2, y2 = to_xy(a2, max(0, e2))
                cv.line(x1, y1, x2, y2, cp(CLR_DIM))
        stars = SM.visible_stars(o.lat, o.lon, t, max_mag=self.max_mag)
        for az, el, _m in stars:
            x, y = to_xy(az, el)
            cv.plot(x, y, cp(CLR_HEADER))
        n_sat = 0
        pred = Predictor()
        pred.set_site(o)
        sel = self.state.sat
        for s in self.state.store.db.sats:
            if s.norad not in self.state.store.favorites and s is not sel:
                continue
            try:
                if not pred.set_sat(s):
                    continue
                look = pred.look(t)
            except Exception:
                continue
            if look.el < 0:
                continue
            x, y = to_xy(look.az, look.el)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cv.plot(x + dx, y + dy, cp(CLR_WARN))
            n_sat += 1
        blit(win, cv, y0 + 1, x0)
        for az, lab in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
            x, y = to_xy(az, 0)
            try:
                win.addstr(y0 + 1 + int(y) // 4, x0 + int(x) // 2, lab,
                           cp(CLR_ACCENT))
            except Exception:
                pass
        addstr(win, y0 + h - 1, x0, clip(
            "%d stars to mag %.1f, %d sat(s) up   m mag   l lines"
            % (len(stars), self.max_mag, n_sat), w), cp(CLR_DIM))

    def handle_key(self, ch):
        if ch == ord("m"):
            self.max_mag = {3.0: 4.0, 4.0: 5.0, 5.0: 3.0}.get(self.max_mag,
                                                              4.0)
            return True
        if ch == ord("l"):
            self.show_lines = not self.show_lines
            return True
        return False

    def help_keys(self):
        return [("m", "magnitude"), ("l", "lines")]


class OrbitHistoryScreen(Screen):
    sat_scoped = ("samples",)
    title = "Orbital History"
    refresh_secs = 0.0

    CACHE = os.path.join(os.path.expanduser("~"), ".orbitdeck", "sthist")
    COLUMNS = ["APOAPSIS", "PERIAPSIS", "INCLINATION", "ECCENTRICITY",
               "PERIOD", "SEMIMAJOR_AXIS", "BSTAR"]

    def __init__(self, app):
        super().__init__(app)
        self.col = 0
        self.view = 0                 # 0 value, 1 rate, 2 analysis, 3 table
        self.zoom = (0.0, 1.0)
        self.scroll = 0
        self.samples = []
        self.status = "c column  t view  +/- zoom  [ ] pan  0 reset  f fetch"

    def on_enter(self):
        self._load()

    def _load(self):
        sat = self.state.sat
        if sat is None:
            self.status = "no satellite selected"
            return
        path = os.path.join(self.CACHE, "%d.json" % sat.norad)
        try:
            with open(path) as f:
                self.samples = json.load(f)
            span = (self.samples[-1]["epoch"] - self.samples[0]["epoch"])
            self.status = "%d element sets over %.1f years" % (
                len(self.samples), span / 86400.0 / 365.25)
        except Exception:
            self.samples = []
            self.status = ("no cached history - press f to fetch from "
                           "Space-Track")

    def _cache_path(self, norad):
        return os.path.join(self.CACHE, "%d.json" % int(norad))

    def _fetch(self):
        """Fetch this object's archive from Space-Track and cache it.

        OrbitTerm no longer needs the desktop app for this: the credentials come
        from Settings, and the result is written to the same cache the desktop
        screen reads, so either front-end can populate it for the other.
        """
        sat = self.state.sat
        if sat is None:
            self.status = "no satellite selected"
            return
        cfg = self.state.store.config
        user = cfg.get("spacetrack_user", "")
        pw = cfg.get("spacetrack_pass", "")
        if not user or not pw:
            self.status = "set Space-Track credentials in Settings first"
            return
        self.status = "fetching %s from Space-Track..." % sat.name
        try:
            cli = ST.SpaceTrackClient(user, pw)
            samples = cli.fetch_history(sat.norad)
        except Exception as exc:
            self.status = "fetch failed: %s" % str(exc)[:60]
            return
        if not samples:
            self.status = "no archived elements returned for this object"
            return
        self.samples = samples
        try:
            os.makedirs(self.CACHE, exist_ok=True)
            with open(self._cache_path(sat.norad), "w") as f:
                json.dump(samples, f)
        except Exception:
            pass                      # a failed cache write is not fatal
        span = samples[-1]["epoch"] - samples[0]["epoch"]
        self.status = "%d element sets over %.1f years (cached)" % (
            len(samples), span / 86400.0 / 365.25)

    VIEWS = ["value", "rate", "analysis", "table"]

    def _visible(self):
        return ST.window(self.samples, *self.zoom)

    def draw(self, win, y0, x0, h, w):
        sat = self.state.sat
        col = self.COLUMNS[self.col]
        label, unit = ST.COLUMN_LABELS[col]
        if self.samples and self.view == 2:
            return self._draw_analysis(win, y0, x0, h, w, col, label, unit)
        if self.samples and self.view == 3:
            return self._draw_table(win, y0, x0, h, w, col, label, unit)
        addstr(win, y0, x0, clip("%s \u2014 %s%s" % (
            sat.name if sat else "-", label,
            (" (%s)" % unit) if unit else ""), w), cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status + "   c column", w),
               cp(CLR_DIM))
        if not self.samples:
            return
        vis = self._visible()
        if self.view == 1:
            ts, vs = ST.rate_series(vis, col)
            unit_note = " per year"
        else:
            ts, vs = ST.series(vis, col)
            unit_note = ""
        if not vs:
            addstr(win, y0 + 3, x0, "no data in this view", cp(CLR_WARN))
            return
        addstr(win, y0 + 2, x0, clip("%s%s   [%s]  %s" % (
            label, unit_note, self.VIEWS[self.view],
            "full record" if self.zoom == (0.0, 1.0)
            else "%.0f%%-%.0f%%" % (self.zoom[0] * 100, self.zoom[1] * 100)),
            w), cp(CLR_ACCENT))
        rows = max(2, h - 4)
        cv = Canvas(max(10, w - 10), rows)
        vmin, vmax = min(vs), max(vs)
        tmin, tmax = ts[0], ts[-1]
        prev = None
        for t, v in zip(ts, vs):
            px = int(scale(t, tmin, tmax, 0, cv.width - 1))
            py = int(scale(v, vmin, vmax, 0, cv.height - 1, invert=True))
            if prev:
                cv.line(prev[0], prev[1], px, py, cp(CLR_OK))
            prev = (px, py)
        blit(win, cv, y0 + 3, x0 + 9)
        addstr(win, y0 + 3, x0, clip("%9.4g" % vmax, 9), cp(CLR_DIM))
        addstr(win, y0 + 3 + rows - 1, x0, clip("%9.4g" % vmin, 9),
               cp(CLR_DIM))
        if y0 + 3 + rows < y0 + h:
            addstr(win, y0 + 3 + rows, x0 + 9,
                   clip("%s   ...   %s" % (fmt_clock(tmin, True),
                                           fmt_clock(tmax, True)), w - 9),
                   cp(CLR_DIM))

    def _draw_analysis(self, win, y0, x0, h, w, col, label, unit):
        a = ST.analyse_rate(self.samples, col)
        addstr(win, y0, x0, clip("%s \u2014 rate analysis (whole record)"
                                 % label, w), cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        if a is None:
            addstr(win, y0 + 3, x0, "not enough data for analysis",
                   cp(CLR_WARN))
            return
        per = "%s/yr" % (unit or "units")
        rows = [("Verdict", a["verdict"]),
                ("Early era mean", "%.4g %s" % (a["early_mean"], per)),
                ("Late era mean", "%.4g %s" % (a["late_mean"], per)),
                ("Acceleration", "%.4g %s/yr" % (a["accel_per_year"], per)),
                ("Median |rate|", "%.4g %s" % (a["median_abs"], per)),
                ("Peak |rate|", "%.4g %s on %s" % (
                    a["peak_rate"], per, fmt_clock(a["peak_time"], True)[:10])),
                ("Jumps (>5x med)", "%d" % a["n_jumps"]),
                ("Intervals", "%d" % a["n"])]
        y = y0 + 3
        for k, v in rows:
            if y >= y0 + h:
                break
            addstr(win, y, x0, clip("%-18s" % k, 18), cp(CLR_DIM))
            addstr(win, y, x0 + 19, clip(str(v), max(1, w - 19)),
                   cp(CLR_OK) if k == "Verdict" else 0)
            y += 1
        if a["jumps"] and y + 1 < y0 + h:
            y += 1
            addstr(win, y, x0, "LARGEST JUMPS", cp(CLR_HEADER))
            y += 1
            for t, r in sorted(a["jumps"], key=lambda j: -abs(j[1]))[:4]:
                if y >= y0 + h:
                    break
                addstr(win, y, x0, clip("  %s   %+.4g %s" % (
                    fmt_clock(t, True)[:10], r, per), w), cp(CLR_WARN))
                y += 1

    def _draw_table(self, win, y0, x0, h, w, col, label, unit):
        rows = ST.summarize(self._visible())
        addstr(win, y0, x0, clip("Summary \u2014 %s" % (
            "full record" if self.zoom == (0.0, 1.0)
            else "%.0f%%-%.0f%% of record" % (self.zoom[0] * 100,
                                              self.zoom[1] * 100)), w),
               cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        addstr(win, y0 + 3, x0, clip("%-14s %9s %9s %9s %9s" % (
            "ELEMENT", "FIRST", "LAST", "CHANGE", "PER YR"), w),
            cp(CLR_HEADER))
        y = y0 + 4
        for r in rows[self.scroll:]:
            if y >= y0 + h:
                break
            addstr(win, y, x0, clip("%-14s %9.4g %9.4g %+9.3g %+9.3g" % (
                r["label"][:14], r["first"], r["last"], r["delta"],
                r["rate_per_year"]), w),
                cp(CLR_ROW_SEL) if r["column"] == col else 0)
            y += 1

    def handle_key(self, ch):
        if ch == ord("t"):
            self.view = (self.view + 1) % len(self.VIEWS)
            self.scroll = 0
            return True
        if ch in (ord("+"), ord("="), ord("-"), ord("["), ord("]"), ord("0")):
            lo, hi = self.zoom
            span = hi - lo
            ctr = 0.5 * (lo + hi)
            if ch == ord("0"):
                lo, hi = 0.0, 1.0
            elif ch in (ord("+"), ord("=")):
                span = max(0.02, span / 2)
                lo, hi = ctr - span / 2, ctr + span / 2
            elif ch == ord("-"):
                span = min(1.0, span * 2)
                lo, hi = ctr - span / 2, ctr + span / 2
            else:
                step = span / 4 * (1 if ch == ord("]") else -1)
                lo, hi = lo + step, hi + step
            if lo < 0:
                hi -= lo
                lo = 0.0
            if hi > 1:
                lo -= hi - 1
                hi = 1.0
            self.zoom = (max(0.0, lo), min(1.0, hi))
            return True
        if ch == ord("c"):
            self.col = (self.col + 1) % len(self.COLUMNS)
            return True
        if ch == ord("r"):
            self._load()
            return True
        if ch == ord("f"):
            self._fetch()
            return True
        return False

    def help_keys(self):
        return [("c", "column"), ("t", "view"), ("+/-", "zoom"),
                ("[ ]", "pan"), ("f", "fetch")]
