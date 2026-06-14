"""worldmap.py - world map with subpoint, footprint, ground track, terminator."""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, now_unix)
from ..mapdraw import draw_basemap, have_cartopy
from ...engine.predict import _sun_eci_unit, _gmst_rad, jd_of, DEG


class WorldMapScreen(Screen):
    live = True

    def build(self):
        self.header("World Map \u2014 footprint, ground track & terminator")
        self.note = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.note, style="Muted.TLabel").pack(
            anchor="w", padx=16)
        wrap = ttk.Frame(self.frame, style="Panel.TFrame")
        wrap.pack(fill="both", expand=True, padx=12, pady=8)
        self.mpl = MplPanel(wrap, figsize=(9.2, 4.8), polar=False)
        self.mpl.pack(fill="both", expand=True, padx=8, pady=8)
        self._counter = 0

    def on_show(self):
        self._render(now_unix())

    def on_tick(self, now_dt):
        self._counter += 1
        if self._counter % 2 == 0:
            self._render(now_dt.timestamp())

    def _render(self, t):
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        draw_basemap(ax)

        self._draw_terminator(ax, t)

        s = self.sat()
        if not s:
            self.note.set("No satellite selected.")
            self.mpl.draw()
            return

        period = s.period_min * 60.0 if s.period_min else 5400.0
        track = []
        for k in range(-60, 61):
            tt = t + (k / 60.0) * period
            lat, lon, alt = self.pred().subpoint_at(tt)
            track.append((lon, lat))
        self._plot_track(ax, track, COL_ACCENT)

        lat, lon, alt = self.pred().subpoint_at(t)
        ax.plot([lon], [lat], "o", color=COL_ACCENT2, markersize=9, zorder=6)
        ax.annotate(s.name, (lon, lat), color=COL_TEXT, fontsize=9,
                    xytext=(5, 5), textcoords="offset points", zorder=7)
        self._draw_footprint(ax, lat, lon, alt)

        ax.plot([self.store.obs.lon], [self.store.obs.lat], "^",
                color=COL_WARN, markersize=10, zorder=6)
        self.note.set("%s  \u2022  sub-point %.2f, %.2f  \u2022  alt %.0f km  "
                      "\u2022  footprint %.0f km" %
                      (s.name, lat, lon, alt,
                       self.pred().footprint_radius_km(alt)))
        self.mpl.draw()

    def _plot_track(self, ax, track, color):
        seg_lon, seg_lat, prev = [], [], None
        for lon, lat in track:
            if prev is not None and abs(lon - prev) > 180:
                ax.plot(seg_lon, seg_lat, color=color, linewidth=1.5, zorder=4)
                seg_lon, seg_lat = [], []
            seg_lon.append(lon)
            seg_lat.append(lat)
            prev = lon
        if seg_lon:
            ax.plot(seg_lon, seg_lat, color=color, linewidth=1.5, zorder=4)

    def _draw_footprint(self, ax, lat0, lon0, alt):
        radius = self.pred().footprint_radius_km(alt)
        ang = radius / 6378.135
        pts = []
        for b in range(0, 361, 5):
            br = math.radians(b)
            la = math.asin(math.sin(math.radians(lat0)) * math.cos(ang) +
                           math.cos(math.radians(lat0)) * math.sin(ang) *
                           math.cos(br))
            lo = math.radians(lon0) + math.atan2(
                math.sin(br) * math.sin(ang) * math.cos(math.radians(lat0)),
                math.cos(ang) - math.sin(math.radians(lat0)) * math.sin(la))
            pts.append((math.degrees(lo), math.degrees(la)))
        seg_lon, seg_lat, prev = [], [], None
        for lo, la in pts:
            lo = ((lo + 180) % 360) - 180
            if prev is not None and abs(lo - prev) > 180:
                ax.plot(seg_lon, seg_lat, color=COL_ACCENT2, linewidth=1.0,
                        alpha=0.85, zorder=5)
                seg_lon, seg_lat = [], []
            seg_lon.append(lo)
            seg_lat.append(la)
            prev = lo
        if seg_lon:
            ax.plot(seg_lon, seg_lat, color=COL_ACCENT2, linewidth=1.0,
                    alpha=0.85, zorder=5)

    def _draw_terminator(self, ax, t):
        jd = jd_of(t)
        sx, sy, sz = _sun_eci_unit(jd)
        th = _gmst_rad(jd)
        ss_lat = math.degrees(math.asin(sz))
        ss_lon = math.degrees(math.atan2(sy, sx) - th)
        ss_lon = ((ss_lon + 180) % 360) - 180
        lons = list(range(-180, 181, 2))
        slat = math.radians(ss_lat)
        slon = math.radians(ss_lon)
        night = []
        for lon in lons:
            lo = math.radians(lon)
            if abs(slat) > 1e-6:
                lat = math.atan(-math.cos(lo - slon) / math.tan(slat))
            else:
                lat = 0.0
            night.append(math.degrees(lat))
        if ss_lat >= 0:
            ax.fill_between(lons, night, -90, color="#000010", alpha=0.42,
                            zorder=2)
        else:
            ax.fill_between(lons, night, 90, color="#000010", alpha=0.42,
                            zorder=2)
        ax.plot([ss_lon], [ss_lat], "o", color=COL_WARN, markersize=6,
                alpha=0.85, zorder=3)
