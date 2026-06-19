"""
us_states.py - representative interior points for each US state + DC.

Used to decide which states fall under a satellite footprint. Each state has one
or more (lat, lon) sample points; the state counts as "workable" when ANY of its
points lies inside the footprint cap. Large states carry several points so
partial coverage is caught; compact states carry one centroid. This mirrors the
intent of CardSat's workable-states screen (which-states-can-work-the-bird) at
footprint scale, without shipping heavy boundary polygons.
"""

# name: list of (lat, lon) interior sample points
US_STATES = {
    "AL": [(32.8, -86.8)],
    "AK": [(64.2, -149.5), (61.2, -150.0), (58.3, -134.4), (66.0, -157.0),
           (70.2, -148.5)],
    "AZ": [(34.3, -111.7), (32.2, -110.9), (35.2, -114.0)],
    "AR": [(34.8, -92.4)],
    "CA": [(38.6, -121.5), (34.1, -118.2), (36.7, -119.8), (40.6, -122.4),
           (32.8, -117.1), (37.8, -122.4)],
    "CO": [(39.0, -105.5), (38.3, -104.6), (40.4, -106.9)],
    "CT": [(41.6, -72.7)],
    "DE": [(39.0, -75.5)],
    "DC": [(38.9, -77.0)],
    "FL": [(28.7, -81.5), (30.4, -84.3), (26.1, -80.2), (25.8, -81.5)],
    "GA": [(32.7, -83.4), (34.0, -84.4)],
    "HI": [(21.3, -157.8), (20.8, -156.3), (19.6, -155.5), (22.1, -159.5)],
    "ID": [(44.4, -114.6), (43.6, -116.2), (47.0, -116.5)],
    "IL": [(40.0, -89.2), (41.8, -87.7)],
    "IN": [(39.9, -86.3)],
    "IA": [(42.0, -93.5)],
    "KS": [(38.5, -98.0)],
    "KY": [(37.5, -85.3)],
    "LA": [(31.0, -92.0), (29.9, -90.1)],
    "ME": [(45.4, -69.2), (43.7, -70.3)],
    "MD": [(39.0, -76.8)],
    "MA": [(42.3, -71.8), (42.0, -70.6)],
    "MI": [(43.3, -84.5), (46.5, -87.5), (42.3, -83.0)],
    "MN": [(46.3, -94.3), (44.9, -93.2), (47.9, -91.5)],
    "MS": [(32.7, -89.7)],
    "MO": [(38.5, -92.5), (39.1, -94.6)],
    "MT": [(47.0, -109.6), (45.8, -111.0), (48.3, -114.2)],
    "NE": [(41.5, -99.7)],
    "NV": [(39.5, -116.9), (36.2, -115.1)],
    "NH": [(43.7, -71.6)],
    "NJ": [(40.1, -74.5)],
    "NM": [(34.4, -106.1), (32.3, -106.7)],
    "NY": [(42.9, -75.5), (40.7, -74.0), (43.0, -78.8)],
    "NC": [(35.5, -79.4), (35.6, -82.6)],
    "ND": [(47.4, -100.3)],
    "OH": [(40.2, -82.8), (41.5, -81.7)],
    "OK": [(35.5, -97.5), (35.4, -99.4)],
    "OR": [(44.0, -120.5), (45.5, -122.7), (42.3, -122.9)],
    "PA": [(40.9, -77.6), (40.0, -75.2), (40.4, -80.0)],
    "RI": [(41.7, -71.5)],
    "SC": [(34.0, -81.0)],
    "SD": [(44.4, -100.2)],
    "TN": [(35.9, -86.4), (35.2, -90.0)],
    "TX": [(31.5, -99.3), (29.4, -98.5), (32.8, -96.8), (29.8, -95.4),
           (31.8, -106.4), (27.5, -97.9), (33.6, -101.9)],
    "UT": [(39.3, -111.7), (40.8, -111.9)],
    "VT": [(44.1, -72.7)],
    "VA": [(37.5, -78.7), (38.8, -77.3), (37.0, -76.4)],
    "WA": [(47.4, -120.5), (47.6, -122.3), (47.7, -117.4)],
    "WV": [(38.6, -80.6)],
    "WI": [(44.6, -89.9), (43.1, -87.9)],
    "WY": [(43.0, -107.6), (41.1, -104.8)],
}


def workable_states(in_footprint):
    """Return sorted list of state codes with at least one point in footprint.

    `in_footprint(lat, lon) -> bool` decides membership for a single point.

    Uses the denser bundled boundary dataset (a ~0.5-deg interior fill per
    state) when available so coverage is detected accurately across each
    state's extent, falling back to the sparse representative city points.
    """
    try:
        from .us_state_boundaries import US_STATE_BOUNDARIES as _PTS
    except Exception:
        _PTS = US_STATES
    out = []
    for code, pts in _PTS.items():
        if any(in_footprint(lat, lon) for (lat, lon) in pts):
            out.append(code)
    return sorted(out)
