"""planning.py (screen) - goal-directed planning & status.

Tabs:
  Work a target  - best upcoming windows to work a grid/state/DXCC via a sat
  Visible passes - optically observable passes with estimated magnitude
  Sat <-> Sat     - line-of-sight windows between two satellites
  Element trust   - element-set age, trust level, and drift estimate
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, TabBar, now_unix,
               fmt_utc, make_scrolled_tree)
from ...engine import planning as PL
from ...engine import linkbudget as LB
from ...engine.predict import grid_to_latlon
from .. import exports as EX


# US state centroids (approx) for the "work a state" target option
_STATE_CENTROIDS = {
    "AL": (32.8, -86.8), "AK": (64.2, -149.5), "AZ": (34.3, -111.7),
    "AR": (34.8, -92.4), "CA": (37.2, -119.3), "CO": (39.0, -105.5),
    "CT": (41.6, -72.7), "DE": (39.0, -75.5), "FL": (28.6, -82.4),
    "GA": (32.6, -83.4), "HI": (20.3, -156.4), "ID": (44.4, -114.6),
    "IL": (40.0, -89.2), "IN": (39.9, -86.3), "IA": (42.0, -93.5),
    "KS": (38.5, -98.4), "KY": (37.5, -85.3), "LA": (31.0, -92.0),
    "ME": (45.4, -69.2), "MD": (39.0, -76.8), "MA": (42.3, -71.8),
    "MI": (44.3, -85.4), "MN": (46.3, -94.3), "MS": (32.7, -89.7),
    "MO": (38.4, -92.5), "MT": (47.0, -109.6), "NE": (41.5, -99.8),
    "NV": (39.3, -116.6), "NH": (43.7, -71.6), "NJ": (40.1, -74.7),
    "NM": (34.4, -106.1), "NY": (42.9, -75.5), "NC": (35.5, -79.4),
    "ND": (47.4, -100.5), "OH": (40.3, -82.8), "OK": (35.6, -97.5),
    "OR": (44.0, -120.5), "PA": (40.9, -77.8), "RI": (41.7, -71.6),
    "SC": (33.9, -80.9), "SD": (44.4, -100.2), "TN": (35.9, -86.4),
    "TX": (31.5, -99.3), "UT": (39.3, -111.7), "VT": (44.1, -72.7),
    "VA": (37.5, -78.9), "WA": (47.4, -120.4), "WV": (38.6, -80.6),
    "WI": (44.6, -90.0), "WY": (43.0, -107.6),
}


class PlanningScreen(Screen):
    def build(self):
        self.sat_header("Planning & Status")
        tabs = TabBar(self.frame)
        self._tabs = tabs
        tabs.pack(fill="both", expand=True, padx=12, pady=8)
        self._t_work = tabs.add("Work a target")
        self._t_vis = tabs.add("Visible passes")
        self._t_s2s = tabs.add("Sat \u2194 Sat")
        self._t_rove = tabs.add("Rove")
        self._t_trust = tabs.add("Element trust")
        self._build_work(self._t_work)
        self._build_vis(self._t_vis)
        self._build_s2s(self._t_s2s)
        self._build_rove(self._t_rove)
        self._build_trust(self._t_trust)

    # ---- work a target ----
    def _build_work(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Target type:", style="TLabel").pack(side="left")
        self._tgt_type = tk.StringVar(value="grid")
        for lab, v in (("Grid", "grid"), ("US state", "state"),
                       ("DXCC", "dxcc"), ("Lat,Lon", "ll")):
            ttk.Radiobutton(bar, text=lab, value=v, variable=self._tgt_type,
                            command=self._on_tgt_type).pack(side="left")
        ttk.Label(bar, text="Target:", style="TLabel").pack(
            side="left", padx=(10, 2))
        self._tgt = tk.StringVar(value="FN31")
        self._tgt_entry = ttk.Entry(bar, textvariable=self._tgt, width=12)
        self._tgt_entry.pack(side="left")
        # DXCC entity picker (shown only for the DXCC target type)
        from ...data.dxcc import DXCC
        self._dxcc = DXCC
        self._dxcc_names = sorted({v[0] for v in DXCC.values()})
        self._tgt_dxcc = tk.StringVar(value=self._dxcc_names[0]
                                      if self._dxcc_names else "")
        self._tgt_combo = ttk.Combobox(bar, textvariable=self._tgt_dxcc,
                                       values=self._dxcc_names, state="readonly",
                                       width=22)
        self._find_btn = ttk.Button(bar, text="Find windows",
                                    command=self._render_work)
        self._find_btn.pack(side="left", padx=8)
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._export_work).pack(side="right", padx=2)
        cols = ("start", "dur", "margin")
        heads = ("Start (UTC)", "Duration (min)", "Footprint margin")
        treewrap, self.work_tree = make_scrolled_tree(
            parent, cols, show="headings", height=14)
        for c, h in zip(cols, heads):
            self.work_tree.heading(c, text=h)
            self.work_tree.column(c, width=180, anchor="center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        self.work_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.work_info,
                  style="Muted.TLabel").pack(anchor="w", padx=8, pady=(0, 6))

    def _on_tgt_type(self):
        # swap between the free-text entry (grid/state/lat,lon) and the DXCC
        # entity combobox, keeping both just left of the Find button
        if self._tgt_type.get() == "dxcc":
            self._tgt_entry.pack_forget()
            self._tgt_combo.pack(side="left", before=self._find_btn)
        else:
            self._tgt_combo.pack_forget()
            self._tgt_entry.pack(side="left", before=self._find_btn)

    def _target_latlon(self):
        ttype = self._tgt_type.get()
        val = self._tgt.get().strip()
        try:
            if ttype == "grid":
                return grid_to_latlon(val)
            if ttype == "state":
                return _STATE_CENTROIDS.get(val.upper())
            if ttype == "dxcc":
                name = self._tgt_dxcc.get()
                for _pfx, (nm, lat, lon) in self._dxcc.items():
                    if nm == name:
                        return (lat, lon)
                return None
            if ttype == "ll":
                a, b = val.split(",")
                return (float(a), float(b))
        except Exception:
            return None
        return None

    def _render_work(self):
        for i in self.work_tree.get_children():
            self.work_tree.delete(i)
        s = self.sat()
        ll = self._target_latlon()
        if not s or not ll:
            self.work_info.set("Enter a valid target (grid like FN31, a US "
                               "state code, a DXCC entity, or 'lat,lon').")
            return
        pred = self.pred()
        res = PL.best_passes_for_target(pred, self.store.obs, ll[0], ll[1],
                                        now_unix(), hours=72,
                                        min_el=getattr(self.store, "min_el", 5),
                                        max_results=20)
        self._work_res = res
        self._work_target = self._target_label()
        for w in res:
            self.work_tree.insert("", "end", values=(
                fmt_utc(w["start"]), "%.1f" % (w["duration_s"] / 60.0),
                "%.1f\u00b0" % w["margin_deg"]))
        self.work_info.set(
            "%d windows in 72h where %s and your station are both inside %s's "
            "footprint. Bigger margin = both nearer footprint centre."
            % (len(res), "the target", s.name))

    def _target_label(self):
        ttype = self._tgt_type.get()
        if ttype == "dxcc":
            return self._tgt_dxcc.get()
        return self._tgt.get().strip()

    def _export_work(self):
        s = self.sat()
        res = getattr(self, "_work_res", None)
        if not s or not res:
            return
        h, rows = EX.work_target_rows(res, s.name,
                                      getattr(self, "_work_target", ""))
        self.save_text_dialog(
            EX.rows_to_csv(h, rows),
            "work_target_%s.csv" % s.name.replace("/", "-").replace(" ", "_"),
            title="Export work-a-target windows", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    # ---- visible passes ----
    def _build_vis(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Std. magnitude:", style="TLabel").pack(side="left")
        self._stdmag = tk.StringVar(value="2.0")
        ttk.Entry(bar, textvariable=self._stdmag, width=6).pack(side="left")
        ttk.Label(bar, text="Twilight:", style="TLabel").pack(
            side="left", padx=(10, 2))
        self._twi = tk.IntVar(value=-6)
        for lab, v in (("Civil", -6), ("Nautical", -12), ("Astro", -18)):
            ttk.Radiobutton(bar, text=lab, value=v, variable=self._twi).pack(
                side="left")
        ttk.Button(bar, text="Find visible passes",
                   command=self._render_vis).pack(side="left", padx=8)
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._export_vis).pack(side="right", padx=2)
        cols = ("aos", "maxel", "mag", "dur")
        heads = ("Start (UTC)", "Max El", "Est. mag", "Duration (min)")
        treewrap, self.vis_tree = make_scrolled_tree(
            parent, cols, show="headings", height=14)
        for c, h in zip(cols, heads):
            self.vis_tree.heading(c, text=h)
            self.vis_tree.column(c, width=160, anchor="center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        self.vis_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.vis_info,
                  style="Muted.TLabel").pack(anchor="w", padx=8, pady=(0, 6))

    def _render_vis(self):
        for i in self.vis_tree.get_children():
            self.vis_tree.delete(i)
        s = self.sat()
        if not s:
            self.vis_info.set("No satellite selected.")
            return
        try:
            stdmag = float(self._stdmag.get())
        except Exception:
            stdmag = 2.0
        pred = self.pred()
        t = now_unix()
        passes = pred.predict_passes(t, getattr(self.store, "min_el", 5), 60,
                                     horizon_end=t + 5 * 86400.0)
        found = 0
        self._vis_rows = []
        for p in passes:
            if not (p.aos and p.los):
                continue
            # sample at TCA: is it a visible-pass candidate?
            tt = p.aos
            best_mag = 99.0
            visible = False
            while tt <= p.los:
                look = pred.look(tt)
                if LB.is_optically_visible(look.sunlit, look.sun_el, look.el,
                                           self._twi.get(), 10.0):
                    visible = True
                    m = LB.apparent_magnitude(stdmag, look.range_km, 90.0)
                    best_mag = min(best_mag, m)
                tt += 30.0
            if visible:
                found += 1
                self._vis_rows.append({"aos": p.aos, "los": p.los,
                                       "max_el": p.max_el, "mag": best_mag})
                self.vis_tree.insert("", "end", values=(
                    fmt_utc(p.aos), "%.0f\u00b0" % p.max_el,
                    "%.1f" % best_mag,
                    "%.1f" % ((p.los - p.aos) / 60.0)))
        self.vis_info.set(
            "%d optically visible passes in 5 days (satellite sunlit, you in "
            "darkness, el\u226510\u00b0). Magnitude is an estimate." % found)

    def _export_vis(self):
        s = self.sat()
        rows = getattr(self, "_vis_rows", None)
        if not s or not rows:
            return
        h, out = EX.visible_passes_rows(rows, s.name)
        self.save_text_dialog(
            EX.rows_to_csv(h, out),
            "visible_passes_%s.csv" % s.name.replace("/", "-").replace(
                " ", "_"),
            title="Export visible passes", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    # ---- sat to sat ----
    def _build_s2s(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Other satellite (NORAD or name):",
                  style="TLabel").pack(side="left")
        self._other = tk.StringVar(value="")
        ttk.Entry(bar, textvariable=self._other, width=14).pack(side="left")
        ttk.Label(bar, text="Window (h):", style="TLabel").pack(
            side="left", padx=(10, 2))
        self._s2s_hours = tk.IntVar(value=12)
        for v in (3, 6, 12, 24):
            ttk.Radiobutton(bar, text=str(v), value=v,
                            variable=self._s2s_hours,
                            command=self._render_s2s).pack(side="left")
        ttk.Button(bar, text="Find LOS windows",
                   command=self._render_s2s).pack(side="left", padx=8)
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._export_s2s).pack(side="right", padx=2)
        cols = ("start", "end", "dur", "range")
        heads = ("Start (UTC)", "End (UTC)", "Duration (min)",
                 "Min range (km)")
        treewrap, self.s2s_tree = make_scrolled_tree(
            parent, cols, show="headings", height=12)
        for c, h in zip(cols, heads):
            self.s2s_tree.heading(c, text=h)
            self.s2s_tree.column(c, width=160, anchor="center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        self.s2s_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.s2s_info,
                  style="Muted.TLabel").pack(anchor="w", padx=8, pady=(0, 6))
        self._s2s_windows = []
        self._s2s_names = ("", "")

    def _resolve_other_sat(self):
        q = self._other.get().strip()
        if not q:
            return None
        try:
            norad = int(q)
            return next((x for x in self.store.db.sats
                         if x.norad == norad), None)
        except ValueError:
            ql = q.lower()
            return next((x for x in self.store.db.sats
                         if ql in x.name.lower()), None)

    def _render_s2s(self):
        for i in self.s2s_tree.get_children():
            self.s2s_tree.delete(i)
        self._s2s_windows = []
        s = self.sat()
        if not s:
            self.s2s_info.set("No satellite selected.")
            return
        other = self._resolve_other_sat()
        if not other:
            self.s2s_info.set("Enter the NORAD id or part of the name of a "
                              "second satellite (see the Satellites screen).")
            return
        from ...engine.predict import Predictor
        from ...engine import celestial as CE
        p1 = self.pred()
        p2 = Predictor()
        p2.set_site(self.store.obs)
        p2.set_sat(other)
        wins = CE.sat_to_sat_windows(p1, p2, now_unix(),
                                     hours=self._s2s_hours.get(), step_s=30.0)
        self._s2s_windows = wins
        self._s2s_names = (s.name, other.name)
        for w in wins:
            self.s2s_tree.insert("", "end", values=(
                fmt_utc(w["start"]), fmt_utc(w["end"]),
                "%.1f" % (w["duration_s"] / 60.0),
                "%.0f" % w["min_range_km"]))
        self.s2s_info.set(
            "%s \u2194 %s: %d line-of-sight window(s) in %d h. A clear LOS "
            "means the chord between the two satellites does not pass through "
            "the Earth." % (s.name, other.name, len(wins),
                            self._s2s_hours.get()))

    def _export_s2s(self):
        if not self._s2s_windows:
            return
        from .. import exports as EX
        headers, rows = EX.sat2sat_rows(self._s2s_names[0], self._s2s_names[1],
                                        self._s2s_windows)
        self.save_text_dialog(EX.rows_to_csv(headers, rows), "sat2sat.csv",
                              title="Export sat-to-sat windows", ext=".csv",
                              filetypes=[("CSV", "*.csv")])

    # ---- element trust ----
    def _build_trust(self, parent):
        self.trust_kv = KVPanel(parent, label_width=22)
        self.trust_kv.pack(fill="both", expand=True, padx=8, pady=6)

    def _render_trust(self):
        s = self.sat()
        self.trust_kv.begin()
        if not s:
            self.trust_kv.note("No satellite selected.")
            self.trust_kv.end()
            return
        epoch = getattr(s, "epoch_unix", 0.0)
        mm = getattr(s, "mean_motion", 15.0)
        age = LB.element_age_days(epoch, now_unix())
        label, conf = LB.trust_level(age)
        drift = LB.along_track_error_km(age, mm)
        self.trust_kv.section("Element set")
        self.trust_kv.row("Epoch", fmt_utc(epoch) if epoch else "unknown")
        self.trust_kv.row("Age", "%.1f days" % age)
        self.trust_kv.row("Trust", "%s (%.0f%%)" % (label, conf * 100))
        self.trust_kv.row("Est. along-track error", "~%.0f km" % drift)
        self.trust_kv.section("Guidance")
        if age <= 7:
            self.trust_kv.note("Fresh enough for accurate pass times.")
        elif age <= 14:
            self.trust_kv.note("Aging \u2014 pass times may be off by seconds to "
                               "a minute. Consider refreshing (Update GP).")
        else:
            self.trust_kv.note("Stale \u2014 predictions may be unreliable. "
                               "Click Update GP (online) to refresh elements.")
        self.trust_kv.end()

    # ---- rove planner ----
    def _build_rove(self, parent):
        intro = ttk.Label(
            parent,
            text=("Rove route planner. Add the grids you plan to activate with "
                  "the date and approximate UTC time window you'll be there. "
                  "The windows are hints \u2014 the selected satellite's passes "
                  "that cover each stop near its window are shown, each with the "
                  "US states, DXCC entities, and grid count workable through "
                  "that pass."),
            style="MutedBg.TLabel", wraplength=720, justify="left")
        intro.pack(anchor="w", padx=10, pady=(8, 4))

        # ---- entry row: Grid / Date / Start / End / Add ----
        entry = ttk.Frame(parent, style="TFrame")
        entry.pack(fill="x", padx=10, pady=(2, 2))
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._rv_grid = tk.StringVar(value="FN31")
        self._rv_date = tk.StringVar(value=today)
        self._rv_start = tk.StringVar(value="13:00")
        self._rv_end = tk.StringVar(value="17:00")

        def _field(parent_, label, var, width):
            col = ttk.Frame(parent_, style="TFrame")
            col.pack(side="left", padx=(0, 8))
            ttk.Label(col, text=label, style="Muted.TLabel").pack(anchor="w")
            ttk.Entry(col, textvariable=var, width=width).pack(anchor="w")

        _field(entry, "Grid", self._rv_grid, 8)
        _field(entry, "Date (UTC)", self._rv_date, 12)
        _field(entry, "Start", self._rv_start, 7)
        _field(entry, "End", self._rv_end, 7)
        addcol = ttk.Frame(entry, style="TFrame")
        addcol.pack(side="left", padx=(2, 0))
        ttk.Label(addcol, text=" ", style="Muted.TLabel").pack(anchor="w")
        ttk.Button(addcol, text="Add stop",
                   command=self._rove_add_stop).pack(anchor="w")

        # ---- the planned-stops list ----
        mid = ttk.Frame(parent, style="TFrame")
        mid.pack(fill="x", padx=10, pady=(4, 2))
        scols = ("grid", "date", "start", "end")
        sheads = ("Grid", "Date (UTC)", "Start", "End")
        stopwrap, self.stops_tree = make_scrolled_tree(
            mid, scols, show="headings", height=4)
        for c, h in zip(scols, sheads):
            self.stops_tree.heading(c, text=h)
            self.stops_tree.column(c, width=110,
                                   anchor="w" if c == "grid" else "center")
        stopwrap.pack(side="left", fill="x", expand=True)
        sbtns = ttk.Frame(mid, style="TFrame")
        sbtns.pack(side="left", fill="y", padx=6)
        ttk.Button(sbtns, text="Remove",
                   command=self._rove_remove_stop).pack(anchor="w", pady=1)
        ttk.Button(sbtns, text="Clear all",
                   command=self._rove_clear_stops).pack(anchor="w", pady=1)
        # backing list of stop dicts (starts empty)
        self._stops = []
        self._refresh_stops_tree()

        btns = ttk.Frame(parent, style="TFrame")
        btns.pack(fill="x", padx=10, pady=4)
        ttk.Button(btns, text="Plan route",
                   command=self._render_rove).pack(side="left")
        ttk.Button(btns, text="Export CSV\u2026",
                   command=self._export_rove).pack(side="left", padx=4)
        ttk.Button(btns, text="PDF\u2026",
                   command=self._export_rove_pdf).pack(side="left")
        ttk.Label(btns, text="   Satellites:", style="MutedBg.TLabel").pack(
            side="left")
        self._rove_scope = tk.StringVar(value="selected")
        ttk.Radiobutton(btns, text="Selected", value="selected",
                        variable=self._rove_scope).pack(side="left")
        ttk.Radiobutton(btns, text="All favorites", value="favorites",
                        variable=self._rove_scope).pack(side="left")

        cols = ("stop", "sat", "aos", "los", "maxel", "states", "dxcc", "grids")
        heads = ("Stop", "Satellite", "AOS (UTC)", "LOS (UTC)", "Max El",
                 "States", "DXCC", "Grids")
        treewrap, self.rove_tree = make_scrolled_tree(
            parent, cols, show="headings", height=9)
        widths = {"stop": 70, "sat": 90, "aos": 120, "los": 120, "maxel": 55,
                  "states": 60, "dxcc": 55, "grids": 55}
        for c, h in zip(cols, heads):
            self.rove_tree.heading(c, text=h)
            self.rove_tree.column(c, width=widths[c],
                                  anchor="w" if c in ("stop", "sat") else
                                  "center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        self.rove_tree.bind("<<TreeviewSelect>>", self._on_rove_pick)
        self.rove_detail = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.rove_detail,
                  style="MutedBg.TLabel", wraplength=720,
                  justify="left").pack(anchor="w", padx=10, pady=(0, 4))
        self.rove_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.rove_info,
                  style="MutedBg.TLabel", wraplength=720,
                  justify="left").pack(anchor="w", padx=10, pady=(0, 6))

    def _refresh_stops_tree(self):
        self.stops_tree.delete(*self.stops_tree.get_children())
        for st in self._stops:
            self.stops_tree.insert("", "end", values=(
                st["grid"], st["date"], st["start"], st["end"]))

    def _rove_add_stop(self):
        from tkinter import messagebox
        grid = self._rv_grid.get().strip().upper()
        if not grid_to_latlon(grid):
            messagebox.showinfo("Rove", "Enter a valid Maidenhead grid "
                                "(e.g. FN31 or FN31pr).")
            return
        # validate date/time
        win = self._stop_window(self._rv_date.get().strip(),
                                self._rv_start.get().strip(),
                                self._rv_end.get().strip())
        if win is None:
            messagebox.showinfo("Rove", "Enter the date as YYYY-MM-DD and "
                                "times as HH:MM (UTC).")
            return
        self._stops.append({"grid": grid, "date": self._rv_date.get().strip(),
                            "start": self._rv_start.get().strip(),
                            "end": self._rv_end.get().strip()})
        self._refresh_stops_tree()

    def _rove_remove_stop(self):
        sel = self.stops_tree.selection()
        if not sel:
            return
        idx = self.stops_tree.index(sel[0])
        if 0 <= idx < len(self._stops):
            del self._stops[idx]
            self._refresh_stops_tree()

    def _rove_clear_stops(self):
        self._stops = []
        self._refresh_stops_tree()

    @staticmethod
    def _stop_window(date_str, start_str, end_str):
        """Parse a stop's date + start/end (UTC) into (frm_unix, to_unix), or
        None if invalid. If end <= start the window is treated as spanning to
        the next day (an overnight stop)."""
        from datetime import datetime, timezone, timedelta
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc)
            sh, sm = (int(x) for x in start_str.split(":"))
            eh, em = (int(x) for x in end_str.split(":"))
            frm = d + timedelta(hours=sh, minutes=sm)
            to = d + timedelta(hours=eh, minutes=em)
            if to <= frm:
                to = to + timedelta(days=1)
            return frm.timestamp(), to.timestamp()
        except Exception:
            return None

    def _resolve_stops(self):
        """Build [(grid, lat, lon, frm, to), ...] from the planned-stops list,
        skipping any with an invalid grid or window."""
        out = []
        for st in self._stops:
            ll = grid_to_latlon(st["grid"])
            win = self._stop_window(st["date"], st["start"], st["end"])
            if not ll or win is None:
                continue
            out.append((st["grid"], ll[0], ll[1], win[0], win[1]))
        return out

    def _render_rove(self):
        for i in self.rove_tree.get_children():
            self.rove_tree.delete(i)
        self.rove_detail.set("")
        stops = self._resolve_stops()
        if not stops:
            self.rove_info.set("Add at least one stop (valid grid, date "
                               "YYYY-MM-DD, and HH:MM times).")
            return
        # which satellites to plan for
        if self._rove_scope.get() == "favorites":
            sats = [s for s in self.store.db.sats
                    if s.norad in self.store.favorites]
            if not sats:
                self.rove_info.set("No favorites yet \u2014 mark some "
                                   "satellites as favorites, or use Selected.")
                return
        else:
            s = self.sat()
            if not s:
                self.rove_info.set("Select a satellite first.")
                return
            sats = [s]
        min_el = getattr(self.store, "min_el", 5)
        self._rove_rows = []
        total_pass = 0
        for grid, lat, lon, frm, to in stops:
            any_for_stop = False
            for s in sats:
                pred = self.pred() if s is self.sat() else self._pred_for_sat(s)
                if pred is None:
                    continue
                results = PL.rove_stop_passes(pred, lat, lon, frm, to,
                                              min_el=min_el)
                for r in results:
                    any_for_stop = True
                    total_pass += 1
                    self.rove_tree.insert("", "end", values=(
                        grid, s.name, fmt_utc(r["aos"]), fmt_utc(r["los"]),
                        "%.0f\u00b0" % r["max_el"], len(r["states"]),
                        len(r["dxcc"]), len(r["grids"])))
                    self._rove_rows.append((grid, s.name, r))
            if not any_for_stop:
                self.rove_tree.insert("", "end", values=(
                    grid, "", "\u2014 no covering passes in window \u2014", "",
                    "", "", "", ""))
                self._rove_rows.append((grid, "", None))
        scope = ("all favorites (%d sats)" % len(sats)
                 if self._rove_scope.get() == "favorites"
                 else sats[0].name)
        self.rove_info.set(
            "%d stops, %d covering passes for %s. Select a row to see the "
            "workable states / DXCC / grids for that pass. Time windows are "
            "hints." % (len(stops), total_pass, scope))

    def _pred_for_sat(self, s):
        """A Predictor bound to the current site and a given satellite."""
        from ...engine.predict import Predictor
        pred = Predictor()
        pred.set_site(self.store.obs)
        if not pred.set_sat(s):
            return None
        return pred

    def _on_rove_pick(self, _evt=None):
        sel = self.rove_tree.selection()
        if not sel:
            return
        idx = self.rove_tree.index(sel[0])
        if not (0 <= idx < len(self._rove_rows)):
            return
        grid, sat_name, r = self._rove_rows[idx]
        if r is None:
            self.rove_detail.set("")
            return
        states = ", ".join(sorted(r["states"])) or "\u2014"
        dxcc = ", ".join(sorted(r["dxcc"])) or "\u2014"
        ngrids = len(r["grids"])
        self.rove_detail.set(
            "%s via %s, pass %s\u2013%s UTC:\n  States: %s\n  DXCC: %s\n  "
            "Grids: %d in footprint"
            % (grid, sat_name or "\u2014", fmt_utc(r["aos"]), fmt_utc(r["los"]),
               states, dxcc, ngrids))

    def _rove_export_rows(self):
        headers = ["Stop", "Satellite", "AOS (UTC)", "LOS (UTC)", "Max El",
                   "States", "DXCC", "Grids"]
        rows = []
        for grid, sat_name, r in getattr(self, "_rove_rows", []):
            if r is None:
                rows.append([grid, "", "no covering passes", "", "", "", "",
                             ""])
                continue
            rows.append([
                grid, sat_name, fmt_utc(r["aos"]), fmt_utc(r["los"]),
                "%.0f" % r["max_el"],
                " ".join(sorted(r["states"])),
                " ".join(sorted(d.split()[0] for d in r["dxcc"])),
                "%d" % len(r["grids"])])
        return headers, rows

    def _export_rove(self):
        if not getattr(self, "_rove_rows", None):
            return
        s = self.sat()
        headers, rows = self._rove_export_rows()
        self.save_text_dialog(
            EX.rows_to_csv(headers, rows),
            "rove_%s.csv" % (s.name.replace("/", "-") if s else "plan"),
            title="Export rove plan (CSV)", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    def _export_rove_pdf(self):
        from tkinter import filedialog, messagebox
        if not getattr(self, "_rove_rows", None):
            messagebox.showinfo("Rove plan",
                                "Plan a route first (Plan route).")
            return
        s = self.sat()
        favmode = getattr(self, "_rove_scope", None) and \
            self._rove_scope.get() == "favorites"
        title_name = "" if favmode else (s.name if s else "")
        path = filedialog.asksaveasfilename(
            title="Export rove sheet (PDF)", defaultextension=".pdf",
            initialfile="rove_%s.pdf" % ("favorites" if favmode else
                                         (s.name.replace("/", "-")
                                          if s else "plan")),
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            from ..rovesheet import generate_rove_sheet_pdf
            generate_rove_sheet_pdf(path, title_name,
                                    self.store, self._rove_rows)
        except Exception as e:
            messagebox.showerror("Rove plan", "Could not generate PDF:\n%s" % e)
            return
        self.app.set_status("Saved rove sheet: %s" % path)

    def on_show(self):
        self._render_trust()
