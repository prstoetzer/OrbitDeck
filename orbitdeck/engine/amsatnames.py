"""orbitdeck.engine.amsatnames - match catalog satellites to AMSAT API names.

The AMSAT status API does not use catalog names. It uses its own designators
carrying the transponder mode, like ``AO-7_[V/a]``, ``ISS_[FM]`` or
``CAS-3H``, while the GP catalog carries ``AO-7 (OSCAR 7)``, ``ISS (ZARYA)`` or
``LILACSAT-2``. Guessing a name is how the AO-7 fit ended up querying
``AO-7[A]`` and getting a 404 back.

CardSat solves this by pulling the API's own catalog (``catalog.php``) and
matching each API name to a catalog entry through a ladder of increasingly
tolerant rules. This is that ladder, ported:

  1. **parenthesised designator** - ``AO-7`` matches ``AO-7 (OSCAR 7)`` via the
     token in brackets, which is the usual CelesTrak-name bridge;
  2. **whole-name equality** on the normalised form;
  3. **delimited-token containment** - the API name appears as a whole word;
  4. **legacy prefix base** - ``AO-07`` and ``AO-7`` collapse to the same stem;
  5. **known alias table** for designators with no lexical bridge at all
     (``IO-117`` is ``GREENCUBE``; nothing in the strings connects them).

A satellite can hold several API names - AO-7 has one per transponder mode - so
``names_for`` returns all of them, which is what the mode-switch calculator and
the reporting picker need.

Report precedence, for a satellite seen with several report values in one
summary: Heard beats Telemetry Only beats Not Heard beats nothing, ties broken
by recency, so the status, age and count all come from a single row.
"""

import json
import re

# Designators with no lexical bridge to the catalog name.
ALIASES = {
    "CAS-3H": "LILACSAT-2",     # proven gap vs the AMSAT daily bulletin
    "IO-117": "GREENCUBE",      # bulletin may carry either name
    "LO-19": "LUSAT",           # historic name in most GP sources
}

# Report value -> precedence. Heard(3) > Telemetry Only(2) > Not Heard(1).
PRIORITY = {"heard": 3, "crew active": 3, "telemetry only": 2, "not heard": 1}


def norm(text):
    """Upper-case, keep alphanumerics and hyphens, collapse everything else to
    single spaces. 'AO-7 (OSCAR 7)' -> 'AO-7 OSCAR 7'."""
    out = []
    space = True
    for ch in (text or ""):
        up = ch.upper()
        if up.isalnum() or up == "-":
            out.append(up)
            space = False
        elif not space:
            out.append(" ")
            space = True
    return "".join(out).strip()


def collapse(text):
    """Drop spaces and hyphens too, so AO-7 / AO 7 / AO7 all become AO7."""
    return re.sub(r"[^A-Z0-9]", "", norm(text))


def base_call(text):
    """The legacy stem: stop at the first space/bracket, strip leading zeros in
    the segment after the last hyphen. 'AO-07_[V/a]' -> 'AO-7'."""
    stem = []
    prev = ""
    for ch in (text or ""):
        if ch in " [(":
            break
        if ch == "_":
            break
        stem.append(ch.upper())
        prev = ch
    _ = prev
    s = "".join(stem)
    if "-" in s:
        head, _sep, tail = s.rpartition("-")
        tail = tail.lstrip("0") or "0"
        return "%s-%s" % (head, tail)
    return s


def api_base(api_name):
    """Strip the mode tag: 'AO-7_[V/a]' -> 'AO-7'. Also handles 'AO-7[V/a]'."""
    s = (api_name or "").strip()
    m = re.match(r"^(.*?)_?\[[^\]]*\]$", s)
    return (m.group(1) if m else s).strip()


def _token_in(haystack_norm, needle_norm):
    """True if the needle appears as a whole delimited token."""
    if not needle_norm:
        return False
    return re.search(r"(^|\s)%s($|\s)" % re.escape(needle_norm),
                     haystack_norm) is not None


def match_api_name(api_name, sat_names):
    """Index of the catalog entry this API name belongs to, or None.

    ``sat_names`` is the list of catalog names, in catalog order.
    """
    base = api_base(api_name)
    if not base:
        return None
    bn = norm(base)
    ab = base_call(base)
    bc = collapse(base)
    normed = [norm(n) for n in sat_names]

    # 1. parenthesised designator equality
    for i, name in enumerate(sat_names):
        for tok in re.findall(r"\(([^)]*)\)", name or ""):
            if norm(tok) and norm(tok) == bn:
                return i
    # 2. whole-name equality
    for i, nm in enumerate(normed):
        if nm == bn:
            return i
    # 3. delimited-token containment
    for i, nm in enumerate(normed):
        if _token_in(nm, bn):
            return i
    # 4. legacy prefix base
    for i, name in enumerate(sat_names):
        if ab and base_call(name) == ab:
            return i
    # 5. collapsed form (AO-7 vs AO7), more tolerant than the token tiers
    for i, name in enumerate(sat_names):
        if bc and collapse(name) == bc:
            return i
    # 6. known aliases
    target = ALIASES.get(base.upper())
    if target:
        tn = norm(target)
        for i, nm in enumerate(normed):
            if nm == tn or _token_in(nm, tn):
                return i
    return None


def build_map(catalog_names, sat_names):
    """Map API name -> catalog index for every name that resolves.

    ``catalog_names`` comes from the API's catalog.php; duplicates are ignored.
    """
    out = {}
    for api in catalog_names:
        if not api or api in out:
            continue
        idx = match_api_name(api, sat_names)
        if idx is not None:
            out[api] = idx
    return out


def names_for(name_map, sat_index):
    """Every API name that resolved to this catalog entry.

    AO-7 has one per transponder mode, so this returns a list.
    """
    return sorted(n for n, i in name_map.items() if i == sat_index)


def parse_catalog_names(text):
    """Pull the ``name`` values out of a catalog.php response.

    The API pretty-prints its JSON, so a naive ``"name":"`` byte match finds
    nothing - CardSat hit exactly that and ended up with an empty map, which
    left multi-mode birds like AO-7 offering only one mode. Parse it properly,
    and fall back to a whitespace-tolerant regex if the body is truncated.
    """
    try:
        data = json.loads(text)
        rows = data.get("data") if isinstance(data, dict) else data
        if isinstance(rows, list):
            names = [str(r.get("name", "")).strip()
                     for r in rows if isinstance(r, dict)]
            return [n for n in names if n]
    except (TypeError, ValueError, AttributeError):
        pass
    return [m.group(1) for m in
            re.finditer(r'"name"\s*:\s*"([^"]+)"', text or "")]


def status_priority(report):
    return PRIORITY.get((report or "").strip().lower(), 0)


def best_status(rows):
    """Fold several summary rows for one satellite into the one that wins.

    Higher report precedence wins; a tie is broken by the more recent
    ``latest_reported_time``, so status, age and count all come from one row.
    """
    best = None
    for r in rows:
        p = status_priority(r.get("report"))
        if best is None:
            best = (p, r)
            continue
        bp, br = best
        if p > bp or (p == bp and str(r.get("latest_reported_time", "")) >
                      str(br.get("latest_reported_time", ""))):
            best = (p, r)
    return best[1] if best else None
