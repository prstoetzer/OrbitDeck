"""Space weather: feed parsing, interpretation, and the MUF SSN seed."""

import json

from orbitdeck.engine import spacewx_interp as SI


def test_newest_record_is_chosen_by_sorting_not_position():
    """SWPC feeds disagree on direction: f107_cm_flux.json is newest-FIRST
    while planetary_k_index_1m.json is oldest-first. Taking [-1] returned a
    flux 40 days stale (201 sfu when the day's value was 95)."""
    from orbitdeck.gui.spacewx import _newest
    newest_first = [{"time_tag": "2026-08-11T17:00:00", "flux": 95.0},
                    {"time_tag": "2026-07-01T17:00:00", "flux": 201.0}]
    oldest_first = list(reversed(newest_first))
    for feed in (newest_first, oldest_first):
        assert _newest(feed, "flux")["flux"] == 95.0
    assert _newest([], "flux") is None
    assert _newest([{"time_tag": "x", "flux": None}], "flux") is None


def test_fetch_parses_the_real_feed_shapes():
    import orbitdeck.gui.spacewx as sw
    f107 = json.dumps([
        {"time_tag": "2026-08-11T17:00:00", "flux": 95.0,
         "ninety_day_mean": None},
        {"time_tag": "2026-07-01T17:00:00", "flux": 201.0,
         "ninety_day_mean": None}])
    ssn = json.dumps([{"time-tag": "2026-06", "ssn": 70.0, "f10.7": 130.0},
                      {"time-tag": "2026-07", "ssn": 78.1, "f10.7": 136.01}])
    kp = json.dumps([{"time_tag": "2026-08-11T13:53:00", "kp_index": 2},
                     {"time_tag": "2026-08-11T19:50:00", "kp_index": 1}])

    def fake(url, timeout=20):
        if "f107" in url:
            return f107
        if "solar-cycle" in url:
            return ssn
        if "planetary" in url:
            return kp
        raise OSError("no")

    saved = sw._http_get
    sw._http_get = fake
    try:
        out = sw.fetch(timeout=1)
    finally:
        sw._http_get = saved
    assert out["flux"] == 95.0                 # newest, not the 201 tail
    assert out["ssn"] == 78.1
    assert out["flux_90d"] == 136.01
    assert out["kp"] == 1.0                    # newest by time, not position


def test_ssn_gap_marker_is_rejected():
    """-1 marks an unsmoothed gap in the SWPC indices, not a real SSN."""
    import orbitdeck.gui.spacewx as sw
    body = json.dumps([{"time-tag": "2026-07", "ssn": -1.0, "f10.7": 136.0}])

    def fake(url, timeout=20):
        if "solar-cycle" in url:
            return body
        raise OSError("no")
    saved = sw._http_get
    sw._http_get = fake
    try:
        out = sw.fetch(timeout=1)
    finally:
        sw._http_get = saved
    assert out["ssn"] is None
    assert out["flux_90d"] == 136.0            # the flux beside it is usable


def test_condition_labels_match_cardsat_thresholds():
    assert SI.flux_label(80)[0] == "low"
    assert SI.flux_label(95)[0] == "moderate"
    assert SI.flux_label(140)[0] == "good"
    assert SI.flux_label(200)[0] == "very high"
    assert SI.kp_label(2)[0] == "quiet"
    assert SI.kp_label(4.5)[0] == "unsettled"
    assert SI.kp_label(8)[0] == "major storm"
    assert SI.a_label(5)[0] == "quiet"
    assert SI.a_label(40)[0] == "storm"
    assert SI.aurora_label(2)[0] == "unlikely"
    assert SI.aurora_label(8)[0] == "likely mid lat"
    assert SI.flux_label(None)[0] is None


def test_outlook_lets_a_storm_dominate_the_flux():
    """A geomagnetic storm changes the evening whatever the sun is doing."""
    stormy = SI.outlook(f107=150, kp=6)
    assert "storm" in stormy.lower()
    assert "good HF" in SI.outlook(f107=150, kp=2)
    assert "Weak sun" in SI.outlook(f107=80, kp=2)
    assert "Settled" in SI.outlook(f107=None, kp=None)


def test_rows_show_missing_values_rather_than_dropping_them():
    rows = SI.rows({"ts": 0}, now_unix=0)
    labels = [r[0] for r in rows]
    assert "Solar flux (F10.7)" in labels and "Kp index" in labels
    vals = {r[0]: r[1] for r in rows}
    assert vals["Solar flux (F10.7)"] == "--"


def test_age_text():
    assert SI.age_text(0, 1800) == "<1h old"
    assert SI.age_text(0, 3600 * 5) == "5h old"
    assert SI.age_text(0, 3600 * 72) == "3d old"
    assert SI.age_text(None, 100) == ""


def test_ssn_from_flux_relation():
    from orbitdeck.engine.muf import ssn_from_flux
    assert ssn_from_flux(67) == 0.0
    assert ssn_from_flux(40) == 0.0            # floored, never negative
    assert 40 < ssn_from_flux(95) < 50
    assert ssn_from_flux(150) > ssn_from_flux(100)
    assert ssn_from_flux("bad") == 0.0


def test_muf_screen_seeds_ssn_from_space_weather():
    """MINIMUF is driven by SSN; making the operator look it up elsewhere
    defeats having fetched the space-weather data."""
    import inspect
    from orbitdeck.gui.screens import muf
    from orbitdeck.engine import spacewx_interp as _si
    src = inspect.getsource(muf.MufScreen)
    assert "load_spacewx_cache" in src
    assert "seed_ssn" in src
    assert "_seed_from_spacewx" in src
    # the flux fallback lives in the shared helper now, not inline
    assert "ssn_from_flux" in inspect.getsource(_si.seed_ssn)


def test_seed_ssn_prefers_observed_then_derived_then_default():
    from orbitdeck.engine.spacewx_interp import seed_ssn
    v, src = seed_ssn({"ssn": 78.1, "ssn_month": "2026-07", "flux": 95.0})
    assert v == 78.1 and "Space Wx" in src
    v, src = seed_ssn({"flux": 95.0})
    assert 40 < v < 50 and "derived" in src
    # -1 is the SWPC gap marker, not an SSN, so fall through to the flux
    v, src = seed_ssn({"ssn": -1.0, "flux": 95.0})
    assert "derived" in src
    v, src = seed_ssn({})
    assert v == 100.0 and "default" in src
    assert seed_ssn(None)[0] == 100.0


def test_both_front_ends_seed_muf_from_space_weather():
    """The desktop screen was seeded but the TUI stayed pinned at 100, so the
    two front-ends disagreed about the current SSN."""
    import inspect
    from orbitterm.screens import analysis2
    from orbitdeck.gui.screens import muf
    tui = inspect.getsource(analysis2.MufScreen)
    gui = inspect.getsource(muf.MufScreen)
    for src in (tui, gui):
        assert "seed_ssn" in src                # one shared implementation
        assert "load_spacewx_cache" in src


def test_tui_muf_seeds_and_tracks_provenance():
    import os
    import json
    import time
    os.environ["ORBITDECK_TEST"] = "1"
    from orbitdeck.gui import store as S
    os.makedirs(os.path.dirname(S.SPACEWX_CACHE), exist_ok=True)
    with open(S.SPACEWX_CACHE, "w") as f:
        json.dump({"flux": 95.0, "ssn": 78.1, "ssn_month": "2026-07",
                   "ts": time.time()}, f)
    from orbitterm.state import AppState
    from orbitterm.screens.analysis2 import MufScreen

    class _App:
        def __init__(self, st):
            self.state = st
    m = MufScreen(_App(AppState()))
    m.on_enter()
    assert m.ssn == 78.1 and "Space Wx" in m.ssn_src
    assert len(m.rows) == 24
    # a manual nudge must stop claiming the value came from the feed
    m.handle_key(ord("+"))
    assert m.ssn == 88.1 and m.ssn_src == "manual"
    # 's' reseeds
    m.handle_key(ord("s"))
    assert m.ssn == 78.1 and "Space Wx" in m.ssn_src
