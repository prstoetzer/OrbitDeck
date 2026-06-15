"""oscarlocator.py - generate printable OSCARLOCATOR sheets as vector PDFs.

A classic OSCARLOCATOR is a paper aid for visualising satellite passes: an
azimuthal-equidistant map centred on your station, plus transparent overlays you
pin at the map centre and rotate. This module produces three print-ready pages,
all drawn to the *same angular scale* so the overlays register on top of the
base map:

  1. Base map  (print on paper / card)   - az-equidistant map centred on the QTH
     with a lat/lon graticule, range rings, azimuth spokes and coastlines
     (full-resolution via cartopy when available).
  2. Footprint (print on transparency)   - the selected satellite's coverage
     circle with distance rings every 1000 km and radial lines every 15 deg.
  3. Path arc  (print on transparency)   - the classic rotatable any-orbit ground
     -track arc for the satellite's inclination, with tick marks every minute
     (longer every ten minutes) and a small diagram of how many degrees to
     advance the arc for each successive pass.

Everything is laid out in physical inches so a printed page has a known scale,
and the overlays are the same physical size as the base map's plotting area.

Projection: a point at great-circle central angle ``rho`` (deg) and bearing
``az`` from the station maps to polar (r = rho, theta = az) -- azimuthal
equidistant, station at centre, antipode on the rim at rho = 180 deg.
"""

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from ..engine.predict import Predictor
from ..engine import analysis as A
from .mapdraw import COASTLINES

RE_KM = 6378.135
SIDEREAL_DAY_S = 86164.0905           # Earth's rotation period

PLOT_DIAMETER_IN = 7.0
PAGE_W_IN = 8.5
PAGE_H_IN = 11.0
MAP_RADIUS_DEG = 90.0
KM_PER_DEG = math.pi / 180.0 * RE_KM

# --- visual style: bolder lines and larger text so the printed sheets read
# clearly, especially through stacked transparencies. Tune here in one place.
LW_GRID = 0.9            # graticule / faint reference lines
LW_RING = 1.3            # latitude / range rings
LW_SPOKE = 0.9           # azimuth / meridian spokes
LW_COAST = 0.8           # coastlines
LW_TRACK = 2.6           # satellite ground track
LW_FOOT = 3.0            # footprint circle
LW_INDICATOR = 2.4       # per-pass rotation arrow

FS_TITLE = 18
FS_SUBTITLE = 11
FS_CARDINAL = 14         # N/E/S/W letters
FS_AZLABEL = 9           # azimuth/longitude degree labels
FS_RINGLABEL = 8         # ring distance/latitude labels
FS_TICKLABEL = 8         # minute-tick numbers
FS_NOTE = 9              # footer note
FS_BIGLABEL = 11         # rotation-indicator label

MARK_CROSS = 16          # centre cross marker size
MEW_CROSS = 2.4          # centre cross line width


def _central_angle_bearing(qlat, qlon, lat, lon):
    p1, l1 = math.radians(qlat), math.radians(qlon)
    p2, l2 = math.radians(lat), math.radians(lon)
    dl = l2 - l1
    ca = math.acos(max(-1.0, min(1.0,
        math.sin(p1) * math.sin(p2) +
        math.cos(p1) * math.cos(p2) * math.cos(dl))))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    br = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return math.degrees(ca), br


class _Projection:
    """Maps (lat, lon) -> (rho_deg, bearing_deg) for the azimuthal-equidistant
    sheet. Modes:

      * 'qth'        - centred on the station; rho is great-circle distance and
                       bearing is azimuth from the QTH (a personalised sheet).
      * 'polar'      - centred on the North Pole; rho is colatitude (90-lat),
                       bearing is longitude. Classic PE1RAH OSCARLATOR polar map
                       of the northern hemisphere -- generic, QTH-independent.
      * 'polar-south'- centred on the South Pole for southern-hemisphere
                       stations; rho is 90+lat (colatitude from the S pole) and
                       the longitude bearing is mirrored so the sheet reads
                       correctly when viewed from the southern side.
    """

    def __init__(self, mode="qth", qlat=0.0, qlon=0.0):
        self.mode = mode
        self.qlat = qlat
        self.qlon = qlon

    def project(self, lat, lon):
        if self.mode == "polar":
            # North-pole-centred: distance from pole = 90 - lat, bearing = lon
            return 90.0 - lat, (lon + 360.0) % 360.0
        if self.mode == "polar-south":
            # South-pole-centred: distance from S pole = 90 + lat. Mirror the
            # longitude so the map is not left-right reversed when laid out with
            # the same N-up/clockwise polar axes as the northern sheet.
            return 90.0 + lat, (-lon + 360.0) % 360.0
        return _central_angle_bearing(self.qlat, self.qlon, lat, lon)

    @property
    def is_polar(self):
        return self.mode in ("polar", "polar-south")

    @property
    def is_south(self):
        return self.mode == "polar-south"


def _polar_axes(fig, title, subtitle, rmax=MAP_RADIUS_DEG, show_rim=True):
    w = PLOT_DIAMETER_IN / PAGE_W_IN
    h = PLOT_DIAMETER_IN / PAGE_H_IN
    left = (1 - w) / 2
    bottom = (1 - h) / 2 - 0.02
    ax = fig.add_axes([left, bottom, w, h], projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, rmax)
    ax.set_rticks([])
    ax.set_xticks([])
    ax.set_facecolor("white")
    if not show_rim:
        # hide the outer boundary circle so only the drawn content inks the
        # sheet (used by the footprint overlay, which is its own boundary)
        ax.spines["polar"].set_visible(False)
    fig.text(0.5, 0.95, title, ha="center", va="top", fontsize=FS_TITLE,
             fontweight="bold")
    if subtitle:
        fig.text(0.5, 0.915, subtitle, ha="center", va="top",
                 fontsize=FS_SUBTITLE, color="#222222")
    return ax


def _coastline_segments():
    """Prefer cartopy's Natural Earth coastlines (high detail); fall back to the
    bundled polylines."""
    try:
        import cartopy.feature as cfeature
        feat = cfeature.NaturalEarthFeature("physical", "coastline", "110m")
        segs = []
        for geom in feat.geometries():
            geoms = getattr(geom, "geoms", [geom])
            for g in geoms:
                try:
                    xy = list(g.coords)
                except (NotImplementedError, AttributeError):
                    xy = list(g.exterior.coords)
                segs.append([(x, y) for x, y in xy])
        if segs:
            return segs
    except Exception:
        pass
    return COASTLINES


def _project_polyline(ax, proj, pts, color, lw, zorder, rmax):
    """Project a (lon,lat) polyline into the map via ``proj``, breaking it where
    it leaves the plotted area or wraps across the rim."""
    th, rr, prev_br = [], [], None
    for lon, lat in pts:
        ca, br = proj.project(lat, lon)
        if ca > rmax:
            if len(th) > 1:
                ax.plot(th, rr, color=color, linewidth=lw, zorder=zorder)
            th, rr, prev_br = [], [], None
            continue
        if prev_br is not None and abs(br - prev_br) > 180:
            if len(th) > 1:
                ax.plot(th, rr, color=color, linewidth=lw, zorder=zorder)
            th, rr = [], []
        th.append(math.radians(br))
        rr.append(ca)
        prev_br = br
    if len(th) > 1:
        ax.plot(th, rr, color=color, linewidth=lw, zorder=zorder)


def _draw_coastlines(ax, proj, segments, rmax):
    for seg in segments:
        _project_polyline(ax, proj, seg, "#4d6b80", LW_COAST, 2, rmax)


def _draw_graticule(ax, proj, rmax):
    """Parallels and meridians every 15 deg, projected into the map. In polar
    mode the parallels become concentric circles and meridians become radial
    spokes -- the classic polar great-circle grid."""
    if proj.is_south:
        lat_lo, lat_hi = -90, 1               # southern hemisphere meridians
        par_lo, par_hi = -75, 1               # parallels down to the equator
    elif proj.is_polar:
        lat_lo, lat_hi = 0, 91
        par_lo, par_hi = 0, 76
    else:
        lat_lo, lat_hi = -90, 91
        par_lo, par_hi = -75, 76
    for lon in range(-180, 180, 15):
        pts = [(lon, j) for j in range(lat_lo, lat_hi, 2)]
        _project_polyline(ax, proj, pts, "#c4c4c4", LW_GRID, 1, rmax)
    for lat in range(par_lo, par_hi, 15):
        pts = [(k, lat) for k in range(-180, 181, 2)]
        _project_polyline(ax, proj, pts, "#c4c4c4", LW_GRID, 1, rmax)


def _draw_az_grid(ax, proj, rmax):
    if proj.is_polar:
        # polar map: radial spokes are meridians (longitude), rings are
        # parallels of latitude (colatitude from the pole). For the southern
        # sheet the bearing is mirrored, so a spoke drawn at screen-angle a
        # corresponds to longitude -a.
        for a in range(0, 360, 30):
            ax.plot([math.radians(a), math.radians(a)], [0, rmax],
                    color="#b0b0b0", linewidth=LW_SPOKE, zorder=1)
            lon = (-a if proj.is_south else a) % 360
            disp = lon if lon <= 180 else lon - 360
            hemi = "E" if 0 < disp < 180 else ("W" if disp < 0 else "")
            ax.text(math.radians(a), rmax * 1.05,
                    "%d\u00b0%s" % (abs(disp), hemi),
                    ha="center", va="center", fontsize=FS_AZLABEL,
                    color="#444444", fontweight="bold")
        # latitude rings every 15 deg
        for lat_abs in range(0, 91, 15):
            ring = 90 - lat_abs
            if ring <= 0:
                continue
            th = [math.radians(a) for a in range(0, 361, 2)]
            ax.plot(th, [ring] * len(th), color="#9a9a9a", linewidth=LW_RING,
                    zorder=1)
            lat_label = -lat_abs if proj.is_south else lat_abs
            ax.text(math.radians(45), ring, "%d\u00b0" % lat_label,
                    fontsize=FS_RINGLABEL, color="#555555", ha="center",
                    va="bottom", fontweight="bold")
        ax.plot([0], [0], marker="+", color="black", markersize=MARK_CROSS,
                markeredgewidth=MEW_CROSS, zorder=6)
        return
    # QTH-centred: azimuth spokes + great-circle range rings
    for az in range(0, 360, 15):
        ax.plot([math.radians(az), math.radians(az)], [0, rmax],
                color="#b0b0b0", linewidth=LW_SPOKE, zorder=1)
    for az in range(0, 360, 30):
        ax.text(math.radians(az), rmax * 1.04, "%d\u00b0" % az,
                ha="center", va="center", fontsize=FS_AZLABEL,
                color="#444444", fontweight="bold")
    for az, name in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
        ax.text(math.radians(az), rmax * 1.11, name, ha="center",
                va="center", fontsize=FS_CARDINAL, fontweight="bold")
    for rho in range(30, int(rmax) + 1, 30):
        th = [math.radians(a) for a in range(0, 361, 2)]
        ax.plot(th, [rho] * len(th), color="#9a9a9a", linewidth=LW_RING,
                zorder=1)
        ax.text(math.radians(45), rho, "%d km" % round(rho * KM_PER_DEG, -2),
                fontsize=FS_RINGLABEL, color="#555555", ha="center",
                va="bottom", fontweight="bold")
    ax.plot([0], [0], marker="+", color="black", markersize=MARK_CROSS,
            markeredgewidth=MEW_CROSS, zorder=6)


def _base_map_page(pdf, proj, qth_name, segments, rmax):
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    if proj.is_polar:
        hemi = "southern" if proj.is_south else "northern"
        pole = "South" if proj.is_south else "North"
        title = "OSCARLATOR \u2014 Polar Base Map (%s)" % hemi
        sub = ("Polar great-circle map of the %s hemisphere "
               "(generic \u2014 use with any QTH via the EQX list)" % hemi)
    else:
        title = "OSCARLOCATOR \u2014 Base Map"
        sub = "Azimuthal-equidistant map centred on %s  (%.3f, %.3f)" % (
            qth_name, proj.qlat, proj.qlon)
    ax = _polar_axes(fig, title, sub, rmax=rmax)
    _draw_graticule(ax, proj, rmax)
    _draw_coastlines(ax, proj, segments, rmax)
    _draw_az_grid(ax, proj, rmax)
    if proj.is_polar:
        note = ("Print on paper or card at 100%% (actual size). Centre is the "
                "%s Pole; rings are latitude (15\u00b0), spokes are longitude. "
                "Lay the satellite overhead and footprint on top." % pole)
    else:
        note = ("Print on paper or card at 100% (actual size). Overlays "
                "register on the centre cross; rings are great-circle distance, "
                "spokes are azimuth, grey graticule is lat/lon (15\u00b0).")
    fig.text(0.5, 0.05, note, ha="center", va="bottom", fontsize=FS_NOTE,
             color="#333333", wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def _footprint_page(pdf, sat_name, alt_km, proj, rmax):
    foot_deg = A.footprint_radius_deg(alt_km)
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    sub = ("Footprint radius %.1f\u00b0 (~%d km) at %.0f km altitude"
           % (foot_deg, round(foot_deg * KM_PER_DEG, -1), alt_km))
    # IMPORTANT: keep the same angular scale (rmax) as the base map and arc
    # sheets so this transparency registers on top of them. We simply don't draw
    # anything beyond the footprint, so the rest of the sheet is clear and the
    # map shows through.
    fr = min(foot_deg, rmax)
    ax = _polar_axes(fig, "%s \u2014 Footprint Overlay" % sat_name, sub,
                     rmax=rmax, show_rim=False)

    # azimuth rose: spokes every 30 deg, drawn only out to the footprint edge,
    # with degree labels and cardinal letters just outside the footprint circle
    for az in range(0, 360, 30):
        ax.plot([math.radians(az), math.radians(az)], [0, fr],
                color="#a0a0a0", linewidth=LW_SPOKE, zorder=2)
    for az in range(0, 360, 30):
        if az % 90 != 0:
            ax.text(math.radians(az), fr * 1.07, "%d" % az, ha="center",
                    va="center", fontsize=FS_AZLABEL, color="#444444",
                    fontweight="bold", zorder=3)
    for az, name in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
        ax.text(math.radians(az), fr * 1.16, name, ha="center",
                va="center", fontsize=FS_CARDINAL, fontweight="bold", zorder=3)

    # a few distance rings INSIDE the footprint only (not out to the sheet edge)
    foot_km = foot_deg * KM_PER_DEG
    if foot_km <= 2500:
        step_km = 500
    elif foot_km <= 6000:
        step_km = 1000
    else:
        step_km = 2000
    th = [math.radians(a) for a in range(0, 361, 2)]
    km = step_km
    while km < foot_km - 1:                 # strictly inside the footprint
        rho = km / KM_PER_DEG
        ax.plot(th, [rho] * len(th), color="#9a9a9a", linewidth=LW_RING,
                zorder=2)
        ax.text(math.radians(45), rho, "%d km" % km, fontsize=FS_RINGLABEL,
                color="#555555", ha="center", va="bottom", fontweight="bold",
                zorder=3)
        km += step_km

    # the footprint circle itself (the outer edge of coverage)
    th1 = [math.radians(a) for a in range(0, 361, 1)]
    ax.plot(th1, [fr] * len(th1), color="#cc0000", linewidth=LW_FOOT, zorder=4)
    ax.plot([0], [0], marker="+", color="black", markersize=MARK_CROSS,
            markeredgewidth=MEW_CROSS, zorder=5)
    fig.text(0.5, 0.05,
             "Print on transparency at 100%. Pin the centre cross at the "
             "satellite's sub-point; the red circle is the edge of coverage "
             "(footprint). Inner rings are distance from the sub-point; spokes "
             "are azimuth. Scale matches the base map.",
             ha="center", va="bottom", fontsize=FS_NOTE, color="#333333",
             wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def _node_shift_deg(sat):
    """Longitude advance (deg; westward negative) of the ascending node per orbit
    -- how far to rotate the arc for each successive pass. Earth's rotation
    during one period plus the J2 nodal regression."""
    period_s = sat.period_min * 60.0 if sat.period_min else 5400.0
    earth_turn = -360.0 * period_s / SIDEREAL_DAY_S
    try:
        node_dpd, _ = A.j2_rates(sat.mean_motion, sat.incl, sat.ecc)
        node_per_orbit = node_dpd * period_s / 86400.0
    except Exception:
        node_per_orbit = 0.0
    return earth_turn + node_per_orbit


def _canonical_track(sat):
    """One orbit of the satellite's ground track as a station-independent set of
    (lon_rel, lat, minute) points, starting at an ascending node at lon 0. This
    is the rotatable OSCARLOCATOR arc: an idealised circular-orbit ground track
    at the satellite's inclination with Earth rotation removed-then-applied per
    minute, so it can be pinned at the pole and rotated to any pass."""
    incl_deg = sat.incl
    retro = incl_deg > 90.0
    incl = math.radians(incl_deg)
    period_min = sat.period_min if sat.period_min else 95.0
    n = 361
    pts = []
    for i in range(n):
        frac = i / (n - 1)
        u = 2.0 * math.pi * frac                 # arg of latitude from node
        lat = math.degrees(math.asin(math.sin(incl) * math.sin(u)))
        lon = math.degrees(math.atan2(math.cos(incl) * math.sin(u),
                                      math.cos(u)))
        if retro:
            lon = -lon
        earth = -360.0 * (frac * period_min * 60.0) / SIDEREAL_DAY_S
        pts.append((lon + earth, lat, frac * period_min))
    return pts


def _arc_page(pdf, pred, sat, proj, rmax):
    """The satellite 'overhead': its orbit ground-track for one revolution, with
    1-minute ticks (longer every 10 min) and an inset showing the per-pass
    advance angle.

    In QTH mode the arc is the rotatable canonical track centred on the station
    sub-pole. In polar mode it is the orbit ground-track drawn directly on the
    pole-centred map (PE1RAH 'overhead' style): rotate the whole transparency to
    the current orbit using the EQX longitude.
    """
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    shift = _node_shift_deg(sat)
    title = ("%s \u2014 Overhead (orbit)" % sat.name if proj.is_polar
             else "%s \u2014 Path Arc Overlay" % sat.name)
    sub = ("Ground-track \u2014 inclination %.1f\u00b0, period %.1f min. "
           "Advance %.1f\u00b0 %s per pass." % (
               sat.incl, sat.period_min, abs(shift),
               "W" if shift < 0 else "E"))
    ax = _polar_axes(fig, title, sub, rmax=rmax)
    for rho in range(30, int(rmax) + 1, 30):
        th = [math.radians(a) for a in range(0, 361, 2)]
        ax.plot(th, [rho] * len(th), color="#cccccc", linewidth=LW_GRID)

    track = _canonical_track(sat)
    th, rr = [], []
    segs = []
    ticks = []
    prev_br = None
    for lon_rel, lat, minute in track:
        # place the orbit track on the sheet. For the polar sheets we use the
        # same pole/colatitude convention as the base-map projection so the
        # overhead registers; the node sits at sheet-longitude 0 (rotate the
        # transparency to the EQX longitude in use).
        if proj.is_south:
            ca = 90.0 + lat
            br = (-lon_rel + 360.0) % 360.0
        else:
            ca = 90.0 - lat
            br = (lon_rel + 360.0) % 360.0
        if ca > rmax:
            if len(th) > 1:
                segs.append((th[:], rr[:]))
            th, rr, prev_br = [], [], None
            continue
        if prev_br is not None and abs(br - prev_br) > 180:
            if len(th) > 1:
                segs.append((th[:], rr[:]))
            th, rr = [], []
        th.append(math.radians(br))
        rr.append(ca)
        ticks.append((math.radians(br), ca, minute))
        prev_br = br
    if len(th) > 1:
        segs.append((th, rr))
    for sth, srr in segs:
        ax.plot(sth, srr, color="#0033bb", linewidth=LW_TRACK, zorder=4)

    # 1-minute ticks, longer/labelled every 10 minutes
    last_min = None
    for thb, ca, minute in ticks:
        mm = int(round(minute))
        if mm == last_min:
            continue
        if abs(minute - mm) <= (sat.period_min / (len(track) - 1)) / 2 + 1e-6:
            major = (mm % 10 == 0)
            ax.plot([thb], [ca], marker="o",
                    markersize=5.0 if major else 2.6,
                    color="#001f7a" if major else "#2255cc", zorder=5)
            if major:
                ax.text(thb, ca - 3, "%d" % mm, fontsize=FS_TICKLABEL,
                        color="#001f7a", ha="center", va="top",
                        fontweight="bold", zorder=6)
            last_min = mm

    ax.plot([0], [0], marker="+", color="black", markersize=14,
            markeredgewidth=2, zorder=6)

    # --- per-pass rotation indicator, drawn in the clear ring just OUTSIDE the
    # plot so it never overlaps the track. The overlay pivots on the centre, so
    # the move is a rotation: a curved arrow on the rim shows its size and sense.
    #
    # The sheet's azimuth axis is N-up, theta clockwise. A westward node drift
    # rotates the sheet counter-clockwise on the page; at the top of the page
    # CCW motion sweeps toward the LEFT (toward West/270deg). On the southern
    # sheet the longitude is mirrored, which flips the on-screen sense.
    west = shift < 0
    ccw = west if not proj.is_south else (not west)   # on-screen rotation sense
    r_ind = rmax * 1.18      # radius of the indicator arc, beyond the plot edge
    half = math.radians(abs(shift)) / 2.0
    a_lo, a_hi = -half, half          # centred on North (top)
    arc = [a_lo + (a_hi - a_lo) * k / 60 for k in range(61)]
    ax.plot(arc, [r_ind] * len(arc), color="#cc0000", linewidth=LW_INDICATOR,
            zorder=7, clip_on=False, solid_capstyle="round")
    # CCW (screen) -> head at the left end (a_lo); CW -> head at right (a_hi)
    if ccw:
        tip, pre = a_lo, a_lo + math.radians(0.6)
    else:
        tip, pre = a_hi, a_hi - math.radians(0.6)
    ax.annotate("", xy=(tip, r_ind), xytext=(pre, r_ind),
                arrowprops=dict(arrowstyle="-|>", color="#cc0000",
                                lw=LW_INDICATOR),
                annotation_clip=False, zorder=8)
    # numeric label sitting above the arc, in the top margin. The node always
    # drifts west geographically; we also state the on-sheet turn sense.
    geo = "west" if west else "east"
    sense = "counter-clockwise" if ccw else "clockwise"
    fig.text(0.5, 0.875,
             "rotate sheet %.1f\u00b0 %s (node moves %s) each pass"
             % (abs(shift), sense, geo),
             ha="center", va="bottom", fontsize=FS_BIGLABEL, color="#cc0000",
             fontweight="bold")

    if proj.is_polar:
        node = "descending node" if proj.is_south else "ascending node"
        note = ("Print on transparency at 100%%. Lay over the polar base map "
                "with centres aligned and the %s at the EQX longitude, then "
                "rotate the whole sheet %.1f\u00b0 %s about the centre for each "
                "successive pass (see the rim arrow). Dots are 1-minute marks; "
                "larger dots every 10 minutes." % (
                    node, abs(shift),
                    "westward" if shift < 0 else "eastward"))
    else:
        note = ("Print on transparency at 100%%. Pin the centre cross over the "
                "station, then rotate the arc %.1f\u00b0 %s about the centre for "
                "each successive pass (see the rim arrow). Dots are 1-minute "
                "marks; larger dots every 10 minutes." % (
                    abs(shift), "westward" if shift < 0 else "eastward"))
    fig.text(0.5, 0.04, note, ha="center", va="bottom", fontsize=FS_NOTE,
             color="#333333", wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def _footprint_locus(qlat, qlon, foot_deg, n=361):
    """Return the (lat, lon) points of a small circle of angular radius
    ``foot_deg`` centred on the QTH -- i.e. the footprint edge when the satellite
    sub-point is over the station. Walk all bearings from the QTH at the fixed
    great-circle distance ``foot_deg``."""
    p1 = math.radians(qlat)
    l1 = math.radians(qlon)
    d = math.radians(foot_deg)
    pts = []
    for i in range(n):
        brg = math.radians(360.0 * i / (n - 1))
        lat2 = math.asin(math.sin(p1) * math.cos(d) +
                         math.cos(p1) * math.sin(d) * math.cos(brg))
        lon2 = l1 + math.atan2(math.sin(brg) * math.sin(d) * math.cos(p1),
                               math.cos(d) - math.sin(p1) * math.sin(lat2))
        pts.append((math.degrees(lat2),
                    (math.degrees(lon2) + 540.0) % 360.0 - 180.0))
    return pts


def _base_map_with_footprint_page(pdf, proj, obs, qth_name, segments, rmax,
                                  foot_deg):
    """Combined sheet: the base map plus the satellite footprint drawn at the
    station's position. The footprint is always centred on the QTH (when the
    satellite is overhead), so this single sheet shows the coverage directly on
    the map -- no separate transparency needed."""
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    if proj.is_polar:
        hemi = "southern" if proj.is_south else "northern"
        title = "OSCARLATOR \u2014 Map + Footprint at QTH (%s)" % hemi
        sub = ("Footprint of the satellite when overhead your station "
               "(%s), on the %s polar map" % (qth_name, hemi))
    else:
        title = "OSCARLOCATOR \u2014 Map + Footprint at QTH"
        sub = ("Footprint when the satellite is overhead %s (%.3f, %.3f)"
               % (qth_name, obs.lat, obs.lon))
    ax = _polar_axes(fig, title, sub, rmax=rmax)
    _draw_graticule(ax, proj, rmax)
    _draw_coastlines(ax, proj, segments, rmax)
    _draw_az_grid(ax, proj, rmax)

    # draw the footprint centred on the station's position in this projection
    locus = _footprint_locus(obs.lat, obs.lon, min(foot_deg, rmax))
    _project_polyline(ax, proj, [(lon, lat) for lat, lon in locus],
                      "#cc0000", LW_FOOT, 5, rmax)
    # mark the QTH itself
    q_rho, q_br = proj.project(obs.lat, obs.lon)
    if q_rho <= rmax:
        ax.plot([math.radians(q_br)], [q_rho], marker="*", color="#cc0000",
                markersize=15, zorder=6)
    fig.text(0.5, 0.05,
             "Print on paper or card at 100%. The red circle is the satellite's "
             "footprint when it is directly over your station (red star). Use "
             "the separate path-arc overlay to see when it enters this circle.",
             ha="center", va="bottom", fontsize=FS_NOTE, color="#333333",
             wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def generate_oscarlocator_pdf(path, store, sat, when_unix=None,
                              projection="qth", footprint_on_qth=False):
    """Write an OSCARLOCATOR PDF for ``sat``.

    Standard output (``footprint_on_qth`` False) is 3 pages: base map, footprint
    overlay (transparency), orbit/arc overlay (transparency).

    With ``footprint_on_qth`` True the output is a 2-page set: page 1 is the base
    map with the satellite footprint drawn directly at the station (no separate
    footprint transparency needed), and page 2 is the path-arc overlay. Available
    for both the QTH-centred and the polar maps.

    ``projection`` selects the base map:
      * "qth"         - azimuthal-equidistant map centred on the station.
      * "polar"       - North-pole-centred polar great-circle map (PE1RAH
                        OSCARLATOR style; generic, usable by anyone with the
                        ascending-node EQX list). Best for northern stations.
      * "polar-south" - South-pole-centred version for southern-hemisphere
                        stations; use with the descending-node EQX list.
      * "polar-auto"  - pick north or south automatically from the station
                        latitude in ``store``.
    """
    import time
    if when_unix is None:
        when_unix = time.time()
    obs = store.obs
    qth_name = store.my_grid()

    if projection == "polar-auto":
        projection = "polar-south" if obs.lat < 0 else "polar"

    if projection == "polar":
        proj = _Projection("polar")
        rmax = 90.0                       # northern hemisphere: pole to equator
    elif projection == "polar-south":
        proj = _Projection("polar-south")
        rmax = 90.0                       # southern hemisphere: pole to equator
    else:
        proj = _Projection("qth", obs.lat, obs.lon)
        rmax = MAP_RADIUS_DEG

    pred = Predictor()
    pred.set_site(obs)
    pred.set_sat(sat)
    _lat, _lon, alt_km = pred.subpoint_at(when_unix)
    foot_deg = A.footprint_radius_deg(alt_km)

    segments = _coastline_segments()
    with PdfPages(path) as pdf:
        if footprint_on_qth:
            # 2-page set: map+footprint, then the path arc
            _base_map_with_footprint_page(pdf, proj, obs, qth_name, segments,
                                          rmax, foot_deg)
            _arc_page(pdf, pred, sat, proj, rmax)
        else:
            # standard 3-page set: map, footprint transparency, path arc
            _base_map_page(pdf, proj, qth_name, segments, rmax)
            _footprint_page(pdf, sat.name, alt_km, proj, rmax)
            _arc_page(pdf, pred, sat, proj, rmax)
        d = pdf.infodict()
        kind = {"polar": "polar-north", "polar-south": "polar-south"}.get(
            projection, "QTH-centred")
        d["Title"] = "OSCARLOCATOR (%s) \u2014 %s" % (kind, sat.name)
        d["Subject"] = "Printable base map, footprint and orbit overlays"
        d["Creator"] = "OrbitDeck"
    return path
