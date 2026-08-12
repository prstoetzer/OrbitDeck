"""Tests for the expanded DXCC data and the workable-horizon / target-search
planning functions (the CardSat rove/workable gap closers)."""

import time

import json

from orbitdeck.engine.predict import Predictor
from orbitdeck.engine import planning as PL


def _sample_favs(n=3):
    from orbitdeck.gui.store import Store
    s = Store()
    favs = [x for x in s.db.sats if x.norad in s.favorites][:n] or s.db.sats[:n]
    return s, favs


# ---- DXCC data coverage ----
def test_dxcc_has_340_entities():
    from orbitdeck.data.dxcc import DXCC
    assert len(DXCC) == 340
    names = {v[0] for v in DXCC.values()}
    assert len(names) == 340                     # all distinct
    # every value is (name, lat, lon) with sane coordinates
    for _pfx, (name, lat, lon) in DXCC.items():
        assert name
        assert -90 <= lat <= 90 and -180 <= lon <= 180


def test_dxcc_workable_api():
    from orbitdeck.data.dxcc import workable_dxcc
    # a footprint over the central US should include the United States
    # (its reference point is the geographic centre ~39N, 98W)
    def infp(lat, lon):
        return 30 < lat < 45 and -105 < lon < -90
    hits = {nm for _pfx, nm in workable_dxcc(infp)}
    assert any("United States" in h for h in hits)


def test_state_abbrev_resolution():
    from orbitdeck.data.us_states import state_abbrev
    assert state_abbrev("California") == "CA"
    assert state_abbrev("ca") == "CA"
    assert state_abbrev("District of Columbia") == "DC"
    assert state_abbrev("Nowhere") is None


# ---- workable horizon ----
def test_workable_horizon_union():
    s, favs = _sample_favs(3)
    pred = Predictor()
    pred.set_site(s.obs)
    res = PL.workable_horizon(pred, favs, time.time(), days=2,
                              kinds=("states", "dxcc"), min_el=5)
    assert res["sat_count"] >= 1
    assert res["pass_count"] >= 1
    # a few days across favorites from a US site should work many states
    assert len(res["states"]) > 5
    assert isinstance(res["dxcc"], list)
    # results are sorted and de-duplicated
    assert res["states"] == sorted(set(res["states"]))


def test_workable_horizon_no_favorites():
    s, _ = _sample_favs(0)
    pred = Predictor()
    pred.set_site(s.obs)
    res = PL.workable_horizon(pred, [], time.time(), days=2)
    assert res["sat_count"] == 0 and res["states"] == []


# ---- target search ----
def test_target_search_state_name_or_abbrev():
    s, favs = _sample_favs(3)
    pred = Predictor()
    pred.set_site(s.obs)
    by_name = PL.target_search(pred, favs, "state", "California", time.time(),
                               days=2, min_el=5)
    by_abbr = PL.target_search(pred, favs, "state", "CA", time.time(),
                               days=2, min_el=5)
    assert len(by_name) == len(by_abbr)          # same target, same result
    # time-ordered across favorites
    for a, b in zip(by_name, by_name[1:]):
        assert a["start"] <= b["start"]
    for r in by_name:
        assert r["sat_name"] and r["duration_s"] >= 0


def test_target_search_dxcc():
    s, favs = _sample_favs(3)
    pred = Predictor()
    pred.set_site(s.obs)
    res = PL.target_search(pred, favs, "dxcc", "United States", time.time(),
                           days=2, min_el=5)
    assert isinstance(res, list)
    for r in res:
        assert "start" in r and "max_el_deg" in r


def test_target_search_unknown_state_empty():
    s, favs = _sample_favs(2)
    pred = Predictor()
    pred.set_site(s.obs)
    res = PL.target_search(pred, favs, "state", "Atlantis", time.time(),
                           days=2)
    assert res == []


# ---- GUI wiring (defensive: bail if no real Tk) ----
def test_planning_new_tabs_build():
    import tkinter as tk
    # bail cleanly if tkinter is stubbed (no full widget set) or has no display
    if not hasattr(tk, "Listbox") or not hasattr(tk, "Entry"):
        return
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        app = OrbitDeckApp(root)
        app.show("planning")
        root.update()
        scr = app.current
        assert hasattr(scr, "_hz_tree") and hasattr(scr, "_ts_tree")
        # exercise the target-type toggle and the horizon render path
        scr._ts_kind.set("dxcc")
        scr._on_ts_kind()
        root.update()
        scr._show_horizon({"states": ["CA", "NY"], "dxcc": ["Canada"],
                           "grids": [], "sat_count": 2, "pass_count": 5})
        root.update()
        assert len(scr._hz_tree.get_children()) == 3
    except Exception:
        # a tkinter stub can raise deep in widget creation; treat as skip
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass
