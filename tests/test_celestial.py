"""Celestial-body, Sun/Moon and illumination tests.

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


def test_analysis_sun_sync_detection():
    from orbitdeck.engine import analysis as A
    # a ~98 deg, 14.8 rev/day SSO should come out sun-synchronous
    node, _ = A.j2_rates(14.8, 97.9, 0.001)
    assert A.is_sun_synchronous(node) is True

def test_fo29_illumination_not_all_dark():
    import json, datetime
    from orbitdeck.gui.store import Store
    from orbitdeck.engine import SatDb
    omm = [{"OBJECT_NAME": "FO-29", "OBJECT_ID": "1996-046B",
            "EPOCH": datetime.datetime.now(datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.000000"),
            "MEAN_MOTION": 12.78, "ECCENTRICITY": 0.0351,
            "INCLINATION": 98.56, "RA_OF_ASC_NODE": 100.0,
            "ARG_OF_PERICENTER": 180.0, "MEAN_ANOMALY": 180.0,
            "BSTAR": 0.0001, "NORAD_CAT_ID": 24278, "REV_AT_EPOCH": 40000,
            "ELEMENT_SET_NO": 999}]
    st = Store()
    st.db.load_gp_json(json.dumps(omm))
    s = st.db.sats[0]
    st.pred.set_sat(s)
    import time
    t0 = time.time()
    lit = sum(1 for k in range(96)
              if st.pred.sunlit_at(t0 + (k / 96) * s.period_min * 60))
    # should be a healthy mix, not all-dark
    assert 10 < lit < 96

def test_radec_to_azel_basics():
    import time
    from orbitdeck.engine import celestial as CE
    # an object at the observer's zenith: its Dec equals the latitude and its
    # hour angle is zero. Construct RA so HA=0 at this instant.
    lat, lon = 40.0, -75.0
    t = time.time()
    jd = CE.jd_of(t)
    lst = (CE._gmst_rad(jd) + lon * CE.DEG)
    import math
    ra = math.degrees(lst) % 360.0           # HA = LST - RA = 0
    # an object at Dec = latitude with HA = 0 sits at the observer's zenith
    az, el = CE.radec_to_azel(ra, lat, lat, lon, t)
    # at the zenith the elevation should be ~90 deg
    assert el > 88.0

def test_planet_positions_reasonable():
    import time
    from orbitdeck.engine import celestial as CE
    t = time.time()
    for p in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        rd = CE.planet_radec(p, t)
        assert rd is not None
        ra, dec = rd
        assert 0.0 <= ra < 360.0
        assert -90.0 <= dec <= 90.0
        ae = CE.planet_azel(p, 38.9, -77.0, t)
        assert 0.0 <= ae[0] < 360.0
        assert -90.0 <= ae[1] <= 90.0
    # Mercury and Venus are inferior planets: they never stray far from the Sun,
    # so their ecliptic elongation stays modest. Just sanity-check finiteness.
    assert CE.planet_radec("Pluto", t) is None     # not in our table

def test_subsolar_point_tracks_season(iss_predictor):
    """The terminator's subsolar latitude (used to shade the globe night side)
    must track the seasons: ~+23.4 deg at the June solstice, ~-23.4 at December,
    ~0 at an equinox."""
    from orbitdeck.engine.predict import (_sun_eci_unit, jd_of,
                                          _teme_to_ecef_lla)
    import datetime as _dt

    def subsolar(iso):
        t = _dt.datetime.fromisoformat(iso).replace(
            tzinfo=_dt.timezone.utc).timestamp()
        jd = jd_of(t)
        sx, sy, sz = _sun_eci_unit(jd)
        lat, lon, _ = _teme_to_ecef_lla((sx * 1e6, sy * 1e6, sz * 1e6), jd)
        return lat, lon

    jlat, _ = subsolar("2024-06-21T12:00:00")
    dlat, _ = subsolar("2024-12-21T12:00:00")
    elat, _ = subsolar("2024-03-20T12:00:00")
    assert jlat == pytest.approx(23.4, abs=0.6)
    assert dlat == pytest.approx(-23.4, abs=0.6)
    assert elat == pytest.approx(0.0, abs=1.5)
