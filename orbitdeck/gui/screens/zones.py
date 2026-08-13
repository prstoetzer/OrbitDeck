"""zones.py (screen) - orbital environment zones.

Where the selected satellite spends its time: the South Atlantic Anomaly, the
inner and outer radiation belts, the polar caps and eclipse. Shows the current
verdict (with L shell and B/B0 for the belts), the upcoming entry/exit windows,
and the dwell time per day.

Belt classification uses a tilted centered-dipole field, not IGRF - see
``engine.zones`` - so belt verdicts are indicative rather than dosimetric. The
SAA, polar and eclipse zones are geometric and exact.
"""

import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, COL_ACCENT2, COL_WARN, COL_TEXT,
               fmt_utc, fmt_hms, now_unix, make_scrolled_tree)
from ...engine.predict import Predictor
from ...engine import zones as Z


class ZonesScreen(Screen):
    sat_scoped = ("_res",)
    def build(self):
        self.sat_header("Orbital Zones \u2014 SAA, belts, polar, eclipse")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(bar, text="Zone:", style="TLabel").pack(side="left")
        self.zone = tk.StringVar(value=Z.ZONES[0])
        cb = ttk.Combobox(bar, textvariable=self.zone, state="readonly",
                          width=24, values=Z.ZONES)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._scan())
        ttk.Label(bar, text="Scan:", style="TLabel").pack(side="left",
                                                           padx=(12, 2))
        self.hours = tk.IntVar(value=24)
        for v in (6, 24, 48):
            ttk.Radiobutton(bar, text="%dh" % v, value=v,
                            variable=self.hours).pack(side="left")
        self.scanbtn = ttk.Button(bar, text="Scan", command=self._scan)
        self.scanbtn.pack(side="left", padx=10)
        self.info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel", wraplength=820).pack(
            side="left", padx=8)

        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self.kv = KVPanel(body, label_width=18)
        self.kv.pack(side="left", fill="y", padx=(0, 12))

        cols = ("enter", "exit", "dur")
        heads = ("Enter", "Exit", "Duration")
        wrap, self.tree = make_scrolled_tree(body, cols, show="headings",
                                             height=12)
        for c, h, w in zip(cols, heads, (180, 180, 110)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c != "dur" else "center")
        wrap.pack(side="left", fill="both", expand=True)

        note = ("Belt verdicts use a tilted dipole field (not IGRF), so treat "
                "them as indicative near the belt horns and inside the SAA. "
                "SAA, polar and eclipse zones are geometric and exact.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))

    def on_show(self):
        self.refresh_sat_header()
        self._scan()

    def _zone_index(self):
        try:
            return Z.ZONES.index(self.zone.get())
        except ValueError:
            return 0

    def _scan(self):
        sat = self.store.selected_sat()
        if not sat:
            self.info.set("No satellite selected.")
            return
        zi = self._zone_index()
        hours = self.hours.get()
        self.info.set("Scanning %dh\u2026" % hours)
        self.scanbtn.state(["disabled"])

        def work():
            try:
                pred = Predictor()
                pred.set_site(self.store.obs)
                res = Z.scan_zone(pred, sat, zi, now_unix(), hours=hours)
                self._ui(lambda: self._show(res, sat, zi))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _show(self, res, sat, zi):
        self.scanbtn.state(["!disabled"])
        self.kv.begin()
        self.kv.row("Satellite", sat.name)
        self.kv.row("Zone", Z.ZONES[zi])
        self.kv.row("Now", "IN ZONE" if res["in_now"] else "outside",
                    COL_ACCENT2 if res["in_now"] else COL_TEXT)
        if zi in (Z.ZONE_INNER, Z.ZONE_OUTER):
            self.kv.row("L shell", "%.2f" % res["shell_l"])
            self.kv.row("B/B0", "%.1f" % res["b_ratio"],
                        COL_WARN if res["b_ratio"] > Z.BRATIO_MAX else COL_TEXT)
        self.kv.row("Dwell", "%.1f min/day" % res["dwell_min_day"])
        self.kv.row("Windows", "%d" % len(res["windows"]))
        self.kv.row("Scanned", "%.1f h" % res["scanned_h"])
        self.kv.end()

        self.tree.delete(*self.tree.get_children())
        for a, b in res["windows"]:
            self.tree.insert("", "end", values=(
                fmt_utc(a, "%Y-%m-%d %H:%M:%S"),
                fmt_utc(b, "%H:%M:%S"), fmt_hms(b - a)))
        self.info.set("%s: %d window(s), %.1f min/day."
                      % (Z.ZONES[zi], len(res["windows"]),
                         res["dwell_min_day"]))

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
        save_report_dialog(self, "zones", title="Orbital zones", subtitle="SAA, radiation belts, polar and eclipse",
                           sections=[("", "table", (cols, rows))])
