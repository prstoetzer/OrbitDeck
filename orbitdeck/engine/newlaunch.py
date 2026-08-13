"""orbitdeck.engine.newlaunch - "what went up that I can actually work?"

Crosses the recently catalogd objects against the SatNOGS transmitter
database and returns the intersection.

OrbitDeck takes the design document's **portable alternative** rather than the
embedded path: instead of probing candidates one at a time against SatNOGS, it
reuses the bulk transmitter database the app already fetches and caches by
NORAD id. That turns roughly a hundred network round-trips into a dictionary
lookup, and removes the probe budget entirely - every filtered candidate is
checked, not just the newest N. The document's ordering caution therefore
stops mattering here, but the filter still runs first because the counts shown
to the operator should describe what was actually considered.

A negative result means "not known to SatNOGS", never "has no transmitter".
SatNOGS coverage lags launches by days to weeks, and the wording throughout
reflects that.
"""

import json

LAST_30_URL = ("https://celestrak.org/NORAD/elements/gp.php"
               "?GROUP=last-30-days&FORMAT=JSON")

# CelesTrak publishes exactly ONE recency group: last-30-days. There is no
# last-60-days group - a request for it returns an empty result rather than an
# error, which is the worst kind of wrong: it looks like a quiet two months.
# A wider window has to come from the international designator instead, which
# IS in the GP data.
LAUNCH_YEAR_URL = ("https://celestrak.org/NORAD/elements/gp.php"
                   "?INTDES=%s&FORMAT=JSON")


def launch_year(intl_des):
    """Launch year from an international designator, or None.

    Delegates to :func:`analysis.cospar_launch_year`, which already handles
    both the 4-digit form the GP JSON uses ("1998-067A") and the 2-digit TLE
    form with its 1957 pivot. My first version read the first two characters
    and turned 1998 into 2019 - a duplicate of working code, written wrong.
    """
    from .analysis import cospar_launch_year
    return cospar_launch_year(intl_des)


def filter_by_launch_year(entries, year):
    """Candidates whose international designator names ``year``."""
    out = []
    for e in entries:
        des = (e.get("omm") or {}).get("OBJECT_ID") or ""
        if launch_year(des) == year:
            out.append(e)
    return out

# ---------------------------------------------------------------------------
# The noise filter
# ---------------------------------------------------------------------------
# Two justifications only: the object *cannot carry an amateur transmitter*, or
# it *exists in industrial quantities*. Not "looks obscure", not "commercial
# operator" - those would cut real targets.

# Constellations and fleets that arrive in batches of twenty to sixty.
_TOKENS = [
    # broadband / IoT
    "STARLINK", "ONEWEB", "KUIPER", "QIANFAN", "SPACESAIL", "GUOWANG",
    "LIGHTSPEED", "HONGYAN", "HONGYUN", "YINHE", "GALAXYSPACE", "LEOSAT",
    "IRIDIUM", "GLOBALSTAR", "ORBCOMM", "SPACEBEE", "SWARM", "LACUNA",
    "O3B", "ASTROCAST", "KEPLER", "FOSSA",
    # commercial imaging / SAR
    "FLOCK", "SKYSAT", "LEMUR", "ICEYE", "CAPELLA", "BLACKSKY", "PLANET",
    "NUSAT", "SUPERVIEW", "JILIN", "GAOFEN", "YAOGAN", "SIWEI", "PELICAN",
    "TANAGER", "EOS-", "SENTINEL", "WORLDVIEW", "GEOEYE",
    # navigation
    "NAVSTAR", "GPS BIII", "GLONASS", "BEIDOU", "GALILEO", "IRNSS", "QZS",
    # launch hardware
    "SHROUD", "FAIRING", "PLATFORM", "AKM", "ADAPTER", "DISPENSER",
    "BREEZE", "CENTAUR", "FREGAT", "BLOCK DM",
]

def is_noise(name):
    """True if this catalog name is a rocket body, debris or a fleet member.

    ``TBA`` objects are never filtered: that is precisely the state a freshly
    launched amateur cubesat occupies for its first weeks, and cutting it would
    defeat the whole feature.
    """
    n = (name or "").upper().strip()
    if not n:
        return False
    if "TBA" in n or "TO BE ASSIGNED" in n:
        return False                      # the escape clause, checked first
    # structural rules
    if "R/B" in n:
        return True
    if " DEB" in n or n.endswith("DEB") or "DEBRIS" in n:
        return True
    return any(tok in n for tok in _TOKENS)

def parse_gp(text):
    """CelesTrak GP JSON to candidates, keeping the element set for reuse.

    The GP entry is the element source for anything the operator adds, so it
    travels with the candidate rather than being fetched a second time.
    """
    try:
        arr = json.loads(text)
    except Exception:
        return []
    out = []
    for item in arr:
        norad = item.get("NORAD_CAT_ID")
        if norad is None:
            continue
        try:
            norad = int(norad)
        except (TypeError, ValueError):
            continue
        out.append({"norad": norad,
                    "name": (item.get("OBJECT_NAME") or "").strip(),
                    "omm": item})
    return out

def select_candidates(entries, filter_noise=True, limit=None):
    """Filter, then take the newest.

    In that order: filtering afterwards lets one constellation batch consume
    the whole budget and bury everything else. Newest is by descending catalog
    number, which is monotonic with cataloging date and present in the GP data;
    an explicit launch date is not, and deriving one from the epoch is
    unreliable for objects cataloged late.
    """
    rows = [e for e in entries if not (filter_noise and is_noise(e["name"]))]
    rows.sort(key=lambda e: -e["norad"])
    return rows[:limit] if limit else rows

def transmitters_for(tx_by_norad, norad):
    """Transmitter records for one object from the cached SatNOGS database."""
    if not tx_by_norad:
        return []
    return tx_by_norad.get(str(int(norad))) or []

def summarize_tx(records):
    """Count, first downlink (Hz) and first mode, as the list needs."""
    if not records:
        return {"count": 0, "downlink_hz": None, "mode": None}
    downlink = None
    mode = None
    for r in records:
        if downlink is None and r.get("downlink_low"):
            try:
                downlink = int(r["downlink_low"])
            except (TypeError, ValueError):
                pass
        if mode is None and r.get("mode"):
            mode = str(r["mode"])
        if downlink is not None and mode is not None:
            break
    return {"count": len(records), "downlink_hz": downlink, "mode": mode}

def discover(entries, tx_by_norad, filter_noise=True, limit=None,
             known_norads=()):
    """Cross candidates against the transmitter database.

    Returns ``(hits, stats)``. ``stats`` carries the provenance line the UI
    must show: how many were considered and how many the filter cut. Without
    it the operator cannot tell a quiet month from a Starlink-heavy one, and
    the filter's behavior stays mysterious.
    """
    total = len(entries)
    cands = select_candidates(entries, filter_noise=filter_noise, limit=limit)
    cut = total - len(cands)
    known = {int(n) for n in known_norads}
    hits = []
    for c in cands:
        recs = transmitters_for(tx_by_norad, c["norad"])
        if not recs:
            continue
        info = summarize_tx(recs)
        hits.append({
            "norad": c["norad"], "name": c["name"], "omm": c["omm"],
            "tx_count": info["count"], "downlink_hz": info["downlink_hz"],
            "mode": info["mode"], "records": recs,
            "in_catalog": c["norad"] in known,
        })
    return hits, {"total": total, "probed": len(cands), "cut": cut,
                  "hits": len(hits), "filtered": filter_noise}

def provenance(stats):
    """The one line that makes the filter's behavior visible."""
    base = "%d hit / %d probed, %d cut" % (
        stats["hits"], stats["probed"], stats["cut"])
    if not stats["filtered"]:
        base += " (filter off)"
    return base

def empty_message(stats):
    """Worded so a negative is never read as 'this has no transmitter'."""
    if stats["probed"] == 0:
        return ("Nothing to check \u2014 every object in the window was "
                "filtered out. Turn the filter off to see them all.")
    return ("No transmitters found among the %d objects checked. New payloads "
            "are often silent at first, or not yet listed by SatNOGS \u2014 "
            "coverage lags a launch by days to weeks, so this is not proof "
            "that any of them is quiet." % stats["probed"])

def fmt_downlink(hz):
    if not hz:
        return "\u2014"
    return "%.4f MHz" % (hz / 1e6)

