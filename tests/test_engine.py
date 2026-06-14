"""
Engine tests for OrbitDeck.

These lock in the orbital math so refactors can't silently break accuracy.
The headline test verifies the vendored SGP4 against the canonical Vallado
AIAA-2006-6753 reference vector (catalog 88888).
"""

import datetime as dt
import json
import math

import pytest

from orbitdeck.engine.sgp4_lite import Satrec
from orbitdeck.engine import (SatDb, Predictor, Observer,
                              latlon_to_grid, grid_to_latlon)


def _jd_from_tle_epoch(year, day):
    if year < 57:
        year += 2000
    else:
        year += 1900
    d = dt.datetime(year, 1, 1)
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    jdn = d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    return (jdn - 0.5) + (day - 1.0)


def test_sgp4_vallado_reference_vector():
    """Position must match the published reference to ~1 metre at epoch."""
    jd = _jd_from_tle_epoch(0, 179.78495062)
    s = Satrec()
    ok = s.init_from_elements(jd, 0.66816e-4, 0.0, 0.0,
                              0.0086731, 52.6988, 72.8435, 110.5714,
                              16.05824518, 115.9689, 88888)
    assert ok and s.error == 0
    r, v = s.sgp4(0.0)
    # Reference at t=0: r = [2328.969, -5995.220, 1719.974] km
    assert r[0] == pytest.approx(2328.969, abs=0.01)
    assert r[1] == pytest.approx(-5995.220, abs=0.01)
    assert r[2] == pytest.approx(1719.974, abs=0.01)


def test_iss_altitude_and_speed_stable():
    """An ISS-like LEO should stay near 400-430 km at ~7.66 km/s over a day."""
    jd = _jd_from_tle_epoch(24, 179.5)
    s = Satrec()
    s.init_from_elements(jd, 3.0e-4, 0.0, 0.0, 0.0007, 130.0, 51.64,
                         230.0, 15.50, 290.0, 25544)
    for k in range(0, 16):
        r, v = s.sgp4(k * 90.0)
        alt = math.sqrt(sum(c * c for c in r)) - 6378.135
        spd = math.sqrt(sum(c * c for c in v))
        assert 380 < alt < 460
        assert 7.5 < spd < 7.8
        assert s.error == 0


@pytest.fixture
def iss_predictor():
    omm = [{
        "OBJECT_NAME": "ISS (ZARYA)", "OBJECT_ID": "1998-067A",
        "EPOCH": "2024-06-01T12:00:00.000000", "MEAN_MOTION": 15.50103472,
        "ECCENTRICITY": 0.0004364, "INCLINATION": 51.6393,
        "RA_OF_ASC_NODE": 210.0, "ARG_OF_PERICENTER": 80.0,
        "MEAN_ANOMALY": 280.0, "BSTAR": 0.00025, "MEAN_MOTION_DOT": 0.0001,
        "MEAN_MOTION_DDOT": 0.0, "NORAD_CAT_ID": 25544, "REV_AT_EPOCH": 45000,
        "ELEMENT_SET_NO": 999,
    }]
    db = SatDb()
    db.load_gp_json(json.dumps(omm))
    pred = Predictor()
    pred.set_site(Observer(lat=39.93, lon=-74.89, alt_m=20, valid=True))
    assert pred.set_sat(db.sats[0])
    return pred, db.sats[0]


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


def test_doppler_sign_and_magnitude(iss_predictor):
    pred, sat = iss_predictor
    # over a pass, downlink Doppler should swing through both signs
    t0 = sat.epoch_unix
    passes = pred.predict_passes(t0, 5.0, 1, t0 + 6 * 3600)
    assert passes
    p = passes[0]
    shifts = []
    for i in range(41):
        tt = p.aos + (p.los - p.aos) * i / 40
        L = pred.look(tt)
        rx, _ = pred.doppler_freqs(145_800_000, 0, L.range_rate)
        shifts.append(rx - 145_800_000)
    assert max(shifts) > 0 and min(shifts) < 0       # crosses zero
    assert max(abs(s) for s in shifts) < 6000        # 2m LEO ~ few kHz


def test_footprint_increases_with_altitude(iss_predictor):
    pred, _ = iss_predictor
    assert pred.footprint_radius_km(400) < pred.footprint_radius_km(1500)
    assert 2000 < pred.footprint_radius_km(420) < 2600


def test_maidenhead_roundtrip():
    g = latlon_to_grid(39.93, -74.89)
    assert g.upper().startswith("FM29")
    lat, lon = grid_to_latlon(g)
    assert abs(lat - 39.93) < 0.5
    assert abs(lon - (-74.89)) < 0.5


def test_grid_known_values():
    # London ~ IO91
    assert latlon_to_grid(51.5, -0.1).upper().startswith("IO91")
