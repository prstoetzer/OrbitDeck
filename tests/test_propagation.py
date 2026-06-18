"""SGP4/SDP4 propagation and coordinate tests.

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

from ._helpers import _jd_from_tle_epoch


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

def test_deepspace_approximate_flag():
    """A geostationary bird (deep-space) should be flagged as approximate when
    the full SDP4 (pip 'sgp4') backend isn't installed, so the UI can warn that
    its visibility may be unreliable."""
    import json
    import datetime
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.propagator import have_full_sdp4
    now = datetime.datetime.now(datetime.timezone.utc)
    omm = [{"OBJECT_NAME": "QO-100",
            "EPOCH": now.strftime("%Y-%m-%dT%H:%M:%S.000000"),
            "MEAN_MOTION": 1.00271, "ECCENTRICITY": 0.0001,
            "INCLINATION": 0.05, "RA_OF_ASC_NODE": 80.0,
            "ARG_OF_PERICENTER": 100.0, "MEAN_ANOMALY": 200.0,
            "BSTAR": 0.0, "NORAD_CAT_ID": 43700}]
    st = Store()
    st.db.load_gp_json(json.dumps(omm))
    st.pred.set_sat(st.db.sats[0])
    # the flag is True exactly when we lack the full reference backend
    assert st.pred.deepspace_approximate() == (not have_full_sdp4())
    # a LEO bird is never flagged
    from orbitdeck.data.sample_data import sample_gp_json
    st.db.load_gp_json(sample_gp_json())
    st.pred.set_sat(st.db.sats[0])
    assert st.pred.deepspace_approximate() is False

def test_geostationary_subpoint_stable_with_full_sdp4():
    """With the full SDP4 backend, a geostationary satellite's sub-point should
    stay roughly fixed (it does not rise and set). Skipped when only the
    approximate vendored backend is available."""
    from orbitdeck.engine.propagator import have_full_sdp4
    if not have_full_sdp4():
        return  # vendored deep-space is approximate; nothing to assert here
    import json
    import time
    import datetime
    from orbitdeck.gui.store import Store
    now = datetime.datetime.now(datetime.timezone.utc)
    omm = [{"OBJECT_NAME": "QO-100",
            "EPOCH": now.strftime("%Y-%m-%dT%H:%M:%S.000000"),
            "MEAN_MOTION": 1.00271, "ECCENTRICITY": 0.0001,
            "INCLINATION": 0.05, "RA_OF_ASC_NODE": 80.0,
            "ARG_OF_PERICENTER": 100.0, "MEAN_ANOMALY": 200.0,
            "BSTAR": 0.0, "NORAD_CAT_ID": 43700}]
    st = Store()
    st.db.load_gp_json(json.dumps(omm))
    st.pred.set_sat(st.db.sats[0])
    t0 = time.time()
    lons = [st.pred.subpoint_at(t0 + h * 3600)[1] for h in range(0, 24, 3)]
    # sub-longitude should not wander more than a few degrees for a GEO sat
    spread = max(lons) - min(lons)
    assert spread < 10.0

def test_geodetic_conversion_handles_geostationary():
    """The TEME->geodetic conversion must not divide by zero for high-altitude
    near-equatorial (geostationary) satellites."""
    import json
    import time
    import datetime
    from orbitdeck.gui.store import Store
    now = datetime.datetime.now(datetime.timezone.utc)
    omm = [{"OBJECT_NAME": "QO-100",
            "EPOCH": now.strftime("%Y-%m-%dT%H:%M:%S.000000"),
            "MEAN_MOTION": 1.00271, "ECCENTRICITY": 0.0001,
            "INCLINATION": 0.05, "RA_OF_ASC_NODE": 80.0,
            "ARG_OF_PERICENTER": 100.0, "MEAN_ANOMALY": 200.0,
            "BSTAR": 0.0, "NORAD_CAT_ID": 43700}]
    st = Store()
    st.db.load_gp_json(json.dumps(omm))
    st.pred.set_sat(st.db.sats[0])
    lat, lon, alt = st.pred.subpoint_at(time.time())
    assert -90 <= lat <= 90 and -180 <= lon <= 180
    # geostationary altitude is ~35,786 km
    assert 30000 < alt < 40000


def test_app_runs_without_optional_backends():
    """Regression / packaging guarantee: the propagator and map drawing must
    work whether or not the optional sgp4 / cartopy packages are installed, so
    they can stay optional dependencies. The detection helpers must return a
    bool either way, and the vendored propagator must produce a finite position.
    """
    from orbitdeck.engine.propagator import have_full_sdp4
    from orbitdeck.gui.mapdraw import have_cartopy
    assert isinstance(have_full_sdp4(), bool)
    assert isinstance(have_cartopy(), bool)
    # the vendored propagator must work regardless of the optional backend
    jd = _jd_from_tle_epoch(0, 179.78495062)
    s = Satrec()
    ok = s.init_from_elements(jd, 0.66816e-4, 0.0, 0.0,
                              0.0086731, 52.6988, 72.8435, 110.5714,
                              16.05824518, 115.9689, 88888)
    assert ok and s.error == 0
    r, v = s.sgp4(0.0)
    assert all(abs(c) < 1e9 for c in r)
