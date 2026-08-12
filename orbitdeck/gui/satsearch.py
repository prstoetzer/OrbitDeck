"""orbitdeck.gui.satsearch - search the full CelesTrak catalog and parse hits.

CardSat's satellite list can search the *entire* public catalog (independent of
the configured GP source) by name substring or NORAD number, and add any hit as
an auto-updating favorite. This module provides the URL construction and JSON
parsing so the store/UI can offer the same. Network fetching goes through the
store's http helper (kept out of here so the parsing is unit-testable offline).

CelesTrak's gp.php accepts:
  - CATNR=<n>            exact NORAD catalog number
  - NAME=<substring>    case-insensitive name substring match
with FORMAT=JSON returning an OMM/GP JSON array. CelesTrak enforces strict
courtesy limits (a few queries per couple of hours per IP), so callers must rate-
limit; helpers for that live in the store.
"""

import json
from urllib.parse import quote

CELESTRAK_GP = "https://celestrak.org/NORAD/elements/gp.php?"


def search_url(query):
    """Build the CelesTrak gp.php search URL for a query string.

    An all-digits query is treated as a NORAD catalog number (CATNR=); anything
    else is a name substring (NAME=). Returns (url, kind) where kind is
    'catnr' or 'name'.
    """
    q = (query or "").strip()
    if not q:
        raise ValueError("empty query")
    if q.isdigit():
        return CELESTRAK_GP + "CATNR=" + quote(q) + "&FORMAT=JSON", "catnr"
    return CELESTRAK_GP + "NAME=" + quote(q) + "&FORMAT=JSON", "name"


def catnr_url(norad):
    """URL to fetch a single object's current elements by NORAD id."""
    return CELESTRAK_GP + "CATNR=" + quote(str(int(norad))) + "&FORMAT=JSON"


def parse_results(text):
    """Parse a CelesTrak gp.php JSON response into a list of hit dicts.

    Each hit: {norad, name, epoch, omm} where omm is the raw OMM record (so it
    can be handed straight to SatDb.load_gp_json or sat_from_dict). Returns [] for
    an empty/non-JSON body (CelesTrak returns 'No GP data found' as text on a
    miss, and may return a plain-text error/limit notice).
    """
    stripped = (text or "").lstrip()
    if not stripped or stripped[0] not in "[{":
        return []
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    if isinstance(data, dict):
        data = [data]
    out = []
    for rec in data:
        if not isinstance(rec, dict):
            continue
        norad = rec.get("NORAD_CAT_ID")
        name = rec.get("OBJECT_NAME") or rec.get("OBJECT_ID") or "?"
        if norad is None:
            continue
        out.append({
            "norad": int(norad),
            "name": str(name).strip(),
            "epoch": rec.get("EPOCH", ""),
            "omm": rec,
        })
    return out


def looks_rate_limited(text):
    """True if a non-JSON response looks like a CelesTrak throttle/limit notice."""
    stripped = (text or "").lstrip()
    if stripped[:1] in "[{":
        return False
    low = " ".join((text or "").split()).lower()
    return any(w in low for w in ("rate", "throttl", "limit", "too many"))
