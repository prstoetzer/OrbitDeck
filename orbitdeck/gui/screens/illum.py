"""illum.py - illumination raster: sunlit vs eclipse over many orbits/days."""

import tkinter as tk
from tkinter import ttk
import numpy as np

from . import (Screen, MplPanel, COL_TEXT, COL_MUTED, COL_ACCENT, COL_GRID,
               now_unix)


class IllumScreen(Screen):
    def build(self):
        self.header("Illumination \u2014 sunlit / eclipse over 60 days")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16)
        ttk.Label(bar, text="Span:", style="TLabel").pack(side="left")
        self.days = tk.IntVar(value=30)
        for v in (10, 30, 60):
            ttk.Radiobutton(bar, text="%dd" % v, value=v, variable=self.days,
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
        s = self.sat()
        if not s:
            self.mpl.draw()
            return
        days = self.days.get()
        period = s.period_min if s.period_min else 95.0
        cols = 96                       # samples across one "orbit phase" axis
        rows = days
        t0 = now_unix()
        grid = np.zeros((rows, cols))
        for d in range(rows):
            for c in range(cols):
                tt = t0 + d * 86400 + (c / cols) * period * 60.0
                grid[d, c] = 1.0 if self.pred().sunlit_at(tt) else 0.0
        ax.imshow(grid, aspect="auto", origin="lower",
                  extent=[0, period, 0, days], cmap="cividis",
                  interpolation="nearest")
        ax.set_xlabel("minutes into orbit")
        ax.set_ylabel("days from now")
        ax.set_title("%s \u2014 bright = sunlit, dark = eclipse" % s.name,
                     color=COL_TEXT, fontsize=10)
        # eclipse fraction summary
        frac = 1.0 - grid.mean()
        ax.text(0.02, 0.97, "mean eclipse fraction %.0f%%" % (frac * 100),
                transform=ax.transAxes, color=COL_TEXT, fontsize=9,
                va="top")
        self.mpl.draw()
