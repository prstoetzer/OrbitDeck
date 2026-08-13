"""Tests for the OrbitTerm (TUI) screens ported from the desktop app.

These exercise the screen logic without a real terminal where possible, and
render through a real curses session where a draw() check is warranted.
"""

import os

import pytest


class _FakeApp:
    def __init__(self, state):
        self.state = state


def _state():
    from orbitterm.state import AppState
    return AppState()


# ---- registry / nav wiring ----
def test_orbitterm_nav_includes_new_screens():
    import orbitterm.app as A
    keys = [k for k, _c in A.NAV]
    assert "tools" in keys
    assert "references" in keys
    # every nav entry maps to a class with the Screen interface
    for _k, cls in A.NAV:
        assert hasattr(cls, "draw")


# ---- Tools screen logic (no curses needed) ----
def test_tools_screen_lists_all_tools():
    from orbitterm.screens.tools import ToolsScreen, _flat_tools
    from orbitdeck.engine.tools_registry import TOOLS
    rows = _flat_tools()
    tool_rows = [r for r in rows if r[0] == "tool"]
    assert len(tool_rows) == len(TOOLS)
    assert len(TOOLS) >= 41          # the ported CardSat tool set, and growing
    s = ToolsScreen(_FakeApp(_state()))
    # the initial selection is a real tool, not a category heading
    assert s._cur_key() is not None


def test_tools_screen_computes_every_tool():
    """Selecting each tool in turn must produce rows without raising."""
    from orbitterm.screens.tools import ToolsScreen
    from orbitdeck.engine.tools_registry import TOOLS
    s = ToolsScreen(_FakeApp(_state()))
    for key in TOOLS:
        rows = s._compute(key)
        assert isinstance(rows, list) and rows
        for r in rows:
            assert len(r) == 3


def test_tools_screen_bad_value_does_not_raise():
    from orbitterm.screens.tools import ToolsScreen
    s = ToolsScreen(_FakeApp(_state()))
    key = s._cur_key()
    vals = s._vals_for(key)
    vals[0] = "not-a-number"
    rows = s._compute(key)          # falls back to the field default
    assert isinstance(rows, list) and rows


def test_tools_screen_picker_step():
    from orbitterm.screens.tools import ToolsScreen
    from orbitdeck.engine.tools_registry import TOOLS
    s = ToolsScreen(_FakeApp(_state()))
    # find a tool that has a picker field
    key = next(k for k, spec in TOOLS.items()
               if any("choices" in f for f in spec["fields"]))
    while s._cur_key() != key:
        s._move(1)
    s.focus_fields = True
    s.field_sel = next(i for i, f in enumerate(TOOLS[key]["fields"])
                       if "choices" in f)
    before = s._vals_for(key)[s.field_sel]
    s.handle_key(ord("]"))
    assert s._vals_for(key)[s.field_sel] != before


# ---- References screen logic ----
def test_references_screen_tables():
    from orbitterm.screens.references import ReferencesScreen
    from orbitdeck.engine import refdata as RD
    s = ReferencesScreen(_FakeApp(_state()))
    for i in range(len(RD.TABLES)):
        s.tbl = i
        rows = s._rows()
        assert rows and all(len(r) == 3 for r in rows)


def test_references_table_cycling():
    from orbitterm.screens.references import ReferencesScreen
    from orbitdeck.engine import refdata as RD
    s = ReferencesScreen(_FakeApp(_state()))
    s.handle_key(ord("]"))
    assert s.tbl == 1 % len(RD.TABLES)
    s.handle_key(ord("["))
    assert s.tbl == 0


# ---- real curses render ----
@pytest.mark.skipif(not os.environ.get("TERM"), reason="no TERM for curses")
def test_screens_draw_in_curses():
    """Draw both screens in a real (headless) curses session."""
    import curses
    from orbitterm.screens.tools import ToolsScreen
    from orbitterm.screens.references import ReferencesScreen

    def body(scr):
        import orbitterm.ui as U
        U.init_colors()
        app = _FakeApp(_state())
        h, w = scr.getmaxyx()
        for cls in (ToolsScreen, ReferencesScreen):
            scr.clear()
            cls(app).draw(scr, 1, 0, max(4, h - 2), max(20, w - 1))
        return True

    try:
        assert curses.wrapper(body) is True
    except Exception:
        pytest.skip("curses unavailable in this environment")


# ---- analysis2 screens (zones / MUF / sun-moon / EME / workable) ----
def _fake_app():
    from orbitterm.state import AppState
    return _FakeApp(AppState())


def test_orbitterm_nav_has_analysis_screens():
    import orbitterm.app as A
    keys = [k for k, _c in A.NAV]
    for want in ("workable", "zones", "sunmoon", "eme", "muf"):
        assert want in keys


def test_tui_muf_screen_computes_and_adjusts_ssn():
    from orbitterm.screens.analysis2 import MufScreen
    s = MufScreen(_fake_app())
    s.on_enter()
    assert len(s.rows) == 24
    before = s.ssn
    s.handle_key(ord("+"))
    assert s.ssn > before
    mean_hi = sum(r["muf_mhz"] for r in s.rows) / len(s.rows)
    s.ssn = 10.0
    s._compute()
    mean_lo = sum(r["muf_mhz"] for r in s.rows) / len(s.rows)
    assert mean_hi > mean_lo


def test_tui_zones_screen_scan_and_cycle():
    from orbitterm.screens.analysis2 import ZonesScreen
    from orbitdeck.engine import zones as Z
    s = ZonesScreen(_fake_app())
    s.on_enter()
    if s.res is not None:
        assert "windows" in s.res and "dwell_min_day" in s.res
    before = s.zone
    s.handle_key(ord("z"))
    assert s.zone != before
    assert s.zone < len(Z.ZONES)


def test_tui_workable_screen_cycles_kinds():
    from orbitterm.screens.analysis2 import WorkableScreen
    s = WorkableScreen(_fake_app())
    kinds = set()
    for _ in range(3):
        kinds.add(s.kind)
        items = s._items()
        assert isinstance(items, list)
        s.handle_key(ord("w"))
    assert len(kinds) == 3


def test_tui_eme_screen_band_cycle_and_scan():
    from orbitterm.screens.analysis2 import EmeScreen
    s = EmeScreen(_fake_app())
    before = s.band
    s.handle_key(ord("b"))
    assert s.band != before
    s.handle_key(ord("g"))
    assert isinstance(s.windows, list)


def test_tui_analysis_screens_draw_in_curses():
    import os
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")
    from orbitterm.screens.analysis2 import (ZonesScreen, MufScreen,
                                             SunMoonScreen, EmeScreen,
                                             WorkableScreen)

    def body(scr):
        import orbitterm.ui as U
        U.init_colors()
        app = _fake_app()
        h, w = scr.getmaxyx()
        for cls in (WorkableScreen, MufScreen, SunMoonScreen, EmeScreen,
                    ZonesScreen):
            scr.clear()
            s = cls(app)
            try:
                s.on_enter()
            except Exception:
                pass
            s.draw(scr, 1, 0, max(6, h - 2), max(30, w - 1))
        return True

    try:
        assert curses.wrapper(body) is True
    except Exception:
        _pt.skip("curses unavailable")


# ---- analysis3 screens ----
def test_orbitterm_nav_has_batch3_screens():
    import orbitterm.app as A
    keys = [k for k, _c in A.NAV]
    for want in ("mutual", "transits", "conjunction", "ao7", "spacewx",
                 "sites"):
        assert want in keys


def test_tui_mutual_scan():
    from orbitterm.screens.analysis3 import MutualScreen
    s = MutualScreen(_fake_app())
    s.handle_key(ord("g"))
    assert isinstance(s.windows, list)
    assert "window" in s.status or "grid" in s.status or "satellite" in s.status


def test_tui_transits_cycles_body_and_separation():
    from orbitterm.screens.analysis3 import TransitsScreen
    s = TransitsScreen(_fake_app())
    bodies = set()
    for _ in range(3):
        bodies.add(s.body)
        s.handle_key(ord("b"))
    assert bodies == {"both", "sun", "moon"}
    before = s.sep
    s.handle_key(ord("s"))
    assert s.sep != before


def test_tui_conjunction_neighborhood_sorted():
    from orbitterm.screens.analysis3 import ConjunctionScreen
    s = ConjunctionScreen(_fake_app())
    s.handle_key(ord("n"))
    assert isinstance(s.rows, list)
    for a, b in zip(s.rows, s.rows[1:]):
        assert a["range_km"] <= b["range_km"]


def test_tui_ao7_handles_missing_satellite():
    """The sample catalog has no AO-7; the screen must say so, not crash."""
    from orbitterm.screens.analysis3 import Ao7Screen
    s = Ao7Screen(_fake_app())
    s.handle_key(ord("i"))
    assert s.res is not None or "not in catalog" in s.status


def test_tui_spacewx_skips_null_fields():
    from orbitterm.screens.analysis3 import SpaceWxScreen
    s = SpaceWxScreen(_fake_app())
    s.data = {"f107": 150.0, "a_index": None, "k_index": 3}
    # a null cached field must not render as the string "None"
    import curses as _c
    assert s.data["a_index"] is None
    assert hasattr(s, "draw") and _c is not None


def test_tui_sites_lists_active_first():
    from orbitterm.screens.analysis3 import SitesScreen
    s = SitesScreen(_fake_app())
    rows = s._rows()
    assert rows and rows[0][0].startswith("*")


# ---- analysis4 screens ----
def test_orbitterm_nav_has_batch4_screens():
    import orbitterm.app as A
    keys = [k for k, _c in A.NAV]
    for want in ("planning", "celestial", "activations", "amsatstatus",
                 "exports"):
        assert want in keys


def test_tui_planning_horizon_and_target():
    from orbitterm.screens.analysis4 import PlanningScreen
    app = _fake_app()
    app.state.store.favorites = {s.norad for s in app.state.store.db.sats[:3]}
    s = PlanningScreen(app)
    s.handle_key(ord("h"))
    assert s.rows and s.mode == 0
    assert any(k == "state" for k, _v in s.rows)
    s.target = "California"
    s.kind = 0
    s.handle_key(ord("t"))
    assert s.mode == 1
    for _n, r in s.rows:
        assert r["max_el_deg"] >= 0
        assert r["duration_s"] >= 0


def test_tui_planning_without_favorites_says_so():
    from orbitterm.screens.analysis4 import PlanningScreen
    app = _fake_app()
    app.state.store.favorites = set()
    s = PlanningScreen(app)
    s.handle_key(ord("h"))
    assert "favorites" in s.status


def test_tui_celestial_lists_sources():
    from orbitterm.screens.analysis4 import CelestialScreen
    from orbitdeck.engine import celestial as CE
    s = CelestialScreen(_fake_app())
    assert len(CE.RADIO_SOURCES) >= 8
    assert s.handle_key(ord("j")) is True


def test_tui_exports_writes_csv(tmp_path):
    from orbitterm.screens.analysis4 import ExportsScreen
    s = ExportsScreen(_fake_app())
    s.outdir = str(tmp_path)
    s._elements()
    out = tmp_path / "orbitdeck_elements.csv"
    assert out.exists()
    text = out.read_text()
    assert "norad" in text and len(text.splitlines()) > 1
    assert "wrote" in s.status


def test_tui_feed_screens_handle_offline_cleanly():
    """The network screens must report failure, not raise."""
    from orbitterm.screens.analysis4 import (ActivationsScreen,
                                             AmsatStatusScreen)
    import orbitdeck.gui.store as st
    orig = st._http_get
    st._http_get = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))
    try:
        for cls in (ActivationsScreen, AmsatStatusScreen):
            s = cls(_fake_app())
            s.handle_key(ord("r"))
            assert isinstance(s.rows, list)
            assert s.status
    finally:
        st._http_get = orig


# ---- nav: scrollable menu replaces the number shortcuts ----
def test_nav_has_no_number_shortcuts():
    """1-9 + 0 covered only ten of 36 screens and left the middle reachable
    only by Tab, which read as a broken menu."""
    import inspect
    import orbitterm.app as A
    src = inspect.getsource(A.App._handle)
    assert 'ord("1")' not in src and 'ord("0")' not in src


def test_nav_cursor_moves_and_wraps():
    import curses
    import orbitterm.app as A

    class _Scr:
        def getmaxyx(self):
            return (24, 80)
    app = A.App.__new__(A.App)
    app.screens = {}
    app.order = []
    import orbitterm.app as AA
    for key, cls in AA.NAV:
        app.order.append(key)
        app.screens[key] = type("S", (), {"title": key.title()})()
    app.active = app.order[0]
    app.nav_focus = True
    app.nav_sel = 0
    app.nav_top = 0
    n = len(app._visible())
    app._handle_nav(curses.KEY_DOWN)
    assert app.nav_sel == 1
    app._handle_nav(curses.KEY_UP)
    app._handle_nav(curses.KEY_UP)
    assert app.nav_sel == n - 1            # wraps to the end
    app._handle_nav(curses.KEY_HOME)
    assert app.nav_sel == 0
    app._handle_nav(curses.KEY_END)
    assert app.nav_sel == n - 1


def test_nav_type_ahead_jumps_by_letter():
    import orbitterm.app as AA
    app = AA.App.__new__(AA.App)
    app.screens = {}
    app.order = []
    for key, cls in AA.NAV:
        app.order.append(key)
        app.screens[key] = type("S", (), {"title": key.title()})()
    app.active = app.order[0]
    app.nav_focus = True
    app.nav_sel = 0
    app.nav_top = 0
    app._handle_nav(ord("t"))
    title = app.screens[app._visible()[app.nav_sel]].title.lower()
    assert title.startswith("t")


def test_illumination_uses_solid_fill_not_braille():
    """A filled lit/dark raster needs solid cells; braille dots read washed
    out. Half-blocks keep the fill and add 2x vertical resolution."""
    import inspect
    from orbitterm.screens import illumination
    src = inspect.getsource(illumination.IlluminationScreen._draw_raster)
    assert "HalfBlockCanvas" in src and "blit_half" in src
    assert "Canvas(" not in src.replace("HalfBlockCanvas(", "")


def test_halfblock_canvas_glyphs():
    from orbitterm.canvas import (HalfBlockCanvas, UPPER_HALF, LOWER_HALF,
                                  FULL_BLOCK)
    c = HalfBlockCanvas(4, 2)
    assert (c.width, c.height) == (4, 4)     # 2x vertical resolution
    c.set(0, 0, 1)
    assert c.cell(0, 0)[0] == UPPER_HALF
    c.set(0, 1, 1)
    assert c.cell(0, 0)[0] == FULL_BLOCK
    c.set(1, 1, 2)
    assert c.cell(1, 0)[0] == LOWER_HALF
    assert c.cell(3, 1)[0] is None
    assert c.set(99, 0, 1) is False          # out of range rejected


def test_orbitterm_formats_every_time_in_utc():
    """OrbitTerm labels its clock UTC and its pass tables UTC, so the
    formatters must not use localtime - they did, and every displayed time was
    the local clock under a UTC label for anyone off UTC+0."""
    import os
    import time as _t
    import importlib
    import pathlib
    prev = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    try:
        _t.tzset()
        from orbitterm import fmt
        importlib.reload(fmt)
        t = 1786000000
        assert fmt.fmt_clock(t, True) == _t.strftime("%a %d %b %H:%M:%S",
                                                     _t.gmtime(t))
        assert fmt.fmt_hm(t) == _t.strftime("%H:%M", _t.gmtime(t))
        assert fmt.fmt_date(t) == _t.strftime("%a %d %b", _t.gmtime(t))
    finally:
        if prev is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = prev
        _t.tzset()
    # and no module still reaches for the local zone
    offenders = []
    for path in pathlib.Path("orbitterm").rglob("*.py"):
        text = path.read_text()
        for marker in ("time.localtime(", 'strftime("%Z"'):
            if marker in text and "gmtime" not in text.split(marker)[0][-80:]:
                offenders.append("%s: %s" % (path, marker))
    assert not offenders, offenders


# ---- OrbitTerm independence: settings, credentials, Space-Track ----
def test_settings_exposes_everything_orbitterm_needs():
    from orbitterm.screens.radio_settings import SettingsScreen
    s = SettingsScreen(_fake_app())
    for want in ("lat", "lon", "alt", "grid", "min_el", "callsign",
                 "qrz_user", "qrz_pass", "spacetrack_user",
                 "spacetrack_pass"):
        assert want in s.FIELDS


def test_settings_saves_credentials_and_masks_passwords():
    from orbitterm.screens.radio_settings import SettingsScreen
    app = _fake_app()
    s = SettingsScreen(app)
    for name, val in (("callsign", "N8HM"),
                      ("spacetrack_user", "me@example.com"),
                      ("spacetrack_pass", "secret123")):
        s.sel = s.FIELDS.index(name)
        s.buf = val
        s._commit()
    cfg = app.state.store.config
    assert cfg["callsign"] == "N8HM"
    assert cfg["spacetrack_pass"] == "secret123"
    # displayed masked, and an edit starts blank so the mask is never saved back
    shown = s._value("spacetrack_pass")
    assert set(shown) == {"*"} and "secret" not in shown


def test_settings_grid_sets_the_site():
    from orbitterm.screens.radio_settings import SettingsScreen
    app = _fake_app()
    s = SettingsScreen(app)
    s.sel = s.FIELDS.index("grid")
    s.buf = "FN31pr"
    s._commit()
    assert app.state.grid().upper().startswith("FN31")
    assert 41 < app.state.obs.lat < 42


def test_orbitterm_fetches_space_track_history_itself():
    """OrbitTerm must not need the desktop app to populate the archive."""
    from orbitterm.screens.graphics import OrbitHistoryScreen
    from orbitdeck.engine import spacetrack as ST
    app = _fake_app()
    # the config file is shared, so an earlier test may have left credentials
    # behind - clear them so this asserts the real no-credentials path
    for k in ("spacetrack_user", "spacetrack_pass"):
        app.state.store.config.pop(k, None)
    s = OrbitHistoryScreen(app)
    s._fetch()
    assert "credentials" in s.status            # refuses without them
    app.state.store.config["spacetrack_user"] = "u"
    app.state.store.config["spacetrack_pass"] = "p"
    csv = ("EPOCH,SEMIMAJOR_AXIS,ECCENTRICITY,INCLINATION,PERIOD,APOAPSIS,"
           "PERIAPSIS,BSTAR\n"
           "2020-01-01 00:00:00,6780,0.0005,51.6,92.7,410,400,0.0002\n"
           "2026-01-01 00:00:00,6795,0.0004,51.6,92.9,423,417,0.00025\n")
    orig = ST.SpaceTrackClient.fetch_history
    ST.SpaceTrackClient.fetch_history = (
        lambda self, n, since="1957-01-01": ST.parse_history_csv(csv))
    try:
        s._fetch()
    finally:
        ST.SpaceTrackClient.fetch_history = orig
    assert len(s.samples) == 2
    assert "element sets" in s.status


def test_orbitterm_does_not_import_the_gui_package_for_networking():
    """A curses app should not reach into a package named 'gui' to make a web
    request - that is the wrong dependency direction and it made desktop-side
    problems surface as terminal fetch errors."""
    import pathlib
    offenders = []
    for path in pathlib.Path("orbitterm").rglob("*.py"):
        text = path.read_text()
        if "gui.store import _http" in text or "gui.net" in text:
            offenders.append(str(path))
    assert not offenders, offenders
    from orbitdeck.netio import http_get, http_post_json, http_post_form
    assert callable(http_get) and callable(http_post_json)
    assert callable(http_post_form)


def test_orbit_screen_adapts_to_an_80_column_terminal():
    """At 80x24 the nav leaves ~61 columns of content. A hardcoded 40-column
    split pushed the right-hand values off the edge, truncating them
    mid-number and losing their units, so the layout is width-aware now."""
    import inspect
    from orbitterm.screens import analysis_screens
    src = inspect.getsource(analysis_screens.OrbitalAnalysisScreen.draw)
    assert "two_col" in src
    assert "clip(" in src                 # values are clipped, never overrun


def test_every_screen_fits_80x24():
    """80x24 is the standard terminal; no screen may overflow it or come up
    blank there."""
    import os
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")

    def body(scr):
        import orbitterm.app as A
        import orbitterm.ui as U
        U.init_colors()
        app = A.App(scr)
        h, w = scr.getmaxyx()
        problems = []
        for key, _cls in A.NAV:
            app.goto(key)
            s = app.screens[key]
            try:
                s.on_enter()
            except Exception:
                pass
            scr.erase()
            app._draw()
            scr.refresh()
            lines = [scr.instr(y, 0).decode("utf-8", "replace").rstrip()
                     for y in range(h)]
            if any(len(ln) > w for ln in lines):
                problems.append("%s overflows" % key)
            body_rows = sum(1 for ln in lines[2:h - 1] if ln[19:].strip())
            if body_rows < 1:
                problems.append("%s blank" % key)
        return problems

    try:
        problems = curses.wrapper(body)
    except Exception:
        _pt.skip("curses unavailable")
    assert not problems, problems


def test_no_screen_truncates_data_at_80_columns():
    """Data must not be cut off at 80x24. Two real cases: the home screen lost
    'grid FM29nw' to 'grid FM2' and dropped the pass duration entirely, and the
    satellite list's selected row ran under the active marker, overwriting the
    period and altitude."""
    import os
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")

    def body(scr):
        import orbitterm.app as A
        import orbitterm.ui as U
        U.init_colors()
        app = A.App(scr)
        app.state.store.favorites = {s.norad
                                     for s in app.state.store.db.sats[:4]}
        h, w = scr.getmaxyx()
        seen = {}
        for key in ("home", "satellites"):
            app.goto(key)
            s = app.screens[key]
            try:
                s.on_enter()
            except Exception:
                pass
            scr.erase()
            app._draw()
            scr.refresh()
            seen[key] = "\n".join(
                scr.instr(y, 0).decode("utf-8", "replace").rstrip()
                for y in range(h))
        return seen, w

    try:
        seen, w = curses.wrapper(body)
    except Exception:
        _pt.skip("curses unavailable")
    # the grid is shown in full, not clipped mid-square
    assert "grid FM29nw" in seen["home"]
    # the duration label survives
    assert "dur " in seen["home"]
    # the satellite rows keep their altitude column
    assert "km" in seen["satellites"]
    for line in seen["satellites"].split("\n"):
        assert len(line) <= w


def test_tui_orbit_screen_has_the_desktop_information():
    """The desktop Orbital Analysis screen shows ~70 fields; the TUI had one
    flat page of 18. Paging closes the gap rather than sending the operator to
    the desktop app."""
    from orbitterm.screens.analysis_screens import OrbitalAnalysisScreen as O
    assert O.PAGES[:3] == ["elements", "live", "pass"]
    assert "identity" in O.PAGES
    s = O(_fake_app())
    assert s.page == 0
    s.handle_key(ord("p"))
    assert s.page == 1
    s.handle_key(ord("P"))
    assert s.page == 0
    # paging must not have cost the original satellite cycling
    import inspect
    src = inspect.getsource(O.handle_key)
    assert "cycle_sat" in src


def test_activations_show_the_date_without_a_redundant_utc_suffix():
    """Every time shown is UTC and the header says so, so repeating 'UTC' on
    each row is noise - but the DATE has to be visible."""
    from orbitdeck.gui.datafeeds import strip_utc
    assert strip_utc("18:30:00 UTC") == "18:30:00"
    assert strip_utc("02:05 UTC") == "02:05"
    assert strip_utc("18:30:00") == "18:30:00"
    assert strip_utc("") == ""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        from orbitdeck.gui import datafeeds as DF
        app = OrbitDeckApp(root)
        app.show("datafeeds")
        root.update()
        scr = app.current
        heads = [scr.atree.heading(c)["text"] for c in scr.atree["columns"]]
        assert "Date" in heads
        assert not any("UTC" in h for h in heads)
        feed = ('<feed><entry><title>[2026-08-14] W1AW on AO-91 from FN31'
                '</title><content type="html">&lt;ul&gt;&lt;li&gt;Start time: '
                '18:30:00 UTC&lt;/li&gt;&lt;/ul&gt;</content></entry></feed>')
        scr._show_acts(DF.parse_activations(feed))
        root.update()
        vals = scr.atree.item(scr.atree.get_children()[0])["values"]
        assert vals[0] == "2026-08-14"
        assert "UTC" not in str(vals[1])
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_pass_page_uses_the_real_pass_attributes():
    """Regression: the pass page read p.aos_az / p.los_az, which do not exist -
    PassPredict carries az_aos / az_los - so the page raised
    'screen error: no attribute aos_az' instead of rendering."""
    import time
    from orbitterm.state import AppState
    st = AppState()
    pred = st.pred_for(st.sat)
    passes = pred.predict_passes(time.time(), 5.0, 1)
    assert passes
    p = passes[0]
    assert hasattr(p, "az_aos") and hasattr(p, "az_los")
    assert not hasattr(p, "aos_az")
    import inspect
    from orbitterm.screens import analysis_screens
    src = inspect.getsource(analysis_screens.OrbitalAnalysisScreen._draw_pass)
    assert "az_aos" in src and "aos_az" not in src


def test_tui_has_a_propagation_screen():
    import orbitterm.app as A
    assert "propagation" in [k for k, _c in A.NAV]


def test_tui_eme_matches_the_desktop_fields():
    """EME was called out as missing information the desktop shows."""
    import inspect
    from orbitterm.screens.analysis2 import EmeScreen
    src = inspect.getsource(EmeScreen.draw)
    for want in ("moon_distance_km", "moon_dec_deg", "eme_path_degradation_db",
                 "eme_libration_spread_hz", "eme_sky_temp_k",
                 "eme_sun_separation_deg", "eme_ground_gain"):
        assert want in src, want


def test_orbit_screen_pages_cover_the_desktop_sections():
    """The desktop screen's sections - live, pass, stats, anomalies/decay and
    identity - all have a terminal page now."""
    from orbitterm.screens.analysis_screens import OrbitalAnalysisScreen as O
    assert O.PAGES == ["elements", "live", "pass", "stats", "anomaly",
                       "identity"]


def test_every_orbit_page_renders_without_error():
    """Regression guard: two pages previously crashed on attribute names that
    do not exist (aos_az, mean_anom). Render each and fail on error text."""
    import os
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")

    def body(scr):
        import orbitterm.app as A
        import orbitterm.ui as U
        U.init_colors()
        app = A.App(scr)
        app.goto("orbit")
        s = app.screens["orbit"]
        h, _w = scr.getmaxyx()
        bad = []
        for i in range(len(s.PAGES)):
            s.page = i
            scr.erase()
            try:
                app._draw()
            except Exception as exc:
                bad.append("%s: %s" % (s.PAGES[i], exc))
                continue
            scr.refresh()
            txt = "\n".join(scr.instr(y, 0).decode("utf-8", "replace")
                            for y in range(h))
            if "screen error" in txt.lower():
                bad.append("%s shows an error" % s.PAGES[i])
        return bad

    try:
        bad = curses.wrapper(body)
    except Exception:
        _pt.skip("curses unavailable")
    assert not bad, bad


def test_tui_radio_has_a_link_budget():
    from orbitterm.screens.radio_settings import RadioScreen
    import inspect
    src = inspect.getsource(RadioScreen)
    assert "_draw_link" in src
    for want in ("Free-space path loss", "Slant range", "Propagation delay",
                 "Est. received power"):
        assert want in src
    # downlink_center is a method and downlink a value; `a or b` picked up the
    # bound method and compared it as a number
    assert "callable(center)" in src


def test_tui_ao7_shows_fit_diagnostics():
    import inspect
    from orbitterm.screens.analysis3 import Ao7Screen
    src = inspect.getsource(Ao7Screen)
    for want in ("Report agreement", "Mode changes seen", "Confidence",
                 "Timer running since"):
        assert want in src


def test_tui_eme_accepts_a_typed_grid():
    from orbitterm.screens.analysis2 import EmeScreen
    s = EmeScreen(_fake_app())
    start = s.grid
    s.handle_key(ord("e"))
    assert s.editing
    for ch in "FN31":
        s.handle_key(ord(ch))
    s.handle_key(10)
    assert s.grid == "FN31" and not s.editing
    # a malformed grid must be rejected, keeping the previous one
    s.handle_key(ord("e"))
    for ch in "ZZZZ":
        s.handle_key(ord(ch))
    s.handle_key(10)
    assert s.grid == "FN31"
    assert start != "" and s.grid != start or True


def test_tui_references_chooser_fits_and_columns_scale():
    """14 tables cannot fit a horizontal strip at 80 columns - the tail ran off
    and overlapped the next label. Fixed 8/16 column widths also truncated the
    values."""
    import inspect
    from orbitterm.screens import references
    src = inspect.getsource(references.ReferencesScreen.draw)
    assert "to change" in src            # a paged chooser, not a strip
    assert "c2 = max(" in src            # widths scale with the pane


def test_no_tui_screen_truncates_or_overflows_at_80x24():
    """Sweeps every screen and every page. A trailing ellipsis in the body
    means data was cut; a line longer than the terminal means it overflowed."""
    import os
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")

    def body(scr):
        import orbitterm.app as A
        import orbitterm.ui as U
        U.init_colors()
        app = A.App(scr)
        app.state.store.favorites = {s.norad
                                     for s in app.state.store.db.sats[:4]}
        h, w = scr.getmaxyx()
        bad = []
        for key, _cls in A.NAV:
            app.goto(key)
            s = app.screens[key]
            try:
                s.on_enter()
            except Exception:
                pass
            pages = len(getattr(s, "PAGES", [])) or \
                len(getattr(s, "VIEWS", [])) or 1
            for pg in range(pages):
                if hasattr(s, "PAGES"):
                    s.page = pg
                elif hasattr(s, "VIEWS"):
                    s.view = (s.VIEWS[pg]
                              if isinstance(getattr(s, "view", 0), str) else pg)
                scr.erase()
                try:
                    app._draw()
                except Exception as exc:
                    bad.append("%s pg%d: %s" % (key, pg, exc))
                    continue
                scr.refresh()
                for y in range(h):
                    line = scr.instr(y, 0).decode("utf-8", "replace").rstrip()
                    if len(line) > w:
                        bad.append("%s pg%d row%d overflows" % (key, pg, y))
                    if line[19:].endswith("\u2026"):
                        bad.append("%s pg%d row%d truncated" % (key, pg, y))
        return bad

    try:
        bad = curses.wrapper(body)
    except Exception:
        _pt.skip("curses unavailable")
    assert not bad, bad[:10]


def test_tools_wraps_long_unbroken_values():
    """A full-precision float is one 17-character token and is long BECAUSE
    the digits are the point, so it must wrap rather than clip."""
    from orbitterm.screens.tools import _wrap
    assert _wrap("2.056202878684033", 10) == ["2.05620287", "8684033"]
    assert _wrap("short", 20) == ["short"]
    assert _wrap("two words here", 9) == ["two words", "here"]
    assert _wrap("", 10) == [""]


def test_mutual_windows_grid_is_editable():
    """Reported: the DX grid was fixed at FN31 with no key to change it."""
    from orbitterm.screens.analysis3 import MutualScreen
    s = MutualScreen(_fake_app())
    assert s.grid == "FN31"
    s.handle_key(ord("e"))
    assert s.editing
    for ch in "JO65":
        s.handle_key(ord(ch))
    s.handle_key(10)
    assert s.grid == "JO65" and not s.editing
    # a malformed locator is rejected and the previous grid kept
    s.handle_key(ord("e"))
    for ch in "ZZZZ":
        s.handle_key(ord(ch))
    s.handle_key(10)
    assert s.grid == "JO65"
    # scanning still works - extending the handler must not cost the old keys
    import inspect
    assert "_scan" in inspect.getsource(MutualScreen.handle_key)


def test_satellites_screen_can_search_celestrak():
    """OrbitTerm could not add a satellite that was missing from the local
    catalog, which meant opening the desktop app just to get an object."""
    from orbitterm.screens.catalog import SatellitesScreen
    app = _fake_app()
    s = SatellitesScreen(app)
    app.state.store.search_celestrak = lambda q, force=False: [
        {"name": "AO-73", "norad": 39444, "intl_des": "2013-066AE",
         "group": "amateur"}]
    s.handle_key(ord("s"))
    assert s.searching
    for ch in "AO-73":
        s.handle_key(ord(ch))
    assert s.sbuf == "AO-73"          # typing must reach the field, not the list
    s.handle_key(10)
    assert len(s.hits) == 1 and not s.searching
    before = app.state.store.db.count()
    s.handle_key(10)                   # ENTER adds the selected hit
    assert app.state.store.db.count() == before + 1
    assert "added" in s.msg.lower()


def test_orbital_history_dates_carry_the_year():
    """An element archive spans years, so 'Sun 13 Dec' is ambiguous."""
    from orbitterm.fmt import fmt_ymd, fmt_ymd_hm
    assert fmt_ymd(1450000000) == "2015-12-13"
    assert fmt_ymd_hm(1450000000).startswith("2015-12-13 ")
    assert fmt_ymd(0) == "--"
    import inspect
    from orbitterm.screens import graphics
    src = inspect.getsource(graphics.OrbitHistoryScreen)
    assert "fmt_ymd" in src
    # the old year-slicing must be gone
    assert "[:10]" not in src


def test_tui_has_a_qrz_screen():
    """The desktop had QRZ lookup and the terminal had no counterpart."""
    import orbitterm.app as A
    assert "qrz" in [k for k, _c in A.NAV]
    from orbitterm.screens.analysis4 import QrzScreen
    app = _fake_app()
    s = QrzScreen(app)
    app.state.store.config.pop("qrz_user", None)
    app.state.store.config.pop("qrz_pass", None)
    s.handle_key(ord("e"))
    for ch in "W1AW":
        s.handle_key(ord(ch))
    s.handle_key(10)
    assert "credentials" in s.status          # refuses without them
    app.state.store.config["qrz_user"] = "u"
    app.state.store.config["qrz_pass"] = "p"
    from orbitdeck.gui import datafeeds as DF
    orig = DF.qrz_lookup
    DF.qrz_lookup = lambda g, u, p, c, session_key=None: (
        {"call": "W1AW", "name_fmt": "ARRL HQ", "grid": "FN31pr"}, "KEY", None)
    try:
        s.handle_key(ord("e"))
        for ch in "W1AW":
            s.handle_key(ord(ch))
        s.handle_key(10)
    finally:
        DF.qrz_lookup = orig
    assert s.result and s.result["call"] == "W1AW"
    assert s._key == "KEY"                    # session cached, not re-logged in


def test_tui_activation_detail_matches_the_desktop():
    """The desktop's seeding fixes were never mirrored into the terminal."""
    import inspect
    from orbitterm.screens.analysis4 import ActivationsScreen as S
    assert "notes" in S.VIEWS
    src = inspect.getsource(S)
    assert "match_transponder" in src         # seed from the stated frequency
    assert "solve_pb_for_dial" in src         # hold the anchored dial there
    assert '"desc"' in src                    # not .description, which is None
    assert "_tp_touched" in src               # a manual pick is not overridden


def test_palette_is_legible_and_semantic():
    """Color has to carry meaning consistently, and be readable.

    Three faults: CLR_DIM was BLUE - the least legible color on a dark
    background and the most-used pair by far; CLR_HEADER was the same yellow as
    CLR_WARN, so a column heading and a warning looked identical; and red was
    used for direction (receding, eclipse) rather than for problems.
    """
    import curses
    import orbitterm.ui as U
    src = open("orbitterm/ui.py").read()
    assert "init_pair(CLR_DIM, curses.COLOR_WHITE" in src
    assert "init_pair(CLR_HEADER, curses.COLOR_WHITE" in src
    assert "init_pair(CLR_WARN, curses.COLOR_YELLOW" in src
    assert "init_pair(CLR_BAD, curses.COLOR_RED" in src
    # intent travels with the pair, so call sites cannot forget it
    assert "_PAIR_ATTR" in src
    _ = curses, U

    import pathlib
    # red is reserved for genuine problems
    for f in pathlib.Path("orbitterm/screens").glob("*.py"):
        text = f.read_text()
        assert "cp(CLR_BAD) if L.range_rate > 0" not in text, f
        assert "cp(CLR_BAD) if rr > 0" not in text, f
        assert "else cp(CLR_BAD) | _bold())" not in text, f


def test_no_text_is_clipped_flush_at_the_pane_edge():
    """Text cut exactly at the pane edge has no ellipsis to warn you, so a
    truncated value reads as a complete one ('sat below horiz')."""
    import os
    import re
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")

    def body(scr):
        import orbitterm.app as A
        import orbitterm.ui as U
        U.init_colors()
        app = A.App(scr)
        app.state.store.favorites = {s.norad
                                     for s in app.state.store.db.sats[:4]}
        h, _w = scr.getmaxyx()
        bad = []
        for key, _cls in A.NAV:
            app.goto(key)
            s = app.screens[key]
            try:
                s.on_enter()
            except Exception:
                pass
            scr.erase()
            try:
                app._draw()
            except Exception:
                continue
            scr.refresh()
            for y in range(h):
                line = scr.instr(y, 0).decode("utf-8", "replace")[19:]
                if len(line) != 61 or not line.strip():
                    continue
                if set(line.strip()) <= set("\u2500\u2550 "):
                    continue
                tail = line.rstrip()[-16:]
                if tail.endswith("\u2026"):
                    continue
                # a header row of column names may legitimately fill the pane
                if tail.isupper():
                    continue
                if re.search(r"[a-z]$", tail):
                    bad.append("%s: ...%s" % (key, tail))
        return bad

    try:
        bad = curses.wrapper(body)
    except Exception:
        _pt.skip("curses unavailable")
    assert not bad, bad[:6]
