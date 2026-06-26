"""orbitterm/fmt.py - formatting helpers shared by OrbitTerm screens."""

import time

COMPASS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(az):
    return COMPASS_16[int((az % 360) / 22.5 + 0.5) % 16]


def fmt_clock(unix, with_date=False):
    if not unix:
        return "--:--"
    lt = time.localtime(unix)
    if with_date:
        return time.strftime("%a %d %b %H:%M:%S", lt)
    return time.strftime("%H:%M:%S", lt)


def fmt_hm(unix):
    if not unix:
        return "--:--"
    return time.strftime("%H:%M", time.localtime(unix))


def fmt_date(unix):
    return time.strftime("%a %d %b", time.localtime(unix))


def fmt_dur(secs):
    secs = int(max(0, secs))
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return "%dh%02dm" % (h, m)
    return "%dm%02ds" % (m, s)


def fmt_countdown(secs):
    """Signed countdown: +mm:ss until, -mm:ss since."""
    sign = "+" if secs >= 0 else "-"
    secs = int(abs(secs))
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return "%s%d:%02d:%02d" % (sign, h, m, s)
    return "%s%02d:%02d" % (sign, m, s)


def fmt_az(az):
    return "%05.1f\u00b0 %s" % (az % 360, compass(az))


def fmt_el(el):
    return "%+05.1f\u00b0" % el


def fmt_freq(hz):
    if hz is None:
        return "--"
    mhz = hz / 1e6
    return "%.4f MHz" % mhz


def fmt_doppler(hz):
    if hz is None:
        return "--"
    if abs(hz) >= 1000:
        return "%+.2f kHz" % (hz / 1000.0)
    return "%+d Hz" % int(round(hz))


def fmt_rate(kms):
    return "%+.3f km/s" % kms


def fmt_latlon(lat, lon):
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return "%5.2f\u00b0%s %6.2f\u00b0%s" % (abs(lat), ns, abs(lon), ew)


def el_bar(el, width=10):
    """A small horizontal elevation bar 0..90deg."""
    frac = max(0.0, min(1.0, el / 90.0))
    fill = int(round(frac * width))
    return "\u2588" * fill + "\u2591" * (width - fill)
