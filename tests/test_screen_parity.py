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
    """~1700 grids under a footprint is unusable without a filter (CardSat f/c)."""
    import os
    os.environ["ORBITDECK_TEST"] = "1"
    from orbitterm.state import AppState
    from orbitterm.screens.analysis2 import WorkableScreen

    class _App:
        def __init__(self, st):
            self.state = st
    st = AppState()
    # pin the site: another test may have moved the QTH, which changes which
    # grids are under the footprint and so which prefix exists
    st.set_site(39.93, -74.89, 20.0)
    s = WorkableScreen(_App(st))
    every = s._items()
    assert every
    pre = every[0][:2]
    s.filter = pre
    sub = s._items()
    assert sub and set(sub) <= set(every)
    assert all(i.upper().startswith(pre.upper()) for i in sub)
    s.filter = "ZZZZ"
    assert s._items() == []
    # 'c' clears
    s.handle_key(ord("c"))
    assert s.filter == "" and len(s._items()) == len(every)


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
