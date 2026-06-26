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
    ("settings", SettingsScreen),
]


class App:
    def __init__(self, scr):
        self.scr = scr
        self.state = AppState()
        self.screens = {}
        self.order = []
        for key, cls in NAV:
            self.screens[key] = cls(self)
            self.order.append(key)
        self.active = "home"
        self.nav_focus = False     # True when the nav column has focus
        self._running = True
        self._last_draw = 0.0
        self.screens[self.active].on_enter()

    # ---- navigation ----
    def goto(self, key):
        if key in self.screens and key != self.active:
            self.active = key
            self.screens[key].on_enter()

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
            return
        # number shortcuts: 1..9 -> first nine items, 0 -> last item (Settings)
        if ord("1") <= ch <= ord("9"):
            idx = ch - ord("1")
            visible = [k for k in self.order if k != "passdetail"]
            if idx < len(visible):
                self.goto(visible[idx])
            return
        if ch == ord("0"):
            visible = [k for k in self.order if k != "passdetail"]
            if visible:
                self.goto(visible[-1])
            return

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

    def _handle_nav(self, ch):
        visible = [k for k in self.order if k != "passdetail"]
        cur = self.active if self.active in visible else visible[0]
        i = visible.index(cur) if cur in visible else 0
        if ch in (curses.KEY_DOWN, ord("j")):
            i = (i + 1) % len(visible)
            self.goto(visible[i])
        elif ch in (curses.KEY_UP, ord("k")):
            i = (i - 1) % len(visible)
            self.goto(visible[i])
        elif ch in (curses.KEY_RIGHT, curses.KEY_ENTER, 10, 13):
            self.nav_focus = False

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
        addstr(scr, 0, w - 19, time.strftime("%H:%M:%S  "), cp(CLR_HEADER))
        addstr(scr, 0, w - 10, time.strftime("%Z") or "local", cp(CLR_DIM))
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
        visible = [k for k in self.order if k != "passdetail"]
        last_idx = len(visible) - 1
        for i, key in enumerate(visible):
            screen = self.screens[key]
            # number-key hint: 1-9 for the first nine, 0 for the last item,
            # blank for any middle overflow (reached via Tab)
            if i < 9:
                keyhint = str(i + 1)
            elif i == last_idx:
                keyhint = "0"
            else:
                keyhint = " "
            label = "%s %s" % (keyhint, screen.title)
            yy = y0 + i
            if yy >= y0 + h:
                break
            is_active = (key == self.active) or (
                self.active == "passdetail" and key == "passes")
            if is_active and self.nav_focus:
                attr = cp(CLR_NAV_SEL) | curses.A_BOLD
            elif is_active:
                attr = cp(CLR_TITLE) | curses.A_BOLD
            else:
                attr = cp(CLR_NAV)
            addstr(scr, yy, x0 + 1, ljust(label, w - 1), attr)
        # focus hint
        addstr(scr, y0 + h - 1, x0 + 1,
               "TAB nav" if not self.nav_focus else "TAB back",
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
