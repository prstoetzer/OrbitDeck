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


def test_sample_epochs_are_fresh():
    """Bundled demo elements must be stamped near 'today' so pass geometry is
    self-consistent rather than years stale."""
    import datetime as _dt
    import json as _json
    from orbitdeck.data.sample_data import sample_gp_json
    now = _dt.datetime.now(_dt.timezone.utc)
    for rec in _json.loads(sample_gp_json()):
        ep = _dt.datetime.strptime(rec["EPOCH"][:19], "%Y-%m-%dT%H:%M:%S")
        ep = ep.replace(tzinfo=_dt.timezone.utc)
        age_days = abs((now - ep).total_seconds()) / 86400.0
        assert age_days < 2, "%s epoch is %.1f days from now" % (
            rec.get("AMSAT_NAME"), age_days)


def test_store_rejects_stale_cache(tmp_path=None):
    """A stale on-disk cache should be discarded in favor of fresh sample data."""
    import os
    import json as _json
    import tempfile
    import orbitdeck.gui.store as store_mod
    tmp = tempfile.mkdtemp()
    store_mod.CONFIG_DIR = tmp
    store_mod.CONFIG_PATH = os.path.join(tmp, "config.json")
    store_mod.GP_CACHE = os.path.join(tmp, "gp.json")
    stale = [{
        "AMSAT_NAME": "OLD", "OBJECT_NAME": "OLD", "OBJECT_ID": "x",
        "EPOCH": "2020-01-01T00:00:00.000000", "MEAN_MOTION": 15.5,
        "ECCENTRICITY": 0.0004, "INCLINATION": 51.6, "RA_OF_ASC_NODE": 210,
        "ARG_OF_PERICENTER": 80, "MEAN_ANOMALY": 280, "BSTAR": 0.00025,
        "MEAN_MOTION_DOT": 0.0001, "MEAN_MOTION_DDOT": 0,
        "NORAD_CAT_ID": 25544, "REV_AT_EPOCH": 45000, "ELEMENT_SET_NO": 1,
    }]
    with open(store_mod.GP_CACHE, "w") as f:
        f.write(_json.dumps(stale))
    s = store_mod.Store()
    assert s.using_sample() is True       # stale cache rejected
    assert s.catalog_age_days() < 2       # fresh sample loaded instead


def test_analysis_j2_rates_iss():
    from orbitdeck.engine import analysis as A
    node, perig = A.j2_rates(15.50103472, 51.6393, 0.0004364)
    # ISS node regresses ~5 deg/day westward; perigee advances a few deg/day
    assert -6.0 < node < -4.0
    assert 2.0 < perig < 5.0
    assert A.is_sun_synchronous(node) is False


def test_analysis_sun_sync_detection():
    from orbitdeck.engine import analysis as A
    # a ~98 deg, 14.8 rev/day SSO should come out sun-synchronous
    node, _ = A.j2_rates(14.8, 97.9, 0.001)
    assert A.is_sun_synchronous(node) is True


def test_analysis_footprint_and_betastar():
    from orbitdeck.engine import analysis as A
    assert 4000 < A.footprint_diameter_km(420) < 5000
    assert A.footprint_diameter_km(1500) > A.footprint_diameter_km(420)
    assert 15 < A.beta_star_deg(420) < 25


def test_analysis_anomaly_chain():
    from orbitdeck.engine import analysis as A
    ma = A.mean_anomaly_now_deg(280.0, 15.5, 1000.0, 0.0)
    assert 0 <= ma < 360
    nu = A.true_anomaly_deg(ma, 0.0004)
    assert abs(nu - ma) < 1.0          # near-circular: true ~ mean
    u = A.arg_of_latitude_deg(80.0, nu)
    assert 0 <= u < 360


def test_analysis_decay_iss_order_of_magnitude():
    from orbitdeck.engine import analysis as A
    # un-reboosted ISS-class at B*~2.5e-4 -> months-to-a-couple-years, not stable
    d = A.estimate_decay_days(0.00025, 15.50103472, 0.0004364)
    assert 30 < d < 3000


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


def test_spacewx_labels_and_ap():
    from orbitdeck.gui import spacewx as W
    assert W.flux_label(140)[1] == "good"
    assert W.flux_label(80)[1] == "low"
    assert W.kp_label(1)[0] == "quiet"
    assert W.kp_label(6.5)[0] == "moderate storm"
    assert W.kp_label(8)[0] == "major storm"
    # Kp->ap monotonic and matches table anchors
    assert W._kp_to_ap(0) == 0
    assert W._kp_to_ap(4) == 27
    assert W._kp_to_ap(9) == 400
    out = W.outlook(140, 6)
    assert "storm" in out.lower()


def test_transponder_bulk_cache(tmp_path=None):
    import os, json, tempfile
    import orbitdeck.gui.store as store_mod
    tmp = tempfile.mkdtemp()
    store_mod.CONFIG_DIR = tmp
    store_mod.CONFIG_PATH = os.path.join(tmp, "config.json")
    store_mod.GP_CACHE = os.path.join(tmp, "gp.json")
    store_mod.TX_CACHE = os.path.join(tmp, "transmitters.json")
    s = store_mod.Store()
    # simulate a cached bulk SatNOGS dump grouped by NORAD
    dump = {"25544": [{"description": "Voice", "downlink_low": 437800000,
                       "uplink_low": 145990000, "mode": "FM",
                       "status": "active"}]}
    with open(store_mod.TX_CACHE, "w") as f:
        json.dump(dump, f)
    n = s._apply_tx_cache()
    iss = s.db.get(25544)
    assert n >= 1
    assert iss is not None and len(iss.transponders) == 1
    assert iss.transponders[0].downlink == 437800000


def test_decay_range_brackets_nominal():
    from orbitdeck.engine import analysis as A
    mm = 15.50103472
    nominal = A.estimate_decay_days(0.00025, mm, 0.0004, dens_scale=1.0)
    fast = A.estimate_decay_days(0.00025, mm, 0.0004, dens_scale=2.5)
    slow = A.estimate_decay_days(0.00025, mm, 0.0004, dens_scale=0.4)
    # higher density (solar max) -> shorter life; lower -> longer
    assert fast < nominal < slow


def test_spacewx_ka_populate_from_feeds():
    import json
    from orbitdeck.gui import spacewx as W
    def fake(url, timeout=20):
        if "f107" in url:
            return json.dumps([{"flux": "138.2"}])
        if "planetary_k_index_1m" in url:
            return json.dumps([{"kp_index": 3.67}, {"kp_index": 4.33}])
        if "daily-geomagnetic" in url:
            return "# h\n2026 06 14   27   4 4 5 4 3 3 3 2\n"
        return "[]"
    orig = W._http_get
    W._http_get = fake
    try:
        d = W.fetch()
    finally:
        W._http_get = orig
    assert abs(d["kp"] - 4.33) < 0.01
    assert abs(d["a_index"] - 27) < 0.01      # A populates from DGD
    assert abs(d["flux"] - 138.2) < 0.1


def test_spacewx_ka_fallback_products_array():
    import json
    from orbitdeck.gui import spacewx as W
    def fake(url, timeout=20):
        if "planetary_k_index_1m" in url:
            return "[]"
        if "noaa-planetary-k-index" in url:
            return json.dumps([["time_tag", "Kp", "a_running", "n"],
                               ["2026-06-14 09:00:00", "5.33", "56", "8"]])
        if "f107" in url:
            return json.dumps([{"flux": "120"}])
        return "# none\n"
    orig = W._http_get
    W._http_get = fake
    try:
        d = W.fetch()
    finally:
        W._http_get = orig
    assert abs(d["kp"] - 5.33) < 0.01
    assert d["a_index"] is not None           # derived from Kp


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
