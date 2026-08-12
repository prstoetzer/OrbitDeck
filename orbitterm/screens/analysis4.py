"""orbitterm/screens/analysis4.py - a fourth batch of TUI screens.

Five text-native screens completing the non-graphical TUI gap:

  * Planning - workable horizon (10-day union across favorites) and target
    search (every pass where one state / DXCC / grid is workable)
  * Activations - the hams.at upcoming-activations feed
  * AMSAT Status - the community status board
  * Celestial - radio-source az/el for antenna alignment and sun-noise work
  * Exports - write pass and element CSVs to disk

The remaining TUI screens (globe, sky map, sky-at-a-glance, orbital history,
graphing calculator, OSCARLOCATOR sim, Learn) are graphical and need ASCII
rendering rather than a table.
"""

import curses
import os
import time

from ..ui import Screen, ScrollList, addstr, cp, clip
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_DIM, CLR_OK, CLR_ACCENT, CLR_ROW_SEL, CLR_WARN)
from ..fmt import fmt_dur, fmt_clock

from orbitdeck.engine.predict import Predictor
from orbitdeck.engine import planning as PL
from orbitdeck.engine import celestial as CE
from orbitdeck.engine import amsatstatus as AS
from orbitdeck.gui import datafeeds as DF
from orbitdeck.gui import exports as EX


def _kv(win, y, x, w, label, value, attr=0):
    addstr(win, y, x, clip("%-18s" % label, 18), cp(CLR_DIM))
    addstr(win, y, x + 19, clip(str(value), max(1, w - 19)), attr)


def _favs(state):
    return [s for s in state.store.db.sats if s.norad in state.store.favorites]


class PlanningScreen(Screen):
    title = "Planning"
    refresh_secs = 0.0

    MODES = ["Workable horizon", "Target search"]
    KINDS = ["state", "dxcc", "grid"]

    def __init__(self, app):
        super().__init__(app)
        self.mode = 0
        self.kind = 0
        self.target = "California"
        self.rows = []
        self.list = ScrollList()
        self.status = "h horizon   t target search   k kind"

    def _horizon(self):
        favs = _favs(self.state)
        if not favs:
            self.status = "no favorites - star some in Satellites"
            return
        self.status = "scanning %d favorites over 10 d..." % len(favs)
        pred = Predictor()
        pred.set_site(self.state.store.obs)
        res = PL.workable_horizon(pred, favs, time.time(), days=10)
        self.rows = ([("state", s) for s in res["states"]]
                     + [("DXCC", d) for d in res["dxcc"]])
        self.mode = 0
        self.status = "%d states, %d DXCC across %d favorites" % (
            len(res["states"]), len(res["dxcc"]), res["sat_count"])

    def _target(self):
        favs = _favs(self.state)
        if not favs:
            self.status = "no favorites - star some in Satellites"
            return
        pred = Predictor()
        pred.set_site(self.state.store.obs)
        res = PL.target_search(pred, favs, self.KINDS[self.kind], self.target,
                               time.time(), days=10)
        self.rows = [(r["sat_name"], r) for r in res]
        self.mode = 1
        self.status = "%d pass(es) work %s over 10 d" % (len(res), self.target)

    def draw(self, win, y0, x0, h, w):
        addstr(win, y0, x0, clip("%s \u2014 %s" % (
            self.MODES[self.mode],
            self.target if self.mode else "all favorites"), w), cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        if self.mode == 0:
            head = "%-10s %s" % ("TYPE", "WORKABLE")
        else:
            head = "%-18s %-16s %10s %6s" % ("SATELLITE", "START",
                                             "WINDOW", "MAX EL")
        addstr(win, y0 + 3, x0, clip(head, w), cp(CLR_HEADER))
        page = max(1, h - 5)
        self.list.clamp(len(self.rows), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(self.rows):
                break
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else 0
            if self.mode == 0:
                kind, item = self.rows[idx]
                line = "%-10s %s" % (kind, item)
            else:
                _n, r = self.rows[idx]
                line = "%-18s %-16s %10s %5.0f" % (
                    r["sat_name"][:18], fmt_clock(r["start"], True),
                    fmt_dur(r["duration_s"]), r["max_el_deg"])
            addstr(win, y0 + 4 + i, x0, clip(line, w), attr)

    def handle_key(self, ch):
        if ch == ord("h"):
            self._horizon()
            return True
        if ch == ord("t"):
            self._target()
            return True
        if ch == ord("k"):
            self.kind = (self.kind + 1) % len(self.KINDS)
            self.status = "target kind: %s" % self.KINDS[self.kind]
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, len(self.rows), 10)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, len(self.rows), 10)
            return True
        return False

    def help_keys(self):
        return [("h", "horizon"), ("t", "target"), ("k", "kind")]


class ActivationsScreen(Screen):
    title = "Activations"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.rows = []
        self.list = ScrollList()
        self.status = "r fetch   w check   a star   ENTER detail"
        self.detail = None          # (act, info) once checked
        self.view = "list"
        self.win_sel = 0
        self.tp_sel = 0
        self.mode_sel = 0
        self.anchor_sel = 1
        # once the operator picks, stop overriding them with the seed
        self._tp_touched = False
        self._mode_touched = False

    def _fetch(self):
        self.status = "fetching hams.at feed..."
        from orbitdeck.netio import http_get as _http_get
        try:
            self.rows = DF.fetch_activations(
                lambda url, timeout=25: _http_get(url, timeout))
            self.status = ("%d upcoming activation(s)" % len(self.rows)
                           if self.rows else "feed reachable, nothing "
                           "scheduled right now")
        except Exception as exc:
            self.status = "fetch failed: %s" % str(exc)[:40]

    def draw(self, win, y0, x0, h, w):
        if self.detail and self.view != "list":
            return self._draw_detail(win, y0, x0, h, w)
        addstr(win, y0, x0, "Upcoming satellite activations (hams.at)",
               cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        addstr(win, y0 + 3, x0, clip("%-18s %-9s %-10s %-6s %-5s %s" % (
            "START", "CALL", "SATELLITE", "GRID", "EL", "MODE"), w),
            cp(CLR_HEADER))
        page = max(1, h - 5)
        self.list.clamp(len(self.rows), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(self.rows):
                break
            a = self.rows[idx]
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else 0
            addstr(win, y0 + 4 + i, x0, clip("%-18s %-9s %-10s %-6s %-5s %s" % (
                a["start"][:18], a["callsign"][:9], a["sat"][:10],
                a["grid"][:6], a["max_el"][:5], a["mode"][:8]), w), attr)

    VIEWS = ["list", "windows", "doppler", "notes"]

    def _cycle_view(self):
        if not self.detail:
            self.status = "press w to check this activation first"
            return
        i = (self.VIEWS.index(self.view) + 1) % len(self.VIEWS)
        self.view = self.VIEWS[i]

    def _draw_notes(self, win, y0, x0, h, w):
        """The activation's own record, including the operator's comment.

        The feed carries what the activator is doing and any conditions, and
        there was no way to read it in the terminal.
        """
        act, _info = self.detail
        # _draw_detail has already written the "CALL on SAT from GRID" header
        # at y0; writing another there produced "Activation detailFN31".
        y = y0 + 2
        for label, key in (("Satellite", "sat"), ("Callsign", "callsign"),
                           ("Grid", "grid"), ("Date", "date"),
                           ("Start", "start"), ("End", "end"),
                           ("Mode", "mode"), ("Frequency", "freq"),
                           ("Max elevation", "max_el")):
            val = act.get(key)
            if not val or y >= y0 + h:
                continue
            _kv(win, y, x0, w, label, str(val))
            y += 1
        comment = (act.get("comment") or "").strip()
        if comment and y + 1 < y0 + h:
            y += 1
            addstr(win, y, x0, "NOTES", cp(CLR_HEADER))
            y += 1
            line = ""
            for word in comment.split():
                if len(line) + 1 + len(word) > w - 1:
                    addstr(win, y, x0, line)
                    y += 1
                    line = word
                    if y >= y0 + h:
                        break
                else:
                    line = (line + " " + word).strip()
            if line and y < y0 + h:
                addstr(win, y, x0, clip(line, w))

    def _draw_detail(self, win, y0, x0, h, w):
        """Mutual windows, then the DX Doppler table for the chosen one."""
        from orbitdeck.engine import dxdoppler as DXD
        act, info = self.detail
        addstr(win, y0, x0, clip("%s on %s from %s" % (
            act.get("callsign", "?"), act.get("sat", "?"),
            info.get("grid", "?")), w), cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        wins = info.get("windows") or []
        if self.view == "notes":
            return self._draw_notes(win, y0, x0, h, w)
        if self.view == "windows" or not wins:
            addstr(win, y0 + 3, x0, clip("%-20s %-10s %-9s %8s %8s" % (
                "START", "END", "DURATION", "MY EL", "DX EL"), w),
                cp(CLR_HEADER))
            for i, wm in enumerate(wins):
                if y0 + 4 + i >= y0 + h:
                    break
                attr = cp(CLR_ROW_SEL) if i == self.win_sel else 0
                addstr(win, y0 + 4 + i, x0, clip(
                    "%-20s %-10s %-9s %7.0f %7.0f" % (
                        fmt_clock(wm["start"], True), fmt_clock(wm["end"]),
                        fmt_dur(wm["end"] - wm["start"]),
                        wm["my_max_el"], wm["dx_max_el"]), w), attr)
            if not wins:
                addstr(win, y0 + 4, x0, "no mutual window", cp(CLR_WARN))
            return
        # doppler view
        wm = wins[min(self.win_sel, len(wins) - 1)]
        sat = info.get("sat")
        tps = list(getattr(sat, "transponders", []) or [])
        if not tps:
            addstr(win, y0 + 3, x0, clip(
                "No transponder data for %s \u2014 update the transponder "
                "database." % getattr(sat, "name", "?"), w), cp(CLR_WARN))
            return
        # Seed from the activation's own stated frequency, as the desktop
        # detail view does: match it to a transponder LEG and hold the anchored
        # dial there. These fixes were made desktop-side and never mirrored.
        from orbitdeck.engine import activations as ACT
        seed_idx, seed_leg, seed_hz = ACT.match_transponder(sat, act)
        if seed_idx is not None and not self._tp_touched:
            self.tp_sel = seed_idx
        tp = tps[self.tp_sel % len(tps)]
        linear = False
        try:
            linear = bool(getattr(tp, "is_linear", False)) and \
                tp.bandwidth() > 0
        except Exception:
            linear = False
        if seed_leg and not self._mode_touched:
            # A single-channel transponder has no passband to hold a dial in,
            # so a "fixed" mode there would be theatre - stay in true rule.
            if linear:
                self.mode_sel = 1 if seed_leg == "downlink" else 2
                self.anchor_sel = 2 if seed_leg == "downlink" else 3
            else:
                self.mode_sel = 0
        mode = [DXD.TRUE_RULE, DXD.FIXED_DL, DXD.FIXED_UL][self.mode_sel % 3]
        anchor = [DXD.ME_RX, DXD.ME_TX, DXD.DX_RX,
                  DXD.DX_TX][self.anchor_sel % 4]
        pb = 0
        seeded = False
        if linear and seed_hz and mode in (DXD.FIXED_DL, DXD.FIXED_UL):
            try:
                pb = DXD.solve_pb_for_dial(wm["start"], sat,
                                           self.state.store.obs, info["dx"],
                                           tp, seed_hz, anchor, mode)
                seeded = True
            except Exception:
                pb = 0
        if not seeded:
            try:
                if linear:
                    pb = int(tp.bandwidth() / 2)
            except Exception:
                pb = 0
        addstr(win, y0 + 2, x0, clip(
            "%s | %s | anchor %s  (m mode, n anchor, p transponder)" % (
                # the attribute is .desc - .description does not exist, which
                # showed "tp" for every transponder
                (getattr(tp, "desc", None) or getattr(tp, "name", None)
                 or "transponder")[:24],
                ["true rule", "fixed DL", "fixed UL"][self.mode_sel % 3],
                ["me RX", "me TX", "DX RX", "DX TX"][self.anchor_sel % 4]), w),
            cp(CLR_ACCENT))
        # Four dials plus a clock will not fit 80 columns at 14 wide each.
        # MHz values need 8 significant chars ("437.8089"); the unit goes in
        # the header instead of on every row.
        addstr(win, y0 + 3, x0, clip("%-9s %11s %11s %11s %11s" % (
            "UTC", "MY RX MHz", "MY TX MHz", "DX RX MHz", "DX TX MHz"), w),
            cp(CLR_HEADER))
        try:
            rows = DXD.dx_doppler_table(wm["start"], wm["end"], sat,
                                        self.state.store.obs, info["dx"],
                                        tp, pb, mode=mode, anchor=anchor)
        except Exception as exc:
            addstr(win, y0 + 4, x0, clip("table failed: %s" % str(exc)[:60],
                                         w), cp(CLR_WARN))
            return
        for i, (t, mrx, mtx, drx, dtx) in enumerate(rows):
            if y0 + 4 + i >= y0 + h:
                break
            addstr(win, y0 + 4 + i, x0, clip(
                "%-9s %11.4f %11.4f %11.4f %11.4f" % (
                    fmt_clock(t), mrx / 1e6, mtx / 1e6, drx / 1e6,
                    dtx / 1e6), w))

    def _check(self):
        """Can you and the activator both see the satellite at the listed time?"""
        from orbitdeck.engine import activations as ACT
        if not self.rows or self.list.sel >= len(self.rows):
            self.status = "no activation selected"
            return
        act = self.rows[self.list.sel]
        self.status = "checking mutual visibility..."
        try:
            state, info = ACT.check_activation(self.state.store, act)
        except Exception as exc:
            self.status = "check failed: %s" % str(exc)[:50]
            return
        base = "%s on %s" % (act.get("callsign", "?"), act.get("sat", "?"))
        if state == ACT.FP_OK:
            a, b = info["window"]
            self.status = ("%s: workable %s-%s UTC  (ENTER for windows / "
                           "Doppler)" % (base, fmt_clock(a), fmt_clock(b)))
            self.detail = (act, info)
            self.view = "windows"
        else:
            self.status = "%s: %s" % (base, ACT.FP_TEXT[state])

    def _add(self):
        """Star the activation's satellite, looking locally before CelesTrak."""
        from orbitdeck.engine import activations as ACT
        if not self.rows or self.list.sel >= len(self.rows):
            return
        name = self.rows[self.list.sel].get("sat", "")
        store = self.state.store
        have = ACT.find_local(store.db, name)
        if have is None:
            self.status = "%s is not in your catalog (add it in Satellites)" \
                % name
            return
        if have.norad in store.favorites:
            self.status = "%s is already a favorite" % have.name
            return
        store.favorites.add(have.norad)
        store.save_config()
        self.status = "starred %s (NORAD %d)" % (have.name, have.norad)

    def handle_key(self, ch):
        if ch == ord("r"):
            self._fetch()
            return True
        if ch == ord("w"):
            self._check()
            return True
        if ch == ord("a"):
            self._add()
            return True
        if ch in (ord("\n"), curses.KEY_ENTER, ord("v")):
            self._cycle_view()
            return True
        if self.detail and self.view != "list":
            wins = (self.detail[1].get("windows") or [])
            if ch == ord("m"):
                self.mode_sel = (self.mode_sel + 1) % 3
                self._mode_touched = True
                return True
            if ch == ord("n"):
                self.anchor_sel = (self.anchor_sel + 1) % 4
                self._mode_touched = True
                return True
            if ch == ord("p"):
                self.tp_sel += 1
                self._tp_touched = True
                return True
            if ch in (ord("i"), ord("N")):
                self.view = "notes"
                return True
            if ch == 27:
                self.view = "list"
                return True
            if ch in (curses.KEY_DOWN, ord("j")) and wins:
                self.win_sel = (self.win_sel + 1) % len(wins)
                return True
            if ch in (curses.KEY_UP, ord("k")) and wins:
                self.win_sel = (self.win_sel - 1) % len(wins)
                return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, len(self.rows), 10)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, len(self.rows), 10)
            return True
        return False

    def help_keys(self):
        if self.detail and self.view != "list":
            return [("ENTER", "view"), ("m", "mode"), ("n", "anchor"),
                    ("p", "transponder"), ("ESC", "list")]
        return [("r", "refresh"), ("w", "can I work it"), ("a", "star sat"),
                ("ENTER", "detail")]


class AmsatStatusScreen(Screen):
    title = "AMSAT Status"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.rows = []
        self.list = ScrollList()
        self.hours = 24
        self.status = "r fetches the status board"

    def _resolve(self):
        """API names for the active satellite, via the catalog matcher."""
        from orbitdeck.netio import http_get as _http_get
        sat = self.state.sat
        if sat is None:
            self.status = "no satellite selected"
            return
        try:
            body = _http_get(AS.CATALOG_URL, 25)
            names = AS.resolve_names(AS.parse_catalog(body),
                                     getattr(sat, "name", ""))
        except Exception as exc:
            self.status = "catalog fetch failed: %s" % str(exc)[:50]
            return
        self.status = ("%s -> %s" % (sat.name, ", ".join(names)) if names
                       else "%s has no AMSAT status entry" % sat.name)

    def _fetch(self):
        self.status = "fetching..."
        from orbitdeck.netio import http_get as _http_get
        try:
            body = _http_get(AS.summary_url(self.hours), 25)
            self.rows = AS.parse_summary(body)
            self.status = ("%d satellite(s) reported in %dh"
                           % (len(self.rows), self.hours)
                           if self.rows else "no reports (or offline)")
        except Exception as exc:
            self.status = "fetch failed: %s" % str(exc)[:40]

    def draw(self, win, y0, x0, h, w):
        addstr(win, y0, x0, "AMSAT community status board", cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        addstr(win, y0 + 3, x0, clip("%-26s %9s %8s  %s" % (
            "SATELLITE", "REPORTS", "HEARD", "LAST"), w), cp(CLR_HEADER))
        page = max(1, h - 5)
        self.list.clamp(len(self.rows), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(self.rows):
                break
            r = self.rows[idx]
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else (
                cp(CLR_OK) if r["heard"] else 0)
            addstr(win, y0 + 4 + i, x0, clip("%-26s %9d %8d  %s" % (
                r["pretty"][:26], r["reports"], r["heard"],
                str(r["last_report"])[:19]), w), attr)

    def handle_key(self, ch):
        if ch == ord("r"):
            self._fetch()
            return True
        if ch == ord("w"):
            self.hours = {6: 24, 24: 48, 48: 6}.get(self.hours, 24)
            self.status = "window %dh - press r" % self.hours
            return True
        if ch == ord("m"):
            self._resolve()
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, len(self.rows), 10)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, len(self.rows), 10)
            return True
        return False

    def help_keys(self):
        return [("r", "refresh"), ("w", "window"), ("m", "match this sat")]


class CelestialScreen(Screen):
    # Cold-sky temperature is what tells you whether the background behind a
    # source is quiet enough to hear it - the desktop screen shows it.

    title = "Celestial"
    refresh_secs = 5.0

    def __init__(self, app):
        super().__init__(app)
        self.list = ScrollList()

    def draw(self, win, y0, x0, h, w):
        o = self.state.store.obs
        t = time.time()
        addstr(win, y0, x0, "Radio sources \u2014 az/el for alignment and "
               "sun-noise work", cp(CLR_TITLE))
        # Cold-sky temperature: what the background behind a source is, which
        # decides whether a weak source is audible at all.
        try:
            cold = CE.eme_sky_temp_k(t, 144.0)
            addstr(win, y0 + 1, x0, clip(
                "Cold-sky temperature %.0f K at 144 MHz" % cold, w),
                cp(CLR_DIM))
        except Exception:
            pass
        addstr(win, y0 + 2, x0, clip("%-22s %9s %9s  %s" % (
            "SOURCE", "AZ", "EL", "STATE"), w), cp(CLR_HEADER))
        names = list(CE.RADIO_SOURCES)
        page = max(1, h - 4)
        self.list.clamp(len(names), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(names):
                break
            name = names[idx]
            if name == "Sun":
                from orbitdeck.engine.transits import _sun_azel
                az, el = _sun_azel(o.lat, o.lon, t)
            else:
                res = CE.source_azel(name, o.lat, o.lon, t)
                if res is None:
                    continue
                az, el = res
            up = el > 0
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else (
                cp(CLR_OK) if up else cp(CLR_DIM))
            addstr(win, y0 + 3 + i, x0, clip("%-22s %8.1f\u00b0 %8.1f\u00b0  %s"
                                             % (name[:22], az, el,
                                                "up" if up else "below"), w),
                   attr)

    def handle_key(self, ch):
        n = len(CE.RADIO_SOURCES)
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, n, 8)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, n, 8)
            return True
        return False

    def help_keys(self):
        return [("up/dn", "scroll")]


class ExportsScreen(Screen):
    title = "Exports"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.status = "p passes CSV   e elements CSV"
        self.outdir = os.path.expanduser("~")

    def _write(self, name, text):
        path = os.path.join(self.outdir, name)
        try:
            with open(path, "w") as f:
                f.write(text)
            self.status = "wrote %s" % path
        except Exception as exc:
            self.status = "write failed: %s" % str(exc)[:50]

    def _passes(self):
        sat = self.state.sat
        if sat is None:
            self.status = "no satellite selected"
            return
        pred = Predictor()
        pred.set_site(self.state.store.obs)
        if not pred.set_sat(sat):
            self.status = "cannot propagate"
            return
        passes = pred.predict_passes(time.time(), 5.0, 50,
                                     time.time() + 7 * 86400)
        self._write("orbitdeck_passes.csv",
                    EX.passes_to_csv(passes, sat.name))

    def _elements(self):
        rows = []
        for s in self.state.store.db.sats:
            rows.append((s.name, s.norad, "%.4f" % s.incl,
                         "%.6f" % s.ecc, "%.8f" % s.mean_motion))
        self._write("orbitdeck_elements.csv", EX.rows_to_csv(
            ["name", "norad", "incl_deg", "ecc", "mean_motion"], rows))

    def draw(self, win, y0, x0, h, w):
        addstr(win, y0, x0, "Exports", cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(self.status, w), cp(CLR_DIM))
        y = y0 + 3
        _kv(win, y, x0, w, "Output folder", self.outdir)
        y += 2
        sat = self.state.sat
        addstr(win, y, x0, "p  \u2014 7-day pass list for %s"
               % (sat.name if sat else "(no satellite)"), cp(CLR_ACCENT))
        y += 1
        addstr(win, y, x0, "e  \u2014 element set for the whole catalog (%d)"
               % self.state.store.db.count(), cp(CLR_ACCENT))
        y += 2
        addstr(win, y, x0, "CSV is written to your home folder.", cp(CLR_DIM))

    def handle_key(self, ch):
        if ch == ord("p"):
            self._passes()
            return True
        if ch == ord("e"):
            self._elements()
            return True
        return False

    def help_keys(self):
        return [("p", "passes CSV"), ("e", "elements CSV")]


class PropagationScreen(Screen):
    """HF / 6 m operating outlook - the desktop screen had no terminal twin."""

    title = "Propagation"
    refresh_secs = 0.0

    def _cache(self):
        try:
            return self.state.store.load_spacewx_cache() or {}
        except Exception:
            return {}

    def draw(self, win, y0, x0, h, w):
        from orbitdeck.engine import propagation as PROP
        res = PROP.outlook(self._cache(), time.time())
        addstr(win, y0, x0, "HF / 6 m propagation outlook", cp(CLR_TITLE))
        if not res["have_data"]:
            addstr(win, y0 + 2, x0,
                   "No space-weather data \u2014 update it on Space Wx.",
                   cp(CLR_WARN))
            return
        y = y0 + 2
        if res["muf_day"]:
            _kv(win, y, x0, w, "MUF (day)", "%.0f MHz" % res["muf_day"])
            y += 1
            _kv(win, y, x0, w, "MUF (night)", "%.0f MHz" % res["muf_night"])
            y += 1
        if res["flux"] is not None:
            _kv(win, y, x0, w, "Solar flux", "%.0f sfu" % res["flux"])
            y += 1
        sev = {0: cp(CLR_DIM), 1: 0, 2: cp(CLR_OK), 3: cp(CLR_WARN)}
        for label, key in (("Geomagnetic", "geomagnetic"),
                           ("Aurora (VHF)", "aurora"),
                           ("Absorption", "absorption"),
                           ("Meteor scatter", "meteor"),
                           ("Sporadic E", "sporadic_e")):
            text, s = res[key]
            _kv(win, y, x0, w, label, text, sev.get(s, 0))
            y += 1
        y += 1
        addstr(win, y, x0, clip("%-8s %-8s %s" % ("BAND", "DAY", "NIGHT"), w),
               cp(CLR_HEADER))
        y += 1
        night = {b: st for b, st, _v in res["bands_night"]}
        for band, state, s in res["bands_day"]:
            if y >= y0 + h:
                break
            addstr(win, y, x0, clip("%-8s %-8s %s" % (
                band, state, night.get(band, "?")), w),
                cp(CLR_OK) if state == "open" else
                (cp(CLR_WARN) if state == "shut" else 0))
            y += 1

    def help_keys(self):
        return [("(rules of thumb from flux and Kp)", "")]


class QrzScreen(Screen):
    """QRZ callsign lookup — the desktop screen had no terminal counterpart.

    Credentials come from Settings, so this needs no desktop install. The
    session key is cached for the run: QRZ expires keys, and re-logging in on
    every lookup would burn the account's query allowance.
    """

    title = "QRZ Lookup"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.editing = False
        self.buf = ""
        self.call = ""
        self.result = None
        self.status = "e enter a callsign"
        self._key = ""

    def _lookup(self, call):
        from orbitdeck.gui import datafeeds as DF
        from orbitdeck.netio import http_get
        cfg = self.state.store.config
        user = cfg.get("qrz_user", "")
        pw = cfg.get("qrz_pass", "")
        if not user or not pw:
            self.status = "set QRZ credentials in Settings first"
            return
        self.status = "looking up %s\u2026" % call
        try:
            res, key, err = DF.qrz_lookup(
                lambda url, timeout=15: http_get(url, timeout),
                user, pw, call, session_key=self._key)
        except Exception as exc:
            self.result = None
            self.status = "lookup failed: %s" % str(exc)[:60]
            return
        if key:
            self._key = key
        if err or not res:
            self.result = None
            self.status = err or "no QRZ record for %s" % call
            return
        self.result = res
        self.call = call
        self.status = "%s \u2014 %s" % (call, res.get("name_fmt")
                                       or res.get("name") or "")

    def draw(self, win, y0, x0, h, w):
        addstr(win, y0, x0, "QRZ callsign lookup", cp(CLR_TITLE))
        addstr(win, y0 + 1, x0, clip(
            ("callsign: %s_" % self.buf) if self.editing else self.status, w),
            cp(CLR_ACCENT) if self.editing else cp(CLR_DIM))
        if not self.result:
            return
        r = self.result
        y = y0 + 3
        for label, key in (("Callsign", "call"), ("Name", "name_fmt"),
                           ("Class", "class"), ("Grid", "grid"),
                           ("Address", "addr"), ("State", "state"),
                           ("ZIP", "zip"), ("Country", "country")):
            val = r.get(key) or ""
            if not val:
                continue
            if y >= y0 + h:
                break
            _kv(win, y, x0, w, label, str(val))
            y += 1
        grid = r.get("grid")
        if grid and y + 1 < y0 + h:
            # Distance and bearing from your station: the reason an operator
            # looks a call up mid-pass.
            try:
                from orbitdeck.engine.muf import great_circle
                from orbitdeck.engine.predict import grid_to_latlon
                lat, lon = grid_to_latlon(grid)
                o = self.state.store.obs
                dist, brg = great_circle(o.lat, o.lon, lat, lon)
                y += 1
                _kv(win, y, x0, w, "From you",
                    "%.0f km  bearing %03.0f\u00b0" % (dist, brg))
            except Exception:
                pass

    def handle_key(self, ch):
        if self.editing:
            if ch in (ord("\n"), curses.KEY_ENTER):
                cand = self.buf.strip().upper()
                self.editing = False
                if cand:
                    self._lookup(cand)
                return True
            if ch == 27:
                self.editing = False
                return True
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                self.buf = self.buf[:-1]
                return True
            if 32 <= ch < 127:
                self.buf += chr(ch)
                return True
            return True
        if ch in (ord("e"), ord("E")):
            self.editing = True
            self.buf = ""
            return True
        if ch == ord("r") and self.call:
            self._lookup(self.call)
            return True
        return False

    def help_keys(self):
        if self.editing:
            return [("ENTER", "look up"), ("ESC", "cancel")]
        return [("e", "callsign"), ("r", "repeat")]
