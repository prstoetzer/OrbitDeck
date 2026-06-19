"""passdetail.py - detail view of a single pass: polar arc + elevation profile."""

import math
from tkinter import ttk

from . import (Screen, MplPanel, KVPanel, COL_TEXT, COL_MUTED,
               COL_ACCENT, COL_ACCENT2, COL_WARN, COL_GRID, fmt_hms, fmt_utc, compass)


class PassDetailScreen(Screen):
    def build(self):
        self.sat_header("Pass Detail")
        self._pass = None
        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        left = ttk.Frame(body, style="Panel.TFrame")
        left.pack(side="left", fill="y", padx=(0, 8))
        self.kv = KVPanel(left, label_width=10)
        self.kv.pack(fill="y", padx=6, pady=8)
        self._empty = True

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
        else:
            self.kv.begin()
            self.kv.section("Pass detail")
            self.kv.note("Select a pass from Next Passes (double-click a row).")
            self.kv.end()
            self._show_empty_plots()

    def _show_empty_plots(self):
        """Show a single tidy placeholder; hide the profile plot until a pass is
        chosen so no empty cartesian frame is shown."""
        self.prof.widget.pack_forget()
        self.polar.clear(polar=True)
        pax = self.polar.ax
        pax.set_theta_zero_location("E")
        pax.set_rticks([])
        pax.set_rlim(0, 1)
        pax.tick_params(colors=COL_MUTED, labelsize=7)
        pax.set_title("Select a pass to see its sky track",
                      color=COL_MUTED, fontsize=9)
        self.polar.draw()

    def _render(self):
        p = self._pass
        s = self.sat()
        if not p or not s:
            return
        # ensure the profile plot is visible (it is hidden in the empty state)
        if not self.prof.widget.winfo_manager():
            self.prof.widget.pack(side="left", fill="both", expand=True,
                                  padx=6, pady=6)
        r_tca = self.pred().look(p.tca).range_km
        k = self.kv
        k.begin()
        k.section(s.name)
        k.row("Max el", "%.1f\u00b0" % p.max_el, COL_ACCENT, big=True)
        k.row("Duration", fmt_hms(p.los - p.aos))
        k.section("AOS")
        k.row("Time", fmt_utc(p.aos, "%H:%M:%S"))
        k.row("Azimuth", "%.0f\u00b0 %s" % (p.az_aos, compass(p.az_aos)))
        k.section("TCA")
        k.row("Time", fmt_utc(p.tca, "%H:%M:%S"))
        k.row("Range", "%.0f km" % r_tca)
        k.section("LOS")
        k.row("Time", fmt_utc(p.los, "%H:%M:%S"))
        k.row("Azimuth", "%.0f\u00b0 %s" % (p.az_los, compass(p.az_los)))
        k.row("Date", fmt_utc(p.aos, "%Y-%m-%d"), COL_MUTED)
        # educational "why is this pass like this" explainer
        try:
            from ..lab import pass_explain
            why = pass_explain(self.pred(), p)
        except Exception:
            why = []
        if why:
            k.section("Why this pass?")
            for line in why:
                k.note(line)
        k.end()

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
        # rlim runs 90 (centre) -> 0 (rim), so the gridline at radius r must be
        # labelled with r itself: zenith=90 at the centre, horizon=0 at the rim.
        # (Previously the labels were reversed, making a high-elevation pass read
        # as though it skimmed the horizon.)
        ax.set_rgrids([0, 30, 60, 90], labels=["0", "30", "60", "90"],
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
