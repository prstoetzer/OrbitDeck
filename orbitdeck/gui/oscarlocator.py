"""oscarlocator.py - generate printable OSCARLOCATOR sheets as vector PDFs.

A classic OSCARLOCATOR is a paper aid for visualising satellite passes: an
azimuthal-equidistant map centred on your station, plus transparent overlays you
pin at the map centre and rotate. This module produces three print-ready pages,
all drawn to the *same angular scale* so the overlays register on top of the
base map:

  1. Base map  (print on paper / card)   - az-equidistant map centred on the QTH
     with a lat/lon graticule, range rings, azimuth spokes and coastlines
     (full-resolution via cartopy when available).
  2. Footprint (print on transparency)   - the selected satellite's range
     circle, the same radius as its coverage footprint. Pinned over the QTH at
     the map centre, the satellite is in range whenever its ground track is
     inside this circle; AOS/LOS are read where the path-arc crosses it. Inner
     distance rings every 1000 km and radial lines every 15 deg.
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

PLOT_DIAMETER_IN = 6.6
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

# Page margins as a fraction of the figure width/height. Titles, subtitles and
# footer notes must stay inside these so nothing spills off the printed page.
MARGIN_X = 0.08          # left/right margin (about 0.68" on an 8.5" page)
TEXT_L = MARGIN_X
TEXT_R = 1.0 - MARGIN_X
TEXT_W = TEXT_R - TEXT_L


def _wrap_to_width(s, fontsize, width_frac=TEXT_W):
    """Wrap a string to fit within ``width_frac`` of the page width at the given
    font size, returning a string with embedded newlines. Uses an estimate of
    the average character width so we wrap to a margin rather than to the figure
    edge (matplotlib's wrap=True wraps only at the figure boundary)."""
    import textwrap
    avg_char_in = fontsize * 0.0090          # ~ average glyph advance, inches
    usable_in = width_frac * PAGE_W_IN
    ncols = max(12, int(usable_in / max(avg_char_in, 0.01)))
    # protect non-breaking spaces (\u00a0) from textwrap, which otherwise treats
    # them as ordinary break points, then restore them after wrapping so
    # value+unit groups like "2240 km" never split across lines
    sentinel = "\x00"
    lines = textwrap.wrap(s.replace("\u00a0", sentinel), width=ncols)
    out = "\n".join(ln.replace(sentinel, "\u00a0") for ln in lines)
    return out or s


def _fit_sat_name(name, suffix, min_fs=13.0, width_frac=TEXT_W):
    """Return a possibly-truncated satellite name so the composed title
    ``"<name> <suffix>"`` fits within the page margins at a readable font size.

    The title auto-shrinks (see ``_draw_title``), but for very long names that
    would force the whole title (including the descriptive suffix) down to an
    unreadable size. Instead we cap the shrink at ``min_fs`` and, if the name is
    still too long, truncate just the NAME with an ellipsis -- so the
    "... OSCARLOCATOR Base Map" part always stays legible. ``suffix`` is the
    fixed descriptive remainder of the title (e.g. " \u2014 OSCARLOCATOR Base
    Map"), measured but never truncated.
    """
    avg_char_in = min_fs * 0.0102            # bold glyph advance, inches/pt
    usable_in = width_frac * PAGE_W_IN
    max_chars = max(8, int(usable_in / max(avg_char_in, 0.01)))
    budget = max_chars - len(suffix)
    if budget < 6:                           # suffix alone is huge; keep a stub
        budget = 6
    if len(name) <= budget:
        return name
    return name[:max(1, budget - 1)].rstrip() + "\u2026"


def _fit_title_fontsize(s, base=FS_TITLE, width_frac=TEXT_W):
    """Shrink the title font size just enough that the (single-line) title fits
    within the margins, so long satellite names don't push it off the page.
    Titles are bold, whose glyphs are wider, so the per-character estimate is
    deliberately generous."""
    avg_char_in = base * 0.0102          # bold title glyph advance, inches/pt
    usable_in = width_frac * PAGE_W_IN
    max_chars = max(1, usable_in / max(avg_char_in, 0.01))
    if len(s) <= max_chars:
        return base
    return max(10.0, base * max_chars / len(s))


def _draw_title(fig, title, subtitle):
    """Draw a centred title (auto-shrunk to fit the margins) and a wrapped
    subtitle, both kept inside the page margins."""
    t = fig.text(0.5, 0.955, title, ha="center", va="top", fontsize=FS_TITLE,
                 fontweight="bold")
    # measure the rendered width and shrink the font until it fits the margins
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        fig_w = fig.get_size_inches()[0] * fig.dpi
        max_w = TEXT_W * fig_w
        bb = t.get_window_extent(renderer=renderer)
        fs = FS_TITLE
        while bb.width > max_w and fs > 9:
            fs -= 0.5
            t.set_fontsize(fs)
            bb = t.get_window_extent(renderer=renderer)
    except Exception:
        # headless / no renderer: fall back to the character-width estimate
        t.set_fontsize(_fit_title_fontsize(title))
    if subtitle:
        wrapped = _wrap_to_width(subtitle, FS_SUBTITLE)
        fig.text(0.5, 0.917, wrapped, ha="center", va="top",
                 fontsize=FS_SUBTITLE, color="#222222", linespacing=1.3)


def _draw_footer(fig, note, y=0.072):
    """Draw a centred footer note wrapped to the page margins. The baseline sits
    a little above the very bottom so the OrbitDeck/author credit can occupy the
    bottom band without colliding (both stay inside the printer's safe area)."""
    wrapped = _wrap_to_width(note, FS_NOTE)
    fig.text(0.5, y, wrapped, ha="center", va="bottom", fontsize=FS_NOTE,
             color="#333333", linespacing=1.3)


def _draw_branding(fig):
    """Unobtrusive OrbitDeck branding + author credit centred along the bottom of
    a sheet. Kept small and grey so it never competes with the map or the printed
    instructions. Placed ~0.5 inch up from the page edge so it stays inside the
    unprintable margin that most desktop printers impose (which was clipping a
    corner-anchored credit)."""
    try:
        from .. import __version__ as _ver
    except Exception:
        _ver = ""
    tag = "OrbitDeck%s \u2022 Paul Stoetzer, N8HM" % (
        " v%s" % _ver if _ver else "")
    # y as a fraction of page height: ~0.5 in on an 11 in page. Centred so it is
    # symmetric within the printable area regardless of left/right margins.
    fig.text(0.5, 0.045, tag, ha="center", va="bottom", fontsize=6.5,
             color="#9a9a9a")


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
                       bearing is longitude. Classic PE1RAH OSCARLOCATOR polar map
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
        # For the polar maps the bearing returned here is simply the longitude;
        # the conventional (un-mirrored) handedness is set by the axes
        # orientation in _polar_axes (north: east CCW, south: east CW), so both
        # hemispheres use the same plain-longitude bearing.
        if self.mode == "polar":
            return 90.0 - lat, (lon + 360.0) % 360.0       # colat from N pole
        if self.mode == "polar-south":
            return 90.0 + lat, (lon + 360.0) % 360.0       # colat from S pole
        return _central_angle_bearing(self.qlat, self.qlon, lat, lon)

    @property
    def is_polar(self):
        return self.mode in ("polar", "polar-south")

    @property
    def is_south(self):
        return self.mode == "polar-south"


def _polar_axes(fig, title, subtitle, rmax=MAP_RADIUS_DEG, show_rim=True,
                proj=None):
    w = PLOT_DIAMETER_IN / PAGE_W_IN
    h = PLOT_DIAMETER_IN / PAGE_H_IN
    left = (1 - w) / 2
    bottom = (1 - h) / 2 - 0.02
    ax = fig.add_axes([left, bottom, w, h], projection="polar")
    # Orientation depends on the sheet type:
    #  * QTH azimuth map: bearing is a compass azimuth -- N at top, increasing
    #    CLOCKWISE (N->E->S->W), the natural antenna-pointing layout.
    #  * North polar map (atlas-standard view, looking down at the N pole):
    #    0 deg longitude points DOWN, longitude increases EASTWARD going
    #    COUNTER-CLOCKWISE. This is the conventional ARRL OSCAR Locator layout;
    #    drawing it any other way mirrors (left-right flips) the continents.
    #  * South polar map (looking down THROUGH the earth at the S pole): 0 deg
    #    longitude points DOWN, longitude increases EASTWARD going CLOCKWISE.
    if proj is not None and proj.is_polar:
        if proj.is_south:
            ax.set_theta_zero_location("S")
            ax.set_theta_direction(-1)        # east clockwise (southern view)
        else:
            ax.set_theta_zero_location("S")
            ax.set_theta_direction(1)         # east counter-clockwise (north)
    else:
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)            # compass azimuth, clockwise
    ax.set_rlim(0, rmax)
    ax.set_rticks([])
    ax.set_xticks([])
    ax.set_facecolor("white")
    if not show_rim:
        # hide the outer boundary circle so only the drawn content inks the
        # sheet (used by the footprint overlay, which is its own boundary)
        ax.spines["polar"].set_visible(False)
    _draw_title(fig, title, subtitle)
    return ax


def _draw_rim_ticks(ax, rmax, zorder=6):
    """Draw fine tick marks every degree around the outer ring (rim) of an
    OSCARLOCATOR sheet, with progressively longer marks every 5 and 10 degrees,
    so the rim can be read like a protractor and stacked overlays registered to
    the degree. The tick angle is the sheet's own theta coordinate (azimuth on
    the QTH map, longitude on the polar maps), matching whatever the rim already
    represents.
    """
    # tick lengths as a fraction of the sheet radius
    minor = rmax * 0.010          # every 1 deg
    mid = rmax * 0.020            # every 5 deg
    major = rmax * 0.032          # every 10 deg
    for deg in range(0, 360):
        if deg % 10 == 0:
            ln, lw = major, 1.1
        elif deg % 5 == 0:
            ln, lw = mid, 0.8
        else:
            ln, lw = minor, 0.5
        a = math.radians(deg)
        ax.plot([a, a], [rmax - ln, rmax], color="black", linewidth=lw,
                zorder=zorder, solid_capstyle="butt")


# The range-circle transparency is a true circle of constant ground distance
# from the QTH. On the QTH-centred base map that circle is exact. On the POLAR
# base map (which is azimuthal-equidistant about the pole, not the QTH) the same
# constant-distance locus re-projects to an oval that bulges outward, so the raw
# circle sits inside the true coverage boundary and under-states coverage by an
# amount that grows away from the pole.
#
# The polar transparency is meant to stay GENERIC -- one printed circle anyone
# can use, with no QTH input -- so we can't fit each station's oval. Instead we
# enlarge the circle by a single fixed factor chosen to minimise the error
# across the world's population (which is heavily concentrated at 25-55 deg
# latitude). +6.5% is a population-weighted optimum: it cuts the typical
# mid-latitude error by ~20% while only modestly enlarging the (already small)
# error for high-latitude stations. The factor is essentially independent of
# footprint size because the distortion depends on the QTH's colatitude, not on
# the footprint.
POLAR_RANGE_CIRCLE_INFLATION = 1.065


def _polar_range_circle_deg(foot_deg):
    """Radius (deg) to draw for the range-circle transparency when it is laid
    over the generic POLAR base map: the footprint radius enlarged by the fixed
    population-optimised factor so a single generic circle best fits the polar
    map's distortion for the majority of users. See
    POLAR_RANGE_CIRCLE_INFLATION."""
    return foot_deg * POLAR_RANGE_CIRCLE_INFLATION


def _km_ring_step(reach_km):
    """Pick a clean distance-ring step (km) that yields ~2-4 rings out to
    ``reach_km``, used for the OSCARLOCATOR range-circle distance rings."""
    if reach_km <= 1500:
        return 500
    if reach_km <= 3500:
        return 1000
    if reach_km <= 7000:
        return 2000
    return 3000


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


def _draw_az_grid(ax, proj, rmax, alt_km=None, skip_horizon=False,
                  dist_rings=False, dist_max_deg=None, label_el=True):
    if proj.is_polar:
        # polar map: radial spokes are meridians (longitude), rings are
        # parallels of latitude (colatitude from the pole). A spoke drawn at
        # theta-value a corresponds to longitude a; the axes set the visual
        # handedness (north: east CCW, south: east CW), so the label is the same
        # for both hemispheres.
        for a in range(0, 360, 30):
            ax.plot([math.radians(a), math.radians(a)], [0, rmax],
                    color="#b0b0b0", linewidth=LW_SPOKE, zorder=1)
            disp = a if a <= 180 else a - 360
            hemi = "E" if 0 < disp < 180 else ("W" if disp < 0 else "")
            # 0 deg points down and 180 deg up on the sheet (where the footer and
            # title sit), so nudge those two labels radially inward a touch and
            # give them a white backing so they read clearly and never collide
            # with the surrounding text. 90 E / 90 W sit left/right with room.
            cardinal = a in (0, 90, 180, 270)
            r_label = rmax * 1.065 if a in (0, 180) else rmax * 1.10
            bbox = (dict(boxstyle="round,pad=0.10", fc="white", ec="none",
                        alpha=0.9) if cardinal else None)
            ax.text(math.radians(a), r_label,
                    "%d\u00b0%s" % (abs(disp), hemi),
                    ha="center", va="center", fontsize=FS_AZLABEL,
                    color="#444444", fontweight="bold", zorder=4, bbox=bbox)
        # latitude rings every 15 deg. Labels sit on a quiet spoke (just off the
        # 60 deg meridian) with a small white backing so they read clearly over
        # the ring lines, and the outermost ring (the equator / rim) is NOT
        # labelled here -- that ring is the map boundary and its longitude
        # labels already sit just outside it, so a value there would collide.
        for lat_abs in range(15, 91, 15):
            ring = 90 - lat_abs
            if ring <= 0:
                continue
            th = [math.radians(a) for a in range(0, 361, 2)]
            ax.plot(th, [ring] * len(th), color="#9a9a9a", linewidth=LW_RING,
                    zorder=1)
            lat_label = -lat_abs if proj.is_south else lat_abs
            ax.text(math.radians(62), ring, "%d\u00b0" % lat_label,
                    fontsize=FS_RINGLABEL, color="#555555", ha="center",
                    va="center", fontweight="bold", zorder=3,
                    bbox=dict(boxstyle="round,pad=0.12", fc="white",
                              ec="none", alpha=0.85))
        # registration ticks at the four cardinal longitudes (0/90/180/270),
        # so stacked transparencies can be aligned by eye
        for a in (0, 90, 180, 270):
            ax.plot([math.radians(a), math.radians(a)],
                    [rmax * 0.97, rmax], color="black",
                    linewidth=2.2, zorder=6, solid_capstyle="butt")
        ax.plot([0], [0], marker="+", color="black", markersize=MARK_CROSS,
                markeredgewidth=MEW_CROSS, zorder=6)
        return
    # QTH-centred: azimuth spokes + range rings
    for az in range(0, 360, 15):
        ax.plot([math.radians(az), math.radians(az)], [0, rmax],
                color="#b0b0b0", linewidth=LW_SPOKE, zorder=1)
    # numeric azimuth labels every 30 deg, EXCEPT at the four cardinals (the
    # N/E/S/W letters mark those, so a number there would overlap the letter)
    for az in range(0, 360, 30):
        if az in (0, 90, 180, 270):
            continue
        ax.text(math.radians(az), rmax * 1.05, "%d\u00b0" % az,
                ha="center", va="center", fontsize=FS_AZLABEL,
                color="#444444", fontweight="bold")
    for az, name in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
        ax.text(math.radians(az), rmax * 1.07, name, ha="center",
                va="center", fontsize=FS_CARDINAL, fontweight="bold")
        # registration tick: a short bold radial mark at each cardinal on the
        # rim, so stacked transparencies can be aligned by eye
        ax.plot([math.radians(az), math.radians(az)],
                [rmax * 0.97, rmax], color="black",
                linewidth=2.2, zorder=6, solid_capstyle="butt")
    if alt_km:
        # Elevation rings: a satellite of this altitude appears at a fixed
        # elevation when its sub-point is a given ground distance from the QTH,
        # so each ring is an elevation contour. This is what an operator reads
        # off the sheet ("track crosses the 10 deg ring -> 10 deg elevation").
        # 0 deg el is the horizon (= footprint edge). All labels sit on one
        # radial (the 45 deg spoke) so they read as a tidy aligned column; the
        # rings are at different radii, so the labels naturally separate.
        label_brg = 45
        ring_specs = []
        for el in (0, 10, 30, 60):
            if el == 0 and skip_horizon:
                continue
            rho = A.central_angle_for_elevation_deg(el, alt_km)
            if rho is None or rho > rmax:
                continue
            ring_specs.append((el, rho))
        for el, rho in ring_specs:
            th = [math.radians(a) for a in range(0, 361, 2)]
            # the horizon ring (el=0) is drawn a touch heavier as the visibility
            # boundary; higher-elevation rings are lighter
            lw = LW_RING + 0.5 if el == 0 else LW_RING
            col = "#7a7a7a" if el == 0 else "#9a9a9a"
            ax.plot(th, [rho] * len(th), color=col, linewidth=lw, zorder=1)
        # draw the labels after the rings so they sit on top; suppress any that
        # would overlap a neighbour on the shared radial (keep the lower-el one,
        # since the outer rings have more room). Skipped entirely when label_el
        # is False (e.g. the combined QTH map, where a number on the footprint
        # circle would duplicate the base map's elevation rings).
        min_gap = rmax * 0.05
        placed = []
        for el, rho in sorted(ring_specs, key=lambda r: r[1], reverse=True):
            if not label_el:
                break
            if rho < rmax * 0.06:                 # too close to the centre cross
                continue
            if any(abs(rho - pr) < min_gap for pr in placed):
                continue
            placed.append(rho)
            ax.text(math.radians(label_brg), rho, "%d\u00b0 el" % el,
                    fontsize=FS_RINGLABEL,
                    color="#444444" if el == 0 else "#555555", ha="center",
                    va="bottom", fontweight="bold")
        # distance rings: concentric great-circle range circles labelled in km,
        # so the operator can read the ground distance from the QTH to the
        # sub-point directly off the sheet (the same scale the standalone
        # footprint overlay carries). Rings are placed on a clean km step out to
        # the footprint edge (dist_max_deg) and labelled on the 135 deg spoke,
        # clear of the elevation labels on the 45 deg spoke.
        if dist_rings:
            reach_deg = min(dist_max_deg or rmax, rmax)
            reach_km = reach_deg * KM_PER_DEG
            step_km = _km_ring_step(reach_km)
            th = [math.radians(a) for a in range(0, 361, 2)]
            km = step_km
            while km < reach_km - step_km * 0.25:
                rho = km / KM_PER_DEG
                if rho < rmax * 0.05:
                    km += step_km
                    continue
                ax.plot(th, [rho] * len(th), color="#bdbdbd",
                        linewidth=LW_GRID, zorder=1, linestyle=(0, (4, 3)))
                ax.text(math.radians(135), rho, "%d\u00a0km" % km,
                        fontsize=FS_RINGLABEL, color="#777777", ha="center",
                        va="bottom", fontweight="bold", zorder=3)
                km += step_km
        else:
            # a single faint distance reference ring + km label at mid-map, so
            # the sheet still carries a physical scale
            mid = round(rmax / 2.0 / 10.0) * 10.0
            if 0 < mid < rmax:
                th = [math.radians(a) for a in range(0, 361, 2)]
                ax.plot(th, [mid] * len(th), color="#cccccc", linewidth=LW_GRID,
                        zorder=1, linestyle=(0, (4, 3)))
                ax.text(math.radians(225), mid,
                        "%d km" % round(mid * KM_PER_DEG, -2),
                        fontsize=FS_RINGLABEL, color="#888888", ha="center",
                        va="bottom")
    else:
        # generic base map (no satellite bound): plain great-circle range rings
        for rho in range(30, int(rmax) + 1, 30):
            th = [math.radians(a) for a in range(0, 361, 2)]
            ax.plot(th, [rho] * len(th), color="#9a9a9a", linewidth=LW_RING,
                    zorder=1)
            ax.text(math.radians(45), rho,
                    "%d km" % round(rho * KM_PER_DEG, -2),
                    fontsize=FS_RINGLABEL, color="#555555", ha="center",
                    va="bottom", fontweight="bold")
    ax.plot([0], [0], marker="+", color="black", markersize=MARK_CROSS,
            markeredgewidth=MEW_CROSS, zorder=6)


def _base_map_page(pdf, proj, qth_name, segments, rmax, alt_km=None,
                   sat_name="", reduced_text=False):
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    # In reduced-text mode the base map must be reusable with ANY satellite, so
    # it carries no satellite-specific markings (no elevation rings, which assume
    # a particular altitude) and no satellite name.
    ring_alt = None if reduced_text else alt_km
    if proj.is_polar:
        hemi = "southern" if proj.is_south else "northern"
        pole = "South" if proj.is_south else "North"
        title = "OSCARLOCATOR \u2014 Polar Base Map (%s)" % hemi
        sub = ("Polar great-circle map of the %s hemisphere "
               "(generic \u2014 use with any QTH via the EQX list)" % hemi)
    else:
        if sat_name and not reduced_text:
            _suffix = " \u2014 OSCARLOCATOR Base Map"
            title = _fit_sat_name(sat_name, _suffix) + _suffix
        else:
            title = "OSCARLOCATOR \u2014 Base Map"
        if ring_alt:
            sub = ("Azimuthal-equidistant map centred on %s  (%.3f, %.3f) "
                   "\u2014 rings are elevation at %.0f\u00a0km altitude" % (
                       qth_name, proj.qlat, proj.qlon, ring_alt))
        else:
            sub = "Azimuthal-equidistant map centred on %s  (%.3f, %.3f)" % (
                qth_name, proj.qlat, proj.qlon)
    ax = _polar_axes(fig, title, sub, rmax=rmax, proj=proj)
    _draw_graticule(ax, proj, rmax)
    _draw_coastlines(ax, proj, segments, rmax)
    _draw_az_grid(ax, proj, rmax, alt_km=None if proj.is_polar else ring_alt)
    _draw_rim_ticks(ax, rmax)
    if reduced_text:
        # the base map carries ALL the how-to-use instructions for the set, so
        # the transparencies can stay clean
        if proj.is_polar:
            note = (
                "OSCARLOCATOR \u2014 print this base map on paper/card at 100%% "
                "(actual size); print the range-circle and path-arc overlays on "
                "transparency film at 100%%. Centre is the %s Pole; rings are "
                "latitude (15\u00b0), spokes are longitude, rim ticks are 1\u00b0. "
                "Align overlay centres on the pole. Rotate the path-arc to the "
                "ascending-node longitude from the Crossings List; the satellite "
                "is workable while its track is inside the range circle. Read "
                "AOS/LOS where the track crosses the circle; the rim ticks give "
                "azimuth." % pole)
        else:
            note = (
                "OSCARLOCATOR \u2014 print this base map on paper/card at 100% "
                "(actual size); print the range-circle and path-arc overlays on "
                "transparency film at 100%. Pin the overlays through the centre "
                "cross over your station. Spokes are azimuth, rim ticks are 1\u00b0. "
                "The satellite is workable while its ground track (path-arc) is "
                "inside the range circle; read AOS/LOS where the track crosses "
                "the circle.")
        _draw_footer(fig, note)
        _draw_branding(fig)
        pdf.savefig(fig)
        plt.close(fig)
        return
    if proj.is_polar:
        note = ("Print on paper or card at 100%% (actual size). Centre is the "
                "%s Pole; rings are latitude (15\u00b0), spokes are longitude. "
                "Black rim ticks register stacked overlays. Lay the path-arc "
                "and range-circle overlays on top." % pole)
    elif alt_km:
        note = ("Print on paper or card at 100% (actual size). Overlays "
                "register on the centre cross and the black rim ticks; rings "
                "show the satellite's elevation angle (the 0\u00b0 el ring is its "
                "range-circle edge), spokes are azimuth.")
    else:
        note = ("Print on paper or card at 100% (actual size). Overlays "
                "register on the centre cross; rings are great-circle distance, "
                "spokes are azimuth, grey graticule is lat/lon (15\u00b0).")
    _draw_footer(fig, note)
    _draw_branding(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _draw_footprint_overlay(ax, foot_deg, rmax, with_rose=True,
                            center=(0.0, 0.0)):
    """Draw the standard OSCARLOCATOR footprint overlay so it looks identical
    wherever it appears (the standalone 3-sheet transparency AND the combined
    QTH map): a bold red range circle and a centre cross. When ``with_rose`` is
    set (the standalone transparency, which prints on its own with nothing
    underneath) it also draws the azimuth rose (spokes + degree labels + N/E/S/W
    cardinals) and the inner km distance rings. On the combined map the base map
    already carries the azimuth spokes/labels and elevation rings, so the overlay
    is drawn with ``with_rose=False`` -- just the clean red circle and cross --
    to avoid duplicating those markings on top of the footprint.

    ``center`` is (rho_deg, bearing_deg) of the footprint centre on the sheet;
    the rose/rings are only meaningful when the centre is the sheet centre.
    """
    fr = min(foot_deg, rmax)
    c_rho, c_br = center
    concentric = c_rho <= 1e-6

    if with_rose and concentric:
        # azimuth rose: spokes every 30 deg out to the footprint edge, with degree
        # labels and cardinal letters set clear OUTSIDE the red circle.
        for az in range(0, 360, 30):
            ax.plot([math.radians(az), math.radians(az)], [0, fr],
                    color="#a0a0a0", linewidth=LW_SPOKE, zorder=2)
        edge_cap = rmax * (PAGE_W_IN / PLOT_DIAMETER_IN) * 0.95
        gap = max(4.0, rmax * 0.06)
        deg_r = min(fr + gap, edge_cap - gap)
        card_r = min(fr + gap * 2.2, edge_cap)
        if card_r <= deg_r:
            card_r = deg_r + gap
        for az in range(0, 360, 30):
            if az % 90 != 0:
                ax.text(math.radians(az), deg_r, "%d\u00b0" % az, ha="center",
                        va="center", fontsize=FS_AZLABEL, color="#444444",
                        fontweight="bold", zorder=3)
        for az, name in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
            ax.text(math.radians(az), card_r, name, ha="center", va="center",
                    fontsize=FS_CARDINAL, fontweight="bold", zorder=3)

        # inner km distance rings (2-3 rings), labelled on the 135 deg spoke
        foot_km = foot_deg * KM_PER_DEG
        step_km = _km_ring_step(foot_km)
        th = [math.radians(a) for a in range(0, 361, 2)]
        km = step_km
        while km < foot_km - step_km * 0.25:
            rho = km / KM_PER_DEG
            ax.plot(th, [rho] * len(th), color="#9a9a9a", linewidth=LW_RING,
                    zorder=2)
            ax.text(math.radians(135), rho, "%d\u00a0km" % km,
                    fontsize=FS_RINGLABEL, color="#555555", ha="center",
                    va="bottom", fontweight="bold", zorder=3)
            km += step_km

    # the footprint circle + centre cross, in the SAME red / weight everywhere.
    # Drawn whenever the footprint is concentric with the sheet, regardless of
    # whether the rose was drawn, so the combined QTH map gets a clean red circle.
    if concentric:
        th1 = [math.radians(a) for a in range(0, 361, 1)]
        ax.plot(th1, [fr] * len(th1), color="#cc0000", linewidth=LW_FOOT,
                zorder=4)
        ax.plot([0], [0], marker="+", color="black", markersize=MARK_CROSS,
                markeredgewidth=MEW_CROSS, zorder=5)


def _footprint_page(pdf, sat_name, alt_km, proj, rmax, reduced_text=False):
    foot_deg = A.footprint_radius_deg(alt_km)
    # The transparency is laid over the chosen base map. On the QTH-centred map a
    # plain circle of radius foot_deg is exact; on the generic POLAR base map that
    # circle re-projects to an oval, so we enlarge it by a fixed,
    # population-optimised factor (a single generic circle for everyone). See
    # POLAR_RANGE_CIRCLE_INFLATION.
    polar_fit = proj.is_polar
    draw_deg = _polar_range_circle_deg(foot_deg) if polar_fit else foot_deg
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    fr = min(draw_deg, rmax)
    if reduced_text:
        # clean transparency: no title/subtitle/footer text outside the circular
        # area. The azimuth labels (from the rose) are the only text outside the
        # circle; the satellite name sits unobtrusively inside it.
        ax = _polar_axes(fig, "", "", rmax=rmax, show_rim=False)
        _draw_footprint_overlay(ax, draw_deg, rmax, with_rose=True)
        ax.text(math.radians(0), fr * 0.18, sat_name, ha="center", va="center",
                fontsize=9, color="#888888", zorder=6)
        pdf.savefig(fig)
        plt.close(fig)
        return
    if polar_fit:
        sub = ("Range-circle radius %.1f\u00b0 (~%d km) at %.0f km mean altitude "
               "\u2014 enlarged ~%.0f%% to best fit the polar map across "
               "latitudes"
               % (foot_deg, round(foot_deg * KM_PER_DEG, -1), alt_km,
                  (POLAR_RANGE_CIRCLE_INFLATION - 1.0) * 100.0))
    else:
        sub = ("Range-circle radius %.1f\u00b0 (~%d km) at %.0f km mean altitude"
               % (foot_deg, round(foot_deg * KM_PER_DEG, -1), alt_km))
    # IMPORTANT: keep the same angular scale (rmax) as the base map and arc
    # sheets so this transparency registers on top of them. We simply don't draw
    # anything beyond the range circle, so the rest of the sheet is clear and the
    # map shows through.
    _fp_suffix = " \u2014 OSCARLOCATOR Range Circle Overlay"
    ax = _polar_axes(fig, _fit_sat_name(sat_name, _fp_suffix) + _fp_suffix,
                     sub, rmax=rmax, show_rim=False)

    # the standalone range circle is concentric with the sheet, so it gets the
    # full rose + km rings + red circle via the shared helper.
    _draw_footprint_overlay(ax, draw_deg, rmax, with_rose=True)
    note = ("Print on transparency at 100%. Pin the centre cross over "
            "your QTH at the map centre. The red circle is the range "
            "circle: the satellite is in range whenever its ground track "
            "(path-arc overlay) is INSIDE the circle. Read AOS and LOS "
            "where the arc crosses the red circle; inner rings are ground "
            "distance, spokes are azimuth. Scale matches the base map.")
    if polar_fit:
        note += (" (On the polar map the true coverage edge is a slight oval; "
                 "this generic circle is sized to fit it well at most "
                 "latitudes.)")
    _draw_footer(fig, note)
    _draw_branding(fig)
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


def _kepler_E(M, e, iters=8):
    """Solve Kepler's equation M = E - e*sin(E) for the eccentric anomaly E."""
    M = (M + math.pi) % (2 * math.pi) - math.pi
    E = M if e < 0.8 else math.pi
    for _ in range(iters):
        E = E - (E - e * math.sin(E) - M) / (1.0 - e * math.cos(E))
    return E


def _canonical_track(sat, descending=False):
    """One orbit of the satellite's ground track as a station-independent set of
    (lon_rel, lat, minute) points. With ``descending`` False the track starts at
    the ASCENDING node (equator crossing going north) at lon 0, minute 0 -- the
    reference for northern-hemisphere sheets. With ``descending`` True it starts
    at the DESCENDING node (crossing going south), the reference for southern-
    hemisphere sheets. Either way minute 0 sits on the equator at sheet-lon 0, so
    the EQX mark on the overlay lines up with the EQX longitude on the map.

    The track is referenced to the chosen node and includes Earth rotation, so it
    can be pinned at the pole and rotated to any pass. Eccentricity is handled via
    Kepler's equation (the satellite sweeps the orbit non-uniformly), and the
    inclination formula handles retrograde (i>90deg) orbits natively -- so this
    follows the real SGP4 ground track closely for both circular and eccentric,
    prograde and retrograde orbits.
    """
    incl = math.radians(sat.incl)
    ecc = max(0.0, min(getattr(sat, "ecc", 0.0) or 0.0, 0.95))
    argp = math.radians(getattr(sat, "argp", 0.0) or 0.0)
    period_min = sat.period_min if sat.period_min else 95.0
    period_s = period_min * 60.0

    # argument of latitude at the chosen node: u = argp + true_anomaly, and at
    # the ascending node u = 0 (descending node u = pi). Solve for the true
    # anomaly nu_node at the node, then its mean anomaly M_node, so we can start
    # the clock there and advance M uniformly in time.
    u_node = math.pi if descending else 0.0
    nu_node = u_node - argp
    E_node = math.atan2(math.sqrt(1 - ecc * ecc) * math.sin(nu_node),
                        ecc + math.cos(nu_node))
    M_node = E_node - ecc * math.sin(E_node)

    n = 361
    pts = []
    for i in range(n):
        frac = i / (n - 1)
        dt = frac * period_s
        # mean anomaly advances uniformly from the node
        M = M_node + 2.0 * math.pi * dt / period_s
        E = _kepler_E(M, ecc)
        nu = math.atan2(math.sqrt(1 - ecc * ecc) * math.sin(E),
                        math.cos(E) - ecc)
        u = argp + nu                              # argument of latitude
        lat = math.degrees(math.asin(math.sin(incl) * math.sin(u)))
        # longitude from the node in the (non-rotating) orbital frame; atan2
        # handles retrograde natively because cos(incl) < 0 for i > 90 deg
        lon = math.degrees(math.atan2(math.cos(incl) * math.sin(u),
                                      math.cos(u)))
        # subtract the node's own orbital longitude so the node sits at sheet-0
        lon_node = math.degrees(math.atan2(math.cos(incl) * math.sin(u_node),
                                           math.cos(u_node)))
        earth = -360.0 * dt / SIDEREAL_DAY_S       # Earth rotation (eastward)
        pts.append((lon - lon_node + earth, lat, frac * period_min))
    return pts


def _arc_page(pdf, pred, sat, proj, rmax, reduced_text=False):
    """The satellite 'overhead': its orbit ground-track for one revolution, with
    1-minute ticks (longer every 10 min) and an inset showing the per-pass
    advance angle.

    In QTH mode the arc is the rotatable canonical track centred on the station
    sub-pole. In polar mode it is the orbit ground-track drawn directly on the
    pole-centred map (PE1RAH 'overhead' style): rotate the whole transparency to
"""
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    shift = _node_shift_deg(sat)
    if reduced_text:
        # clean transparency: no title/subtitle outside the circle
        ax = _polar_axes(fig, "", "", rmax=rmax, proj=proj)
    else:
        _arc_suffix = (" \u2014 OSCARLOCATOR Path Arc (orbit)" if proj.is_polar
                       else " \u2014 OSCARLOCATOR Path Arc Overlay")
        title = _fit_sat_name(sat.name, _arc_suffix) + _arc_suffix
        sub = ("Ground-track \u2014 incl. %.1f\u00b0, period %.1f\u00a0min "
               "\u2014 advance %.1f\u00b0\u00a0%s per pass." % (
                   sat.incl, sat.period_min, abs(shift),
                   "W" if shift < 0 else "E"))
        ax = _polar_axes(fig, title, sub, rmax=rmax, proj=proj)
    _draw_rim_ticks(ax, rmax)
    for rho in range(30, int(rmax) + 1, 30):
        th = [math.radians(a) for a in range(0, 361, 2)]
        ax.plot(th, [rho] * len(th), color="#cccccc", linewidth=LW_GRID)

    track = _canonical_track(sat, descending=proj.is_south)
    th, rr = [], []
    segs = []
    ticks = []
    prev_br = None
    for lon_rel, lat, minute in track:
        # place the orbit track on the sheet using the SAME convention as the
        # base map: colatitude from the relevant pole, bearing = longitude.
        # The conventional (un-mirrored) handedness is set by the axes, so both
        # hemispheres use plain longitude here. The node sits at sheet-longitude
        # 0 (rotate the transparency to the EQX longitude in use).
        ca = (90.0 + lat) if proj.is_south else (90.0 - lat)
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

    # Minute ticks: short straight marks ACROSS the track (perpendicular to the
    # local track direction) so they read consistently all the way along the
    # arc. Major ticks (every 10 min) are longer and labelled; the number is
    # offset to the outside of the curve so it never sits on the line or another
    # tick. We work in Cartesian (x = rho*sin(theta), y = rho*cos(theta) to match
    # the N-up/relevant axes) to get a true perpendicular, then convert back.
    def _xy(theta, rho):
        return rho * math.sin(theta), rho * math.cos(theta)

    def _rt(x, y):
        return math.atan2(x, y), math.hypot(x, y)

    last_min = None
    minor_len = 1.7          # tick half-length (deg of radius) for minor marks
    major_len = 3.4          # longer marks every 10 minutes
    npts = len(ticks)
    # Scale the labelled-tick interval and font with the orbital period so a long
    # high-orbit pass doesn't crowd dozens of numbers along the arc. Minor ticks
    # stay at 1 minute; labels appear every ``label_step`` minutes.
    per = sat.period_min if sat.period_min else 95.0
    label_step = 10
    for cand in (10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300):
        if per / cand <= 14:
            label_step = cand
            break
    else:
        label_step = max(10, int(round(per / 14.0 / 10.0)) * 10)
    n_labels = max(1, int(per) // label_step + 1)
    label_fs = (FS_TICKLABEL + 1 if n_labels <= 12
                else FS_TICKLABEL if n_labels <= 18 else FS_TICKLABEL - 1.5)
    for i, (thb, ca, minute) in enumerate(ticks):
        mm = int(round(minute))
        if mm == last_min:
            continue
        if abs(minute - mm) > (sat.period_min / (len(track) - 1)) / 2 + 1e-6:
            continue
        major = (mm % label_step == 0)
        # local track direction from neighbouring track points
        j0 = max(i - 1, 0)
        j1 = min(i + 1, npts - 1)
        x0, y0 = _xy(ticks[j0][0], ticks[j0][1])
        x1, y1 = _xy(ticks[j1][0], ticks[j1][1])
        dx, dy = x1 - x0, y1 - y0
        dn = math.hypot(dx, dy) or 1.0
        # unit perpendicular to the track
        px, py = -dy / dn, dx / dn
        cx, cy = _xy(thb, ca)
        hl = major_len if major else minor_len
        ax_pts_x = [cx - px * hl, cx + px * hl]
        ax_pts_y = [cy - py * hl, cy + py * hl]
        seg_t = [_rt(x, y)[0] for x, y in zip(ax_pts_x, ax_pts_y)]
        seg_r = [_rt(x, y)[1] for x, y in zip(ax_pts_x, ax_pts_y)]
        ax.plot(seg_t, seg_r, color="#001f7a" if major else "#2255cc",
                linewidth=3.0 if major else 1.8, zorder=5,
                solid_capstyle="butt")
        if major and mm != 0:
            # place the number just beyond the OUTER end of the tick, pushed a
            # little further along the perpendicular so it clears the arc.
            # Minute 0 is omitted: it sits on the equator-crossing node where the
            # EQX indicator and its "0 min" label already are, so the number is
            # superfluous and collides.
            lx = cx + px * (hl + 3.2)
            ly = cy + py * (hl + 3.2)
            lt, lr = _rt(lx, ly)
            ax.text(lt, lr, "%d" % mm, fontsize=label_fs,
                    color="#001f7a", ha="center", va="center",
                    fontweight="bold", zorder=6)
        last_min = mm

    # --- EQX alignment marker: minute 0 sits on the equator at sheet-lon 0.
    # Draw a bold arrowed line from the centre out through that point to the rim
    # and label it, so the user knows exactly which radial to line up with the
    # EQX longitude on the base map.
    node = "descending node" if proj.is_south else "ascending node"
    eqx_th = 0.0                       # sheet-longitude 0 is the node meridian
    ax.annotate("", xy=(eqx_th, rmax), xytext=(eqx_th, 0),
                arrowprops=dict(arrowstyle="-|>", color="#cc0000",
                                lw=LW_INDICATOR), zorder=7)
    # Axes are 0deg at the bottom. North map: theta increases CCW, so the
    # ascending-node track climbs the right/upper side and the clear area is the
    # LEFT (theta ~250). South map: theta increases CW, so the descending track
    # climbs the LEFT side and the clear area is the RIGHT (theta ~290).
    lbl_th = math.radians(290) if proj.is_south else math.radians(250)
    # The hemisphere/node DOES matter on the arc sheet (the arc is built from the
    # ascending node for northern sheets, the descending node for southern), so
    # state it right at the EQX indicator the user lines up. Keep the box compact
    # (short wrapped wording, smaller font) and a bit inboard so it doesn't crowd
    # the outer rim circle.
    node_label = ("descending node\n(S sheet)" if proj.is_south
                  else "ascending node\n(N sheet)")
    ax.text(lbl_th, rmax * 0.52,
            "EQX \u2014 0 min\n%s\nline up on map" % node_label,
            color="#cc0000", fontsize=FS_BIGLABEL - 3, fontweight="bold",
            ha="center", va="center", rotation=0, zorder=8,
            linespacing=1.3,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#cc0000",
                      lw=1.0, alpha=0.92))

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
    # the per-pass rotation indicator sits OUTSIDE the rim; in reduced-text mode
    # keep the sheet clean (nothing outside the circle), since the advance angle
    # is already stated inside the circle.
    if not reduced_text:
        r_ind = rmax * 1.18  # radius of the indicator arc, beyond the plot edge
        half = math.radians(abs(shift)) / 2.0
        # The arc must sit in the clear band at the TOP of the printed page. The
        # azimuth (QTH) sheet has theta=0 at the top, but the polar sheets put
        # theta=0 at the BOTTOM (zero-location "S") -- there the page top is
        # theta=180. Centre the arc on whichever theta points up, so it never
        # drops onto the footer text at the bottom of the sheet.
        top = math.pi if (proj is not None and proj.is_polar) else 0.0
        a_lo, a_hi = top - half, top + half
        arc = [a_lo + (a_hi - a_lo) * k / 60 for k in range(61)]
        ax.plot(arc, [r_ind] * len(arc), color="#cc0000",
                linewidth=LW_INDICATOR, zorder=7, clip_on=False,
                solid_capstyle="round")
        # Put the arrowhead on the correct END for the on-screen sense. The
        # theta->screen mapping differs by projection (zero-location and
        # direction), so resolve "which end is screen-left" geometrically rather
        # than from raw theta ordering: project both ends to display pixels and
        # pick by x. CCW sweep -> head on the LEFT end; CW -> the RIGHT end.
        try:
            px_lo = ax.transData.transform((a_lo, r_ind))[0]
            px_hi = ax.transData.transform((a_hi, r_ind))[0]
        except Exception:
            px_lo, px_hi = (0.0, 1.0)
        left_ang = a_lo if px_lo <= px_hi else a_hi
        right_ang = a_hi if px_lo <= px_hi else a_lo
        tip = left_ang if ccw else right_ang
        # the short tail sits just inside the arc, toward its centre angle
        pre = tip + math.copysign(math.radians(0.6), top - tip)
        ax.annotate("", xy=(tip, r_ind), xytext=(pre, r_ind),
                    arrowprops=dict(arrowstyle="-|>", color="#cc0000",
                                    lw=LW_INDICATOR),
                    annotation_clip=False, zorder=8)
    # numeric label sitting above the arc, in the top margin. The node always
    # drifts west geographically; we also state the on-sheet turn sense.
    geo = "west" if west else "east"
    sense = "counter-clockwise" if ccw else "clockwise"
    if not reduced_text:
        fig.text(0.5, 0.862,
                 "rotate sheet %.1f\u00b0 %s (node moves %s) each pass"
                 % (abs(shift), sense, geo),
                 ha="center", va="bottom", fontsize=FS_BIGLABEL, color="#cc0000",
                 fontweight="bold")

    if reduced_text:
        # The only text on this transparency sits INSIDE the circle: the
        # satellite name and key orbit facts. Place it in the clearest part of
        # the sheet -- the track's geometry varies a lot with inclination and
        # hemisphere (prograde tracks climb one side, retrograde the other), so
        # rather than a fixed angle we find the widest angular gap that the track
        # (and the red EQX box) leave open, and drop the label at a mid radius
        # there. This keeps it off the track and off the EQX marker for any orbit.
        occupied = set()
        for tth, trho, _m in ticks:
            # only the mid-band radii matter for a label placed at ~0.6 rmax;
            # ignore track points very close to the centre or right at the rim
            if 0.30 * rmax <= trho <= 0.92 * rmax:
                occupied.add(int(math.degrees(tth)) % 360)
        # block the wedge around the EQX box (theta 250 N / 290 S, +/-25 deg)
        eqx_deg = 290 if proj.is_south else 250
        for d in range(eqx_deg - 28, eqx_deg + 29):
            occupied.add(d % 360)
        # also keep clear of the vertical EQX arrow (straight up, theta ~0/360)
        for d in list(range(0, 12)) + list(range(348, 360)):
            occupied.add(d % 360)
        # find the widest contiguous gap of free degrees
        free = [d for d in range(360) if d not in occupied]
        best_centre = 200                          # sensible fallback
        if free:
            # rotate the circle so gaps don't wrap; scan for the longest run
            runs = []
            start = free[0]
            prev = free[0]
            for d in free[1:] + [free[0] + 360]:
                if d == prev + 1:
                    prev = d
                else:
                    runs.append((start, prev))
                    start = d % 360 if d < 360 else d - 360
                    prev = d
            if runs:
                s, e = max(runs, key=lambda r: r[1] - r[0])
                best_centre = int(((s + e) / 2.0)) % 360
        info = ("%s\nincl %.1f\u00b0   \u2022   period %.1f min\n"
                "advance %.1f\u00b0 %s per pass"
                % (sat.name, sat.incl, sat.period_min, abs(shift),
                   "W" if shift < 0 else "E"))
        ax.text(math.radians(best_centre), rmax * 0.6, info, color="#333333",
                fontsize=8.5, ha="center", va="center", linespacing=1.5,
                zorder=9,
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#cccccc",
                          lw=0.8, alpha=0.9))
        pdf.savefig(fig)
        plt.close(fig)
        return

    if proj.is_polar:
        node = "descending node" if proj.is_south else "ascending node"
        note = ("Print on transparency at 100%%. Lay over the polar base map "
                "with centres aligned and the %s at the EQX longitude, then "
                "rotate the whole sheet %.1f\u00b0 %s about the centre for each "
                "successive pass (see the rim arrow). Tick marks count minutes "
                "after the EQX, with longer labelled marks every 10 minutes." % (
                    node, abs(shift),
                    "westward" if shift < 0 else "eastward"))
    else:
        note = ("Print on transparency at 100%%. Pin the centre cross over the "
                "station, then rotate the arc %.1f\u00b0 %s about the centre for "
                "each successive pass (see the rim arrow). Tick marks count "
                "minutes after the EQX, with longer labelled marks every 10 "
                "minutes." % (
                    abs(shift), "westward" if shift < 0 else "eastward"))
    _draw_footer(fig, note)
    _draw_branding(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _dest_point(lat, lon, dist_deg, bearing_deg):
    """Point at angular distance ``dist_deg`` and ``bearing_deg`` from (lat,lon),
    returned as (lat, lon) in degrees. Same great-circle math as the footprint
    locus, for a single bearing (used to place ring labels)."""
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    d = math.radians(dist_deg)
    brg = math.radians(bearing_deg)
    lat2 = math.asin(math.sin(p1) * math.cos(d) +
                     math.cos(p1) * math.sin(d) * math.cos(brg))
    lon2 = l1 + math.atan2(math.sin(brg) * math.sin(d) * math.cos(p1),
                           math.cos(d) - math.sin(p1) * math.sin(lat2))
    return math.degrees(lat2), (math.degrees(lon2) + 540.0) % 360.0 - 180.0


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


def _draw_qth_rings_projected(ax, proj, obs, alt_km, rmax, foot_deg):
    """Draw the QTH-centred elevation rings (and km distance rings) onto a map
    where the QTH is NOT at the sheet centre -- e.g. the polar map -- by walking
    each small circle around the station and projecting it. On the polar map the
    rings come out as the correct off-centre ovals so the operator can still read
    elevation and ground distance to the sub-point. Labels are placed where each
    ring crosses the QTH->due-south bearing so they sit on a tidy line."""
    if not alt_km:
        return
    # elevation rings (skip 0 deg: that's the footprint edge, drawn in red)
    for el in (10, 30, 60):
        rho = A.central_angle_for_elevation_deg(el, alt_km)
        if rho is None or rho >= foot_deg:
            continue
        locus = _footprint_locus(obs.lat, obs.lon, rho)
        _project_polyline(ax, proj, [(lon, lat) for lat, lon in locus],
                          "#9a9a9a", LW_RING, 3, rmax)
        # (no numeric elevation label here -- the ring itself is the cue, and a
        # number on the footprint duplicates the base map's elevation rings)
    # km distance rings out to the footprint edge
    foot_km = foot_deg * KM_PER_DEG
    step_km = _km_ring_step(foot_km)
    km = step_km
    while km < foot_km - step_km * 0.25:
        rdeg = km / KM_PER_DEG
        locus = _footprint_locus(obs.lat, obs.lon, rdeg)
        _project_polyline(ax, proj, [(lon, lat) for lat, lon in locus],
                          "#bdbdbd", LW_GRID, 3, rmax)
        llat, llon = _dest_point(obs.lat, obs.lon, rdeg, 135.0)
        lr, lb = proj.project(llat, llon)
        if lr <= rmax:
            ax.text(math.radians(lb), lr, "%d\u00a0km" % km,
                    fontsize=FS_RINGLABEL, color="#777777", ha="center",
                    va="bottom", fontweight="bold", zorder=4)
        km += step_km


def _base_map_with_footprint_page(pdf, proj, obs, qth_name, segments, rmax,
                                  foot_deg, sat_name="", alt_km=None,
                                  reduced_text=False):
    """Combined sheet: the base map plus the satellite range circle drawn at the
    station's position. The range circle is always centred on the QTH (when the
    satellite is overhead), so this single sheet shows the coverage directly on
    the map -- no separate transparency needed."""
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    foot_km = round(foot_deg * KM_PER_DEG, -1)
    # use non-breaking spaces (\u00a0) inside value+unit groups so the line
    # wrapper never breaks "2240 km", "20.2 deg" or "(~2240 km)" across lines
    size = "range-circle radius %.1f\u00b0 (~%d\u00a0km)" % (foot_deg, foot_km)
    if alt_km:
        size += " at %.0f\u00a0km mean altitude" % alt_km
    if proj.is_polar:
        hemi = "southern" if proj.is_south else "northern"
        _suffix = " \u2014 OSCARLOCATOR \u2014 Map + Range Circle at QTH (%s)" % hemi
        nm = _fit_sat_name(sat_name, _suffix) if sat_name else ""
        title = (nm + _suffix) if nm else \
            "OSCARLOCATOR \u2014 Map + Range Circle at QTH (%s)" % hemi
        sub = ("Range circle over %s on the %s polar map \u2014 %s"
               % (qth_name, hemi, size))
    else:
        _suffix = " \u2014 OSCARLOCATOR \u2014 Map + Range Circle at QTH"
        nm = _fit_sat_name(sat_name, _suffix) if sat_name else ""
        title = (nm + _suffix) if nm else \
            "OSCARLOCATOR \u2014 Map + Range Circle at QTH"
        sub = ("Range circle over %s (%.3f, %.3f) \u2014 %s"
               % (qth_name, obs.lat, obs.lon, size))
    ax = _polar_axes(fig, title, sub, rmax=rmax, proj=proj)
    _draw_graticule(ax, proj, rmax)
    _draw_coastlines(ax, proj, segments, rmax)
    _draw_rim_ticks(ax, rmax)

    if proj.is_polar:
        # Polar map with a QTH: the station is OFF the sheet centre, so draw the
        # graticule spokes/rings of the polar map, then add the QTH-centred
        # elevation + distance rings as projected (off-centre) loci, and the
        # footprint as a projected locus too. Keep the red footprint style.
        _draw_az_grid(ax, proj, rmax, alt_km=None, skip_horizon=True)
        _draw_qth_rings_projected(ax, proj, obs, alt_km, rmax, foot_deg)
        locus = _footprint_locus(obs.lat, obs.lon, min(foot_deg, rmax))
        _project_polyline(ax, proj, [(lon, lat) for lat, lon in locus],
                          "#cc0000", LW_FOOT, 5, rmax)
        # QTH-centre marker (cross, to match the standalone overlay's centre)
        q_rho, q_br = proj.project(obs.lat, obs.lon)
        if q_rho <= rmax:
            ax.plot([math.radians(q_br)], [q_rho], marker="+", color="black",
                    markersize=MARK_CROSS, markeredgewidth=MEW_CROSS, zorder=6)
            ax.plot([math.radians(q_br)], [q_rho], marker="*", color="#cc0000",
                    markersize=13, zorder=7)
    else:
        # QTH-centred map: the sheet IS azimuthal-equidistant about the station,
        # so the footprint is concentric. Draw the elevation rings (still useful
        # as the visual cue) but WITHOUT their numeric labels, and draw the
        # footprint with with_rose=False so it's a clean red circle + cross -- the
        # base map underneath already carries the azimuth spokes/labels and the
        # elevation rings, so repeating the azimuth numbers/letters and the
        # "deg el" labels on the footprint would just duplicate that.
        _draw_az_grid(ax, proj, rmax, alt_km=alt_km, skip_horizon=True,
                      dist_rings=False, label_el=False)
        _draw_footprint_overlay(ax, foot_deg, rmax, with_rose=False)
        # mark the QTH itself at the centre
        ax.plot([0], [0], marker="*", color="#cc0000", markersize=13, zorder=7)
    if reduced_text:
        note = (
            "OSCARLOCATOR \u2014 print this sheet on paper/card at 100%% (actual "
            "size) and print the path-arc overlay on transparency at 100%%. The "
            "red circle is the satellite's range circle, centred on your station "
            "(red star); spokes are azimuth and rim ticks are 1\u00b0. Pin the "
            "path-arc through the centre, rotate it %s to the node longitude from "
            "the Crossings List, then %s for each successive pass. The satellite "
            "is workable while its track is inside the red circle; read AOS/LOS "
            "where the track crosses it." % (
                "to", "rotate by the per-pass advance"))
    else:
        note = (
            "Print on paper or card at 100%. The red circle is the satellite's "
            "range circle when it is directly over your station (red star). The "
            "base map's spokes give azimuth and the rings inside the circle give "
            "elevation and ground distance to the sub-point. Use the separate "
            "path-arc overlay to see when the satellite enters this circle.")
    _draw_footer(fig, note)
    _draw_branding(fig)
    pdf.savefig(fig)
    plt.close(fig)


def generate_oscarlocator_pdf(path, store, sat, when_unix=None,
                              projection="qth", footprint_on_qth=False,
                              reduced_text=False):
    """Write an OSCARLOCATOR PDF for ``sat``.

    Standard output (``footprint_on_qth`` False) is 3 pages: base map, range
    circle overlay (transparency), orbit/arc overlay (transparency).

    With ``footprint_on_qth`` True the output is a 2-page set: page 1 is the base
    map with the satellite range circle drawn directly at the station (no separate
    transparency needed), and page 2 is the path-arc overlay. Available for both
    the QTH-centred and the polar maps.

    With ``reduced_text`` True the transparencies are kept visually clean: the
    base map carries ALL the printed how-to-use instructions, and the overlay
    sheets put nothing outside their circular area except the azimuth labels --
    the range-circle transparency just names the satellite unobtrusively inside
    the circle, and the path-arc transparency lists the satellite name,
    inclination, period and per-pass advance inside the circle. The base map in
    this mode is kept generic (no satellite-specific text) so it can be reused
    with any satellite -- except that, when the range circle is drawn on the QTH
    map, the satellite name appears inside that circle.

    ``projection`` selects the base map:
      * "qth"         - azimuthal-equidistant map centred on the station.
      * "polar"       - North-pole-centred polar great-circle map (PE1RAH
                        OSCARLOCATOR style; generic, usable by anyone with the
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
        # Cap the QTH map so it doesn't extend far into the opposite hemisphere
        # (which crowds the equator/EQX line near the rim and distorts heavily).
        # Reach the equator (|lat| away from the station) plus a 25 deg band so
        # the EQX longitude line is clearly placeable, but stop well short of the
        # full 90 deg hemisphere. Clamp to a sensible 50-80 deg window.
        rmax = max(50.0, min(80.0, abs(obs.lat) + 25.0))

    pred = Predictor()
    pred.set_site(obs)
    pred.set_sat(sat)
    # Size the footprint / QTH reticle to the MAX ground distance the satellite
    # is ever visible -- i.e. the footprint radius at the satellite's MEAN
    # orbital altitude (semi-major axis minus Earth radius), not the
    # instantaneous altitude at a single moment.
    _sma = A.semi_major_axis_km(sat.mean_motion)
    alt_km = max(_sma - RE_KM, 1.0) if _sma > 0 else \
        pred.subpoint_at(when_unix)[2]
    foot_deg = A.footprint_radius_deg(alt_km)

    segments = _coastline_segments()
    with PdfPages(path) as pdf:
        if footprint_on_qth:
            # 2-page set: map+range-circle, then the path arc
            _base_map_with_footprint_page(pdf, proj, obs, qth_name, segments,
                                          rmax, foot_deg, sat_name=sat.name,
                                          alt_km=alt_km,
                                          reduced_text=reduced_text)
            _arc_page(pdf, pred, sat, proj, rmax, reduced_text=reduced_text)
        else:
            # standard 3-page set: map, range-circle transparency, path arc
            _base_map_page(pdf, proj, qth_name, segments, rmax,
                           alt_km=alt_km, sat_name=sat.name,
                           reduced_text=reduced_text)
            _footprint_page(pdf, sat.name, alt_km, proj, rmax,
                            reduced_text=reduced_text)
            _arc_page(pdf, pred, sat, proj, rmax, reduced_text=reduced_text)
        d = pdf.infodict()
        kind = {"polar": "polar-north", "polar-south": "polar-south"}.get(
            projection, "QTH-centred")
        d["Title"] = "OSCARLOCATOR (%s) \u2014 %s" % (kind, sat.name)
        d["Subject"] = "Printable base map, footprint and orbit overlays"
        d["Creator"] = "OrbitDeck"
    return path
