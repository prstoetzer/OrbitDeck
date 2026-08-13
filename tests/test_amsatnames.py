"""Tests for AMSAT status API name matching (CardSat's matching ladder).

The API uses its own mode-tagged designators, not catalog names. Guessing them
is how the AO-7 fit ended up querying a name the API 404s on.
"""

from orbitdeck.engine import amsatnames as AN

SATS = ["ISS (ZARYA)", "AO-7 (OSCAR 7)", "SO-50 (SAUDISAT 1C)",
        "LILACSAT-2", "GREENCUBE", "LUSAT (LO-19)", "AO-91 (RADFXSAT)"]


def test_normalization_helpers():
    assert AN.norm("AO-7 (OSCAR 7)") == "AO-7 OSCAR 7"
    assert AN.collapse("AO-7") == AN.collapse("AO 7") == AN.collapse("AO7")
    assert AN.base_call("AO-07_[V/a]") == "AO-7"
    assert AN.api_base("AO-7_[V/a]") == "AO-7"
    assert AN.api_base("AO-7[V/a]") == "AO-7"
    assert AN.api_base("CAS-3H") == "CAS-3H"


def test_parenthesised_designator_match():
    """'AO-7' must reach 'AO-7 (OSCAR 7)' - the usual CelesTrak-name bridge."""
    assert AN.match_api_name("AO-7_[V/a]", SATS) == SATS.index("AO-7 (OSCAR 7)")
    assert AN.match_api_name("ISS_[FM]", SATS) == SATS.index("ISS (ZARYA)")


def test_alias_table_for_names_with_no_lexical_bridge():
    """Nothing in the strings connects these - only the alias table does."""
    assert AN.match_api_name("CAS-3H", SATS) == SATS.index("LILACSAT-2")
    assert AN.match_api_name("IO-117", SATS) == SATS.index("GREENCUBE")


def test_unmatched_name_returns_none():
    assert AN.match_api_name("NOPE-99_[X]", SATS) is None
    assert AN.match_api_name("", SATS) is None


def test_multi_mode_satellite_yields_every_name():
    """AO-7 has one API name per transponder mode; the mode calculator needs
    both, and the reporting picker needs to offer both."""
    api = ["AO-7_[V/a]", "AO-7_[U/v]", "ISS_[FM]", "ISS_[APRS]", "SO-50_[FM]"]
    m = AN.build_map(api, SATS)
    got = AN.names_for(m, SATS.index("AO-7 (OSCAR 7)"))
    assert got == ["AO-7_[U/v]", "AO-7_[V/a]"]
    assert len(AN.names_for(m, SATS.index("ISS (ZARYA)"))) == 2


def test_parse_catalog_names_tolerates_pretty_printed_json():
    """The API pretty-prints, so a naive '"name":"' byte match finds nothing -
    which is how CardSat ended up with an empty map."""
    pretty = '{\n  "data": [\n    { "name" : "AO-7_[V/a]" },\n' \
             '    { "name": "SO-50_[FM]" }\n  ]\n}'
    assert AN.parse_catalog_names(pretty) == ["AO-7_[V/a]", "SO-50_[FM]"]
    # and a truncated body still yields what it can
    assert "AO-7_[V/a]" in AN.parse_catalog_names('{"data":[{"name":"AO-7_[V/a]"')


def test_status_precedence_and_recency():
    rows = [{"report": "Not Heard", "latest_reported_time": "2026-08-11T12:00:00Z"},
            {"report": "Heard", "latest_reported_time": "2026-08-11T09:00:00Z"},
            {"report": "Heard", "latest_reported_time": "2026-08-11T11:00:00Z"}]
    best = AN.best_status(rows)
    assert best["report"] == "Heard"                    # precedence beats recency
    assert best["latest_reported_time"].endswith("11:00:00Z")   # newest Heard
    assert AN.status_priority("Heard") > AN.status_priority("Telemetry Only")
    assert AN.status_priority("Telemetry Only") > AN.status_priority("Not Heard")
    assert AN.status_priority("") == 0


def test_ao7_resolves_modes_from_the_catalog():
    from orbitdeck.engine import ao7 as A7
    assert A7.mode_of_api_name("AO-7_[V/a]") == A7.MODE_A
    assert A7.mode_of_api_name("AO-7_[U/v]") == A7.MODE_B
    assert A7.mode_of_api_name("AO-7_[??]") is None
    cat = '{"data":[{"name":"AO-7_[V/a]"},{"name":"AO-7_[U/v]"}]}'
    got = A7.resolve_api_names(lambda u: cat, ["AO-7 (OSCAR 7)"])
    assert got[A7.MODE_A] == "AO-7_[V/a]"
    assert got[A7.MODE_B] == "AO-7_[U/v]"
    # a catalog failure must degrade to the defaults, not break the fit
    fell_back = A7.resolve_api_names(
        lambda u: (_ for _ in ()).throw(OSError("offline")), ["AO-7 (OSCAR 7)"])
    assert fell_back[A7.MODE_A] == A7.API_NAMES[A7.MODE_A]


def test_reports_url_accepts_a_resolved_name():
    from orbitdeck.engine import ao7 as A7
    u = A7.reports_url(A7.MODE_A, name="AO-7_[V/a]")
    assert "%5B" in u and "%2F" in u and "[" not in u


def test_amsatstatus_resolve_uses_the_ladder():
    from orbitdeck.engine import amsatstatus as AS
    rows = [{"name": "AO-7_[U/v]"}, {"name": "AO-7_[V/a]"},
            {"name": "CAS-3H"}, {"name": "IO-117"}]
    assert AS.resolve_names(rows, "AO-7 (OSCAR 7)") == ["AO-7_[U/v]",
                                                        "AO-7_[V/a]"]
    assert AS.resolve_names(rows, "LILACSAT-2") == ["CAS-3H"]
    assert AS.resolve_names(rows, "GREENCUBE") == ["IO-117"]
    m = AS.resolve_for_catalog(rows, ["AO-7 (OSCAR 7)", "LILACSAT-2"])
    assert m["CAS-3H"] == 1
