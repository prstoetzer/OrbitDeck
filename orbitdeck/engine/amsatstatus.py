"""orbitdeck.engine.amsatstatus - read and submit AMSAT satellite status reports.

The AMSAT status pages are the community's live "is this bird working" board:
operators post Heard / Not Heard / Telemetry Only / Crew Active against a
satellite, and everyone else reads the last day's worth before a pass.

This module covers both directions:

  * ``parse_summary`` / ``parse_reports`` - read the public status API;
  * ``build_report`` / ``submit_report`` - post your own observation.

Ported from CardSat 0.9.75. Submitting is a **public, attributed** action: the
report carries your callsign and grid and appears on amsat.org, so the caller is
expected to confirm intent and to have set a callsign first - ``build_report``
refuses without one rather than posting anonymously or with a placeholder.

AMSAT tracks reports per satellite *mode name* (e.g. "AO-91[FM]"), not per NORAD
id, so the caller supplies the API name; ``pretty_name`` renders those for
display.
"""

import json
import re
import time
from urllib.parse import quote

BASE = "https://www.amsat.org/status/api/v1"
SUMMARY_URL = BASE + "/summary.php?hours="
REPORTS_URL = BASE + "/reports.php?name="
CATALOG_URL = BASE + "/catalog.php"
REPORT_POST = BASE + "/reports.php"

STATUSES = ["Heard", "Telemetry Only", "Not Heard", "Crew Active"]
DEFAULT_WINDOW_H = 24


class AmsatError(Exception):
    """Bad input or a rejected submission."""


def pretty_name(api_name):
    """Render an AMSAT API name for display: 'AO-91[FM]' -> 'AO-91 (FM)'."""
    if not api_name:
        return ""
    m = re.match(r"^(.+?)_?\[([^\]]*)\]$", api_name.strip())
    if not m:
        return api_name.strip()
    base, mode = m.group(1).strip(), m.group(2).strip()
    mode = mode.replace("_", " ")
    return "%s (%s)" % (base, mode) if mode else base


def summary_url(hours=DEFAULT_WINDOW_H):
    return "%s%d" % (SUMMARY_URL, int(hours))


def reports_url(api_name, hours=DEFAULT_WINDOW_H, limit=200):
    return "%s%s&hours=%d&limit=%d" % (REPORTS_URL, quote(api_name, safe=''),
                                       int(hours), int(limit))


class AmsatApiError(AmsatError):
    """The API returned its error envelope."""


def _as_list(data, *keys):
    """Unwrap the API's response envelope, raising on its error envelope.

    v1 endpoints return {"data": [...], "meta": {...}}; errors return
    {"error": {"code", "message", "status"}}. The legacy endpoints return a
    bare array. Silently treating an error envelope as "no data" is what made a
    broken endpoint look like an empty feed, so it raises instead."""
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            raise AmsatApiError(err.get("message") or err.get("code")
                                or "API error")
        for k in keys:
            if isinstance(data.get(k), list):
                return data[k]
        return []
    return data if isinstance(data, list) else []


def parse_summary(text):
    """Parse /summary.php into one row per satellite.

    The endpoint returns one record per (satellite, report value) - so a bird
    with Heard and Not Heard rows appears twice - with fields ``report_count``,
    ``report``, ``latest_reported_time`` and ``display_name``. This folds those
    into a single row per satellite carrying the total, the Heard count and the
    most recent report time.
    """
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    rows = {}
    for rec in _as_list(data, "data", "summary", "satellites"):
        if not isinstance(rec, dict):
            continue
        name = str(rec.get("name") or rec.get("satellite") or "").strip()
        if not name:
            continue
        count = _int(rec.get("report_count") or rec.get("reports")
                     or rec.get("count"))
        status = str(rec.get("report") or rec.get("status") or "").strip()
        last = (rec.get("latest_reported_time") or rec.get("last_report")
                or rec.get("reported_time") or "")
        row = rows.setdefault(name, {
            "name": name,
            "pretty": (rec.get("satellite_display_name")
                       or rec.get("display_name") or pretty_name(name)),
            "reports": 0, "heard": 0, "last_report": "",
        })
        row["reports"] += count
        if status.lower().startswith("heard"):
            row["heard"] += count
        if str(last) > str(row["last_report"]):
            row["last_report"] = last
    out = list(rows.values())
    out.sort(key=lambda r: -r["reports"])
    return out


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def parse_reports(text):
    """Parse the per-satellite reports endpoint.

    Returns a list of {callsign, grid, status, time, heard} newest first.
    """
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    out = []
    for rec in _as_list(data, "data", "reports"):
        if not isinstance(rec, dict):
            continue
        status = str(rec.get("report") or rec.get("status") or "").strip()
        if not status:
            continue
        stamp = (rec.get("reported_time") or rec.get("reported_at")
                 or rec.get("time") or "")
        out.append({
            "callsign": str(rec.get("callsign") or rec.get("call")
                            or "").upper().strip(),
            "grid": str(rec.get("grid_square") or rec.get("grid")
                        or "").upper().strip(),
            "status": status,
            "time": stamp,
            "unix": parse_time(stamp),
            "heard": not status.lower().startswith("not"),
        })
    out.sort(key=lambda r: r["unix"] or 0, reverse=True)
    return out


def parse_time(stamp):
    if not stamp:
        return None
    s = str(stamp).strip().replace("T", " ").replace("Z", "").strip()
    if "." in s:
        s = s.split(".")[0]
    import calendar
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return float(calendar.timegm(time.strptime(s, fmt)))
        except ValueError:
            continue
    return None


def grid_counts(reports):
    """How many distinct grids reported, and how many reports were 'heard'."""
    grids = {r["grid"] for r in reports if r["grid"]}
    heard = sum(1 for r in reports if r["heard"])
    return len(grids), heard


def build_report(api_name, status, callsign, grid=None, when=None):
    """Build the JSON body for a status submission.

    Refuses without a callsign or with an unknown status - a report is public
    and attributed, so it should not go out anonymous or malformed.
    """
    if not api_name:
        raise AmsatError("No AMSAT catalog name for this satellite")
    if status not in STATUSES:
        raise AmsatError("Unknown status %r" % status)
    call = (callsign or "").strip().upper()
    if not call:
        raise AmsatError("Set your callsign first")
    tm = time.gmtime(when if when is not None else time.time())
    body = {
        "name": api_name,
        "report": status,
        "callsign": call,
        "reported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", tm),
    }
    if grid:
        body["grid_square"] = str(grid).strip().upper()
    return body


def submit_report(http_post, api_name, status, callsign, grid=None,
                  when=None):
    """Post a status report. ``http_post`` is callable(url, json_body) -> text.

    Returns (ok, message). Never raises for a transport failure - the caller
    shows the message.
    """
    try:
        body = build_report(api_name, status, callsign, grid, when)
    except AmsatError as exc:
        return False, str(exc)
    try:
        resp = http_post(REPORT_POST, json.dumps(body))
    except Exception as exc:
        return False, "Report failed: %s" % str(exc)[:60]
    low = (resp or "").lower()
    if "error" in low or "fail" in low or "invalid" in low:
        return False, "Report rejected: %s" % (resp or "")[:60]
    return True, "%s reported: %s" % (status, pretty_name(api_name))


CATALOG_URL_STATS = CATALOG_URL + "?include_stats=true"


def parse_catalog(text):
    """Parse /catalog.php into [{name, pretty, reports, last_report}].

    The canonical API name carries the mode, e.g. ``AO-91_[FM]`` - a bare
    ``AO-91`` is not a valid name and the API answers 404. Callers that only
    know a satellite's common name should resolve it through here.
    """
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    out = []
    for rec in _as_list(data, "data", "catalog", "satellites"):
        if not isinstance(rec, dict):
            continue
        name = str(rec.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "name": name,
            "pretty": rec.get("display_name") or pretty_name(name),
            "reports": _int(rec.get("report_count")),
            "last_report": rec.get("latest_reported_time") or "",
        })
    out.sort(key=lambda r: r["name"])
    return out


def resolve_names(catalog_rows, common_name):
    """Every canonical API name matching a catalog satellite name.

    Delegates to :mod:`orbitdeck.engine.amsatnames`, which implements CardSat's
    matching ladder - parenthesised designator, whole name, delimited token,
    legacy stem, collapsed form, then a small alias table. A plain stem compare
    only worked for names that already looked alike, and missed the cases that
    matter: ``CAS-3H`` is ``LILACSAT-2`` and ``IO-117`` is ``GREENCUBE``, with
    nothing in the strings to connect them.

    ``AO-7`` resolves to both ``AO-7_[U/v]`` and ``AO-7_[V/a]``.
    """
    from . import amsatnames as _an
    names = [r["name"] if isinstance(r, dict) else str(r) for r in catalog_rows]
    mapping = _an.build_map(names, [common_name])
    return _an.names_for(mapping, 0)


def resolve_for_catalog(catalog_rows, sat_names):
    """Map every API name onto an index in ``sat_names`` (or drop it)."""
    from . import amsatnames as _an
    names = [r["name"] if isinstance(r, dict) else str(r) for r in catalog_rows]
    return _an.build_map(names, sat_names)
