"""grids.py - workable Maidenhead grids / US states / DXCC inside the footprint.

Three sub-views over the same footprint geometry (matching CardSat's separate
Workable Grids / States / DXCC screens). LIVE mode shows what's under the
footprint right now (refreshes ~3 s); PASS mode shows the union across the next
pass.
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT, COL_ACCENT2,
               COL_GRID, FONT_MONO, now_unix)
from ...engine import analysis as A
from ...data.us_states import workable_states
from ...data.dxcc import workable_dxcc


class GridsScreen(Screen):
    live = True

    def build(self):
        self.sat_header("Workable \u2014 what's inside the footprint")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=(0, 4))
        self.kind = tk.StringVar(value="grids")
        for label, val in (("Grids", "grids"), ("US States", "states"),
                           ("DXCC", "dxcc")):
            ttk.Radiobutton(bar, text=label, value=val, variable=self.kind,
                            command=self._recompute).pack(side="left", padx=2)
        ttk.Label(bar, text="   ", style="TLabel").pack(side="left")
        self.mode = tk.StringVar(value="live")
        ttk.Radiobutton(bar, text="Live (now)", value="live",
                        variable=self.mode, command=self._recompute).pack(
            side="left")
        ttk.Radiobutton(bar, text="Across next pass", value="pass",
                        variable=self.mode, command=self._recompute).pack(
            side="left", padx=6)
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._export).pack(side="right", padx=2)

        self.count_var = tk.StringVar(value="")
        tk.Label(self.frame, textvariable=self.count_var, bg=COL_PANEL,
                 fg=COL_ACCENT, font=("DejaVu Sans", 11, "bold"),
                 anchor="w").pack(fill="x", padx=16)

        # a grid of cells rendered as a multi-column Treeview
        self.ncols = 8
        cols = tuple("c%d" % i for i in range(self.ncols))
        self.tree = ttk.Treeview(self.frame, columns=cols, show="",
                                 height=18)
        for c in cols:
            self.tree.column(c, width=120, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.subhdr = tk.StringVar(value="")
        tk.Label(self.frame, textvariable=self.subhdr, bg=COL_PANEL,
                 fg=COL_MUTED, font=("DejaVu Sans", 9), anchor="w").pack(
            fill="x", padx=16, pady=(0, 6))
        self._last_live = 0
        self._pass_cache = {}

    def on_show(self):
        self._pass_cache = {}
        self._recompute()

    def on_tick(self, now_dt):
        if self.mode.get() == "live" and now_dt.timestamp() - self._last_live > 3:
            self._recompute()

    def _recompute(self):
        s = self.sat()
        if not s:
            self.count_var.set("")
            self.subhdr.set("No satellite selected.")
            self._fill([])
            return
        t = now_unix()
        kind = self.kind.get()
        if self.mode.get() == "live":
            self._last_live = t
            lat, lon, alt = self.pred().subpoint_at(t)
            items = self._compute(kind, lat, lon, alt)
            sub = "under the footprint now (refreshes ~3 s)"
        else:
            items = self._pass_union(s, t, kind)
            sub = "union across the next pass"
        noun = {"grids": "grids", "states": "states",
                "dxcc": "entities"}[kind]
        self.count_var.set("%d %s workable" % (len(items), noun))
        self.subhdr.set("%s \u2014 %s" % (s.name, sub))
        self._last_items = items
        self._last_kind = kind
        self._last_mode = self.mode.get()
        # DXCC entries are wider; use fewer columns for them
        self.ncols = 3 if kind == "dxcc" else 8
        self._fill(items, kind)

    def _export(self):
        s = self.sat()
        items = getattr(self, "_last_items", None)
        if not s or not items:
            return
        from .. import exports as EX
        kind = getattr(self, "_last_kind", "grids")
        when = "live" if getattr(self, "_last_mode", "live") == "live" \
            else "next pass union"
        h, rows = EX.workable_rows(kind, items, s.name, when)
        self.save_text_dialog(
            EX.rows_to_csv(h, rows),
            "workable_%s_%s.csv" % (kind, s.name.replace("/", "-").replace(
                " ", "_")),
            title="Export workable list", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    def _fill(self, items, kind="grids"):
        for i in self.tree.get_children():
            self.tree.delete(i)
        # rebuild columns to current ncols
        cols = tuple("c%d" % i for i in range(self.ncols))
        self.tree.configure(columns=cols)
        width = 230 if kind == "dxcc" else 90
        for c in cols:
            self.tree.column(c, width=width, anchor="w")
        if not items:
            self.tree.insert("", "end", values=("(none under footprint)",))
            return
        row = []
        for it in items:
            row.append(it)
            if len(row) == self.ncols:
                self.tree.insert("", "end", values=tuple(row))
                row = []
        if row:
            row += [""] * (self.ncols - len(row))
            self.tree.insert("", "end", values=tuple(row))

    def _compute(self, kind, lat, lon, alt):
        if kind == "grids":
            return A.workable_grids(lat, lon, alt)
        inside = A.make_footprint_test(lat, lon, alt)
        if kind == "states":
            return workable_states(inside)
        return ["%s  %s" % (p, n) for p, n in workable_dxcc(inside)]

    def _pass_union(self, s, t, kind):
        if kind in self._pass_cache:
            return self._pass_cache[kind]
        passes = self.pred().predict_passes(t - 600, self.store.min_el, 1,
                                            t + 6 * 86400)
        union = set()
        if passes:
            p = passes[0]
            steps = max(8, int((p.los - p.aos) / 60))
            for i in range(steps + 1):
                tt = p.aos + (p.los - p.aos) * i / steps
                lat, lon, alt = self.pred().subpoint_at(tt)
                union.update(self._compute(kind, lat, lon, alt))
        res = sorted(union)
        self._pass_cache[kind] = res
        return res
