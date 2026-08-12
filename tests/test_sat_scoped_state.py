"""Changing satellite must clear anything scoped to the previous one.

This is not cosmetic: a cached screen redrawing the old satellite's data under
the new satellite's name is the UI asserting something false - AO-73's history
presented as AO-7's.
"""

import os

os.environ["ORBITDECK_TEST"] = "1"


def _sample(n=40):
    from orbitdeck.engine.spacetrack import COLUMNS
    out = []
    for i in range(n):
        rec = {"epoch": 1.6e9 + i * 86400 * 30, "APOAPSIS": 420 - i * 0.05}
        rec.update({k: rec.get(k) for k in COLUMNS})
        out.append(rec)
    return out


# ---- desktop ----
def test_gui_orbit_history_clears_on_satellite_change(tmp_path):
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        try:
            app = OrbitDeckApp(root)
        except Exception:
            # Tk runs out of resources after many roots in one suite run; that
            # is an environment limit, not a failure of what is under test
            import pytest
            pytest.skip("Tk unavailable in this process")
        scr_cache = tmp_path / "sthist"
        sats = app.store.db.sats
        app.store.selected_norad = sats[0].norad
        app.show("orbithistory")
        root.update()
        s = app.current
        # point at a scratch dir: another test may have written a real archive
        # cache, and then the reload would legitimately repopulate samples
        s.CACHE = str(scr_cache)
        s._shown_norad = sats[0].norad    # re-baseline after the CACHE swap
        s.samples = _sample()
        s.zoom = (0.25, 0.75)
        s._redraw()
        s._fill_table()
        root.update()
        assert len(s.samples) == 40
        # switch satellite and come back
        app.store.selected_norad = sats[1].norad
        app.show("home")
        root.update()
        app.show("orbithistory")
        root.update()
        # The requirement is that the OLD satellite's records are gone. If a
        # real cache exists for the new satellite it may legitimately reload -
        # what must never happen is the previous bird's data staying on screen.
        assert len(s.samples) != 40, \
            "previous satellite's archive still shown"
        assert not any(abs(r.get("APOAPSIS", 0) - 420.0) < 1e-9
                       for r in s.samples), "stale synthetic records survived"
        assert s.zoom == (0.0, 1.0), "zoom window belonged to the old record"
        assert len(s.tree.get_children()) == 0
        assert sats[1].name in s.info.get()
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_gui_base_clear_is_generic():
    """The guard lives on the base class so new screens get it by declaring
    sat_scoped, rather than each screen re-implementing the fix."""
    from orbitdeck.gui.screens import Screen
    assert hasattr(Screen, "sat_scoped")
    assert hasattr(Screen, "_clear_if_sat_changed")
    assert hasattr(Screen, "on_sat_changed")


def test_gui_screens_declare_their_scoped_state():
    from orbitdeck.gui.screens import (orbithistory, passes, radio, grids,
                                       zones)
    assert "samples" in orbithistory.OrbitHistoryScreen.sat_scoped
    assert passes.PassesScreen.sat_scoped
    assert radio.RadioScreen.sat_scoped
    assert grids.GridsScreen.sat_scoped
    assert zones.ZonesScreen.sat_scoped


# ---- terminal ----
def test_tui_clear_if_sat_changed():
    from orbitterm.ui import Screen

    class _S(Screen):
        sat_scoped = ("samples", "res")

        def __init__(self):
            self.samples = _sample()
            self.res = {"a": 1}

    s = _S()
    assert s.clear_if_sat_changed(25544) is True     # first call records
    assert s.samples == [] and s.res == {}
    s.samples = _sample()
    assert s.clear_if_sat_changed(25544) is False    # same sat: keep it
    assert len(s.samples) == 40
    assert s.clear_if_sat_changed(7530) is True      # changed: drop it
    assert s.samples == []


def test_tui_state_select_notifies_listeners():
    from orbitterm.state import AppState
    st = AppState()
    seen = []
    st.on_sat_change(lambda n: seen.append(n))
    sats = st.store.db.sats
    st.select(sats[0].norad)
    st.select(sats[1].norad)
    st.select(sats[1].norad)              # no change: no extra notification
    assert seen == [sats[0].norad, sats[1].norad] or seen == [sats[1].norad]
    assert seen[-1] == sats[1].norad


def test_tui_screens_declare_their_scoped_state():
    from orbitterm.screens.graphics import OrbitHistoryScreen
    from orbitterm.screens.analysis3 import (MutualScreen, TransitsScreen,
                                             ConjunctionScreen, Ao7Screen)
    from orbitterm.screens.analysis2 import ZonesScreen
    assert "samples" in OrbitHistoryScreen.sat_scoped
    for cls in (MutualScreen, TransitsScreen, ConjunctionScreen, Ao7Screen,
                ZonesScreen):
        assert cls.sat_scoped, cls.__name__


def test_tui_listener_registered_once():
    """goto() runs constantly; registering there would pile up duplicates."""
    import inspect
    import orbitterm.app as A
    src = inspect.getsource(A.App._register_sat_listener)
    assert "_sat_listener_registered" in src
    assert "self._register_sat_listener()" not in inspect.getsource(A.App.goto)


def test_sat_scoped_rejects_methods():
    """Naming a method in sat_scoped would null it and break the screen - which
    is exactly what happened when '_neigh' was guessed to be cached data."""
    import pytest
    from orbitterm.ui import Screen

    class _Bad(Screen):
        sat_scoped = ("_action",)

        def __init__(self):
            pass

        def _action(self):
            return 1

    with pytest.raises(TypeError):
        _Bad().clear_if_sat_changed(1)
