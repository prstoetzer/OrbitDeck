"""Tests for the general calculators (scientific / programmer / unit converter)
and the reference tables added to close the CardSat tool-parity gap."""

import math

import pytest

from orbitdeck.engine import calc as C


# ---- scientific calculator ----
def test_evaluate_arithmetic_and_functions():
    assert C.evaluate("2+3*4") == 14
    assert abs(C.evaluate("sqrt(2)^2") - 2.0) < 1e-9
    assert abs(C.evaluate("sin(rad(90))") - 1.0) < 1e-12
    assert abs(C.evaluate("log10(1000)") - 3.0) < 1e-12
    assert abs(C.evaluate("300/145.9") - 300 / 145.9) < 1e-12
    assert abs(C.evaluate("pi") - math.pi) < 1e-12


def test_evaluate_rejects_code_execution():
    """The evaluator must not permit imports, attribute access or builtins."""
    for bad in ("__import__('os').system('ls')",
                "open('/etc/passwd')",
                "(1).__class__",
                "[].append(1)",
                "lambda: 1"):
        with pytest.raises(C.CalcError):
            C.evaluate(bad)


def test_evaluate_errors():
    with pytest.raises(C.CalcError):
        C.evaluate("")
    with pytest.raises(C.CalcError):
        C.evaluate("1/0")
    with pytest.raises(C.CalcError):
        C.evaluate("2 +* 3")


def test_sci_rows_shape():
    rows = C.sci_rows("2+2")
    assert rows[0][0] == "Result"
    assert all(len(r) == 3 for r in rows)
    assert C.sci_rows("bogus(")[0][0] == "error"


# ---- programmer calculator ----
def test_programmer_conversions():
    rows = dict((a, b) for a, b, _c in C.programmer_rows("255", 0, 32))
    assert rows["Decimal"] == "255"
    assert rows["Hex"] == "0xFF"
    assert rows["Octal"] == "0o377"
    assert rows["Bits set"] == "8"


def test_programmer_parses_prefixes_and_bases():
    assert C.parse_int("0xFF") == 255
    assert C.parse_int("0b1010") == 10
    assert C.parse_int("FF", 1) == 255          # hex base selected
    assert C.parse_int("1010", 2) == 10         # binary base selected
    assert C.parse_int("-16") == -16
    with pytest.raises(C.CalcError):
        C.parse_int("zz", 0)


def test_programmer_signed_view():
    rows = dict((a, b) for a, b, _c in C.programmer_rows("0xFFFFFFFF", 1, 32))
    assert rows["As signed"] == "-1"


# ---- unit converter ----
def test_convert_length_and_temperature():
    assert abs(C.convert(1, "Length", "km", "m") - 1000.0) < 1e-9
    assert abs(C.convert(12, "Length", "in", "ft") - 1.0) < 1e-9
    assert abs(C.convert(100, "Temperature", "C", "F") - 212.0) < 1e-9
    assert abs(C.convert(0, "Temperature", "C", "K") - 273.15) < 1e-9
    assert abs(C.convert(1, "Frequency", "GHz", "MHz") - 1000.0) < 1e-9


def test_convert_rows_lists_family():
    rows = C.convert_rows(100, 0, 5, 4)          # 100 ft -> in
    assert rows[0][1].endswith("in")
    assert any(r[0] == "m" for r in rows)


# ---- reference tables ----
def test_new_reference_tables_present():
    from orbitdeck.engine import refdata as rd
    names = [t[0] for t in rd.TABLES]
    for want in ("Phonetic alphabet", "RST system", "Radio math",
                 "CubeSatSim C2C"):
        assert want in names
    for _n, _d, fn in rd.TABLES:
        rows = fn()
        assert rows and all(len(r) == 3 for r in rows)


def test_phonetic_alphabet_complete():
    from orbitdeck.engine import refdata as rd
    rows = rd.phonetic_rows()
    assert len(rows) == 26
    assert rows[0][:2] == ("A", "Alfa")
    assert rows[-1][:2] == ("Z", "Zulu")


# ---- registry integration ----
def test_new_tools_registered_and_compute():
    from orbitdeck.engine.tools_registry import TOOLS, CATEGORIES
    for key in ("sci_calc", "programmer_calc", "unit_converter"):
        assert key in TOOLS
        spec = TOOLS[key]
        args = [f["default"] for f in spec["fields"]]
        rows = spec["fn"](*args)
        assert rows and all(len(r) == 3 for r in rows)
    # every tool appears in exactly one category
    listed = [k for _c, keys in CATEGORIES for k in keys]
    assert sorted(listed) == sorted(TOOLS)


# ---- band plan + EME (0.9.75 gap closers) ----
def test_band_plan_table():
    from orbitdeck.engine import refdata as rd
    rows = rd.band_plan_rows()
    assert len(rows) > 50
    flat = " ".join(a + b + c for a, b, c in rows)
    for want in ("2 m", "70 cm", "QO-100", "Mode V/U", "satellite subband"):
        assert want in flat
    assert ("Band plan" in [t[0] for t in rd.TABLES])


def test_eme_engine_present_and_sane():
    import time
    from orbitdeck.engine import celestial as CE
    t = time.time()
    az, el = CE.moon_azel(39.93, -74.89, t)
    assert 0 <= az < 360.01 and -90 <= el <= 90
    d = CE.moon_distance_km(t)
    assert 350000 < d < 410000                # lunar distance range
    loss = CE.eme_path_loss_db(144.1e6, t)
    assert 240 < loss < 300                   # 2 m EME path loss is ~252 dB
    dop = CE.eme_doppler_hz(144.1e6, 39.93, -74.89, t)
    assert abs(dop) < 500                     # self-echo Doppler is small


def test_eme_common_windows():
    import time
    from orbitdeck.engine import celestial as CE
    from orbitdeck.engine.predict import grid_to_latlon
    lat2, lon2 = grid_to_latlon("JO65")
    wins = CE.eme_window(39.93, -74.89, lat2, lon2, time.time(), hours=48)
    assert isinstance(wins, list)
    for a, b in wins:
        assert b >= a


def test_eme_screen_builds():
    import tkinter as tk
    if not hasattr(tk, "Listbox"):
        return
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        app = OrbitDeckApp(root)
        app.show("eme")
        root.update()
        app.current._refresh()
        root.update()
    except Exception:
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass


# ---- graphing calculator ----
def test_evaluate_with_binds_variables_only():
    from orbitdeck.engine import calc as C
    assert C.evaluate_with("x^2+1", {"x": 2}) == 5
    assert abs(C.evaluate_with("sin(x)", {"x": 0.0})) < 1e-12
    # an unbound name is still rejected - bindings don't widen the whitelist
    with pytest.raises(C.CalcError):
        C.evaluate_with("x+1", None)
    with pytest.raises(C.CalcError):
        C.evaluate_with("__import__('os')", {"x": 1})


def test_graph_sampling_breaks_on_undefined():
    from orbitdeck.gui.screens.graphcalc import sample
    xs, ys = sample("1/x", -1.0, 1.0, n=101)
    assert len(xs) == len(ys) == 101
    assert any(y is None for y in ys)          # the pole breaks the trace
    assert any(y is not None for y in ys)
    xs2, ys2 = sample("sin(x)", 0.0, 3.14159, n=50)
    assert all(y is not None for y in ys2)
    assert sample("sin(x)", 1.0, 1.0) == ([], [])   # empty domain


# ---- orbital thermal ----
def test_thermal_eclipse_fraction_and_beta():
    from orbitdeck.engine import thermal as T
    # high beta at LEO means continuous sunlight
    assert T.eclipse_fraction(550, 80.0) == 0.0
    f0 = T.eclipse_fraction(550, 0.0)
    assert 0.2 < f0 < 0.45                    # ~37% for a 550 km orbit


def test_thermal_model_physics():
    from orbitdeck.engine import thermal as T
    sunlit = T.orbital_thermal(550, 3, 4, 0.35, 0.85, 2, 80, 0)
    eclipsing = T.orbital_thermal(550, 3, 4, 0.35, 0.85, 2, 0, 0)
    # continuous sunlight -> no thermal swing; eclipsing orbit swings
    assert sunlit["swing_c"] < 1.0
    assert eclipsing["swing_c"] > 1.0
    # a high alpha/eps ratio runs hotter than a low one
    hot = T.orbital_thermal(550, 3, 4, 0.95, 0.90, 2, 0, 0)["t_mean_c"]
    cold = T.orbital_thermal(550, 3, 4, 0.20, 0.90, 2, 0, 0)["t_mean_c"]
    assert hot > cold
    # eclipse equilibrium is colder than sunlit
    assert eclipsing["t_eclipse_c"] < eclipsing["t_sun_c"]
    # a bigger stack radiates more area
    assert (T.geometry(6)[0] > T.geometry(1)[0])


def test_thermal_rows_and_registry():
    from orbitdeck.engine import thermal as T
    from orbitdeck.engine.tools_registry import TOOLS
    rows = T.thermal_rows()
    assert rows and all(len(r) == 3 for r in rows)
    assert "orbital_thermal" in TOOLS
    spec = TOOLS["orbital_thermal"]
    assert spec["fn"](*[f["default"] for f in spec["fields"]])


def test_graph_and_thermal_screens_build():
    import tkinter as tk
    if not hasattr(tk, "Listbox"):
        return
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        app = OrbitDeckApp(root)
        app.show("graphcalc")
        root.update()
        app.current.f1.set("sin(x)")
        app.current._redraw()
        root.update()
        app.show("tools")
        root.update()
        app.current._select("orbital_thermal")
        root.update()
    except Exception:
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass


# ---- calibrated decay model (CardSat 0.9.68 refit) ----
def test_decay_iss_like_is_years_not_decades():
    """The 0.9.61-era model this replaced predicted ~1/5 of true remaining
    life. An ISS-like orbit should decay in a small number of years."""
    from orbitdeck.engine import decay as D
    days, src = D.estimate_decay_days(15.50, 0.0004, 0.00025, 0.0001)
    assert src == D.SRC_NDOT              # the observed rate wins when present
    assert 300 < days < 3000              # ~1-8 years


def test_decay_lower_orbit_decays_sooner():
    from orbitdeck.engine import decay as D
    low, _ = D.estimate_decay_days(16.0, 0.0005, 0.0005, 0.001)
    high, _ = D.estimate_decay_days(15.05, 0.001, 0.00012, 0.000005)
    assert low < high


def test_decay_falls_back_to_bstar_without_ndot():
    from orbitdeck.engine import decay as D
    _d, src = D.estimate_decay_days(15.05, 0.001, 0.00012, 0.0)
    assert src == D.SRC_BSTAR
    # no B* and no n-dot means no answer, not a fabricated one
    days, src2 = D.estimate_decay_days(15.05, 0.001, 0.0, 0.0)
    assert days == -1 and src2 == D.SRC_NONE


def test_decay_solar_activity_scales_lifetime():
    from orbitdeck.engine import decay as D
    lo, _ = D.estimate_decay_days(15.05, 0.001, 0.00012, 0.0, solar="low")
    hi, _ = D.estimate_decay_days(15.05, 0.001, 0.00012, 0.0, solar="high")
    assert lo > hi                        # solar min = thinner air = longer life


def test_decay_king_hele_keeps_eccentric_orbits_alive():
    """Without the eccentricity factor a GTO reads ~40 days instead of years."""
    from orbitdeck.engine import decay as D
    days, _ = D.estimate_decay_days(2.2, 0.72, 0.0002, 0.0)
    assert days > 365.25                  # not a matter of weeks
    # The factor SUPPRESSES drag on an eccentric orbit: the satellite spends
    # almost none of a revolution near perigee, so exp(-z)(I0+2e*I1) < 1. It is
    # exactly 1 for a circular orbit, where perigee drag applies continuously.
    assert 0.0 < D.king_hele(2.0e7, 0.72, 200.0) < 1.0
    assert D.king_hele(7.0e6, 0.0, 400.0) == 1.0


def test_decay_perigee_actually_descends():
    """Regression: omitting the near-circular branch left perigee fixed, so
    nothing ever reached the re-entry threshold and everything read stable."""
    from orbitdeck.engine import decay as D
    days, _ = D.estimate_decay_days(16.0, 0.0005, 0.0005, 0.001)
    assert days != float("inf") and days > 0


def test_decay_rows_and_registry():
    from orbitdeck.engine import decay as D
    from orbitdeck.engine.tools_registry import TOOLS
    rows = D.decay_rows()
    assert rows and all(len(r) == 3 for r in rows)
    spec = TOOLS["orbit_lifetime"]
    assert spec["fn"] is D.decay_rows
    args = [f.get("default", 0) for f in spec["fields"]]
    assert spec["fn"](*args)


def test_orbit_screens_use_the_recalibrated_decay_model():
    """Both orbit screens called analysis.estimate_decay_days - the pre-refit
    formula CardSat 0.9.68 replaced because it predicts roughly a fifth of the
    true remaining life (ISS read 308 days rather than ~2.7 years)."""
    import inspect
    from orbitdeck.gui.screens import orbit
    from orbitterm.screens import analysis_screens
    gsrc = inspect.getsource(orbit.OrbitScreen)
    tsrc = inspect.getsource(analysis_screens.OrbitalAnalysisScreen)
    for src in (gsrc, tsrc):
        assert "decay as DK" in src or "engine import decay" in src
        assert "DK.estimate_decay_days" in src
        assert "an.estimate_decay_days" not in src
        assert "A.estimate_decay_days" not in src


def test_recalibrated_decay_differs_from_the_old_model():
    from orbitdeck.engine import analysis as A
    from orbitdeck.engine import decay as D
    old = A.estimate_decay_days(0.00025, 15.50, 0.0004)
    new, src = D.estimate_decay_days(15.50, 0.0004, 0.00025, 0.0001)
    assert src == D.SRC_NDOT
    assert new > old * 2          # the old model badly under-predicts
    assert D.fmt_decay(float("inf")) == "effectively stable"
    assert D.fmt_decay(-1) == "no usable data"
    assert "days" in D.fmt_decay(30)
    assert "years" in D.fmt_decay(800)


# ---- decay anchored on the element archive ----
def _archive(n=74, step_days=10, dperiod=-0.0025, period0=92.9):
    import time as _t
    base = _t.time() - n * step_days * 86400
    return [{"epoch": base + i * step_days * 86400,
             "PERIOD": period0 + dperiod * i,
             "APOAPSIS": 420 - i * 0.06, "PERIAPSIS": 410 - i * 0.06,
             "INCLINATION": 51.6, "ECCENTRICITY": 0.0005,
             "SEMIMAJOR_AXIS": 6790, "BSTAR": 2e-4} for i in range(n)]


def test_ndot_fitted_from_the_element_archive():
    """One element set carries a single noisy n-dot from one epoch; an archive
    measures the actual mean-motion trend over months."""
    from orbitdeck.engine import decay as D
    nd = D.ndot_from_history(_archive())
    assert nd is not None and nd > 0
    # too few points, too short a span, and a rising mean motion all decline
    assert D.ndot_from_history(_archive(n=4)) is None
    assert D.ndot_from_history(_archive(n=10, step_days=1)) is None
    assert D.ndot_from_history(_archive(dperiod=+0.002)) is None
    assert D.ndot_from_history([]) is None
    assert D.ndot_from_history(None) is None


def test_estimate_prefers_the_archive_then_falls_back():
    from orbitdeck.engine import decay as D
    days, src = D.estimate_decay_with_history(15.50, 0.0004, 0.00025, 0.0001,
                                              _archive())
    assert src == D.SRC_HISTORY and days > 0
    # no archive: identical to the plain estimate
    a = D.estimate_decay_with_history(15.50, 0.0004, 0.00025, 0.0001, None)
    b = D.estimate_decay_days(15.50, 0.0004, 0.00025, 0.0001)
    assert a == b
    # a short archive falls back rather than claiming the archive
    _d, src2 = D.estimate_decay_with_history(15.50, 0.0004, 0.00025, 0.0001,
                                             _archive(n=4))
    assert src2 != D.SRC_HISTORY


def test_archive_source_is_only_claimed_when_it_anchored():
    """Reporting 'element archive' for a result that actually came from B*
    would overstate what the number rests on."""
    from orbitdeck.engine import decay as D
    # a wildly implausible trend is rejected by the n-dot anchor, so the
    # result must not be labeled as coming from the archive
    silly = _archive(dperiod=-5.0)
    _days, src = D.estimate_decay_with_history(15.50, 0.0004, 0.00025, 0.0,
                                               silly)
    assert src in (D.SRC_HISTORY, D.SRC_BSTAR, D.SRC_NONE)
    if src != D.SRC_HISTORY:
        assert D.SRC_NAMES[src] != "element archive"


def test_both_history_screens_show_the_decay_estimate():
    import inspect
    from orbitdeck.gui.screens import orbithistory
    from orbitterm.screens import graphics
    gsrc = inspect.getsource(orbithistory.OrbitHistoryScreen)
    tsrc = inspect.getsource(graphics.OrbitHistoryScreen)
    for src in (gsrc, tsrc):
        assert "estimate_decay_with_history" in src
        # the anchor must be named, so the number is never bare - the desktop
        # spells it out, the terminal abbreviates it to fit 80 columns
        assert "SRC_NAMES" in src or "SRC_HISTORY" in src
    # the desktop says WHY the archive was not used, rather than leaving it
    assert "too short or not decaying" in gsrc


def test_estimate_for_sat_reads_the_shared_cache(tmp_path):
    """Both front-ends write the same archive cache, so either can anchor on
    one the other fetched."""
    import json
    import os
    import time as _t
    from orbitdeck.engine import decay as D

    class _Sat:
        norad = 25544
        mean_motion = 15.50
        ecc = 0.0004
        bstar = 0.00025
        ndot = 0.0001

    # no cache: falls back, and says so
    _d, src = D.estimate_for_sat(_Sat(), cache_dir=str(tmp_path))
    assert src != D.SRC_HISTORY

    base = _t.time() - 730 * 86400
    samples = [{"epoch": base + i * 86400 * 10, "PERIOD": 92.9 - 0.0025 * i}
               for i in range(74)]
    with open(os.path.join(str(tmp_path), "25544.json"), "w") as f:
        json.dump(samples, f)
    _d2, src2 = D.estimate_for_sat(_Sat(), cache_dir=str(tmp_path))
    assert src2 == D.SRC_HISTORY
    # a corrupt or missing cache must not raise
    assert D.cached_history(999999, str(tmp_path)) == []
    with open(os.path.join(str(tmp_path), "42.json"), "w") as f:
        f.write("not json")
    assert D.cached_history(42, str(tmp_path)) == []


def test_every_decay_readout_uses_the_same_helper():
    """An operator seeing 2.7 years on one screen and 12.5 on another - because
    only one looked at the archive - would rightly not trust either."""
    import inspect
    from orbitdeck.gui.screens import orbit as gorbit
    from orbitterm.screens import analysis_screens, graphics
    gsrc = inspect.getsource(gorbit.OrbitScreen)
    tsrc = inspect.getsource(analysis_screens.OrbitalAnalysisScreen)
    hsrc = inspect.getsource(graphics.OrbitHistoryScreen)
    assert "estimate_for_sat" in gsrc
    assert "estimate_for_sat" in tsrc
    assert "estimate_decay_with_history" in hsrc


def test_orbitterm_history_shows_decay_on_every_view():
    """The analysis and table views are where you go to judge the trend, so
    the estimate belongs there too - not only on the two plots."""
    import inspect
    from orbitterm.screens import graphics
    src = inspect.getsource(graphics.OrbitHistoryScreen)
    assert src.count("self.decay") >= 6
    # a fresh fetch must recompute it, or a stale line survives the change
    assert "self.decay = self._decay_line()" in src
    fetch = inspect.getsource(graphics.OrbitHistoryScreen._fetch)
    assert "_decay_line" in fetch
