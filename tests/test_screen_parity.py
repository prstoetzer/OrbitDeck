"""Per-screen feature parity with CardSat 0.9.75.

The earlier audit confirmed each tool *existed*; these cover features CardSat
offers inside a screen that OrbitDeck was missing.
"""

import time


def test_workable_on_pass_engine():
    """CardSat's Passes screen answers 'what can I work on THIS pass' (g/w/e).
    The Workable screen only answered 'what is under the footprint now'."""
    import os
    os.environ["ORBITDECK_TEST"] = "1"
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.predict import Predictor
    from orbitdeck.engine import planning as PL
    st = Store()
    sat = st.db.sats[0]
    pred = Predictor()
    pred.set_site(st.obs)
    pred.set_sat(sat)
    passes = pred.predict_passes(time.time(), 5.0, 1)
    assert passes
    p = passes[0]
    res = PL.workable_on_pass(pred, sat, st.obs, p.aos, p.los)
    assert res["samples"] > 1
    assert res["grids"] and res["states"]
    assert all(isinstance(g, str) for g in res["grids"])
    # a pass sweeps more territory than a single instant
    lat, lon, alt = pred.subpoint_at(p.aos)
    from orbitdeck.engine import analysis as AN
    instant = set(AN.workable_grids(lat, lon, alt))
    assert len(res["grids"]) >= len(instant)
    # kinds are selectable
    only = PL.workable_on_pass(pred, sat, st.obs, p.aos, p.los,
                               kinds=("states",))
    assert only["states"] and not only["grids"]


def test_tui_workable_prefix_filter():
    """~1700 grids under a footprint is unusable without a filter (CardSat f/c).

    Asserted as PROPERTIES rather than counts: the satellite moves between
    calls, so any two live snapshots differ and a prefix taken from one may not
    exist in the next. Counting made this flaky by construction.
    """
    import os
    os.environ["ORBITDECK_TEST"] = "1"
    from orbitterm.state import AppState
    from orbitterm.screens.analysis2 import WorkableScreen

    class _App:
        def __init__(self, st):
            self.state = st
    st = AppState()
    st.set_site(39.93, -74.89, 20.0)
    s = WorkableScreen(_App(st))

    # nothing matches this, whatever is underfoot
    s.filter = "ZZZZ"
    assert s._items() == []

    # a real prefix returns only matching items - checked against the same
    # call that produced the result, never across two snapshots
    s.filter = ""
    every = s._items()
    assert every
    s.filter = every[0][:2]
    for item in s._items():
        assert item.upper().startswith(s.filter.upper())

    # 'c' clears the filter and the unfiltered list is non-empty again
    s.handle_key(ord("c"))
    assert s.filter == ""
    assert s._items()



def test_tui_workable_filter_editing_keys():
    import os
    import curses
    os.environ["ORBITDECK_TEST"] = "1"
    from orbitterm.state import AppState
    from orbitterm.screens.analysis2 import WorkableScreen

    class _App:
        def __init__(self, st):
            self.state = st
    s = WorkableScreen(_App(AppState()))
    s.handle_key(ord("f"))
    assert s.editing
    for ch in "FM":
        s.handle_key(ord(ch))
    assert s.filter == "FM"
    s.handle_key(curses.KEY_BACKSPACE)
    assert s.filter == "F"
    s.handle_key(27)                      # ESC cancels and clears
    assert not s.editing and s.filter == ""


def test_gui_screens_expose_the_new_features():
    import inspect
    from orbitdeck.gui.screens import passes, grids, track
    assert "_workable_on_pass" in inspect.getsource(passes.PassesScreen)
    src = inspect.getsource(grids.GridsScreen)
    assert "_apply_filter" in src and "Filter (prefix)" in src
    # one-key "I heard it" report, which CardSat puts on the tracking screen
    assert "_report_heard" in inspect.getsource(track.TrackScreen)


def test_report_heard_resolves_the_api_name():
    """It must go through the catalog matcher - a catalog name is not an API
    name, which is what made the earlier AO-7 queries 404."""
    import inspect
    from orbitdeck.gui.screens import track
    src = inspect.getsource(track.TrackScreen)
    assert "resolve_names" in src
    assert "callsign" in src               # refuses to report anonymously
