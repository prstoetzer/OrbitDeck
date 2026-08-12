"""orbitdeck.engine.muf - HF maximum usable frequency to world regions.

Implements **MINIMUF-3.5** (Rose/Martin, the classic short-path MUF estimator)
and applies it from your QTH to a set of world regions, so you can see at a
glance which bands are open where.

Ported from CardSat 0.9.75. The algorithm is transcribed structurally from the
published MINIMUF-3.5 BASIC - the cryptic variable names (K1, G0, Y1...) are
kept deliberately so it stays checkable line-by-line against the reference
rather than being "tidied" into something unverifiable.

Caveats worth stating: MINIMUF is a monthly-median model driven by sunspot
number, not a real-time ionosonde. It is weakest on very short (<~800 km) and
antipodal paths, says nothing about absorption, and gives the *maximum usable*
frequency - the practical working frequency is nearer 85% of it.
"""

import math

D2R = math.pi / 180.0
PIC = 3.141593
P0C = 1.570796

# Region centres. NOTE: longitudes here are **west-positive**, matching the
# MINIMUF convention; convert when handing them to normal east-positive code.
REGIONS = [
    ("W Europe", 50.0, -5.0), ("E Europe", 52.0, -21.0),
    ("Scandinavia", 60.0, -18.0), ("Iceland", 64.0, 22.0),
    ("Mediterranean", 40.0, -15.0), ("W Africa", 10.0, 2.0),
    ("N Africa", 30.0, -5.0), ("E Africa", 1.0, -37.0),
    ("S Africa", -26.0, -28.0), ("Middle East", 30.0, -45.0),
    ("Russia/C Asia", 55.0, -83.0), ("S Asia", 20.0, -78.0),
    ("China", 35.0, -116.0), ("Japan", 36.0, -140.0),
    ("SE Asia", 1.0, -104.0), ("Oceania", -18.0, -178.0),
    ("Australia", -34.0, -151.0), ("N America E", 40.0, 74.0),
    ("N America W", 37.0, 122.0), ("Caribbean", 18.0, 66.0),
    ("C America", 15.0, 90.0), ("S America N", 4.0, 74.0),
    ("S America S", -34.0, 58.0), ("Arctic", 80.0, 0.0),
]

WORKABLE_FRACTION = 0.85      # rule of thumb: work up to ~85% of the MUF


def _sgn(x):
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


def _clamp1(x):
    return -1.0 if x < -1 else (1.0 if x > 1 else x)


def minimuf_mhz(lat1, wlon1, lat2, wlon2, month, day, ut_hours, ssn):
    """MINIMUF-3.5 MUF in MHz for one path.

    Latitudes and longitudes in **radians**, longitudes **west-positive**.
    ``month`` 1-12, ``day`` 1-31, ``ut_hours`` decimal UTC, ``ssn`` sunspot
    number. Result is clamped to 2-32 MHz as in the original.
    """
    L1, W1, L2, W2 = lat1, wlon1, lat2, wlon2
    M0, D6, T5, S9 = month, day, ut_hours, ssn

    ft = (math.sin(L1) * math.sin(L2)
          + math.cos(L1) * math.cos(L2) * math.cos(W2 - W1))
    dist = math.acos(_clamp1(ft))
    K6 = max(1.0, 1.59 * dist)
    P, Q = math.sin(L2), math.cos(L2)
    if abs(Q) < 1e-12 or abs(math.sin(dist)) < 1e-12:
        A = 0.0
    else:
        A = (math.sin(L1) - P * math.cos(dist)) / (Q * math.sin(dist))
    Y1 = 0.0172 * (10 + (M0 - 1) * 30.4 + D6)
    Y2 = 0.409 * math.cos(Y1)
    ft = min(P0C, 2.5 * dist / K6)
    ft = math.sin(ft)
    M9 = 1 + 2.5 * ft * math.sqrt(ft)
    J9 = 100.0

    step = abs(0.9999 - 1.0 / K6)
    if step <= 0:
        step = 1.0
    K1 = 1.0 / (2 * K6)
    while K1 <= 1 - 1.0 / (2 * K6) + 1e-12:
        gt = dist * K1
        ft = P * math.cos(gt) + Q * math.sin(gt) * A
        ft = _clamp1(ft)
        Y3 = P0C - math.acos(ft)
        denom = Q * math.sqrt(max(1e-12, 1 - ft * ft))
        ft2 = (math.cos(gt) - ft * P) / denom if abs(denom) > 1e-12 else 0.0
        ft2 = _clamp1(ft2)
        ft2 = W2 + _sgn(math.sin(W1 - W2)) * math.acos(ft2)
        if ft2 < 0:
            ft2 += 2 * PIC
        if ft2 >= 2 * PIC:
            ft2 -= 2 * PIC
        ft2 = 3.82 * ft2 + 12 + 0.13 * (math.sin(Y1) + 1.2 * math.sin(2 * Y1))
        K8 = ft2 - 12 * (1 + _sgn(ft2 - 24)) * _sgn(abs(ft2 - 24))

        if math.cos(Y3 + Y2) <= -0.26:
            K9 = 0.0
            G0 = 0.0
        else:
            f = ((-0.26 + math.sin(Y2) * math.sin(Y3))
                 / (math.cos(Y2) * math.cos(Y3) + 0.001))
            K9 = 12 - math.atan(f / math.sqrt(abs(1 - f * f))) * 7.639437
            T = K8 - K9 / 2 + 12 * (1 - _sgn(K8 - K9 / 2)) * _sgn(abs(K8 - K9 / 2))
            T4 = K8 + K9 / 2 - 12 * (1 + _sgn(K8 + K9 / 2 - 24)) * _sgn(
                abs(K8 + K9 / 2 - 24))
            C0 = abs(math.cos(Y3 + Y2))
            T9 = max(0.1, 9.7 * (C0 ** 9.6))
            G8 = PIC * T9 / K9 if K9 else 0.0
            if ((T4 < T and (T5 - T4) * (T - T5) > 0.0)
                    or (T4 >= T and (T5 - T) * (T4 - T5) <= 0)):
                f = T5 + 12 * (1 + _sgn(T4 - T5)) * _sgn(abs(T4 - T5))
                f = (T4 - f) / 2
                G0 = (C0 * (G8 * (math.exp(-K9 / T9) + 1)) * math.exp(f)
                      / (1 + G8 * G8))
            else:
                f = T5 + 12 * (1 + _sgn(T - T5)) * _sgn(abs(T - T5))
                gt2 = PIC * (f - T) / K9 if K9 else 0.0
                f2 = (T - f) / T9
                G0 = (C0 * (math.sin(gt2) + G8 * (math.exp(f2) - math.cos(gt2)))
                      / (1 + G8 * G8))
                floor_ = (C0 * (G8 * (math.exp(-K9 / T9) + 1))
                          * math.exp((K9 - 24) / 2) / (1 + G8 * G8))
                G0 = max(G0, floor_)

        v = (1 + S9 / 250.0) * M9 * math.sqrt(6 + 58 * math.sqrt(max(0.0, G0)))
        v *= 1 - 0.1 * math.exp((K9 - 24) / 3)
        v *= 1 + 0.1 * (1 - _sgn(L1) * _sgn(L2))
        v *= 1 - 0.1 * (1 + _sgn(abs(math.sin(Y3)) - math.cos(Y3)))
        J9 = min(J9, v)
        K1 += step

    return 2.0 if J9 < 2 else (32.0 if J9 > 32 else J9)


def workable_band(muf_mhz):
    """Best band label for a MUF, using the ~85%-of-MUF rule of thumb."""
    w = WORKABLE_FRACTION * muf_mhz
    for limit, name in ((28, "10m"), (24, "12m"), (21, "15m"), (18, "17m"),
                        (14, "20m"), (10, "30m"), (7, "40m")):
        if w >= limit:
            return name
    return "80m"


def muf_band_colour_key(muf_mhz):
    """Coarse quality bucket: 'low', 'fair', 'good' or 'high'."""
    if muf_mhz < 10:
        return "low"
    if muf_mhz < 17:
        return "fair"
    if muf_mhz < 24:
        return "good"
    return "high"


def great_circle(lat1, lon1, lat2, lon2, re_km=6371.0):
    """Distance (km) and initial bearing (deg) - east-positive longitudes."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    dist = 2 * re_km * math.asin(min(1.0, math.sqrt(a)))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return dist, (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def muf_to_regions(lat, lon, when, ssn, regions=None):
    """MUF from a QTH (east-positive lon) to each region.

    Returns a list of dicts: {name, muf_mhz, band, quality, distance_km,
    bearing_deg}, ordered as REGIONS.
    """
    import time as _t
    tm = _t.gmtime(when)
    month, day = tm.tm_mon, tm.tm_mday
    ut = tm.tm_hour + tm.tm_min / 60.0
    q_lat = lat * D2R
    q_wlon = -lon * D2R                      # east-positive -> west-positive
    out = []
    for name, r_lat, r_wlon in (regions or REGIONS):
        muf = minimuf_mhz(q_lat, q_wlon, r_lat * D2R, r_wlon * D2R,
                          month, day, ut, ssn)
        dist, brg = great_circle(lat, lon, r_lat, -r_wlon)
        out.append({
            "name": name, "muf_mhz": muf, "band": workable_band(muf),
            "quality": muf_band_colour_key(muf),
            "distance_km": dist, "bearing_deg": brg,
            "workable_mhz": WORKABLE_FRACTION * muf,
        })
    return out



def ssn_from_flux(f107):
    """Approximate sunspot number from F10.7 solar flux.

    The classic inverse of the Covington relation used across ham propagation
    software: SSN = 1.61 * (F10.7 - 67.0), floored at zero. It is a
    monthly-scale statistical fit, not an identity - daily flux and daily SSN
    scatter widely around it - so callers should label a value derived this way
    rather than present it as observed.
    """
    try:
        f = float(f107)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, 1.61 * (f - 67.0))


def muf_to_dxcc(lat, lon, when, ssn, prefix, max_results=8):
    """MUF from a QTH to a named DXCC entity.

    The region table answers "how is Europe"; an operator asks "can I work
    ZS right now". Matches on prefix or entity name, and returns a row per
    match so an ambiguous search still shows what it found.
    """
    from ..data.dxcc import DXCC
    q = (prefix or "").strip().upper()
    if not q:
        return []
    hits = []
    for pfx, (name, dlat, dlon) in DXCC.items():
        if pfx.upper() == q or q in name.upper():
            hits.append((pfx, name, dlat, dlon))
    # exact prefix first, then name matches, so "ZS" beats "ZS8"
    hits.sort(key=lambda h: (h[0].upper() != q, h[0]))
    out = []
    import time as _t
    tm = _t.gmtime(when)
    ut = tm.tm_hour + tm.tm_min / 60.0
    for pfx, name, dlat, dlon in hits[:max_results]:
        muf = minimuf_mhz(lat * D2R, -lon * D2R, dlat * D2R, -dlon * D2R,
                          tm.tm_mon, tm.tm_mday, ut, ssn)
        dist, brg = great_circle(lat, lon, dlat, dlon)
        out.append({
            "prefix": pfx, "name": name,
            "muf_mhz": muf, "band": workable_band(muf),
            "quality": muf_band_colour_key(muf),
            "workable_mhz": WORKABLE_FRACTION * muf,
            "distance_km": dist, "bearing_deg": brg,
        })
    return out


def muf_grid(lat, lon, when, ssn, lat_step=15.0, lon_step=15.0):
    """MUF from the QTH to a grid of points, for a shaded world map.

    The region table gives 24 representative centres; a grid shows the *shape*
    of the opening - where the band edge actually falls - which is what a map
    is for. Coarse by default because MINIMUF is a per-path model and the cost
    grows with the square of the resolution.

    Returns (lats, lons, values) with values[i][j] the MUF in MHz, or None
    where the model cannot answer.
    """
    import time as _t
    tm = _t.gmtime(when)
    ut = tm.tm_hour + tm.tm_min / 60.0
    lats, lons, vals = [], [], []
    la = -75.0
    while la <= 75.0 + 1e-9:
        lats.append(la)
        la += lat_step
    lo = -180.0
    while lo <= 180.0 - 1e-9:
        lons.append(lo)
        lo += lon_step
    for la in lats:
        row = []
        for lo in lons:
            try:
                m = minimuf_mhz(lat * D2R, -lon * D2R, la * D2R, -lo * D2R,
                                tm.tm_mon, tm.tm_mday, ut, ssn)
            except Exception:
                m = None
            row.append(m)
        vals.append(row)
    return lats, lons, vals
