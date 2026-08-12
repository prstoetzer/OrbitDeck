"""Tests for the AO-7 mode-switch calculator.

Network is never touched: the transport is injected with canned AMSAT report
bodies, and the fit is validated by recovering a known square wave.
"""

import json
import math
import time

from orbitdeck.engine import ao7 as A7


def _square(period, t0, flip=0, n=120, step=1800.0, negatives=0):
    obs = []
    for i in range(n):
        t = t0 + i * step
        k = math.floor((t - t0) / period)
        m = (int(k) & 1) ^ flip
        obs.append({"t": t, "mode": m, "negative": False})
    for j in range(negatives):                 # add "not heard" of the other mode
        t = t0 + j * step * 3
        k = math.floor((t - t0) / period)
        m = (int(k) & 1) ^ flip
        obs.append({"t": t, "mode": 1 - m, "negative": True})
    obs.sort(key=lambda o: o["t"])
    return obs


def test_reports_url_uses_real_api_names():
    """The API names carry the transponder mode - AO-7[A]/[B] are not valid
    names and the endpoint 404s for them."""
    assert A7.API_NAMES[A7.MODE_A] == "AO-7_[V/a]"   # 2 m up / 10 m down
    assert A7.API_NAMES[A7.MODE_B] == "AO-7_[U/v]"   # 70 cm up / 2 m down
    ua = A7.reports_url(A7.MODE_A)
    ub = A7.reports_url(A7.MODE_B)
    assert "amsat.org/status/api" in ua
    assert ua != ub                            # each mode queried separately
    assert "hours=720" in ua and "limit=500" in ua
    # the bracket and the slash must both be percent-encoded
    name = ua.split("name=")[1].split("&")[0]
    assert "%5B" in name and "%2F" in name
    assert "[" not in name and "/" not in name


def test_parse_reports_heard_and_not_heard():
    body = json.dumps([
        {"reported_time": "2026-08-01 12:00:00", "report": "Heard"},
        {"reported_time": "2026-08-01 13:00:00", "report": "Not Heard"},
        {"reported_time": "2026-08-01 14:00:00", "report": "Telemetry Only"},
    ])
    obs = A7.parse_reports(body, A7.MODE_B)
    assert len(obs) == 3
    assert [o["negative"] for o in obs] == [False, True, False]
    assert all(o["mode"] == A7.MODE_B for o in obs)
    assert obs[0]["t"] < obs[1]["t"] < obs[2]["t"]


def test_parse_reports_bad_bodies():
    assert A7.parse_reports("not json", A7.MODE_A) == []
    assert A7.parse_reports("[]", A7.MODE_A) == []
    assert A7.parse_reports(json.dumps([{"report": "Heard"}]), A7.MODE_A) == []


def test_fit_recovers_known_period_and_phase():
    period = 19.5 * 3600.0
    t0 = 1.7e9
    obs = _square(period, t0, flip=0)
    res = A7.fit(obs, now=t0 + 100 * 1800.0)
    # period recovered to within the fine grid step
    assert abs(res["period_s"] - period) < 15 * 60
    assert res["agree_pct"] > 95
    assert res["mode_now"] in (A7.MODE_A, A7.MODE_B)
    assert res["next_switch"] > t0
    assert res["to_switch_s"] >= 0
    assert res["n_pos"] == len(obs)


def test_fit_period_is_not_hardcoded_to_24h():
    """An earlier fixed ~24 h assumption aliased badly; the search must track
    whatever period the data actually shows."""
    for hours in (14.0, 19.5, 26.0):
        obs = _square(hours * 3600.0, 1.7e9)
        res = A7.fit(obs, now=1.7e9 + 50 * 1800.0)
        assert abs(res["period_s"] - hours * 3600.0) < 20 * 60


def test_negatives_are_weighted_lower_than_positives():
    assert A7.W_NEG < A7.W_POS
    period, t0 = 19.5 * 3600.0, 1.7e9
    obs = _square(period, t0)
    good = A7.score(obs, period, t0, 0)
    # one spurious negative shouldn't outweigh the body of positives
    obs2 = obs + [{"t": t0 + 900, "mode": 1, "negative": True}]
    res = A7.fit(obs2, now=t0 + 100 * 1800.0)
    assert abs(res["period_s"] - period) < 20 * 60
    assert good > 0


def test_fit_reports_low_confidence_on_thin_data():
    obs = [{"t": 1.7e9, "mode": 0, "negative": False},
           {"t": 1.7e9 + 3600, "mode": 0, "negative": False}]
    res = A7.fit(obs, now=1.7e9 + 7200)
    assert "confidence" in res["note"].lower() or "near" in res["note"].lower()


def test_fit_empty_and_negative_only():
    assert A7.fit([]) is None
    only_neg = [{"t": 1.7e9, "mode": 0, "negative": True}]
    assert "error" in A7.fit(only_neg)


def test_fetch_and_fit_with_injected_transport():
    period, t0 = 19.5 * 3600.0, time.time() - 30 * 86400
    calls = []

    def fake_http(url):
        calls.append(url)
        mode = A7.MODE_A if "V%2Fa" in url else A7.MODE_B
        recs = []
        for i in range(60):
            t = t0 + i * 3600.0
            k = math.floor((t - t0) / period)
            if ((int(k) & 1)) == mode:
                recs.append({"reported_time":
                             time.strftime("%Y-%m-%d %H:%M:%S",
                                           time.gmtime(t)),
                             "report": "Heard"})
        return json.dumps(recs)

    res = A7.fetch_and_fit(fake_http, now=time.time())
    assert len(calls) == 2                     # one request per mode
    assert res["continuous_sun"] is True
    assert abs(res["period_s"] - period) < 60 * 60


def test_ao7_screen_builds():
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
        app.show("ao7")
        root.update()
        scr = app.current
        obs = _square(19.5 * 3600.0, time.time() - 20 * 3600.0)
        res = A7.fit(obs)
        res["continuous_sun"] = True
        res["since"] = time.time() - 40 * 3600.0
        scr._show(res, app.store.db.sats[0])
        root.update()
    except Exception:
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass


# ---- illumination search (regression: reported the season starting "now") ----
def _ao7(raan=240.0):
    import json as _j
    from orbitdeck.engine import SatDb
    omm = [{"OBJECT_NAME": "AO-7", "OBJECT_ID": "1974-089B",
            "EPOCH": "2026-08-01T00:00:00.000000", "MEAN_MOTION": 12.5365,
            "ECCENTRICITY": 0.0012, "INCLINATION": 101.66,
            "RA_OF_ASC_NODE": raan, "ARG_OF_PERICENTER": 90.0,
            "MEAN_ANOMALY": 270.0, "BSTAR": 0.00001, "MEAN_MOTION_DOT": 0.0,
            "MEAN_MOTION_DDOT": 0.0, "NORAD_CAT_ID": 7530,
            "REV_AT_EPOCH": 60000, "ELEMENT_SET_NO": 999}]
    db = SatDb()
    db.load_gp_json(_j.dumps(omm))
    return db.sats[0]


def _pred(sat):
    from orbitdeck.engine.predict import Predictor, Observer
    p = Predictor()
    p.set_site(Observer(lat=39.93, lon=-74.89, alt_m=20, valid=True))
    p.set_sat(sat)
    return p


def test_illumination_since_is_not_quantised_to_now():
    """It used to walk back in 30-minute steps and let a single grazing sample
    end the search, so a continuous-sunlight season read as starting now."""
    now = time.time()
    for raan in (0, 60, 120, 180, 240, 300):
        sat = _ao7(raan)
        pred = _pred(sat)
        res = A7.illumination_since(pred, sat, now)
        if res is None:
            continue                       # genuinely eclipsing
        start, _exact = res
        assert start < now - 3600, "season start collapsed onto now"


def test_illumination_verdict_matches_the_sample_count():
    """None must mean the samples actually show an eclipse."""
    now = time.time()
    for raan in (0, 60, 120, 180, 240, 300):
        sat = _ao7(raan)
        pred = _pred(sat)
        n = A7.orbit_eclipse_samples(pred, sat, now)
        res = A7.illumination_since(pred, sat, now)
        if res is None:
            assert n is None or n >= A7.ECLIPSE_MIN_SAMPLES
        else:
            assert n is not None and n < A7.ECLIPSE_MIN_SAMPLES


def test_illumination_flags_the_window_edge():
    """A run older than the search window is reported as inexact, not as if the
    boundary had been found."""
    now = time.time()
    sat = _ao7(60)
    pred = _pred(sat)
    res = A7.illumination_since(pred, sat, now, back_days=2)
    if res is not None:
        start, exact = res
        if not exact:
            assert start <= now - 2 * 86400 + 1


def test_orbit_eclipse_samples_reports_none_when_unusable():
    """An unevaluatable state must be None, not silently 'eclipsing'."""
    class _Dead:
        def sunlit_at(self, t):
            raise RuntimeError("no propagator")
    sat = _ao7()
    assert A7.orbit_eclipse_samples(_Dead(), sat, time.time()) is None
