"""analytics.py - new visualization & analysis screens.

Contains:
  GlobeScreen      - rotatable orthographic 3D-look globe with a time scrubber
  RadarScreen      - all-passes radar (overlaid sky tracks) + sky-coverage heatmap
"""

import math
import tkinter as tk
from tkinter import ttk

import numpy as np

from . import (Screen, MplPanel, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, now_unix, fmt_utc)
from ...engine import planning as PL

DEG = math.pi / 180.0
RE_KM = 6378.135

# distinct marker colours for favorite satellites on the globe / radar
PALETTE = ["#3fb950", "#2f81f7", "#d29922", "#db61a2", "#39c5cf",
           "#f0883e", "#a371f7", "#7ee787", "#ff7b72", "#79c0ff"]


# ===========================================================================
# 3D globe + time scrubber
# ===========================================================================

class GlobeScreen(Screen):
    """An orthographic 'view from space' globe centred on a chosen viewpoint,
    showing the satellite, its ground track, footprint, the day/night
    terminator, and the station -- with a time scrubber to fly forward/back."""

    def build(self):
        self.sat_header("3D Globe")
        self._preds = {}            # norad -> Predictor (for favorites)
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16)
        ttk.Label(bar, text="View:", style="TLabel").pack(side="left")
        self._view = tk.StringVar(value="sat")
        for lab, val in (("Follow satellite", "sat"), ("Over station", "qth"),
                         ("North pole", "north"), ("South pole", "south")):
            ttk.Radiobutton(bar, text=lab, value=val, variable=self._view,
                            command=self._render).pack(side="left", padx=2)
        self._show_favs = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="All favorites", variable=self._show_favs,
                        command=self._render).pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="Now", command=self._reset_now).pack(
            side="right", padx=4)

        # time scrubber
        sb = ttk.Frame(self.frame, style="TFrame")
        sb.pack(fill="x", padx=16, pady=(6, 0))
        ttk.Label(sb, text="Time offset:", style="TLabel").pack(side="left")
        self._offset_min = tk.DoubleVar(value=0.0)
        self._scrub = ttk.Scale(sb, from_=-180, to=180, orient="horizontal", style="Accent.Horizontal.TScale",
                                variable=self._offset_min, command=self._on_scrub)
        self._scrub.pack(side="left", fill="x", expand=True, padx=8)
        self._tlabel = tk.StringVar(value="now")
        ttk.Label(sb, textvariable=self._tlabel, style="Muted.TLabel").pack(
            side="left", padx=6)
        # playback
        pb = ttk.Frame(self.frame, style="TFrame")
        pb.pack(fill="x", padx=16, pady=(4, 0))
        self._playing = False
        self._speed = tk.IntVar(value=60)
        ttk.Button(pb, text="\u25b6 Play", command=self._toggle_play,
                   width=8).pack(side="left")
        ttk.Label(pb, text="Speed (x):", style="TLabel").pack(
            side="left", padx=(10, 2))
        for v in (10, 60, 300, 1800):
            ttk.Radiobutton(pb, text=str(v), value=v, variable=self._speed).pack(
                side="left")
        self._play_btn = pb.winfo_children()[0]

        self.panel = MplPanel(self.frame, figsize=(6.4, 6.0))
        self.panel.pack(fill="both", expand=True, padx=16, pady=10)
        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info,
                  style="Muted.TLabel").pack(anchor="w", padx=16, pady=(0, 8))
        # live at the present moment (favorites advance in real time)
        self.live = True

    def on_show(self):
        self._render()

    def on_tick(self, now=None):
        # keep the globe live at the present moment: when the scrubber is at
        # 'now' and we're not animating a playback, re-render so all favorites
        # advance in real time. (When scrubbed into the past/future, hold still.)
        if not self._playing and abs(self._offset_min.get()) < 0.5:
            self._render()

    def _reset_now(self):
        self._offset_min.set(0.0)
        self._render()

    def _on_scrub(self, _=None):
        self._render()

    def _toggle_play(self):
        self._playing = not self._playing
        self._play_btn.configure(text="\u25fc Stop" if self._playing
                                 else "\u25b6 Play")
        if self._playing:
            self._advance()

    def _advance(self):
        if not self._playing:
            return
        step = self._speed.get() / 60.0   # minutes per ~1s tick
        v = self._offset_min.get() + step
        if v > 180:
            v = -180
        self._offset_min.set(v)
        self._render()
        self.frame.after(1000, self._advance)

    def _disp_time(self):
        return now_unix() + self._offset_min.get() * 60.0

    def _favsats(self):
        return [s for s in self.store.db.sats
                if s.norad in self.store.favorites]

    def _pred_for(self, s):
        p = self._preds.get(s.norad)
        if p is None:
            from ...engine.predict import Predictor
            p = Predictor()
            p.set_site(self.store.obs)
            p.set_sat(s)
            self._preds[s.norad] = p
        return p

    def _render(self):
        s = self.sat()
        t = self._disp_time()
        off = self._offset_min.get()
        self._tlabel.set("now" if abs(off) < 0.5
                         else ("%+d min  (%s)" % (int(off),
                               fmt_utc(t, "%H:%M:%S"))))
        self.panel.clear()
        ax = self.panel.ax
        ax.set_aspect("equal")
        ax.axis("off")
        if not s:
            ax.text(0.5, 0.5, "no satellite selected", color=COL_MUTED,
                    ha="center", transform=ax.transAxes)
            self.panel.draw()
            return
        pred = self.pred()
        sub = pred.subpoint_at(t)
        sub_lat, sub_lon, alt = sub[0], sub[1], sub[2]
        # choose viewpoint (centre of orthographic projection)
        view = self._view.get()
        if view == "sat":
            clat, clon = sub_lat, sub_lon
        elif view == "qth":
            clat, clon = self.store.obs.lat, self.store.obs.lon
        elif view == "north":
            clat, clon = 90.0, 0.0
        else:
            clat, clon = -90.0, 0.0
        self._draw_globe(ax, clat, clon, t, pred, sub_lat, sub_lon, alt)
        self.panel.draw()
        # info line
        az, el = pred.azel_at(t)
        extra = ""
        if self._show_favs.get():
            n = getattr(self, "_fav_count", 0)
            extra = ("   \u2022  %d favorite%s shown live"
                     % (n, "" if n == 1 else "s")) if n else ""
        self.info.set(
            "%s: sub-point %.1f\u00b0, %.1f\u00b0   alt %.0f km   "
            "az %.0f\u00b0 el %.0f\u00b0   %s%s"
            % (s.name, sub_lat, sub_lon, alt, az, el, fmt_utc(t), extra))

    def _ortho(self, lat, lon, clat, clon):
        """Orthographic projection of (lat,lon) for a globe centred at
        (clat,clon). Returns (x, y, visible)."""
        la, lo = lat * DEG, lon * DEG
        cla, clo = clat * DEG, clon * DEG
        cosc = (math.sin(cla) * math.sin(la)
                + math.cos(cla) * math.cos(la) * math.cos(lo - clo))
        x = math.cos(la) * math.sin(lo - clo)
        y = (math.cos(cla) * math.sin(la)
             - math.sin(cla) * math.cos(la) * math.cos(lo - clo))
        return x, y, (cosc >= 0)

    def _draw_globe(self, ax, clat, clon, t, pred, sub_lat, sub_lon, alt):
        # globe disc
        th = np.linspace(0, 2 * math.pi, 200)
        ax.plot(np.cos(th), np.sin(th), color=COL_GRID, lw=1.2)
        ax.add_patch(plt_circle(0, 0, 1.0, "#0b1a2b"))
        # graticule
        for lat in range(-60, 61, 30):
            pts = [self._ortho(lat, lo, clat, clon)
                   for lo in range(-180, 181, 4)]
            xs = [p[0] for p in pts if p[2]]
            ys = [p[1] for p in pts if p[2]]
            ax.plot(xs, ys, color=COL_GRID, lw=0.5, alpha=0.6)
        for lon in range(-180, 181, 30):
            pts = [self._ortho(la, lon, clat, clon)
                   for la in range(-90, 91, 4)]
            xs = [p[0] for p in pts if p[2]]
            ys = [p[1] for p in pts if p[2]]
            ax.plot(xs, ys, color=COL_GRID, lw=0.5, alpha=0.6)
        # coastlines (bundled)
        self._draw_coasts(ax, clat, clon)
        # day/night terminator: shade the night hemisphere
        self._draw_terminator(ax, clat, clon, t, pred)
        # station
        sx, sy, sv = self._ortho(self.store.obs.lat, self.store.obs.lon,
                                 clat, clon)
        if sv:
            ax.plot([sx], [sy], marker="*", color=COL_WARN, markersize=12,
                    zorder=8)

        sel = self.sat()
        sel_norad = sel.norad if sel else None
        # the satellite currently followed/selected: its ground track + marker
        self._draw_track(ax, clat, clon, t, pred)
        self._draw_footprint(ax, clat, clon, sub_lat, sub_lon, alt,
                             color=COL_ACCENT2)
        ssx, ssy, ssv = self._ortho(sub_lat, sub_lon, clat, clon)
        if ssv:
            ax.plot([ssx], [ssy], marker="o", color=COL_ACCENT2,
                    markersize=9, zorder=9)

        # all other favorites as live markers (footprint + dot + label)
        self._fav_count = 0
        if self._show_favs.get():
            for i, fs in enumerate(self._favsats()):
                if fs.norad == sel_norad:
                    self._fav_count += 1
                    continue
                col = PALETTE[i % len(PALETTE)]
                fp = self._pred_for(fs)
                flat, flon, falt = fp.subpoint_at(t)
                fx, fy, fv = self._ortho(flat, flon, clat, clon)
                if not fv:
                    continue          # on the far side of the globe
                self._draw_footprint(ax, clat, clon, flat, flon, falt,
                                     color=col, alpha=0.5)
                ax.plot([fx], [fy], marker="o", color=col, markersize=6,
                        zorder=7)
                ax.annotate(fs.name, (fx, fy), color=COL_TEXT, fontsize=7,
                            xytext=(5, 4), textcoords="offset points",
                            zorder=8, clip_on=True, annotation_clip=True)
                self._fav_count += 1
        ax.set_xlim(-1.08, 1.08)
        ax.set_ylim(-1.08, 1.08)

    def _draw_coasts(self, ax, clat, clon):
        segs = _coastline_segments()
        for seg in segs:
            xs, ys = [], []
            for lat, lon in seg:
                x, y, v = self._ortho(lat, lon, clat, clon)
                if v:
                    xs.append(x)
                    ys.append(y)
                else:
                    if len(xs) > 1:
                        ax.plot(xs, ys, color="#3a6ea5", lw=0.6)
                    xs, ys = [], []
            if len(xs) > 1:
                ax.plot(xs, ys, color="#3a6ea5", lw=0.6)

    def _draw_terminator(self, ax, clat, clon, t, pred):
        # Subsolar point (the spot where the Sun is straight overhead).
        try:
            from ...engine.predict import (_sun_eci_unit, jd_of,
                                           _teme_to_ecef_lla)
            jd = jd_of(t)
            sx, sy, sz = _sun_eci_unit(jd)
            slat, slon, _ = _teme_to_ecef_lla(
                (sx * 1e6, sy * 1e6, sz * 1e6), jd)
        except Exception:
            return

        # Robust night shading: rather than stitch the terminator and limb arcs
        # (which is fragile when the night cap wraps the projection seam), sample
        # the visible disc on a grid, invert the orthographic projection back to
        # (lat, lon), and mark every point whose angular distance from the
        # subsolar point exceeds 90 deg as night. contourf then fills exactly the
        # night region, hugging both the terminator and the limb automatically.
        cla, clo = clat * DEG, clon * DEG
        sla, slo = slat * DEG, slon * DEG
        # unit vector to the subsolar point (for the day/night dot product)
        sun = (math.cos(sla) * math.cos(slo),
               math.cos(sla) * math.sin(slo),
               math.sin(sla))
        # orthographic basis at the view centre: east (e) and north (nth) unit
        # vectors in ECEF, plus the outward centre normal (cen).
        cen = (math.cos(cla) * math.cos(clo),
               math.cos(cla) * math.sin(clo),
               math.sin(cla))
        east = (-math.sin(clo), math.cos(clo), 0.0)
        nth = (-math.sin(cla) * math.cos(clo),
               -math.sin(cla) * math.sin(clo),
               math.cos(cla))

        N = 160
        gx = np.linspace(-1.0, 1.0, N)
        gy = np.linspace(-1.0, 1.0, N)
        X, Y = np.meshgrid(gx, gy)
        # a grid point (x, y) on the visible disc maps to the surface unit vector
        #   p = x*east + y*north + z*cen,  z = sqrt(1 - x^2 - y^2)
        R2 = X * X + Y * Y
        on_disc = R2 <= 1.0
        Z = np.sqrt(np.clip(1.0 - R2, 0.0, 1.0))
        # ECEF components of each grid point's surface normal
        px = X * east[0] + Y * nth[0] + Z * cen[0]
        py = X * east[1] + Y * nth[1] + Z * cen[1]
        pz = X * east[2] + Y * nth[2] + Z * cen[2]
        # cosine of the angle to the Sun; < 0 means more than 90 deg => night
        dot = px * sun[0] + py * sun[1] + pz * sun[2]
        # field: +1 day, -1 night on the disc; NaN off-disc so nothing is filled
        field = np.where(on_disc, np.where(dot < 0.0, -1.0, 1.0), np.nan)
        # fill only the night band (-1 ..  0)
        try:
            ax.contourf(X, Y, field, levels=[-1.0, 0.0],
                        colors=["#000018"], alpha=0.38, zorder=1,
                        antialiased=True)
        except Exception:
            pass
        # draw the terminator line itself for a crisp day/night edge
        try:
            ax.contour(X, Y, field, levels=[0.0], colors=["#1b2a44"],
                       linewidths=0.8, zorder=2)
        except Exception:
            pass

    def _draw_track(self, ax, clat, clon, t, pred):
        P = (self.sat().period_min or 95.0) * 60.0
        xs, ys = [], []
        n = 120
        for i in range(n + 1):
            tt = t - P * 0.5 + (P) * i / n
            sub = pred.subpoint_at(tt)
            x, y, v = self._ortho(sub[0], sub[1], clat, clon)
            if v:
                xs.append(x)
                ys.append(y)
            else:
                if len(xs) > 1:
                    ax.plot(xs, ys, color=COL_ACCENT, lw=1.4, alpha=0.9)
                xs, ys = [], []
        if len(xs) > 1:
            ax.plot(xs, ys, color=COL_ACCENT, lw=1.4, alpha=0.9)

    def _draw_footprint(self, ax, clat, clon, sub_lat, sub_lon, alt,
                        color=COL_ACCENT2, alpha=0.8):
        r = RE_KM + alt
        if r <= RE_KM:
            return
        radius = math.acos(RE_KM / r) / DEG
        pts = []
        for az in range(0, 361, 4):
            la, lo = _dest_point(sub_lat, sub_lon, radius, az)
            x, y, v = self._ortho(la, lo, clat, clon)
            if v:
                pts.append((x, y))
        if len(pts) > 2:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            ax.plot(xs, ys, color=color, lw=1.0, ls="--", alpha=alpha)


# ===========================================================================
# All-passes radar + sky coverage heatmap
# ===========================================================================

class RadarScreen(Screen):
    """Overlay the next N passes of the selected satellite (or all favorites) on
    one polar sky plot, and show a sky-coverage heatmap aggregated over passes.
    """

    def build(self):
        self.sat_header("Sky Radar")
        self._preds = {}            # norad -> Predictor (favorites)
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16)
        ttk.Label(bar, text="Show:", style="TLabel").pack(side="left")
        self._mode = tk.StringVar(value="live")
        ttk.Radiobutton(bar, text="Live (all favorites)", value="live",
                        variable=self._mode, command=self._render).pack(
            side="left", padx=2)
        ttk.Radiobutton(bar, text="All-passes radar", value="overlay",
                        variable=self._mode, command=self._render).pack(
            side="left", padx=2)
        ttk.Radiobutton(bar, text="Sky-coverage heatmap", value="heat",
                        variable=self._mode, command=self._render).pack(
            side="left", padx=2)
        ttk.Label(bar, text="Window (h):", style="TLabel").pack(
            side="left", padx=(12, 2))
        self._hours = tk.IntVar(value=24)
        for v in (6, 12, 24, 48):
            ttk.Radiobutton(bar, text=str(v), value=v, variable=self._hours,
                            command=self._render).pack(side="left")

        self.panel = MplPanel(self.frame, figsize=(6.0, 6.0), polar=True)
        self.panel.pack(fill="both", expand=True, padx=16, pady=10)
        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info,
                  style="Muted.TLabel").pack(anchor="w", padx=16, pady=(0, 8))
        # the live view ticks so satellites move across the sky in real time
        self.live = True

    def on_tick(self, now=None):
        if self._mode.get() == "live":
            self._render()

    def _favsats(self):
        return [s for s in self.store.db.sats
                if s.norad in self.store.favorites]

    def _pred_for(self, s):
        p = self._preds.get(s.norad)
        if p is None:
            from ...engine.predict import Predictor
            p = Predictor()
            p.set_site(self.store.obs)
            p.set_sat(s)
            self._preds[s.norad] = p
        return p

    def on_show(self):
        self._render()

    def _render(self):
        self.panel.clear(polar=True)
        ax = self.panel.ax
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(0, 90)
        ax.set_rgrids([0, 30, 60, 90], labels=["90", "60", "30", "0"],
                      color=COL_MUTED, fontsize=7)
        ax.set_thetagrids(range(0, 360, 45),
                          labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                          color=COL_MUTED, fontsize=8)
        mode = self._mode.get()
        if mode == "live":
            self._draw_live(ax)
            self.panel.draw()
            return
        s = self.sat()
        if not s:
            self.info.set("no satellite selected")
            self.panel.draw()
            return
        pred = self.pred()
        t = now_unix()
        passes = pred.predict_passes(
            t, getattr(self.store, "min_el", 5.0), 60,
            horizon_end=t + self._hours.get() * 3600.0)
        if mode == "overlay":
            self._draw_overlay(ax, pred, passes)
        else:
            self._draw_heat(ax, pred, passes)
        self.panel.draw()

    def _draw_live(self, ax):
        """Show the current sky position (az/el) of every favorite satellite
        that is above the horizon right now -- a live 'radar' of what's up."""
        t = now_unix()
        favs = self._favsats()
        if not favs:
            self.info.set("No favorites yet \u2014 mark some on the Satellites "
                          "screen (space bar) to see them here.")
            return
        up = 0
        for i, s in enumerate(favs):
            p = self._pred_for(s)
            az, el = p.azel_at(t)
            if el < 0:
                continue              # below the horizon, not in the sky now
            col = PALETTE[i % len(PALETTE)]
            ax.plot([az * DEG], [90 - el], marker="o", color=col,
                    markersize=9, zorder=6)
            ax.annotate(s.name, (az * DEG, 90 - el), color=COL_TEXT,
                        fontsize=8, xytext=(5, 4), textcoords="offset points",
                        zorder=7)
            up += 1
        if up:
            self.info.set("%d of %d favorite%s above the horizon now (live; "
                          "centre = zenith, rim = horizon)."
                          % (up, len(favs), "" if len(favs) == 1 else "s"))
        else:
            self.info.set("None of your %d favorite%s is above the horizon "
                          "right now. They'll appear here as they rise."
                          % (len(favs), "" if len(favs) == 1 else "s"))

    def _draw_overlay(self, ax, pred, passes):
        import matplotlib.cm as cm
        n = max(1, len(passes))
        for i, p in enumerate(passes):
            if not (p.aos and p.los):
                continue
            ths, rs = [], []
            tt = p.aos
            while tt <= p.los:
                az, el = pred.azel_at(tt)
                if el >= 0:
                    ths.append(az * DEG)
                    rs.append(90 - el)
                tt += 15.0
            col = cm.viridis(i / n)
            ax.plot(ths, rs, color=col, lw=1.6, alpha=0.85)
            if ths:
                ax.plot([ths[0]], [rs[0]], marker="o", color=col, markersize=4)
        self.info.set("%d passes overlaid (next %dh). Each arc is one pass; "
                      "dot = AOS." % (len(passes), self._hours.get()))

    def _draw_heat(self, ax, pred, passes):
        az_bins, el_bins = 36, 9
        grid = PL.sky_coverage_grid(pred, self.store.obs, passes,
                                    az_bins=az_bins, el_bins=el_bins)
        # render as pcolormesh in polar: theta edges, r edges
        import numpy as np
        theta = np.linspace(0, 2 * math.pi, az_bins + 1)
        r = np.linspace(0, 90, el_bins + 1)
        T, R = np.meshgrid(theta, r)
        # grid[el][az] dwell; map el index 0..el_bins-1 (low->high) to r 90->0
        Z = np.zeros((el_bins, az_bins))
        for ei in range(el_bins):
            for ai in range(az_bins):
                # row 0 of Z is the outer ring (low el); el bin 0 is low el
                Z[el_bins - 1 - ei][ai] = grid[ei][ai]
        ax.pcolormesh(T, R, Z, cmap="inferno", shading="auto")
        total = sum(sum(row) for row in grid)
        self.info.set("Sky-coverage dwell over %d passes (%dh): %.0f min total. "
                      "Brighter = more time spent in that part of your sky."
                      % (len(passes), self._hours.get(), total / 60.0))


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _dest_point(lat, lon, dist_deg, bearing_deg):
    """Destination lat/lon a great-circle angular distance dist_deg from
    (lat,lon) along bearing_deg."""
    la = lat * DEG
    d = dist_deg * DEG
    br = bearing_deg * DEG
    la2 = math.asin(math.sin(la) * math.cos(d)
                    + math.cos(la) * math.sin(d) * math.cos(br))
    lo2 = lon * DEG + math.atan2(
        math.sin(br) * math.sin(d) * math.cos(la),
        math.cos(d) - math.sin(la) * math.sin(la2))
    return la2 / DEG, ((lo2 / DEG + 540) % 360) - 180


def plt_circle(x, y, r, color):
    from matplotlib.patches import Circle
    return Circle((x, y), r, facecolor=color, edgecolor="none", zorder=0)


def plt_polygon(pts, color, alpha):
    from matplotlib.patches import Polygon
    return Polygon(pts, closed=True, facecolor=color, edgecolor="none",
                   alpha=alpha, zorder=1)


_COAST_CACHE = None


def _coastline_segments():
    """Load bundled/cartopy coastline segments as [[(lat,lon),...], ...].
    The oscarlocator helper returns (lon,lat) tuples, so we swap to (lat,lon)."""
    global _COAST_CACHE
    if _COAST_CACHE is not None:
        return _COAST_CACHE
    segs = []
    try:
        from ..oscarlocator import _coastline_segments as _cs
        raw = _cs()
        segs = [[(lat, lon) for (lon, lat) in seg] for seg in raw]
    except Exception:
        segs = []
    _COAST_CACHE = segs
    return segs
