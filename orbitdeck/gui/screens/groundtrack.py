"""groundtrack.py - forward ground track over several upcoming orbits."""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_TEXT, COL_MUTED, COL_ACCENT, COL_ACCENT2,
               COL_WARN, COL_GRID, now_unix)
from ..mapdraw import draw_basemap


class GroundTrackScreen(Screen):
    def build(self):
        self.header("Ground Track \u2014 forward orbits")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16)
        ttk.Label(bar, text="Orbits ahead:", style="TLabel").pack(side="left")
        self.norbits = tk.IntVar(value=3)
        for v in (1, 3, 5, 8):
            ttk.Radiobutton(bar, text=str(v), value=v, variable=self.norbits,
                            command=self._render).pack(side="left", padx=2)
        wrap = ttk.Frame(self.frame, style="Panel.TFrame")
        wrap.pack(fill="both", expand=True, padx=12, pady=8)
        self.mpl = MplPanel(wrap, figsize=(9, 4.6), polar=False)
        self.mpl.pack(fill="both", expand=True, padx=8, pady=8)

    def on_show(self):
        self._render()

    def _render(self):
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        draw_basemap(ax)
        s = self.sat()
        if not s:
            self.mpl.draw()
            return
        t = now_unix()
        period = s.period_min * 60.0 if s.period_min else 5400.0
        total = period * self.norbits.get()
        steps = int(self.norbits.get() * 180)
        track = []
        for i in range(steps + 1):
            tt = t + total * i / steps
            lat, lon, alt = self.pred().subpoint_at(tt)
            track.append((lon, lat))
        # plot with antimeridian splits, fading color by time
        seg_lon, seg_lat = [], []
        prev = None
        for lon, lat in track:
            if prev is not None and abs(lon - prev) > 180:
                ax.plot(seg_lon, seg_lat, color=COL_ACCENT, linewidth=1.3)
                seg_lon, seg_lat = [], []
            seg_lon.append(lon)
            seg_lat.append(lat)
            prev = lon
        if seg_lon:
            ax.plot(seg_lon, seg_lat, color=COL_ACCENT, linewidth=1.3)
        lat0, lon0, _ = self.pred().subpoint_at(t)
        ax.plot([lon0], [lat0], "o", color=COL_ACCENT2, markersize=9)
        ax.plot([self.store.obs.lon], [self.store.obs.lat], "^",
                color=COL_WARN, markersize=9)
        ax.set_title("%s \u2014 next %d orbits" % (s.name, self.norbits.get()),
                     color=COL_TEXT, fontsize=10)
        self.mpl.draw()
