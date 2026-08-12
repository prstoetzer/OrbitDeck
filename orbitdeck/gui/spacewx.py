"""
spacewx.py - solar/geomagnetic indices for propagation planning.

Fetches the indices CardSat shows -- the 10.7 cm solar radio flux (F10.7), the
planetary Kp index, and the running A index -- from NOAA SWPC's public JSON
feeds. No API key. Results are cached to disk so the screen still shows the last
values (with an age note) when offline.

NOAA SWPC endpoints used (documented, public):
  * F10.7 flux:  https://services.swpc.noaa.gov/json/f107_cm_flux.json
  * Kp (planetary):
        https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json
  * A index (daily, from the DGD report is text; we derive a running A from Kp
    when a numeric feed isn't available).
"""

import json
import time

F107_URL = "https://services.swpc.noaa.gov/json/f107_cm_flux.json"
# Observed monthly indices, for the sunspot number (the MUF model wants SSN,
# not flux) and a 90-day flux mean.
SSN_URL = ("https://services.swpc.noaa.gov/json/solar-cycle/"
           "observed-solar-cycle-indices.json")
# Kp products feed: rows of [time_tag, Kp, a_running, station_count] with a
# header row first. Kp values are strings.
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
# Dict-format 1-minute Kp feed (fallback / cross-check):
KP_JSON_URL = ("https://services.swpc.noaa.gov/json/"
               "planetary_k_index_1m.json")
# Daily geomagnetic indices (DGD) gives the planetary A index directly:
DGD_URL = ("https://services.swpc.noaa.gov/text/"
           "daily-geomagnetic-indices.txt")


def _http_get(url, timeout=20):
    from .net import http_get
    return http_get(url, timeout=timeout)


def _kp_to_ap(kp):
    """Convert a Kp value to its equivalent ap amplitude (standard table)."""
    table = {0.0: 0, 0.33: 2, 0.67: 3, 1.0: 4, 1.33: 5, 1.67: 6, 2.0: 7,
             2.33: 9, 2.67: 12, 3.0: 15, 3.33: 18, 3.67: 22, 4.0: 27,
             4.33: 32, 4.67: 39, 5.0: 48, 5.33: 56, 5.67: 67, 6.0: 80,
             6.33: 94, 6.67: 111, 7.0: 132, 7.33: 154, 7.67: 179, 8.0: 207,
             8.33: 236, 8.67: 300, 9.0: 400}
    # nearest key
    best = min(table.keys(), key=lambda k: abs(k - kp))
    return table[best]


def _newest(records, value_key, time_key="time_tag"):
    """The record with the latest timestamp, chosen by SORTING.

    SWPC's feeds do not agree on direction: f107_cm_flux.json is newest-FIRST
    while planetary_k_index_1m.json is oldest-first. Taking [-1] gave a flux
    40 days stale (201 sfu when the day's value was 95). Sort on the timestamp
    and the ordering stops mattering.
    """
    vals = [r for r in records
            if r.get(value_key) not in (None, "") and r.get(time_key)]
    if not vals:
        return None
    return max(vals, key=lambda r: str(r[time_key]))


def fetch(timeout=20):
    """Fetch current space-weather indices. Returns a dict with keys:
    flux, ssn, flux_90d, kp, a_index, ts (unix fetched), plus None for any
    that failed."""
    out = {"flux": None, "ssn": None, "flux_90d": None,
           "kp": None, "a_index": None, "ts": time.time()}

    # --- F10.7 flux ---
    try:
        data = json.loads(_http_get(F107_URL, timeout=timeout))
        rec = _newest(data, "flux")
        if rec:
            out["flux"] = float(rec["flux"])
            out["flux_time"] = rec.get("time_tag")
            if rec.get("ninety_day_mean") not in (None, ""):
                out["flux_90d"] = float(rec["ninety_day_mean"])
    except Exception:
        pass

    # --- sunspot number (monthly observed) ---
    # The MUF model is driven by SSN, not flux, so fetch it rather than making
    # the user type a number they would have to look up elsewhere.
    try:
        data = json.loads(_http_get(SSN_URL, timeout=timeout))
        rec = _newest(data, "ssn", time_key="time-tag")
        if rec:
            val = float(rec["ssn"])
            if val >= 0:                       # -1 marks an unsmoothed gap
                out["ssn"] = val
                out["ssn_month"] = rec.get("time-tag")
            if out["flux_90d"] is None and rec.get("f10.7") not in (None, ""):
                f = float(rec["f10.7"])
                if f > 0:
                    out["flux_90d"] = f
    except Exception:
        pass

    # --- Kp (planetary): try the dict feed first, then the products array ---
    kp = None
    try:
        data = json.loads(_http_get(KP_JSON_URL, timeout=timeout))
        # list of {"time_tag":..., "kp_index":..., "estimated_kp":...}
        vals = [d for d in data
                if d.get("kp_index") is not None
                or d.get("estimated_kp") is not None
                or d.get("kp") is not None]
        if vals:
            # sorted, not [-1]: see _newest() - the SWPC feeds disagree on
            # direction and this one happens to be oldest-first today
            last = max(vals, key=lambda r: str(r.get("time_tag", "")))
            raw = (last.get("kp_index")
                   if last.get("kp_index") is not None
                   else last.get("estimated_kp")
                   if last.get("estimated_kp") is not None
                   else last.get("kp"))
            kp = float(raw)
    except Exception:
        kp = None

    if kp is None:
        try:
            data = json.loads(_http_get(KP_URL, timeout=timeout))
            rows = [r for r in data if isinstance(r, list)]
            # drop a header row if present (non-numeric second column)
            if rows:
                try:
                    float(rows[0][1])
                except (ValueError, TypeError, IndexError):
                    rows = rows[1:]
            # walk backwards to the last row with a parseable Kp
            for row in reversed(rows):
                try:
                    kp = float(row[1])
                    break
                except (ValueError, TypeError, IndexError):
                    continue
        except Exception:
            kp = None
    out["kp"] = kp

    # --- A index: prefer the DGD daily report (gives planetary A directly) ---
    a_idx = None
    try:
        txt = _http_get(DGD_URL, timeout=timeout)
        a_idx = _parse_dgd_planetary_a(txt)
    except Exception:
        a_idx = None
    # fall back to converting Kp -> ap-equivalent amplitude
    if a_idx is None and kp is not None:
        a_idx = float(_kp_to_ap(kp))
    out["a_index"] = a_idx

    return out


def _parse_dgd_planetary_a(text):
    """Pull the most recent planetary A index from NOAA's daily-geomagnetic-
    indices text report. The file has a header block of comment lines (# / :)
    then dated rows; the planetary A is the first numeric column after the date
    in the 'Planetary' section. We take the last dated data row's A value."""
    last_a = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#:":
            continue
        parts = line.split()
        # rows look like: YYYY MM DD  <A>  <K-values...>; require date + A
        if len(parts) >= 4 and parts[0].isdigit() and len(parts[0]) == 4:
            try:
                a = int(parts[3])
                if 0 <= a <= 400:
                    last_a = float(a)
            except (ValueError, IndexError):
                continue
    return last_a


# ---- plain-language interpretation (the labels CardSat shows) ----
def flux_label(flux):
    if flux is None:
        return "\u2014", None
    if flux < 90:
        return "low", "low"
    if flux < 120:
        return "moderate", "moderate"
    if flux < 160:
        return "good", "good"
    return "very high", "high"


def kp_label(kp):
    if kp is None:
        return "\u2014", None
    if kp < 3:
        return "quiet", "quiet"
    if kp < 4:
        return "unsettled", "unsettled"
    if kp < 5:
        return "active", "active"
    if kp < 6:
        return "minor storm", "minor"
    if kp < 7:
        return "moderate storm", "moderate"
    return "major storm", "major"


def a_label(a):
    if a is None:
        return "\u2014", None
    if a < 8:
        return "quiet", "quiet"
    if a < 16:
        return "unsettled", "unsettled"
    if a < 30:
        return "active", "active"
    return "storm", "storm"


def outlook(flux, kp):
    """One-line operating outlook heuristic (HF + satellite paths)."""
    if kp is not None and kp >= 5:
        return ("Geomagnetic storm: expect auroral flutter on VHF, degraded "
                "high-latitude HF, possible aurora-mode openings.")
    parts = []
    if flux is not None:
        if flux >= 120:
            parts.append("good HF ionisation (higher MUF, 10/12 m likely open)")
        elif flux < 90:
            parts.append("weak HF ionisation (low MUF, higher bands quiet)")
        else:
            parts.append("moderate HF conditions")
    if kp is not None and kp < 3:
        parts.append("quiet geomagnetic field (stable paths)")
    return "; ".join(parts).capitalize() + "." if parts else \
        "Indices unavailable."
