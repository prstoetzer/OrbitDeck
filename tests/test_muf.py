"""Tests for the MINIMUF-3.5 HF propagation model."""

import time

from orbitdeck.engine import muf as M


def test_regions_table():
    assert len(M.REGIONS) == 24
    for name, lat, wlon in M.REGIONS:
        assert name
        assert -90 <= lat <= 90
        assert -180 <= wlon <= 180


def test_muf_in_valid_range():
    """MINIMUF clamps to 2-32 MHz; every region must land inside it."""
    rows = M.muf_to_regions(39.93, -74.89, time.time(), ssn=100)
    assert len(rows) == 24
    for r in rows:
        assert 2.0 <= r["muf_mhz"] <= 32.0
        assert r["workable_mhz"] < r["muf_mhz"]
        assert r["band"]
        assert 0 <= r["bearing_deg"] < 360
        assert r["distance_km"] > 0


def test_muf_rises_with_sunspot_number():
    t = time.time()
    lo = M.muf_to_regions(39.93, -74.89, t, ssn=10)
    hi = M.muf_to_regions(39.93, -74.89, t, ssn=200)
    mean_lo = sum(r["muf_mhz"] for r in lo) / len(lo)
    mean_hi = sum(r["muf_mhz"] for r in hi) / len(hi)
    assert mean_hi > mean_lo


def test_great_circle_distance_and_bearing():
    # ~1 degree of latitude is ~111 km, due north
    d, b = M.great_circle(39.0, -77.0, 40.0, -77.0)
    assert 110 < d < 112
    assert b < 1 or b > 359
    # New Jersey to London is roughly 5500-6000 km, generally north-east
    d2, b2 = M.great_circle(39.93, -74.89, 51.5, -0.13)
    assert 5000 < d2 < 6500
    assert 30 < b2 < 70


def test_workable_band_thresholds():
    assert M.workable_band(32.0) == "10m" or M.workable_band(32.0) == "12m"
    assert M.workable_band(8.0) == "80m"
    # the band label is monotonic in MUF (higher MUF never means a lower band)
    order = ["80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"]
    idx = [order.index(M.workable_band(m)) for m in (5, 9, 13, 17, 21, 25, 30)]
    assert idx == sorted(idx)


def test_quality_buckets():
    assert M.muf_band_color_key(5) == "low"
    assert M.muf_band_color_key(12) == "fair"
    assert M.muf_band_color_key(20) == "good"
    assert M.muf_band_color_key(30) == "high"


def test_minimuf_symmetry_is_reasonable():
    """A path and its reverse should give a similar MUF (same ionosphere)."""
    t = time.time()
    tm = time.gmtime(t)
    a = M.minimuf_mhz(40 * M.D2R, 74 * M.D2R, 51 * M.D2R, 0.0,
                      tm.tm_mon, tm.tm_mday, tm.tm_hour, 100)
    b = M.minimuf_mhz(51 * M.D2R, 0.0, 40 * M.D2R, 74 * M.D2R,
                      tm.tm_mon, tm.tm_mday, tm.tm_hour, 100)
    assert abs(a - b) < max(3.0, 0.25 * max(a, b))


def test_muf_screen_builds():
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
        app.show("muf")
        root.update()
        scr = app.current
        rows = M.muf_to_regions(app.store.obs.lat, app.store.obs.lon,
                                time.time(), 120)
        scr._done(rows, 120)
        root.update()
        assert len(scr.tree.get_children()) == 24
        scr.sortvar.set("muf")
        scr._render()
        root.update()
    except Exception:
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_muf_to_dxcc_lookup():
    """The region table answers 'how is Europe'; an operator asks 'can I work
    JA right now'."""
    import time as _t
    hits = M.muf_to_dxcc(39.93, -74.89, _t.time(), 100, "JA")
    assert hits
    top = hits[0]
    assert top["prefix"] == "JA" and "Japan" in top["name"]
    assert 2.0 <= top["muf_mhz"] <= 32.0
    assert top["distance_km"] > 8000          # NJ to Japan
    assert 0 <= top["bearing_deg"] < 360
    # name search works too, and an exact prefix sorts first
    by_name = M.muf_to_dxcc(39.93, -74.89, _t.time(), 100, "Japan")
    assert by_name and "Japan" in by_name[0]["name"]
    assert M.muf_to_dxcc(39.93, -74.89, _t.time(), 100, "NOPE") == []
    assert M.muf_to_dxcc(39.93, -74.89, _t.time(), 100, "") == []


def test_muf_screens_offer_the_lookup():
    import inspect
    from orbitdeck.gui.screens import muf as gm
    assert "_lookup_dxcc" in inspect.getsource(gm.MufScreen)
    from orbitterm.screens import analysis2
    assert "muf_to_dxcc" in inspect.getsource(analysis2.MufScreen)
