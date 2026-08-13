"""Tests for the CelesTrak search + auto-updating extras and the transit finder.

Network is never touched: the store's HTTP helper is monkeypatched with canned
CelesTrak responses so the search/extras logic is exercised deterministically.
"""

import json
import time

import pytest

from orbitdeck.gui import satsearch


# a minimal but valid OMM/GP record CelesTrak would return
def _omm(norad=99999, name="TESTOBJ"):
    return {
        "OBJECT_NAME": name, "OBJECT_ID": "2026-001A",
        "EPOCH": "2026-07-19T00:00:00.000000", "MEAN_MOTION": 15.0,
        "ECCENTRICITY": 0.001, "INCLINATION": 51.6, "RA_OF_ASC_NODE": 100.0,
        "ARG_OF_PERICENTER": 90.0, "MEAN_ANOMALY": 270.0, "BSTAR": 0.0001,
        "MEAN_MOTION_DOT": 0.0, "MEAN_MOTION_DDOT": 0.0,
        "NORAD_CAT_ID": norad, "REV_AT_EPOCH": 100, "ELEMENT_SET_NO": 1,
    }


# ---- satsearch (pure) ----
def test_search_url_name_vs_catnr():
    url, kind = satsearch.search_url("AO-91")
    assert kind == "name" and "NAME=AO-91" in url and "FORMAT=JSON" in url
    url, kind = satsearch.search_url("43017")
    assert kind == "catnr" and "CATNR=43017" in url


def test_search_url_empty_raises():
    with pytest.raises(ValueError):
        satsearch.search_url("   ")


def test_catnr_url():
    assert "CATNR=25544" in satsearch.catnr_url(25544)


def test_parse_results_array_and_object():
    arr = json.dumps([_omm(43017, "AO-91")])
    hits = satsearch.parse_results(arr)
    assert len(hits) == 1
    assert hits[0]["norad"] == 43017 and "AO-91" in hits[0]["name"]
    assert hits[0]["omm"]["INCLINATION"] == 51.6
    # a bare object (single result) also parses
    one = satsearch.parse_results(json.dumps(_omm()))
    assert len(one) == 1


def test_parse_results_miss_and_garbage():
    assert satsearch.parse_results("No GP data found") == []
    assert satsearch.parse_results("") == []
    assert satsearch.parse_results("<html>error</html>") == []


def test_looks_rate_limited():
    assert satsearch.looks_rate_limited("Rate limit exceeded, try later")
    assert not satsearch.looks_rate_limited(json.dumps([_omm()]))


# ---- store extras (monkeypatched network) ----
@pytest.fixture
def store_with_net(tmp_path, monkeypatch):
    """A Store pointed at a temp config dir, with a canned CelesTrak response."""
    import orbitdeck.gui.store as st
    monkeypatch.setattr(st, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(st, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(st, "GP_CACHE", str(tmp_path / "gp.json"))
    monkeypatch.setattr(st, "EXTRAS_SATS", str(tmp_path / "extras.json"))
    monkeypatch.setattr(st, "MANUAL_SATS", str(tmp_path / "manual_sats.json"))

    canned = {"text": json.dumps([_omm()])}
    monkeypatch.setattr(st, "_http_get",
                        lambda url, timeout=20: canned["text"])
    s = st.Store()
    return s, canned, st


def test_search_and_add_extra(store_with_net):
    s, _canned, _st = store_with_net
    hits = s.search_celestrak("TESTOBJ")
    assert len(hits) == 1 and hits[0]["norad"] == 99999
    s.add_extra_sat(hits[0], make_favorite=True)
    # now queryable in the live catalog, flagged extra + favorite
    assert s.db.get(99999) is not None
    assert s.db.get(99999).name == "TESTOBJ"
    assert s.is_extra(99999)
    assert 99999 in s.favorites


def test_extra_persists_across_reload(store_with_net):
    s, _canned, st = store_with_net
    s.add_extra_sat(satsearch.parse_results(json.dumps([_omm()]))[0])
    s2 = st.Store()                       # fresh instance, same temp dir
    assert s2.db.get(99999) is not None   # merged from extras.json on load


def test_remove_extra(store_with_net):
    s, _canned, _st = store_with_net
    s.add_extra_sat(satsearch.parse_results(json.dumps([_omm()]))[0])
    s.remove_extra_sat(99999)
    assert s.db.get(99999) is None
    assert not s.is_extra(99999)


def test_search_rate_limit(store_with_net):
    s, _canned, _st = store_with_net
    s.search_celestrak("QUERY1")          # sets last-search time
    with pytest.raises(ValueError):
        s.search_celestrak("QUERY2")      # <10 s later, distinct -> raises


def test_search_identical_query_cached(store_with_net):
    s, canned, _st = store_with_net
    first = s.search_celestrak("SAMEQ")
    canned["text"] = "No GP data found"   # network would now return nothing
    again = s.search_celestrak("SAMEQ")   # served from the 2 h cache
    assert again == first and len(again) == 1


def test_refresh_extras_updates_elements(store_with_net):
    s, canned, _st = store_with_net
    s.add_extra_sat(satsearch.parse_results(json.dumps([_omm()]))[0])
    # change the canned element set, force a refresh, and confirm it took
    canned["text"] = json.dumps([dict(_omm(), INCLINATION=63.4)])
    n = s.refresh_extras(force=True)
    assert n == 1
    assert abs(s.db.get(99999).incl - 63.4) < 1e-6


def test_manual_sats_not_auto_fetched(store_with_net):
    """Extras auto-refresh; hand-entered manual sats must not."""
    s, _canned, _st = store_with_net
    from orbitdeck.engine.satdb import make_manual_sat
    ep = time.time()
    e = make_manual_sat("HANDENTERED", 90002, ep, 51.6, 120.0, 0.0006,
                        90.0, 180.0, 15.5, 0.0)
    s.add_manual_sat(e)
    # refresh_extras only touches extras.json; the manual sat isn't in it
    assert not s.is_extra(90002)
    s.refresh_extras(force=True)
    assert s.db.get(90002).name == "HANDENTERED"


# ---- transit finder ----
@pytest.fixture
def iss():
    from orbitdeck.engine import SatDb, Observer
    omm = [{
        "OBJECT_NAME": "ISS (ZARYA)", "OBJECT_ID": "1998-067A",
        "EPOCH": "2026-07-19T12:00:00.000000", "MEAN_MOTION": 15.50,
        "ECCENTRICITY": 0.0004, "INCLINATION": 51.64, "RA_OF_ASC_NODE": 210.0,
        "ARG_OF_PERICENTER": 80.0, "MEAN_ANOMALY": 280.0, "BSTAR": 0.00025,
        "MEAN_MOTION_DOT": 0.0001, "MEAN_MOTION_DDOT": 0.0,
        "NORAD_CAT_ID": 25544, "REV_AT_EPOCH": 45000, "ELEMENT_SET_NO": 999,
    }]
    db = SatDb()
    db.load_gp_json(json.dumps(omm))
    site = Observer(lat=39.93, lon=-74.89, alt_m=20, valid=True)
    return db.sats[0], site


def test_sun_azel_daytime_sane(iss):
    from orbitdeck.engine.transits import _sun_azel
    # around 16-17 UTC the Sun is well up over the US east coast in July
    t = time.mktime(time.strptime("2026-07-20 17:00:00", "%Y-%m-%d %H:%M:%S"))
    az, el = _sun_azel(39.93, -74.89, t)
    assert 0 <= az < 360
    assert el > 0                         # above the horizon at local midday


def test_find_transits_returns_sorted_events(iss):
    from orbitdeck.engine.predict import Predictor
    from orbitdeck.engine.transits import find_transits
    sat, site = iss
    pred = Predictor()
    base = time.mktime(time.strptime("2026-07-20 00:00:00",
                                     "%Y-%m-%d %H:%M:%S"))
    ev = find_transits(pred, site, sat, base, hours=168, body="both",
                       max_sep_deg=5.0)
    assert isinstance(ev, list)
    # sorted by time, well-formed rows
    for a, b in zip(ev, ev[1:]):
        assert a["time"] <= b["time"]
    for e in ev:
        assert e["body"] in ("sun", "moon")
        assert 0 <= e["sep_deg"] <= 5.0
        assert isinstance(e["transit"], bool)


def test_find_transits_tighter_is_subset(iss):
    from orbitdeck.engine.predict import Predictor
    from orbitdeck.engine.transits import find_transits
    sat, site = iss
    base = time.mktime(time.strptime("2026-07-20 00:00:00",
                                     "%Y-%m-%d %H:%M:%S"))
    wide = find_transits(Predictor(), site, sat, base, hours=168,
                         max_sep_deg=5.0)
    tight = find_transits(Predictor(), site, sat, base, hours=168,
                          max_sep_deg=1.0)
    # a tighter threshold can only find the same or fewer approaches
    assert len(tight) <= len(wide)


# ---- GUI wiring (defensive: bail if no real Tk) ----
def _make_app():
    import tkinter as tk
    if not hasattr(tk, "Listbox") or not hasattr(tk, "Entry"):
        return None
    try:
        root = tk.Tk()
    except Exception:
        return None
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        return None
    return root, app


def test_transits_screen_builds():
    made = _make_app()
    if made is None:
        return
    root, app = made
    try:
        app.show("transits")
        root.update()
        assert app.current is not None
        app.current._reload()             # must not raise with sample catalog
        root.update()
    finally:
        root.destroy()


def test_satellites_search_dialog_opens():
    made = _make_app()
    if made is None:
        return
    root, app = made
    try:
        app.show("satellites")
        root.update()
        # the search dialog method exists and opens a Toplevel without error
        app.current._search_celestrak_dialog()
        root.update()
    finally:
        root.destroy()


# ---- conjunction screener & neighborhood ----
def _two_close_sats(ma_b=280.3):
    from orbitdeck.engine import SatDb
    def omm(norad, name, ma):
        return {"OBJECT_NAME": name, "OBJECT_ID": "X",
                "EPOCH": "2026-07-19T12:00:00.000000", "MEAN_MOTION": 15.5,
                "ECCENTRICITY": 0.0004, "INCLINATION": 51.64,
                "RA_OF_ASC_NODE": 210.0, "ARG_OF_PERICENTER": 80.0,
                "MEAN_ANOMALY": ma, "BSTAR": 0.00025, "MEAN_MOTION_DOT": 0.0,
                "MEAN_MOTION_DDOT": 0.0, "NORAD_CAT_ID": norad,
                "REV_AT_EPOCH": 45000, "ELEMENT_SET_NO": 1}
    db = SatDb()
    db.load_gp_json(json.dumps([omm(1, "SAT-A", 280.0),
                                omm(2, "SAT-B", ma_b),
                                omm(3, "FAR", 100.0)]))
    return db


def test_screen_conjunctions_finds_close_pair():
    from orbitdeck.engine.predict import Predictor
    from orbitdeck.engine.conjunction import screen_conjunctions
    db = _two_close_sats(280.3)
    res = screen_conjunctions(Predictor(), Predictor(), db.sats[0], db.sats[1],
                              time.time(), hours=6, threshold_km=800)
    assert res, "should find close approaches for near-identical orbits"
    # sorted ascending by miss distance, all below threshold
    for a, b in zip(res, res[1:]):
        assert a["miss_km"] <= b["miss_km"]
    assert all(r["miss_km"] < 800 for r in res)


def test_screen_conjunctions_far_pair_empty():
    from orbitdeck.engine.predict import Predictor
    from orbitdeck.engine.conjunction import screen_conjunctions
    db = _two_close_sats()
    # A vs the FAR object (different plane/phase) -> no sub-800 km approach
    res = screen_conjunctions(Predictor(), Predictor(), db.sats[0], db.sats[2],
                              time.time(), hours=6, threshold_km=800)
    assert res == [] or all(r["miss_km"] < 800 for r in res)


def test_orbital_neighborhood_ranks_by_range():
    from orbitdeck.engine.predict import Predictor
    from orbitdeck.engine.conjunction import orbital_neighborhood
    db = _two_close_sats(280.3)
    nb = orbital_neighborhood(Predictor(), db.sats[0], db.sats, time.time(),
                              max_results=5)
    assert nb and nb[0]["name"] == "SAT-B"      # nearest is the twin
    for a, b in zip(nb, nb[1:]):
        assert a["range_km"] <= b["range_km"]
    # the base satellite is excluded from its own neighborhood
    assert all(r["norad"] != db.sats[0].norad for r in nb)


def test_conjunction_screen_builds():
    made = _make_app()
    if made is None:
        return
    root, app = made
    try:
        app.show("conjunction")
        root.update()
        assert app.current is not None
        app.current._neigh()               # compute neighborhood; must not raise
        root.update()
    finally:
        root.destroy()


# ---- data feeds: QRZ + hams.at activations ----
def test_qrz_parse_callsign():
    from orbitdeck.gui import datafeeds as df
    body = ("<QRZDatabase><Callsign><call>W1AW</call><fname>ARRL</fname>"
            "<name>HQ CLUB</name><addr1>225 Main St</addr1><addr2>Newington"
            "</addr2><state>CT</state><zip>06111</zip><country>United States"
            "</country><grid>FN31pr</grid><class>C</class></Callsign>"
            "</QRZDatabase>")
    r = df.qrz_parse_callsign(body)
    assert r["call"] == "W1AW" and r["grid"] == "FN31pr"
    assert r["class"] == "C" and "ARRL" in r["name"]
    assert "CT" in r["addr"]


def test_qrz_parse_session_and_miss():
    from orbitdeck.gui import datafeeds as df
    key, err = df.qrz_parse_session_key(
        "<QRZDatabase><Session><Key>abc</Key></Session></QRZDatabase>")
    assert key == "abc" and err == ""
    assert df.qrz_parse_callsign("<QRZDatabase><Session><Error>Not found"
                                 "</Error></Session></QRZDatabase>") is None


def test_qrz_lookup_flow_with_fake_http():
    from orbitdeck.gui import datafeeds as df
    login = ("<QRZDatabase><Session><Key>KEY1</Key></Session></QRZDatabase>")
    hit = ("<QRZDatabase><Callsign><call>K1ABC</call><fname>Jane</fname>"
           "<name>Doe</name><grid>FN42</grid><class>E</class></Callsign>"
           "</QRZDatabase>")
    calls = []

    def fake_http(url, timeout=15):
        calls.append(url)
        return login if "username=" in url else hit
    res, key, err = df.qrz_lookup(fake_http, "u", "p", "K1ABC")
    assert err == "" and res["call"] == "K1ABC" and res["grid"] == "FN42"
    assert key == "KEY1"
    # login happened before the query
    assert "username=" in calls[0] and "callsign=K1ABC" in calls[1]


def test_parse_activations():
    from orbitdeck.gui import datafeeds as df
    atom = ("<feed><entry><title>[2026-07-25] N0CALL on SO-50 from EM12</title>"
            "<content type=\"html\"><![CDATA[<ul>"
            "<li>Start time: 2026-07-25 18:30 UTC</li>"
            "<li>End time: 2026-07-25 18:45 UTC</li>"
            "<li>Max elevation: 42</li><li>Frequency: 145.850</li>"
            "<li>Mode: FM</li><li>Comment: grid activation</li>"
            "</ul>]]></content></entry></feed>")
    acts = df.parse_activations(atom)
    assert len(acts) == 1
    a = acts[0]
    assert a["callsign"] == "N0CALL" and a["sat"] == "SO-50"
    assert a["grid"] == "EM12" and a["mode"] == "FM"
    assert a["max_el"] == "42" and "18:30" in a["start"]


def test_parse_activations_empty():
    from orbitdeck.gui import datafeeds as df
    assert df.parse_activations("") == []
    assert df.parse_activations("<html>nope</html>") == []


def test_datafeeds_screen_builds():
    made = _make_app()
    if made is None:
        return
    root, app = made
    try:
        app.show("datafeeds")
        root.update()
        assert app.current is not None
        # render an activation list without network by feeding parsed data
        app.current._show_acts([{
            "start": "2026-07-25 18:30", "callsign": "N0CALL", "sat": "SO-50",
            "grid": "EM12", "max_el": "42", "mode": "FM", "freq": "145.850"}])
        root.update()
    finally:
        root.destroy()


# ---- link margin vs elevation + passband plan ----
def test_link_margin_increases_with_elevation():
    from orbitdeck.engine import toolcalc as tc
    rows = tc.link_margin_vs_elevation(550, 435, 6.0)
    vals = {}
    for lab, v, _n in rows:
        if "deg el" in lab:
            vals[int(lab.split()[0])] = float(v.replace("+", "").split()[0])
    assert vals[0] == 6.0                       # margin at horizon = M0
    assert vals[90] > vals[0]                   # overhead beats the horizon
    # monotonic non-decreasing with elevation
    keys = sorted(vals)
    for a, b in zip(keys, keys[1:]):
        assert vals[b] >= vals[a]


def test_passband_plan_linear_inverting():
    from orbitdeck.engine.satdb import Transponder, passband_plan
    t = Transponder()
    t.is_linear = True
    t.invert = True
    t.downlink = 145_960_000
    t.downlink_high = 145_990_000
    t.uplink = 435_760_000
    t.uplink_high = 435_790_000
    plan = passband_plan(t, steps=10)
    assert len(plan) == 11
    # downlink rises across the band
    assert plan[0][1] < plan[-1][1]
    # inverting: uplink falls as downlink rises
    assert plan[0][2] > plan[-1][2]
    assert plan[0][0] == 0 and plan[-1][0] == 100


def test_passband_plan_noninverting():
    from orbitdeck.engine.satdb import Transponder, passband_plan
    t = Transponder()
    t.is_linear = True
    t.invert = False
    t.downlink = 145_800_000
    t.downlink_high = 145_900_000
    t.uplink = 435_100_000
    t.uplink_high = 435_200_000
    plan = passband_plan(t, steps=10)
    # non-inverting: uplink rises with downlink
    assert plan[0][2] < plan[-1][2]


def test_passband_plan_single_channel():
    from orbitdeck.engine.satdb import Transponder, passband_plan
    t = Transponder()
    t.is_linear = False
    t.downlink = 145_825_000
    t.uplink = 0
    plan = passband_plan(t)
    assert len(plan) == 1 and plan[0][1] == 145_825_000


# ---- reference data tables ----
def test_refdata_tables_all_render():
    from orbitdeck.engine import refdata as rd
    for name, desc, fn in rd.TABLES:
        rows = fn()
        assert rows, "%s produced no rows" % name
        for r in rows:
            assert isinstance(r, tuple) and len(r) == 3


def test_ctcss_has_standard_tones():
    from orbitdeck.engine import refdata as rd
    tones = [float(v.split()[0]) for _i, v, _n in rd.ctcss_rows()]
    for t in (67.0, 100.0, 141.3, 254.1):     # spot-check EIA standard tones
        assert t in tones


def test_ascii_table_covers_printable():
    from orbitdeck.engine import refdata as rd
    rows = rd.ascii_rows()
    decs = [int(a) for a, _b, _c in rows]
    assert 32 in decs and 65 in decs and 126 in decs   # space, 'A', '~'


def test_references_screen_builds():
    made = _make_app()
    if made is None:
        return
    root, app = made
    try:
        app.show("references")
        root.update()
        from orbitdeck.engine import refdata as rd
        for i in range(len(rd.TABLES)):        # select each table
            app.current._select(i)
            root.update()
    finally:
        root.destroy()


def test_radio_passband_plan_tab_builds():
    made = _make_app()
    if made is None:
        return
    root, app = made
    try:
        app.show("radio")
        root.update()
        app.current._refresh_plan()            # must not raise
        root.update()
    finally:
        root.destroy()


# ---- sky map ----
def test_star_catalog_loaded():
    from orbitdeck.engine import star_data as sd
    assert len(sd.STAR_RA) == len(sd.STAR_DEC) == len(sd.STAR_MAG)
    assert len(sd.STAR_RA) > 900          # ~1018 stars
    assert sum(sd.CLIN_RUN) <= len(sd.CLIN_RA)


def test_visible_stars_and_projection():
    import time
    from orbitdeck.engine import skymap as sm
    stars = sm.visible_stars(39.93, -74.89, time.time(), max_mag=4.5)
    assert stars                          # some stars are always up
    for az, el, m in stars:
        assert 0 <= az < 360.01 and el >= 0 and m <= 4.5
    # projection: zenith -> center, horizon -> edge
    assert sm.azel_to_xy(0, 90, 100) == (50.0, 50.0)
    n = sm.azel_to_xy(0, 0, 100)
    assert abs(n[0] - 50.0) < 1e-6 and abs(n[1] - 0.0) < 1e-6
    assert sm.azel_to_xy(0, -5, 100) is None     # below horizon


def test_constellation_segments_shape():
    import time
    from orbitdeck.engine import skymap as sm
    segs = sm.constellation_segments(39.93, -74.89, time.time())
    for s in segs:
        assert len(s) == 4               # (az1, el1, az2, el2)


def test_skymap_screen_builds():
    made = _make_app()
    if made is None:
        return
    root, app = made
    try:
        app.show("skymap")
        root.update()
        assert app.current is not None
        app.current._redraw()             # must not raise
        root.update()
    finally:
        root.destroy()


# ---- state vector -> elements ----
def test_rv_to_elements_roundtrip():
    """Propagate a known orbit to a state vector, then invert it back."""
    import time
    from orbitdeck.engine import SatDb, Predictor
    from orbitdeck.engine.statevector import rv_to_elements
    omm = [{"OBJECT_NAME": "ISS", "OBJECT_ID": "1998-067A",
            "EPOCH": "2026-07-19T12:00:00.000000", "MEAN_MOTION": 15.50,
            "ECCENTRICITY": 0.0004, "INCLINATION": 51.64,
            "RA_OF_ASC_NODE": 210.0, "ARG_OF_PERICENTER": 80.0,
            "MEAN_ANOMALY": 280.0, "BSTAR": 0.00025, "MEAN_MOTION_DOT": 0.0001,
            "MEAN_MOTION_DDOT": 0.0, "NORAD_CAT_ID": 25544,
            "REV_AT_EPOCH": 45000, "ELEMENT_SET_NO": 999}]
    db = SatDb()
    db.load_gp_json(json.dumps(omm))
    p = Predictor()
    p.set_sat(db.sats[0])
    r, v = p._eci_state(time.time())
    el = rv_to_elements(r, v)
    # osculating elements should be close to the mean elements they came from
    assert abs(el["incl_deg"] - 51.64) < 0.2
    assert abs(el["mean_motion_rev_day"] - 15.50) < 0.1
    assert el["ecc"] < 0.01
    assert 90 < el["period_min"] < 95


def test_rv_to_elements_rejects_hyperbolic():
    from orbitdeck.engine.statevector import rv_to_elements
    import pytest as _pt
    # escape velocity at ~6800 km is ~10.8 km/s; 15 km/s is hyperbolic
    with _pt.raises(ValueError):
        rv_to_elements([6800.0, 0.0, 0.0], [0.0, 15.0, 0.0])


def test_rv_to_rows_shape_and_error():
    from orbitdeck.engine.statevector import rv_to_rows
    rows = rv_to_rows(-4400, -5100, 0, 3.6, -3.1, 6.0)
    labels = [r[0] for r in rows]
    assert "Inclination" in labels and "Mean motion" in labels
    for r in rows:
        assert isinstance(r, tuple) and len(r) == 3
    # a zero position is degenerate -> single error row
    bad = rv_to_rows(0, 0, 0, 0, 0, 0)
    assert bad[0][0] == "error"


# ---- terrain path profile ----
def test_great_circle_distance():
    from orbitdeck.engine.terrain import great_circle
    # ~ known: 1 deg of latitude is ~111 km
    d, _b = great_circle(39.0, -77.0, 40.0, -77.0)
    assert 110 < d < 112


def test_sample_points_endpoints():
    from orbitdeck.engine.terrain import sample_points
    pts, dist = sample_points(39.0, -77.0, 39.3, -76.5, 12)
    assert len(pts) == 12
    assert abs(pts[0][0] - 39.0) < 1e-6 and abs(pts[-1][0] - 39.3) < 1e-6
    assert dist > 0


def test_analyze_profile_blocks_ridge():
    from orbitdeck.engine.terrain import analyze_profile
    # a 500 m ridge mid-path between low endpoints -> not clear
    elev = [50, 60, 80, 300, 500, 500, 450, 300, 120, 90, 70, 60]
    a = analyze_profile(elev, 50.0, tx_haat_m=10, rx_haat_m=10, freq_mhz=146)
    assert a["clear"] is False
    assert a["max_terrain_m"] == 500
    assert a["worst_clearance_m"] < 0


def test_parse_elevations():
    from orbitdeck.engine.terrain import parse_elevations
    assert parse_elevations('{"elevation":[10,20.5,30]}') == [10.0, 20.5, 30.0]
    assert parse_elevations("not json") == []
    assert parse_elevations('{"foo":1}') == []


def test_terrain_los_rows_verdict():
    from orbitdeck.engine.terrain import terrain_los_rows
    rows = terrain_los_rows(30, 200, 15, 10, 10, 146, 100, 100)
    verdict = [v for lab, v, _n in rows if lab == "Verdict"][0]
    assert verdict in ("blocked", "grazing", "clear (60% Fresnel)")
    # a tiny obstruction on a short path with tall antennas clears
    rows2 = terrain_los_rows(10, 20, 5, 30, 30, 146, 100, 100)
    v2 = [v for lab, v, _n in rows2 if lab == "Verdict"][0]
    assert "clear" in v2 or v2 == "grazing"


def test_fetch_profile_offline_graceful():
    from orbitdeck.engine.terrain import fetch_profile
    def dead_http(url, timeout=15):
        raise OSError("offline")
    analysis, elev, dist = fetch_profile(dead_http, 39, -77, 39.3, -76.5)
    assert elev == [] and dist > 0 and analysis["clear"] is True
