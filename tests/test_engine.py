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


def test_transponder_center_frequency():
    import json
    from orbitdeck.engine import SatDb
    arr = [{"description": "Linear B", "type": "Transponder",
            "downlink_low": 145925000, "downlink_high": 145975000,
            "uplink_low": 432125000, "uplink_high": 432175000,
            "mode": "LSB", "invert": True, "status": "active"},
           {"description": "FM", "type": "Transceiver",
            "downlink_low": 145800000, "uplink_low": 435100000,
            "mode": "FM", "status": "active"}]
    tps = SatDb.parse_transmitters_json(json.dumps(arr))
    lin, fm = tps[0], tps[1]
    # linear: center is the passband midpoint, not the low edge
    assert lin.downlink_center() == 145950000
    assert lin.uplink_center() == 432150000
    assert lin.downlink_center() != lin.downlink
    assert lin.kind() == "Linear (inverting)"
    # single channel: center equals the channel frequency
    assert fm.downlink_center() == fm.downlink == 145800000
    assert fm.kind() == "FM"


def test_transponder_kind_labels():
    import json
    from orbitdeck.engine import SatDb
    arr = [{"description": "CW Beacon", "mode": "CW", "downlink_low": 1,
            "status": "active"},
           {"description": "BPSK1200", "mode": "BPSK", "baud": 1200,
            "downlink_low": 1, "status": "active"}]
    tps = SatDb.parse_transmitters_json(json.dumps(arr))
    assert tps[0].kind() == "CW/Beacon"
    assert "Data" in tps[1].kind() and tps[1].baud == 1200


def test_net_builds_verifying_ssl_context():
    from orbitdeck.gui import net
    ctx = net._context()
    # a real, certificate-verifying context (not an unverified one)
    import ssl
    assert ctx is not None
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_kvpanel_skips_repack_when_unchanged():
    """The live-page smoothness fix: when the row set/order is identical across
    refreshes, KVPanel must not pack_forget()+pack() every time (that forces a
    slow geometry relayout on macOS). It should only repack on structural
    changes."""
    import sys
    import types

    class FakeW:
        def __init__(self, *a, **k):
            self._cfg = dict(k)
            self.pack_count = 0
            self.forget_count = 0
            self.destroyed = False

        def pack(self, *a, **k):
            self.pack_count += 1

        def pack_forget(self):
            self.forget_count += 1

        def configure(self, **k):
            self._cfg.update(k)

        def cget(self, key):
            return self._cfg.get(key, "")

        def destroy(self):
            self.destroyed = True

    real_tk = sys.modules.get("tkinter")
    real_ttk = sys.modules.get("tkinter.ttk")
    real_mbk = sys.modules.get("matplotlib.backends.backend_tkagg")
    fake_tk = types.ModuleType("tkinter")
    fake_tk.Frame = FakeW
    fake_tk.Label = FakeW
    fake_ttk = types.ModuleType("tkinter.ttk")
    for _n in ("Frame", "Label", "Button", "Style", "Treeview", "Entry",
               "Radiobutton", "Checkbutton", "Separator", "Notebook",
               "Combobox", "Scrollbar"):
        setattr(fake_ttk, _n, FakeW)
    fake_mbk = types.ModuleType("matplotlib.backends.backend_tkagg")

    class _FC:
        def __init__(self, *a, **k):
            pass

        def get_tk_widget(self):
            return FakeW()

        def draw_idle(self):
            pass

    fake_mbk.FigureCanvasTkAgg = _FC
    sys.modules["tkinter"] = fake_tk
    sys.modules["tkinter.ttk"] = fake_ttk
    sys.modules["matplotlib.backends.backend_tkagg"] = fake_mbk
    try:
        import importlib
        # ensure a fresh import against the fakes
        sys.modules.pop("orbitdeck.gui.screens", None)
        screens = importlib.import_module("orbitdeck.gui.screens")
        kv = screens.KVPanel(FakeW())

        def render(v):
            kv.begin()
            kv.section("S")
            kv.row("A", v)
            kv.row("B", v)
            kv.end()

        render("1")     # first build packs (repack expected here)
        before = sum(e["frame"].forget_count for e in kv._cache.values())
        render("2")     # same structure -> must NOT repack
        after = sum(e["frame"].forget_count for e in kv._cache.values())
        assert after - before == 0, "KVPanel repacked despite unchanged layout"
        aval = [e for e in kv._cache.values()
                if e["kind"] == "row" and e["lab"].cget("text") == "A"][0]["val"]
        assert aval.cget("text") == "2"
    finally:
        for name, mod in (("tkinter", real_tk), ("tkinter.ttk", real_ttk),
                          ("matplotlib.backends.backend_tkagg", real_mbk)):
            if mod is not None:
                sys.modules[name] = mod
            else:
                sys.modules.pop(name, None)
        sys.modules.pop("orbitdeck.gui.screens", None)


def test_orbit_live_page_stable_structure_across_ticks():
    """The Live page must not change its KVPanel structure every second (a
    timestamp in a section title used to do that, forcing a full relayout and
    visible flashing on macOS)."""
    import sys
    import types
    import time

    class FakeW:
        def __init__(self, *a, **k):
            self._cfg = dict(k)
            self.forget_count = 0

        def pack(self, *a, **k):
            pass

        def pack_forget(self):
            self.forget_count += 1

        def configure(self, **k):
            self._cfg.update(k)

        def cget(self, key):
            return self._cfg.get(key, "")

        def destroy(self):
            pass

        def bind(self, *a, **k):
            pass

        def winfo_ismapped(self):
            return 1

        def __getattr__(self, n):
            return lambda *a, **k: FakeW()

    saved = {n: sys.modules.get(n) for n in (
        "tkinter", "tkinter.ttk", "tkinter.messagebox",
        "matplotlib.backends.backend_tkagg")}
    tk = types.ModuleType("tkinter")
    for n in ("Frame", "Button", "Listbox", "Text", "Entry", "Toplevel",
              "Tk", "Radiobutton", "Checkbutton", "Canvas", "Scrollbar",
              "PhotoImage", "Label"):
        setattr(tk, n, FakeW)

    class _SV:
        def __init__(self, value="", master=None):
            self._v = value

        def set(self, v):
            self._v = v

        def get(self):
            return self._v

        def trace_add(self, *a, **k):
            pass
    tk.StringVar = tk.IntVar = tk.BooleanVar = tk.DoubleVar = _SV
    for c in ("END", "LEFT", "RIGHT", "TOP", "BOTH", "X", "Y", "W", "E"):
        setattr(tk, c, c.lower())
    ttk = types.ModuleType("tkinter.ttk")
    for n in ("Frame", "Label", "Button", "Treeview", "Style", "Entry",
              "Radiobutton", "Checkbutton", "Separator", "Notebook",
              "Scrollbar", "Combobox"):
        setattr(ttk, n, FakeW)
    mb = types.ModuleType("tkinter.messagebox")
    mb.showerror = mb.showinfo = mb.showwarning = lambda *a, **k: None
    mbk = types.ModuleType("matplotlib.backends.backend_tkagg")

    class _FC:
        def __init__(self, *a, **k):
            pass

        def get_tk_widget(self):
            return FakeW()

        def draw_idle(self):
            pass

        def draw(self):
            pass
    mbk.FigureCanvasTkAgg = _FC
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk,
                        "tkinter.messagebox": mb,
                        "matplotlib.backends.backend_tkagg": mbk})
    sys.modules.pop("orbitdeck.gui.screens", None)
    sys.modules.pop("orbitdeck.gui.screens.orbit", None)
    try:
        from orbitdeck.gui import screens
        from orbitdeck.gui.store import Store
        store = Store()

        class App:
            class _R:
                def after(self, ms, fn=None):
                    return None

            def __init__(self, st):
                self.store = st
                self.current = None
                self._screen_cache = {}
                self.root = App._R()

            def set_status(self, t):
                pass

            def show(self, k):
                pass
        scr = screens.make_screen("orbit", FakeW(), App(store))
        scr.page.set(1)        # Live page
        scr._render(time.time())
        before = sum(e["frame"].forget_count for e in scr.kv._cache.values())
        scr._render(time.time() + 1)
        after = sum(e["frame"].forget_count for e in scr.kv._cache.values())
        assert after - before == 0, "Live page relayouts every tick (flashing)"
    finally:
        for n, m in saved.items():
            if m is not None:
                sys.modules[n] = m
            else:
                sys.modules.pop(n, None)
        sys.modules.pop("orbitdeck.gui.screens", None)
        sys.modules.pop("orbitdeck.gui.screens.orbit", None)


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


def test_doppler_downlink_list_from_transponders():
    """The Doppler page builds its downlink dropdown from the satellite's
    transponders, using the passband center for linear transponders."""
    import sys
    import types
    import json

    # minimal tk/ttk/mpl stubs so the orbit screen constructs headlessly
    class W:
        def __init__(self, *a, **k):
            self._cfg = dict(k)

        def pack(self, *a, **k):
            pass

        def pack_forget(self):
            pass

        def configure(self, **k):
            self._cfg.update(k)

        def cget(self, key):
            return self._cfg.get(key, "")

        def bind(self, *a, **k):
            pass

        def current(self, *a):
            return 0

        def winfo_ismapped(self):
            return 0

        def __getattr__(self, n):
            return lambda *a, **k: W()

    saved = {n: sys.modules.get(n) for n in (
        "tkinter", "tkinter.ttk", "tkinter.messagebox",
        "matplotlib.backends.backend_tkagg")}
    tk = types.ModuleType("tkinter")
    for n in ("Frame", "Button", "Label", "Canvas", "Toplevel", "Entry"):
        setattr(tk, n, W)

    class _SV:
        def __init__(self, value="", master=None):
            self._v = value

        def set(self, v):
            self._v = v

        def get(self):
            return self._v

        def trace_add(self, *a, **k):
            pass
    tk.StringVar = tk.IntVar = tk.BooleanVar = tk.DoubleVar = _SV
    ttk = types.ModuleType("tkinter.ttk")
    for n in ("Frame", "Label", "Button", "Style", "Entry", "Combobox",
              "Treeview", "Radiobutton", "Checkbutton", "Separator",
              "Notebook", "Scrollbar"):
        setattr(ttk, n, W)
    mb = types.ModuleType("tkinter.messagebox")
    mb.showerror = mb.showinfo = mb.showwarning = lambda *a, **k: None
    mbk = types.ModuleType("matplotlib.backends.backend_tkagg")

    class _FC:
        def __init__(self, *a, **k):
            self.widget = W()

        def get_tk_widget(self):
            return self.widget

        def draw_idle(self):
            pass

        def draw(self):
            pass
    mbk.FigureCanvasTkAgg = _FC
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk,
                        "tkinter.messagebox": mb,
                        "matplotlib.backends.backend_tkagg": mbk})
    sys.modules.pop("orbitdeck.gui.screens", None)
    sys.modules.pop("orbitdeck.gui.screens.orbit", None)
    try:
        from orbitdeck.gui import screens
        from orbitdeck.gui.store import Store
        from orbitdeck.engine import SatDb
        store = Store()
        s = store.selected_sat()
        arr = [{"description": "Linear B", "downlink_low": 145925000,
                "downlink_high": 145975000, "uplink_low": 432125000,
                "mode": "LSB", "invert": True, "status": "active"},
               {"description": "FM", "downlink_low": 145800000,
                "mode": "FM", "status": "active"}]
        s.transponders = SatDb.parse_transmitters_json(json.dumps(arr))

        class App:
            class _R:
                def after(self, *a, **k):
                    return None

            def __init__(self, st):
                self.store = st
                self.current = None
                self._screen_cache = {}
                self.root = App._R()

            def set_status(self, t):
                pass
        orbit = screens.make_screen("orbit", W(), App(store))
        orbit._sync_dop_list(s)
        freqs = [hz for _lbl, hz in orbit._dop_list]
        # linear transponder contributes its center, FM its single freq
        assert 145950000 in freqs       # linear center, not 145925000 low edge
        assert 145800000 in freqs
        assert 145925000 not in freqs
    finally:
        for n, m in saved.items():
            if m is not None:
                sys.modules[n] = m
            else:
                sys.modules.pop(n, None)
        sys.modules.pop("orbitdeck.gui.screens", None)
        sys.modules.pop("orbitdeck.gui.screens.orbit", None)


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


def test_oscarlocator_pdf_generates():
    """The OSCARLOCATOR generator produces a non-trivial 3-page PDF for a LEO
    satellite without error."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    st = Store()
    s = st.db.sats[0]
    out = os.path.join(tempfile.mkdtemp(), "osc.pdf")
    generate_oscarlocator_pdf(out, st, s)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 5000      # vector content, not empty
    # PDF magic bytes
    with open(out, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_oscarlocator_node_shift_and_track():
    """The per-pass arc advance and canonical track behave physically: ISS
    advances ~23 deg west/pass, a polar sun-sync ~25 deg, and the canonical
    track latitude never exceeds the inclination."""
    import json
    import datetime
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import _node_shift_deg, _canonical_track
    now = datetime.datetime.now(datetime.timezone.utc)

    def make(mm, incl, nid):
        omm = [{"OBJECT_NAME": "T",
                "EPOCH": now.strftime("%Y-%m-%dT%H:%M:%S.000000"),
                "MEAN_MOTION": mm, "ECCENTRICITY": 0.001, "INCLINATION": incl,
                "RA_OF_ASC_NODE": 100, "ARG_OF_PERICENTER": 90,
                "MEAN_ANOMALY": 180, "BSTAR": 0.0001, "NORAD_CAT_ID": nid}]
        st = Store()
        st.db.load_gp_json(json.dumps(omm))
        return st.db.sats[0]

    iss = make(15.5, 51.6, 25544)
    shift = _node_shift_deg(iss)
    assert shift < 0                                  # westward for prograde LEO
    assert 20 < abs(shift) < 27                       # ~23 deg/orbit

    polar = make(14.3, 98.7, 99998)
    assert 22 < abs(_node_shift_deg(polar)) < 28

    # canonical track: |lat| <= inclination, one orbit of minute stamps
    track = _canonical_track(iss)
    assert all(abs(lat) <= iss.incl + 0.5 for _lon, lat, _m in track)
    assert abs(track[-1][2] - iss.period_min) < 0.5   # ends ~one period in


def test_oscarlocator_pdf_geostationary_ok():
    """The enhanced generator handles a geostationary satellite (huge footprint,
    360 deg/pass) without error."""
    import os
    import json
    import tempfile
    import datetime
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    now = datetime.datetime.now(datetime.timezone.utc)
    omm = [{"OBJECT_NAME": "QO-100",
            "EPOCH": now.strftime("%Y-%m-%dT%H:%M:%S.000000"),
            "MEAN_MOTION": 1.00271, "ECCENTRICITY": 0.0001, "INCLINATION": 0.05,
            "RA_OF_ASC_NODE": 80.0, "ARG_OF_PERICENTER": 100.0,
            "MEAN_ANOMALY": 200.0, "BSTAR": 0.0, "NORAD_CAT_ID": 43700}]
    st = Store()
    st.db.load_gp_json(json.dumps(omm))
    out = os.path.join(tempfile.mkdtemp(), "geo.pdf")
    generate_oscarlocator_pdf(out, st, st.db.sats[0])
    assert os.path.getsize(out) > 5000
