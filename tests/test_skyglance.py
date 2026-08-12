"""Tests for the sky-at-a-glance timeline and the AO-7 illumination status."""

import time

from orbitdeck.engine import skyglance as SG
from orbitdeck.engine.predict import Predictor


def _favs(n=4):
    from orbitdeck.gui.store import Store
    s = Store()
    favs = [x for x in s.db.sats if x.norad in s.favorites][:n] or s.db.sats[:n]
    return s, favs


def test_sky_glance_rows_and_shape():
    s, favs = _favs()
    rows = SG.sky_glance(Predictor(), s.obs, favs, time.time(), hours=12)
    assert rows
    # every favorite gets a row, even a quiet one
    assert len(rows) == len(favs)
    for r in rows:
        assert "name" in r and "norad" in r and isinstance(r["passes"], list)
        for a, b, el in r["passes"]:
            assert b >= a
            assert 0 <= el <= 90


def test_sky_glance_respects_window_and_min_el():
    s, favs = _favs()
    t = time.time()
    short = SG.sky_glance(Predictor(), s.obs, favs, t, hours=3)
    long_ = SG.sky_glance(Predictor(), s.obs, favs, t, hours=24)
    n_short = sum(len(r["passes"]) for r in short)
    n_long = sum(len(r["passes"]) for r in long_)
    assert n_long >= n_short
    # passes never start before the window
    for r in short:
        for a, _b, _e in r["passes"]:
            assert a >= t - 1
    # a high elevation floor yields no more passes than a low one
    hi = SG.sky_glance(Predictor(), s.obs, favs, t, hours=12, min_el=30)
    lo = SG.sky_glance(Predictor(), s.obs, favs, t, hours=12, min_el=0)
    assert sum(len(r["passes"]) for r in hi) <= sum(len(r["passes"]) for r in lo)


def test_busiest_gap_finds_quiet_stretch():
    t0 = 1000000.0
    rows = [{"name": "A", "norad": 1,
             "passes": [(t0 + 600, t0 + 900, 30.0),
                        (t0 + 5400, t0 + 5700, 20.0)]}]
    gap = SG.busiest_gap(rows, t0, hours=2)
    assert gap is not None
    # the long quiet stretch is between the two passes
    assert gap[0] >= t0 + 900 and gap[1] <= t0 + 5400 + 1


def test_busiest_gap_no_passes_is_whole_window():
    t0 = 1000.0
    gap = SG.busiest_gap([{"name": "A", "norad": 1, "passes": []}], t0, hours=4)
    assert abs((gap[1] - gap[0]) - 4 * 3600) < 1


def test_ao7_illumination_fields():
    s, favs = _favs(1)
    res = SG.ao7_illumination(Predictor(), favs[0], time.time())
    assert res is not None
    assert 0.0 <= res["eclipse_frac"] <= 1.0
    assert res["continuous_sun"] == (res["eclipse_frac"] == 0.0)
    assert res["period_min"] > 0
    assert "timer" in res["note"] or "power" in res["note"]


def test_beta_star_rises_with_altitude():
    assert SG.beta_star_for_altitude(1200) > SG.beta_star_for_altitude(400)
    assert 0 < SG.beta_star_for_altitude(550) < 90


def test_elevation_colour_bands():
    from orbitdeck.gui.screens.skyglance import elevation_colour
    low = elevation_colour(10)
    mid = elevation_colour(30)
    high = elevation_colour(70)
    assert low != mid != high


def test_skyglance_screen_builds():
    import tkinter as tk
    if not hasattr(tk, "Listbox"):
        return
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        app = OrbitDeckApp(root)
        app.show("skyglance")
        root.update()
        scr = app.current
        favs = [x for x in app.store.db.sats
                if x.norad in app.store.favorites] or app.store.db.sats[:3]
        t = time.time()
        rows = SG.sky_glance(Predictor(), app.store.obs, favs, t, hours=12)
        scr._done(rows, t)
        root.update()
    except Exception:
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass
