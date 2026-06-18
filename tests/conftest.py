"""Shared pytest fixtures for the OrbitDeck test suite.

Non-fixture helpers live in tests/_helpers.py.
"""

import json

import pytest

from orbitdeck.engine import SatDb, Predictor, Observer


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
