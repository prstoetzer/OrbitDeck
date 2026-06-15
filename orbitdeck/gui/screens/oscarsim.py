"""oscarsim.py - an interactive on-screen OSCARLOCATOR.

Lets the user play with a virtual OSCARLOCATOR without printing transparencies:
a polar (or QTH-centred) azimuthal-equidistant base map with a rotatable orbit
path-arc overlay and the satellite footprint. The overlay can be driven three
ways:

  * LIVE      - follow the satellite's real current position and EQX.
  * EQX slider- pin the ascending/descending node to a chosen longitude and
                step the minutes-into-orbit to see where the satellite is.
  * NEXT PASS - jump the EQX to the node of the next pass from the station.

The projection conventions match the printable OSCARLOCATOR (north pole: 0 deg
longitude at the bottom, east counter-clockwise; south pole mirrored), so what
you see here is exactly what the printed sheet does.
"""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, COL_BG, fmt_utc, now_unix)
from ...data.worldmap_data import COASTLINES

SIDEREAL_DAY_S = 86164.0905
RE_KM = 6378.135
KM_PER_DEG = math.pi / 180.0 * RE_KM


class OscarSimScreen(Screen):
    def build(self):
        self.sat_header("OSCARLOCATOR Simulator")
        self._mode = tk.StringVar(value="live")
        self._proj_mode = tk.StringVar(value="polar-auto")
        self._eqx_lon = tk.DoubleVar(value=0.0)
        self._minute = tk.DoubleVar(value=0.0)
        self._show_foot = tk.BooleanVar(value=True)

        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        # --- left: controls
        ctrl = ttk.Frame(body, style="Panel.TFrame")
        ctrl.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(ctrl, text="Drive the overlay", style="TLabel",
                  font=("DejaVu Sans", 11, "bold")).pack(anchor="w", padx=10,
                                                         pady=(10, 4))
        for txt, val in (("Live (current position)", "live"),
                         ("Manual EQX + minutes", "manual"),
                         ("Next pass from QTH", "nextpass")):
            ttk.Radiobutton(ctrl, text=txt, value=val, variable=self._mode,
                            command=self._on_mode).pack(anchor="w", padx=14)

        ttk.Separator(ctrl, orient="horizontal").pack(fill="x", pady=8, padx=8)
        ttk.Label(ctrl, text="Base map", style="Muted.TLabel").pack(
            anchor="w", padx=10)
        for txt, val in (("Polar (auto N/S)", "polar-auto"),
                         ("Polar North", "polar"),
                         ("Polar South", "polar-south"),
                         ("QTH-centred", "qth")):
            ttk.Radiobutton(ctrl, text=txt, value=val,
                            variable=self._proj_mode,
                            command=self._render).pack(anchor="w", padx=14)

        ttk.Separator(ctrl, orient="horizontal").pack(fill="x", pady=8, padx=8)
        self._eqx_row = ttk.Frame(ctrl, style="Panel.TFrame")
        self._eqx_row.pack(fill="x", padx=10, pady=2)
        ttk.Label(self._eqx_row, text="EQX longitude", style="Muted.TLabel").pack(
            anchor="w")
        self._eqx_scale = ttk.Scale(self._eqx_row, from_=-180, to=180,
                                    variable=self._eqx_lon,
                                    command=lambda *_: self._render())
        self._eqx_scale.pack(fill="x")
        self._eqx_lbl = tk.StringVar(value="")
        ttk.Label(self._eqx_row, textvariable=self._eqx_lbl,
                  style="Muted.TLabel").pack(anchor="w")

        self._min_row = ttk.Frame(ctrl, style="Panel.TFrame")
        self._min_row.pack(fill="x", padx=10, pady=2)
        ttk.Label(self._min_row, text="Minutes after EQX",
                  style="Muted.TLabel").pack(anchor="w")
        self._min_scale = ttk.Scale(self._min_row, from_=0, to=100,
                                    variable=self._minute,
                                    command=lambda *_: self._render())
        self._min_scale.pack(fill="x")
        self._min_lbl = tk.StringVar(value="")
        ttk.Label(self._min_row, textvariable=self._min_lbl,
                  style="Muted.TLabel").pack(anchor="w")

        ttk.Separator(ctrl, orient="horizontal").pack(fill="x", pady=8, padx=8)
        ttk.Checkbutton(ctrl, text="Show footprint", variable=self._show_foot,
                        command=self._render).pack(anchor="w", padx=14)
        ttk.Button(ctrl, text="Make printable OSCARLOCATOR\u2026",
                   command=self._print).pack(anchor="w", padx=12, pady=10)

        self._readout = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self._readout, style="Muted.TLabel",
                  justify="left").pack(anchor="w", padx=10, pady=(4, 10))

        # --- right: the map
        right = ttk.Frame(body, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.map = MplPanel(right, figsize=(6.4, 6.4), polar=True)
        self.map.pack(fill="both", expand=True, padx=6, pady=6)

    # ---- mode handling -----------------------------------------------------
    def on_show(self):
        self._on_mode()

    def _on_mode(self):
        mode = self._mode.get()
        # show/hide the manual sliders
        manual = (mode == "manual")
        for w in (self._eqx_row, self._min_row):
            if manual:
                w.pack(fill="x", padx=10, pady=2)
            else:
                w.pack_forget()
        # the 'minutes after EQX' slider should span exactly one orbit
        s = self.sat()
        if s is not None:
            per = s.period_min if s.period_min else 95.0
            try:
                self._min_scale.configure(to=round(per))
            except Exception:
                pass
        if mode == "nextpass":
            self._seed_next_pass()
        self._render()

    def _seed_next_pass(self):
        s = self.sat()
        if not s:
            return
        pred = self.pred()
        t = now_unix()
        south = self.store.obs.lat < 0
        nodes = (pred.descending_nodes(t, t + 3 * 86400) if south
                 else pred.ascending_nodes(t, t + 3 * 86400))
        if nodes:
            tc, lon = nodes[0]
            self._eqx_lon.set(lon)
            self._minute.set(0.0)
            self._seed_unix = tc

    # ---- projection (matches the printable OSCARLOCATOR) -------------------
    def _resolve_proj(self):
        mode = self._proj_mode.get()
        if mode == "polar-auto":
            mode = "polar-south" if self.store.obs.lat < 0 else "polar"
        return mode

    def _project(self, mode, lat, lon):
        """Return (rho_deg, theta_rad) for the chosen projection, in the same
        convention as oscarlocator.py."""
        if mode == "polar":
            rho = 90.0 - lat
            theta = math.radians(lon)            # axes: S-zero, CCW
        elif mode == "polar-south":
            rho = 90.0 + lat
            theta = math.radians(lon)            # axes: S-zero, CW
        else:  # qth
            rho, brg = self._gc(self.store.obs.lat, self.store.obs.lon,
                                lat, lon)
            theta = math.radians(brg)            # axes: N-zero, CW
        return rho, theta

    @staticmethod
    def _gc(lat1, lon1, lat2, lon2):
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dl = math.radians(lon2 - lon1)
        ca = math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * \
            math.cos(dl)
        ca = max(-1.0, min(1.0, ca))
        d = math.degrees(math.acos(ca))
        y = math.sin(dl) * math.cos(p2)
        x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * \
            math.cos(dl)
        brg = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
        return d, brg

    def _setup_axes(self, ax, mode, rmax):
        if mode == "polar":
            ax.set_theta_zero_location("S")
            ax.set_theta_direction(1)
        elif mode == "polar-south":
            ax.set_theta_zero_location("S")
            ax.set_theta_direction(-1)
        else:
            ax.set_theta_zero_location("N")
            ax.set_theta_direction(-1)
        ax.set_rlim(0, rmax)
        ax.set_rticks([])
        ax.set_xticks([])

    # ---- rendering ---------------------------------------------------------
    def _render(self):
        s = self.sat()
        self.map.clear(polar=True)
        ax = self.map.ax
        ax.set_facecolor(COL_PANEL)
        if not s:
            ax.set_title("Select a satellite first.", color=COL_MUTED,
                         fontsize=10)
            self.map.draw()
            return
        mode = self._resolve_proj()
        is_south = (mode == "polar-south")
        if mode in ("polar", "polar-south"):
            rmax = 90.0
        else:
            rmax = max(50.0, min(80.0, abs(self.store.obs.lat) + 25.0))
        self._setup_axes(ax, mode, rmax)

        self._draw_graticule(ax, mode, rmax)
        self._draw_coastlines(ax, mode, rmax)
        self._draw_qth(ax, mode, rmax)

        # figure out the time / EQX to display
        t, eqx_lon, minute = self._current_state(s)
        live = (self._mode.get() == "live")

        # draw the rotated path arc + the satellite marker + footprint
        self._draw_track(ax, mode, rmax, s, eqx_lon)
        self._draw_satellite(ax, mode, rmax, s, t, eqx_lon, minute, live)

        self.map.draw()
        self._update_readout(s, t, eqx_lon, minute)

    def _current_state(self, s):
        """Return (display_time, eqx_lon, minute) for the active mode."""
        pred = self.pred()
        mode = self._mode.get()
        if mode == "live":
            t = now_unix()
            # find the most recent node and the minutes since
            south = self.store.obs.lat < 0
            nodes = (pred.descending_nodes(t - 2 * 3600, t) if south
                     else pred.ascending_nodes(t - 2 * 3600, t))
            if nodes:
                tc, lon = nodes[-1]
                return t, lon, (t - tc) / 60.0
            sp = pred.subpoint_at(t)
            return t, sp[1], 0.0
        if mode == "nextpass":
            tc = getattr(self, "_seed_unix", now_unix())
            minute = self._minute.get()
            return tc + minute * 60.0, self._eqx_lon.get(), minute
        # manual
        minute = self._minute.get()
        return now_unix(), self._eqx_lon.get(), minute

    def _draw_graticule(self, ax, mode, rmax):
        if mode in ("polar", "polar-south"):
            lat_lo = -90 if mode == "polar-south" else 0
            lat_hi = 1 if mode == "polar-south" else 91
            for lon in range(-180, 180, 30):
                pts = [(lon, j) for j in range(lat_lo, lat_hi, 3)]
                self._poly(ax, mode, pts, COL_GRID, 0.5, rmax)
            par_lo = -75 if mode == "polar-south" else 0
            par_hi = 1 if mode == "polar-south" else 76
            for lat in range(par_lo, par_hi, 15):
                pts = [(k, lat) for k in range(-180, 181, 4)]
                self._poly(ax, mode, pts, COL_GRID, 0.5, rmax)
        else:
            for rho in range(30, int(rmax) + 1, 30):
                th = [math.radians(a) for a in range(0, 361, 3)]
                ax.plot(th, [rho] * len(th), color=COL_GRID, linewidth=0.5)
            for az in range(0, 360, 30):
                ax.plot([math.radians(az)] * 2, [0, rmax], color=COL_GRID,
                        linewidth=0.5)

    def _draw_coastlines(self, ax, mode, rmax):
        for poly in self._coastline_polys():
            self._poly(ax, mode, poly, "#5a86a8", 0.7, rmax)

    def _coastline_polys(self):
        """High-resolution coastline polylines as lists of (lon, lat).

        Prefers cartopy's Natural Earth coastline geometry (much denser and more
        accurate than the small bundled outline); falls back to the bundled
        COASTLINES when cartopy isn't installed. The result is cached per session
        so we only build it once."""
        cached = getattr(self, "_coast_cache", None)
        if cached is not None:
            return cached
        polys = self._cartopy_coastlines()
        if not polys:
            polys = [[(lon, lat) for lon, lat in poly] for poly in COASTLINES]
        self._coast_cache = polys
        return polys

    @staticmethod
    def _cartopy_coastlines(resolution="110m"):
        """Return coastline polylines from cartopy/Natural Earth, or [] if
        cartopy isn't available."""
        try:
            import cartopy.feature as cfeature
            from shapely.geometry import LineString, MultiLineString
        except Exception:
            return []
        try:
            feat = cfeature.NaturalEarthFeature("physical", "coastline",
                                                resolution)
            polys = []
            for geom in feat.geometries():
                geoms = (geom.geoms if isinstance(geom, MultiLineString)
                         else [geom])
                for g in geoms:
                    if isinstance(g, LineString):
                        polys.append([(x, y) for x, y in g.coords])
            return polys
        except Exception:
            return []

    def _poly(self, ax, mode, lonlat_pts, color, lw, rmax):
        th, rr = [], []
        prev = None
        for lon, lat in lonlat_pts:
            rho, theta = self._project(mode, lat, lon)
            if rho > rmax:
                if len(th) > 1:
                    ax.plot(th, rr, color=color, linewidth=lw)
                th, rr, prev = [], [], None
                continue
            if prev is not None and abs(theta - prev) > math.pi:
                if len(th) > 1:
                    ax.plot(th, rr, color=color, linewidth=lw)
                th, rr = [], []
            th.append(theta)
            rr.append(rho)
            prev = theta
        if len(th) > 1:
            ax.plot(th, rr, color=color, linewidth=lw)

    def _draw_qth(self, ax, mode, rmax):
        rho, theta = self._project(mode, self.store.obs.lat,
                                   self.store.obs.lon)
        if rho <= rmax:
            ax.plot([theta], [rho], marker="*", color=COL_WARN, markersize=13,
                    zorder=6)

    def _canonical_track(self, s, descending):
        incl = math.radians(s.incl)
        retro = s.incl > 90.0
        period_min = s.period_min if s.period_min else 95.0
        u0 = math.pi if descending else 0.0
        lon0 = math.degrees(math.atan2(math.cos(incl) * math.sin(u0),
                                       math.cos(u0)))
        if retro:
            lon0 = -lon0
        pts = []
        for i in range(241):
            frac = i / 240.0
            u = u0 + 2.0 * math.pi * frac
            lat = math.degrees(math.asin(math.sin(incl) * math.sin(u)))
            lon = math.degrees(math.atan2(math.cos(incl) * math.sin(u),
                                          math.cos(u)))
            if retro:
                lon = -lon
            earth = -360.0 * (frac * period_min * 60.0) / SIDEREAL_DAY_S
            pts.append((lon - lon0 + earth, lat, frac * period_min))
        return pts

    def _draw_track(self, ax, mode, rmax, s, eqx_lon):
        is_south = (mode == "polar-south")
        track = self._canonical_track(s, descending=is_south)
        th, rr = [], []
        prev = None
        ticks = []
        for lon_rel, lat, minute in track:
            lon = lon_rel + eqx_lon
            if mode == "polar":
                rho = 90.0 - lat
                theta = math.radians(lon)
            elif mode == "polar-south":
                rho = 90.0 + lat
                theta = math.radians(lon)
            else:
                rho, brg = self._gc(self.store.obs.lat, self.store.obs.lon,
                                    lat, lon)
                theta = math.radians(brg)
            if rho > rmax:
                if len(th) > 1:
                    ax.plot(th, rr, color=COL_ACCENT, linewidth=2.0, zorder=4)
                th, rr, prev = [], [], None
                continue
            if prev is not None and abs(theta - prev) > math.pi:
                if len(th) > 1:
                    ax.plot(th, rr, color=COL_ACCENT, linewidth=2.0, zorder=4)
                th, rr = [], []
            th.append(theta)
            rr.append(rho)
            ticks.append((theta, rho, minute))
            prev = theta
        if len(th) > 1:
            ax.plot(th, rr, color=COL_ACCENT, linewidth=2.0, zorder=4)
        # minute ticks every 10 min
        for theta, rho, minute in ticks:
            if abs(minute - round(minute)) < 0.25 and int(round(minute)) % 10 == 0:
                ax.plot([theta], [rho], marker="o", markersize=4,
                        color="#9ecbff", zorder=5)
                ax.text(theta, rho, "  %d" % int(round(minute)), fontsize=7,
                        color="#9ecbff", zorder=6)

    def _track_point(self, s, eqx_lon, minute, is_south):
        """Sub-point (lat, lon) ON the drawn pass arc at the given minute after
        the EQX. This is the same idealised track the arc is plotted from, so the
        marker always sits exactly on the line."""
        incl = math.radians(s.incl)
        retro = s.incl > 90.0
        period_min = s.period_min if s.period_min else 95.0
        u0 = math.pi if is_south else 0.0
        lon0 = math.degrees(math.atan2(math.cos(incl) * math.sin(u0),
                                       math.cos(u0)))
        if retro:
            lon0 = -lon0
        frac = (minute / period_min)
        u = u0 + 2.0 * math.pi * frac
        lat = math.degrees(math.asin(math.sin(incl) * math.sin(u)))
        lon = math.degrees(math.atan2(math.cos(incl) * math.sin(u),
                                      math.cos(u)))
        if retro:
            lon = -lon
        earth = -360.0 * (frac * period_min * 60.0) / SIDEREAL_DAY_S
        return lat, (lon - lon0 + earth) + eqx_lon

    def _to_polar(self, mode, lat, lon):
        if mode == "polar":
            return 90.0 - lat, math.radians(lon)
        if mode == "polar-south":
            return 90.0 + lat, math.radians(lon)
        rho, brg = self._gc(self.store.obs.lat, self.store.obs.lon, lat, lon)
        return rho, math.radians(brg)

    def _draw_satellite(self, ax, mode, rmax, s, t, eqx_lon, minute, live):
        """Draw the satellite marker. In live mode it follows the true current
        sub-point; in manual / next-pass mode it slides along the drawn arc as
        the 'minutes after EQX' changes. The footprint is ALWAYS centred on the
        QTH (the OSCARLOCATOR range reticle is a fixed QTH-centred overlay)."""
        pred = self.pred()
        is_south = (mode == "polar-south")
        if live:
            lat, lon, alt = pred.subpoint_at(t)
        else:
            lat, lon = self._track_point(s, eqx_lon, minute, is_south)
            # altitude from the ephemeris (near-constant for these orbits)
            _a, _o, alt = pred.subpoint_at(now_unix())
        rho, theta = self._to_polar(mode, lat, lon)
        if rho <= rmax:
            ax.plot([theta], [rho], marker="o", markersize=9,
                    color=COL_ACCENT2, markeredgecolor="white",
                    markeredgewidth=1.0, zorder=8)
        # footprint circle, always centred on the QTH
        if self._show_foot.get():
            foot = self._footprint_deg(alt)
            self._draw_footprint(ax, mode, rmax, self.store.obs.lat,
                                 self.store.obs.lon, foot)

    @staticmethod
    def _footprint_deg(alt_km):
        re = RE_KM
        x = re / (re + max(alt_km, 1.0))
        return math.degrees(math.acos(max(-1.0, min(1.0, x))))

    def _draw_footprint(self, ax, mode, rmax, qlat, qlon, foot_deg):
        p1 = math.radians(qlat)
        l1 = math.radians(qlon)
        d = math.radians(foot_deg)
        th, rr = [], []
        prev = None
        for i in range(0, 361, 4):
            brg = math.radians(i)
            lat2 = math.asin(math.sin(p1) * math.cos(d) +
                             math.cos(p1) * math.sin(d) * math.cos(brg))
            lon2 = l1 + math.atan2(math.sin(brg) * math.sin(d) * math.cos(p1),
                                   math.cos(d) - math.sin(p1) * math.sin(lat2))
            la = math.degrees(lat2)
            lo = (math.degrees(lon2) + 540) % 360 - 180
            if mode == "polar":
                rho = 90.0 - la
                theta = math.radians(lo)
            elif mode == "polar-south":
                rho = 90.0 + la
                theta = math.radians(lo)
            else:
                rho, brg2 = self._gc(self.store.obs.lat, self.store.obs.lon,
                                     la, lo)
                theta = math.radians(brg2)
            if rho > rmax:
                if len(th) > 1:
                    ax.plot(th, rr, color="#d29922", linewidth=1.4, zorder=5)
                th, rr, prev = [], [], None
                continue
            if prev is not None and abs(theta - prev) > math.pi:
                if len(th) > 1:
                    ax.plot(th, rr, color="#d29922", linewidth=1.4, zorder=5)
                th, rr = [], []
            th.append(theta)
            rr.append(rho)
            prev = theta
        if len(th) > 1:
            ax.plot(th, rr, color="#d29922", linewidth=1.4, zorder=5)

    def _update_readout(self, s, t, eqx_lon, minute):
        pred = self.pred()
        lat, lon, alt = pred.subpoint_at(t)
        az, el = pred.azel_at(t)
        vis = "VISIBLE" if el > 0 else "below horizon"
        hemi_e = "E" if eqx_lon >= 0 else "W"
        self._eqx_lbl.set("%.1f\u00b0 %s" % (abs(eqx_lon), hemi_e))
        self._min_lbl.set("%.0f min after EQX" % minute)
        self._readout.set(
            "Sub-point: %.1f\u00b0%s, %.1f\u00b0%s\n"
            "Altitude: %.0f km\n"
            "From your QTH: az %.0f\u00b0, el %.0f\u00b0 (%s)\n"
            "Time: %s UTC" % (
                abs(lat), "N" if lat >= 0 else "S",
                abs(lon), "E" if lon >= 0 else "W",
                alt, az % 360, el, vis,
                fmt_utc(t, "%Y-%m-%d %H:%M:%S")))

    def on_tick(self):
        # keep the live view moving
        if self._mode.get() == "live":
            self._render()

    def _print(self):
        s = self.sat()
        if not s:
            return
        from tkinter import filedialog, messagebox
        from ..oscarlocator import generate_oscarlocator_pdf
        mode = self._proj_mode.get()
        proj = "polar-auto" if mode == "polar-auto" else mode
        default = "oscarlocator_%s.pdf" % s.name.replace("/", "-").replace(
            " ", "_")
        path = filedialog.asksaveasfilename(
            title="Save OSCARLOCATOR PDF", defaultextension=".pdf",
            initialfile=default, filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_oscarlocator_pdf(path, self.store, s, projection=proj)
        except Exception as e:
            messagebox.showerror("OSCARLOCATOR", "Could not generate PDF:\n%s"
                                 % e)
            return
        self.app.set_status("Saved OSCARLOCATOR PDF: %s" % path)
        messagebox.showinfo("OSCARLOCATOR",
                            "Saved a printable OSCARLOCATOR for %s." % s.name)
