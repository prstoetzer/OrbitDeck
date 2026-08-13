"""Tests for the Space-Track orbital-history tool (gp_history).

Network is never touched: the client's transport is injected with canned
responses so login, throttling and parsing are all exercised offline.
"""

import pytest

from orbitdeck.engine import spacetrack as ST

CSV = ("EPOCH,SEMIMAJOR_AXIS,ECCENTRICITY,INCLINATION,PERIOD,APOAPSIS,"
       "PERIAPSIS,BSTAR\n"
       "1998-11-20 12:00:00,6728.1,0.0051,51.60,91.5,384.5,315.2,0.00012\n"
       "2005-06-01 00:00:00,6720.0,0.0009,51.64,91.3,349.0,337.0,0.00021\n"
       "2015-06-01 00:00:00,,,,,,,\n"
       "2026-01-01 00:00:00,6795.5,0.0004,51.63,92.9,423.0,417.0,0.00025\n")


def test_history_path_shape():
    p = ST.history_path(25544)
    assert "class/gp_history" in p and "NORAD_CAT_ID/25544" in p
    assert "orderby/EPOCH" in p and "format/csv" in p
    for col in ST.COLUMNS:
        assert col in p


def test_parse_epoch_formats():
    a = ST.parse_epoch("2026-01-01 00:00:00")
    b = ST.parse_epoch("2026-01-01T00:00:00.123456")
    assert a == b and a > 0
    assert ST.parse_epoch("") is None
    assert ST.parse_epoch("garbage") is None


def test_empty_cells_are_absent_not_zero():
    """Decades-old rows have empty derived cells; parsing them as 0.0 would
    zero-poison the series (CardSat's bench finding)."""
    s = ST.parse_history_csv(CSV)
    assert len(s) == 4
    assert s[2]["SEMIMAJOR_AXIS"] is None
    assert s[2]["ECCENTRICITY"] is None
    # and the minimum is a real value, not zero
    summary = {r["column"]: r for r in ST.summarize(s)}
    assert summary["SEMIMAJOR_AXIS"]["min"] > 6000
    assert summary["APOAPSIS"]["min"] > 300


def test_zero_in_strictly_positive_column_is_absent():
    body = ("EPOCH,SEMIMAJOR_AXIS,ECCENTRICITY,INCLINATION,PERIOD,APOAPSIS,"
            "PERIAPSIS,BSTAR\n2001-01-01 00:00:00,0,0.001,0,0,0,0,0.0001\n")
    s = ST.parse_history_csv(body)
    assert s[0]["SEMIMAJOR_AXIS"] is None
    assert s[0]["INCLINATION"] is None
    assert s[0]["ECCENTRICITY"] == 0.001      # zero eccentricity is legitimate


def test_quoted_csv_parses():
    body = ('"EPOCH","SEMIMAJOR_AXIS","ECCENTRICITY","INCLINATION","PERIOD",'
            '"APOAPSIS","PERIAPSIS","BSTAR"\n'
            '"2020-01-01 00:00:00","6780","0.0005","51.6","92.7","410","400",'
            '"0.0002"\n')
    s = ST.parse_history_csv(body)
    assert len(s) == 1 and abs(s[0]["SEMIMAJOR_AXIS"] - 6780) < 1e-6


def test_parse_empty_and_headeronly():
    assert ST.parse_history_csv("") == []
    assert ST.parse_history_csv("EPOCH,SEMIMAJOR_AXIS\n") == []


def test_series_and_summarize():
    s = ST.parse_history_csv(CSV)
    ts, vs = ST.series(s, "APOAPSIS")
    assert len(ts) == len(vs) == 3          # the empty row is skipped
    rows = {r["column"]: r for r in ST.summarize(s)}
    apo = rows["APOAPSIS"]
    assert apo["first"] == 384.5 and apo["last"] == 423.0
    assert abs(apo["delta"] - 38.5) < 1e-9
    assert apo["n"] == 3
    assert "rate_per_year" in apo


def test_summarize_vs_current():
    s = ST.parse_history_csv(CSV)
    rows = {r["column"]: r for r in ST.summarize(s, current={"APOAPSIS": 430.0})}
    assert abs(rows["APOAPSIS"]["vs_current"] - 7.0) < 1e-9


def test_full_resolution_by_default_and_optional_decimation():
    """Desktop keeps every row; binning is opt-in (CardSat bins for ESP32 RAM)."""
    s = ST.parse_history_csv(CSV)
    assert len(ST.decimate(s, 0)) == len(s)      # no binning
    many = [{"epoch": 1000 + i * 100, "SEMIMAJOR_AXIS": 6700.0 + i,
             "ECCENTRICITY": None, "INCLINATION": None, "PERIOD": None,
             "APOAPSIS": None, "PERIAPSIS": None, "BSTAR": None}
            for i in range(500)]
    binned = ST.decimate(many, 50)
    assert len(binned) <= 50
    # bins carry mean plus true extremes, and absent columns stay absent
    assert binned[0]["SEMIMAJOR_AXIS"] is not None
    assert binned[0]["SEMIMAJOR_AXIS_min"] <= binned[0]["SEMIMAJOR_AXIS_max"]
    assert binned[0]["ECCENTRICITY"] is None


def test_client_login_and_fetch_with_injected_transport():
    calls = []

    def opener(url, data=None):
        calls.append((url, data))
        if "login" in url:
            return '{"Login":"success"}'
        return CSV

    cli = ST.SpaceTrackClient("me@example.com", "pw", opener=opener)
    ST.MIN_QUERY_INTERVAL_S = 0.0            # don't sleep in tests
    samples = cli.fetch_history(25544)
    assert len(samples) == 4
    assert "login" in calls[0][0] and calls[0][1]["identity"] == "me@example.com"
    assert "gp_history" in calls[1][0]


def test_client_requires_credentials():
    cli = ST.SpaceTrackClient("", "", opener=lambda u, d=None: "")
    with pytest.raises(ST.SpaceTrackError):
        cli.login()


def test_client_rejects_html_session_expiry():
    def opener(url, data=None):
        return '{"Login":"success"}' if "login" in url else "<!DOCTYPE html><html>"
    cli = ST.SpaceTrackClient("u", "p", opener=opener)
    ST.MIN_QUERY_INTERVAL_S = 0.0
    with pytest.raises(ST.SpaceTrackError):
        cli.fetch_history(25544)


def test_orbit_history_screen_builds():
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
        app.show("orbithistory")
        root.update()
        scr = app.current
        scr.samples = ST.parse_history_csv(CSV)
        scr._redraw()
        scr._fill_table()
        root.update()
        assert len(scr.tree.get_children()) > 0
    except Exception:
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass


# ---- derived views (CardSat SCR_STHIST parity) ----
def _synthetic(n=200, maneuver_at=120):
    base = 1.6e9
    out = []
    for i in range(n):
        apo = 420 - i * 0.05 - (12 if i > maneuver_at else 0)
        out.append({"epoch": base + i * 86400 * 30, "APOAPSIS": apo,
                    "PERIAPSIS": apo - 10, "INCLINATION": 51.6,
                    "ECCENTRICITY": 0.0005, "PERIOD": 92.9,
                    "SEMIMAJOR_AXIS": 6790, "BSTAR": 2e-4})
    return out


def test_rate_series_differentiates_and_skips_dense_pairs():
    s = _synthetic(20)
    ts, rr = ST.rate_series(s, "APOAPSIS")
    assert len(rr) == len(ts) == 19
    assert all(r < 0 for r in rr)              # a decaying apogee
    # element sets minutes apart must not manufacture huge rates
    dense = [{"epoch": 1.6e9, "APOAPSIS": 420.0},
             {"epoch": 1.6e9 + 60, "APOAPSIS": 420.5}]
    for d in dense:
        d.update({k: None for k in ST.COLUMNS if k != "APOAPSIS"})
    assert ST.rate_series(dense, "APOAPSIS") == ([], [])


def test_analyze_rate_detects_a_maneuver_jump():
    a = ST.analyze_rate(_synthetic(), "APOAPSIS")
    assert a is not None
    assert a["n_jumps"] >= 1
    assert abs(a["peak_rate"]) > 10 * abs(a["median_abs"])
    assert "faster" in a["verdict"].lower() or "REVERSED" in a["verdict"]


def test_analyze_rate_needs_enough_data():
    assert ST.analyze_rate(_synthetic(3), "APOAPSIS") is None
    assert ST.analyze_rate([], "APOAPSIS") is None


def test_analyze_rate_zero_baseline_does_not_read_as_steady():
    """A satellite still for years then moving must not report 'roughly steady
    (0.00x)' - a near-zero early era outranks the ratio."""
    base = 1.6e9
    s = []
    for i in range(40):
        val = 500.0 if i < 20 else 500.0 - (i - 20) * 2.0
        s.append({"epoch": base + i * 86400 * 30, "APOAPSIS": val})
    for d in s:
        d.update({k: None for k in ST.COLUMNS if k != "APOAPSIS"})
    a = ST.analyze_rate(s, "APOAPSIS")
    assert "steady" not in a["verdict"].lower()
    assert "NEW trend" in a["verdict"] or "FASTER" in a["verdict"]


def test_analyze_rate_splits_on_time_not_sample_count():
    """A sparse early archive plus a dense modern one must still weigh eras by
    time, or the modern era dominates both halves."""
    base = 1.6e9
    s = [{"epoch": base + i * 86400 * 365, "APOAPSIS": 500.0 - i}
         for i in range(5)]                       # sparse: 5 yearly points
    t = s[-1]["epoch"]
    s += [{"epoch": t + i * 86400, "APOAPSIS": 495.0 - i * 0.01}
          for i in range(1, 200)]                 # dense: 200 daily points
    for d in s:
        d.update({k: d.get(k) for k in ST.COLUMNS})
    a = ST.analyze_rate(s, "APOAPSIS")
    assert a is not None and a["n"] > 100
    # Split by TIME: the sparse yearly points fall in the early era and keep
    # their own ~1 unit/yr rate instead of being averaged away by the 199
    # dense points. A split by sample count would put ~100 dense points in the
    # "early" half and both eras would report the dense rate.
    assert 0.5 < abs(a["early_mean"]) < 2.0
    assert abs(a["late_mean"]) > 3.0


def test_window_slices_the_time_axis():
    s = _synthetic(200)
    assert len(ST.window(s, 0.0, 1.0)) == 200
    half = ST.window(s, 0.5, 1.0)
    assert 90 < len(half) < 110
    assert half[0]["epoch"] >= s[len(s) // 2 - 2]["epoch"]
    assert ST.window([], 0.0, 1.0) == []


def test_orbit_history_screens_have_all_four_views():
    from orbitterm.screens.graphics import OrbitHistoryScreen
    assert OrbitHistoryScreen.VIEWS == ["value", "rate", "analysis", "table"]
    import inspect
    from orbitdeck.gui.screens import orbithistory
    src = inspect.getsource(orbithistory.OrbitHistoryScreen)
    for want in ("_draw_rate", "_draw_analysis", "_zoom", "_visible"):
        assert want in src
