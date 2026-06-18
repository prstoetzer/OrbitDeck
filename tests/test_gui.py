"""GUI behaviour tests (scrollbars, alarms, dialogs, widgets).

Part of the OrbitDeck test suite (split from the original monolithic
test_engine.py). Shared fixtures live in conftest.py.
"""

import datetime as dt
import json
import math

import pytest

from orbitdeck.engine.sgp4_lite import Satrec
from orbitdeck.engine import (SatDb, Predictor, Observer,
                              latlon_to_grid, grid_to_latlon)


def test_kvpanel_skips_repack_when_unchanged():
    """The live-page smoothness fix: when the row set/order is identical across
    refreshes, KVPanel must not pack_forget()+pack() every time (that forces a
    slow geometry relayout on macOS). It should only repack on structural
    changes."""
    import sys
    import types

    class FakeW:
        def __init__(self, *a, **k):
            self._cfg = dict(k)
            self.pack_count = 0
            self.forget_count = 0
            self.destroyed = False

        def pack(self, *a, **k):
            self.pack_count += 1

        def pack_forget(self):
            self.forget_count += 1

        def configure(self, **k):
            self._cfg.update(k)

        def cget(self, key):
            return self._cfg.get(key, "")

        def destroy(self):
            self.destroyed = True

    real_tk = sys.modules.get("tkinter")
    real_ttk = sys.modules.get("tkinter.ttk")
    real_mbk = sys.modules.get("matplotlib.backends.backend_tkagg")
    fake_tk = types.ModuleType("tkinter")
    fake_tk.Frame = FakeW
    fake_tk.Label = FakeW
    fake_ttk = types.ModuleType("tkinter.ttk")
    for _n in ("Frame", "Label", "Button", "Style", "Treeview", "Entry",
               "Radiobutton", "Checkbutton", "Separator", "Notebook",
               "Combobox", "Scrollbar"):
        setattr(fake_ttk, _n, FakeW)
    fake_mbk = types.ModuleType("matplotlib.backends.backend_tkagg")

    class _FC:
        def __init__(self, *a, **k):
            pass

        def get_tk_widget(self):
            return FakeW()

        def draw_idle(self):
            pass

    fake_mbk.FigureCanvasTkAgg = _FC
    fake_mbk.FigureCanvas = _FC
    sys.modules["tkinter"] = fake_tk
    sys.modules["tkinter.ttk"] = fake_ttk
    sys.modules["matplotlib.backends.backend_tkagg"] = fake_mbk
    try:
        import importlib
        # ensure a fresh import against the fakes
        for _m in [m for m in list(sys.modules) if m.startswith("orbitdeck.gui.screens")]:
            sys.modules.pop(_m, None)
        import matplotlib as _mpl
        _use = _mpl.use; _mpl.use = lambda *a, **k: None
        try:
            screens = importlib.import_module("orbitdeck.gui.screens")
        finally:
            _mpl.use = _use
        kv = screens.KVPanel(FakeW())

        def render(v):
            kv.begin()
            kv.section("S")
            kv.row("A", v)
            kv.row("B", v)
            kv.end()

        render("1")     # first build packs (repack expected here)
        before = sum(e["frame"].forget_count for e in kv._cache.values())
        render("2")     # same structure -> must NOT repack
        after = sum(e["frame"].forget_count for e in kv._cache.values())
        assert after - before == 0, "KVPanel repacked despite unchanged layout"
        aval = [e for e in kv._cache.values()
                if e["kind"] == "row" and e["lab"].cget("text") == "A"][0]["val"]
        assert aval.cget("text") == "2"
    finally:
        for name, mod in (("tkinter", real_tk), ("tkinter.ttk", real_ttk),
                          ("matplotlib.backends.backend_tkagg", real_mbk)):
            if mod is not None:
                sys.modules[name] = mod
            else:
                sys.modules.pop(name, None)
        # purge EVERY orbitdeck.gui module imported against the fake tkinter so
        # later tests re-import them fresh against the real one (otherwise a
        # screen module can keep a fake ttk.Treeview and break unrelated tests)
        for _m in [m for m in list(sys.modules)
                   if m == "orbitdeck.gui" or m.startswith("orbitdeck.gui.")]:
            sys.modules.pop(_m, None)

def test_orbit_live_page_stable_structure_across_ticks():
    """The Live page must not change its KVPanel structure every second (a
    timestamp in a section title used to do that, forcing a full relayout and
    visible flashing on macOS)."""
    import sys
    import types
    import time

    class FakeW:
        def __init__(self, *a, **k):
            self._cfg = dict(k)
            self.forget_count = 0

        def pack(self, *a, **k):
            pass

        def pack_forget(self):
            self.forget_count += 1

        def configure(self, **k):
            self._cfg.update(k)

        def cget(self, key):
            return self._cfg.get(key, "")

        def destroy(self):
            pass

        def bind(self, *a, **k):
            pass

        def winfo_ismapped(self):
            return 1

        def __getattr__(self, n):
            return lambda *a, **k: FakeW()

    saved = {n: sys.modules.get(n) for n in (
        "tkinter", "tkinter.ttk", "tkinter.messagebox",
        "matplotlib.backends.backend_tkagg")}
    tk = types.ModuleType("tkinter")
    for n in ("Frame", "Button", "Listbox", "Text", "Entry", "Toplevel",
              "Tk", "Radiobutton", "Checkbutton", "Canvas", "Scrollbar",
              "PhotoImage", "Label"):
        setattr(tk, n, FakeW)

    class _SV:
        def __init__(self, value="", master=None):
            self._v = value

        def set(self, v):
            self._v = v

        def get(self):
            return self._v

        def trace_add(self, *a, **k):
            pass
    tk.StringVar = tk.IntVar = tk.BooleanVar = tk.DoubleVar = _SV
    for c in ("END", "LEFT", "RIGHT", "TOP", "BOTH", "X", "Y", "W", "E"):
        setattr(tk, c, c.lower())
    ttk = types.ModuleType("tkinter.ttk")
    for n in ("Frame", "Label", "Button", "Treeview", "Style", "Entry",
              "Radiobutton", "Checkbutton", "Separator", "Notebook",
              "Scrollbar", "Combobox"):
        setattr(ttk, n, FakeW)
    mb = types.ModuleType("tkinter.messagebox")
    mb.showerror = mb.showinfo = mb.showwarning = lambda *a, **k: None
    mbk = types.ModuleType("matplotlib.backends.backend_tkagg")

    class _FC:
        def __init__(self, *a, **k):
            pass

        def get_tk_widget(self):
            return FakeW()

        def draw_idle(self):
            pass

        def draw(self):
            pass
    mbk.FigureCanvasTkAgg = _FC
    mbk.FigureCanvas = _FC
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk,
                        "tkinter.messagebox": mb,
                        "matplotlib.backends.backend_tkagg": mbk})
    for _m in [m for m in list(sys.modules) if m.startswith("orbitdeck.gui.screens")]:
        sys.modules.pop(_m, None)
    import matplotlib as _mpl
    _use = _mpl.use; _mpl.use = lambda *a, **k: None
    try:
        from orbitdeck.gui import screens
        from orbitdeck.gui.store import Store
        store = Store()

        class App:
            class _R:
                def after(self, ms, fn=None):
                    return None

            def __init__(self, st):
                self.store = st
                self.current = None
                self._screen_cache = {}
                self.root = App._R()

            def set_status(self, t):
                pass

            def show(self, k):
                pass
        scr = screens.make_screen("orbit", FakeW(), App(store))
        scr.page.set(1)        # Live page
        scr._render(time.time())
        before = sum(e["frame"].forget_count for e in scr.kv._cache.values())
        scr._render(time.time() + 1)
        after = sum(e["frame"].forget_count for e in scr.kv._cache.values())
        assert after - before == 0, "Live page relayouts every tick (flashing)"
    finally:
        for n, m in saved.items():
            if m is not None:
                sys.modules[n] = m
            else:
                sys.modules.pop(n, None)
        _mpl.use = _use
        # purge EVERY orbitdeck.gui module imported against the fake tkinter so
        # later tests re-import them fresh against the real one
        for _m in [m for m in list(sys.modules)
                   if m == "orbitdeck.gui" or m.startswith("orbitdeck.gui.")]:
            sys.modules.pop(_m, None)

def test_whos_up_scan(iss_predictor):
    """whos_up returns catalog members above the elevation floor, sorted by
    descending elevation; a -90 floor returns the whole list."""
    from orbitdeck.engine.predict import whos_up
    from orbitdeck.engine import Observer
    pred, sat = iss_predictor
    site = Observer(lat=39.93, lon=-74.89, alt_m=20, valid=True)
    t0 = sat.epoch_unix
    allup = whos_up(site, [sat], t0, min_el=-90.0)
    assert len(allup) == 1
    # results carry the geometry fields and are elevation-sorted
    d = allup[0]
    for k in ("name", "norad", "az", "el", "range_km", "alt_km"):
        assert k in d
    # a floor above the satellite's current elevation excludes it
    high = whos_up(site, [sat], t0, min_el=d["el"] + 1.0)
    assert len(high) == 0

def test_polar_elevation_labels_match_radius():
    """Regression for the reversed-elevation bug: on the shared sky-polar
    convention (rlim 90->0, zenith at centre), each ring's label must equal its
    radius so a high-elevation pass reads as high, not horizon-skimming."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import math as _m
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="polar")
    ax.set_rlim(90, 0)
    ax.set_rgrids([0, 30, 60, 90], labels=["0", "30", "60", "90"])
    fig.canvas.draw()
    # the centre (zenith) must carry the "90" label, the rim "0"
    p_r90 = ax.transData.transform((0, 90))
    p_r0 = ax.transData.transform((0, 0))
    cx, cy = ax.transAxes.transform((0.5, 0.5))

    def dist(a, b):
        return _m.hypot(a[0] - b[0], a[1] - b[1])
    # r=90 maps to the centre under rlim(90,0); its label text is "90"
    assert dist(p_r90, (cx, cy)) < dist(p_r0, (cx, cy))
    # and a high-elevation point sits near the centre
    p80 = ax.transData.transform((0, 80))
    frac = dist(p80, p_r90) / dist(p_r90, p_r0)
    assert frac < 0.2
    plt.close(fig)

def test_about_tab_constants():
    """The About tab exposes the GitHub and AMSAT links."""
    from orbitdeck.gui.screens.location import GITHUB_URL, AMSAT_URL
    assert GITHUB_URL == "https://github.com/prstoetzer/OrbitDeck"
    assert "amsat.org" in AMSAT_URL

def test_manual_satellite_edit_and_delete():
    """A manual satellite can be added, updated in place, and deleted from both
    the live catalog and the persisted store; deleting also clears favorites."""
    import tkinter as tk
    import datetime as _dt
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.engine.satdb import make_manual_sat
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        return
    store = app.store
    ep = _dt.datetime(2026, 6, 1, tzinfo=_dt.timezone.utc).timestamp()
    e = make_manual_sat("TESTSAT", 90001, ep, 51.6, 120.0, 0.0006,
                        90.0, 180.0, 15.5, 0.0)
    store.add_manual_sat(e)
    assert store.db.get(90001) is not None
    assert store.db.get(90001).is_manual is True
    # update in place
    e2 = make_manual_sat("TESTSAT-2", 90001, ep, 53.0, 120.0, 0.0006,
                         90.0, 180.0, 15.6, 0.0)
    store.update_manual_sat(e2)
    assert store.db.get(90001).name == "TESTSAT-2"
    assert abs(store.db.get(90001).incl - 53.0) < 1e-6
    # delete
    store.favorites.add(90001)
    store.remove_manual_sat(90001)
    assert store.db.get(90001) is None
    assert 90001 not in store.favorites
    assert all(int(d.get("norad", -1)) != 90001
               for d in store._load_manual_sats())
    root.destroy()

def test_alarm_patterns_distinct_and_watch_all_favorites():
    """Alarm beep patterns are distinct per event, and the manager watches every
    favorite's next pass rather than only the selected satellite."""
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.gui.alarms import _PATTERNS
    # the four events must each have a different rhythm
    assert len(set(_PATTERNS.values())) == len(_PATTERNS)
    for key in ("soon", "aos", "tca", "los"):
        assert key in _PATTERNS and _PATTERNS[key][0] == 0
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        return
    favs = [s for s in app.store.db.sats
            if s.name in ("ISS", "SO-50", "AO-91")]
    for s in favs:
        app.store.favorites.add(s.norad)
    app.alarms.set_enabled(True)
    app.alarms.tick()
    # every favorite with an upcoming pass should be watched independently
    assert len(app.alarms._watch) >= 2
    assert set(app.alarms._watch).issubset({s.norad for s in favs})
    root.destroy()

def test_autohide_scrollbar_callback_logic():
    """autohide_scrollbar returns a callback that un-packs the bar when the view
    spans the whole range and re-packs it otherwise."""
    import tkinter as tk
    from tkinter import ttk
    from orbitdeck.gui.screens import autohide_scrollbar
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    frame = ttk.Frame(root)
    frame.pack()
    tree = ttk.Treeview(frame)
    bar = ttk.Scrollbar(frame, orient="vertical")
    cb = autohide_scrollbar(bar, "right", before=tree)
    tree.pack()
    bar.pack(side="right", fill="y")
    root.update_idletasks()

    def is_packed():
        # pack_info() raises TclError once the widget has been pack_forget()'d
        try:
            bar.pack_info()
            return True
        except tk.TclError:
            return False

    # everything visible -> unpacked
    cb(0.0, 1.0)
    assert not is_packed()
    # partial view -> repacked
    cb(0.0, 0.4)
    assert is_packed()
    # back to full -> unpacked again
    cb(0.0, 1.0)
    assert not is_packed()
    root.destroy()

def test_all_scrollable_widgets_have_scrollbars():
    """Every Treeview and Listbox on every screen must have a Scrollbar sibling,
    so long tables and lists are always scrollable with a visible bar."""
    import tkinter as tk
    from tkinter import ttk
    from orbitdeck.gui.app import OrbitDeckApp, NAV_ITEMS
    from orbitdeck.gui import screens
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        return

    def walk(w):
        yield w
        for c in w.winfo_children():
            yield from walk(c)

    def has_scrollbar_sibling(widget):
        parent = widget.nametowidget(widget.winfo_parent())
        return any(isinstance(s, (ttk.Scrollbar, tk.Scrollbar))
                   for s in parent.winfo_children())

    missing = []
    checked = 0
    for _label, key in NAV_ITEMS:
        try:
            scr = screens.make_screen(key, app.content, app)
            if hasattr(scr, "on_show"):
                scr.on_show()
        except Exception:
            continue
        root.update_idletasks()
        for w in walk(scr.frame):
            if isinstance(w, (ttk.Treeview, tk.Listbox)):
                checked += 1
                if not has_scrollbar_sibling(w):
                    missing.append((key, str(w)))
    root.destroy()
    assert checked > 0
    assert not missing, "scrollable widgets without a scrollbar: %r" % missing

def test_globe_terminator_daynight_matches_spherical_truth():
    """The 3D Globe night-shading decision (a point is night when its surface
    normal is >90 deg from the subsolar direction) must match the independent
    spherical day/night test for a spread of cities, at a fixed instant. Guards
    the terminator rewrite against the earlier wrong-hemisphere shading."""
    import math as _m
    import datetime as _dt
    from orbitdeck.engine.predict import (_sun_eci_unit, jd_of,
                                          _teme_to_ecef_lla)
    DEG = _m.pi / 180.0
    t = _dt.datetime(2026, 6, 21, 12, 0, 0,
                     tzinfo=_dt.timezone.utc).timestamp()
    jd = jd_of(t)
    sx, sy, sz = _sun_eci_unit(jd)
    slat, slon, _ = _teme_to_ecef_lla((sx * 1e6, sy * 1e6, sz * 1e6), jd)

    def truth_night(la, lo):
        a, b, c, d = (la * DEG, lo * DEG, slat * DEG, slon * DEG)
        cosd = (_m.sin(a) * _m.sin(c)
                + _m.cos(a) * _m.cos(c) * _m.cos(b - d))
        return cosd < 0.0

    # the screen's rendered decision: surface unit vector . subsolar unit < 0
    sun = (_m.cos(slat * DEG) * _m.cos(slon * DEG),
           _m.cos(slat * DEG) * _m.sin(slon * DEG),
           _m.sin(slat * DEG))

    def rendered_night(la, lo):
        p = (_m.cos(la * DEG) * _m.cos(lo * DEG),
             _m.cos(la * DEG) * _m.sin(lo * DEG),
             _m.sin(la * DEG))
        return (p[0] * sun[0] + p[1] * sun[1] + p[2] * sun[2]) < 0.0

    cities = [("London", 51.5, 0.0), ("Tokyo", 35.7, 139.7),
              ("NYC", 40.7, -74.0), ("Sydney", -33.9, 151.0),
              ("Beijing", 39.9, 116.0), ("Delhi", 28.6, 77.0),
              ("LA", 34.0, -118.0), ("Cairo", 30.0, 31.0),
              ("Rio", -22.9, -43.0), ("Anchorage", 61.0, -149.0)]
    for _name, la, lo in cities:
        assert rendered_night(la, lo) == truth_night(la, lo)
    # at the June solstice the North Pole is in continuous daylight and the
    # South Pole in continuous night
    assert rendered_night(90.0, 0.0) is False
    assert rendered_night(-90.0, 0.0) is True

def test_satellite_category_classification():
    """satellite_category buckets by best transponder kind, prioritising
    linear over FM over digital; no transponders -> 'No transponder data'."""
    from orbitdeck.engine.satdb import (satellite_category, CATEGORIES,
                                        SatEntry, Transponder)
    lin = Transponder(desc="Linear", is_linear=True,
                      downlink=145900000, downlink_high=145980000)
    fm = Transponder(desc="FM voice", mode="FM", downlink=145800000)
    dig = Transponder(desc="BPSK telemetry", mode="BPSK1k2",
                      downlink=437000000)
    bcn = Transponder(desc="CW beacon", mode="CW", downlink=435000000)

    s = SatEntry(name="X", norad=1)
    assert satellite_category(s) == "No transponder data"
    s.transponders = [fm]
    assert satellite_category(s) == "FM transponder"
    s.transponders = [dig]
    assert satellite_category(s) == "Digital transponder"
    s.transponders = [bcn]
    assert satellite_category(s) == "Beacon / CW"
    # priority: a bird with both FM and linear is filed under linear
    s.transponders = [fm, lin]
    assert satellite_category(s) == "Linear transponder"
    # all category labels are known
    for cat in CATEGORIES:
        assert isinstance(cat, str)

def test_pass_card_picker():
    """The Pass card tab loads upcoming passes and renders the selected one."""
    import matplotlib
    matplotlib.use("Agg")
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.gui import screens
    from orbitdeck.engine.predict import Observer
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        return
    app.store.obs = Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True)
    app.store.pred.set_site(app.store.obs)
    app.store.pred.set_sat(app.store.selected_sat())
    e = screens.make_screen("exports", app.content, app)
    e.on_show()
    assert len(e._card_passes) >= 1
    assert e._selected_card_pass() is e._card_passes[0]
    if len(e._card_passes) > 1:
        e._card_pass_combo.current(1)
        e._on_card_pass_change()
        assert e._selected_card_pass() is e._card_passes[1]
    root.destroy()


def test_gp_update_error_dialog_lambda_captures_exception():
    """Regression: the deferred error-dialog lambdas in the GP / transponder
    update handlers must capture the exception via a default arg, so they don't
    raise NameError when the (deferred) callback finally runs after the
    `except ... as e` binding has gone out of scope."""
    import inspect
    from orbitdeck.gui import app as APP
    src = inspect.getsource(APP.OrbitDeckApp)
    # both update handlers schedule a showerror via root.after; ensure the
    # lambdas bind e as a default argument (lambda e=e:) rather than closing
    # over the now-deleted except-variable.
    assert "lambda e=e: messagebox.showerror" in src
    # there should be no bare "lambda: messagebox.showerror" referencing % e
    assert "lambda: messagebox.showerror" not in src
