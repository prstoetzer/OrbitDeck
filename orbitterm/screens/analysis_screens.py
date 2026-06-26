"""orbitterm/screens/analysis_screens.py - orbital analysis and ground track."""

import time
import math

from ..ui import Screen, addstr, cp, ljust
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_OK, CLR_WARN, CLR_BAD, CLR_DIM,
                  CLR_ACCENT)
from .. import fmt
from orbitdeck.engine import analysis as an


class OrbitalAnalysisScreen(Screen):
    title = "Orbital Analysis"
    refresh_secs = 2.0

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        now = time.time()
        if sat is None:
            addstr(win, y0, x0, "No satellite selected (press 2).", cp(CLR_WARN))
            return
        addstr(win, y0, x0, sat.name, cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + len(sat.name) + 2, "#%d  %s" % (
            sat.norad, sat.intl_des if hasattr(sat, "intl_des") else ""),
            cp(CLR_DIM))

        mm = sat.mean_motion
        a = an.semi_major_axis_km(mm)
        node, perigee = an.j2_rates(mm, sat.incl, sat.ecc)
        alt_apo = sat.apogee_km
        alt_per = sat.perigee_km
        mean_alt = a - 6378.135
        foot_d = an.footprint_diameter_km(mean_alt)
        repeat = an.repeat_ground_track(mm)
        longest = an.longest_possible_pass_min(mm, sat.ecc)
        gt_shift = an.groundtrack_shift_deg(mm)
        beta_star = an.beta_star_deg(mean_alt)
        sunsync = an.is_sun_synchronous(node)
        try:
            ltan = an.ltan_hours(sat.raan, now)
        except Exception:
            ltan = None
        decay = an.estimate_decay_days(sat.bstar, mm, sat.ecc)

        col2 = x0 + max(40, w // 2)
        rows_left = [
            ("Mean motion", "%.6f rev/day" % mm),
            ("Period", "%.2f min" % sat.period_min),
            ("Semi-major axis", "%.1f km" % a),
            ("Apogee alt", "%.1f km" % alt_apo),
            ("Perigee alt", "%.1f km" % alt_per),
            ("Eccentricity", "%.5f" % sat.ecc),
            ("Inclination", "%.4f\u00b0" % sat.incl),
            ("RAAN", "%.3f\u00b0" % sat.raan),
            ("Arg perigee", "%.3f\u00b0" % sat.argp),
        ]
        rows_right = [
            ("Footprint dia", "%.0f km" % foot_d),
            ("Node drift", "%+.3f\u00b0/day" % node),
            ("Perigee drift", "%+.3f\u00b0/day" % perigee),
            ("Sun-synchronous", "yes" if sunsync else "no"),
            ("LTAN", ("%.2f h" % ltan) if ltan is not None else "--"),
            ("Beta* threshold", "%.1f\u00b0" % beta_star),
            ("Track shift/orbit", "%.2f\u00b0 W" % abs(gt_shift)),
            ("Repeat track", repeat or "no short cycle"),
            ("Longest pass", "%.1f min" % longest),
        ]
        addstr(win, y0 + 2, x0, "Elements & geometry", cp(CLR_HEADER) | _bold())
        addstr(win, y0 + 2, col2, "Derived", cp(CLR_HEADER) | _bold())
        y = y0 + 3
        for lab, val in rows_left:
            addstr(win, y, x0, ljust(lab, 18), cp(CLR_DIM))
            addstr(win, y, x0 + 18, val)
            y += 1
        y = y0 + 3
        for lab, val in rows_right:
            addstr(win, y, col2, ljust(lab, 18), cp(CLR_DIM))
            addstr(win, y, col2 + 18, val)
            y += 1

        # decay line
        yb = y0 + 3 + max(len(rows_left), len(rows_right)) + 1
        addstr(win, yb, x0, "Decay estimate", cp(CLR_HEADER) | _bold())
        dtxt = an.fmt_decay(decay)
        dattr = cp(CLR_BAD) if (decay and decay < 365) else cp(CLR_OK)
        addstr(win, yb, x0 + 18, dtxt, dattr)
        addstr(win, yb, x0 + 18 + len(dtxt) + 2,
               "(B* %.2e)" % sat.bstar, cp(CLR_DIM))

        # live mean/true anomaly
        yb += 1
        ma = an.mean_anomaly_now_deg(sat.ma, mm, now, sat.epoch_unix)
        ta = an.true_anomaly_deg(ma, sat.ecc)
        addstr(win, yb, x0, "Anomaly now", cp(CLR_HEADER) | _bold())
        addstr(win, yb, x0 + 18, "M %.1f\u00b0   \u03bd %.1f\u00b0   u %.1f\u00b0"
               % (ma, ta, an.arg_of_latitude_deg(sat.argp, ta)))

        if st.pred_for(sat).deepspace_approximate():
            addstr(win, y0 + h - 1, x0,
                   "deep-space orbit: positions approximate (no full SDP4)",
                   cp(CLR_WARN))

    def help_keys(self):
        return [("[ ]", "prev/next sat")]

    def handle_key(self, ch):
        if ch in (ord("["), ord("]")):
            self.app.cycle_sat(-1 if ch == ord("[") else 1)
            return True
        return False


# A coarse equirectangular coastline mask for the ASCII world map. We render a
# land/sea grid by sampling a compact set of lon/lat land rectangles. This keeps
# the map dependency-free and tiny; it is a schematic, not a precise coastline.
class GroundTrackScreen(Screen):
    title = "Ground Track"
    refresh_secs = 2.0

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        now = time.time()
        if sat is None:
            addstr(win, y0, x0, "No satellite selected (press 2).", cp(CLR_WARN))
            return
        pred = st.pred_for(sat)
        addstr(win, y0, x0, sat.name, cp(CLR_TITLE) | _bold())
        L = pred.look(now)
        addstr(win, y0, x0 + len(sat.name) + 2,
               "sub-point %s  alt %.0f km" % (
                   fmt.fmt_latlon(L.sub_lat, L.sub_lon), L.alt_km),
               cp(CLR_DIM))

        # map area
        my0 = y0 + 2
        mw = w - 2
        mh = h - 3
        if mw < 20 or mh < 8:
            addstr(win, my0, x0, "(terminal too small for map)", cp(CLR_DIM))
            return

        grid = [[" "] * mw for _ in range(mh)]
        # land
        for ry in range(mh):
            lat = 90 - (ry + 0.5) / mh * 180
            for rx in range(mw):
                lon = -180 + (rx + 0.5) / mw * 360
                if _is_land(lat, lon):
                    grid[ry][rx] = "\u2591"
        # equator + prime meridian
        eq = int((90 - 0) / 180 * mh)
        for rx in range(mw):
            if grid[eq][rx] == " ":
                grid[eq][rx] = "\u00b7"

        def to_cell(lat, lon):
            rx = int((lon + 180) / 360 * mw)
            ry = int((90 - lat) / 180 * mh)
            return max(0, min(mw - 1, rx)), max(0, min(mh - 1, ry))

        # render base map
        for ry in range(mh):
            addstr(win, my0 + ry, x0, "".join(grid[ry]), cp(CLR_DIM))

        # ground track: +/- one period sampled
        per = (sat.period_min or 95) * 60
        n = 180
        track = []
        for i in range(n + 1):
            t = now - per + (2 * per) * i / n
            la, lo, _ = pred.subpoint_at(t)
            track.append((t, la, lo))
        for t, la, lo in track:
            rx, ry = to_cell(la, lo)
            past = t <= now
            ch = "." if past else "+"
            addstr(win, my0 + ry, x0 + rx, ch,
                   cp(CLR_DIM) if past else cp(CLR_ACCENT))

        # footprint circle (coverage) around current sub-point
        foot_deg = an.footprint_radius_deg(L.alt_km)
        for k in range(72):
            brg = math.radians(k * 5)
            la2, lo2 = _dest(L.sub_lat, L.sub_lon, foot_deg, math.degrees(brg))
            rx, ry = to_cell(la2, lo2)
            if grid_ok(rx, ry, mw, mh):
                addstr(win, my0 + ry, x0 + rx, "\u00b0", cp(CLR_WARN))

        # the satellite itself
        rx, ry = to_cell(L.sub_lat, L.sub_lon)
        addstr(win, my0 + ry, x0 + rx, "\u25c9",
               cp(CLR_OK) | _bold() if L.sunlit else cp(CLR_BAD) | _bold())
        # observer
        orx, ory = to_cell(st.obs.lat, st.obs.lon)
        addstr(win, my0 + ory, x0 + orx, "\u25b2", cp(CLR_ACCENT) | _bold())

        addstr(win, y0 + h - 1, x0,
               "\u25c9 sat   \u25b2 you   + future track   . past   "
               "\u00b0 footprint", cp(CLR_DIM))

    def help_keys(self):
        return [("[ ]", "prev/next sat")]

    def handle_key(self, ch):
        if ch in (ord("["), ord("]")):
            self.app.cycle_sat(-1 if ch == ord("[") else 1)
            return True
        return False


def grid_ok(rx, ry, mw, mh):
    return 0 <= rx < mw and 0 <= ry < mh


def _dest(lat, lon, dist_deg, bearing_deg):
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    d = math.radians(dist_deg)
    brg = math.radians(bearing_deg)
    lat2 = math.asin(math.sin(p1) * math.cos(d) +
                     math.cos(p1) * math.sin(d) * math.cos(brg))
    lon2 = l1 + math.atan2(math.sin(brg) * math.sin(d) * math.cos(p1),
                           math.cos(d) - math.sin(p1) * math.sin(lat2))
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


# Compact schematic land test: a set of lon/lat boxes approximating the
# continents at world-map scale. Good enough to orient the eye; not a coastline.
_LAND_BOXES = [
    # (lat_min, lat_max, lon_min, lon_max)
    (7, 72, -168, -52),     # North America
    (-56, 12, -82, -34),    # South America
    (35, 71, -10, 40),      # Europe
    (-35, 37, -18, 52),     # Africa
    (5, 78, 40, 180),       # Asia
    (-45, -10, 112, 154),   # Australia
    (-90, -63, -180, 180),  # Antarctica
    (60, 84, -55, -12),     # Greenland
]


def _is_land(lat, lon):
    for la0, la1, lo0, lo1 in _LAND_BOXES:
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return True
    return False


def _bold():
    import curses
    return curses.A_BOLD
