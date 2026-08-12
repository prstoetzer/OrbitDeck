"""orbitdeck.engine.skymap - project the star catalog into the local sky.

Turns the bundled star catalog (engine.star_data, from d3-celestial, BSD-3) into
the stars and constellation-line segments currently above the horizon for an
observer, in local az/el. A sky-map screen can then plot these and overlay
satellite positions (which are already az/el from the predictor).
"""

from .celestial import radec_to_azel
from . import star_data as _sd


def visible_stars(lat, lon, t, min_el=0.0, max_mag=5.5):
    """Stars above ``min_el`` now, as (az, el, mag) tuples.

    RA/dec are stored in 0.01 deg; magnitude is encoded as (mag+2)*10.
    """
    out = []
    ra, dec, mag = _sd.STAR_RA, _sd.STAR_DEC, _sd.STAR_MAG
    for i in range(len(ra)):
        m = mag[i] / 10.0 - 2.0
        if m > max_mag:
            continue
        az, el = radec_to_azel(ra[i] / 100.0, dec[i] / 100.0, lat, lon, t)
        if el >= min_el:
            out.append((az, el, m))
    return out


def constellation_segments(lat, lon, t, min_el=0.0):
    """Constellation lines as [(az1, el1, az2, el2), ...] for segments with at
    least one endpoint above ``min_el``. Points are stored as consecutive runs
    (CLIN_RUN gives the length of each polyline)."""
    ra, dec, runs = _sd.CLIN_RA, _sd.CLIN_DEC, _sd.CLIN_RUN
    segs = []
    idx = 0
    for run_len in runs:
        pts = []
        for k in range(run_len):
            j = idx + k
            if j >= len(ra):
                break
            az, el = radec_to_azel(ra[j] / 100.0, dec[j] / 100.0, lat, lon, t)
            pts.append((az, el))
        idx += run_len
        for a, b in zip(pts, pts[1:]):
            if a[1] >= min_el or b[1] >= min_el:
                segs.append((a[0], a[1], b[0], b[1]))
    return segs


def azel_to_xy(az_deg, el_deg, size=1.0):
    """Project az/el to x,y in a unit circle sky plot (zenith centre, horizon
    edge; north up, east right). Returns (x, y) with the circle radius = size/2
    centred at (size/2, size/2), or None if below the horizon."""
    import math
    if el_deg < 0:
        return None
    r = (90.0 - el_deg) / 90.0 * (size / 2.0)
    a = math.radians(az_deg)
    x = size / 2.0 + r * math.sin(a)
    y = size / 2.0 - r * math.cos(a)
    return x, y
