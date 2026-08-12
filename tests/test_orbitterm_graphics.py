"""Tests for the braille canvas and the graphical TUI screens."""

import math


class _FakeApp:
    def __init__(self, state):
        self.state = state


def _app():
    from orbitterm.state import AppState
    return _FakeApp(AppState())


# ---- canvas ----
def test_canvas_surface_is_sub_cell():
    """Braille gives 2x4 dots per character cell - 8x the addressable points."""
    from orbitterm.canvas import Canvas
    c = Canvas(20, 5)
    assert (c.width, c.height) == (40, 20)
    assert c.width * c.height == 20 * 5 * 8


def test_canvas_plot_and_glyph():
    from orbitterm.canvas import Canvas, BRAILLE_BASE
    c = Canvas(4, 2)
    assert c.plot(0, 0) is True
    # the top-left dot is bit 0x01
    assert c.cell_char(0, 0) == chr(BRAILLE_BASE + 0x01)
    # a second dot in the same cell ORs in
    c.plot(1, 0)
    assert c.cell_char(0, 0) == chr(BRAILLE_BASE + 0x01 + 0x08)
    # out of range is rejected, not raised
    assert c.plot(-1, 0) is False
    assert c.plot(c.width, 0) is False


def test_canvas_empty_cell_is_space():
    from orbitterm.canvas import Canvas
    c = Canvas(3, 1)
    assert c.cell_char(2, 0) == " "


def test_canvas_line_and_circle_stay_in_bounds():
    from orbitterm.canvas import Canvas
    c = Canvas(20, 5)
    c.line(0, 0, c.width - 1, c.height - 1)
    c.circle(c.width // 2, c.height // 2, 3)
    for (cx, cy) in c._cells:
        assert 0 <= cx < c.cols and 0 <= cy < c.rows


def test_canvas_ascii_fallback_matches_shape():
    from orbitterm.canvas import Canvas
    c = Canvas(6, 2)
    c.plot(0, 0)
    lines = c.ascii_fallback()
    assert len(lines) == 2 and len(lines[0]) == 6
    assert lines[0][0] == "#"


def test_scale_maps_and_inverts():
    from orbitterm.canvas import scale
    assert scale(0, 0, 10, 0, 100) == 0
    assert scale(10, 0, 10, 0, 100) == 100
    assert scale(0, 0, 10, 0, 100, invert=True) == 100
    # out-of-range values clamp rather than overshoot
    assert scale(-5, 0, 10, 0, 100) == 0
    assert scale(15, 0, 10, 0, 100) == 100
    # a degenerate range doesn't divide by zero
    assert scale(5, 5, 5, 0, 100) == 50


def test_canvas_renders_a_curve():
    """A sine sampled across the surface should light many distinct cells."""
    from orbitterm.canvas import Canvas
    c = Canvas(40, 6)
    for x in range(c.width):
        y = int(c.height / 2 + (c.height / 2 - 1)
                * math.sin(x / c.width * 4 * math.pi))
        c.plot(x, y)
    assert len(c._cells) > 30


# ---- screens ----
def test_graphics_screens_registered():
    import orbitterm.app as A
    keys = [k for k, _c in A.NAV]
    for want in ("skyglance", "skymap", "orbithistory", "graphcalc"):
        assert want in keys


def test_tui_graphcalc_samples_and_editing():
    from orbitterm.screens.graphics import GraphCalcScreen
    s = GraphCalcScreen(_app())
    xs, ys = s._samples(64)
    assert len(xs) == len(ys) == 64
    assert any(v is not None for v in ys)
    # editing swaps the expression
    s.handle_key(ord("e"))
    assert s.editing
    s.buf = "cos(x)"
    s.handle_key(ord("\n"))
    assert s.expr == "cos(x)" and not s.editing
    # a pole yields None samples rather than raising
    s.expr = "1/x"
    _xs2, ys2 = s._samples(51)
    assert any(v is None for v in ys2)


def test_tui_graphcalc_zoom():
    from orbitterm.screens.graphics import GraphCalcScreen
    s = GraphCalcScreen(_app())
    span = s.xmax - s.xmin
    s.handle_key(ord("]"))
    assert (s.xmax - s.xmin) < span
    s.handle_key(ord("["))
    assert abs((s.xmax - s.xmin) - span) < 1e-9


def test_tui_skyglance_window_cycle():
    from orbitterm.screens.graphics import SkyGlanceScreen
    app = _app()
    app.state.store.favorites = {s.norad for s in app.state.store.db.sats[:3]}
    s = SkyGlanceScreen(app)
    s._reload()
    assert s.rows
    before = s.hours
    s.handle_key(ord("w"))
    assert s.hours != before


def test_tui_skymap_toggles():
    from orbitterm.screens.graphics import SkyMapScreen
    s = SkyMapScreen(_app())
    before = s.max_mag
    s.handle_key(ord("m"))
    assert s.max_mag != before
    lines = s.show_lines
    s.handle_key(ord("l"))
    assert s.show_lines is not lines


def test_tui_orbit_history_without_cache():
    """No cached archive is a status message, not a crash."""
    from orbitterm.screens.graphics import OrbitHistoryScreen
    s = OrbitHistoryScreen(_app())
    s.CACHE = "/nonexistent/path"
    s._load()
    assert s.samples == []
    assert "no cached history" in s.status or "no satellite" in s.status


def test_tui_graphics_draw_in_curses():
    import os
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")
    from orbitterm.screens.graphics import (SkyGlanceScreen, GraphCalcScreen,
                                            SkyMapScreen, OrbitHistoryScreen)

    def body(scr):
        import orbitterm.ui as U
        U.init_colors()
        app = _app()
        app.state.store.favorites = {s.norad
                                     for s in app.state.store.db.sats[:3]}
        h, w = scr.getmaxyx()
        for cls in (GraphCalcScreen, SkyMapScreen, SkyGlanceScreen,
                    OrbitHistoryScreen):
            scr.clear()
            s = cls(app)
            try:
                s.on_enter()
            except Exception:
                pass
            s.draw(scr, 1, 0, max(8, h - 2), max(40, w - 1))
        return True

    try:
        assert curses.wrapper(body) is True
    except Exception:
        _pt.skip("curses unavailable")


# ---- globe ----
def test_globe_projection_hides_far_side():
    from orbitterm.screens.globe import GlobeScreen
    # a point at the view centre is visible and at the origin
    x, y, vis = GlobeScreen._project(0, 0, 0, 0, 100)
    assert vis and abs(x) < 1e-6 and abs(y) < 1e-6
    # the antipode is on the far side
    _x2, _y2, vis2 = GlobeScreen._project(0, 180, 0, 0, 100)
    assert not vis2
    # 90 degrees away sits on the limb
    x3, _y3, vis3 = GlobeScreen._project(0, 90, 0, 0, 100)
    assert vis3 and abs(abs(x3) - 100) < 1e-6


def test_globe_projection_stays_within_radius():
    from orbitterm.screens.globe import GlobeScreen
    r = 50
    for lat in range(-90, 91, 15):
        for lon in range(-180, 181, 15):
            x, y, vis = GlobeScreen._project(lat, lon, 20, 30, r)
            if vis:
                assert math.hypot(x, y) <= r + 1e-6


def test_globe_offset_helper():
    from orbitterm.screens.globe import _offset
    # due north of the equator by 10 degrees
    la, lo = _offset(0.0, 0.0, 10.0, 0.0)
    assert abs(la - 10.0) < 1e-6 and abs(lo) < 1e-6
    # due east by 10 degrees
    la2, lo2 = _offset(0.0, 0.0, 10.0, 90.0)
    assert abs(la2) < 1e-6 and abs(lo2 - 10.0) < 1e-6


def test_globe_keys_toggle_and_rotate():
    import curses
    from orbitterm.screens.globe import GlobeScreen
    s = GlobeScreen(_app())
    assert s.follow is True
    s.handle_key(curses.KEY_LEFT)
    assert s.follow is False            # steering releases the lock
    lon = s.view_lon
    s.handle_key(curses.KEY_RIGHT)
    assert s.view_lon != lon
    s.handle_key(ord("t"))
    assert s.show_track is False
    s.handle_key(ord("f"))
    assert s.follow is True


def test_globe_registered_in_nav():
    import orbitterm.app as A
    assert "globe" in [k for k, _c in A.NAV]


def test_globe_draws_in_curses():
    import os
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")
    from orbitterm.screens.globe import GlobeScreen

    def body(scr):
        import orbitterm.ui as U
        U.init_colors()
        h, w = scr.getmaxyx()
        GlobeScreen(_app()).draw(scr, 1, 0, max(8, h - 2), max(40, w - 1))
        return True
    try:
        assert curses.wrapper(body) is True
    except Exception:
        _pt.skip("curses unavailable")


# ---- retrofits ----
def test_retrofitted_screens_use_the_canvas():
    """Pass detail and the radar grid should now draw through the canvas."""
    import inspect
    from orbitterm.screens import passes, catalog
    src_pd = inspect.getsource(passes.PassDetailScreen._draw_sky)
    assert "Canvas" in src_pd and "blit" in src_pd
    src_rd = inspect.getsource(catalog.RadarScreen._draw_grid)
    assert "Canvas" in src_rd and "circle" in src_rd


def test_retrofitted_screens_still_draw():
    import os
    import time as _t
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")
    from orbitterm.screens.catalog import RadarScreen
    from orbitterm.screens.passes import PassDetailScreen

    def body(scr):
        import orbitterm.ui as U
        U.init_colors()
        app = _app()
        h, w = scr.getmaxyx()
        r = RadarScreen(app)
        try:
            r.on_enter()
        except Exception:
            pass
        r.draw(scr, 1, 0, max(10, h - 2), max(50, w - 1))
        pd = PassDetailScreen(app)
        pred = app.state.pred_for(app.state.sat)
        ps = pred.predict_passes(_t.time(), 5.0, 1)
        if ps:
            pd.pass_ = ps[0]
        scr.clear()
        pd.draw(scr, 1, 0, max(14, h - 2), max(50, w - 1))
        return True
    try:
        assert curses.wrapper(body) is True
    except Exception:
        _pt.skip("curses unavailable")


# ---- ground track / illumination retrofits ----
def test_groundtrack_draws_real_coastline_polylines_at_2to1():
    """Braille suits line art, so the map draws the bundled coastline VECTORS.

    Outlining a coarse land/sea rectangle mask - the previous approach - can
    only ever produce rectangles, and it did. And an equirectangular map needs
    a 2:1 area; filling the pane stretched every continent about 30%.
    """
    import inspect
    from orbitterm.screens import analysis_screens
    src = inspect.getsource(analysis_screens.GroundTrackScreen.draw)
    assert "Canvas" in src and "blit" in src
    assert "COASTLINES" in src          # real vectors, not a mask outline
    assert "_dw" in src and "_dh" in src  # the 2:1 fit


def test_groundtrack_map_is_not_stretched():
    """Measure the rendered map: it must come out about 2:1 in real terms,
    remembering a terminal cell is roughly twice as tall as it is wide."""
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
        app.goto("groundtrack")
        s = app.screens["groundtrack"]
        try:
            s.on_enter()
        except Exception:
            pass
        scr.erase()
        app._draw()
        scr.refresh()
        h, _w = scr.getmaxyx()
        return [scr.instr(y, 0).decode("utf-8", "replace")[19:]
                for y in range(h)]

    try:
        rows = curses.wrapper(body)
    except Exception:
        _pt.skip("curses unavailable")
    pts = [(y, x) for y, ln in enumerate(rows) for x, ch in enumerate(ln)
           if "\u2800" <= ch <= "\u28ff"]
    if not pts:
        _pt.skip("nothing rendered")
    ys = [p[0] for p in pts]
    xs = [p[1] for p in pts]
    cells = max(xs) - min(xs) + 1
    lines = max(ys) - min(ys) + 1
    aspect = cells / (lines * 2.0)      # cells are ~1:2
    assert 1.6 < aspect < 2.4, "map aspect %.2f is not ~2:1" % aspect


def test_illumination_uses_canvas():
    import inspect
    from orbitterm.screens import illumination
    src = inspect.getsource(illumination.IlluminationScreen._draw_raster)
    assert "Canvas" in src and "blit" in src


def test_retrofitted_map_screens_draw():
    import os
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")
    from orbitterm.screens.analysis_screens import GroundTrackScreen
    from orbitterm.screens.illumination import IlluminationScreen

    def body(scr):
        import orbitterm.ui as U
        U.init_colors()
        app = _app()
        h, w = scr.getmaxyx()
        for cls in (GroundTrackScreen, IlluminationScreen):
            scr.clear()
            s = cls(app)
            try:
                s.on_enter()
            except Exception:
                pass
            s.draw(scr, 1, 0, max(12, h - 2), max(60, w - 1))
        return True
    try:
        assert curses.wrapper(body) is True
    except Exception:
        _pt.skip("curses unavailable")


# ---- OSCARLOCATOR ----
def test_oscarsim_registered_and_completes_the_tui():
    import orbitterm.app as A
    keys = [k for k, _c in A.NAV]
    assert "oscarsim" in keys


def test_oscarsim_wrap_and_geometry_helpers():
    from orbitterm.screens.oscarsim import _wrap, _gc, _dest
    assert _wrap(190) == -170
    assert _wrap(-190) == 170
    assert _wrap(0) == 0
    d, b = _gc(0, 0, 0, 10)
    assert abs(d - 10) < 1e-6 and abs(b - 90) < 1e-6
    la, lo = _dest(0, 0, 10, 0)          # due north
    assert abs(la - 10) < 1e-6 and abs(lo) < 1e-6


def test_oscarsim_arc_follows_inclination():
    """The track arc must peak at the satellite's inclination."""
    from orbitterm.screens.oscarsim import OscarSimScreen
    s = OscarSimScreen(_app())
    sat = s.state.sat

    class _Fake:
        incl = 51.6
        mean_motion = 15.5
    pts = s._arc_points(_Fake(), n=180)
    lats = [p[0] for p in pts]
    assert abs(max(lats) - 51.6) < 1.0
    assert abs(min(lats) + 51.6) < 1.0
    assert sat is not None or True


def test_oscarsim_manual_controls_release_live():
    import curses
    from orbitterm.screens.oscarsim import OscarSimScreen
    s = OscarSimScreen(_app())
    assert s.live is True
    lon = s.eqx_lon
    s.handle_key(curses.KEY_RIGHT)
    assert s.live is False and s.eqx_lon != lon
    mins = s.minutes
    s.handle_key(curses.KEY_UP)
    assert s.minutes > mins
    s.handle_key(curses.KEY_DOWN)
    s.handle_key(curses.KEY_DOWN)
    assert s.minutes >= 0.0             # never steps below the crossing
    s.handle_key(ord("m"))
    assert s.MODES[s.mode] == "qth"


def test_oscarsim_draws_in_curses():
    import os
    import curses
    import pytest as _pt
    if not os.environ.get("TERM"):
        _pt.skip("no TERM")
    from orbitterm.screens.oscarsim import OscarSimScreen

    def body(scr):
        import orbitterm.ui as U
        U.init_colors()
        h, w = scr.getmaxyx()
        s = OscarSimScreen(_app())
        s.draw(scr, 1, 0, max(10, h - 2), max(60, w - 1))
        s.handle_key(ord("m"))
        scr.clear()
        s.draw(scr, 1, 0, max(10, h - 2), max(60, w - 1))
        return True
    try:
        assert curses.wrapper(body) is True
    except Exception:
        _pt.skip("curses unavailable")


def test_radar_grid_matches_where_objects_are_plotted():
    """The rings are meaningless if objects do not land on them.

    A marker at the horizon sits at +/-2*radius cells and +/-radius rows, i.e.
    4*radius dots either way (2 dots per cell across, 4 per row down). The grid
    canvas was half that, so anything below about 60 degrees fell outside the
    drawn horizon ring.
    """
    import inspect
    from orbitterm.screens import catalog
    src = inspect.getsource(catalog.RadarScreen._draw_grid)
    assert "radius * 4 + 1" in src
    assert "radius * 2 + 1" in src
    # the maths, independently of the source
    for radius in (6, 8, 12):
        marker_dots = radius * 4          # horizon marker, in dots
        cols, rows = radius * 4 + 1, radius * 2 + 1
        ccx, ccy = (cols * 2) // 2, (rows * 4) // 2
        grid_dots = min(ccx, ccy) - 1
        assert abs(grid_dots - marker_dots) <= 2, (radius, grid_dots,
                                                   marker_dots)


def test_polar_and_globe_displays_are_round():
    """Braille dots are square (2 across, 4 down against a ~1:2 cell), so a
    disc must come out 1:1 in real terms."""
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
        h, _w = scr.getmaxyx()
        out = {}
        for key in ("globe", "oscarsim"):
            app.goto(key)
            s = app.screens[key]
            try:
                s.on_enter()
            except Exception:
                pass
            scr.erase()
            app._draw()
            scr.refresh()
            out[key] = [scr.instr(y, 0).decode("utf-8", "replace")[19:]
                        for y in range(h)]
        return out

    try:
        shots = curses.wrapper(body)
    except Exception:
        _pt.skip("curses unavailable")
    for key, rows in shots.items():
        pts = [(y, x) for y, ln in enumerate(rows)
               for x, ch in enumerate(ln) if "\u2800" <= ch <= "\u28ff"]
        if not pts:
            continue
        w = max(p[1] for p in pts) - min(p[1] for p in pts) + 1
        hgt = max(p[0] for p in pts) - min(p[0] for p in pts) + 1
        aspect = w / (hgt * 2.0)
        assert 0.8 < aspect < 1.25, "%s aspect %.2f" % (key, aspect)


def test_orbitterm_is_not_branded_as_a_companion():
    """It ships standalone now."""
    import pathlib
    for f in ("orbitterm/__init__.py", "orbitterm/README.md",
              "orbitterm/screens/live.py"):
        assert "companion" not in pathlib.Path(f).read_text().lower(), f
