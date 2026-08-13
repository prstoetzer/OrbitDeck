"""skyglance.py (screen) - all-favorites pass timeline.

A horizontal timeline of every upcoming pass across your favorites: one row per
satellite, one bar per pass, colored by peak elevation. Answers "what is my sky
doing tonight" at a glance, and calls out the longest quiet gap.
"""

import datetime as dt
import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_MUTED, COL_ACCENT, COL_ACCENT2, COL_WARN,
               fmt_hms, fmt_utc, now_unix)
from ...engine.predict import Predictor
from ...engine import skyglance as SG


def elevation_color(max_el):
    """Bar color by peak elevation: low / useful / excellent."""
    if max_el >= 45:
        return COL_ACCENT2
    if max_el >= 20:
        return COL_ACCENT
    return COL_WARN


class SkyGlanceScreen(Screen):
    def build(self):
        self.header("Sky at a Glance \u2014 all favorites")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(bar, text="Window:", style="TLabel").pack(side="left")
        self.hours = tk.IntVar(value=12)
        for v in (6, 12, 24):
            ttk.Radiobutton(bar, text="%dh" % v, value=v, variable=self.hours,
                            command=self._reload).pack(side="left")
        ttk.Label(bar, text="Min el:", style="TLabel").pack(side="left",
                                                             padx=(12, 2))
        self.minel = tk.DoubleVar(value=5.0)
        for v in (0.0, 5.0, 10.0, 20.0):
            ttk.Radiobutton(bar, text="%d\u00b0" % v, value=v,
                            variable=self.minel,
                            command=self._reload).pack(side="left")
        ttk.Button(bar, text="Print screen\u2026",

                   command=self._report).pack(side="right", padx=4)
        ttk.Button(bar, text="Refresh", command=self._reload).pack(side="left",
                                                                    padx=10)
        self.info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel", wraplength=760).pack(
            side="left", padx=8)

        self.panel = MplPanel(self.frame, figsize=(8.4, 4.8))
        self.panel.widget.pack(fill="both", expand=True, padx=10, pady=6)
        note = ("Bar color is peak elevation: amber below 20\u00b0, blue to "
                "45\u00b0, green above. Favorite satellites with no pass in the "
                "window still get a row, so a quiet bird is visible as quiet.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))
        self._rows = []

    def on_show(self):
        self._reload()

    def _reload(self):
        favs = [s for s in self.store.db.sats
                if s.norad in self.store.favorites]
        if not favs:
            self.info.set("No favorites yet \u2014 star some in Satellites.")
            self._draw([], now_unix())
            return
        self.info.set("Predicting %d favorites\u2026" % len(favs))
        hours = self.hours.get()
        minel = self.minel.get()
        t0 = now_unix()

        def work():
            try:
                pred = Predictor()
                rows = SG.sky_glance(pred, self.store.obs, favs, t0, hours=hours,
                                     min_el=minel)
                self._ui(lambda: self._done(rows, t0))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _done(self, rows, t0):
        self._rows = rows
        self._draw(rows, t0)
        n = sum(len(r["passes"]) for r in rows)
        gap = SG.busiest_gap(rows, t0, self.hours.get())
        msg = "%d pass(es) across %d favorites in %dh." % (
            n, len(rows), self.hours.get())
        if gap and gap[1] - gap[0] > 60:
            msg += "  Longest quiet gap %s from %s." % (
                fmt_hms(gap[1] - gap[0]), fmt_utc(gap[0], "%H:%M"))
        self.info.set(msg)

    def _draw(self, rows, t0):
        self.panel.fig.clf()
        ax = self.panel.fig.add_subplot(111)
        self.panel.ax = ax
        ax.set_facecolor("#0d1117")
        for s in ax.spines.values():
            s.set_color(COL_MUTED)
        ax.tick_params(colors=COL_MUTED, labelsize=8)
        hours = self.hours.get()
        t1 = t0 + hours * 3600.0
        x0 = dt.datetime.fromtimestamp(t0, dt.timezone.utc)
        x1 = dt.datetime.fromtimestamp(t1, dt.timezone.utc)
        if not rows:
            ax.text(0.5, 0.5, "No favorites", color=COL_MUTED, ha="center",
                    va="center", transform=ax.transAxes)
            ax.set_xlim(x0, x1)
            self.panel.canvas.draw_idle()
            return
        labels = []
        for i, r in enumerate(rows):
            y = len(rows) - 1 - i
            labels.append((y, r["name"]))
            for a, b, el in r["passes"]:
                xa = dt.datetime.fromtimestamp(a, dt.timezone.utc)
                width = (b - a) / 86400.0          # matplotlib date units = days
                ax.barh(y, width, left=xa, height=0.6,
                        color=elevation_color(el), edgecolor="none")
                if (b - a) > (hours * 3600.0) / 40.0:
                    ax.text(dt.datetime.fromtimestamp((a + b) / 2,
                                                      dt.timezone.utc),
                            y, "%.0f\u00b0" % el, ha="center", va="center",
                            fontsize=7, color="#0d1117")
        ax.set_yticks([y for y, _n in labels])
        ax.set_yticklabels([n for _y, n in labels], fontsize=8,
                           color=COL_MUTED)
        ax.set_ylim(-0.6, len(rows) - 0.4)
        ax.set_xlim(x0, x1)
        ax.grid(True, axis="x", color="#20304a", lw=0.5)
        self.panel.fig.autofmt_xdate()
        self.panel.fig.tight_layout()
        self.panel.canvas.draw_idle()
