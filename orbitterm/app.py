"""orbitterm/app.py - the OrbitTerm curses application shell.

Lays out a left nav column and a content pane, runs the input/refresh loop, and
dispatches keys to the active screen. Reuses OrbitDeck's engine and config via
AppState.
"""

import curses
import time

from .state import AppState
from . import ui
from .ui import addstr, hline, cp, ljust
from .ui import (CLR_TITLE, CLR_NAV, CLR_NAV_SEL, CLR_HEADER, CLR_DIM,
                 CLR_STATUS, CLR_WARN)

from .screens.live import HomeScreen, TrackScreen
from .screens.passes import PassesScreen, PassDetailScreen
from .screens.catalog import SatellitesScreen, RadarScreen
from .screens.analysis_screens import OrbitalAnalysisScreen, GroundTrackScreen
from .screens.progression import ProgressionScreen
from .screens.illumination import IlluminationScreen
from .screens.radio_settings import RadioScreen, SettingsScreen
from .screens.tools import ToolsScreen
from .screens.references import ReferencesScreen
from .screens.analysis2 import (ZonesScreen, MufScreen, SunMoonScreen,
                                EmeScreen, WorkableScreen)
from .screens.analysis3 import (MutualScreen, TransitsScreen,
                                ConjunctionScreen, Ao7Screen,
                                SpaceWxScreen, SitesScreen)
from .screens.analysis4 import (PlanningScreen, ActivationsScreen,
                                AmsatStatusScreen, CelestialScreen,
                                ExportsScreen, PropagationScreen)
from .screens.graphics import (SkyGlanceScreen, GraphCalcScreen,
                               SkyMapScreen, OrbitHistoryScreen)
from .screens.globe import GlobeScreen
from .screens.oscarsim import OscarSimScreen


# (key_hint, registry_key, ScreenClass) - order defines the nav list and the
# number-key shortcuts.
NAV = [
    ("home", HomeScreen),
    ("satellites", SatellitesScreen),
    ("track", TrackScreen),
    ("passes", PassesScreen),
    ("passdetail", PassDetailScreen),
    ("radar", RadarScreen),
    ("groundtrack", GroundTrackScreen),
    ("progression", ProgressionScreen),
    ("illum", IlluminationScreen),
    ("orbit", OrbitalAnalysisScreen),
    ("radio", RadioScreen),
    ("tools", ToolsScreen),
    ("globe", GlobeScreen),
    ("skyglance", SkyGlanceScreen),
    ("planning", PlanningScreen),
    ("mutual", MutualScreen),
    ("transits", TransitsScreen),
    ("conjunction", ConjunctionScreen),
    ("ao7", Ao7Screen),
    ("workable", WorkableScreen),
    ("zones", ZonesScreen),
    ("sunmoon", SunMoonScreen),
    ("eme", EmeScreen),
    ("skymap", SkyMapScreen),
    ("orbithistory", OrbitHistoryScreen),
    ("graphcalc", GraphCalcScreen),
    ("muf", MufScreen),
    ("propagation", PropagationScreen),
    ("spacewx", SpaceWxScreen),
    ("celestial", CelestialScreen),
    ("activations", ActivationsScreen),
    ("amsatstatus", AmsatStatusScreen),
    ("sites", SitesScreen),
    ("exports", ExportsScreen),
    ("oscarsim", OscarSimScreen),
    ("references", ReferencesScreen),
    ("settings", SettingsScreen),
]


class App:
    def __init__(self, scr):
        self.scr = scr
        self.state = AppState()
        self.screens = {}
        self.order = []
        self._sat_listener_registered = False
        for key, cls in NAV:
            self.screens[key] = cls(self)
            self.order.append(key)
        self.active = "home"
        self._register_sat_listener()
        self.nav_focus = False     # True when the nav column has focus
        self.nav_sel = 0           # highlighted row in the nav list
        self.nav_top = 0           # first visible nav row (scrolling)
        self._running = True
        self._last_draw = 0.0
        self.screens[self.active].on_enter()

    # ---- navigation ----
    def goto(self, key):
        if key in self.screens and key != self.active:
            self.active = key
            scr = self.screens[key]
            # screens persist, so clear the old satellite's results first
            try:
                scr.clear_if_sat_changed(self.state.selected_norad)
            except Exception:
                pass
            scr.on_enter()

    def _register_sat_listener(self):
        # once only: goto() runs constantly and would otherwise pile up
        # duplicate listeners, each re-clearing on every satellite change
        if getattr(self, "_sat_listener_registered", False):
            return
        self._sat_listener_registered = True
        try:
            self.state.on_sat_change(lambda _n: self._notify_sat_change())
        except Exception:
            pass

    def _notify_sat_change(self):
        """Every screen drops stale results when the satellite changes."""
        for scr in self.screens.values():
            try:
                scr.clear_if_sat_changed(self.state.selected_norad)
            except Exception:
                pass

    def cycle_sat(self, delta):
        sats = self.state.sats
        if not sats:
            return
        cur = self.state.selected_norad
        idx = 0
        for i, s in enumerate(sats):
            if s.norad == cur:
                idx = i
                break
        idx = (idx + delta) % len(sats)
        self.state.select(sats[idx].norad)
        self.state.flash("Selected %s" % sats[idx].name)

    def show_pass_detail(self, p):
        pd = self.screens["passdetail"]
        pd.pass_ = p
        self.goto("passdetail")

    def do_refresh_catalog(self):
        self.state.flash("Fetching AMSAT elements\u2026", 30)
        self._draw()
        curses.doupdate()

        def prog(msg):
            self.state.flash(msg, 30)
        ok, msg = self.state.refresh_catalog(progress=prog)
        self.state.flash(msg, 5)

    # ---- main loop ----
    def run(self):
        self.scr.timeout(250)
        while self._running:
            self._draw()
            curses.doupdate()
            try:
                ch = self.scr.getch()
            except KeyboardInterrupt:
                break
            if ch == -1:
                continue
            self._handle(ch)

    def _handle(self, ch):
        # global keys
        if ch in (ord("q"), ord("Q")):
            self._running = False
            return
        if ch == curses.KEY_RESIZE:
            return
        if ch == ord("\t"):
            self.nav_focus = not self.nav_focus
            if self.nav_focus:
                vis = self._visible()
                if self.active in vis:
                    self.nav_sel = vis.index(self.active)
            return
        # No number shortcuts: with 36 screens the 1-9 + 0 scheme covered only
        # ten of them and silently left the middle unreachable except by Tab,
        # which read as a broken menu. The nav is a plain scrolling list now.
        if self.nav_focus:
            self._handle_nav(ch)
            return

        # let the active screen consume it
        scr = self.screens[self.active]
        if scr.handle_key(ch):
            return
        # fall back: arrows move nav if screen didn't use them
        if ch in (curses.KEY_LEFT,):
            self.nav_focus = True

    def _visible(self):
        return [k for k in self.order if k != "passdetail"]

    def _handle_nav(self, ch):
        visible = self._visible()
        if not visible:
            return
        if self.nav_sel >= len(visible):
            self.nav_sel = 0
        if ch in (curses.KEY_DOWN, ord("j")):
            self.nav_sel = (self.nav_sel + 1) % len(visible)
        elif ch in (curses.KEY_UP, ord("k")):
            self.nav_sel = (self.nav_sel - 1) % len(visible)
        elif ch in (curses.KEY_NPAGE,):
            self.nav_sel = min(len(visible) - 1, self.nav_sel + 10)
        elif ch in (curses.KEY_PPAGE,):
            self.nav_sel = max(0, self.nav_sel - 10)
        elif ch == curses.KEY_HOME:
            self.nav_sel = 0
        elif ch == curses.KEY_END:
            self.nav_sel = len(visible) - 1
        elif ch in (curses.KEY_RIGHT, curses.KEY_ENTER, 10, 13):
            self.goto(visible[self.nav_sel])
            self.nav_focus = False
        elif 32 <= ch < 127:
            # type-ahead: jump to the next screen whose title starts with the
            # letter, which is what a long menu actually needs
            want = chr(ch).lower()
            n = len(visible)
            for step in range(1, n + 1):
                i = (self.nav_sel + step) % n
                if self.screens[visible[i]].title.lower().startswith(want):
                    self.nav_sel = i
                    break

    # ---- drawing ----
    def _draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        nav_w = 18
        # title bar
        title = " OrbitTerm "
        addstr(scr, 0, 0, title, cp(CLR_NAV_SEL) | curses.A_BOLD)
        sat = self.state.sat
        sub = "  %s @ %s" % (
            sat.name if sat else "(no sat)", self.state.grid())
        addstr(scr, 0, len(title), ljust(sub, w - len(title) - 20), cp(CLR_DIM))
        # UTC everywhere: pass tables, progression and the AOS countdowns are
        # all UTC, so a local-zone header clock invited reading them against the
        # wrong reference.
        addstr(scr, 0, w - 19, time.strftime("%H:%M:%S  ", time.gmtime()),
               cp(CLR_HEADER))
        addstr(scr, 0, w - 10, "UTC", cp(CLR_DIM))
        hline(scr, 1, 0, w, "\u2500", cp(CLR_DIM))

        # nav column
        self._draw_nav(scr, 2, 0, h - 3, nav_w)
        # vertical divider
        for y in range(2, h - 1):
            addstr(scr, y, nav_w, "\u2502", cp(CLR_DIM))

        # content
        cx = nav_w + 2
        cy = 2
        cw = w - cx - 1
        ch_ = h - 3 - cy + 1
        try:
            self.screens[self.active].draw(scr, cy, cx, ch_, cw)
        except Exception as e:
            addstr(scr, cy, cx, "screen error: %s" % e, cp(CLR_WARN))

        # status / help footer
        self._draw_footer(scr, h - 1, 0, w)
        scr.noutrefresh()

    def _draw_nav(self, scr, y0, x0, h, w):
        visible = self._visible()
        if not visible:
            return
        # Keep the cursor in view: the list is longer than any terminal, so the
        # window scrolls with the selection rather than clipping at the bottom.
        page = max(1, h - 1)
        if self.nav_sel >= len(visible):
            self.nav_sel = len(visible) - 1
        if self.nav_sel < self.nav_top:
            self.nav_top = self.nav_sel
        elif self.nav_sel >= self.nav_top + page:
            self.nav_top = self.nav_sel - page + 1
        self.nav_top = max(0, min(self.nav_top, max(0, len(visible) - page)))

        for row in range(page):
            i = self.nav_top + row
            if i >= len(visible):
                break
            key = visible[i]
            screen = self.screens[key]
            is_active = (key == self.active) or (
                self.active == "passdetail" and key == "passes")
            cursor = ">" if (self.nav_focus and i == self.nav_sel) else " "
            label = "%s %s" % (cursor, screen.title)
            if self.nav_focus and i == self.nav_sel:
                attr = cp(CLR_NAV_SEL) | curses.A_BOLD
            elif is_active:
                attr = cp(CLR_TITLE) | curses.A_BOLD
            else:
                attr = cp(CLR_NAV)
            addstr(scr, y0 + row, x0 + 1, ljust(label, w - 1), attr)
        # scroll indicators, so it is obvious there is more list
        if self.nav_top > 0:
            addstr(scr, y0, x0 + w - 1, "\u2191", cp(CLR_DIM))
        if self.nav_top + page < len(visible):
            addstr(scr, y0 + page - 1, x0 + w - 1, "\u2193", cp(CLR_DIM))
        # focus hint
        addstr(scr, y0 + h - 1, x0 + 1,
               "TAB menu" if not self.nav_focus else "ENTER open  TAB back",
               cp(CLR_DIM))

    def _draw_footer(self, scr, y, x0, w):
        st = self.state
        status = st.current_status()
        if status:
            addstr(scr, y, x0, ljust(" " + status, w),
                   cp(CLR_STATUS) | curses.A_BOLD)
            return
        # per-screen key hints + global
        hints = list(self.screens[self.active].help_keys())
        parts = ["%s %s" % (k, lbl) for k, lbl in hints]
        parts += ["TAB nav", "q quit"]
        line = "  ".join(parts)
        addstr(scr, y, x0, ljust(" " + line, w), cp(CLR_STATUS))


def main():
    def _run(scr):
        curses.curs_set(0)
        ui.init_colors()
        scr.keypad(True)
        App(scr).run()
    curses.wrapper(_run)


if __name__ == "__main__":
    main()
