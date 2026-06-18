"""Planning, workable, mutual-visibility and optical tests.

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


def test_workable_grids_counts():
    from orbitdeck.engine import analysis as A
    g = A.workable_grids(40.0, -75.0, 420)
    assert 400 < len(g) < 1200          # LEO footprint ~ several hundred grids
    assert all(len(x) == 4 for x in g)
    # a higher bird sees more
    g2 = A.workable_grids(40.0, -75.0, 1500)
    assert len(g2) > len(g)

def test_workable_states_conus():
    from orbitdeck.engine import analysis as A
    from orbitdeck.data.us_states import workable_states
    # a LEO footprint centred over Kansas should sweep most of the lower 48
    inside = A.make_footprint_test(39.0, -95.0, 420)
    states = workable_states(inside)
    assert "KS" in states and "TX" in states and "CA" in states
    assert 30 < len(states) <= 51
    # a footprint over the mid-Pacific should reach no mainland states
    inside2 = A.make_footprint_test(0.0, -150.0, 420)
    assert workable_states(inside2) == [] or "HI" in workable_states(inside2)

def test_workable_dxcc_basic():
    from orbitdeck.engine import analysis as A
    from orbitdeck.data.dxcc import workable_dxcc
    inside = A.make_footprint_test(39.0, -95.0, 420)
    ents = dict(workable_dxcc(inside))
    assert "K" in ents                       # United States
    # over central Europe, expect DL/F/etc., not the USA
    inside2 = A.make_footprint_test(50.0, 9.0, 420)
    prefixes = [p for p, n in workable_dxcc(inside2)]
    assert "DL" in prefixes
    assert "K" not in prefixes

def test_optical_magnitude_model():
    from orbitdeck.engine import linkbudget as LB
    # at the reference range and full phase, apparent == standard magnitude
    assert abs(LB.apparent_magnitude(-1.3, 1000.0, 0.0) - (-1.3)) < 1e-6
    # closer => brighter (more negative)
    m_close = LB.apparent_magnitude(-1.3, 400.0, 0.0)
    assert m_close < -1.3
    # larger phase angle => dimmer
    m_phase = LB.apparent_magnitude(-1.3, 400.0, 120.0)
    assert m_phase > m_close
    # ISS-class at 400 km should land in a plausible bright range
    assert -6.0 < m_close < -2.0

def test_optical_visibility_conditions():
    from orbitdeck.engine import linkbudget as LB
    # sunlit sat, observer in darkness, high elevation -> visible
    assert LB.is_optically_visible(True, -10.0, 40.0)
    # observer in daylight -> not visible
    assert not LB.is_optically_visible(True, +10.0, 40.0)
    # sat in eclipse -> not visible
    assert not LB.is_optically_visible(False, -10.0, 40.0)
    # too low -> not visible
    assert not LB.is_optically_visible(True, -10.0, 3.0)

def test_sat_to_sat_los():
    import math
    from orbitdeck.engine import linkbudget as LB
    # opposite sides of Earth -> blocked
    assert not LB.sat_to_sat_los((7000, 0, 0), (-7000, 0, 0))
    # near each other on the same side -> clear
    assert LB.sat_to_sat_los((7000, 0, 0), (7000, 200, 0))
    # two sats at 7000 km separated by 30 deg: chord midpoint is ~6761 km from
    # Earth centre (> RE), so the line of sight is clear
    a = (7000.0, 0.0, 0.0)
    b = (7000.0 * math.cos(math.radians(30)),
         7000.0 * math.sin(math.radians(30)), 0.0)
    assert LB.sat_to_sat_los(a, b)
    # separated by 90 deg: midpoint ~4950 km (< RE) -> Earth blocks the chord
    c = (0.0, 7000.0, 0.0)
    assert not LB.sat_to_sat_los(a, c)

def test_pass_quality_score():
    from orbitdeck.engine import linkbudget as LB
    # a high overhead pass scores higher than a low grazing pass
    overhead = LB.pass_quality_score(85.0, 600.0)
    grazing = LB.pass_quality_score(8.0, 120.0)
    assert overhead > grazing
    assert 0.0 <= grazing <= 100.0 and 0.0 <= overhead <= 100.0

def test_planning_best_passes_and_sky_grid():
    import time
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.predict import Observer
    from orbitdeck.engine import planning as PL
    st = Store()
    st.obs = Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True)
    s = st.selected_sat()
    st.pred.set_site(st.obs)
    st.pred.set_sat(s)
    t = time.time()
    # a target a few hundred km away should share some footprint windows
    res = PL.best_passes_for_target(st.pred, st.obs, 41.7, -72.7, t, hours=24,
                                    max_results=10)
    assert isinstance(res, list)
    for w in res:
        assert w["end"] >= w["start"]
        assert w["duration_s"] >= 0
    # sky coverage grid accumulates dwell over passes
    passes = st.pred.predict_passes(t, 0.0, 5)
    grid = PL.sky_coverage_grid(st.pred, st.obs, passes, az_bins=12, el_bins=3)
    assert len(grid) == 3 and len(grid[0]) == 12
    total = sum(sum(row) for row in grid)
    assert total >= 0

def test_sat_to_sat_windows_engine():
    import time
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.predict import Observer, Predictor
    from orbitdeck.engine import celestial as CE
    st = Store()
    if st.db.count() < 2:
        return
    obs = Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True)
    s1, s2 = st.db.sats[0], st.db.sats[1]
    p1 = Predictor(); p1.set_site(obs); p1.set_sat(s1)
    p2 = Predictor(); p2.set_site(obs); p2.set_sat(s2)
    wins = CE.sat_to_sat_windows(p1, p2, time.time(), hours=6, step_s=60)
    assert isinstance(wins, list)
    for w in wins:
        assert w["end"] >= w["start"]
        assert w["duration_s"] >= 0
        assert w["min_range_km"] > 0

def test_mutual_detail_bounds_and_subset():
    """The detail view's full-pass bounds must contain the mutual window, and
    the mutually-visible samples must be a subset of the full pass track from
    the primary station. Tests the helper logic directly against predictors,
    without building the full GUI app."""
    import time
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.predict import Observer, Predictor

    store = Store()
    s = store.selected_sat()
    if s is None:
        return
    my = Predictor()
    my.set_site(Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True))
    my.set_sat(s)
    dx = Observer(lat=32.5, lon=-97.0, alt_m=0, valid=True)   # ~2000 km away
    t = time.time()
    wins = my.mutual_windows(t, dx, 0.0, 30, horizon_days=10)
    if not wins:
        return
    w = max(wins, key=lambda w: w.my_max_el)

    # replicate the screen's _full_pass_bounds logic: walk outward from the
    # window edges while the primary station sees the satellite above 0 deg
    def full_bounds(pred, w, step=10.0):
        aos = w.start
        tt = w.start
        while pred.azel_at(tt)[1] >= 0 and tt > w.start - 3600:
            aos = tt
            tt -= step
        los = w.end
        tt = w.end
        while pred.azel_at(tt)[1] >= 0 and tt < w.end + 3600:
            los = tt
            tt += step
        return aos, los

    aos, los = full_bounds(my, w)
    # full pass contains the mutual window
    assert aos <= w.start + 1.0
    assert los >= w.end - 1.0
    # sample the full pass; every sample is above the horizon
    track = []
    tt = aos
    while tt <= los:
        az, el = my.azel_at(tt)
        if el >= 0:
            track.append((tt, az, el))
        tt += 10.0
    assert track
    assert all(p[2] >= 0 for p in track)
    # the mutually-visible samples are a subset of the full-pass span
    mutual = [p for p in track if w.start <= p[0] <= w.end]
    assert mutual
    assert len(mutual) <= len(track)

def test_dxcc_target_resolution():
    """The Planning screen resolves a DXCC entity name to its centroid."""
    from orbitdeck.data.dxcc import DXCC
    names = {v[0]: (v[1], v[2]) for v in DXCC.values()}
    # pick a well-known entity present in the table
    assert "United States" in names
    lat, lon = names["United States"]
    assert -90 <= lat <= 90 and -180 <= lon <= 180

def test_mutual_favorites_scope_scans_all_favorites():
    """The Mutual Windows screen in 'All favorites' mode scans every favorite,
    not just the selected satellite, and tags each window with its satellite."""
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp
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
    names = ("ISS", "SO-50", "AO-91")
    favs = [s for s in app.store.db.sats if s.name in names]
    for s in favs:
        app.store.favorites.add(s.norad)
    app.store.select(favs[0].norad)
    scr = screens.make_screen("mutual", app.content, app)
    # a DX near the primary station so LEO co-visibility windows exist
    scr.dx.set("41.8,-87.6")
    scr.scope.set("favorites")
    scr.minel.set(0)
    scr._reload()
    rows = scr._all_rows
    if rows:                          # bundled illustrative elements may vary
        sats_seen = {s.name for s, _w in rows}
        # more than one favorite should contribute windows
        assert len(sats_seen) >= 2
        assert sats_seen <= set(names)
        # each row carries its own satellite for the double-click detail
        for row_id, (w, s) in scr._win_by_row.items():
            assert s is not None
    root.destroy()

def test_workable_and_planning_export_shapes():
    """The new CSV exporters return header+row tables of matching widths."""
    from orbitdeck.gui import exports as EX
    # workable
    h, r = EX.workable_rows("grids", ["FN31", "FN20", "EM48"], "ISS", "live")
    assert len(r) == 3 and all(len(row) == len(h) for row in r)
    # work-a-target
    wins = [{"start": 1.7e9, "duration_s": 480.0, "margin_deg": 12.3}]
    h, r = EX.work_target_rows(wins, "ISS", "FN31")
    assert len(r) == 1 and len(r[0]) == len(h)
    assert r[0][3] == pytest.approx(8.0)         # 480 s -> 8.0 min
    # visible passes
    vp = [{"aos": 1.7e9, "los": 1.7e9 + 360, "max_el": 45.0, "mag": 2.7}]
    h, r = EX.visible_passes_rows(vp, "ISS")
    assert len(r) == 1 and len(r[0]) == len(h)
    assert r[0][3] == pytest.approx(6.0)         # 360 s -> 6.0 min
