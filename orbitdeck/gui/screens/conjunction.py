"""conjunction.py (screen) - close-approach screener and orbital neighborhood.

Two tabs for the selected satellite (A):
  * Conjunctions - pick a second object (B) and screen the next N hours for close
    approaches, with miss distance and relative velocity.
  * Neighborhood - rank the rest of the catalog by how close it is right now.

Both are awareness tools built on public GP elements (km-class), never
collision-avoidance; the screen says so.
"""

import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, TabBar, fmt_utc, now_unix, make_scrolled_tree)
from ...engine.predict import Predictor
from ...engine.conjunction import screen_conjunctions, orbital_neighborhood


class ConjunctionScreen(Screen):
    def build(self):
        self.sat_header("Conjunctions \u2014 close-approach screening")
        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        self._t_conj = tabs.add("Conjunctions")
        self._t_neigh = tabs.add("Neighborhood")
        tabs.on_change = self._on_tab
        self._build_conj(self._t_conj)
        self._build_neigh(self._t_neigh)
        note = ("Public GP elements are km-class accurate: a small miss distance "
                "means \u201clook closer\u201d, never a confirmed conjunction. "
                "Awareness, not avoidance.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))

    # ---- conjunctions tab ----
    def _build_conj(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=6)
        ttk.Label(bar, text="Object B:", style="TLabel").pack(side="left")
        self.bvar = tk.StringVar()
        self.bcombo = ttk.Combobox(bar, textvariable=self.bvar, width=28,
                                   state="readonly")
        self.bcombo.pack(side="left", padx=6)
        ttk.Label(bar, text="Hours:", style="TLabel").pack(side="left",
                                                           padx=(12, 2))
        self.hours = tk.IntVar(value=6)
        for v in (6, 12, 24):
            ttk.Radiobutton(bar, text="%d" % v, value=v, variable=self.hours).pack(
                side="left")
        self.scanbtn = ttk.Button(bar, text="Scan", command=self._scan)
        self.scanbtn.pack(side="left", padx=12)
        self.cinfo = tk.StringVar(value="Pick an object and scan.")
        ttk.Label(bar, textvariable=self.cinfo, style="Muted.TLabel").pack(
            side="left", padx=8)

        cols = ("when", "miss", "relv")
        heads = ("Closest approach", "Miss (km)", "Rel vel (km/s)")
        wrap, self.ctree = make_scrolled_tree(parent, cols, show="headings",
                                              height=12)
        for c, h, w in zip(cols, heads, (240, 120, 140)):
            self.ctree.heading(c, text=h)
            self.ctree.column(c, width=w,
                              anchor="w" if c == "when" else "center")
        wrap.pack(fill="both", expand=True, padx=4, pady=8)

    def _build_neigh(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=6)
        ttk.Button(bar, text="Report\u2026",

                   command=self._report).pack(side="right", padx=4)
        ttk.Button(bar, text="Compute now",
                   command=self._neigh).pack(side="left")
        self.ninfo = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.ninfo, style="Muted.TLabel").pack(
            side="left", padx=8)
        cols = ("name", "norad", "range", "relv")
        heads = ("Name", "NORAD", "Range now (km)", "Rel vel (km/s)")
        wrap, self.ntree = make_scrolled_tree(parent, cols, show="headings",
                                              height=13)
        for c, h, w in zip(cols, heads, (240, 90, 140, 140)):
            self.ntree.heading(c, text=h)
            self.ntree.column(c, width=w,
                              anchor="w" if c == "name" else "center")
        wrap.pack(fill="both", expand=True, padx=4, pady=8)

    def on_show(self):
        self.refresh_sat_header()
        self._refresh_blist()

    def _on_tab(self, _idx):
        pass

    def _refresh_blist(self):
        sats = self.store.db.sats
        a = self.store.selected_sat()
        self._blist = [s for s in sats if not (a and s.norad == a.norad)]
        self.bcombo["values"] = ["%s (%d)" % (s.name, s.norad)
                                 for s in self._blist]
        if self._blist and not self.bvar.get():
            self.bcombo.current(0)

    def _scan(self):
        a = self.store.selected_sat()
        if not a:
            self.cinfo.set("No satellite selected.")
            return
        idx = self.bcombo.current()
        if idx < 0 or idx >= len(self._blist):
            self.cinfo.set("Pick an object B first.")
            return
        b = self._blist[idx]
        self.cinfo.set("Screening %d h\u2026" % self.hours.get())
        self.scanbtn.state(["disabled"])
        hours = self.hours.get()

        def work():
            try:
                res = screen_conjunctions(Predictor(), Predictor(), a, b,
                                          now_unix(), hours=hours)
                self._ui(lambda: self._show_conj(res, a, b))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _show_conj(self, res, a, b):
        self.scanbtn.state(["!disabled"])
        self.ctree.delete(*self.ctree.get_children())
        for r in res:
            self.ctree.insert("", "end", values=(
                fmt_utc(r["time"], "%Y-%m-%d %H:%M:%S"),
                "%.1f" % r["miss_km"], "%.2f" % r["rel_vel_kms"]))
        if res:
            self.cinfo.set("%d approach(es) < 800 km, %s vs %s."
                           % (len(res), a.name, b.name))
        else:
            self.cinfo.set("No approach < 800 km in %d h." % self.hours.get())

    def _neigh(self):
        a = self.store.selected_sat()
        self.ntree.delete(*self.ntree.get_children())
        if not a:
            self.ninfo.set("No satellite selected.")
            return
        self.ninfo.set("Computing\u2026")

        def work():
            try:
                res = orbital_neighborhood(Predictor(), a, self.store.db.sats,
                                           now_unix(), max_results=15)
                self._ui(lambda: self._show_neigh(res, a))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _show_neigh(self, res, a):
        self.ntree.delete(*self.ntree.get_children())
        for r in res:
            self.ntree.insert("", "end", values=(
                r["name"], r["norad"], "%.0f" % r["range_km"],
                "%.2f" % r["rel_vel_kms"]))
        self.ninfo.set("%d nearest objects to %s right now." % (len(res),
                                                                a.name))

    def _report(self):
        """Print whatever this screen is currently showing."""
        from ..reports import save_report_dialog
        tree = self.ctree
        cols = [tree.heading(c)["text"] for c in tree["columns"]]
        rows = [list(tree.item(i)["values"]) for i in tree.get_children()]
        if not rows:
            from tkinter import messagebox
            messagebox.showinfo("Report", "Nothing to print yet.",
                                parent=self.frame)
            return
        save_report_dialog(self, "conjunction", title="Conjunctions", subtitle="Close approaches and orbital neighborhood",
                           sections=[("", "table", (cols, rows))])
