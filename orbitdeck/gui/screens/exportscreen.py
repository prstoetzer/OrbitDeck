"""exportscreen.py - data exports & sharing.

CSV / iCal / JSON pass schedule exports, equator-crossing CSV, a multi-satellite
comparison table (with export), and a per-pass shareable 'card' image.
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, TabBar, MplPanel, now_unix,
               fmt_utc, make_scrolled_tree)
from .. import exports as EX
from ...engine.predict import Predictor


class ExportScreen(Screen):
    def build(self):
        self.sat_header("Exports & Sharing")
        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=8)
        self._t_pass = tabs.add("Pass schedule")
        self._t_cmp = tabs.add("Compare favorites")
        self._t_card = tabs.add("Pass card")
        self._t_list = tabs.add("Listings")
        tabs.on_change = self._on_tab
        self._build_pass(self._t_pass)
        self._build_cmp(self._t_cmp)
        self._build_card(self._t_card)
        self._build_listings(self._t_list)

    def _on_tab(self, idx):
        if idx == 3:
            self._render_listing()

    # ---- pass schedule exports ----
    def _build_pass(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Window (days):", style="TLabel").pack(side="left")
        self._days = tk.IntVar(value=3)
        for v in (1, 3, 7):
            ttk.Radiobutton(bar, text=str(v), value=v, variable=self._days,
                            command=self._refresh_pass).pack(side="left")
        ttk.Button(bar, text="CSV\u2026", command=self._exp_csv).pack(
            side="right", padx=2)
        ttk.Button(bar, text="Excel\u2026", command=self._exp_xlsx).pack(
            side="right", padx=2)
        ttk.Button(bar, text="iCal\u2026", command=self._exp_ics).pack(
            side="right", padx=2)
        ttk.Button(bar, text="JSON\u2026", command=self._exp_json).pack(
            side="right", padx=2)
        cols = ("aos", "maxel", "dur", "los")
        heads = ("AOS (UTC)", "Max El", "Duration (min)", "LOS (UTC)")
        treewrap, self.tree = make_scrolled_tree(
            parent, cols, show="headings", height=15)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=170, anchor="center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        self.info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.info,
                  style="Muted.TLabel").pack(anchor="w", padx=8, pady=(0, 6))
        self._passes = []

    def _get_passes(self):
        s = self.sat()
        if not s:
            return []
        pred = self.pred()
        t = now_unix()
        return pred.predict_passes(t, getattr(self.store, "min_el", 5), 200,
                                   horizon_end=t + self._days.get() * 86400.0)

    def _refresh_pass(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._passes = self._get_passes()
        for p in self._passes:
            if not (p.aos and p.los):
                continue
            self.tree.insert("", "end", values=(
                fmt_utc(p.aos), "%.0f\u00b0" % p.max_el,
                "%.1f" % ((p.los - p.aos) / 60.0), fmt_utc(p.los)))
        s = self.sat()
        self.info.set("%d passes for %s over %d days."
                      % (len(self._passes), s.name if s else "?",
                         self._days.get()))

    def on_show(self):
        self._refresh_pass()
        self._reload_card_passes()

    def _site_dict(self):
        o = self.store.obs
        return {"lat": o.lat, "lon": o.lon, "alt_m": o.alt_m}

    def _exp_csv(self):
        s = self.sat()
        if not s or not self._passes:
            return
        self.save_text_dialog(
            EX.passes_to_csv(self._passes, s.name),
            "passes_%s.csv" % _safe(s.name), title="Export passes (CSV)",
            ext=".csv", filetypes=[("CSV", "*.csv")])

    def _exp_ics(self):
        s = self.sat()
        if not s or not self._passes:
            return
        site = "%.3f,%.3f" % (self.store.obs.lat, self.store.obs.lon)
        self.save_text_dialog(
            EX.passes_to_ics(self._passes, s.name, site,
                             getattr(self.store, "min_el", 5)),
            "passes_%s.ics" % _safe(s.name), title="Export passes (iCal)",
            ext=".ics", filetypes=[("iCalendar", "*.ics")])

    def _exp_json(self):
        s = self.sat()
        if not s or not self._passes:
            return
        self.save_text_dialog(
            EX.passes_to_json(self._passes, s.name, self._site_dict(),
                              getattr(self.store, "min_el", 5)),
            "passes_%s.json" % _safe(s.name), title="Export passes (JSON)",
            ext=".json", filetypes=[("JSON", "*.json")])

    def _exp_xlsx(self):
        s = self.sat()
        if not s or not self._passes:
            return
        from tkinter import filedialog, messagebox
        if not EX.have_xlsx():
            messagebox.showinfo("Excel export",
                                "openpyxl is not installed; use CSV instead.")
            return
        path = filedialog.asksaveasfilename(
            title="Export passes (Excel)", defaultextension=".xlsx",
            initialfile="passes_%s.xlsx" % _safe(s.name),
            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        headers = ["AOS (UTC)", "LOS (UTC)", "TCA (UTC)", "Max El (deg)",
                   "Duration (min)", "AOS az", "LOS az"]
        rows = []
        for p in self._passes:
            if not (p.aos and p.los):
                continue
            rows.append([fmt_utc(p.aos), fmt_utc(p.los), fmt_utc(p.tca),
                         round(p.max_el, 1), round((p.los - p.aos) / 60.0, 1),
                         round(p.az_aos, 1), round(p.az_los, 1)])
        try:
            EX.sheets_to_xlsx(path, [("Passes", headers, rows)])
        except Exception as e:
            messagebox.showerror("Excel export", str(e))
            return
        self.app.set_status("Saved: %s" % path)

    # ---- compare favorites ----
    def _build_cmp(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Window (days):", style="TLabel").pack(side="left")
        self._cdays = tk.IntVar(value=3)
        for v in (1, 3, 7):
            ttk.Radiobutton(bar, text=str(v), value=v, variable=self._cdays,
                            command=self._render_cmp).pack(side="left")
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._exp_cmp).pack(side="right", padx=2)
        cols = ("sat", "n", "best", "el", "dur")
        heads = ("Satellite", "Passes", "Best pass (UTC)", "Best max el",
                 "Best dur (min)")
        treewrap, self.cmp_tree = make_scrolled_tree(
            parent, cols, show="headings", height=15)
        for c, h in zip(cols, heads):
            self.cmp_tree.heading(c, text=h)
            self.cmp_tree.column(c, width=140, anchor="center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        self.cmp_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.cmp_info,
                  style="Muted.TLabel").pack(anchor="w", padx=8, pady=(0, 6))
        self._cmp_entries = []

    def _compute_cmp(self):
        favs = [s for s in self.store.db.sats
                if s.norad in self.store.favorites]
        if not favs:
            favs = self.store.db.sats[:8]
        t = now_unix()
        entries = []
        for s in favs:
            pred = Predictor()
            pred.set_site(self.store.obs)
            if not pred.set_sat(s):
                continue
            ps = pred.predict_passes(t, getattr(self.store, "min_el", 5), 100,
                                     horizon_end=t + self._cdays.get() * 86400.0)
            best = max(ps, key=lambda p: p.max_el) if ps else None
            entries.append({"name": s.name, "n_passes": len(ps),
                            "best_pass": best})
        return entries

    def _render_cmp(self):
        for i in self.cmp_tree.get_children():
            self.cmp_tree.delete(i)
        self._cmp_entries = self._compute_cmp()
        headers, rows = EX.comparison_rows(self._cmp_entries)
        for r in rows:
            self.cmp_tree.insert("", "end", values=tuple(r))
        self.cmp_info.set("%d satellites compared over %d days (favorites, or "
                          "the first few if none favorited)."
                          % (len(self._cmp_entries), self._cdays.get()))

    def _exp_cmp(self):
        if not self._cmp_entries:
            return
        headers, rows = EX.comparison_rows(self._cmp_entries)
        self.save_text_dialog(
            EX.rows_to_csv(headers, rows), "comparison.csv",
            title="Export comparison (CSV)", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    # ---- pass card ----
    def _build_card(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Pass:", style="TLabel").pack(side="left")
        self._card_pass_var = tk.StringVar()
        self._card_pass_combo = ttk.Combobox(
            bar, textvariable=self._card_pass_var, state="readonly", width=44)
        self._card_pass_combo.pack(side="left", padx=6)
        self._card_pass_combo.bind("<<ComboboxSelected>>",
                                   self._on_card_pass_change)
        ttk.Button(bar, text="Save pass card\u2026",
                   command=self._save_card).pack(side="right", padx=2)
        ttk.Button(bar, text="Refresh passes",
                   command=self._reload_card_passes).pack(side="right", padx=2)
        self.card_panel = MplPanel(parent, figsize=(7.2, 3.8))
        self.card_panel.pack(fill="both", expand=True, padx=8, pady=(2, 4))
        self.card_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.card_info, style="Muted.TLabel",
                  wraplength=640, justify="left").pack(
            anchor="w", padx=12, pady=(0, 8))
        self._card_passes = []
        self._card_pass_index = 0

    def _reload_card_passes(self):
        s = self.sat()
        self._card_passes = []
        if s:
            pred = self.pred()
            self._card_passes = pred.predict_passes(
                now_unix(), getattr(self.store, "min_el", 5), 12)
        labels = []
        for p in self._card_passes:
            labels.append("%s  max el %.0f\u00b0  %.0f min"
                          % (fmt_utc(p.aos, "%a %m-%d %H:%M"), p.max_el,
                             (p.los - p.aos) / 60.0))
        if not labels:
            labels = ["(no upcoming pass above min elevation)"]
        self._card_pass_combo.configure(values=labels)
        if self._card_pass_index >= len(self._card_passes):
            self._card_pass_index = 0
        self._card_pass_combo.current(
            self._card_pass_index if self._card_passes else 0)
        self._render_card()

    def _on_card_pass_change(self, _evt=None):
        self._card_pass_index = self._card_pass_combo.current()
        self._card_pass_combo.selection_clear()
        self.frame.focus_set()
        self._render_card()

    def _selected_card_pass(self):
        if self._card_passes and \
                0 <= self._card_pass_index < len(self._card_passes):
            return self._card_passes[self._card_pass_index]
        return None

    def _render_card(self):
        from ..passcard import draw_pass_card
        s = self.sat()
        self.card_panel.fig.clf()
        if not s:
            self.card_info.set("No satellite selected.")
            self.card_panel.draw()
            return
        p = self._selected_card_pass()
        if not p:
            self.card_info.set("No upcoming pass found for %s." % s.name)
            self.card_panel.draw()
            return
        try:
            draw_pass_card(self.card_panel.fig, self.store, s, p)
        except Exception as e:
            self.card_info.set("Could not render card: %s" % e)
            self.card_panel.draw()
            return
        self.card_panel.draw()
        self.card_info.set("A shareable single-image summary of the chosen "
                           "pass: sky track, Doppler curve, and the key facts. "
                           "Use \u201cSave pass card\u2026\u201d to export the "
                           "PNG.")

    def _save_card(self):
        s = self.sat()
        if not s:
            return
        from tkinter import filedialog, messagebox
        from ..passcard import generate_pass_card
        p = self._selected_card_pass()
        if not p:
            messagebox.showinfo("Pass card", "No upcoming pass found.")
            return
        path = filedialog.asksaveasfilename(
            title="Save pass card", defaultextension=".png",
            initialfile="passcard_%s.png" % _safe(s.name),
            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        try:
            generate_pass_card(path, self.store, s, p)
        except Exception as e:
            messagebox.showerror("Pass card", str(e))
            return
        self.app.set_status("Saved pass card: %s" % path)

    # ---- listings (one-observer stepped, AOS/LOS quick, two-observer) ----
    def _build_listings(self, parent):
        from . import TabBar
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Step:", style="TLabel").pack(side="left")
        self._lstep = tk.IntVar(value=60)
        for label, v in (("30s", 30), ("1m", 60), ("2m", 120), ("5m", 300)):
            ttk.Radiobutton(bar, text=label, value=v, variable=self._lstep,
                            command=self._render_listing).pack(side="left")
        ttk.Label(bar, text="  Span:", style="TLabel").pack(side="left")
        self._lspan = tk.IntVar(value=2)
        for label, v in (("2h", 2), ("6h", 6), ("12h", 12), ("24h", 24)):
            ttk.Radiobutton(bar, text=label, value=v, variable=self._lspan,
                            command=self._render_listing).pack(side="left")
        self._lvis = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Visible only", variable=self._lvis,
                        command=self._render_listing).pack(side="left", padx=8)
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._exp_listing).pack(side="right", padx=2)

        # second-observer picker (for the Two-observers sub-tab)
        bar2 = ttk.Frame(parent, style="TFrame")
        bar2.pack(fill="x", padx=8, pady=(0, 2))
        ttk.Label(bar2, text="Second station:", style="TLabel").pack(
            side="left")
        self._dx_var = tk.StringVar()
        self._dx_combo = ttk.Combobox(bar2, textvariable=self._dx_var,
                                      state="readonly", width=32)
        self._dx_combo.pack(side="left", padx=6)
        self._dx_combo.bind("<<ComboboxSelected>>",
                            lambda _e: self._render_listing())

        sub = TabBar(parent)
        sub.pack(fill="both", expand=True, padx=2, pady=2)
        sub.on_change = lambda _i: self._render_listing()
        self._lsub = sub
        page_one = sub.add("One observer")
        page_aos = sub.add("AOS / LOS")
        page_two = sub.add("Two observers")

        # one-observer stepped
        cols = ("t", "az", "el", "rng", "rr", "sub", "alt", "sun")
        heads = ("Time (UTC)", "Az", "El", "Range km", "Rate km/s",
                 "Sub-point", "Alt km", "Sun")
        w1, self._lt_one = make_scrolled_tree(
            page_one, cols, show="headings", height=16)
        for c, h in zip(cols, heads):
            self._lt_one.heading(c, text=h)
            self._lt_one.column(c, width=96, anchor="center")
        w1.pack(fill="both", expand=True, padx=6, pady=6)

        # AOS/LOS quick list
        cols2 = ("aos", "los", "dur", "maxel", "aaz", "laz")
        heads2 = ("AOS (UTC)", "LOS (UTC)", "Duration", "Max El",
                  "AOS Az", "LOS Az")
        w2, self._lt_aos = make_scrolled_tree(
            page_aos, cols2, show="headings", height=16)
        for c, h in zip(cols2, heads2):
            self._lt_aos.heading(c, text=h)
            self._lt_aos.column(c, width=120, anchor="center")
        w2.pack(fill="both", expand=True, padx=6, pady=6)

        # two-observer stepped
        cols3 = ("t", "az1", "el1", "r1", "az2", "el2", "r2")
        heads3 = ("Time (UTC)", "Az\u2081", "El\u2081", "Rng\u2081 km",
                  "Az\u2082", "El\u2082", "Rng\u2082 km")
        w3, self._lt_two = make_scrolled_tree(
            page_two, cols3, show="headings", height=16)
        for c, h in zip(cols3, heads3):
            self._lt_two.heading(c, text=h)
            self._lt_two.column(c, width=110, anchor="center")
        w3.pack(fill="both", expand=True, padx=6, pady=6)

        self._linfo = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._linfo,
                  style="Muted.TLabel").pack(anchor="w", padx=8, pady=(0, 6))
        self._list_one = []
        self._list_aos = []
        self._list_two = []

    def _refresh_dx_combo(self):
        # all_sites() -> [(name, Observer), ...] with the PRIMARY first; the DX
        # picker offers only the secondary sites (skip index 0).
        sites = self.store.all_sites()[1:]
        labels = [name for name, _obs in sites]
        if not labels:
            labels = ["(no secondary sites \u2014 add them in Sites)"]
        cur = self._dx_combo.current()
        self._dx_combo.configure(values=labels)
        if cur < 0 or cur >= len(labels):
            self._dx_combo.current(0)

    def _selected_dx(self):
        sites = self.store.all_sites()[1:]
        if not sites:
            return None, ""
        i = max(0, self._dx_combo.current())
        if i >= len(sites):
            i = 0
        name, obs = sites[i]
        return obs, name

    def _render_listing(self):
        self._refresh_dx_combo()
        for t in (self._lt_one, self._lt_aos, self._lt_two):
            for i in t.get_children():
                t.delete(i)
        s = self.sat()
        if not s:
            self._linfo.set("No satellite selected.")
            self._list_one = self._list_aos = self._list_two = []
            return
        pred = self.pred()
        t0 = now_unix()
        step = self._lstep.get()
        count = int(self._lspan.get() * 3600 / step) + 1
        vis = self._lvis.get()

        # one-observer
        self._list_one = pred.listing_rows(t0, step, count, visible_only=vis)
        for r in self._list_one:
            self._lt_one.insert("", "end", values=(
                fmt_utc(r["t"], "%m-%d %H:%M:%S"),
                "%.0f\u00b0" % r["az"], "%.1f\u00b0" % r["el"],
                "%.0f" % r["range_km"], "%+.3f" % r["range_rate"],
                "%.1f, %.1f" % (r["sub_lat"], r["sub_lon"]),
                "%.0f" % r["alt_km"], "\u2600" if r["sunlit"] else "\u263d"))

        # AOS/LOS quick list over the span (use the span as a day-fraction)
        self._list_aos = pred.predict_passes(
            t0, getattr(self.store, "min_el", 5), 200,
            horizon_end=t0 + self._lspan.get() * 3600.0)
        for p in self._list_aos:
            if not (p.aos and p.los):
                continue
            self._lt_aos.insert("", "end", values=(
                fmt_utc(p.aos, "%m-%d %H:%M:%S"),
                fmt_utc(p.los, "%m-%d %H:%M:%S"),
                EX._hms(p.los - p.aos), "%.0f\u00b0" % p.max_el,
                "%.0f\u00b0" % p.az_aos, "%.0f\u00b0" % p.az_los))

        # two-observer
        dx, dxname = self._selected_dx()
        if dx is not None:
            self._list_two = pred.listing_rows_two(t0, step, count, dx,
                                                   visible_only=vis)
            for r in self._list_two:
                self._lt_two.insert("", "end", values=(
                    fmt_utc(r["t"], "%m-%d %H:%M:%S"),
                    "%.0f\u00b0" % r["az1"], "%.1f\u00b0" % r["el1"],
                    "%.0f" % r["range1_km"],
                    "%.0f\u00b0" % r["az2"], "%.1f\u00b0" % r["el2"],
                    "%.0f" % r["range2_km"]))
        else:
            self._list_two = []
        self._linfo.set(
            "%s \u2014 step %ds over %dh. One-obs: %d rows; AOS/LOS: %d passes; "
            "two-obs second station: %s."
            % (s.name, step, self._lspan.get(), len(self._list_one),
               len(self._list_aos), dxname or "none (add sites)"))

    def _exp_listing(self):
        s = self.sat()
        if not s:
            return
        active = self._lsub._active if hasattr(self._lsub, "_active") else 0
        if active == 0 and self._list_one:
            h, rows = EX.listing_one_rows(self._list_one, s.name,
                                          self.store.obs_name)
            csv = EX.rows_to_csv(h, rows)
            name = "listing_one_%s.csv" % _safe(s.name)
        elif active == 1 and self._list_aos:
            h, rows = EX.aoslos_rows(self._list_aos, s.name)
            csv = EX.rows_to_csv(h, rows)
            name = "aoslos_%s.csv" % _safe(s.name)
        elif active == 2 and self._list_two:
            _dx, dxname = self._selected_dx()
            h, rows = EX.listing_two_rows(self._list_two, s.name,
                                          self.store.obs_name, dxname)
            csv = EX.rows_to_csv(h, rows)
            name = "listing_two_%s.csv" % _safe(s.name)
        else:
            return
        self.save_text_dialog(csv, name, title="Export listing (CSV)",
                              ext=".csv", filetypes=[("CSV", "*.csv")])


def _safe(name):
    return name.replace("/", "-").replace(" ", "_")
