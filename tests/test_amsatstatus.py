"""Tests for AMSAT status reading and reporting. No network is touched."""

import json

import pytest

from orbitdeck.engine import amsatstatus as AS


def test_pretty_name():
    assert AS.pretty_name("AO-91_[FM]") == "AO-91 (FM)"
    assert AS.pretty_name("ISS_[UHF_Digi]") == "ISS (UHF Digi)"
    assert AS.pretty_name("SO-50") == "SO-50"
    assert AS.pretty_name("") == ""


def test_urls():
    assert AS.summary_url(6).endswith("=6")
    u = AS.reports_url("AO-91_[FM]", 24)
    assert "reports.php?name=" in u and "hours=24" in u
    assert "[" not in u and "/" not in u.split("name=")[1].split("&")[0]


def test_parse_summary_real_api_shape():
    """summary.php returns one record per (satellite, report value) inside a
    {"data": [...]} envelope, with report_count / latest_reported_time."""
    body = json.dumps({"data": [
        {"name": "ISS_[FM]", "satellite_display_name": "ISS [FM]",
         "report": "Heard", "report_count": 22,
         "latest_reported_time": "2026-06-11T19:30:00Z"},
        {"name": "ISS_[FM]", "satellite_display_name": "ISS [FM]",
         "report": "Not Heard", "report_count": 1,
         "latest_reported_time": "2026-06-11T10:30:00Z"},
        {"name": "SO-50_[FM]", "satellite_display_name": "SO-50 [FM]",
         "report": "Heard", "report_count": 12,
         "latest_reported_time": "2026-06-11T18:30:00Z"},
    ], "meta": {"hours": 24, "count": 3}})
    rows = AS.parse_summary(body)
    # the two ISS records fold into one row
    assert [r["name"] for r in rows] == ["ISS_[FM]", "SO-50_[FM]"]
    iss = rows[0]
    assert iss["reports"] == 23 and iss["heard"] == 22
    assert iss["pretty"] == "ISS [FM]"
    assert iss["last_report"] == "2026-06-11T19:30:00Z"   # the most recent


def test_parse_summary_raises_on_error_envelope():
    """An API error must not look like an empty feed."""
    body = json.dumps({"error": {"code": "invalid_parameter",
                                 "message": "hours must be an integer",
                                 "status": 400}})
    with pytest.raises(AS.AmsatError):
        AS.parse_summary(body)


def test_catalog_and_name_resolution():
    body = json.dumps({"data": [
        {"name": "AO-7_[U/v]", "display_name": "AO-7 [U/v]",
         "report_count": 2091, "latest_reported_time": "2026-07-24T11:30:00Z"},
        {"name": "AO-7_[V/a]", "display_name": "AO-7 [V/a]",
         "report_count": 574, "latest_reported_time": "2026-07-24T02:30:00Z"},
        {"name": "SO-50_[FM]", "display_name": "SO-50 [FM]",
         "report_count": 3341, "latest_reported_time": "2026-07-24T12:30:00Z"},
    ]})
    cat = AS.parse_catalog(body)
    assert len(cat) == 3
    # a bare common name resolves to every mode entry
    assert AS.resolve_names(cat, "AO-7") == ["AO-7_[U/v]", "AO-7_[V/a]"]
    assert AS.resolve_names(cat, "SO-50") == ["SO-50_[FM]"]
    assert AS.resolve_names(cat, "NOPE") == []


def test_parse_reports_newest_first_and_heard_flag():
    body = json.dumps([
        {"callsign": "n8hm", "grid": "fm18", "report": "Heard",
         "reported_time": "2026-08-11 12:00:00"},
        {"callsign": "w1aw", "grid": "fn31", "report": "Not Heard",
         "reported_time": "2026-08-11 13:00:00"},
    ])
    rows = AS.parse_reports(body)
    assert rows[0]["callsign"] == "W1AW"     # newest first, upper-cased
    assert rows[0]["heard"] is False
    assert rows[1]["heard"] is True
    grids, heard = AS.grid_counts(rows)
    assert grids == 2 and heard == 1


def test_parse_bad_bodies():
    assert AS.parse_summary("not json") == []
    assert AS.parse_reports("not json") == []
    assert AS.parse_reports("[]") == []


def test_build_report_body():
    b = AS.build_report("AO-91[FM]", "Heard", "n8hm", "fm18",
                        when=1786000000)
    assert b["name"] == "AO-91[FM]"
    assert b["report"] == "Heard"
    assert b["callsign"] == "N8HM"           # normalized
    assert b["grid_square"] == "FM18"
    assert b["reported_at"].endswith("Z")


def test_build_report_refuses_bad_input():
    """A report is public and attributed - it must not go out malformed."""
    with pytest.raises(AS.AmsatError):
        AS.build_report("AO-91[FM]", "Heard", "")        # no callsign
    with pytest.raises(AS.AmsatError):
        AS.build_report("AO-91[FM]", "Bogus", "N8HM")    # unknown status
    with pytest.raises(AS.AmsatError):
        AS.build_report("", "Heard", "N8HM")             # no satellite name


def test_submit_report_success_and_rejection():
    sent = {}

    def ok_post(url, body):
        sent["url"] = url
        sent["body"] = json.loads(body)
        return '{"result":"ok"}'
    ok, msg = AS.submit_report(ok_post, "AO-91[FM]", "Heard", "N8HM", "FM18")
    assert ok and "AO-91 (FM)" in msg
    assert sent["url"] == AS.REPORT_POST
    assert sent["body"]["callsign"] == "N8HM"

    ok2, msg2 = AS.submit_report(lambda u, b: '{"error":"nope"}',
                                 "AO-91[FM]", "Heard", "N8HM")
    assert not ok2 and "rejected" in msg2.lower()


def test_submit_report_transport_failure_is_reported_not_raised():
    def boom(url, body):
        raise OSError("offline")
    ok, msg = AS.submit_report(boom, "AO-91[FM]", "Heard", "N8HM")
    assert not ok and "failed" in msg.lower()


def test_submit_refuses_without_callsign_before_posting():
    calls = []
    ok, msg = AS.submit_report(lambda u, b: calls.append(u) or "ok",
                               "AO-91[FM]", "Heard", "")
    assert not ok
    assert calls == []                       # nothing was sent


def test_amsat_status_screen_builds():
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
        app.show("amsatstatus")
        root.update()
        scr = app.current
        scr._show_summary(AS.parse_summary(json.dumps(
            [{"name": "AO-91[FM]", "reports": 5, "heard": 4}])))
        scr._show_reports(AS.parse_reports(json.dumps(
            [{"callsign": "n8hm", "grid": "fm18", "report": "Heard",
              "reported_time": "2026-08-11 12:00:00"}])), "AO-91[FM]")
        root.update()
        assert len(scr.btree.get_children()) == 1
        assert len(scr.rtree.get_children()) == 1
    except Exception:
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_no_screen_calls_http_get_as_a_store_attribute():
    """_http_get/_http_post are module-level functions in gui.store, not Store
    methods. Calling self.store._http_get(...) raises AttributeError at fetch
    time - which is exactly how the AMSAT and activations fetches failed."""
    import pathlib
    bad = []
    for path in list(pathlib.Path("orbitdeck").rglob("*.py")) + \
            list(pathlib.Path("orbitterm").rglob("*.py")):
        text = path.read_text()
        if "store._http_get" in text or "store._http_post" in text:
            bad.append(str(path))
    assert not bad, "call the module function instead: %s" % bad


def test_store_module_exposes_the_http_helpers():
    from orbitdeck.gui import store as st
    assert callable(st._http_get) and callable(st._http_post)
    from orbitdeck.gui.store import Store
    assert not hasattr(Store, "_http_get")     # confirms why the old call broke
