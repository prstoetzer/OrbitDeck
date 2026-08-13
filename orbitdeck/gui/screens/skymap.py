"""skymap.py (screen) - a naked-eye sky map with satellite overlays.

Plots the stars and constellation lines currently above the horizon (from the
bundled catalog) on a zenith-centered sky disk, and overlays the selected
satellite plus favorites at their current az/el, so you can relate a pass to
what you'd actually see. Refreshes on the shared tick.
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_MUTED, COL_ACCENT, COL_ACCENT2,
               COL_WARN, now_unix)
from ...engine.predict import Predictor
from ...engine import skymap as SM


class SkyMapScreen(Screen):
    def build(self):
        self.header("Sky Map \u2014 stars & satellites overhead")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=2)
        self.showcon = tk.BooleanVar(value=True)
        ttk.Button(bar, text="Print screen\u2026",
                   command=self._report).pack(side="right", padx=4)
        ttk.Checkbutton(bar, text="Constellation lines", variable=self.showcon,
                        command=self._redraw).pack(side="left")
        self.showfav = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Favorite satellites", variable=self.showfav,
                        command=self._redraw).pack(side="left", padx=12)
        ttk.Label(bar, text="Limiting mag:", style="TLabel").pack(
            side="left", padx=(12, 2))
        self.maxmag = tk.DoubleVar(value=4.5)
        for v in (3.5, 4.5, 5.5):
            ttk.Radiobutton(bar, text="%.1f" % v, value=v, variable=self.maxmag,
                            command=self._redraw).pack(side="left")
        self.info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel").pack(
            side="left", padx=12)

        self.panel = MplPanel(self.frame, figsize=(6.4, 6.4))
        self.panel.widget.pack(fill="both", expand=True, padx=8, pady=8)

    def on_show(self):
        self._redraw()

    def on_tick(self, _now_dt):
        # a light refresh once a minute is plenty for the sky
        self._redraw()

    def _redraw(self):
        obs = self.store.obs
        t = now_unix()
        ax = self.panel.ax
        self.panel.fig.clf()
        ax = self.panel.fig.add_subplot(111)
        self.panel.ax = ax
        ax.set_facecolor("#0d1117")
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.set_aspect("equal")
        ax.axis("off")
        # horizon circle + cardinal marks
        ax.add_artist(__import__("matplotlib").patches.Circle(
            (50, 50), 50, fill=False, color=COL_MUTED, lw=1.2))
        for az, lab in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
            xy = SM.azel_to_xy(az, 0, 100)
            ax.text(xy[0], xy[1], lab, color=COL_ACCENT, ha="center",
                    va="center", fontsize=11, fontweight="bold")

        # constellation lines
        if self.showcon.get():
            for a1, e1, a2, e2 in SM.constellation_segments(obs.lat, obs.lon, t):
                p1 = SM.azel_to_xy(a1, max(0, e1), 100)
                p2 = SM.azel_to_xy(a2, max(0, e2), 100)
                if p1 and p2:
                    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#24406a",
                            lw=0.6, zorder=1)

        # stars (size/brightness scaled by magnitude)
        stars = SM.visible_stars(obs.lat, obs.lon, t, max_mag=self.maxmag.get())
        for az, el, m in stars:
            xy = SM.azel_to_xy(az, el, 100)
            if not xy:
                continue
            size = max(1.0, (self.maxmag.get() - m + 0.5) * 3.0)
            ax.plot(xy[0], xy[1], ".", color="#e8eef7", markersize=size,
                    zorder=2)

        # satellite overlays
        n_sat = 0
        sats = []
        sel = self.store.selected_sat()
        if sel:
            sats.append((sel, True))
        if self.showfav.get():
            for s in self.store.db.sats:
                if s.norad in self.store.favorites and (
                        not sel or s.norad != sel.norad):
                    sats.append((s, False))
        pred = Predictor()
        pred.set_site(obs)
        for s, is_sel in sats:
            try:
                if not pred.set_sat(s):
                    continue
                look = pred.look(t)
            except Exception:
                continue
            if look.el < 0:
                continue
            xy = SM.azel_to_xy(look.az, look.el, 100)
            if not xy:
                continue
            color = COL_WARN if is_sel else COL_ACCENT2
            ax.plot(xy[0], xy[1], "o", color=color, markersize=9 if is_sel else 6,
                    markeredgecolor="#0d1117", zorder=4)
            ax.text(xy[0] + 1.5, xy[1] + 1.5, s.name, color=color, fontsize=8,
                    zorder=5)
            n_sat += 1

        self.info.set("%d stars, %d satellite(s) up now." % (len(stars), n_sat))
        self.panel.canvas.draw_idle()
