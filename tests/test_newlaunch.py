"""New-launch transmitter discovery."""

import json

from orbitdeck.engine import newlaunch as NL

# The design document's fixture set. The filter is tested in BOTH directions:
# cutting junk is the easy half, not eating real targets is the half that
# matters.
MUST_CUT = [
    "STARLINK-31234", "ONEWEB-0712", "KUIPER-0034", "QIANFAN-18",
    "FLOCK 4V-12", "LEMUR-2-ZOEY", "ICEYE-X31", "BEIDOU-3 M26",
    "NAVSTAR 82 (USA 343)", "CZ-6A R/B", "FREGAT DEB", "SPACEBEE-190",
    "IRIDIUM 172", "GLOBALSTAR M097", "SENTINEL-6B",
]
MUST_KEEP = [
    "LEDSAT", "HADES-D", "TEVEL-2", "SO-50", "AO-7", "ISS (ZARYA)",
    "CAS-5A", "BEESAT-9", "GENESIS-L", "TBA - TO BE ASSIGNED", "UVSQ-SAT",
    "INSPIRE-SAT 7", "MESHTASTIC-1", "STELLA", "ES'HAIL 2", "QO-100",
]


def test_filter_cuts_the_noise():
    missed = [n for n in MUST_CUT if not NL.is_noise(n)]
    assert not missed, missed


def test_filter_keeps_every_real_target():
    """The half that matters: a filter that eats an amateur payload has
    defeated the feature it serves."""
    eaten = [n for n in MUST_KEEP if NL.is_noise(n)]
    assert not eaten, eaten


def test_tba_objects_are_never_filtered():
    """That is exactly the state a freshly launched cubesat occupies for its
    first weeks."""
    for name in ("TBA - TO BE ASSIGNED", "TBA", "OBJECT A TBA"):
        assert not NL.is_noise(name)


def test_structural_rules_catch_numbered_and_suffixed_forms():
    for name in ("FALCON 9 R/B", "ARIANE 5 R/B(1)", "COSMOS 2251 DEB",
                 "CZ-6A DEB", "SOMETHING DEBRIS"):
        assert NL.is_noise(name), name


def _gp(*rows):
    return json.dumps([{"NORAD_CAT_ID": n, "OBJECT_NAME": nm}
                       for n, nm in rows])


def test_parse_keeps_the_element_set_for_reuse():
    """The GP entry is the element source for an add, so fetching it twice
    would be waste."""
    entries = NL.parse_gp(_gp((70002, "LEDSAT")))
    assert entries[0]["norad"] == 70002
    assert entries[0]["omm"]["OBJECT_NAME"] == "LEDSAT"
    assert NL.parse_gp("not json") == []
    assert NL.parse_gp(json.dumps([{"OBJECT_NAME": "no norad"}])) == []


def test_filter_runs_before_the_newest_are_taken():
    """Filtering afterwards lets one constellation batch consume the whole
    budget and bury everything else."""
    rows = [(80000 + i, "STARLINK-%d" % i) for i in range(50)]
    rows.append((70002, "LEDSAT"))
    entries = NL.parse_gp(_gp(*rows))
    picked = NL.select_candidates(entries, filter_noise=True, limit=5)
    assert [p["name"] for p in picked] == ["LEDSAT"]
    # newest first, by catalog number
    mixed = NL.parse_gp(_gp((100, "OLD-SAT"), (900, "NEW-SAT")))
    assert [p["norad"] for p in NL.select_candidates(mixed)] == [900, 100]


def test_discover_reports_provenance_and_marks_known_objects():
    entries = NL.parse_gp(_gp((70001, "STARLINK-31234"), (70002, "LEDSAT"),
                              (70003, "CZ-6A R/B"), (70005, "HADES-D")))
    tx = {"70002": [{"uuid": "a", "downlink_low": 435500000, "mode": "FM"},
                    {"uuid": "b", "mode": "CW"}],
          "70005": [{"uuid": "c", "downlink_low": 436666000, "mode": "FSK"}],
          "70001": [{"uuid": "z", "downlink_low": 11e9, "mode": "Ku"}]}
    hits, stats = NL.discover(entries, tx, known_norads=[70005])
    names = [h["name"] for h in hits]
    assert "LEDSAT" in names and "HADES-D" in names
    assert "STARLINK-31234" not in names       # filtered despite having tx
    assert stats == {"total": 4, "probed": 2, "cut": 2, "hits": 2,
                     "filtered": True}
    assert NL.provenance(stats) == "2 hit / 2 probed, 2 cut"
    ledsat = [h for h in hits if h["name"] == "LEDSAT"][0]
    assert ledsat["tx_count"] == 2 and ledsat["downlink_hz"] == 435500000
    assert ledsat["mode"] == "FM" and not ledsat["in_catalog"]
    assert [h for h in hits if h["name"] == "HADES-D"][0]["in_catalog"]


def test_filter_off_returns_strictly_more():
    entries = NL.parse_gp(_gp((70001, "STARLINK-1"), (70002, "LEDSAT")))
    _h1, s1 = NL.discover(entries, {}, filter_noise=True)
    _h2, s2 = NL.discover(entries, {}, filter_noise=False)
    assert s2["probed"] > s1["probed"]
    assert "filter off" in NL.provenance(s2)


def test_a_negative_is_never_stated_as_no_transmitter():
    """SatNOGS coverage lags a launch by days to weeks."""
    entries = NL.parse_gp(_gp((70002, "LEDSAT")))
    _hits, stats = NL.discover(entries, {})
    msg = NL.empty_message(stats)
    assert "not yet listed by SatNOGS" in msg and "lags" in msg
    # "No transmitters FOUND AMONG those checked" is fine; a claim about a
    # specific object having none is not. Check the claim, not the substring -
    # "no transmitters found" legitimately contains "no transmitter".
    for overclaim in ("has no transmitter", "is silent",
                      "does not transmit", "no transmitters."):
        assert overclaim not in msg.lower()
    assert "not proof" in msg
    # everything filtered out reads differently again
    allcut = NL.parse_gp(_gp((70001, "STARLINK-1")))
    _h, s = NL.discover(allcut, {})
    assert "filtered out" in NL.empty_message(s)


def test_summarize_handles_missing_fields():
    assert NL.summarize_tx([]) == {"count": 0, "downlink_hz": None,
                                   "mode": None}
    recs = [{"uuid": "a"}, {"uuid": "b", "mode": "FM"},
            {"uuid": "c", "downlink_low": 145800000}]
    got = NL.summarize_tx(recs)
    assert got["count"] == 3 and got["mode"] == "FM"
    assert got["downlink_hz"] == 145800000
    assert NL.fmt_downlink(None) == "\u2014"
    assert NL.fmt_downlink(435500000) == "435.5000 MHz"


def test_the_store_can_cache_transmitters_already_in_hand(tmp_path,
                                                          monkeypatch):
    """The probe response IS the transponder record, so adding a satellite
    should need no further network.

    Redirected to a temp file: writing the real cache from a test overwrites
    whatever the user has, and it silently broke an unrelated transponder test
    when I first ran it by hand.
    """
    import os
    os.environ["ORBITDECK_TEST"] = "1"
    import orbitdeck.gui.store as store_mod
    monkeypatch.setattr(store_mod, "TX_CACHE",
                        str(tmp_path / "transmitters.json"))
    st = store_mod.Store()
    recs = [{"uuid": "x", "downlink_low": 435500000, "mode": "FM"}]
    assert st.cache_transmitters(70002, recs)
    assert st.load_tx_cache().get("70002") == recs
    assert not st.cache_transmitters(70002, [])


def test_the_feature_is_on_both_front_ends():
    from orbitdeck.gui.app import NAV_ITEMS
    import orbitterm.app as A
    assert "newlaunch" in [k for _l, k in NAV_ITEMS]
    assert "newlaunch" in [n[0] for n in A.NAV]
    import inspect
    from orbitdeck.gui.screens import newlaunch as scr
    src = inspect.getsource(scr.NewLaunchScreen)
    # the scan must be user-initiated, not automatic on entry
    assert "def on_show" not in src
    assert "add_extra_sat" in src           # adds stay auto-updating
    assert "cache_transmitters" in src
