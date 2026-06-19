"""sites.py - manage observer sites and compare passes across them.

The PRIMARY site drives every other screen (Track, passes, etc.). This screen
lets you nickname it and maintain a table of SECONDARY sites (club station,
portable spots, friends' QTHs), then compare the selected satellite's upcoming
passes across all of them side by side. Everything here is exportable.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from . import (Screen, TabBar, now_unix,
               fmt_utc, make_scrolled_tree)
from ...engine.predict import Predictor, grid_to_latlon, latlon_to_grid
from .. import exports as EX


class SitesScreen(Screen):
    def build(self):
        self.sat_header("Sites \u2014 Observer Locations & Comparison")
        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=8)
        self._t_manage = tabs.add("Manage sites")
        self._t_compare = tabs.add("Compare passes")
        self._build_manage(self._t_manage)
        self._build_compare(self._t_compare)

    # ---- manage sites ----
    def _build_manage(self, parent):
        # primary site
        pf = ttk.Frame(parent, style="TFrame")
        pf.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(pf, text="Primary site nickname:",
                  style="TLabel").pack(side="left")
        self._primary_name = tk.StringVar(value=self.store.obs_name)
        ttk.Entry(pf, textvariable=self._primary_name, width=18).pack(
            side="left", padx=6)
        ttk.Button(pf, text="Rename", command=self._rename_primary).pack(
            side="left")
        self._primary_lbl = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._primary_lbl,
                  style="Muted.TLabel").pack(anchor="w", padx=8)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=8,
                                                        pady=8)

        # add a secondary site
        af = ttk.Frame(parent, style="TFrame")
        af.pack(fill="x", padx=8, pady=4)
        ttk.Label(af, text="Add site \u2014 name:", style="TLabel").pack(
            side="left")
        self._new_name = tk.StringVar(value="")
        ttk.Entry(af, textvariable=self._new_name, width=14).pack(
            side="left", padx=4)
        ttk.Label(af, text="grid or lat,lon:", style="TLabel").pack(side="left")
        self._new_loc = tk.StringVar(value="")
        ttk.Entry(af, textvariable=self._new_loc, width=16).pack(
            side="left", padx=4)
        ttk.Label(af, text="alt (m):", style="TLabel").pack(side="left")
        self._new_alt = tk.StringVar(value="0")
        ttk.Entry(af, textvariable=self._new_alt, width=6).pack(
            side="left", padx=4)
        ttk.Button(af, text="Add", command=self._add_site).pack(
            side="left", padx=6)

        # secondary sites table
        cols = ("name", "lat", "lon", "alt", "grid")
        heads = ("Nickname", "Lat", "Lon", "Alt (m)", "Grid")
        treewrap, self.tree = make_scrolled_tree(
            parent, cols, show="headings", height=10)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=120 if c == "name" else 90,
                             anchor="w" if c == "name" else "center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        bf = ttk.Frame(parent, style="TFrame")
        bf.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Button(bf, text="Remove selected",
                   command=self._remove_site).pack(side="left")
        ttk.Label(bf, text="The primary site drives all other screens; "
                  "secondary sites are for comparison here.",
                  style="Muted.TLabel").pack(side="left", padx=10)

    def _rename_primary(self):
        self.store.set_obs_name(self._primary_name.get().strip() or "Home")
        self._refresh_manage()
        self.app.set_status("Renamed primary site to %s" % self.store.obs_name)

    def _add_site(self):
        loc = self._new_loc.get().strip()
        ll = None
        if "," in loc:
            try:
                a, b = loc.split(",")
                ll = (float(a), float(b))
            except Exception:
                ll = None
        else:
            ll = grid_to_latlon(loc)
        if not ll:
            messagebox.showerror("Add site",
                                 "Enter a Maidenhead grid (e.g. FN20) or "
                                 "'lat,lon'.")
            return
        try:
            alt = float(self._new_alt.get())
        except Exception:
            alt = 0.0
        name = self.store.add_site(self._new_name.get() or "Site",
                                   ll[0], ll[1], alt)
        self._new_name.set("")
        self._new_loc.set("")
        self._new_alt.set("0")
        self._refresh_manage()
        try:
            self._render_compare()
        except Exception:
            pass
        self.app.set_status("Added site: %s" % name)

    def _remove_site(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self.store.remove_site(idx)
        self._refresh_manage()
        # the comparison view lists every site, so it must be rebuilt too or it
        # keeps showing the removed observer
        try:
            self._render_compare()
        except Exception:
            pass

    def _refresh_manage(self):
        o = self.store.obs
        self._primary_name.set(self.store.obs_name)
        self._primary_lbl.set(
            "%s \u2014 %.3f, %.3f  (grid %s, alt %.0f m)"
            % (self.store.obs_name, o.lat, o.lon, latlon_to_grid(o.lat, o.lon),
               o.alt_m))
        for i in self.tree.get_children():
            self.tree.delete(i)
        for s in self.store.sites:
            self.tree.insert("", "end", values=(
                s["name"], "%.3f" % s["lat"], "%.3f" % s["lon"],
                "%.0f" % s.get("alt_m", 0.0),
                latlon_to_grid(s["lat"], s["lon"])))

    # ---- compare passes ----
    def _build_compare(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Window (days):", style="TLabel").pack(side="left")
        self._days = tk.IntVar(value=2)
        for v in (1, 2, 3):
            ttk.Radiobutton(bar, text=str(v), value=v, variable=self._days,
                            command=self._render_compare).pack(side="left")
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._export_compare).pack(side="right", padx=2)
        ttk.Button(bar, text="Report (PDF)\u2026",
                   command=self._report_compare).pack(side="right", padx=2)

        cols = ("site", "n", "next", "nextel", "bestel")
        heads = ("Site", "Passes", "Next AOS (UTC)", "Next max el",
                 "Best max el")
        treewrap, self.ctree = make_scrolled_tree(
            parent, cols, show="headings", height=12)
        for c, h in zip(cols, heads):
            self.ctree.heading(c, text=h)
            self.ctree.column(c, width=150 if c in ("next",) else 110,
                              anchor="w" if c == "site" else "center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        self.cinfo = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.cinfo,
                  style="Muted.TLabel").pack(anchor="w", padx=8, pady=(0, 6))
        self._cmp_entries = []

    def _compute_compare(self):
        s = self.sat()
        if not s:
            return []
        t = now_unix()
        horizon = t + self._days.get() * 86400.0
        entries = []
        for name, obs in self.store.all_sites():
            pred = Predictor()
            pred.set_site(obs)
            if not pred.set_sat(s):
                continue
            ps = pred.predict_passes(t, getattr(self.store, "min_el", 5.0),
                                     200, horizon_end=horizon)
            nxt = ps[0] if ps else None
            best = max(ps, key=lambda p: p.max_el) if ps else None
            entries.append({"name": name, "n_passes": len(ps),
                            "next_pass": nxt, "best_pass": best})
        return entries

    def _render_compare(self):
        for i in self.ctree.get_children():
            self.ctree.delete(i)
        s = self.sat()
        if not s:
            self.cinfo.set("No satellite selected.")
            return
        self._cmp_entries = self._compute_compare()
        for e in self._cmp_entries:
            nxt = e["next_pass"]
            best = e["best_pass"]
            self.ctree.insert("", "end", values=(
                e["name"], e["n_passes"],
                fmt_utc(nxt.aos) if nxt else "\u2014",
                "%.0f\u00b0" % nxt.max_el if nxt else "\u2014",
                "%.0f\u00b0" % best.max_el if best else "\u2014"))
        self.cinfo.set(
            "%s passes over %d day(s) across %d site(s). The primary site is "
            "listed first." % (s.name, self._days.get(),
                               len(self._cmp_entries)))

    def on_show(self):
        self._refresh_manage()
        self._render_compare()

    def _export_compare(self):
        s = self.sat()
        if not s or not self._cmp_entries:
            return
        headers, rows = EX.site_comparison_rows(s.name, self._cmp_entries)
        self.save_text_dialog(
            EX.rows_to_csv(headers, rows),
            "sites_%s.csv" % s.name.replace("/", "-").replace(" ", "_"),
            title="Export site comparison", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    def _report_compare(self):
        s = self.sat()
        if not s or not self._cmp_entries:
            return
        from tkinter import filedialog
        from ..reports import generate_site_comparison_report
        path = filedialog.asksaveasfilename(
            title="Site comparison report", defaultextension=".pdf",
            initialfile="sites_%s.pdf" % s.name.replace("/", "-").replace(
                " ", "_"),
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_site_comparison_report(path, self.store, s,
                                             self._cmp_entries, self._days.get())
        except Exception as e:
            messagebox.showerror("Report", str(e))
            return
        self.app.set_status("Saved site comparison: %s" % path)
