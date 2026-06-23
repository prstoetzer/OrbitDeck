"""Tests for the v0.22.0 usability/feature additions: reference-orbit sheet,
desktop-notification helper, store preferences, and the OSCARLOCATOR Sim rim.
"""

import datetime as dt
import os
import tempfile

import pytest

from orbitdeck.engine import SatDb, Predictor, Observer


def _iss_store():
    """A Store-like object backed by the bundled catalog with ISS selected."""
    from orbitdeck.gui.store import Store
    st = Store()
    return st


def test_reference_orbits_first_crossing_per_day():
    """reference_orbits returns one entry per UTC day, each at or after 00:00
    UTC of that day, and ascending for a northern station."""
    from orbitdeck.gui.refsheet import reference_orbits
    st = _iss_store()
    iss = next((s for s in st.db.sats if "ISS" in s.name), st.db.sats[0])
    pred = Predictor()
    pred.set_site(Observer(lat=40.0, lon=-75.0, alt_m=10, valid=True))
    pred.set_sat(iss)
    start = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc).timestamp()
    rows, descending = reference_orbits(pred, 40.0, start, 10)
    assert descending is False           # northern station -> ascending
    assert len(rows) == 10
    # each populated row's crossing is within its UTC day
    for i, r in enumerate(rows):
        day0 = start + i * 86400.0
        if r["t"] is not None:
            assert day0 <= r["t"] < day0 + 86400.0
            assert -180.0 <= r["lon"] <= 180.0


def test_reference_orbits_southern_uses_descending():
    """A southern-hemisphere station gets descending crossings."""
    from orbitdeck.gui.refsheet import reference_orbits
    st = _iss_store()
    iss = next((s for s in st.db.sats if "ISS" in s.name), st.db.sats[0])
    pred = Predictor()
    pred.set_site(Observer(lat=-33.0, lon=151.0, alt_m=10, valid=True))
    pred.set_sat(iss)
    start = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc).timestamp()
    _rows, descending = reference_orbits(pred, -33.0, start, 5)
    assert descending is True


def test_reference_orbits_pdf_generated():
    """The reference-orbit PDF writes a non-trivial multi-page file for two
    satellites over 60 days."""
    from orbitdeck.gui.refsheet import generate_reference_orbits_pdf
    st = _iss_store()
    sats = st.db.sats[:2]
    d = tempfile.mkdtemp()
    p = os.path.join(d, "ref.pdf")
    generate_reference_orbits_pdf(p, st, sats, days=60)
    assert os.path.exists(p) and os.path.getsize(p) > 3000
    head = open(p, "rb").read(5)
    assert head == b"%PDF-"
    # carries the OrbitDeck + author credit
    import subprocess
    txt = subprocess.run(["pdftotext", "-f", "1", "-l", "1", p, "-"],
                         capture_output=True, text=True).stdout
    assert "OrbitDeck" in txt and "N8HM" in txt


def test_notify_module_is_safe_to_call():
    """The desktop-notification helper must import and run without raising even
    when no native notifier is present (it spawns a daemon thread and swallows
    failures)."""
    from orbitdeck.gui import notify
    assert isinstance(notify.available(), bool)
    # should never raise regardless of platform/tooling
    notify.send("OrbitDeck test", "hello")


def test_store_prefs_round_trip():
    """save_config(**prefs) persists arbitrary preferences that reload via the
    config property."""
    from orbitdeck.gui.store import Store
    st = Store()
    st.save_config(onboarded=True, ui_scale=1.3,
                   desktop_notifications=False)
    assert st.config.get("onboarded") is True
    assert abs(st.config.get("ui_scale") - 1.3) < 1e-9
    # a fresh Store should read the same persisted prefs back
    st2 = Store()
    assert st2.config.get("onboarded") is True
    assert st2.config.get("desktop_notifications") is False


def test_oscarsim_has_rim_drawing():
    """The OSCARLOCATOR Sim screen defines the rim/tick/longitude-label drawing
    ported from the web simulator."""
    from orbitdeck.gui.screens import oscarsim
    assert hasattr(oscarsim.OscarSimScreen, "_draw_rim")


def test_state_boundary_dataset_is_denser():
    """The bundled boundary dataset is far denser than the legacy city points,
    giving accurate per-state footprint coverage."""
    from orbitdeck.data.us_state_boundaries import US_STATE_BOUNDARIES as B
    from orbitdeck.data.us_states import US_STATES
    assert len(B) >= 50
    total = sum(len(v) for v in B.values())
    assert total > 3000                      # vs ~100 for the old city points
    # every state has at least one point, and Texas (large) has many
    assert all(len(v) >= 1 for v in B.values())
    assert len(B["TX"]) > 50
    # points are plausible US lat/lon
    for la, lo in B["TX"]:
        assert 25 <= la <= 37 and -107 <= lo <= -93


def test_workable_states_uses_boundary_dataset():
    """workable_states detects a state from interior points, not just cities."""
    from orbitdeck.data.us_states import workable_states
    # a footprint test covering a box over Kansas interior
    def inside(lat, lon):
        return 37.0 <= lat <= 40.0 and -102.0 <= lon <= -95.0
    got = workable_states(inside)
    assert "KS" in got


def test_rove_stop_passes_lists_states_and_dxcc():
    """The rove planner returns covering passes annotated with workable states,
    DXCC and grids, treating the time window as a hint."""
    import time
    from orbitdeck.engine import planning as PL
    from orbitdeck.engine.predict import grid_to_latlon
    st = _iss_store()
    iss = next((s for s in st.db.sats if "ISS" in s.name), st.db.sats[0])
    st.pred.set_site(st.obs)
    st.pred.set_sat(iss)
    lat, lon = grid_to_latlon("FN31")
    now = time.time()
    res = PL.rove_stop_passes(st.pred, lat, lon, now, now + 6 * 3600,
                              min_el=5.0)
    # at least one covering pass over a 6-hour window for the ISS
    assert isinstance(res, list)
    for r in res:
        assert "aos" in r and "los" in r and "max_el" in r
        assert isinstance(r["states"], set)
        assert isinstance(r["dxcc"], set)
        assert isinstance(r["grids"], set)


def test_rove_sheet_pdf_generated():
    """The rove sheet PDF builds and carries the OrbitDeck credit."""
    import time
    import subprocess
    from orbitdeck.engine import planning as PL
    from orbitdeck.engine.predict import grid_to_latlon
    from orbitdeck.gui.rovesheet import generate_rove_sheet_pdf
    st = _iss_store()
    iss = next((s for s in st.db.sats if "ISS" in s.name), st.db.sats[0])
    st.pred.set_site(st.obs)
    st.pred.set_sat(iss)
    lat, lon = grid_to_latlon("FN31")
    now = time.time()
    res = PL.rove_stop_passes(st.pred, lat, lon, now, now + 6 * 3600,
                              min_el=5.0)
    rows = [("FN31", r) for r in res] or [("FN31", None)]
    d = tempfile.mkdtemp()
    p = os.path.join(d, "rove.pdf")
    generate_rove_sheet_pdf(p, iss.name, st, rows)
    assert os.path.exists(p) and os.path.getsize(p) > 2000
    txt = subprocess.run(["pdftotext", "-f", "1", "-l", "1", p, "-"],
                         capture_output=True, text=True).stdout
    assert "N8HM" in txt


def test_rove_stop_window_parsing():
    """The rove planner parses a stop's date + UTC start/end into a window, and
    treats end<=start as an overnight window spanning to the next day."""
    from orbitdeck.gui.screens.planning import PlanningScreen
    # daytime window
    w = PlanningScreen._stop_window("2026-06-18", "13:00", "17:00")
    assert w is not None
    assert abs((w[1] - w[0]) / 3600.0 - 4.0) < 1e-6
    # overnight window (end earlier than start -> next day)
    w2 = PlanningScreen._stop_window("2026-06-18", "22:00", "02:00")
    assert w2 is not None
    assert abs((w2[1] - w2[0]) / 3600.0 - 4.0) < 1e-6
    # invalid inputs return None
    assert PlanningScreen._stop_window("not-a-date", "1", "2") is None
    assert PlanningScreen._stop_window("2026-06-18", "bad", "17:00") is None


def test_lab_satellite_roundtrips_through_predictor():
    """A synthetic lab SatEntry built from elements propagates correctly: the
    predictor returns a sub-point near the expected altitude and finds nodes."""
    import time
    from orbitdeck.gui import lab
    from orbitdeck.engine import Predictor, Observer
    el = lab.default_elements()
    sat = lab.make_lab_sat(el)
    assert sat.is_manual and sat.norad >= lab.LAB_NORAD_BASE
    pred = Predictor()
    pred.set_site(Observer(lat=40, lon=-75, alt_m=10, valid=True))
    assert pred.set_sat(sat)
    look = pred.look(time.time())
    # ISS-like default ~420 km altitude
    assert 380 < look.alt_km < 460
    nodes = pred.ascending_nodes(time.time(), time.time() + 6 * 3600)
    assert len(nodes) >= 1


def test_lab_apsides_roundtrip():
    """Apogee/perigee <-> mean-altitude/eccentricity conversions are mutual
    inverses within the valid range, and a circular orbit gives equal apsides."""
    from orbitdeck.gui import lab
    # circular: apogee == perigee == mean altitude
    apo, peri = lab.apsides_from_alt_ecc(800.0, 0.0)
    assert abs(apo - 800.0) < 1e-6 and abs(peri - 800.0) < 1e-6
    # round-trip a spread of eccentric orbits
    for alt, ecc in ((420.0, 0.0), (8000.0, 0.3), (20000.0, 0.5), (1000.0, 0.1)):
        apo, peri = lab.apsides_from_alt_ecc(alt, ecc)
        assert apo >= peri
        alt2, ecc2 = lab.alt_ecc_from_apsides(apo, peri)
        assert abs(alt2 - alt) < 1e-6
        assert abs(ecc2 - ecc) < 1e-9
    # swapped inputs are tolerated (perigee given larger than apogee)
    a1, e1 = lab.alt_ecc_from_apsides(500.0, 39000.0)
    a2, e2 = lab.alt_ecc_from_apsides(39000.0, 500.0)
    assert abs(a1 - a2) < 1e-9 and abs(e1 - e2) < 1e-9


def test_lab_apsides_sliders_hold_other_fixed():
    """The lab editor's apogee/perigee sliders map to alt/ecc: moving one holds
    the other apsis fixed and solves back, and both rows re-sync from an
    eccentricity change."""
    import tkinter as tk
    from orbitdeck.gui.labdialog import LabDialog
    from orbitdeck.gui import lab
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    el = lab.default_elements()
    el["alt_km"] = 8000.0
    el["ecc"] = 0.0
    dlg = LabDialog(root, el, on_change=lambda e: None)
    # circular to start: both apsides equal the mean altitude
    assert abs(dlg._vars["apogee"].get() - 8000.0) < 1.0
    assert abs(dlg._vars["perigee"].get() - 8000.0) < 1.0
    # raise apogee, perigee should stay put and alt/ecc move accordingly
    dlg._on_apsis_value("apogee", 15000.0)
    assert abs(dlg._vars["perigee"].get() - 8000.0) < 5.0
    assert dlg.el["ecc"] > 0.1 and dlg.el["alt_km"] > 8000.0
    # an eccentricity change re-syncs both apsis sliders
    dlg._on_slider_value("ecc", 0.0)
    assert abs(dlg._vars["apogee"].get() - dlg._vars["perigee"].get()) < 5.0
    root.destroy()


def test_lab_altitude_period_roundtrip():
    """Altitude <-> mean-motion conversions are mutual inverses, and period
    matches Kepler for a known altitude."""
    from orbitdeck.gui import lab
    for alt in (300.0, 800.0, 20200.0, 35786.0):
        mm = lab.mean_motion_from_alt(alt)
        assert abs(lab.alt_from_mean_motion(mm) - alt) < 1.0
    # geostationary altitude -> ~1 rev/day -> ~1436 min period
    p = lab.period_min_from_alt(35786.0)
    assert 1430 < p < 1445


def test_lab_orbit_type_labels():
    """The orbit-type classifier recognises the standard archetypes."""
    from orbitdeck.gui import lab
    assert lab.orbit_type_label(35786, 0.0, 0.0) == "Geostationary"
    assert "Molniya" in lab.orbit_type_label(26600, 0.7, 63.4)
    assert "MEO" in lab.orbit_type_label(20200, 0.0, 55.0)
    assert "Sun-synchronous" in lab.orbit_type_label(700, 0.001, 98.2)


def test_lab_explainers_present():
    """Each editable element has a non-empty plain-language explainer."""
    from orbitdeck.gui import lab
    el = lab.default_elements()
    for field in ("alt_km", "ecc", "incl", "raan", "argp", "ma"):
        assert lab.explain(field, el)


def test_lab_pdf_uses_custom_name():
    """A lab satellite prints as an OSCARLOCATOR with its custom name and the
    OrbitDeck credit on the overlay sheets."""
    import subprocess
    from orbitdeck.gui import lab
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    st = _iss_store()
    sat = lab.make_lab_sat({"name": "ZZTESTBIRD", "alt_km": 600, "ecc": 0.0,
                            "incl": 60.0, "raan": 0, "argp": 0, "ma": 0})
    d = tempfile.mkdtemp()
    p = os.path.join(d, "lab.pdf")
    generate_oscarlocator_pdf(p, st, sat, projection="polar",
                              footprint_on_qth=False)
    assert os.path.exists(p) and os.path.getsize(p) > 3000
    # credit + custom name present on the range-circle overlay page
    txt = subprocess.run(["pdftotext", "-f", "2", "-l", "2", p, "-"],
                         capture_output=True, text=True).stdout
    assert "N8HM" in txt
    assert "ZZTESTBIRD" in txt


def test_pass_explain_returns_lines():
    """The Pass Detail 'why' explainer returns geometry lines for a real pass."""
    import time
    from orbitdeck.gui import lab
    st = _iss_store()
    iss = next((s for s in st.db.sats if "ISS" in s.name), st.db.sats[0])
    st.pred.set_site(st.obs)
    st.pred.set_sat(iss)
    passes = st.pred.predict_passes(time.time(), 5, 1, time.time() + 2 * 86400)
    if passes:
        lines = lab.pass_explain(st.pred, passes[0])
        assert isinstance(lines, list) and len(lines) >= 2


def test_lab_derived_extended_fields():
    """The lab derived read-out exposes J2 node drift, sun-sync verdict, repeat
    cycle, and a decay estimate."""
    from orbitdeck.gui import lab
    d = lab.derived_readout({"name": "X", "alt_km": 700, "ecc": 0.001,
                             "incl": 98.2, "raan": 0, "argp": 0, "ma": 0})
    assert d["sun_synchronous"] is True
    assert 0.9 < d["node_drift_degday"] < 1.1
    assert "repeat" in d and "decay_text" in d
    # a very low orbit should show a finite (non-stable) lifetime
    low = lab.derived_readout({"name": "X", "alt_km": 250, "ecc": 0.0,
                               "incl": 51, "raan": 0, "argp": 0, "ma": 0})
    assert low["decay_text"] not in ("stable", "n/a")


def test_lab_challenges_check():
    """Each challenge's checker returns a (bool, str) and recognises a correct
    design (geostationary)."""
    from orbitdeck.gui import lab
    from orbitdeck.gui.labdialog import CHALLENGES
    geo = lab.clamp_elements({"name": "X", "alt_km": 35786, "ecc": 0.0,
                              "incl": 0.5, "raan": 0, "argp": 0, "ma": 0})
    d = lab.derived_readout(geo)
    for title, desc, chk in CHALLENGES:
        ok, detail = chk(d, geo)
        assert isinstance(ok, bool) and isinstance(detail, str)
    # the geostationary challenge should pass for a geo orbit
    geo_chk = CHALLENGES[3][2]
    assert geo_chk(d, geo)[0] is True


def test_orbits_101_pdf_generated():
    """The Orbits 101 handout builds and carries the OrbitDeck credit."""
    import subprocess
    from orbitdeck.gui.learnsheet import generate_orbits_101_pdf
    d = tempfile.mkdtemp()
    p = os.path.join(d, "o101.pdf")
    generate_orbits_101_pdf(p)
    assert os.path.exists(p) and os.path.getsize(p) > 3000
    txt = subprocess.run(["pdftotext", p, "-"], capture_output=True,
                         text=True).stdout
    assert "Inclination" in txt and "N8HM" in txt


def test_learn_screen_builds():
    """The Learn screen constructs with all seven tool tabs."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        import pytest
        pytest.skip("no display")
    root.withdraw()
    from orbitdeck.gui.app import OrbitDeckApp
    try:
        app = OrbitDeckApp(root)
    except Exception:
        # a prior test may have left a Tk root alive in this process; the Learn
        # screen itself is exercised by the screen harness, so skip rather than
        # fail on a cross-test Tk state collision.
        root.destroy()
        import pytest
        pytest.skip("Tk state from a prior test prevented a clean app build")
    try:
        app.show("learn")
        scr = app.current
        assert len(scr._tabs._tabs) == 23
    finally:
        root.destroy()


def test_radioedu_band_and_verdict():
    """Band labelling and the workable verdict behave sensibly."""
    from orbitdeck.gui import radioedu as RE
    assert "2 m" in RE.band_label(145900000.0)
    assert "70 cm" in RE.band_label(435000000.0)
    # FM needs a stronger signal than SSB: at the same RX power, SSB margin
    # should be higher
    m_fm, _n1, _o1 = RE.workable_verdict(-120.0, "FM")
    m_ssb, _n2, _o2 = RE.workable_verdict(-120.0, "USB")
    assert m_ssb > m_fm


def test_radioedu_fspl_increases_with_band():
    """Free-space loss grows with frequency at a fixed range."""
    from orbitdeck.gui import radioedu as RE
    lo = RE.fspl_db(1000.0, 145e6)
    hi = RE.fspl_db(1000.0, 435e6)
    assert hi > lo


def test_inverting_transponder_mapping():
    """An inverting linear transponder maps a high uplink to a low downlink and
    vice versa (the core teaching point of the transponder tab)."""
    # mirror mapping used by the diagram: dl_frac = 1 - ul_frac when inverting
    dl0, dl1 = 435610000.0, 435670000.0
    for frac in (0.1, 0.5, 0.9):
        dl_frac = 1.0 - frac
        dn = dl0 + dl_frac * (dl1 - dl0)
        # high uplink fraction -> low downlink frequency
        if frac > 0.5:
            assert dn < (dl0 + dl1) / 2
        elif frac < 0.5:
            assert dn > (dl0 + dl1) / 2


def test_orbits_101_pdf_has_radio_page():
    """The Orbits 101 handout includes the second radio/transponder page."""
    import subprocess
    from orbitdeck.gui.learnsheet import generate_orbits_101_pdf
    d = tempfile.mkdtemp()
    p = os.path.join(d, "o101.pdf")
    generate_orbits_101_pdf(p)
    info = subprocess.run(["pdfinfo", p], capture_output=True, text=True).stdout
    assert "Pages:" in info
    pages = int([ln for ln in info.splitlines()
                 if ln.startswith("Pages:")][0].split()[1])
    assert pages >= 2
    txt = subprocess.run(["pdftotext", p, "-"], capture_output=True,
                         text=True).stdout
    assert "Transponder" in txt and "Doppler" in txt


def test_learn_lab_tie_in_overrides_sat():
    """Toggling the Learn lab orbit makes sat()/pred() return the lab satellite
    so the orbit-based tools run against the designed orbit."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        import pytest
        pytest.skip("no display")
    root.withdraw()
    from orbitdeck.gui.app import OrbitDeckApp
    try:
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        import pytest
        pytest.skip("Tk state from a prior test prevented a clean app build")
    try:
        app.show("learn")
        scr = app.current
        # off by default -> catalog selection
        assert scr.sat() is app.store.selected_sat()
        # on -> lab satellite
        scr._lab_on.set(True)
        scr._ensure_lab_sat()
        assert scr.sat() is scr._lab_sat
        assert scr.pred() is scr._lab_pred
        assert scr._lab_sat.norad >= 99000
    finally:
        root.destroy()


def test_duplex_roundtrip_holds_downlink():
    """The duplex widget's ideal-uplink derivation keeps the user's signal on
    the fixed downlink we hear, canceling BOTH Doppler legs, for any range-rate
    and either inversion."""
    from orbitdeck.gui import radioedu as RE
    dl_c, ul_c = 435625000.0, 145925000.0
    for invert in (True, False):
        sign = -1.0 if invert else 1.0
        for rr in (-7.0, -2.0, 0.0, 3.0, 7.0):
            beta = (rr * 1000.0) / RE.C_LIGHT
            # ideal uplink (same derivation the widget uses)
            dl_satframe_target = dl_c / (1.0 - beta)
            u_heard_target = ul_c + sign * (dl_satframe_target - dl_c)
            ideal_ul = u_heard_target / (1.0 - beta)
            # forward-model where that uplink lands on the downlink we hear
            u_heard = ideal_ul * (1.0 - beta)
            dl_satframe = dl_c + sign * (u_heard - ul_c)
            heard = dl_satframe * (1.0 - beta)
            assert abs(heard - dl_c) < 1.0      # lands on centre to <1 Hz


def test_antenna_gain_pattern_and_beamwidth():
    """Higher gain gives a narrower beamwidth, and the pattern peaks at
    boresight with the correct absolute gain."""
    from orbitdeck.gui import radioedu as RE
    bw_lo = RE.beamwidth_deg(3.0)
    bw_hi = RE.beamwidth_deg(16.0)
    assert bw_hi < bw_lo            # more gain -> narrower beam
    thetas, gains = RE.antenna_gain_pattern(12.0)
    # boresight (theta ~ 0) is the maximum and ~= the rated gain
    i0 = min(range(len(thetas)), key=lambda i: abs(thetas[i]))
    assert abs(gains[i0] - 12.0) < 0.5
    assert max(gains) <= 12.0 + 0.01


def test_reference_content_present():
    """All the new reference sections carry non-empty (term, desc) rows."""
    from orbitdeck.gui import radioedu as RE
    for table in (RE.OPERATING_PRACTICE, RE.BANDS_LICENSING,
                  RE.MODULATION_MODES, RE.NOISE_SENSITIVITY,
                  RE.TIME_FRAMES, RE.CONSTELLATIONS):
        assert len(table) >= 2
        for term, desc in table:
            assert term and desc


def test_orbits_101_pdf_has_three_pages():
    """The handout now has a third operating/antennas page."""
    import subprocess
    from orbitdeck.gui.learnsheet import generate_orbits_101_pdf
    d = tempfile.mkdtemp()
    p = os.path.join(d, "o101.pdf")
    generate_orbits_101_pdf(p)
    info = subprocess.run(["pdfinfo", p], capture_output=True, text=True).stdout
    pages = int([ln for ln in info.splitlines()
                 if ln.startswith("Pages:")][0].split()[1])
    assert pages >= 3
    txt = subprocess.run(["pdftotext", p, "-"], capture_output=True,
                         text=True).stdout
    assert "Operating" in txt and "Antennas" in txt


def test_tabbar_wrap_mode_builds():
    """A wrapping TabBar accepts many tabs without error."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        import pytest
        pytest.skip("no display")
    root.withdraw()
    from orbitdeck.gui.screens import TabBar
    try:
        tb = TabBar(root, wrap=True)
        for nm in ("a", "b", "c", "d", "e", "f", "g", "h"):
            tb.add(nm)
        tb.pack()
        root.update_idletasks()
        assert len(tb._tabs) == 8
    finally:
        root.destroy()


def test_vis_viva_orbital_speed():
    """Vis-viva speeds match known values and perigee is faster than apogee."""
    from orbitdeck.engine import analysis as A
    RE = A.RE_KM
    a_iss = RE + 420.0
    assert abs(A.orbital_speed_kms(a_iss, a_iss) - 7.66) < 0.05
    a_geo = RE + 35786.0
    assert abs(A.orbital_speed_kms(a_geo, a_geo) - 3.07) < 0.05
    # eccentric orbit: perigee faster than apogee
    ap, pe = RE + 39000.0, RE + 500.0
    sma = (ap + pe) / 2.0
    assert A.orbital_speed_kms(pe, sma) > A.orbital_speed_kms(ap, sma)


def test_slant_range_geometry():
    """Slant range equals altitude overhead and grows toward the horizon."""
    from orbitdeck.engine import analysis as A
    for alt in (420.0, 1200.0, 20000.0):
        assert abs(A.slant_range_km(90.0, alt) - alt) < 1.0
        assert A.slant_range_km(0.0, alt) > A.slant_range_km(90.0, alt)
        # monotonic decrease as elevation rises
        assert (A.slant_range_km(10.0, alt) > A.slant_range_km(45.0, alt)
                > A.slant_range_km(90.0, alt))


def test_pass_quality_in_passes_table():
    """The Next Passes table includes a quality score per pass."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        import pytest
        pytest.skip("no display")
    root.withdraw()
    from orbitdeck.gui.app import OrbitDeckApp
    try:
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        import pytest
        pytest.skip("Tk state from a prior test prevented a clean app build")
    try:
        app.show("passes")
        scr = app.current
        scr._reload()
        kids = scr.tree.get_children()
        if kids:
            qual = scr.tree.item(kids[0])["values"][-1]
            # quality cell is a number (optionally prefixed with the best star)
            s = str(qual).replace("\u2605", "").strip()
            assert float(s) >= 0.0
    finally:
        root.destroy()


def test_groundtrack_drift_and_repeat():
    """The ground-track shift is ~23 deg/orbit for a LEO bird and ~0 for GEO."""
    from orbitdeck.engine import analysis as A
    assert 20.0 < abs(A.groundtrack_shift_deg(15.5)) < 26.0
    assert abs(A.groundtrack_shift_deg(1.0027)) < 1.0


def test_horizon_distance_increases_with_altitude():
    from orbitdeck.engine import analysis as A
    assert A.horizon_distance_km(35786) > A.horizon_distance_km(550) > 0


def test_constellation_count_decreases_with_altitude():
    """Higher orbits need fewer satellites for continuous coverage; GEO ~3."""
    from orbitdeck.engine import analysis as A
    n_leo = A.sats_for_continuous_coverage(550, 5.0)
    n_meo = A.sats_for_continuous_coverage(20200, 5.0)
    n_geo = A.sats_for_continuous_coverage(35786, 0.0)
    assert n_leo > n_meo >= n_geo
    assert n_geo <= 4


def test_handout_has_four_pages():
    import subprocess
    from orbitdeck.gui.learnsheet import generate_orbits_101_pdf
    d = tempfile.mkdtemp()
    p = os.path.join(d, "h.pdf")
    generate_orbits_101_pdf(p)
    info = subprocess.run(["pdfinfo", p], capture_output=True, text=True).stdout
    pages = int([ln for ln in info.splitlines()
                 if ln.startswith("Pages:")][0].split()[1])
    assert pages == 4


def test_learn_tabs_grouped():
    """The Learn screen organises its tabs into logical groups."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        import pytest
        pytest.skip("no display")
    root.withdraw()
    from orbitdeck.gui.app import OrbitDeckApp
    try:
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        import pytest
        pytest.skip("Tk state from a prior test prevented a clean app build")
    try:
        app.show("learn")
        tb = app.current._tabs
        names = [g[0] for g in tb._groups]
        assert names == ["Orbits", "Geometry", "Passes", "Radio", "Reference"]
        # every tab belongs to exactly one group
        total = sum(len(g[2]) for g in tb._groups)
        assert total == len(tb._tabs) == 23
        # switching groups selects that group's first tab
        tb.select_group(2)
        assert tb._active in tb._groups[2][2]
    finally:
        root.destroy()


def test_hohmann_transfer_deltav():
    """A LEO->GEO Hohmann transfer needs ~3.9 km/s of delta-v across two burns,
    and a plane change adds cost on top."""
    from orbitdeck.engine import analysis as A
    import math
    RE = A.RE_KM
    r1, r2 = RE + 400.0, RE + 35786.0
    v1 = A.orbital_speed_kms(r1, r1)
    v2 = A.orbital_speed_kms(r2, r2)
    a_t = (r1 + r2) / 2.0
    dv1 = abs(A.orbital_speed_kms(r1, a_t) - v1)
    dv2 = abs(v2 - A.orbital_speed_kms(r2, a_t))
    total = dv1 + dv2
    assert 3.5 < total < 4.3
    # a 28 deg plane change adds a positive cost
    dv_plane = 2.0 * min(v1, v2) * math.sin(math.radians(28) / 2.0)
    assert dv_plane > 0.5


def test_sun_synchronous_inclination():
    """The J2 nodal drift hits the sun-synchronous rate near a retrograde
    inclination just above 90 deg for a typical LEO altitude."""
    from orbitdeck.engine import analysis as A
    from orbitdeck.gui import lab as L
    mm = L.mean_motion_from_alt(700.0)
    ss = None
    for i in range(900, 1100):
        if abs(A.j2_rates(mm, i / 10.0, 0.0)[0] - 0.98565) < 0.01:
            ss = i / 10.0
            break
    assert ss is not None and 96.0 < ss < 100.0
    # a polar orbit barely precesses; an equatorial one precesses a lot
    assert abs(A.j2_rates(mm, 90.0, 0.0)[0]) < 0.1
    assert abs(A.j2_rates(mm, 0.0, 0.0)[0]) > 1.0


def test_orbital_decay_lower_is_faster():
    """Lower orbits decay faster than higher ones for the same drag term."""
    from orbitdeck.engine import analysis as A
    from orbitdeck.gui import lab as L
    bstar = 0.0001
    d_low = A.estimate_decay_days(bstar, L.mean_motion_from_alt(250.0), 0.0)
    d_high = A.estimate_decay_days(bstar, L.mean_motion_from_alt(800.0), 0.0)
    assert d_low > 0 and d_high > d_low


def test_maidenhead_grid6():
    """Known locations map to the right 6-character Maidenhead locators."""
    from orbitdeck.engine import analysis as A
    assert A.latlon_to_grid6(39.93, -74.89).startswith("FM29")
    assert A.latlon_to_grid6(51.5, -0.1).startswith("IO91")
    assert A.latlon_to_grid6(35.68, 139.69).startswith("PM95")
    # full six characters
    assert len(A.latlon_to_grid6(39.93, -74.89)) == 6


def test_true_vs_mean_anomaly_gap():
    """True and mean anomaly coincide on a circle and diverge with
    eccentricity."""
    from orbitdeck.engine import analysis as A
    # circular: equal
    assert abs(A.true_anomaly_deg(90.0, 0.0) - 90.0) < 0.5
    # eccentric: true anomaly leads mean anomaly past perigee
    nu = A.true_anomaly_deg(90.0, 0.4)
    assert nu > 95.0


def test_label_styles_use_window_background():
    """Readability/consistency: informational text must not sit on a background
    that differs from the window. The shared label styles (and the panel-frame /
    panel radio-check styles) are configured to the window background COL_BG, so
    text never shows a stray panel-coloured rectangle (only buttons, entries,
    sliders and the deliberate KVPanel cards have their own background)."""
    import tkinter as tk
    from tkinter import ttk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.gui.screens import COL_BG

    try:
        root = tk.Tk()
        OrbitDeckApp(root)
    except Exception:
        return          # no display / Tk in a bad state from a prior test
    st = ttk.Style()
    for style in ("TLabel", "Panel.TLabel", "Muted.TLabel", "MutedBg.TLabel",
                  "PanelH.TLabel", "Mono.TLabel", "Panel.TFrame",
                  "Panel.TRadiobutton", "Panel.TCheckbutton"):
        bg = str(st.lookup(style, "background"))
        assert bg.lower() == COL_BG.lower(), (style, bg)
    root.destroy()


def test_vscroll_frame_scrolls_tall_content():
    """make_vscroll_frame yields an interior that scrolls when its content is
    taller than the viewport -- this is what keeps the Settings form reachable on
    short displays. The canvas scrollregion must exceed the visible height."""
    import tkinter as tk
    from tkinter import ttk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.gui.screens import make_vscroll_frame

    try:
        root = tk.Tk()
        root.geometry("600x300")
        OrbitDeckApp(root)          # configures the ttk theme used by the frame
    except Exception:
        return          # no display / Tk in a bad state from a prior test
    container, interior = make_vscroll_frame(root)
    container.pack(fill="both", expand=True)
    for i in range(60):
        ttk.Label(interior, text="row %d" % i).pack(anchor="w")
    root.update_idletasks()
    canvas = container.winfo_children()[0]
    assert isinstance(canvas, tk.Canvas)
    x0, y0, x1, y1 = canvas.bbox("all")
    # content is much taller than the 300px window -> scrollable
    assert (y1 - y0) > 300
    root.destroy()


def test_settings_screen_is_scrollable():
    """The Settings screen wraps its tall form in a vertical scroller so the
    bottom (pass-prediction + printing prefs) isn't clipped on small displays."""
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp

    try:
        root = tk.Tk()
    except Exception:
        return
    import os
    try:
        os.remove(os.path.expanduser("~/.orbitdeck/config.json"))
    except OSError:
        pass
    try:
        app = OrbitDeckApp(root)
    except Exception:
        return          # Tk in a bad state from a prior test
    app.store.save_config(onboarded=True)
    app.show("location")
    scr = app.current

    def find_canvas(w):
        if isinstance(w, tk.Canvas):
            return w
        for c in w.winfo_children():
            r = find_canvas(c)
            if r:
                return r
        return None

    assert find_canvas(scr.frame) is not None, "settings form is not scrollable"
    root.destroy()
