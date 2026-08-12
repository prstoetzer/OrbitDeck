"""orbitdeck.gui.datafeeds - online lookups: QRZ callsign, hams.at activations.

Two network-backed data sources ported from CardSat, kept as pure parse helpers
plus thin fetch wrappers so the parsing is unit-testable offline:

  * QRZ.com XML API - resolve a callsign to name / location / grid / class.
    Requires the user's QRZ XML-subscription credentials (stored in prefs); the
    API is a session-key login followed by a callsign query.
  * hams.at upcoming-activations Atom feed - scheduled satellite roves and grid
    activations. Public, no credentials.

Network fetches go through the store's http helper. Nothing here raises on a
bad/empty body; parse helpers return empty results so the UI can show a clean
"nothing found" instead of a traceback.
"""

import re
from urllib.parse import quote

QRZ_BASE = "https://xmldata.qrz.com/xml/current/"
HAMSAT_FEED_URL = "https://hams.at/feeds/upcoming_alerts"


# ---------------------------------------------------------------------------
# QRZ XML API
# ---------------------------------------------------------------------------
def qrz_login_url(user, password):
    return "%s?username=%s;password=%s;agent=OrbitDeck" % (
        QRZ_BASE, quote(user or ""), quote(password or ""))


def qrz_query_url(session_key, callsign):
    return "%s?s=%s;callsign=%s" % (QRZ_BASE, quote(session_key or ""),
                                    quote(callsign or ""))


def _xml_tag(body, tag):
    """Inner text of the first <tag>...</tag> (namespace-agnostic), or ''."""
    m = re.search(r"<%s>(.*?)</%s>" % (re.escape(tag), re.escape(tag)),
                  body or "", re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def qrz_parse_session_key(body):
    """Return (key, error). key is '' when login failed."""
    return _xml_tag(body, "Key"), _xml_tag(body, "Error")


def qrz_parse_callsign(body):
    """Parse a QRZ callsign response into a dict, or None if no Callsign node."""
    if "<Callsign>" not in (body or ""):
        return None
    fn = _xml_tag(body, "fname")
    ln = _xml_tag(body, "name")
    name = (fn + " " + ln).strip() or _xml_tag(body, "name_fmt")
    state = _xml_tag(body, "state")
    zipc = _xml_tag(body, "zip")
    addr = _xml_tag(body, "addr1")
    line2 = _xml_tag(body, "addr2")
    if state:
        line2 += (", " if line2 else "") + state
    if zipc:
        line2 += " " + zipc
    if line2:
        addr = (addr + "\n" + line2) if addr else line2
    call = (_xml_tag(body, "call") or "").upper()
    return {
        "call": call,
        "name": name,
        "addr": addr,
        "country": _xml_tag(body, "country"),
        "grid": _xml_tag(body, "grid"),
        "class": _xml_tag(body, "class"),
    }


def qrz_lookup(http_get, user, password, callsign, session_key=None):
    """Full QRZ lookup: (result_dict, session_key, error).

    ``http_get`` is a callable(url, timeout) -> text (the store's helper). A
    cached ``session_key`` is reused; on an expired key one re-login is tried.
    """
    key = session_key or ""
    if not key:
        body = http_get(qrz_login_url(user, password), timeout=15)
        key, err = qrz_parse_session_key(body)
        if not key:
            return None, "", (err or "QRZ login failed")
    body = http_get(qrz_query_url(key, callsign), timeout=15)
    res = qrz_parse_callsign(body)
    if res is None:
        err = _xml_tag(body, "Error")
        if any(w in err for w in ("Session", "Timeout", "invalid")):
            body = http_get(qrz_login_url(user, password), timeout=15)
            key, _e = qrz_parse_session_key(body)
            if key:
                body = http_get(qrz_query_url(key, callsign), timeout=15)
                res = qrz_parse_callsign(body)
        if res is None:
            return None, key, (err or "Not found")
    return res, key, ""


# ---------------------------------------------------------------------------
# hams.at upcoming-activations Atom feed
# ---------------------------------------------------------------------------
def _entry_tag(block, tag):
    m = re.search(r"<%s[^>]*>(.*?)</%s>" % (re.escape(tag), re.escape(tag)),
                  block, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    txt = m.group(1)
    # strip a CDATA wrapper if present
    cd = re.search(r"<!\[CDATA\[(.*?)\]\]>", txt, re.DOTALL)
    if cd:
        txt = cd.group(1)
    return txt.strip()


def _li_value(content, label):
    """Pull '<li>Label: value</li>' from an activation's HTML content block."""
    m = re.search(r"<li>\s*%s\s*:\s*(.*?)</li>" % re.escape(label), content,
                  re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    return re.sub(r"<[^>]+>", "", m.group(1)).strip()


def strip_utc(text):
    """Drop a trailing 'UTC' from a feed value.

    Every time OrbitDeck displays is UTC and the column headers say so, which
    makes a per-row suffix pure noise. Kept as a helper so the raw feed value
    stays intact for parsing.
    """
    s = (text or "").strip()
    for suffix in (" UTC", "UTC", " utc", " Z"):
        if s.endswith(suffix):
            return s[:-len(suffix)].strip()
    return s


def parse_activations(body, max_n=60):
    """Parse the hams.at Atom feed into a list of activation dicts.

    Each: {title, callsign, sat, grid, start, end, max_el, freq, mode, comment}.
    Returns [] on an empty/non-XML body.
    """
    if not body or "<entry" not in body:
        return []
    out = []
    for block in re.findall(r"<entry[^>]*>(.*?)</entry>", body,
                            re.DOTALL | re.IGNORECASE):
        title = _entry_tag(block, "title")
        content = _entry_tag(block, "content")
        # The feed delivers its content HTML-escaped inside the Atom entry
        # (&lt;li&gt;...), and CDATA-wrapped in some entries. Unescape before
        # looking for the list items or every field comes back empty - which is
        # what made every activation report "feed date/time unusable".
        content = content.replace("<![CDATA[", "").replace("]]>", "")
        if "&lt;" in content and "<li" not in content:
            import html as _html
            content = _html.unescape(content)

        # Title format: "[YYYY-MM-DD] CALL on SAT from GRID". The DATE lives
        # here, not in the content - the list items carry only a clock time. It
        # was being matched and thrown away, leaving nothing to combine with
        # "Start time".
        call = sat = grid = date = ""
        md = re.match(r"\s*\[([^\]]*)\]\s*(.*)$", title)
        rest = title
        if md:
            date = md.group(1).strip()
            rest = md.group(2)
        mt = re.match(r"\s*(\S+)\s+on\s+(.+?)\s+from\s+(\S+)", rest)
        if mt:
            call, sat, grid = mt.group(1), mt.group(2).strip(), mt.group(3)
        else:
            call = rest.strip()
        out.append({
            "title": title,
            "date": date,
            "callsign": call,
            "sat": sat,
            "grid": grid,
            "start": _li_value(content, "Start time"),
            "end": _li_value(content, "End time"),
            "max_el": _li_value(content, "Max elevation"),
            "freq": _li_value(content, "Frequency"),
            "mode": _li_value(content, "Mode"),
            "comment": _li_value(content, "Comment"),
        })
        if len(out) >= max_n:
            break
    return out


class FeedError(Exception):
    """The feed could not be fetched or was not a feed."""


def fetch_activations(http_get):
    """Fetch and parse the hams.at feed.

    Raises FeedError on a transport failure or a non-feed body. Returning []
    for both "the fetch failed" and "there is nothing scheduled" is what made a
    broken endpoint look like a quiet weekend - the caller needs to tell them
    apart to show a useful message.
    """
    try:
        body = http_get(HAMSAT_FEED_URL, timeout=25)
    except Exception as exc:
        raise FeedError("could not reach hams.at: %s" % str(exc)[:60]) from exc
    if not body or not body.strip():
        raise FeedError("hams.at returned an empty response")
    low = body.lstrip()[:200].lower()
    if "<entry" not in body and ("<html" in low or "<!doctype" in low):
        raise FeedError("hams.at returned a web page, not the feed "
                        "(has the feed URL or its auth changed?)")
    return parse_activations(body)
