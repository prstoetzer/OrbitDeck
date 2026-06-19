"""Orbital analysis, nodes, grids, store and GP-source tests.

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

def test_decay_range_brackets_nominal():
    from orbitdeck.engine import analysis as A
    mm = 15.50103472
    nominal = A.estimate_decay_days(0.00025, mm, 0.0004, dens_scale=1.0)
    fast = A.estimate_decay_days(0.00025, mm, 0.0004, dens_scale=2.5)
    slow = A.estimate_decay_days(0.00025, mm, 0.0004, dens_scale=0.4)
    # higher density (solar max) -> shorter life; lower -> longer
    assert fast < nominal < slow

def test_net_builds_verifying_ssl_context():
    from orbitdeck.gui import net
    ctx = net._context()
    # a real, certificate-verifying context (not an unverified one)
    import ssl
    assert ctx is not None
    assert ctx.verify_mode == ssl.CERT_REQUIRED

def test_gp_source_url_resolution(tmp_path=None):
    import sys
    import importlib
    import tempfile
    import os
    d = tempfile.mkdtemp()
    import orbitdeck.gui.store as ST
    saved = {a: getattr(ST, a) for a in
             ("CONFIG_DIR", "CONFIG_PATH", "GP_CACHE", "TX_CACHE",
              "SPACEWX_CACHE", "MANUAL_SATS", "MANUAL_TX")}
    ST.CONFIG_DIR = d
    for a, fn in (("CONFIG_PATH", "config.json"), ("GP_CACHE", "gp.json"),
                  ("TX_CACHE", "tx.json"), ("SPACEWX_CACHE", "sw.json"),
                  ("MANUAL_SATS", "manual_sats.json"),
                  ("MANUAL_TX", "manual_tx.json")):
        setattr(ST, a, os.path.join(d, fn))
    try:
        s = ST.Store()
        assert s.gp_source_url()[1] == "AMSAT"
        s.gp_source = {"kind": "celestrak", "group": "stations"}
        url, label = s.gp_source_url()
        assert "GROUP=stations" in url and "CelesTrak" in label
        s.gp_source = {"kind": "custom", "url": "https://x.test/gp.json"}
        assert s.gp_source_url()[0] == "https://x.test/gp.json"
        s.gp_source = {"kind": "custom", "url": ""}     # empty -> AMSAT
        assert s.gp_source_url()[1] == "AMSAT"
    finally:
        for a, v in saved.items():
            setattr(ST, a, v)

def test_gp_update_handles_celestrak_errors():
    """CelesTrak can return HTTP 200 with a non-JSON error/rate-limit body, or an
    empty array. Neither should wipe the working catalog or raise a cryptic
    JSON error -- update_gp_online should raise a clear ValueError and leave the
    catalog intact."""
    import os
    import json
    import tempfile
    import orbitdeck.gui.store as ST
    d = tempfile.mkdtemp()
    saved = {a: getattr(ST, a) for a in
             ("CONFIG_DIR", "CONFIG_PATH", "GP_CACHE", "TX_CACHE",
              "SPACEWX_CACHE", "MANUAL_SATS", "MANUAL_TX")}
    ST.CONFIG_DIR = d
    for a, fn in (("CONFIG_PATH", "config.json"), ("GP_CACHE", "gp.json"),
                  ("TX_CACHE", "tx.json"), ("SPACEWX_CACHE", "sw.json"),
                  ("MANUAL_SATS", "ms.json"), ("MANUAL_TX", "mt.json")):
        setattr(ST, a, os.path.join(d, fn))
    orig_http = ST._http_get
    try:
        s = ST.Store()
        s.gp_source = {"kind": "celestrak", "group": "amateur"}
        base = s.db.count()
        assert base > 0
        for body in ("Rate limit exceeded. Try later.",
                     "Invalid query: empty result.",
                     "<html>503</html>", "[]"):
            ST._http_get = lambda url, timeout=30, b=body: b
            raised = False
            try:
                s.update_gp_online()
            except ValueError:
                raised = True
            assert raised, "expected ValueError for body %r" % body[:20]
            assert s.db.count() == base, "catalog was wiped by a bad fetch"
        # a good payload still works
        good = json.dumps([{"OBJECT_NAME": "T", "NORAD_CAT_ID": 88888,
                            "EPOCH": "2026-06-14T12:00:00.000000",
                            "MEAN_MOTION": 14.5, "ECCENTRICITY": 0.001,
                            "INCLINATION": 51.6, "RA_OF_ASC_NODE": 10,
                            "ARG_OF_PERICENTER": 90, "MEAN_ANOMALY": 180,
                            "BSTAR": 0.0, "REV_AT_EPOCH": 1,
                            "ELEMENT_SET_NO": 1}])
        ST._http_get = lambda url, timeout=30: good
        assert s.update_gp_online() == 1
    finally:
        ST._http_get = orig_http
        for a, v in saved.items():
            setattr(ST, a, v)

def test_ascending_nodes_equator_crossings():
    """Ascending-node finder: one crossing per orbit, sub-latitude ~0 at each
    crossing, and westward longitude regression for a prograde LEO."""
    import time
    from orbitdeck.gui.store import Store
    st = Store()
    s = st.db.sats[0]              # ISS-like LEO from the sample catalog
    st.pred.set_sat(s)
    t0 = time.time()
    nodes = st.pred.ascending_nodes(t0, t0 + 7 * 86400)
    # ~ (7 days * 1440 min) / period crossings
    expected = 7 * 1440.0 / s.period_min
    assert abs(len(nodes) - expected) <= 2
    # each crossing is at the equator (sub-lat ~ 0) and ascending
    for tc, lon in nodes[:5]:
        lat = st.pred.subpoint_at(tc)[0]
        assert abs(lat) < 0.5
        assert -180.0 <= lon <= 180.0
    # spacing between successive ascending nodes ~ one orbital period
    if len(nodes) >= 2:
        dt_min = (nodes[1][0] - nodes[0][0]) / 60.0
        assert abs(dt_min - s.period_min) < 1.0
        # prograde LEO regresses westward (~ -360/rev_per_day per orbit)
        dlon = ((nodes[1][1] - nodes[0][1] + 180) % 360) - 180
        assert dlon < 0

def test_crossings_list_matches_node_finder():
    """The Crossings List page data is just the ascending-node finder formatted
    for display: same count, same chronological order, longitudes in range."""
    import time
    from orbitdeck.gui.store import Store
    st = Store()
    s = st.db.sats[0]
    st.pred.set_sat(s)
    t0 = time.time()
    nodes = st.pred.ascending_nodes(t0, t0 + 7 * 86400)
    assert len(nodes) > 0
    # strictly increasing in time
    times = [tc for tc, _ in nodes]
    assert all(b > a for a, b in zip(times, times[1:]))
    # all within the requested window and longitudes valid
    assert all(t0 <= tc <= t0 + 7 * 86400 for tc in times)
    assert all(-180.0 <= lon <= 180.0 for _, lon in nodes)

def test_descending_nodes():
    """descending_nodes finds southbound equator crossings, roughly as many as
    ascending nodes over the same window, each going + to - in latitude."""
    import time
    from orbitdeck.gui.store import Store
    st = Store()
    s = st.db.sats[0]
    st.pred.set_sat(s)
    t = time.time()
    asc = st.pred.ascending_nodes(t, t + 86400)
    desc = st.pred.descending_nodes(t, t + 86400)
    assert len(desc) > 0
    assert abs(len(asc) - len(desc)) <= 1
    for tc, lon in desc[:3]:
        assert st.pred.subpoint_at(tc - 60)[0] > st.pred.subpoint_at(tc + 60)[0]
        assert -180 <= lon <= 180

def test_min_el_persists_in_config():
    """A custom minimum elevation round-trips through the store's saved config."""
    import json
    import tempfile
    import os
    import orbitdeck.gui.store as store_mod
    from orbitdeck.gui.store import Store
    d = tempfile.mkdtemp()
    saved_dir, saved_path = store_mod.CONFIG_DIR, store_mod.CONFIG_PATH
    store_mod.CONFIG_DIR = d
    store_mod.CONFIG_PATH = os.path.join(d, "config.json")
    try:
        st = Store()
        st.min_el = 15.0
        st.save_config()
        with open(store_mod.CONFIG_PATH) as f:
            assert json.load(f).get("min_el") == 15.0
    finally:
        store_mod.CONFIG_DIR, store_mod.CONFIG_PATH = saved_dir, saved_path

def test_omm_parsing_celestrak_keywords():
    """OrbitDeck parses the CCSDS OMM keywords CelesTrak's gp.php JSON uses,
    including microsecond EPOCH, per the GP data-format documentation."""
    import json
    from orbitdeck.engine.satdb import SatDb
    omm = [{
        "OBJECT_NAME": "ISS (ZARYA)", "OBJECT_ID": "1998-067A",
        "EPOCH": "2026-06-12T19:23:54.123456", "MEAN_MOTION": 15.50103472,
        "ECCENTRICITY": 0.0004364, "INCLINATION": 51.6393,
        "RA_OF_ASC_NODE": 210.0, "ARG_OF_PERICENTER": 80.0,
        "MEAN_ANOMALY": 280.0, "NORAD_CAT_ID": 25544, "BSTAR": 0.00012345,
        "MEAN_MOTION_DOT": 0.00001234, "MEAN_MOTION_DDOT": 0.0,
        "REV_AT_EPOCH": 50001, "ELEMENT_SET_NO": 999,
    }]
    db = SatDb()
    assert db.load_gp_json(json.dumps(omm)) == 1
    s = db.sats[0]
    assert s.norad == 25544
    assert s.intl_des == "1998-067A"
    assert abs(s.mean_motion - 15.50103472) < 1e-8
    assert abs(s.ecc - 0.0004364) < 1e-9
    assert abs(s.incl - 51.6393) < 1e-6
    # EPOCH parsed to the microsecond
    import datetime as dt
    got = dt.datetime.fromtimestamp(s.epoch_unix, dt.timezone.utc)
    assert got.year == 2026 and got.month == 6 and got.day == 12
    assert got.hour == 19 and got.minute == 23 and got.second == 54

def test_omm_supports_6_and_9_digit_catalog_numbers():
    """The OMM/JSON format exists specifically to carry catalog numbers beyond
    5 digits. OrbitDeck must store and look them up as integers (no TLE-style
    truncation), and tolerate null OBJECT_NAME/OBJECT_ID for analyst objects."""
    import json
    from orbitdeck.engine.satdb import SatDb
    omm = [
        {"OBJECT_NAME": "FENCE-OBJ", "OBJECT_ID": "2026-001A",
         "EPOCH": "2026-06-12T00:00:00", "MEAN_MOTION": 15.0,
         "ECCENTRICITY": 0.0001, "INCLINATION": 53.0, "RA_OF_ASC_NODE": 1.0,
         "ARG_OF_PERICENTER": 1.0, "MEAN_ANOMALY": 1.0,
         "NORAD_CAT_ID": 270123, "BSTAR": 0.0, "MEAN_MOTION_DOT": 0.0,
         "MEAN_MOTION_DDOT": 0.0, "REV_AT_EPOCH": 1, "ELEMENT_SET_NO": 1},
        {"OBJECT_NAME": None, "OBJECT_ID": None,
         "EPOCH": "2026-06-12T00:00:00", "MEAN_MOTION": 15.0,
         "ECCENTRICITY": 0.0001, "INCLINATION": 53.0, "RA_OF_ASC_NODE": 1.0,
         "ARG_OF_PERICENTER": 1.0, "MEAN_ANOMALY": 1.0,
         "NORAD_CAT_ID": 799001234, "BSTAR": 0.0, "MEAN_MOTION_DOT": 0.0,
         "MEAN_MOTION_DDOT": 0.0, "REV_AT_EPOCH": 1, "ELEMENT_SET_NO": 1},
    ]
    db = SatDb()
    assert db.load_gp_json(json.dumps(omm)) == 2
    assert db.get(270123) is not None        # 6-digit
    assert db.get(799001234) is not None      # 9-digit
    assert db.get(799001234).name == ""       # null name tolerated

def test_celestrak_uses_org_domain_and_json_format():
    """OrbitDeck queries the canonical .org domain with FORMAT=json (avoiding the
    301 redirect from .com and the TLE 5-digit limit)."""
    from orbitdeck.gui.store import CELESTRAK_BASE
    assert CELESTRAK_BASE.startswith("https://celestrak.org/")
    assert "FORMAT=json" in CELESTRAK_BASE
    assert "gp.php" in CELESTRAK_BASE
    assert ".com" not in CELESTRAK_BASE

def test_store_multisite_helpers():
    from orbitdeck.gui.store import Store
    st = Store()
    # rename primary
    st.set_obs_name("Base")
    assert st.obs_name == "Base"
    # add sites with unique-name handling
    n1 = st.add_site("Hill", 40.0, -75.0, 100)
    n2 = st.add_site("Hill", 41.0, -76.0, 0)
    assert n1 == "Hill" and n2 == "Hill 2"
    # all_sites lists the primary first
    alls = st.all_sites()
    assert alls[0][0] == "Base"
    assert len(alls) == 1 + len(st.sites)
    # remove
    before = len(st.sites)
    st.remove_site(0)
    assert len(st.sites) == before - 1

def test_listing_two_observer_matches_look(iss_predictor):
    """The two-observer stepped listing's first station must reproduce look(),
    and with the second station set to the same site both columns must agree."""
    from orbitdeck.engine.predict import Observer
    pred, sat = iss_predictor
    t0 = sat.epoch_unix
    dx = Observer(lat=39.93, lon=-74.89, alt_m=20, valid=True)   # = primary
    rows = pred.listing_rows_two(t0, 60.0, 5, dx)
    assert len(rows) == 5
    r0 = rows[0]
    L = pred.look(t0)
    assert r0["az1"] == pytest.approx(L.az, abs=0.05)
    assert r0["el1"] == pytest.approx(L.el, abs=0.05)
    # identical observers -> identical columns
    assert r0["az2"] == pytest.approx(r0["az1"], abs=0.01)
    assert r0["el2"] == pytest.approx(r0["el1"], abs=0.01)

def test_listing_visible_only_filters(iss_predictor):
    """visible_only must drop samples below the horizon for the one-observer
    listing while leaving at least one in-pass sample over a long window."""
    pred, sat = iss_predictor
    t0 = sat.epoch_unix
    full = pred.listing_rows(t0, 60.0, 24 * 60, visible_only=False)
    vis = pred.listing_rows(t0, 60.0, 24 * 60, visible_only=True)
    assert len(full) == 24 * 60
    assert 0 < len(vis) < len(full)
    assert all(r["el"] >= 0.0 for r in vis)

def test_version_is_0_35_2():
    """The package version was bumped for this release."""
    import orbitdeck
    assert orbitdeck.__version__ == "0.35.2"
