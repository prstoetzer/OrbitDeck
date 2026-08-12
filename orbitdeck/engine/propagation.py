"""orbitdeck.engine.propagation - HF / 6 m operating outlook.

Space Wx reports the indices; the MUF screen tabulates path MUF to world
regions. Neither answers the question an operator actually asks before sitting
down: *is 40 m open right now, is 6 m worth watching, and will the low bands be
absorbed?* This is that layer, ported from CardSat 0.9.75's `SCR_PROP`.

Everything here is a **rule of thumb** driven by solar flux and Kp. The models
are deliberately crude - CardSat's own note says as much ("6 m Es is seasonal")
- and they are labelled that way wherever they are shown. They answer "is it
worth turning the radio on", not "what will the signal report be".
"""


import time

# Representative band centres used for the open/fair/weak/shut verdicts.
HF_BANDS = [("80 m", 3.6), ("40 m", 7.1), ("30 m", 10.1), ("20 m", 14.1),
            ("17 m", 18.1), ("15 m", 21.2), ("12 m", 24.9), ("10 m", 28.3),
            ("6 m", 50.1)]

# Northern-hemisphere sporadic-E seasons: a broad May-August peak and a weaker
# December-January one. Es is what actually opens 6 m and 10 m most of the time.
ES_STRONG_MONTHS = (5, 6, 7, 8)
ES_WEAK_MONTHS = (12, 1)


def simple_muf_mhz(flux, kp=0.0, day=True):
    """A single headline MUF (MHz), not a path calculation.

    Rises with solar flux, falls with geomagnetic activity, and the daylight
    ionosphere supports a higher frequency than the night one. For a real path
    use the MINIMUF model in :mod:`orbitdeck.engine.muf`; this is the one number
    that goes at the top of a summary.
    """
    if flux is None or flux <= 0:
        return None
    k = kp if (kp is not None and kp >= 0) else 0.0
    muf = 8.0 + (flux - 65.0) * 0.16 - k * 1.2 + (4.0 if day else -3.0)
    return max(3.0, muf)


def band_state(muf_mhz, band_mhz):
    """open / fair / weak / shut for a band, given the headline MUF.

    The margin, not the ratio, is what matters: a band four megahertz below the
    MUF is reliably open, one above it is shut.
    """
    if muf_mhz is None:
        return ("unknown", 0)
    head = muf_mhz - band_mhz
    if head >= 4:
        return ("open", 3)
    if head >= 0:
        return ("fair", 2)
    if head >= -3:
        return ("weak", 1)
    return ("shut", 0)


def band_outlook(flux, kp=0.0, day=True, bands=None):
    """[(band, state, severity), ...] for every band."""
    muf = simple_muf_mhz(flux, kp, day)
    return [(name, ) + band_state(muf, mhz)
            for name, mhz in (bands or HF_BANDS)]


def aurora_vhf(kp):
    """Auroral propagation likelihood on 6 m / 2 m.

    Radio aurora needs a disturbed field; below Kp 5 it is not worth pointing
    north, and above Kp 7 it can reach the mid latitudes.
    """
    if kp is None or kp < 0:
        return ("unknown", 0)
    if kp < 4:
        return ("unlikely", 0)
    if kp < 5:
        return ("possible at high latitudes", 1)
    if kp < 7:
        return ("likely at high latitudes", 2)
    return ("likely into mid latitudes", 3)


def absorption(kp, flux=None):
    """D-layer absorption on the low bands.

    A disturbed field raises absorption, which is what kills 80 m and 40 m
    during a storm even though the MUF looks fine.
    """
    if kp is None or kp < 0:
        return ("unknown", 0)
    if kp < 4:
        return ("low - 80/40 normal", 0)
    if kp < 5:
        return ("moderate - low bands noisy", 1)
    if kp < 7:
        return ("high - 80/40 degraded", 2)
    return ("severe - low bands absorbed", 3)


def meteor_scatter(when=None):
    """Meteor-scatter prospects: named shower, or the sporadic background.

    Dates are the conventional peaks; a shower is worth an early start, the
    background is always there around dawn.
    """
    tm = time.gmtime(when if when is not None else time.time())
    md = (tm.tm_mon, tm.tm_mday)
    showers = [
        ((1, 1), (1, 5), "Quadrantids"),
        ((4, 19), (4, 25), "Lyrids"),
        ((5, 3), (5, 10), "Eta Aquariids"),
        ((7, 25), (8, 20), "Perseids"),
        ((10, 18), (10, 24), "Orionids"),
        ((11, 15), (11, 20), "Leonids"),
        ((12, 10), (12, 16), "Geminids"),
    ]
    for lo, hi, name in showers:
        if lo <= md <= hi:
            return ("%s active - strong MS" % name, 3)
    return ("sporadic background (best near dawn)", 1)


def sporadic_e(when=None):
    """Sporadic-E season, which is what actually opens 6 m most years."""
    mon = time.gmtime(when if when is not None else time.time()).tm_mon
    if mon in ES_STRONG_MONTHS:
        return ("Es season - 6 m and 10 m openings likely", 3)
    if mon in ES_WEAK_MONTHS:
        return ("minor winter Es season", 1)
    return ("outside the main Es season", 0)


def geomagnetic_state(kp):
    if kp is None or kp < 0:
        return ("unknown", 0)
    if kp < 4:
        return ("quiet", 0)
    if kp < 5:
        return ("unsettled", 1)
    if kp < 6:
        return ("minor storm", 2)
    if kp < 7:
        return ("moderate storm", 2)
    return ("major storm", 3)


def outlook(cache, when=None):
    """The whole picture from a space-weather cache dict.

    Returns a dict with the headline MUFs, per-band day and night states, and
    the propagation modes. Missing inputs yield "unknown" rather than a
    fabricated number.
    """
    when = when if when is not None else time.time()
    flux = (cache or {}).get("flux")
    kp = (cache or {}).get("kp")
    day_muf = simple_muf_mhz(flux, kp, True)
    night_muf = simple_muf_mhz(flux, kp, False)
    return {
        "flux": flux,
        "kp": kp,
        "muf_day": day_muf,
        "muf_night": night_muf,
        "bands_day": band_outlook(flux, kp, True),
        "bands_night": band_outlook(flux, kp, False),
        "geomagnetic": geomagnetic_state(kp),
        "aurora": aurora_vhf(kp),
        "absorption": absorption(kp, flux),
        "meteor": meteor_scatter(when),
        "sporadic_e": sporadic_e(when),
        "have_data": flux is not None or kp is not None,
    }


def summary_line(res):
    """One sentence for the top of a screen or report."""
    if not res.get("have_data"):
        return "No space-weather data yet - update it on the Space Wx screen."
    parts = []
    if res["muf_day"]:
        parts.append("MUF about %.0f MHz by day, %.0f at night"
                     % (res["muf_day"], res["muf_night"]))
    parts.append("field %s" % res["geomagnetic"][0])
    open_bands = [b for b, st, _s in res["bands_day"] if st == "open"]
    if open_bands:
        parts.append("open by day: " + ", ".join(open_bands))
    else:
        parts.append("no band comfortably open by day")
    return "; ".join(parts) + "."


