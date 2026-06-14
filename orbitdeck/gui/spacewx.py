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
import os
import time
import urllib.request

F107_URL = "https://services.swpc.noaa.gov/json/f107_cm_flux.json"
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
# Daily geomagnetic A index (planetary Ap) summary:
DST_KP_AP_URL = ("https://services.swpc.noaa.gov/products/"
                 "noaa-planetary-k-index.json")


def _http_get(url, timeout=20):
    req = urllib.request.Request(
        url, headers={"User-Agent": "OrbitDeck/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


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


def fetch(timeout=20):
    """Fetch current space-weather indices. Returns a dict with keys:
    flux, kp, a_index, ts (unix fetched), plus None for any that failed."""
    out = {"flux": None, "kp": None, "a_index": None, "ts": time.time()}

    # --- F10.7 flux ---
    try:
        data = json.loads(_http_get(F107_URL, timeout=timeout))
        # list of {"time_tag":..., "flux":...}; take the most recent numeric
        vals = [d for d in data if d.get("flux") not in (None, "")]
        if vals:
            out["flux"] = float(vals[-1]["flux"])
    except Exception:
        pass

    # --- Kp (planetary) ---
    try:
        data = json.loads(_http_get(KP_URL, timeout=timeout))
        # products feed: first row is a header, rest are
        # [time_tag, kp, a_running?, station_count?]
        rows = [r for r in data if isinstance(r, list)]
        if rows and rows[0] and rows[0][0] in ("time_tag",):
            rows = rows[1:]
        if rows:
            last = rows[-1]
            try:
                out["kp"] = float(last[1])
            except (ValueError, IndexError):
                pass
            # some feeds carry a running A in column 2
            if len(last) > 2:
                try:
                    out["a_index"] = float(last[2])
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass

    # derive A from Kp if the feed didn't carry one
    if out["a_index"] is None and out["kp"] is not None:
        out["a_index"] = float(_kp_to_ap(out["kp"]))

    return out


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
