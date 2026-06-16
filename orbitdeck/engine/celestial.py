"""celestial.py - planets, cosmic radio sources, EME geometry, and
satellite-to-satellite visibility windows.

Builds on the same time/GMST conventions as predict.py. Positions are
low-precision (good to a fraction of a degree for planets, exact for the
fixed-coordinate radio sources) -- enough for antenna pointing and EME planning,
not for ephemeris-grade work.
"""

import math

DEG = math.pi / 180.0
RE_KM = 6378.135
AU_KM = 149_597_870.7
MOON_DIST_KM = 384_400.0
C_LIGHT = 299_792_458.0


def jd_of(unix):
    return unix / 86400.0 + 2440587.5


def _gmst_rad(jd):
    # match predict.py's GMST
    T = (jd - 2451545.0) / 36525.0
    gmst = (280.46061837 + 360.98564736629 * (jd - 2451545.0)
            + 0.000387933 * T * T - T * T * T / 38710000.0)
    return math.radians(gmst % 360.0)


def radec_to_azel(ra_deg, dec_deg, lat, lon, t):
    """Convert equatorial RA/Dec (degrees, J2000-ish) to local az/el for an
    observer at lat/lon (deg) at unix time t."""
    jd = jd_of(t)
    th = _gmst_rad(jd)
    lst = th + lon * DEG                      # local sidereal time (rad)
    ha = lst - ra_deg * DEG                   # hour angle
    dec = dec_deg * DEG
    slat, clat = math.sin(lat * DEG), math.cos(lat * DEG)
    sdec, cdec = math.sin(dec), math.cos(dec)
    sha, cha = math.sin(ha), math.cos(ha)
    el = math.asin(slat * sdec + clat * cdec * cha)
    az = math.atan2(-cdec * sha,
                    cdec * cha * slat - sdec * clat) % (2 * math.pi)
    # the atan2 form above yields az measured from south; convert to from-north
    az = (az + math.pi) % (2 * math.pi)
    return math.degrees(az), math.degrees(el)


# ---------------------------------------------------------------------------
# Planets (low-precision heliocentric Keplerian elements, J2000)
# ---------------------------------------------------------------------------
# elements: a (AU), e, I, L, longPeri, longNode (deg) and their per-century
# rates. From the JPL low-precision formulae (Standish). Good to ~arcminutes
# over 1800-2050.
_PLANETS = {
    "Mercury": (0.38709927, 0.20563593, 7.00497902, 252.25032350,
                77.45779628, 48.33076593,
                0.00000037, 0.00001906, -0.00594749, 149472.67411175,
                0.16047689, -0.12534081),
    "Venus": (0.72333566, 0.00677672, 3.39467605, 181.97909950,
              131.60246718, 76.67984255,
              0.00000390, -0.00004107, -0.00078890, 58517.81538729,
              0.00268329, -0.27769418),
    "Mars": (1.52371034, 0.09339410, 1.84969142, -4.55343205,
             -23.94362959, 49.55953891,
             0.00001847, 0.00007882, -0.00813131, 19140.30268499,
             0.44441088, -0.29257343),
    "Jupiter": (5.20288700, 0.04838624, 1.30439695, 34.39644051,
                14.72847983, 100.47390909,
                -0.00011607, -0.00013253, -0.00183714, 3034.74612775,
                0.21252668, 0.20469106),
    "Saturn": (9.53667594, 0.05386179, 2.48599187, 49.95424423,
               92.59887831, 113.66242448,
               -0.00125060, -0.00050991, 0.00193609, 1222.49362201,
               -0.41897216, -0.28867794),
}

# Earth's elements (for the heliocentric->geocentric step)
_EARTH = (1.00000261, 0.01671123, -0.00001531, 100.46457166,
          102.93768193, 0.0,
          0.00000562, -0.00004392, -0.01294668, 35999.37244981,
          0.32327364, 0.0)


def _helio_xyz(el, t):
    jd = jd_of(t)
    T = (jd - 2451545.0) / 36525.0
    a = el[0] + el[6] * T
    e = el[1] + el[7] * T
    I = (el[2] + el[8] * T) * DEG
    L = (el[3] + el[9] * T)
    wbar = (el[4] + el[10] * T)
    Omega = (el[5] + el[11] * T)
    M = math.radians((L - wbar) % 360.0)
    w = math.radians(wbar - Omega)
    Omega = math.radians(Omega)
    # solve Kepler
    E = M
    for _ in range(8):
        E = E - (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    xv = a * (math.cos(E) - e)
    yv = a * (math.sqrt(1 - e * e) * math.sin(E))
    # position in orbital plane -> ecliptic
    xh = (xv * (math.cos(w) * math.cos(Omega)
                - math.sin(w) * math.sin(Omega) * math.cos(I))
          + yv * (-math.sin(w) * math.cos(Omega)
                  - math.cos(w) * math.sin(Omega) * math.cos(I)))
    yh = (xv * (math.cos(w) * math.sin(Omega)
                + math.sin(w) * math.cos(Omega) * math.cos(I))
          + yv * (-math.sin(w) * math.sin(Omega)
                  + math.cos(w) * math.cos(Omega) * math.cos(I)))
    zh = (xv * (math.sin(w) * math.sin(I))
          + yv * (math.cos(w) * math.sin(I)))
    return xh, yh, zh


def planet_radec(name, t):
    """Geocentric RA/Dec (deg) of a planet at unix time t."""
    if name not in _PLANETS:
        return None
    px, py, pz = _helio_xyz(_PLANETS[name], t)
    ex, ey, ez = _helio_xyz(_EARTH, t)
    # geocentric ecliptic
    gx, gy, gz = px - ex, py - ey, pz - ez
    eps = math.radians(23.43928)
    # ecliptic -> equatorial
    xq = gx
    yq = gy * math.cos(eps) - gz * math.sin(eps)
    zq = gy * math.sin(eps) + gz * math.cos(eps)
    ra = math.degrees(math.atan2(yq, xq)) % 360.0
    dec = math.degrees(math.atan2(zq, math.hypot(xq, yq)))
    return ra, dec


def planet_azel(name, lat, lon, t):
    rd = planet_radec(name, t)
    if rd is None:
        return None
    return radec_to_azel(rd[0], rd[1], lat, lon, t)


# ---------------------------------------------------------------------------
# Cosmic radio sources (fixed RA/Dec, J2000) used for antenna calibration and
# radio astronomy. RA in degrees, Dec in degrees.
# ---------------------------------------------------------------------------
RADIO_SOURCES = {
    "Sun": None,                 # handled specially (moving)
    "Cassiopeia A": (350.866, 58.811),
    "Cygnus A": (299.868, 40.734),
    "Taurus A (Crab)": (83.633, 22.014),
    "Virgo A (M87)": (187.706, 12.391),
    "Sagittarius A* (GC)": (266.417, -29.008),
    "Orion A": (83.809, -5.389),
    "Centaurus A": (201.365, -43.019),
    "Fornax A": (50.674, -37.208),
}

# "Cold sky" is just a direction with minimal background -- a high-galactic-
# latitude reference point. We expose a representative one.
COLD_SKY_RADEC = (192.0, 27.4)   # near the north galactic pole region


def source_azel(name, lat, lon, t):
    rd = RADIO_SOURCES.get(name)
    if rd is None:
        return None
    return radec_to_azel(rd[0], rd[1], lat, lon, t)


# ---------------------------------------------------------------------------
# EME (Earth-Moon-Earth) geometry
# ---------------------------------------------------------------------------

def _moon_eci_unit(jd):
    d = jd - 2451545.0
    L = math.radians((218.316 + 13.176396 * d) % 360)
    M = math.radians((134.963 + 13.064993 * d) % 360)
    F = math.radians((93.272 + 13.229350 * d) % 360)
    lon = L + math.radians(6.289) * math.sin(M)
    lat = math.radians(5.128) * math.sin(F)
    eps = math.radians(23.439)
    x = math.cos(lat) * math.cos(lon)
    y = (math.cos(eps) * math.cos(lat) * math.sin(lon)
         - math.sin(eps) * math.sin(lat))
    z = (math.sin(eps) * math.cos(lat) * math.sin(lon)
         + math.cos(eps) * math.sin(lat))
    return x, y, z


def moon_azel(lat, lon, t):
    jd = jd_of(t)
    mx, my, mz = _moon_eci_unit(jd)
    th = _gmst_rad(jd)
    lst = th + lon * DEG
    ss, cs = math.sin(lst), math.cos(lst)
    slat, clat = math.sin(lat * DEG), math.cos(lat * DEG)
    e = -ss * mx + cs * my
    n = -slat * cs * mx - slat * ss * my + clat * mz
    u = clat * cs * mx + clat * ss * my + slat * mz
    el = math.degrees(math.atan2(u, math.hypot(e, n)))
    az = math.degrees(math.atan2(e, n)) % 360
    return az, el


def moon_distance_km(t):
    """Approximate Earth-Moon distance (km), varying with anomaly."""
    d = jd_of(t) - 2451545.0
    M = math.radians((134.963 + 13.064993 * d) % 360)
    # leading terms of the distance series (km)
    return 385000.56 - 20905.0 * math.cos(M)


def eme_path_loss_db(freq_hz, t):
    """Total EME path loss (dB): the round-trip Earth->Moon->Earth path.

    This is the two-way free-space loss reduced by the Moon's effectiveness as
    a passive reflector. The Moon is physically enormous, so it reflects far
    more than an isotropic target would; the net effect is an effective
    reflection gain that brings the ~375 dB raw round-trip free-space figure
    (at 144 MHz) down to the ~252 dB commonly quoted for 2 m EME. We model the
    reflector gain from the Moon's radar cross-section relative to an isotropic
    target at the lunar distance.
    """
    dist_m = moon_distance_km(t) * 1000.0
    wl = C_LIGHT / freq_hz
    # one-way free space loss (to the Moon)
    fspl_one = 20 * math.log10(4 * math.pi * dist_m / wl)
    # Moon as a reflector: radar cross-section sigma = rho * pi * Rm^2 with
    # rho ~ 0.065 (radar albedo). Its gain over isotropic at the receiver is
    # G_moon = 4*pi*sigma / wl^2 ... but the standard passive-reflector result
    # for a large smooth sphere reduces the round trip to:
    #   L_total = 2*FSPL_one - G_reflector
    # where G_reflector = 10*log10(4*pi*A_eff / wl^2) and A_eff = rho*pi*Rm^2.
    Rm = 1_737_400.0                      # lunar radius, m
    rho = 0.065                           # radar albedo (~6.5%)
    a_eff = rho * math.pi * Rm * Rm
    g_reflector = 10 * math.log10(4 * math.pi * a_eff / (wl * wl))
    return 2 * fspl_one - g_reflector


def eme_doppler_hz(freq_hz, lat, lon, t, dt=1.0):
    """Self-echo EME Doppler (Hz): the shift on your own signal returning from
    the Moon, from the rate of change of the round-trip path length as the Moon
    moves relative to your station. Positive = approaching (up-shift)."""
    r0 = _moon_topocentric_range_km(lat, lon, t)
    r1 = _moon_topocentric_range_km(lat, lon, t + dt)
    range_rate = (r1 - r0) * 1000.0 / dt     # m/s, + receding
    # round trip => 2x; up-shift when approaching (range_rate < 0)
    return -2.0 * freq_hz * (range_rate / C_LIGHT)


def _moon_topocentric_range_km(lat, lon, t):
    """Distance from the observer to the Moon (km), accounting for the
    observer's offset from Earth centre."""
    jd = jd_of(t)
    mx, my, mz = _moon_eci_unit(jd)
    dist = moon_distance_km(t)
    moon = (mx * dist, my * dist, mz * dist)
    # observer ECI (approx, spherical Earth) in the same TEME-ish frame
    th = _gmst_rad(jd)
    lst = th + lon * DEG
    clat = math.cos(lat * DEG)
    ox = RE_KM * clat * math.cos(lst)
    oy = RE_KM * clat * math.sin(lst)
    oz = RE_KM * math.sin(lat * DEG)
    dx, dy, dz = moon[0] - ox, moon[1] - oy, moon[2] - oz
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def eme_window(lat1, lon1, lat2, lon2, t, hours=24.0, step_s=300.0,
               min_el=0.0):
    """Common-Moon-visibility windows between two stations: the times when the
    Moon is above ``min_el`` at BOTH stations (the requirement for an EME QSO).
    Returns a list of (start, end) unix tuples."""
    end = t + hours * 3600.0
    windows = []
    cur = None
    tt = t
    while tt <= end:
        e1 = moon_azel(lat1, lon1, tt)[1]
        e2 = moon_azel(lat2, lon2, tt)[1]
        ok = e1 >= min_el and e2 >= min_el
        if ok and cur is None:
            cur = [tt, tt]
        elif ok:
            cur[1] = tt
        elif cur is not None:
            windows.append(tuple(cur))
            cur = None
        tt += step_s
    if cur is not None:
        windows.append(tuple(cur))
    return windows


def sky_temperature_k(galactic_lat_deg=None, freq_mhz=144.0):
    """A coarse sky-background-temperature estimate (K) for EME link planning.
    Cold sky at 144 MHz is ~200 K; the galactic plane / Sun direction is far
    hotter. We return a representative cold-sky value scaled by frequency
    (T ~ f^-2.5), since detailed maps aren't bundled."""
    t_cold_144 = 200.0
    return t_cold_144 * (144.0 / freq_mhz) ** 2.5


# ---------------------------------------------------------------------------
# Satellite-to-satellite mutual visibility windows
# ---------------------------------------------------------------------------

def _los_clear(r1, r2, re_km=RE_KM):
    """True if the chord between two ECI points clears the Earth sphere."""
    d = (r2[0] - r1[0], r2[1] - r1[1], r2[2] - r1[2])
    dd = d[0] * d[0] + d[1] * d[1] + d[2] * d[2]
    if dd == 0:
        return True
    s = -(r1[0] * d[0] + r1[1] * d[1] + r1[2] * d[2]) / dd
    if s <= 0.0 or s >= 1.0:
        return True
    cx = r1[0] + s * d[0]
    cy = r1[1] + s * d[1]
    cz = r1[2] + s * d[2]
    return math.sqrt(cx * cx + cy * cy + cz * cz) > re_km


def sat_to_sat_windows(pred1, pred2, t, hours=24.0, step_s=30.0):
    """Line-of-sight windows between two satellites over [t, t+hours].

    Both predictors must already have their satellite set. Returns a list of
    dicts {start, end, duration_s, min_range_km} where the chord between the two
    spacecraft clears the Earth.
    """
    end = t + hours * 3600.0
    windows = []
    cur = None
    tt = t
    while tt <= end:
        r1, _ = pred1._eci_state(tt)
        r2, _ = pred2._eci_state(tt)
        clear = _los_clear(r1, r2)
        if clear:
            rng = math.sqrt(sum((a - b) ** 2 for a, b in zip(r1, r2)))
            if cur is None:
                cur = {"start": tt, "end": tt, "min_range_km": rng}
            else:
                cur["end"] = tt
                cur["min_range_km"] = min(cur["min_range_km"], rng)
        elif cur is not None:
            cur["duration_s"] = cur["end"] - cur["start"]
            windows.append(cur)
            cur = None
        tt += step_s
    if cur is not None:
        cur["duration_s"] = cur["end"] - cur["start"]
        windows.append(cur)
    return windows
