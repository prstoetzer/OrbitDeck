"""polar.py - live polar sky view of the current or next pass."""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_TEXT, COL_MUTED, COL_ACCENT, COL_ACCENT2,
               COL_WARN, COL_GRID, fmt_hms, fmt_utc, now_unix, compass)


class PolarScreen(Screen):
    live = True

    def build(self):
        self.header("Polar \u2014 live sky view")
        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info, style="Muted.TLabel").pack(
            anchor="w", padx=16)
        wrap = ttk.Frame(self.frame, style="Panel.TFrame")
        wrap.pack(fill="both", expand=True, padx=12, pady=8)
        self.mpl = MplPanel(wrap, figsize=(6, 6), polar=True)
        self.mpl.pack(fill="both", expand=True, padx=8, pady=8)

    def on_show(self):
        self._render(now_unix())

    def on_tick(self, now_dt):
        self._render(now_dt.timestamp())

    def _render(self, t):
        s = self.sat()
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(90, 0)
        ax.set_rgrids([0, 30, 60, 90], labels=["90", "60", "30", "0"],
                      color=COL_MUTED, fontsize=8)
        ax.set_thetagrids(range(0, 360, 30), color=COL_MUTED, fontsize=8)
        ax.grid(True, color=COL_GRID, linewidth=0.6)
        if not s:
            self.info.set("No satellite selected.")
            self.mpl.draw()
            return

        L = self.pred().look(t)
        passes = self.pred().predict_passes(t - 1800, self.store.min_el, 1,
                                            t + 6 * 86400)
        if passes:
            p = passes[0]
            n = 90
            azs, els = [], []
            for i in range(n + 1):
                tt = p.aos + (p.los - p.aos) * i / n
                a, e = self.pred().azel_at(tt)
                if e >= 0:
                    azs.append(math.radians(a))
                    els.append(e)
            if azs:
                ax.plot(azs, els, color=COL_ACCENT, linewidth=2)
            if p.aos <= t <= p.los:
                self.info.set("%s in view \u2014 LOS in %s" %
                              (s.name, fmt_hms(p.los - t)))
            else:
                self.info.set("%s \u2014 next AOS %s (in %s), max el %.0f\u00b0" %
                              (s.name, fmt_utc(p.aos, "%H:%M:%S"),
                               fmt_hms(p.aos - t), p.max_el))
        if L.visible:
            ax.plot([math.radians(L.az)], [L.el], "o", color=COL_ACCENT2,
                    markersize=11)
            ax.annotate("%.0f\u00b0" % L.el,
                        (math.radians(L.az), L.el), color=COL_TEXT, fontsize=9)
        if L.sun_el > 0:
            ax.plot([math.radians(L.sun_az)], [L.sun_el], "o", color=COL_WARN,
                    markersize=8)
        self.mpl.draw()
