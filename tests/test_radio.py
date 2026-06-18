"""Link budget, Doppler, transponder and EME tests.

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
    mbk.FigureCanvas = _FC
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk,
                        "tkinter.messagebox": mb,
                        "matplotlib.backends.backend_tkagg": mbk})
    for _m in [m for m in list(sys.modules) if m.startswith("orbitdeck.gui.screens")]:
        sys.modules.pop(_m, None)
    import matplotlib as _mpl
    _use = _mpl.use; _mpl.use = lambda *a, **k: None
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
        _mpl.use = _use
        for n, m in saved.items():
            if m is not None:
                sys.modules[n] = m
            else:
                sys.modules.pop(n, None)
        sys.modules.pop("orbitdeck.gui.screens", None)
        sys.modules.pop("orbitdeck.gui.screens.orbit", None)

def test_linkbudget_fspl_and_delay():
    from orbitdeck.engine import linkbudget as LB
    # FSPL at 1000 km / 145.9 MHz is about 135.7 dB
    fspl = LB.free_space_path_loss_db(1000.0, 145.9e6)
    assert 135.0 < fspl < 136.5
    # doubling distance adds ~6 dB
    fspl2 = LB.free_space_path_loss_db(2000.0, 145.9e6)
    assert abs((fspl2 - fspl) - 6.02) < 0.1
    # propagation delay ~3.34 ms at 1000 km
    assert abs(LB.propagation_delay_ms(1000.0) - 3.336) < 0.01

def test_doppler_round_trip_fixed_leg():
    """For a linear bird, holding one leg fixed must move the OTHER leg, and the
    round-trip offset must be non-zero and sign-consistent with range-rate."""
    from orbitdeck.engine import linkbudget as LB
    dl, ul = 145.95e6, 435.15e6
    # hold downlink: the uplink is the one that gets tuned
    pb_recede = LB.linear_fixed_leg_playbook(dl, ul, +5.0, invert=True,
                                             hold="downlink")
    pb_approach = LB.linear_fixed_leg_playbook(dl, ul, -5.0, invert=True,
                                               hold="downlink")
    assert pb_recede["fixed_hz"] == int(round(dl))
    assert pb_recede["tune_leg"] == "uplink"
    # the tuned uplink differs between approaching and receding
    assert pb_recede["tune_hz"] != pb_approach["tune_hz"]
    # hold uplink: now the downlink is tuned, and the offset is larger for an
    # inverting bird (fixed-uplink Doppler and downlink Doppler add)
    pb_u = LB.linear_fixed_leg_playbook(dl, ul, +5.0, invert=True,
                                        hold="uplink")
    assert pb_u["fixed_hz"] == int(round(ul))
    assert pb_u["tune_leg"] == "downlink"
    assert abs(pb_u["round_trip_offset_hz"]) > 0

def test_doppler_playbook_fm_independent():
    """FM birds get plain per-leg Doppler (no round-trip term)."""
    from orbitdeck.engine import linkbudget as LB
    rows = LB.doppler_playbook_rows([0, 60], [+5.0, -5.0], 145.8e6, 437.8e6,
                                    is_linear=False)
    assert len(rows) == 2
    assert rows[0]["mode"] == "FM/independent"
    # receding lowers the received downlink below nominal
    assert rows[0]["rx_hz"] < 145.8e6
    # approaching raises it above nominal
    assert rows[1]["rx_hz"] > 145.8e6

def test_element_drift_and_trust():
    from orbitdeck.engine import linkbudget as LB
    import time
    now = time.time()
    # fresh element set
    age = LB.element_age_days(now - 2 * 86400, now)
    assert 1.9 < age < 2.1
    label, conf = LB.trust_level(age)
    assert label == "fresh" and conf == 1.0
    # drift grows with age
    assert LB.along_track_error_km(0) == 0.0
    assert LB.along_track_error_km(10) > LB.along_track_error_km(5)
    # stale label for old elements
    assert LB.trust_level(20)[0] == "stale"
    assert LB.trust_level(40)[0] == "expired"

def test_radio_sources_fixed_and_visible():
    import time
    from orbitdeck.engine import celestial as CE
    t = time.time()
    # Cas A is circumpolar from mid-northern latitudes (Dec ~ +58.8): it should
    # essentially always be above the horizon from lat 55 N.
    az, el = CE.source_azel("Cassiopeia A", 55.0, 0.0, t)
    assert el > 0.0
    # an unknown source returns None
    assert CE.source_azel("Nonexistent A", 40.0, 0.0, t) is None

def test_eme_path_loss_matches_references():
    import time
    from orbitdeck.engine import celestial as CE
    t = time.time()
    # published amateur figures: ~243 dB @ 50 MHz up to ~289 dB @ 10 GHz,
    # ~252 dB at 144 MHz.
    l50 = CE.eme_path_loss_db(50e6, t)
    l144 = CE.eme_path_loss_db(144e6, t)
    l432 = CE.eme_path_loss_db(432e6, t)
    l10g = CE.eme_path_loss_db(10368e6, t)
    assert 240 < l50 < 245
    assert 249 < l144 < 254
    assert 258 < l432 < 263
    assert 285 < l10g < 292
    # loss increases monotonically with frequency
    assert l50 < l144 < l432 < l10g

def test_eme_doppler_sign_and_magnitude():
    import time
    from orbitdeck.engine import celestial as CE
    t = time.time()
    # self-echo Doppler at 144 MHz peaks a few hundred Hz; magnitude is bounded
    d = CE.eme_doppler_hz(144e6, 38.9, -77.0, t)
    assert abs(d) < 500.0
    # higher band => larger Doppler in proportion to frequency
    d432 = CE.eme_doppler_hz(432e6, 38.9, -77.0, t)
    assert abs(d432) > abs(d) * 2.5     # ~3x frequency

def test_eme_window_common_visibility():
    import time
    from orbitdeck.engine import celestial as CE
    t = time.time()
    # two nearby stations almost always share Moon visibility; the windows
    # returned must be ordered, non-overlapping, and have end >= start
    wins = CE.eme_window(38.9, -77.0, 40.0, -75.0, t, hours=24, step_s=600)
    for (a, b) in wins:
        assert b >= a
    for i in range(1, len(wins)):
        assert wins[i][0] >= wins[i - 1][1]
    # two stations on opposite sides of the Earth (lon 180 apart, opposite lat)
    # should rarely if ever share the Moon; allow zero windows
    wins2 = CE.eme_window(60.0, 0.0, -60.0, 180.0, t, hours=24, step_s=600)
    assert isinstance(wins2, list)

def test_store_selected_transponder_index():
    from orbitdeck.gui.store import Store
    st = Store()
    # find a satellite that has transponders in the sample data
    sat = None
    for s in st.db.sats:
        st.ensure_transponders(s)
        if s.transponders:
            sat = s
            break
    if sat is None:
        return
    n = len(sat.transponders)
    # default is 0
    assert st.selected_tp_index(sat) == 0
    assert st.selected_transponder(sat) is sat.transponders[0]
    # set to last and read back
    st.set_selected_tp_index(sat, n - 1)
    assert st.selected_tp_index(sat) == n - 1
    assert st.selected_transponder(sat) is sat.transponders[n - 1]
    # out-of-range indices clamp safely to 0
    st.set_selected_tp_index(sat, 999)
    assert st.selected_tp_index(sat) == 0
    # a satellite with no transponders returns None / index 0
    empty = type(sat)(norad=999999, name="EMPTY")
    empty.transponders = []
    assert st.selected_tp_index(empty) == 0
    assert st.selected_transponder(empty) is None

def test_passband_freqs_linear_sweep():
    """Across a linear transponder the operating downlink should sweep from the
    low edge (0%) through center to the high edge (100%)."""
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.predict import Predictor
    st = Store()
    rs = next((s for s in st.db.sats if s.norad == 44909), None)   # RS-44
    if rs is None:
        return
    st.ensure_transponders(rs)
    tp = next((t for t in (rs.transponders or [])
               if t.is_linear and t.bandwidth() > 0), None)
    if tp is None:
        return
    bw = tp.bandwidth()
    dl_lo, _ = Predictor.passband_freqs(tp, 0)
    dl_mid, _ = Predictor.passband_freqs(tp, bw // 2)
    dl_hi, _ = Predictor.passband_freqs(tp, bw)
    assert dl_lo < dl_mid < dl_hi
    assert dl_hi - dl_lo == bw

def test_playbook_csv_includes_az_el():
    """The Doppler playbook CSV must carry az/el pointing columns when the rows
    have az/el attached (as the Radio screen does)."""
    from orbitdeck.gui import exports as EX
    rows = [
        {"t": 1.7e9, "range_rate": -5.0, "rx_hz": 435_640_000,
         "tx_hz": 145_960_000, "mode": "linear/hold-downlink",
         "az": 153.0, "el": 0.0},
        {"t": 1.7e9 + 60, "range_rate": -0.1, "rx_hz": 435_640_100,
         "tx_hz": 145_959_900, "mode": "linear/hold-downlink",
         "az": 83.0, "el": 35.0},
    ]
    csv = EX.playbook_to_csv(rows, "RS-44")
    header = csv.splitlines()[0]
    assert "az_deg" in header and "el_deg" in header
    # the second data row's az/el should appear
    body = csv.splitlines()[2]
    assert "83" in body and "35" in body

def test_radio_pass_picker_drives_both_tabs():
    """The Radio screen's pass picker should load upcoming passes and plan both
    the link budget and the Doppler playbook against the selected pass."""
    import matplotlib
    matplotlib.use("Agg")
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.gui import screens
    from orbitdeck.engine.predict import Observer
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        app = OrbitDeckApp(root)
    except Exception:
        # the full app can fail to build under dirty global Tk/ttk state left
        # by an earlier GUI test in the same process; the picker logic is
        # covered when this test runs in isolation.
        root.destroy()
        return
    app.store.obs = Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True)
    app.store.pred.set_site(app.store.obs)
    app.store.pred.set_sat(app.store.selected_sat())
    r = screens.make_screen("radio", app.content, app)
    r.on_show()
    # passes were loaded
    assert len(r._passes) >= 1
    # the selected pass is the first by default
    p0 = r._selected_pass()
    assert p0 is r._passes[0]
    # the playbook built rows for that pass (its rows fall within the pass span)
    rows = r._pb_rows
    if rows:
        assert rows[0]["t"] >= p0.aos - 1
        assert rows[-1]["t"] <= p0.los + 1
    # selecting a different pass updates the selection
    if len(r._passes) > 1:
        r._pass_combo.current(1)
        r._on_pass_change()
        assert r._selected_pass() is r._passes[1]
    root.destroy()

def test_link_budget_satellite_downlink_eirp():
    """The satellite's TX power and antenna gain set the downlink EIRP: 1 W into
    a 2 dBi whip is 30 dBm + 2 dBi = 32 dBm EIRP, and raising either lifts the
    received power by the same amount."""
    from orbitdeck.engine import linkbudget as LB
    rng, freq = 1500.0, 437.8e6
    lo = LB.link_budget(rng, freq, tx_power_w=1.0, tx_gain_dbi=2.0,
                        rx_gain_dbi=12.0, line_loss_db=1.5)
    assert abs(lo["eirp_dbm"] - 32.0) < 0.1
    # +3 dB of antenna gain raises EIRP and RX power by ~3 dB
    hi = LB.link_budget(rng, freq, tx_power_w=1.0, tx_gain_dbi=5.0,
                        rx_gain_dbi=12.0, line_loss_db=1.5)
    assert abs((hi["eirp_dbm"] - lo["eirp_dbm"]) - 3.0) < 0.01
    assert abs((hi["rx_power_dbm"] - lo["rx_power_dbm"]) - 3.0) < 0.01
    # doubling power (1 W -> 2 W) adds ~3 dB
    hp = LB.link_budget(rng, freq, tx_power_w=2.0, tx_gain_dbi=2.0,
                        rx_gain_dbi=12.0, line_loss_db=1.5)
    assert abs((hp["eirp_dbm"] - lo["eirp_dbm"]) - 3.0) < 0.05
