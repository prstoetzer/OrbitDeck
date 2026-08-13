"""orbitterm/screens/oscarsim.py - an on-screen OSCARLOCATOR for the terminal.

The OSCARLOCATOR is the classic paper device: an azimuthal-equidistant base map
with a rotatable transparent overlay carrying the satellite's ground-track arc.
You pin the arc's ascending node to the equator-crossing longitude, then read the
satellite's position minute by minute after the crossing.

This is the same instrument drawn on the braille canvas, which suits it - it is
almost entirely line art (rim, graticule, track arc, footprint circle).

Projection conventions match the printable OSCARLOCATOR and the desktop screen:

  * polar (north): rho = 90 - lat, theta = longitude, 0 deg at the bottom,
    east counter-clockwise
  * QTH-centered: rho = great-circle distance in degrees, theta = bearing,
    north at the top, clockwise

Modes: LIVE follows the satellite's real current position and EQX; MANUAL lets
you rotate the overlay by hand and step the minutes after the crossing, exactly
as you would slide the paper disc.
"""

import curses
import math
import time

from ..ui import Screen, addstr, cp, clip
from ..ui import CLR_TITLE, CLR_DIM, CLR_OK, CLR_WARN, CLR_ACCENT, CLR_HEADER
from ..canvas import Canvas, blit

from orbitdeck.engine.predict import Predictor

RE_KM = 6378.135
SIDEREAL_DAY_S = 86164.0905


class OscarSimScreen(Screen):
    title = "OSCARLOCATOR"
    refresh_secs = 5.0

    MODES = ["polar", "qth"]

    def __init__(self, app):
        super().__init__(app)
        self.mode = 0
        self.live = True
        self.eqx_lon = 0.0          # ascending-node longitude of the overlay
        self.minutes = 0.0          # minutes after the equator crossing
        self.status = "m map   L live/manual   arrows rotate/step"

    # ---- projection ----
    def _project(self, lat, lon):
        if self.MODES[self.mode] == "polar":
            rho = 90.0 - lat
            theta = math.radians(lon)
            return rho, theta, "polar"
        o = self.state.store.obs
        rho, brg = _gc(o.lat, o.lon, lat, lon)
        return rho, math.radians(brg), "qth"

    def _to_px(self, lat, lon, cx, cy, r, rmax):
        rho, theta, kind = self._project(lat, lon)
        if rho > rmax:
            return None
        rr = rho / rmax * r
        if kind == "polar":
            # 0 deg longitude at the bottom, east counter-clockwise
            x = cx - rr * math.sin(theta)
            y = cy + rr * math.cos(theta)
        else:
            # north up, clockwise bearings
            x = cx + rr * math.sin(theta)
            y = cy - rr * math.cos(theta)
        return x, y

    # ---- overlay geometry ----
    def _arc_points(self, sat, n=180):
        """Ground-track arc for one orbit, pinned to the overlay's EQX.

        Rather than propagating (which would tie the arc to real time), this is
        the closed-form track of a circular orbit at the satellite's inclination
        with Earth rotating beneath - which is exactly what the paper overlay
        encodes.
        """
        incl = math.radians(getattr(sat, "incl", 51.6) or 51.6)
        mm = getattr(sat, "mean_motion", 15.0) or 15.0
        period = 86400.0 / mm
        pts = []
        for i in range(n + 1):
            frac = i / n
            u = 2 * math.pi * frac                      # argument of latitude
            lat = math.degrees(math.asin(math.sin(incl) * math.sin(u)))
            dlon = math.degrees(math.atan2(math.cos(incl) * math.sin(u),
                                           math.cos(u)))
            drift = 360.0 * (frac * period) / SIDEREAL_DAY_S
            lon = _wrap(self.eqx_lon + dlon - drift)
            pts.append((lat, lon, frac * period / 60.0))
        return pts

    def _sat_point(self, sat):
        """Where the overlay says the satellite is, for the current minutes."""
        incl = math.radians(getattr(sat, "incl", 51.6) or 51.6)
        mm = getattr(sat, "mean_motion", 15.0) or 15.0
        period = 86400.0 / mm
        secs = self.minutes * 60.0
        u = 2 * math.pi * (secs / period)
        lat = math.degrees(math.asin(math.sin(incl) * math.sin(u)))
        dlon = math.degrees(math.atan2(math.cos(incl) * math.sin(u),
                                       math.cos(u)))
        drift = 360.0 * secs / SIDEREAL_DAY_S
        return lat, _wrap(self.eqx_lon + dlon - drift)

    def _sync_live(self, sat, pred):
        """Pin the overlay to the real satellite: last ascending node + elapsed."""
        t = time.time()
        try:
            nodes = pred.ascending_nodes(t - 2 * 3600.0, t + 60.0)
        except Exception:
            nodes = []
        if not nodes:
            return False
        node = nodes[-1]
        tn = node[0] if isinstance(node, (tuple, list)) else node
        try:
            _la, lo, _al = pred.subpoint_at(tn)
        except Exception:
            return False
        self.eqx_lon = lo
        self.minutes = max(0.0, (t - tn) / 60.0)
        return True

    # ---- drawing ----
    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        if sat is None:
            addstr(win, y0, x0, "No satellite selected.", cp(CLR_WARN))
            return
        pred = Predictor()
        pred.set_site(st.store.obs)
        pred.set_sat(sat)
        if self.live:
            self._sync_live(sat, pred)

        kind = self.MODES[self.mode]
        rmax = 90.0 if kind == "polar" else 90.0
        addstr(win, y0, x0, clip(
            "OSCARLOCATOR \u2014 %s map \u2014 %s" % (
                "north polar" if kind == "polar" else "QTH centered",
                "LIVE" if self.live else "MANUAL"), w), cp(CLR_TITLE))

        rows = max(4, h - 3)
        cols = min(max(12, w - 24), rows * 2)
        cv = Canvas(cols, rows)
        cx, cy = cv.width // 2, cv.height // 2
        r = min(cx, cy) - 1
        cv.circle(cx, cy, r, cp(CLR_DIM))
        for frac in (1.0 / 3.0, 2.0 / 3.0):
            cv.circle(cx, cy, max(1, int(r * frac)), cp(CLR_DIM))
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            cv.line(cx, cy, cx + r * math.sin(a), cy - r * math.cos(a),
                    cp(CLR_DIM))

        # the ground-track arc from the overlay
        prev = None
        for lat, lon, _mins in self._arc_points(sat):
            pt = self._to_px(lat, lon, cx, cy, r, rmax)
            if pt and prev and math.hypot(pt[0] - prev[0],
                                          pt[1] - prev[1]) < r:
                cv.line(prev[0], prev[1], pt[0], pt[1], cp(CLR_OK))
            prev = pt

        # the satellite and its footprint
        slat, slon = self._sat_point(sat)
        spt = self._to_px(slat, slon, cx, cy, r, rmax)
        alt = getattr(sat, "apogee_km", 0.0) or 500.0
        foot = math.degrees(math.acos(RE_KM / (RE_KM + alt)))
        prev = None
        for k in range(0, 361, 6):
            la, lo = _dest(slat, slon, foot, k)
            pt = self._to_px(la, lo, cx, cy, r, rmax)
            if pt and prev and math.hypot(pt[0] - prev[0],
                                          pt[1] - prev[1]) < r:
                cv.line(prev[0], prev[1], pt[0], pt[1], cp(CLR_WARN))
            prev = pt
        if spt:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cv.plot(spt[0] + dx, spt[1] + dy, cp(CLR_ACCENT))
        blit(win, cv, y0 + 1, x0)

        # readout
        lx = x0 + cols + 2
        ly = y0 + 1
        addstr(win, ly, lx, "OVERLAY", cp(CLR_HEADER))
        ly += 1
        addstr(win, ly, lx, clip(sat.name, 20), cp(CLR_TITLE))
        ly += 2
        for label, value in (
                ("EQX longitude", "%.1f\u00b0" % self.eqx_lon),
                ("Minutes after", "%.1f" % self.minutes),
                ("Sub-lat", "%.1f\u00b0" % slat),
                ("Sub-lon", "%.1f\u00b0" % slon),
                ("Footprint", "%.1f\u00b0" % foot)):
            addstr(win, ly, lx, clip("%-13s %s" % (label, value),
                                     max(1, x0 + w - lx)), cp(CLR_DIM))
            ly += 1
        ly += 1
        if self.live:
            addstr(win, ly, lx, clip("follows the real orbit",
                                     max(1, x0 + w - lx)), cp(CLR_OK))
        else:
            addstr(win, ly, lx, "left/right rotate EQX", cp(CLR_DIM))
            ly += 1
            addstr(win, ly, lx, "up/down step minutes", cp(CLR_DIM))
        addstr(win, y0 + h - 1, x0, clip(self.status, w), cp(CLR_DIM))

    def handle_key(self, ch):
        if ch == ord("m"):
            self.mode = (self.mode + 1) % len(self.MODES)
            return True
        if ch in (ord("L"), ord("v")):
            self.live = not self.live
            return True
        if ch in (curses.KEY_LEFT, ord("h")):
            self.live = False
            self.eqx_lon = _wrap(self.eqx_lon - 5.0)
            return True
        if ch in (curses.KEY_RIGHT, ord("l")):
            self.live = False
            self.eqx_lon = _wrap(self.eqx_lon + 5.0)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.live = False
            self.minutes += 1.0
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.live = False
            self.minutes = max(0.0, self.minutes - 1.0)
            return True
        return False

    def help_keys(self):
        return [("m", "map"), ("L", "live/manual"), ("arrows", "rotate/step")]


def _wrap(lon):
    return (lon + 540.0) % 360.0 - 180.0


def _gc(lat1, lon1, lat2, lon2):
    """Great-circle distance (deg) and initial bearing (deg)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    cosd = (math.sin(p1) * math.sin(p2)
            + math.cos(p1) * math.cos(p2) * math.cos(dl))
    d = math.degrees(math.acos(max(-1.0, min(1.0, cosd))))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return d, (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _dest(lat, lon, dist_deg, bearing_deg):
    la = math.radians(lat)
    lo = math.radians(lon)
    d = math.radians(dist_deg)
    b = math.radians(bearing_deg)
    la2 = math.asin(math.sin(la) * math.cos(d)
                    + math.cos(la) * math.sin(d) * math.cos(b))
    lo2 = lo + math.atan2(math.sin(b) * math.sin(d) * math.cos(la),
                          math.cos(d) - math.sin(la) * math.sin(la2))
    return math.degrees(la2), _wrap(math.degrees(lo2))
