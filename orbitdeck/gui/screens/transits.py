"""transits.py (screen) - Sun/Moon transit & close-approach finder.

Scans the selected satellite's passes over a window and lists the moments its
apparent position crosses (or comes near) the Sun's or Moon's disk from the
observer's site - the alignment you need for a satellite-transit photograph.
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, fmt_utc, now_unix, make_scrolled_tree)
from ...engine.predict import Predictor
from ...engine.transits import find_transits


class TransitsScreen(Screen):
    def build(self):
        self.sat_header("Transits \u2014 Sun / Moon crossings")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)

        ttk.Label(bar, text="Body:", style="TLabel").pack(side="left")
        self.body = tk.StringVar(value="both")
        for label, val in (("Both", "both"), ("Sun", "sun"), ("Moon", "moon")):
            ttk.Radiobutton(bar, text=label, value=val, variable=self.body,
                            command=self._reload).pack(side="left")

        ttk.Label(bar, text="Within:", style="TLabel").pack(side="left",
                                                            padx=(12, 2))
        self.sep = tk.DoubleVar(value=1.0)
        for v in (0.5, 1.0, 2.0, 5.0):
            ttk.Radiobutton(bar, text="%.1f\u00b0" % v, value=v,
                            variable=self.sep, command=self._reload).pack(
                side="left")

        ttk.Label(bar, text="Days:", style="TLabel").pack(side="left",
                                                          padx=(12, 2))
        self.days = tk.IntVar(value=7)
        for v in (3, 7, 14):
            ttk.Radiobutton(bar, text="%d" % v, value=v, variable=self.days,
                            command=self._reload).pack(side="left")

        ttk.Button(bar, text="Report\u2026",


                   command=self._report).pack(side="right", padx=4)

        ttk.Button(bar, text="Refresh", command=self._reload).pack(side="left",
                                                                   padx=12)
        self.info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel", wraplength=760).pack(
            side="left", padx=8)

        cols = ("when", "body", "sep", "kind", "az", "el", "range")
        heads = ("When", "Body", "Sep", "Type", "Az", "El", "Range km")
        wrap, self.tree = make_scrolled_tree(self.frame, cols, show="headings",
                                             height=16)
        widths = {"when": 170, "body": 70, "sep": 80, "kind": 90, "az": 70,
                  "el": 70, "range": 100}
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c],
                             anchor="w" if c in ("when", "body", "kind")
                             else "center")
        wrap.pack(fill="both", expand=True, padx=16, pady=10)

        note = ("A \u201ctransit\u201d crosses the disk itself (~0.25\u00b0); "
                "wider settings list near-misses useful for planning a photo. "
                "Only daylight passes yield a Sun transit; the satellite must be "
                "sunlit-or-not irrelevant, but both bodies must be above the "
                "horizon.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))

    def on_show(self):
        self.refresh_sat_header()
        self._reload()

    def _reload(self):
        sat = self.store.selected_sat()
        self.tree.delete(*self.tree.get_children())
        if not sat:
            self.info.set("No satellite selected.")
            return
        pred = Predictor()
        events = find_transits(pred, self.store.obs, sat, now_unix(),
                               hours=self.days.get() * 24.0,
                               body=self.body.get(),
                               max_sep_deg=self.sep.get())
        for e in events:
            self.tree.insert("", "end", values=(
                fmt_utc(e["time"], "%Y-%m-%d %H:%M:%S"),
                e["body"].capitalize(),
                "%.2f\u00b0" % e["sep_deg"],
                "TRANSIT" if e["transit"] else "near",
                "%.0f\u00b0" % e["sat_az"],
                "%.0f\u00b0" % e["sat_el"],
                "%.0f" % e["sat_range_km"],
            ))
        n_tr = sum(1 for e in events if e["transit"])
        self.info.set("%d approach(es), %d disk transit(s) for %s over %dd."
                      % (len(events), n_tr, sat.name, self.days.get()))

    def _report(self):
        """Print whatever this screen is currently showing."""
        from ..reports import save_report_dialog
        tree = self.tree
        cols = [tree.heading(c)["text"] for c in tree["columns"]]
        rows = [list(tree.item(i)["values"]) for i in tree.get_children()]
        if not rows:
            from tkinter import messagebox
            messagebox.showinfo("Report", "Nothing to print yet.",
                                parent=self.frame)
            return
        save_report_dialog(self, "transits", title="Sun/Moon transits", subtitle="Disk crossings and near approaches",
                           sections=[("", "table", (cols, rows))])
