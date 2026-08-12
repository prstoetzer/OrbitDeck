"""orbitdeck.engine.spacewx_interp - plain-language reading of the indices.

Raw numbers are only half the answer: 95 sfu and Kp 6 mean something specific to
an operator, and CardSat's Space Wx screen says what. This is that
interpretation layer - band labels, aurora likelihood and a plain-language
operating outlook - kept in the engine so both front-ends and the report writer
share one set of thresholds.

Thresholds are CardSat 0.9.75's. They are conventional amateur-radio bands
rather than anything official, which is the point: they answer "is this a good
evening" rather than "what is the official NOAA scale".
"""

# (upper bound, label, severity) - severity 0 dim, 1 normal, 2 good, 3 warn,
# 4 bad, so a front-end can colour without re-deriving the meaning.
FLUX_BANDS = ((90, "low", 0), (120, "moderate", 1), (160, "good", 2),
              (float("inf"), "very high", 3))
KP_BANDS = ((4, "quiet", 2), (5, "unsettled", 1), (6, "minor storm", 3),
            (7, "mod. storm", 3), (float("inf"), "major storm", 4))
A_BANDS = ((8, "quiet", 2), (16, "unsettled", 1), (30, "active", 3),
           (float("inf"), "storm", 4))
AURORA_BANDS = ((4, "unlikely", 0), (5, "possible high lat", 1),
                (7, "likely high lat", 3), (float("inf"), "likely mid lat", 4))


def _band(value, bands):
    if value is None:
        return (None, 0)
    for limit, label, sev in bands:
        if value < limit:
            return (label, sev)
    return (bands[-1][1], bands[-1][2])


def flux_label(f107):
    return _band(f107, FLUX_BANDS)


def kp_label(kp):
    return _band(kp, KP_BANDS)


def a_label(a_index):
    return _band(a_index, A_BANDS)


def aurora_label(kp):
    return _band(kp, AURORA_BANDS)


def outlook(f107=None, kp=None):
    """A plain-language operating note.

    Order matters: a geomagnetic storm dominates whatever the flux is doing,
    because that is what will actually change the evening.
    """
    if kp is not None and kp >= 5:
        return ("Geomagnetic storm: aurora and VHF flutter likely; HF paths "
                "disturbed at high latitudes.")
    if f107 is not None and f107 >= 120 and kp is not None and kp < 4:
        return "Strong sun, quiet field: good HF and stable satellite passes."
    if f107 is not None and 0 < f107 < 90:
        return "Weak sun: lower HF MUF; satellite passes unaffected."
    return "Settled conditions; normal HF and satellite operation."


def age_text(fetched_unix, now_unix):
    """How stale the data is, in the form an operator wants to read."""
    # `is None`, not falsiness: a timestamp of 0 is a real (if ancient) epoch,
    # and treating it as "no data" hid the age instead of screaming "very old".
    if fetched_unix is None:
        return ""
    hours = int((now_unix - fetched_unix) / 3600)
    if hours < 1:
        return "<1h old"
    if hours < 48:
        return "%dh old" % hours
    return "%dd old" % (hours // 24)


def rows(data, now_unix=None):
    """Interpreted display rows: [(label, value, severity), ...].

    ``data`` is a spacewx.fetch() dict. Missing values render as '--' rather
    than being dropped, so the screen shows what it could not get.
    """
    import time as _t
    now_unix = now_unix if now_unix is not None else _t.time()
    out = []
    flux = data.get("flux")
    if flux:
        lbl, sev = flux_label(flux)
        out.append(("Solar flux (F10.7)", "%.0f sfu  %s" % (flux, lbl), sev))
    else:
        out.append(("Solar flux (F10.7)", "--", 0))
    if data.get("flux_90d"):
        out.append(("  90-day mean", "%.0f sfu" % data["flux_90d"], 0))
    if data.get("ssn") is not None:
        out.append(("Sunspot number", "%.0f%s" % (
            data["ssn"], ("  (%s)" % data["ssn_month"])
            if data.get("ssn_month") else ""), 1))
    kp = data.get("kp")
    if kp is not None:
        lbl, sev = kp_label(kp)
        out.append(("Kp index", "%.1f  %s" % (kp, lbl), sev))
    else:
        out.append(("Kp index", "--", 0))
    a_idx = data.get("a_index")
    if a_idx is not None:
        lbl, sev = a_label(a_idx)
        out.append(("A index", "%.0f  %s" % (a_idx, lbl), sev))
    if kp is not None:
        lbl, sev = aurora_label(kp)
        out.append(("Aurora", lbl, sev))
    age = age_text(data.get("ts"), now_unix)
    if age:
        out.append(("Data age", age, 0))
    return out


def seed_ssn(cache, default=100.0):
    """Sunspot number for the MUF model, with its provenance.

    Returns ``(ssn, source)``. Order of preference:

      1. an **observed** SSN from the space-weather cache;
      2. one **derived** from F10.7 via the Covington-style relation;
      3. a bare default.

    The source string matters: an observed SSN and one back-computed from flux
    are different claims, and a screen that shows only the number invites the
    operator to trust a derived value as measured. Shared by both front-ends so
    they cannot disagree about what the current SSN is.
    """
    from .muf import ssn_from_flux
    data = cache or {}
    val = data.get("ssn")
    if val not in (None, ""):
        try:
            v = float(val)
            if v >= 0:
                month = data.get("ssn_month")
                return v, "Space Wx (%s)" % (month or "observed")
        except (TypeError, ValueError):
            pass
    flux = data.get("flux")
    if flux not in (None, ""):
        try:
            f = float(flux)
            if f > 0:
                return ssn_from_flux(f), "derived from F10.7 %.0f" % f
        except (TypeError, ValueError):
            pass
    return float(default), "default (no space-weather data yet)"
