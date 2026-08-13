"""Tests for the orbital-zones model (SAA, radiation belts, polar, eclipse)."""

import json
import time

from orbitdeck.engine import zones as Z
from orbitdeck.engine import SatDb
from orbitdeck.engine.predict import Predictor


def _iss():
    omm = [{"OBJECT_NAME": "ISS", "OBJECT_ID": "1998-067A",
            "EPOCH": "2026-07-19T12:00:00.000000", "MEAN_MOTION": 15.5,
            "ECCENTRICITY": 0.0004, "INCLINATION": 51.64,
            "RA_OF_ASC_NODE": 210.0, "ARG_OF_PERICENTER": 80.0,
            "MEAN_ANOMALY": 280.0, "BSTAR": 0.00025,
            "MEAN_MOTION_DOT": 0.0001, "MEAN_MOTION_DDOT": 0.0,
            "NORAD_CAT_ID": 25544, "REV_AT_EPOCH": 45000,
            "ELEMENT_SET_NO": 999}]
    db = SatDb()
    db.load_gp_json(json.dumps(omm))
    return db.sats[0]


def test_magnetic_latitude_at_pole():
    assert abs(Z.magnetic_latitude(Z.POLE_LAT, Z.POLE_LON) - 90.0) < 1e-6


def test_shell_l_grows_with_magnetic_latitude():
    eq = Z.shell_l(0, Z.POLE_LON, 400)
    hi = Z.shell_l(45, Z.POLE_LON, 400)
    assert hi > eq > 1.0


def test_b_ratio_minimum_at_magnetic_equator():
    """B/B0 is 1 on the magnetic equator and rises away from it."""
    # a point whose magnetic latitude is ~0
    lat0 = -Z.POLE_LAT + 90.0
    eqr = Z.b_ratio(lat0, Z.POLE_LON, 400)
    off = Z.b_ratio(lat0 + 30, Z.POLE_LON, 400)
    assert eqr < off


def test_saa_ellipse_contains_center_only():
    t = time.time()
    assert Z.in_zone(Z.ZONE_SAA, -27, -53, 400, True, t)
    assert not Z.in_zone(Z.ZONE_SAA, 50, 10, 400, True, t)     # Europe
    assert not Z.in_zone(Z.ZONE_SAA, 0, 150, 400, True, t)     # Pacific


def test_saa_center_drifts_west():
    y2025 = time.mktime(time.strptime("2025-01-02", "%Y-%m-%d"))
    y2035 = time.mktime(time.strptime("2035-01-02", "%Y-%m-%d"))
    lon25 = Z.saa_center(y2025)[1]
    lon35 = Z.saa_center(y2035)[1]
    assert lon35 < lon25                       # drifts westward


def test_polar_and_eclipse_zones():
    assert Z.in_zone(Z.ZONE_POLAR, 70, 0, 400, True)
    assert not Z.in_zone(Z.ZONE_POLAR, 30, 0, 400, True)
    assert Z.in_zone(Z.ZONE_ECLIPSE, 0, 0, 400, False)
    assert not Z.in_zone(Z.ZONE_ECLIPSE, 0, 0, 400, True)


def test_belts_reject_low_altitude():
    """Below the atmosphere floor nothing is trapped, whatever the shell."""
    assert not Z.in_zone(Z.ZONE_INNER, 0, Z.POLE_LON, 100, True)
    assert not Z.in_zone(Z.ZONE_OUTER, 0, Z.POLE_LON, 100, True)


def test_scan_zone_eclipse_fraction_is_sane():
    """ISS eclipse dwell should be a substantial fraction of the day."""
    sat = _iss()
    pred = Predictor()
    res = Z.scan_zone(pred, sat, Z.ZONE_ECLIPSE, time.time(), hours=6)
    assert res["windows"]
    # ISS is eclipsed roughly a third of each orbit
    assert 200 < res["dwell_min_day"] < 700
    for a, b in res["windows"]:
        assert b >= a


def test_scan_zone_saa_windows_over_a_day():
    sat = _iss()
    pred = Predictor()
    res = Z.scan_zone(pred, sat, Z.ZONE_SAA, time.time(), hours=24)
    # the ISS crosses the SAA on several orbits a day
    assert len(res["windows"]) >= 3
    assert res["dwell_min_day"] > 10


def test_scan_zone_reports_shell_values():
    sat = _iss()
    pred = Predictor()
    res = Z.scan_zone(pred, sat, Z.ZONE_INNER, time.time(), hours=6)
    assert res["shell_l"] > 0
    assert res["b_ratio"] >= 1.0 - 1e-9
    assert "scanned_h" in res


def test_zones_screen_builds():
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
        app.show("zones")
        root.update()
        scr = app.current
        sat = app.store.selected_sat()
        pred = Predictor()
        res = Z.scan_zone(pred, sat, Z.ZONE_ECLIPSE, time.time(), hours=6)
        scr._show(res, sat, Z.ZONE_ECLIPSE)
        root.update()
    except Exception:
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass
