"""orbitdeck.engine.spacetrack - Space-Track orbital history (gp_history).

Fetches a satellite's *historical* mean elements from space-track.org and turns
them into a time series you can plot: semi-major axis, eccentricity,
inclination, period, apogee, perigee and B*. That shows an orbit's whole life -
launch, drift, manoeuvres, drag decay - against its current elements.

Ported from CardSat 0.9.73-0.9.75, with one deliberate difference: CardSat
decimates the CSV into 120-240 time bins because the ESP32 has ~31 KB of
contiguous heap. Desktop has no such constraint, so this keeps **every row at
full resolution**; binning is available but off by default.

Two fidelity details carried over from CardSat's bench findings:

  * Decades-old gp_history rows carry EMPTY derived-value cells. Parsing those
    as 0.0 "zero-poisons" the series - it drags the minimum to zero and flattens
    real structure. An absent cell is recorded as None and simply skipped for
    that column, per column, not per row.
  * gp_history may quote its CSV fields, so the parser is quote-aware.

Credentials are the user's own Space-Track login. Space-Track's API ToS asks
clients to stay well under 30 requests/minute and 300/hour, and treats
gp_history as archival data to fetch once and cache rather than poll - both are
enforced here.
"""

import csv
import io
import time
from urllib.parse import quote

BASE = "https://www.space-track.org"
LOGIN_URL = BASE + "/ajaxauth/login"

# CSV predicate order requested from gp_history.
COLUMNS = ["SEMIMAJOR_AXIS", "ECCENTRICITY", "INCLINATION", "PERIOD",
           "APOAPSIS", "PERIAPSIS", "BSTAR"]
COLUMN_LABELS = {
    "SEMIMAJOR_AXIS": ("Semi-major axis", "km"),
    "ECCENTRICITY": ("Eccentricity", ""),
    "INCLINATION": ("Inclination", "deg"),
    "PERIOD": ("Period", "min"),
    "APOAPSIS": ("Apogee", "km"),
    "PERIAPSIS": ("Perigee", "km"),
    "BSTAR": ("B* drag term", "1/ER"),
}
# columns that are meaningless at or below zero, so a 0 means "absent"
STRICTLY_POSITIVE = {"SEMIMAJOR_AXIS", "INCLINATION", "PERIOD", "APOAPSIS",
                     "PERIAPSIS"}

# Courtesy limits (Space-Track API ToS).
MIN_QUERY_INTERVAL_S = 3.0
MAX_QUERIES_PER_HOUR = 200


class SpaceTrackError(Exception):
    """Login, transport or query failure."""


def history_path(norad, since="1957-01-01"):
    """Relative gp_history query path for one object, oldest first.

    ``since`` is a YYYY-MM-DD date; the default predates Sputnik so it asks for
    the object's entire archive.
    """
    return ("/basicspacedata/query/class/gp_history/NORAD_CAT_ID/%d"
            "/EPOCH/%%3E%s/orderby/EPOCH%%20asc/format/csv/predicates/"
            "EPOCH,%s" % (int(norad), quote(since), ",".join(COLUMNS)))


def history_url(norad, since="1957-01-01"):
    return BASE + history_path(norad, since)


def parse_epoch(text):
    """Parse a Space-Track epoch to a unix timestamp, or None.

    Space-Track CSV uses 'YYYY-MM-DD HH:MM:SS[.ffffff]'; the JSON form uses a
    'T' separator. Epochs are UTC by definition.
    """
    s = (text or "").strip().strip('"')
    if not s:
        return None
    s = s.replace("T", " ")
    if "." in s:
        s = s.split(".")[0]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            import calendar
            return calendar.timegm(time.strptime(s, fmt))
        except ValueError:
            continue
    return None


def _cell(value, column):
    """Return a float for a populated cell, else None.

    An empty (or whitespace) cell is *absent*, not zero - see the module note.
    For strictly-positive columns a zero is also treated as absent, because
    that is what an empty derived value degrades to upstream.
    """
    if value is None:
        return None
    s = str(value).strip().strip('"')
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if column in STRICTLY_POSITIVE and v <= 0.0:
        return None
    return v


def parse_history_csv(text):
    """Parse a gp_history CSV response into a list of sample dicts.

    Each sample: {'epoch': unix, plus one key per column with a float or None}.
    Rows without a usable epoch are skipped. Quote-aware. Returns [] for an
    empty or header-only body.
    """
    if not text or not text.strip():
        return []
    rdr = csv.reader(io.StringIO(text))
    try:
        header = next(rdr)
    except StopIteration:
        return []
    header = [h.strip().strip('"').upper() for h in header]
    if "EPOCH" not in header:
        return []
    idx = {name: header.index(name) for name in header}
    out = []
    for row in rdr:
        if not row:
            continue
        try:
            ep = parse_epoch(row[idx["EPOCH"]])
        except IndexError:
            continue
        if ep is None:
            continue
        rec = {"epoch": ep}
        for col in COLUMNS:
            j = idx.get(col)
            rec[col] = _cell(row[j], col) if (j is not None and j < len(row)) \
                else None
        out.append(rec)
    out.sort(key=lambda r: r["epoch"])
    return out


def series(samples, column):
    """Extract (times, values) for one column, skipping absent cells."""
    ts, vs = [], []
    for s in samples:
        v = s.get(column)
        if v is not None:
            ts.append(s["epoch"])
            vs.append(v)
    return ts, vs


def summarize(samples, current=None):
    """Per-column summary rows: first, last, change, min and max.

    ``current`` may be a dict of the satellite's present values (from the loaded
    GP) to compare the archive against. Returns a list of dicts, one per column
    that has any data.
    """
    out = []
    for col in COLUMNS:
        ts, vs = series(samples, col)
        if not vs:
            continue
        label, unit = COLUMN_LABELS[col]
        first, last = vs[0], vs[-1]
        row = {
            "column": col, "label": label, "unit": unit,
            "n": len(vs),
            "first": first, "last": last,
            "delta": last - first,
            "min": min(vs), "max": max(vs),
            "t_first": ts[0], "t_last": ts[-1],
        }
        span_days = (ts[-1] - ts[0]) / 86400.0
        row["rate_per_year"] = ((last - first) / span_days * 365.25
                                if span_days > 0 else 0.0)
        if current and current.get(col) is not None:
            row["current"] = current[col]
            row["vs_current"] = current[col] - last
        out.append(row)
    return out


def decimate(samples, bins):
    """Optionally reduce samples to ``bins`` time bins (CardSat's ESP32 path).

    Desktop keeps full resolution by default; this exists for very long spans on
    constrained displays. Each bin carries the mean plus the true min/max, and
    counts presence per column so absent cells never dilute a mean.
    """
    if bins <= 0 or len(samples) <= bins:
        return list(samples)
    t0, t1 = samples[0]["epoch"], samples[-1]["epoch"]
    if t1 <= t0:
        return list(samples)
    width = (t1 - t0) / float(bins)
    acc = [None] * bins
    for s in samples:
        i = min(bins - 1, int((s["epoch"] - t0) / width))
        if acc[i] is None:
            acc[i] = {"epoch_sum": 0.0, "n_epoch": 0,
                      "sum": {c: 0.0 for c in COLUMNS},
                      "cnt": {c: 0 for c in COLUMNS},
                      "min": {c: None for c in COLUMNS},
                      "max": {c: None for c in COLUMNS}}
        a = acc[i]
        a["epoch_sum"] += s["epoch"]
        a["n_epoch"] += 1
        for c in COLUMNS:
            v = s.get(c)
            if v is None:
                continue
            a["sum"][c] += v
            a["cnt"][c] += 1
            a["min"][c] = v if a["min"][c] is None else min(a["min"][c], v)
            a["max"][c] = v if a["max"][c] is None else max(a["max"][c], v)
    out = []
    for a in acc:
        if a is None or not a["n_epoch"]:
            continue
        rec = {"epoch": a["epoch_sum"] / a["n_epoch"]}
        for c in COLUMNS:
            rec[c] = (a["sum"][c] / a["cnt"][c]) if a["cnt"][c] else None
            rec[c + "_min"] = a["min"][c]
            rec[c + "_max"] = a["max"][c]
        out.append(rec)
    return out


class SpaceTrackClient:
    """Minimal authenticated Space-Track client with courtesy rate limiting.

    ``opener`` is a callable(url, data=None, headers=None) -> (body, cookies)
    so the transport can be injected (and unit-tested offline). The default
    uses urllib with a cookie jar.
    """

    def __init__(self, identity, password, opener=None):
        self.identity = identity
        self.password = password
        self._opener = opener
        self._logged_in = False
        self._last_query = 0.0
        self._query_times = []
        self._jar = None

    # -- transport --
    def _default_opener(self, url, data=None):
        import urllib.parse
        import urllib.request
        import http.cookiejar
        if self._jar is None:
            self._jar = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar))
        body = urllib.parse.urlencode(data).encode() if data else None
        req = urllib.request.Request(url, data=body,
                                     headers={"User-Agent": "OrbitDeck"})
        with op.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", "replace")

    def _open(self, url, data=None):
        fn = self._opener or self._default_opener
        return fn(url, data) if data is not None else fn(url)

    def login(self):
        if not self.identity or not self.password:
            raise SpaceTrackError("Space-Track credentials not set")
        body = self._open(LOGIN_URL, {"identity": self.identity,
                                      "password": self.password})
        low = (body or "").lower()
        if "fail" in low or "invalid" in low or "login" in low and "deny" in low:
            raise SpaceTrackError("Space-Track login rejected")
        self._logged_in = True
        return True

    def _throttle(self):
        now = time.time()
        wait = MIN_QUERY_INTERVAL_S - (now - self._last_query)
        if wait > 0:
            time.sleep(wait)
        self._query_times = [t for t in self._query_times if now - t < 3600]
        if len(self._query_times) >= MAX_QUERIES_PER_HOUR:
            raise SpaceTrackError(
                "Space-Track hourly query budget reached - gp_history is "
                "archival, so cache it rather than re-fetching.")

    def fetch_history(self, norad, since="1957-01-01"):
        """Log in if needed, fetch the object's history, return parsed samples."""
        if not self._logged_in:
            self.login()
        self._throttle()
        body = self._open(history_url(norad, since))
        self._last_query = time.time()
        self._query_times.append(self._last_query)
        low = (body or "").strip().lower()
        if low.startswith("<!doctype") or low.startswith("<html"):
            raise SpaceTrackError("Space-Track returned HTML (session expired?)")
        return parse_history_csv(body)


# ---------------------------------------------------------------------------
# Derived views (ported from CardSat 0.9.75's SCR_STHIST)
# ---------------------------------------------------------------------------
# The archive is more useful differentiated than raw: the *rate* of change shows
# drag and manoeuvres directly, and asking whether the rate itself has changed
# is what separates "decaying steadily" from "something happened in 2019".

def rate_series(samples, column, per="year"):
    """Rate of change of one column, as (times, rates).

    Differentiates consecutive populated samples. Pairs closer than an hour are
    skipped: the archive holds several element sets per day and dividing by a
    near-zero interval manufactures enormous spurious rates.
    """
    ts, vs = series(samples, column)
    scale = {"day": 86400.0, "year": 86400.0 * 365.25}.get(per, 86400.0 * 365.25)
    out_t, out_r = [], []
    for i in range(1, len(ts)):
        dt = ts[i] - ts[i - 1]
        if dt < 3600.0:
            continue
        out_t.append(0.5 * (ts[i] + ts[i - 1]))
        out_r.append((vs[i] - vs[i - 1]) / dt * scale)
    return out_t, out_r


def _median(values):
    s = sorted(values)
    return s[len(s) // 2] if s else 0.0


def analyse_rate(samples, column, per="year"):
    """Has the rate of change itself changed? Returns a dict, or None.

    Splits the record at the **midpoint of the time axis**, not of the sample
    count: a sparse 1970s archive and a dense modern one would otherwise let the
    modern era dominate both halves. Fits rate against time for the
    acceleration, and flags jumps against a median-|rate| baseline.
    """
    ts, rr = rate_series(samples, column, per)
    if len(rr) < 4:
        return None
    t0, t1 = ts[0], ts[-1]
    tmid = 0.5 * (t0 + t1)
    early = [r for t, r in zip(ts, rr) if t < tmid]
    late = [r for t, r in zip(ts, rr) if t >= tmid]
    e_mean = sum(early) / len(early) if early else 0.0
    l_mean = sum(late) / len(late) if late else 0.0

    # linear fit of rate vs time -> acceleration of change, per year
    days = [(t - t0) / 86400.0 for t in ts]
    n = len(rr)
    sx = sum(days)
    sy = sum(rr)
    sxx = sum(d * d for d in days)
    sxy = sum(d * r for d, r in zip(days, rr))
    den = n * sxx - sx * sx
    accel = ((n * sxy - sx * sy) / den * 365.25) if den else 0.0

    abs_r = [abs(r) for r in rr]
    med_abs = _median(abs_r)
    mean_abs = sum(abs_r) / n
    # A satellite that sat perfectly still for years has a median |rate| of
    # zero, which would disable the detector at exactly the moment its one big
    # manoeuvre arrived. Fall back to the mean.
    base = med_abs if med_abs > 1e-12 else mean_abs
    jumps = [(t, r) for t, r in zip(ts, rr)
             if base > 1e-12 and abs(r) > 5.0 * base]
    peak_i = max(range(n), key=lambda i: abs(rr[i]))

    # Verdict. A sign flip outranks a ratio, and a near-zero era outranks both:
    # "early 0, late large" must not read as "roughly steady (0.00x)".
    sig = mean_abs * 0.1 if mean_abs > 1e-12 else 1e-12
    e_zero, l_zero = abs(e_mean) < sig, abs(l_mean) < sig
    flip = (not e_zero and not l_zero and (e_mean < 0) != (l_mean < 0))
    ratio = (abs(l_mean) / abs(e_mean)) if not e_zero else 0.0
    if e_zero and not l_zero:
        verdict = "NEW trend developed lately"
    elif l_zero and not e_zero:
        verdict = "trend has largely ceased"
    elif e_zero and l_zero:
        verdict = "little change in either era"
    elif flip:
        verdict = "direction REVERSED between eras"
    elif ratio >= 1.5:
        verdict = "change is %.1fx FASTER lately" % ratio
    elif ratio <= 0.67 and ratio > 0:
        verdict = "change is %.1fx slower lately" % (1.0 / ratio)
    else:
        verdict = "rate roughly steady (%.2fx)" % ratio
    return {
        "n": n, "early_mean": e_mean, "late_mean": l_mean,
        "ratio": ratio, "reversed": flip,
        "accel_per_year": accel,
        "median_abs": med_abs, "mean_abs": mean_abs,
        "jumps": jumps, "n_jumps": len(jumps),
        "peak_rate": rr[peak_i], "peak_time": ts[peak_i],
        "verdict": verdict,
        "t_first": t0, "t_last": t1,
    }


def window(samples, lo_frac=0.0, hi_frac=1.0):
    """Samples inside a fractional slice of the time axis (zoom/pan support)."""
    if not samples:
        return []
    t0, t1 = samples[0]["epoch"], samples[-1]["epoch"]
    span = t1 - t0
    if span <= 0:
        return list(samples)
    a = t0 + span * max(0.0, min(1.0, lo_frac))
    b = t0 + span * max(0.0, min(1.0, hi_frac))
    if b < a:
        a, b = b, a
    return [s for s in samples if a <= s["epoch"] <= b]
