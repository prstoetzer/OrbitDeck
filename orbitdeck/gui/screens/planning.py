"""planning.py (screen) - goal-directed planning & status.

Tabs:
  Work a target  - best upcoming windows to work a grid/state/DXCC via a sat
  Visible passes - optically observable passes with estimated magnitude
  Sat <-> Sat     - line-of-sight windows between two satellites
  Element trust   - element-set age, trust level, and drift estimate
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, TabBar, COL_MUTED, COL_ACCENT, COL_WARN, now_unix,
               fmt_utc)
from ...engine import planning as PL
from ...engine import linkbudget as LB
from ...engine.predict import grid_to_latlon, Observer
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
        tabs.pack(fill="both", expand=True, padx=12, pady=8)
        self._t_work = tabs.add("Work a target")
        self._t_vis = tabs.add("Visible passes")
        self._t_s2s = tabs.add("Sat \u2194 Sat")
        self._t_trust = tabs.add("Element trust")
        self._build_work(self._t_work)
        self._build_vis(self._t_vis)
        self._build_s2s(self._t_s2s)
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
        self.work_tree = ttk.Treeview(parent, columns=cols, show="headings",
                                      height=14)
        for c, h in zip(cols, heads):
            self.work_tree.heading(c, text=h)
            self.work_tree.column(c, width=180, anchor="center")
        self.work_tree.pack(fill="both", expand=True, padx=8, pady=6)
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
        self.vis_tree = ttk.Treeview(parent, columns=cols, show="headings",
                                     height=14)
        for c, h in zip(cols, heads):
            self.vis_tree.heading(c, text=h)
            self.vis_tree.column(c, width=160, anchor="center")
        self.vis_tree.pack(fill="both", expand=True, padx=8, pady=6)
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
            vis_mag = None
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
        self.s2s_tree = ttk.Treeview(parent, columns=cols, show="headings",
                                     height=12)
        for c, h in zip(cols, heads):
            self.s2s_tree.heading(c, text=h)
            self.s2s_tree.column(c, width=160, anchor="center")
        self.s2s_tree.pack(fill="both", expand=True, padx=8, pady=6)
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

    def on_show(self):
        self._render_trust()
