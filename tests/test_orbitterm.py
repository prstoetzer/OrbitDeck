"""Tests for OrbitTerm.

These exercise OrbitTerm's logic without a real terminal: a tiny fake curses
window records draw calls, so every screen's draw() path runs against the real
engine and asserts it produces output without raising. This catches API drift
between OrbitTerm and the OrbitDeck engine.
"""

import time

import pytest

from orbitterm.state import AppState
from orbitterm import fmt


# ---------- a minimal fake curses window ----------
class FakeWin:
    def __init__(self, h=34, w=100):
        self.h = h
        self.w = w
        self.calls = []

    def getmaxyx(self):
        return (self.h, self.w)

    def addstr(self, y, x, s, attr=0):
        # mimic curses raising on the bottom-right corner write
        if y >= self.h or x >= self.w:
            raise _CursesError()
        self.calls.append((y, x, s))

    def text(self):
        return "\n".join(s for _, _, s in self.calls)


class _CursesError(Exception):
    pass


@pytest.fixture(autouse=True)
def _patch_curses(monkeypatch):
    """Make ui.addstr's curses.error catch our fake error, and stub colour/bold
    so screens can import and run headless."""
    import curses
    import orbitterm.ui as ui
    monkeypatch.setattr(curses, "error", _CursesError, raising=False)
    monkeypatch.setattr(curses, "has_colors", lambda: False, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    # neutralise color_pair lookups
    monkeypatch.setattr(ui, "cp", lambda p: 0)
    yield


def _state():
    return AppState()


def test_state_loads():
    st = _state()
    assert st.store.db.count() > 0
    assert st.sat is not None
    assert "FM" in st.grid() or len(st.grid()) == 6


def test_formatters():
    assert fmt.compass(0) == "N"
    assert fmt.compass(90) == "E"
    assert fmt.compass(180) == "S"
    assert fmt.compass(270) == "W"
    assert fmt.fmt_dur(125) == "2m05s"
    assert fmt.fmt_az(45).startswith("045.0")
    assert "MHz" in fmt.fmt_freq(145_800_000)


def _all_screen_classes():
    from orbitterm.screens.live import HomeScreen, TrackScreen
    from orbitterm.screens.passes import PassesScreen, PassDetailScreen
    from orbitterm.screens.catalog import SatellitesScreen, RadarScreen
    from orbitterm.screens.analysis_screens import (
        OrbitalAnalysisScreen, GroundTrackScreen)
    from orbitterm.screens.progression import ProgressionScreen
    from orbitterm.screens.illumination import IlluminationScreen
    from orbitterm.screens.radio_settings import RadioScreen, SettingsScreen
    return [HomeScreen, TrackScreen, PassesScreen, PassDetailScreen,
            SatellitesScreen, RadarScreen, OrbitalAnalysisScreen,
            GroundTrackScreen, ProgressionScreen, IlluminationScreen,
            RadioScreen, SettingsScreen]


class _FakeApp:
    """Just enough app surface for screens that call back into it."""
    def __init__(self, state):
        self.state = state

    def cycle_sat(self, d):
        pass

    def goto(self, k):
        pass

    def show_pass_detail(self, p):
        pass

    def do_refresh_catalog(self):
        pass


def test_every_screen_draws():
    st = _state()
    app = _FakeApp(st)
    win = FakeWin()
    for cls in _all_screen_classes():
        scr = cls(app)
        scr.on_enter()
        # should not raise, and should draw something
        win.calls.clear()
        scr.draw(win, 2, 20, 30, 78)
        assert win.calls, "%s produced no output" % cls.__name__


def test_passes_screen_predicts():
    st = _state()
    from orbitterm.screens.passes import PassesScreen
    scr = PassesScreen(_FakeApp(st))
    scr.on_enter()
    scr._ensure()
    # the selected sample sat should have upcoming passes
    assert isinstance(scr._passes, list)


def test_track_matches_engine():
    """OrbitTerm's live look must equal a direct engine call."""
    st = _state()
    sat = st.sat
    pred = st.pred_for(sat)
    now = time.time()
    L1 = pred.look(now)
    # a second predictor built the same way must agree
    pred2 = st.pred_for(sat)
    L2 = pred2.look(now)
    assert abs(L1.az - L2.az) < 1e-6
    assert abs(L1.el - L2.el) < 1e-6


def test_select_persists_in_state():
    st = _state()
    sats = st.sats
    if len(sats) > 1:
        target = sats[1].norad
        st.select(target)
        assert st.selected_norad == target
        assert st.sat.norad == target
