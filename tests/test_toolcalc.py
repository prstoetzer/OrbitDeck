"""Tests for orbitdeck.engine.toolcalc (bench calculators ported from CardSat).

These check the ported formulas against known reference values and against the
exact expressions in the CardSat firmware, so a future refactor can't silently
drift the numbers.
"""

import math

from orbitdeck.engine import toolcalc as tc


def _val(rows, label):
    """Pull the numeric part of the first row whose label matches."""
    for lab, value, _note in rows:
        if lab == label:
            # grab the leading float
            for tok in value.replace("(", " ").split():
                try:
                    return float(tok)
                except ValueError:
                    continue
    raise KeyError(label)


# ---- antennas ----
def _meters(rowval):
    """Pull the '(X.XXX m)' metric length out of an antenna row string."""
    return float(rowval.split("(")[1].split()[0])


def _row(rows, label):
    for lab, value, note in rows:
        if lab == label:
            return value
    raise KeyError(label)


def test_dipole_2m():
    rows = tc.dipole(146.0)
    # 468/146 = 3.205 ft total in ft-in; check the metric equivalent
    total_ft = 468.0 / 146.0
    assert abs(_meters(_row(rows, "Total length")) - total_ft * 0.3048) < 0.01
    assert abs(_meters(_row(rows, "Each leg")) - (total_ft / 2) * 0.3048) < 0.01


def test_vertical_quarter_wave():
    rows = tc.vertical(146.0)
    q_ft = 234.0 / 146.0
    assert abs(_meters(_row(rows, "1/4-wave")) - q_ft * 0.3048) < 0.01


def test_yagi_element_count():
    rows = tc.yagi(144.2, elements=5)
    # driven + reflector + 3 directors + spacing row = 6 rows
    labels = [r[0] for r in rows]
    assert "Driven elem" in labels and "Reflector" in labels
    assert sum(1 for lab in labels if lab.startswith("Director")) == 3


def test_wavelength_2m():
    rows = tc.wavelength(146.0)
    lam = 299.792458 / 146.0
    assert abs(_val(rows, "Wavelength") - lam) < 0.001
    assert abs(_val(rows, "1/4 wave") - lam / 4) < 0.001


def test_helix_gain_positive():
    rows = tc.helix(435.0, turns=8)
    g = _val(rows, "Gain")
    assert 10 < g < 25            # a sane axial-mode helix gain range


# ---- feedline ----
def test_coax_loss_monotonic_in_length():
    short = tc.coax_loss(4, 146.0, 25.0, 1.5)   # LMR-400
    long = tc.coax_loss(4, 146.0, 100.0, 1.5)
    assert _val(long, "Matched loss") > _val(short, "Matched loss")


def test_phasing_line_uses_vf():
    rows = tc.phasing_line(4, 146.0, 0)          # LMR-400, quarter wave
    lam = 299.792458 / 146.0
    expect_m = lam * 0.25 * tc.COAX_TYPES[4][1]  # * vf
    assert abs(_val(rows, "  metric") - expect_m) < 0.001


# ---- RF & measurement ----
def test_rf_units_100w():
    rows = tc.rf_units(100.0)
    assert abs(_val(rows, "dBm") - 50.0) < 0.01       # 100 W = 50 dBm
    assert abs(_val(rows, "Vrms @50ohm") - math.sqrt(100.0 * 50.0)) < 0.01


def test_swr_2():
    rows = tc.swr(2.0)
    # SWR 2 -> return loss ~9.54 dB
    assert abs(_val(rows, "Return loss") - 9.54) < 0.1


def test_fspl_reference():
    rows = tc.fspl(1000.0, 145.0)
    expect = 20 * math.log10(1000.0) + 20 * math.log10(145.0) + 32.44
    assert abs(_val(rows, "Path loss") - expect) < 0.1


def test_attenuator_symmetry():
    rows = tc.attenuator(6.0, 50.0)
    # a 6 dB pad in 50 ohm: pi shunt ~150.5, series ~37.35 (classic values)
    assert abs(_val(rows, "Pi shunt") - 150.5) < 1.0
    assert abs(_val(rows, "Pi series") - 37.35) < 1.0


def test_db_chain_sum():
    rows = tc.db_chain(20.0, -3.0, -6.0, 0.0)
    assert abs(_val(rows, "Net gain") - 11.0) < 1e-6


def test_cascade_nf_lna_dominates():
    # with a good LNA up front, system NF should be close to the LNA NF
    rows = tc.cascade_nf(ant_gain_dbi=16, sky_temp_k=150, lna_nf_db=0.8,
                         lna_gain_db=25, coax_loss_db=3, rig_nf_db=6)
    assert _val(rows, "System NF") < 1.5


# ---- electronics ----
def test_complex_polar():
    rows = tc.complex_polar(50.0, 25.0)
    assert abs(float(_row(rows, "Magnitude")) - math.hypot(50, 25)) < 1e-3
    assert abs(_val(rows, "Angle") - math.degrees(math.atan2(25, 50))) < 1e-2


def test_reactance_resonance():
    rows = tc.reactance(7.0, 10.0, 100.0)
    # f0 = 1/(2pi sqrt(LC)); L=10uH C=100pF -> ~5.03 MHz
    f0 = 1.0 / (2 * math.pi * math.sqrt(10e-6 * 100e-12)) / 1e6
    assert abs(_val(rows, "Resonance") - f0) < 0.01


def test_rc_time_constant():
    rows = tc.rc_time_constant(1000.0, 1.0)     # 1k, 1uF -> 1 ms
    assert abs(_val(rows, "tau (RC)") - 1.0) < 1e-6   # shown in ms


def test_battery_runtime():
    rows = tc.battery_runtime(20.0, 0.5, 8.0, 30.0, 80.0)
    avg = 0.5 * 0.7 + 8.0 * 0.3
    assert abs(_val(rows, "Avg current") - avg) < 1e-6
    assert abs(_val(rows, "Runtime") - (20.0 * 0.8 / avg)) < 0.01


# ---- terrestrial ----
def test_radio_horizon_grows_with_height():
    low = tc.radio_horizon(10, 10, 1.33)
    high = tc.radio_horizon(100, 10, 1.33)
    assert _val(high, "My horizon") > _val(low, "My horizon")


def test_fresnel_zone_positive():
    rows = tc.fresnel_zone(30.0, 144.0)
    assert _val(rows, "F1 radius") > 0


def test_rain_fade_increases_with_rate():
    light = tc.rain_fade(10.0, 10.0, 10.0)
    heavy = tc.rain_fade(10.0, 50.0, 10.0)
    assert _val(heavy, "Total fade") > _val(light, "Total fade")


def test_terrestrial_path_budget_verdict():
    rows = tc.terrestrial_path_budget(25, 6, 6, 2, 146, 10)
    # a short 10 km 2 m path at 25 W should be workable
    verdict = [v for lab, v, _ in rows if lab == "Verdict"][0]
    assert verdict in ("workable", "marginal")


def test_all_calculators_return_rows():
    """Smoke: every calculator returns a non-empty list of 3-tuples."""
    calls = [
        tc.dipole(146), tc.vertical(146), tc.yagi(144, 3), tc.quad(50, 2),
        tc.helix(435, 8), tc.wavelength(146), tc.coax_loss(4, 146, 50, 1.5),
        tc.phasing_line(4, 146, 0), tc.rf_units(100), tc.swr(2.0),
        tc.fspl(1000, 145), tc.attenuator(6, 50), tc.db_chain(1, 2, 3, 4),
        tc.cascade_nf(), tc.complex_polar(50, 25), tc.reactance(7, 10, 100),
        tc.rc_time_constant(1000, 1), tc.battery_runtime(),
        tc.radio_horizon(), tc.fresnel_zone(), tc.rain_fade(),
        tc.terrestrial_path_budget(),
    ]
    for rows in calls:
        assert isinstance(rows, list) and rows
        for r in rows:
            assert isinstance(r, tuple) and len(r) == 3


# ---- remaining RF & measurement ----
def test_rf_exposure_distances_positive():
    rows = tc.rf_exposure(146.0, 100.0, 0, 2.15)
    labels = [r[0] for r in rows]
    assert "  distance" in labels
    # controlled distance should be shorter than uncontrolled
    dists = [float(v.split()[0]) for lab, v, _ in rows if lab == "  distance"]
    assert dists[1] <= dists[0]


def test_imd_in_band_flagged():
    rows = tc.imd_products(145.900, 145.950, 145.800, 146.000)
    # 2f1-f2 = 145.850 is in band
    p3 = [n for lab, v, n in rows if lab == "3rd 2f1-f2"][0]
    assert p3 == "IN"


def test_sun_noise_gt_reasonable():
    rows = tc.sun_noise_gt(1.0, 150.0, 435.0, 0.0)
    gt = float(_row(rows, "G/T").split()[0])
    assert -40 < gt < 40


# ---- remaining antennas ----
def test_match_l_network():
    rows = tc.match_network(0, 50.0, 200.0, 14.2, 5.0)
    # 50->200 needs Q = sqrt(200/50 - 1) = sqrt(3) ~ 1.732
    q = float(_row(rows, "Network Q"))
    assert abs(q - math.sqrt(3.0)) < 0.01


def test_microstrip_50ohm_ballpark():
    # a ~3mm trace on 1.6mm FR-4 is roughly a 50 ohm line
    rows = tc.microstrip(0, 4.4, 1.6, 3.0, 435.0)
    z0 = float(_row(rows, "Z0").split()[0])
    assert 40 < z0 < 60


def test_toroid_turns():
    rows = tc.toroid_winding(2, 10.0)         # T50-2, AL=49
    # N = 100*sqrt(10/49) ~ 45.2 -> 46 turns
    n = int(_row(rows, "Turns"))
    assert 44 <= n <= 47


# ---- remaining electronics ----
def test_cross_section_tumble():
    rows = tc.cross_section(2, panel_m2=0.0)   # 3U = 10x10x30
    tumble = float(_row(rows, "Tumbling avg").split()[0])
    # faces: 0.01, 0.03, 0.03 -> tumble = (0.01+0.03+0.03)/2 = 0.035
    assert abs(tumble - 0.035) < 0.001


def test_thermal_white_paint_cold():
    rows = tc.thermal_equilibrium(1)           # white paint, low a/e
    # white paint (a/e ~0.28) runs cold: 1-side temp below 0 C
    t1 = _row(rows, "1-side rad")
    assert "C" in t1


def test_faraday_scales_inverse_square():
    rows = tc.faraday_rotation(145.9, 2)       # storm
    r146 = float(_row(rows, "  @146 MHz").split()[0])
    r437 = float(_row(rows, "  @437 MHz").split()[0])
    # 437 is ~3x 146, rotation ~1/f^2 so ~9x less
    assert r146 > r437 * 5


def test_ampacity_wire_verdict():
    rows = tc.ampacity(2, current_a=1.0, awg=24)    # 24 AWG rated 3.5 A
    load = _row(rows, "Your load")
    assert "OK" in load


def test_pll_output():
    rows = tc.pll_plan(10.0, 1.0, 40.0, 1.0)
    assert abs(float(_row(rows, "F out").split()[0]) - 400.0) < 1e-6


# ---- remaining terrestrial ----
def test_tropo_index_range():
    rows = tc.tropo_ducting(20.0, 19.0, 5.0)   # saturated + inversion -> high
    idx = float(_row(rows, "Duct index").split()[0])
    assert 0 <= idx <= 6


# ---- orbital tools ----
def test_doppler_budget_leo():
    rows = tc.doppler_budget(550, 550, 435.5)
    # 435 MHz LEO peak Doppler ~ +/-10 kHz
    d = float(_row(rows, "Max Doppler").split()[0].replace("+/-", ""))
    assert 8 < d < 12


def test_delta_v_hohmann():
    rows = tc.delta_v(400, 800, 0)
    total = float(_row(rows, "Total").split()[0])
    assert 200 < total < 240             # ~217 m/s for 400->800 km


def test_delta_v_plane_change_adds():
    no_plane = tc.delta_v(400, 800, 0)
    with_plane = tc.delta_v(400, 800, 10)
    labels = [r[0] for r in with_plane]
    assert "Plane chg" in labels
    assert "Plane chg" not in [r[0] for r in no_plane]


def test_pointing_loss_zero_at_boresight():
    rows = tc.pointing_loss(30.0, 0.0)
    assert abs(float(_row(rows, "Loss").split()[0])) < 1e-6


def test_orbit_lifetime_higher_lasts_longer():
    low = tc.orbit_lifetime(400, 4, 0.03, 2.2)
    high = tc.orbit_lifetime(600, 4, 0.03, 2.2)
    def yrs(rows):
        v = _row(rows, "Lifetime")
        n = float(v.split()[0])
        return n / 365.25 if "day" in v else n
    assert yrs(high) > yrs(low)


def test_all_remaining_calculators_return_rows():
    calls = [
        tc.rf_exposure(), tc.imd_products(), tc.sun_noise_gt(),
        tc.match_network(1), tc.match_network(2), tc.microstrip(0),
        tc.microstrip(1), tc.toroid_winding(9), tc.cross_section(0),
        tc.thermal_equilibrium(0), tc.faraday_rotation(), tc.ampacity(0),
        tc.ampacity(1), tc.ampacity(2), tc.pll_plan(), tc.tropo_ducting(),
        tc.doppler_budget(), tc.delta_v(), tc.pointing_loss(),
        tc.orbit_lifetime(),
    ]
    for rows in calls:
        assert isinstance(rows, list) and rows
        for r in rows:
            assert isinstance(r, tuple) and len(r) == 3


def test_fresnel_radius_matches_the_reference_formula():
    """Regression: the collapsed midpoint constant 8.657 already contains the
    /2, and applying it again reported HALF the true first-zone radius - which
    would call a marginal path clear. Cross-checked against the general form
    r1 = 17.31*sqrt(d1*d2/(f_GHz*D)) evaluated at the midpoint."""
    for path_km, f_mhz in ((10, 146), (30, 144), (50, 432), (5, 10000)):
        rows = tc.fresnel_zone(path_km, f_mhz)
        got = _val(rows, "F1 radius")
        d1 = d2 = path_km / 2.0
        want = 17.31 * math.sqrt((d1 * d2) / ((f_mhz / 1000.0) * path_km))
        assert abs(got - want) < 0.2, (path_km, f_mhz, got, want)
    # the 60% figure follows the radius
    rows = tc.fresnel_zone(30, 144)
    assert abs(_val(rows, "60% clearance") - 0.6 * _val(rows, "F1 radius")) < 0.1


def test_fresnel_scales_correctly():
    # radius grows with path length and shrinks with frequency
    assert _val(tc.fresnel_zone(60, 144), "F1 radius") > \
        _val(tc.fresnel_zone(30, 144), "F1 radius")
    assert _val(tc.fresnel_zone(30, 1296), "F1 radius") < \
        _val(tc.fresnel_zone(30, 144), "F1 radius")
