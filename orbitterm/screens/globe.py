"""orbitterm/screens/globe.py - an orthographic wireframe globe in braille.

The desktop app draws a 3D globe with matplotlib; a terminal can do the same job
honestly with an orthographic projection onto the braille sub-cell surface, which
is exactly the kind of line art it suits: graticule, coastline-free limb, ground
track and satellite positions.

The view point is steerable (arrow keys) and can lock to the sub-satellite point,
which is the view that actually answers "what is it over right now".
"""

import curses
import math
import time

from ..ui import Screen, addstr, cp, clip
from ..ui import CLR_TITLE, CLR_DIM, CLR_OK, CLR_WARN, CLR_ACCENT, CLR_HEADER
from ..canvas import Canvas, blit

from orbitdeck.engine.predict import Predictor

RE_KM = 6378.137


class GlobeScreen(Screen):
    title = "3D Globe"
    refresh_secs = 2.0

    def __init__(self, app):
        super().__init__(app)
        self.view_lat = 20.0
        self.view_lon = 0.0
        self.follow = True
        self.show_track = True

    # ---- projection ----
    @staticmethod
    def _project(lat, lon, vlat, vlon, r):
        """Orthographic projection. Returns (x, y, visible)."""
        la, lo = math.radians(lat), math.radians(lon)
        vla, vlo = math.radians(vlat), math.radians(vlon)
        cos_c = (math.sin(vla) * math.sin(la)
                 + math.cos(vla) * math.cos(la) * math.cos(lo - vlo))
        x = r * math.cos(la) * math.sin(lo - vlo)
        y = r * (math.cos(vla) * math.sin(la)
                 - math.sin(vla) * math.cos(la) * math.cos(lo - vlo))
        return x, -y, cos_c >= 0        # screen y grows downward

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        t = time.time()
        pred = Predictor()
        pred.set_site(st.store.obs)

        sub = None
        if sat is not None and pred.set_sat(sat):
            slat, slon, salt = pred.subpoint_at(t)
            sub = (slat, slon, salt)
            if self.follow:
                self.view_lat, self.view_lon = slat, slon

        addstr(win, y0, x0, clip("3D Globe \u2014 view %.0f\u00b0 %.0f\u00b0%s"
                                 % (self.view_lat, self.view_lon,
                                    "  [following]" if self.follow else ""), w),
               cp(CLR_TITLE))

        rows = max(4, h - 2)
        cols = min(max(12, w - 20), rows * 2)
        cv = Canvas(cols, rows)
        cx, cy = cv.width // 2, cv.height // 2
        r = min(cx, cy) - 1
        cv.circle(cx, cy, r, cp(CLR_DIM))

        # graticule: parallels every 30 deg, meridians every 30 deg
        for lat in range(-60, 61, 30):
            prev = None
            for lon in range(-180, 181, 4):
                px, py, vis = self._project(lat, lon, self.view_lat,
                                            self.view_lon, r)
                pt = (cx + px, cy + py) if vis else None
                if pt and prev:
                    cv.line(prev[0], prev[1], pt[0], pt[1], cp(CLR_DIM))
                prev = pt
        for lon in range(-180, 180, 30):
            prev = None
            for lat in range(-90, 91, 4):
                px, py, vis = self._project(lat, lon, self.view_lat,
                                            self.view_lon, r)
                pt = (cx + px, cy + py) if vis else None
                if pt and prev:
                    cv.line(prev[0], prev[1], pt[0], pt[1], cp(CLR_DIM))
                prev = pt

        # observer
        o = st.store.obs
        ox, oy, ovis = self._project(o.lat, o.lon, self.view_lat,
                                     self.view_lon, r)
        if ovis:
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.plot(cx + ox + dx, cy + oy + dy, cp(CLR_ACCENT))

        # ground track and satellite
        if sub is not None:
            if self.show_track:
                mm = getattr(sat, "mean_motion", 0.0) or 15.0
                period = 86400.0 / mm
                prev = None
                for i in range(-60, 61):
                    tt = t + period * i / 120.0
                    try:
                        la, lo, _al = pred.subpoint_at(tt)
                    except Exception:
                        continue
                    px, py, vis = self._project(la, lo, self.view_lat,
                                                self.view_lon, r)
                    pt = (cx + px, cy + py) if vis else None
                    if pt and prev:
                        cv.line(prev[0], prev[1], pt[0], pt[1], cp(CLR_OK))
                    prev = pt
            slat, slon, salt = sub
            sx, sy, svis = self._project(slat, slon, self.view_lat,
                                         self.view_lon, r)
            if svis:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        cv.plot(cx + sx + dx, cy + sy + dy, cp(CLR_WARN))
                # footprint circle
                if salt > 0:
                    half = math.degrees(math.acos(RE_KM / (RE_KM + salt)))
                    prev = None
                    for b in range(0, 361, 5):
                        la, lo = _offset(slat, slon, half, b)
                        px, py, vis = self._project(la, lo, self.view_lat,
                                                    self.view_lon, r)
                        pt = (cx + px, cy + py) if vis else None
                        if pt and prev:
                            cv.line(prev[0], prev[1], pt[0], pt[1],
                                    cp(CLR_WARN))
                        prev = pt

        blit(win, cv, y0 + 1, x0)

        # side legend
        lx = x0 + cols + 2
        ly = y0 + 1
        addstr(win, ly, lx, "GLOBE", cp(CLR_HEADER))
        ly += 1
        if sat is not None and sub:
            addstr(win, ly, lx, clip(sat.name, 18), cp(CLR_TITLE))
            ly += 1
            addstr(win, ly, lx, "sub %.1f %.1f" % (sub[0], sub[1]),
                   cp(CLR_DIM))
            ly += 1
            addstr(win, ly, lx, "alt %.0f km" % sub[2], cp(CLR_DIM))
            ly += 2
        addstr(win, ly, lx, "arrows rotate", cp(CLR_DIM))
        ly += 1
        addstr(win, ly, lx, "f follow sat", cp(CLR_DIM))
        ly += 1
        addstr(win, ly, lx, "t track on/off", cp(CLR_DIM))

    def handle_key(self, ch):
        if ch == ord("f"):
            self.follow = not self.follow
            return True
        if ch == ord("t"):
            self.show_track = not self.show_track
            return True
        if ch in (curses.KEY_LEFT, ord("h")):
            self.follow = False
            self.view_lon = (self.view_lon - 15 + 180) % 360 - 180
            return True
        if ch in (curses.KEY_RIGHT, ord("l")):
            self.follow = False
            self.view_lon = (self.view_lon + 15 + 180) % 360 - 180
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.follow = False
            self.view_lat = min(90.0, self.view_lat + 15)
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.follow = False
            self.view_lat = max(-90.0, self.view_lat - 15)
            return True
        return False

    def help_keys(self):
        return [("arrows", "rotate"), ("f", "follow"), ("t", "track")]


def _offset(lat, lon, dist_deg, bearing_deg):
    """Point ``dist_deg`` of great-circle arc from (lat, lon) on a bearing."""
    la = math.radians(lat)
    lo = math.radians(lon)
    d = math.radians(dist_deg)
    b = math.radians(bearing_deg)
    la2 = math.asin(math.sin(la) * math.cos(d)
                    + math.cos(la) * math.sin(d) * math.cos(b))
    lo2 = lo + math.atan2(math.sin(b) * math.sin(d) * math.cos(la),
                          math.cos(d) - math.sin(la) * math.sin(la2))
    return math.degrees(la2), (math.degrees(lo2) + 540) % 360 - 180
