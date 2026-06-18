"""Miscellaneous tests.

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


def test_pass_prediction_reasonable(iss_predictor):
    pred, sat = iss_predictor
    t0 = sat.epoch_unix
    passes = pred.predict_passes(t0, 5.0, 20, t0 + 86400)
    assert 4 <= len(passes) <= 9             # ISS gives ~6-7/day from NJ
    for p in passes:
        assert p.los > p.aos
        assert 5.0 <= p.max_el <= 90.0
        assert 0 <= p.az_aos <= 360
        dur_min = (p.los - p.aos) / 60.0
        assert 0 < dur_min < 15

def test_footprint_increases_with_altitude(iss_predictor):
    pred, _ = iss_predictor
    assert pred.footprint_radius_km(400) < pred.footprint_radius_km(1500)
    assert 2000 < pred.footprint_radius_km(420) < 2600

def test_manual_sat_and_tx_helpers():
    import time
    from orbitdeck.engine.satdb import (make_manual_sat, sat_to_dict,
                                        sat_from_dict, make_manual_transponder,
                                        tx_to_dict, tx_from_dict)
    e = make_manual_sat("MANUAL1", 90001, time.time(), 51.6, 100, 0.001,
                        90, 180, 15.5, 0.0001)
    assert e.is_manual and e.norad == 90001
    assert 90 < e.period_min < 95          # ~15.5 rev/day -> ~93 min
    e2 = sat_from_dict(sat_to_dict(e))
    assert e2.norad == e.norad and abs(e2.mean_motion - e.mean_motion) < 1e-9

    # linear transponder: auto-fills uplink_high to matching bandwidth
    lin = make_manual_transponder(145925000, 432125000, 145975000, 0,
                                  True, "SSB")
    assert lin.is_linear and lin.invert
    assert lin.downlink_center() == 145950000
    assert lin.uplink_high == 432175000    # 50 kHz bandwidth matched
    lin2 = tx_from_dict(tx_to_dict(lin))
    assert lin2.downlink_center() == 145950000

    # single-channel FM
    fm = make_manual_transponder(145800000, 435100000, 0, 0, False, "FM")
    assert not fm.is_linear and fm.downlink_center() == 145800000

def test_elevation_central_angle_geometry():
    """The elevation/central-angle helpers are self-consistent: elevation is 0
    exactly at the footprint edge, +90 at the sub-point, and the forward and
    inverse functions round-trip."""
    from orbitdeck.engine import analysis as A
    alt = 420.0
    fr = A.footprint_radius_deg(alt)
    assert abs(A.elevation_for_central_angle_deg(fr, alt)) < 1e-6
    assert abs(A.elevation_for_central_angle_deg(0.0, alt) - 90.0) < 1e-6
    for el in (0, 5, 10, 20, 30, 45, 60):
        gamma = A.central_angle_for_elevation_deg(el, alt)
        assert gamma is not None
        back = A.elevation_for_central_angle_deg(gamma, alt)
        assert abs(back - el) < 1e-3
    assert abs(A.central_angle_for_elevation_deg(0.0, alt) - fr) < 1e-6
    # higher elevation is closer to the station (smaller central angle)
    assert (A.central_angle_for_elevation_deg(60, alt)
            < A.central_angle_for_elevation_deg(10, alt))
