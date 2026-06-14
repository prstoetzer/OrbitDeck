"""passdetail.py - detail view of a single pass: polar arc + elevation profile."""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, FONT_MONO,
               fmt_hms, fmt_utc, now_unix, compass)


class PassDetailScreen(Screen):
    def build(self):
        self.header("Pass Detail")
        self._pass = None
        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        left = ttk.Frame(body, style="Panel.TFrame")
        left.pack(side="left", fill="y", padx=(0, 8))
        self.info = tk.StringVar(value="Select a pass from Next Passes.")
        ttk.Label(left, textvariable=self.info, style="Mono.TLabel",
                  justify="left", wraplength=300).pack(
            anchor="w", padx=14, pady=12)

        right = ttk.Frame(body, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.polar = MplPanel(right, figsize=(4.4, 4.4), polar=True)
        self.polar.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.prof = MplPanel(right, figsize=(4.4, 4.4), polar=False)
        self.prof.pack(side="left", fill="both", expand=True, padx=6, pady=6)

    def set_pass(self, p):
        self._pass = p
        self._render()

    def on_show(self):
        if self._pass:
            self._render()

    def _render(self):
        p = self._pass
        s = self.sat()
        if not p or not s:
            return
        self.info.set(
            "%s\n\nAOS  %s\n     az %.0f\u00b0 %s\n"
            "TCA  %s\n     max el %.1f\u00b0\n"
            "LOS  %s\n     az %.0f\u00b0 %s\n\n"
            "Duration  %s" % (
                s.name,
                fmt_utc(p.aos), p.az_aos, compass(p.az_aos),
                fmt_utc(p.tca, "%H:%M:%S"), p.max_el,
                fmt_utc(p.los, "%H:%M:%S"), p.az_los, compass(p.az_los),
                fmt_hms(p.los - p.aos)))

        n = 80
        azs, els, ts = [], [], []
        for i in range(n + 1):
            tt = p.aos + (p.los - p.aos) * i / n
            a, e = self.pred().azel_at(tt)
            azs.append(a)
            els.append(max(e, 0))
            ts.append((tt - p.aos) / 60.0)

        ax = self.polar.ax
        ax.clear()
        self.polar._style_axes()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(90, 0)
        ax.set_rgrids([0, 30, 60, 90], labels=["90", "60", "30", "0"],
                      color=COL_MUTED, fontsize=7)
        ax.set_thetagrids(range(0, 360, 45),
                          labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                          color=COL_MUTED, fontsize=8)
        ax.grid(True, color=COL_GRID, linewidth=0.6)
        ax.plot([math.radians(a) for a in azs], els, color=COL_ACCENT,
                linewidth=2)
        ax.plot([math.radians(azs[0])], [0], "o", color=COL_ACCENT2)
        ax.plot([math.radians(azs[-1])], [0], "s", color=COL_WARN)
        ax.set_title("Sky track", color=COL_TEXT, fontsize=10)
        self.polar.draw()

        ax2 = self.prof.ax
        ax2.clear()
        self.prof._style_axes()
        ax2.plot(ts, els, color=COL_ACCENT, linewidth=2)
        ax2.fill_between(ts, els, color=COL_ACCENT, alpha=0.15)
        ax2.set_xlabel("minutes after AOS")
        ax2.set_ylabel("elevation (\u00b0)")
        ax2.set_ylim(0, max(90, max(els) + 5))
        ax2.grid(True, color=COL_GRID, linewidth=0.5)
        ax2.set_title("Elevation profile", color=COL_TEXT, fontsize=10)
        self.prof.draw()
