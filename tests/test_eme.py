"""EME analysis: per-band figures and the 90-day planner (CardSat parity)."""

import time

from orbitdeck.engine import celestial as CE


def test_moon_declination_and_galactic_latitude():
    t = time.time()
    dec = CE.moon_dec_deg(t)
    assert -29 < dec < 29                    # the Moon stays inside ~28.5 deg
    b = CE.moon_galactic_lat_deg(t)
    assert -90 <= b <= 90


def test_faraday_falls_as_inverse_square_of_frequency():
    """Faraday matters on 6 m and 2 m and not above 1296 - that is the whole
    reason the figure is shown per band."""
    f144 = CE.eme_faraday_deg(144.0, 120.0)
    f432 = CE.eme_faraday_deg(432.0, 120.0)
    f1296 = CE.eme_faraday_deg(1296.0, 120.0)
    assert abs(f144 - 90.0) < 1.0            # ~quarter turn at mid flux
    assert abs(f432 - f144 / 9.0) < 0.5      # (432/144)^2 = 9
    assert f1296 < 2.0
    # and it scales with solar flux
    assert CE.eme_faraday_deg(144.0, 240.0) > CE.eme_faraday_deg(144.0, 60.0)


def test_sky_temperature_drops_with_frequency():
    t = time.time()
    t144 = CE.eme_sky_temp_k(t, 144.0)
    t432 = CE.eme_sky_temp_k(t, 432.0)
    t10g = CE.eme_sky_temp_k(t, 10368.0)
    assert t144 > t432 > t10g
    assert t10g > 2.0                        # never below the CMB floor


def test_libration_spread_scales_linearly():
    assert abs(CE.eme_libration_spread_hz(144.0) - 2.5) < 0.01
    assert abs(CE.eme_libration_spread_hz(288.0) - 5.0) < 0.01
    assert CE.eme_libration_spread_hz(10368.0) > 100


def test_path_degradation_is_zero_near_perigee_and_positive_at_apogee():
    """This is the number that decides which weeks are worth operating."""
    rows = CE.eme_plan(time.time(), days=60)
    degr = [r["degradation_db"] for r in rows]
    assert min(degr) < 1.0
    assert max(degr) > 1.5
    assert max(degr) - min(degr) > 1.0       # the perigee/apogee cycle shows


def test_band_analysis_shape_and_physics():
    t = time.time()
    rows = CE.eme_band_analysis(t, 39.93, -74.89, solar_flux=95.0)
    assert len(rows) == 5
    for r in rows:
        for k in ("band", "doppler_hz", "faraday_deg", "sky_temp_k",
                  "spread_hz", "path_loss_db"):
            assert k in r
    by = {r["freq_mhz"]: r for r in rows}
    # 2 m EME path loss is about 252 dB two-way
    assert 245 < by[144.0]["path_loss_db"] < 258
    # loss and Doppler both grow with frequency
    assert by[10368.0]["path_loss_db"] > by[144.0]["path_loss_db"]
    assert abs(by[10368.0]["doppler_hz"]) > abs(by[144.0]["doppler_hz"])


def test_ground_gain_window():
    """Below ~8 degrees the ground reflection adds - the reason EME operators
    favour moonrise and moonset."""
    assert CE.eme_ground_gain(3.0)[0] is True
    assert CE.eme_ground_gain(20.0)[0] is False
    assert CE.eme_ground_gain(-5.0)[0] is False
    assert "down" in CE.eme_ground_gain(-5.0)[1]


def test_sun_separation_is_an_angle():
    sep = CE.eme_sun_separation_deg(39.93, -74.89, time.time())
    assert 0.0 <= sep <= 180.0


def test_eme_plan_rows():
    rows = CE.eme_plan(time.time(), days=90)
    assert len(rows) == 90
    for r in rows:
        assert -29 < r["dec_deg"] < 29
        assert r["degradation_db"] >= -0.5
        assert 350000 < r["distance_km"] < 410000
        assert r["good"] == (r["dec_deg"] > 15.0 and r["degradation_db"] < 1.0)
    # sampled a day apart at a fixed hour, so rows compare like with like
    assert abs((rows[1]["t"] - rows[0]["t"]) - 86400) < 1


def test_eme_screens_expose_the_new_views():
    import inspect
    from orbitterm.screens.analysis2 import EmeScreen
    assert EmeScreen.VIEWS == ["live", "bands", "plan"]
    from orbitdeck.gui.screens import eme
    src = inspect.getsource(eme.EmeScreen)
    for want in ("_fill_bands", "_fill_plan", "eme_band_analysis", "eme_plan"):
        assert want in src
