"""illum.py - illumination raster: sunlit vs eclipse, scrollable over time.

Days on X (today at left), one orbital period on Y. Scroll forward/back through
the timeline indefinitely with the buttons or by dragging; the eclipse band
widens and narrows as the orbit plane precesses relative to the Sun.
"""

import tkinter as tk
from tkinter import ttk
import numpy as np

from . import (Screen, MplPanel, COL_TEXT, COL_MUTED, COL_ACCENT, COL_ACCENT2,
               COL_WARN, COL_GRID, now_unix, fmt_utc)

WINDOW_DAYS = 30          # days shown at once
PHASE_ROWS = 96           # vertical resolution (one period)


class IllumScreen(Screen):
    def build(self):
        self.sat_header("Illumination \u2014 sunlit / eclipse")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=(0, 2))
        ttk.Button(bar, text="\u25c0 back", command=lambda: self._scroll(-7)).pack(
            side="left", padx=2)
        ttk.Button(bar, text="forward \u25b6",
                   command=lambda: self._scroll(7)).pack(side="left", padx=2)
        ttk.Button(bar, text="\u23ce today", command=self._reset).pack(
            side="left", padx=8)
        self.range_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.range_var, style="TLabel").pack(
            side="left", padx=12)
        # eclipse-fraction readout lives in the bar, not inside the plot
        self.frac_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.frac_var, style="TLabel").pack(
            side="right", padx=12)

        wrap = ttk.Frame(self.frame, style="Panel.TFrame")
        wrap.pack(fill="both", expand=True, padx=12, pady=8)
        self.mpl = MplPanel(wrap, figsize=(9, 4.6), polar=False)
        self.mpl.pack(fill="both", expand=True, padx=8, pady=8)
        # scroll with the mouse wheel too
        self.mpl.widget.bind("<Button-4>", lambda e: self._scroll(-3))
        self.mpl.widget.bind("<Button-5>", lambda e: self._scroll(3))
        self.mpl.widget.bind("<MouseWheel>",
                             lambda e: self._scroll(-3 if e.delta > 0 else 3))
        self._day0 = 0        # offset in days from today (can go negative? no)

    def on_show(self):
        self._render()

    def _scroll(self, ddays):
        self._day0 = max(0, self._day0 + ddays)   # never before today
        self._render()

    def _reset(self):
        self._day0 = 0
        self._render()

    def _render(self):
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        s = self.sat()
        if not s:
            self.range_var.set("")
            self.frac_var.set("No satellite selected.")
            self.mpl.draw()
            return
        # make sure the predictor is pointed at the selected satellite
        self.pred().set_sat(s)
        period = s.period_min if s.period_min else 95.0
        t0 = now_unix() + self._day0 * 86400
        grid = np.zeros((PHASE_ROWS, WINDOW_DAYS))
        for d in range(WINDOW_DAYS):
            for r in range(PHASE_ROWS):
                tt = t0 + d * 86400 + (r / PHASE_ROWS) * period * 60.0
                grid[r, d] = 1.0 if self.pred().sunlit_at(tt) else 0.0
        ax.imshow(grid, aspect="auto", origin="lower",
                  extent=[self._day0, self._day0 + WINDOW_DAYS, 0, period],
                  cmap="cividis", interpolation="nearest", vmin=0, vmax=1)
        ax.set_xlabel("days from now")
        ax.set_ylabel("minutes into orbit (one period)")
        ax.set_title("%s \u2014 bright = sunlit, dark = eclipse" % s.name,
                     color=COL_TEXT, fontsize=10)
        self.mpl.draw()

        frac = 1.0 - grid.mean()
        self.frac_var.set("mean eclipse %.0f%% / orbit" % (frac * 100))
        self.range_var.set("%s  \u2192  %s" % (
            fmt_utc(t0, "%Y-%m-%d"),
            fmt_utc(t0 + WINDOW_DAYS * 86400, "%Y-%m-%d")))
