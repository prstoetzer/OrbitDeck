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


def _polar_axes(fig, title, subtitle, rmax=MAP_RADIUS_DEG):
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
    fig.text(0.5, 0.95, title, ha="center", va="top", fontsize=15,
             fontweight="bold")
    if subtitle:
        fig.text(0.5, 0.915, subtitle, ha="center", va="top", fontsize=9,
                 color="#333333")
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


def _project_polyline(ax, qlat, qlon, pts, color, lw, zorder):
    """Project a (lon,lat) polyline into the azimuthal map, breaking it where it
    leaves the hemisphere or wraps across the rim."""
    th, rr, prev_br = [], [], None
    for lon, lat in pts:
        ca, br = _central_angle_bearing(qlat, qlon, lat, lon)
        if ca > MAP_RADIUS_DEG:
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


def _draw_coastlines(ax, qlat, qlon, segments):
    for seg in segments:
        _project_polyline(ax, qlat, qlon, seg, "#7799aa", 0.35, 2)


def _draw_graticule(ax, qlat, qlon):
    """Parallels and meridians every 15 deg, projected into the map."""
    for lon in range(-180, 180, 15):
        pts = [(lon, j) for j in range(-90, 91, 2)]
        _project_polyline(ax, qlat, qlon, pts, "#e2e2e2", 0.4, 1)
    for lat in range(-75, 76, 15):
        pts = [(k, lat) for k in range(-180, 181, 2)]
        _project_polyline(ax, qlat, qlon, pts, "#e2e2e2", 0.4, 1)


def _draw_az_grid(ax):
    for az in range(0, 360, 15):
        ax.plot([math.radians(az), math.radians(az)], [0, MAP_RADIUS_DEG],
                color="#cfcfcf", linewidth=0.4, zorder=1)
    for az in range(0, 360, 30):
        ax.text(math.radians(az), MAP_RADIUS_DEG * 1.04, "%d\u00b0" % az,
                ha="center", va="center", fontsize=7, color="#666666")
    for az, name in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
        ax.text(math.radians(az), MAP_RADIUS_DEG * 1.11, name, ha="center",
                va="center", fontsize=11, fontweight="bold")
    for rho in range(30, int(MAP_RADIUS_DEG) + 1, 30):
        th = [math.radians(a) for a in range(0, 361, 2)]
        ax.plot(th, [rho] * len(th), color="#bdbdbd", linewidth=0.6, zorder=1)
        ax.text(math.radians(45), rho, "%d km" % round(rho * KM_PER_DEG, -2),
                fontsize=6, color="#888888", ha="center", va="bottom")
    ax.plot([0], [0], marker="+", color="black", markersize=14,
            markeredgewidth=2, zorder=6)


def _base_map_page(pdf, qlat, qlon, qth_name, segments):
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    sub = "Azimuthal-equidistant map centred on %s  (%.3f, %.3f)" % (
        qth_name, qlat, qlon)
    ax = _polar_axes(fig, "OSCARLOCATOR \u2014 Base Map", sub)
    _draw_graticule(ax, qlat, qlon)
    _draw_coastlines(ax, qlat, qlon, segments)
    _draw_az_grid(ax)
    fig.text(0.5, 0.05,
             "Print on paper or card at 100% (actual size). Overlays register "
             "on the centre cross; rings are great-circle distance, spokes are "
             "azimuth, grey graticule is lat/lon (15\u00b0).",
             ha="center", va="bottom", fontsize=8, color="#555555", wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def _footprint_page(pdf, sat_name, alt_km):
    foot_deg = A.footprint_radius_deg(alt_km)
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    sub = ("Footprint radius %.1f\u00b0 (~%d km) at %.0f km altitude"
           % (foot_deg, round(foot_deg * KM_PER_DEG, -1), alt_km))
    ax = _polar_axes(fig, "%s \u2014 Footprint Overlay" % sat_name, sub)
    for az in range(0, 360, 15):
        ax.plot([math.radians(az), math.radians(az)], [0, MAP_RADIUS_DEG],
                color="#dddddd", linewidth=0.4)
    th = [math.radians(a) for a in range(0, 361, 2)]
    km = 1000
    kmax = MAP_RADIUS_DEG * KM_PER_DEG
    while km <= kmax:
        rho = km / KM_PER_DEG
        ax.plot(th, [rho] * len(th), color="#cccccc", linewidth=0.5)
        ax.text(math.radians(60), rho, "%d km" % km, fontsize=6,
                color="#999999", ha="center", va="bottom")
        km += 1000
    th1 = [math.radians(a) for a in range(0, 361, 1)]
    ax.plot(th1, [foot_deg] * len(th1), color="#cc0000", linewidth=1.8)
    ax.fill(th1, [foot_deg] * len(th1), color="#cc0000", alpha=0.05)
    ax.plot([0], [0], marker="+", color="black", markersize=14,
            markeredgewidth=2)
    fig.text(0.5, 0.05,
             "Print on transparency at 100%. Pin the centre cross over the "
             "station; the red circle is the area that can work the satellite "
             "when its sub-point is at the centre. Rings: 1000 km; radials: "
             "15\u00b0.",
             ha="center", va="bottom", fontsize=8, color="#555555", wrap=True)
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


def _arc_page(pdf, pred, sat, qlat, qlon):
    """Classic rotatable any-orbit ground-track arc, with 1-minute ticks (longer
    every 10 min) and an inset showing the per-pass advance angle.

    The arc is rendered station-independently: it is the satellite's ground
    track for one orbit centred so the ascending node is at the pole, drawn in
    az-equidistant about the centre. Pin at the centre and rotate to the orbit.
    """
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    shift = _node_shift_deg(sat)
    sub = ("Ground-track arc \u2014 inclination %.1f\u00b0, period %.1f min. "
           "Advance %.1f\u00b0 %s per pass." % (
               sat.incl, sat.period_min, abs(shift),
               "W" if shift < 0 else "E"))
    ax = _polar_axes(fig, "%s \u2014 Path Arc Overlay" % sat.name, sub)
    for rho in range(30, int(MAP_RADIUS_DEG) + 1, 30):
        th = [math.radians(a) for a in range(0, 361, 2)]
        ax.plot(th, [rho] * len(th), color="#dddddd", linewidth=0.4)

    # The rotatable arc: take the canonical ground track and place it about the
    # station's sub-pole. We treat the track's latitude as colatitude from the
    # centre (central angle = 90 - lat) and its relative longitude as bearing.
    # This yields the characteristic crossing arc independent of the QTH.
    track = _canonical_track(sat)
    th, rr = [], []
    segs = []
    ticks = []
    prev_br = None
    for lon_rel, lat, minute in track:
        ca = 90.0 - lat                  # colatitude: node region near the rim
        br = (lon_rel + 360.0) % 360.0
        if ca > MAP_RADIUS_DEG:
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
        ax.plot(sth, srr, color="#0044cc", linewidth=1.6, zorder=4)

    # 1-minute ticks, longer/labelled every 10 minutes
    last_min = None
    for thb, ca, minute in ticks:
        mm = int(round(minute))
        if mm == last_min:
            continue
        if abs(minute - mm) <= (sat.period_min / (len(track) - 1)) / 2 + 1e-6:
            major = (mm % 10 == 0)
            ax.plot([thb], [ca], marker="o",
                    markersize=3.2 if major else 1.6,
                    color="#001f7a" if major else "#3366dd", zorder=5)
            if major:
                ax.text(thb, ca - 3, "%d" % mm, fontsize=6, color="#001f7a",
                        ha="center", va="top", zorder=6)
            last_min = mm

    ax.plot([0], [0], marker="+", color="black", markersize=14,
            markeredgewidth=2, zorder=6)

    # per-pass advance inset (bottom-left)
    inset = fig.add_axes([0.06, 0.09, 0.22, 0.22], projection="polar")
    inset.set_theta_zero_location("N")
    inset.set_theta_direction(-1)
    inset.set_rlim(0, 1)
    inset.set_rticks([])
    inset.set_xticks([])
    inset.set_facecolor("white")
    a0 = 0.0
    a1 = math.radians(shift)
    inset.plot([a0, a0], [0, 0.85], color="#444444", lw=1.2)
    inset.plot([a1, a1], [0, 0.85], color="#cc0000", lw=1.2, linestyle="--")
    # arc arrow between the two
    arc_th = [a0 + (a1 - a0) * k / 30 for k in range(31)]
    inset.plot(arc_th, [0.6] * 31, color="#cc0000", lw=1.2)
    inset.annotate("", xy=(a1, 0.6), xytext=(a1 * 0.93, 0.6),
                   arrowprops=dict(arrowstyle="->", color="#cc0000", lw=1.4))
    inset.text(math.radians(0), 1.35, "advance per pass", fontsize=6.5,
               ha="center", va="bottom", color="#333333")
    # the numeric advance angle is labelled just below the inset (a polar axes
    # can't place text at a negative radius, so use a figure-relative label)
    fig.text(0.17, 0.075, "%.1f\u00b0 %s/pass" % (abs(shift),
             "W" if shift < 0 else "E"), fontsize=8.5, ha="center",
             color="#cc0000", fontweight="bold")

    fig.text(0.5, 0.04,
             "Print on transparency at 100%%. Pin the centre cross over the "
             "station, then rotate the arc %.1f\u00b0 %s for each successive "
             "pass (inset). Dots are 1-minute marks; larger dots every 10 "
             "minutes." % (abs(shift), "westward" if shift < 0 else "eastward"),
             ha="center", va="bottom", fontsize=8, color="#555555", wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def generate_oscarlocator_pdf(path, store, sat, when_unix=None):
    """Write a 3-page OSCARLOCATOR PDF for ``sat`` centred on the station in
    ``store``. Pages: base map, footprint overlay, rotatable path-arc overlay."""
    import time
    if when_unix is None:
        when_unix = time.time()
    obs = store.obs
    qlat, qlon = obs.lat, obs.lon
    qth_name = store.my_grid()

    pred = Predictor()
    pred.set_site(obs)
    pred.set_sat(sat)
    _lat, _lon, alt_km = pred.subpoint_at(when_unix)

    segments = _coastline_segments()
    with PdfPages(path) as pdf:
        _base_map_page(pdf, qlat, qlon, qth_name, segments)
        _footprint_page(pdf, sat.name, alt_km)
        _arc_page(pdf, pred, sat, qlat, qlon)
        d = pdf.infodict()
        d["Title"] = "OSCARLOCATOR \u2014 %s" % sat.name
        d["Subject"] = "Printable azimuthal map, footprint and path overlays"
        d["Creator"] = "OrbitDeck"
    return path
