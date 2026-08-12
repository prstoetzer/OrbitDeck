"""orbitdeck.engine.terrain - terrain path profile for a terrestrial link.

Samples ground elevation along the great-circle path between two points (using
Open-Meteo's public elevation API), finds the highest obstruction, and decides
whether a straight radio path between two antenna heights clears it - a quick
planning sketch for a terrestrial VHF/UHF/microwave hop, not a survey.

The great-circle sampling and the line-of-sight / Fresnel clearance test are
pure math (network-free, unit-testable); only the elevation fetch touches the
network, and it degrades gracefully.
"""

import math

ELEVATION_API = "https://api.open-meteo.com/v1/elevation"
RE_KM = 6371.0


def great_circle(lat1, lon1, lat2, lon2):
    """Distance (km) and initial bearing (deg) between two lat/lon points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    dphi = p2 - p1
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2)
    dist = 2 * RE_KM * math.asin(min(1.0, math.sqrt(a)))
    y = math.sin(dlon) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    brg = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return dist, brg


def sample_points(lat1, lon1, lat2, lon2, n=12):
    """``n`` lat/lon points evenly spaced along the great circle (slerp),
    inclusive of both endpoints. Returns (points, dist_km) where points is a list
    of (lat, lon) and each sample's along-path distance is i/(n-1)*dist_km."""
    dist, _brg = great_circle(lat1, lon1, lat2, lon2)
    p1, l1 = math.radians(lat1), math.radians(lon1)
    p2, l2 = math.radians(lat2), math.radians(lon2)
    d = dist / RE_KM
    sd = math.sin(d)
    pts = []
    for i in range(n):
        f = i / (n - 1)
        if sd < 1e-9:
            la, lo = p1, l1
        else:
            A = math.sin((1 - f) * d) / sd
            B = math.sin(f * d) / sd
            x = A * math.cos(p1) * math.cos(l1) + B * math.cos(p2) * math.cos(l2)
            y = A * math.cos(p1) * math.sin(l1) + B * math.cos(p2) * math.sin(l2)
            z = A * math.sin(p1) + B * math.sin(p2)
            la = math.atan2(z, math.hypot(x, y))
            lo = math.atan2(y, x)
        pts.append((math.degrees(la), math.degrees(lo)))
    return pts, dist


def analyze_profile(elevations, dist_km, tx_haat_m=10.0, rx_haat_m=10.0,
                    freq_mhz=146.0):
    """Decide whether a straight LOS path clears the terrain between endpoints.

    ``elevations`` is the sampled ground height (m) at each point from
    sample_points (endpoints included). Antenna heights are added above the
    ground at each end. Returns a dict:
        max_terrain_m, max_at_km, clear (bool), worst_clearance_m,
        fresnel_r_m (first-zone radius at the worst point).
    """
    n = len(elevations)
    if n < 2 or dist_km <= 0:
        return {"clear": True, "max_terrain_m": 0.0, "max_at_km": 0.0,
                "worst_clearance_m": 0.0, "fresnel_r_m": 0.0}
    tx_h = elevations[0] + tx_haat_m
    rx_h = elevations[-1] + rx_haat_m
    worst = 1e18
    max_terr = -1e18
    max_at = 0.0
    fres_at_worst = 0.0
    for i in range(1, n - 1):
        f = i / (n - 1)
        d1 = f * dist_km
        d2 = dist_km - d1
        # straight line-of-sight height at this point, with Earth-curvature bulge
        los = tx_h + (rx_h - tx_h) * f
        bulge_m = (d1 * d2) / (2 * (4.0 / 3.0) * RE_KM) * 1000.0  # 4/3 Earth
        terr = elevations[i] + bulge_m
        clearance = los - terr
        # first Fresnel-zone radius (m): 17.31*sqrt(d1*d2/(f_GHz*D))
        f_ghz = freq_mhz / 1000.0
        if f_ghz > 0 and dist_km > 0:
            fr = 17.31 * math.sqrt((d1 * d2) / (f_ghz * dist_km))
        else:
            fr = 0.0
        if clearance < worst:
            worst = clearance
            fres_at_worst = fr
        if elevations[i] > max_terr:
            max_terr = elevations[i]
            max_at = d1
    # "clear" requires 60% first-Fresnel clearance over the worst obstruction
    clear = worst >= 0.6 * fres_at_worst
    return {
        "max_terrain_m": max_terr,
        "max_at_km": max_at,
        "clear": clear,
        "worst_clearance_m": worst,
        "fresnel_r_m": fres_at_worst,
    }


def elevation_url(points):
    """Build the Open-Meteo elevation request URL for a list of (lat, lon)."""
    lats = ",".join("%.4f" % p[0] for p in points)
    lons = ",".join("%.4f" % p[1] for p in points)
    return "%s?latitude=%s&longitude=%s" % (ELEVATION_API, lats, lons)


def parse_elevations(body):
    """Pull the ``elevation`` array out of an Open-Meteo JSON response."""
    import json
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return []
    ev = data.get("elevation") if isinstance(data, dict) else None
    if not isinstance(ev, list):
        return []
    out = []
    for x in ev:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def fetch_profile(http_get, lat1, lon1, lat2, lon2, n=12,
                  tx_haat_m=10.0, rx_haat_m=10.0, freq_mhz=146.0):
    """Full terrain-profile fetch: sample -> fetch elevations -> analyze.

    Returns (analysis_dict, elevations, dist_km). On a fetch/parse failure,
    elevations is [] and analysis carries the endpoints only.
    """
    pts, dist = sample_points(lat1, lon1, lat2, lon2, n)
    try:
        body = http_get(elevation_url(pts), timeout=15)
        elev = parse_elevations(body)
    except Exception:
        elev = []
    if len(elev) < 2:
        return ({"clear": True, "max_terrain_m": 0.0, "max_at_km": 0.0,
                 "worst_clearance_m": 0.0, "fresnel_r_m": 0.0}, [], dist)
    analysis = analyze_profile(elev, dist, tx_haat_m, rx_haat_m, freq_mhz)
    return analysis, elev, dist


def terrain_los_rows(path_km=30.0, obstruction_m=200.0, obstruction_at_km=15.0,
                     tx_haat_m=10.0, rx_haat_m=10.0, freq_mhz=146.0,
                     tx_ground_m=100.0, rx_ground_m=100.0):
    """Manual-input terrain LOS check for the Tools hub (no network).

    Given the single worst obstruction along a path (height and where), decide
    whether the straight radio path clears it with 60% Fresnel margin. This is
    the offline sibling of fetch_profile(), for when you already know the ridge.
    """
    if path_km <= 0 or not (0 < obstruction_at_km < path_km):
        return [("error", "need 0 < obstruction_at < path", "")]
    tx_h = tx_ground_m + tx_haat_m
    rx_h = rx_ground_m + rx_haat_m
    f = obstruction_at_km / path_km
    d1, d2 = obstruction_at_km, path_km - obstruction_at_km
    los = tx_h + (rx_h - tx_h) * f
    bulge = (d1 * d2) / (2 * (4.0 / 3.0) * RE_KM) * 1000.0
    terr = obstruction_m + bulge
    clearance = los - terr
    f_ghz = freq_mhz / 1000.0
    fr = 17.31 * math.sqrt((d1 * d2) / (f_ghz * path_km)) if f_ghz > 0 else 0.0
    clear = clearance >= 0.6 * fr
    verdict = ("clear (60% Fresnel)" if clear else
               ("grazing" if clearance >= 0 else "blocked"))
    return [
        ("LOS height", "%.0f m" % los, "at obstruction"),
        ("Obstruction", "%.0f m" % terr, "incl Earth bulge"),
        ("Clearance", "%.0f m" % clearance, ""),
        ("Fresnel F1", "%.0f m" % fr, "need 60%%: %.0f m" % (0.6 * fr)),
        ("Earth bulge", "%.0f m" % bulge, "4/3 Earth"),
        ("Verdict", verdict, ""),
    ]
