"""home.py - the default view.

Two tabs:
  * Map: a world map showing every favorited satellite's current sub-point and
    footprint. Click a satellite (in the side list) to focus it; click "All" to
    show the whole fleet again. Updates live.
  * Next Passes: the soonest upcoming pass of every favorite, each with a live
    countdown to AOS (or time-to-LOS while overhead), in the style of CardSat's
    schedule page.
"""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_BG, COL_PANEL, COL_TEXT, COL_MUTED,
               COL_ACCENT, COL_ACCENT2, COL_WARN, COL_GRID, FONT_MONO,
               fmt_hms, fmt_utc, now_unix, compass)
from ..mapdraw import draw_basemap
from ...engine import Predictor
from ...engine.predict import _sun_eci_unit, _gmst_rad, jd_of

# a palette to distinguish satellites on the map
PALETTE = ["#2f81f7", "#3fb950", "#d29922", "#db61a2", "#a371f7",
           "#39c5cf", "#f0883e", "#7ee787", "#ff7b72", "#79c0ff"]


class HomeScreen(Screen):
    live = True

    def build(self):
        self.header("Home \u2014 favorite satellites")
        bar = tk.Frame(self.frame, bg=COL_PANEL)
        bar.pack(fill="x", padx=16, pady=(0, 6))
        self.tab = tk.StringVar(value="map")
        self._tabs = []
        for label, val in (("Map", "map"), ("Next Passes", "passes")):
            holder = tk.Frame(bar, bg=COL_PANEL)
            holder.pack(side="left", padx=1, pady=2)
            btn = tk.Label(holder, text=label, bg=COL_PANEL, fg=COL_MUTED,
                           font=("DejaVu Sans", 10), padx=14, pady=5,
                           cursor="hand2")
            btn.pack(side="top")
            ind = tk.Frame(holder, bg=COL_PANEL, height=2)
            ind.pack(side="top", fill="x")
            btn.bind("<Button-1>", lambda _e, v=val: self._select_tab(v))
            self._tabs.append((val, btn, ind))
        self._highlight()

        # ---- map tab ----
        self.map_wrap = ttk.Frame(self.frame, style="TFrame")
        mbody = ttk.Frame(self.map_wrap, style="TFrame")
        mbody.pack(fill="both", expand=True)
        # side list of favorites (click to focus)
        side = ttk.Frame(mbody, style="Panel.TFrame", width=150)
        side.pack(side="left", fill="y", padx=(12, 6), pady=8)
        side.pack_propagate(False)
        ttk.Label(side, text="Show", style="Muted.TLabel").pack(
            anchor="w", padx=8, pady=(6, 2))
        self.focus_norad = None
        _listwrap = ttk.Frame(side, style="Panel.TFrame")
        _listwrap.pack(fill="both", expand=True, padx=4, pady=4)
        self._list = tk.Listbox(_listwrap, bg=COL_PANEL, fg=COL_TEXT,
                                font=FONT_MONO, selectbackground=COL_ACCENT,
                                borderwidth=0, highlightthickness=0,
                                activestyle="none", exportselection=False)
        _lsb = ttk.Scrollbar(_listwrap, orient="vertical",
                             command=self._list.yview)
        self._list.configure(yscrollcommand=_lsb.set)
        _lsb.pack(side="right", fill="y")
        self._list.pack(side="left", fill="both", expand=True)
        self._list.bind("<<ListboxSelect>>", self._on_pick)
        mp = ttk.Frame(mbody, style="Panel.TFrame")
        mp.pack(side="left", fill="both", expand=True, padx=(6, 12), pady=8)
        self.mpl = MplPanel(mp, figsize=(8.6, 4.8), polar=False)
        self.mpl.pack(fill="both", expand=True, padx=6, pady=6)

        # ---- passes tab ----
        self.pass_wrap = ttk.Frame(self.frame, style="TFrame")
        cols = ("sat", "aos", "maxel", "dur", "count")
        heads = ("Satellite", "AOS (UTC)", "Max El", "Duration", "Countdown")
        widths = {"sat": 130, "aos": 150, "maxel": 90, "dur": 100,
                  "count": 150}
        _twrap = ttk.Frame(self.pass_wrap, style="TFrame")
        _twrap.pack(fill="both", expand=True, padx=16, pady=10)
        self.tree = ttk.Treeview(_twrap, columns=cols,
                                 show="headings", height=18)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c],
                             anchor="w" if c in ("sat", "count") else "center")
        self.tree.tag_configure("now", foreground=COL_ACCENT2)
        _tvsb = ttk.Scrollbar(_twrap, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=_tvsb.set)
        _tvsb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-Button-1>", self._on_pass_pick)
        self.pass_info = tk.StringVar(value="")
        ttk.Label(self.pass_wrap, textvariable=self.pass_info,
                  style="Muted.TLabel").pack(anchor="w", padx=16, pady=(0, 8))
        ttk.Button(self.pass_wrap, text="Print 7-day schedule (all favorites)\u2026",
                   command=self._print_favorites_report).pack(anchor="w",
                                                              padx=16,
                                                              pady=(0, 8))

        # per-favorite predictors and cached next-pass list
        self._preds = {}            # norad -> Predictor
        self._nextpass = {}         # norad -> PassPredict or None
        self._pass_calc_at = 0
        self._counter = 0
        self._build_favlist()
        self._select_tab("map")

    # ---- tab management ----
    def _highlight(self):
        for val, btn, ind in self._tabs:
            on = (val == self.tab.get())
            btn.configure(fg=COL_ACCENT if on else COL_MUTED,
                          font=("DejaVu Sans", 10, "bold") if on
                          else ("DejaVu Sans", 10))
            ind.configure(bg=COL_ACCENT if on else COL_PANEL)

    def _select_tab(self, val):
        self.tab.set(val)
        self._highlight()
        self.map_wrap.pack_forget()
        self.pass_wrap.pack_forget()
        if val == "map":
            self.map_wrap.pack(fill="both", expand=True)
        else:
            self.pass_wrap.pack(fill="both", expand=True)
        self._refresh(now_unix())

    # ---- favorites bookkeeping ----
    def _favsats(self):
        return [s for s in self.store.db.sats
                if s.norad in self.store.favorites]

    def _pred_for(self, s):
        p = self._preds.get(s.norad)
        if p is None:
            p = Predictor()
            p.set_site(self.store.obs)
            p.set_sat(s)
            self._preds[s.norad] = p
        return p

    def _build_favlist(self):
        self._list.delete(0, "end")
        self._list.insert("end", "\u25c9 All")
        self._favorder = self._favsats()
        for i, s in enumerate(self._favorder):
            col = PALETTE[i % len(PALETTE)]
            self._list.insert("end", "  %s" % s.name)
            self._list.itemconfigure(i + 1, foreground=col)
        self._list.selection_clear(0, "end")
        self._list.selection_set(0)

    def _on_pick(self, _evt=None):
        sel = self._list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == 0:
            self.focus_norad = None
        elif 1 <= idx <= len(self._favorder):
            self.focus_norad = self._favorder[idx - 1].norad
            # make this the app-wide selected satellite
            self.store.select(self.focus_norad)
            self.store.save_config()
        self._refresh(now_unix())

    def _on_pass_pick(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self._row_norad):
            norad = self._row_norad[idx]
            self.store.select(norad)
            self.store.save_config()
            self.focus_norad = norad
            sat = self.store.db.get(norad)
            self.app.set_status("Selected %s" % (sat.name if sat else norad))

    def on_show(self):
        # favorites may have changed since last visit
        self._preds = {}
        self._build_favlist()
        self._nextpass = {}
        self._pass_calc_at = 0
        self._refresh(now_unix())

    def on_tick(self, now_dt):
        self._counter += 1
        t = now_dt.timestamp()
        if self.tab.get() == "map":
            if self._counter % 2 == 0:        # map every 2 s
                self._draw_map(t)
        else:
            self._update_countdowns(t)        # countdown every second

    def _refresh(self, t):
        if self.tab.get() == "map":
            self._draw_map(t)
        else:
            self._rebuild_passes(t)

    # ================= MAP =================
    def _draw_map(self, t):
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        draw_basemap(ax)
        self._draw_terminator(ax, t)

        favs = self._favorder
        if not favs:
            ax.set_title("No favorites yet \u2014 mark some on the Satellites "
                         "screen (space bar).", color=COL_MUTED, fontsize=10)
            ax.plot([self.store.obs.lon], [self.store.obs.lat], "^",
                    color=COL_WARN, markersize=10, zorder=6)
            ax.set_xlim(-180, 180)
            ax.set_ylim(-90, 90)
            self.mpl.draw()
            return

        shown = 0
        for i, s in enumerate(favs):
            if self.focus_norad and s.norad != self.focus_norad:
                continue
            col = PALETTE[i % len(PALETTE)]
            p = self._pred_for(s)
            lat, lon, alt = p.subpoint_at(t)
            self._footprint(ax, lat, lon, alt, col)
            ax.plot([lon], [lat], "o", color=col, markersize=8, zorder=6)
            # place the label on whichever side keeps it inside the map, and
            # nudge vertically away from the top/bottom edges
            ha = "right" if lon > 120 else "left"
            dx = -6 if ha == "right" else 6
            va = "top" if lat > 60 else ("bottom" if lat < -60 else "center")
            dy = -6 if va == "top" else (6 if va == "bottom" else 4)
            ax.annotate(s.name, (lon, lat), color=COL_TEXT, fontsize=8,
                        xytext=(dx, dy), textcoords="offset points",
                        ha=ha, va=va, zorder=7,
                        clip_on=True,
                        annotation_clip=True)
            if self.focus_norad:
                # draw the ground track for the focused satellite
                self._track(ax, p, s, t, col)
            shown += 1
        ax.plot([self.store.obs.lon], [self.store.obs.lat], "^",
                color=COL_WARN, markersize=10, zorder=6)
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        title = ("%s" % favs[[s.norad for s in favs].index(self.focus_norad)].name
                 if self.focus_norad else "%d favorite satellites" % shown)
        ax.set_title(title, color=COL_TEXT, fontsize=10)
        self.mpl.draw()

    def _track(self, ax, p, s, t, col):
        period = s.period_min * 60.0 if s.period_min else 5400.0
        pts = []
        for k in range(-30, 31):
            lat, lon, _ = p.subpoint_at(t + (k / 60.0) * period)
            pts.append((lon, lat))
        seg_lo, seg_la, prev = [], [], None
        for lon, lat in pts:
            if prev is not None and abs(lon - prev) > 180:
                ax.plot(seg_lo, seg_la, color=col, linewidth=1.0, alpha=0.7)
                seg_lo, seg_la = [], []
            seg_lo.append(lon)
            seg_la.append(lat)
            prev = lon
        if seg_lo:
            ax.plot(seg_lo, seg_la, color=col, linewidth=1.0, alpha=0.7)

    def _footprint(self, ax, lat0, lon0, alt, col):
        p0 = self._any_pred()
        radius = p0.footprint_radius_km(alt)
        ang = radius / 6378.135
        pts = []
        for b in range(0, 361, 6):
            br = math.radians(b)
            la = math.asin(math.sin(math.radians(lat0)) * math.cos(ang) +
                           math.cos(math.radians(lat0)) * math.sin(ang) *
                           math.cos(br))
            lo = math.radians(lon0) + math.atan2(
                math.sin(br) * math.sin(ang) * math.cos(math.radians(lat0)),
                math.cos(ang) - math.sin(math.radians(lat0)) * math.sin(la))
            pts.append((math.degrees(lo), math.degrees(la)))
        seg_lo, seg_la, prev = [], [], None
        for lo, la in pts:
            lo = ((lo + 180) % 360) - 180
            if prev is not None and abs(lo - prev) > 180:
                ax.plot(seg_lo, seg_la, color=col, linewidth=1.0, alpha=0.6)
                seg_lo, seg_la = [], []
            seg_lo.append(lo)
            seg_la.append(la)
            prev = lo
        if seg_lo:
            ax.plot(seg_lo, seg_la, color=col, linewidth=1.0, alpha=0.6)

    def _any_pred(self):
        if self._preds:
            return next(iter(self._preds.values()))
        return self.store.pred

    def _draw_terminator(self, ax, t):
        jd = jd_of(t)
        sx, sy, sz = _sun_eci_unit(jd)
        th = _gmst_rad(jd)
        ss_lat = math.degrees(math.asin(sz))
        ss_lon = ((math.degrees(math.atan2(sy, sx) - th) + 180) % 360) - 180
        lons = list(range(-180, 181, 2))
        slat = math.radians(ss_lat)
        slon = math.radians(ss_lon)
        night = []
        for lon in lons:
            lo = math.radians(lon)
            night.append(math.degrees(
                math.atan(-math.cos(lo - slon) / math.tan(slat))
                if abs(slat) > 1e-6 else 0.0))
        if ss_lat >= 0:
            ax.fill_between(lons, night, -90, color="#000010", alpha=0.42,
                            zorder=2)
        else:
            ax.fill_between(lons, night, 90, color="#000010", alpha=0.42,
                            zorder=2)

    # ================= NEXT PASSES =================
    def _rebuild_passes(self, t):
        for i in self.tree.get_children():
            self.tree.delete(i)
        favs = self._favsats()
        if not favs:
            self.pass_info.set("No favorites yet \u2014 mark some on the "
                               "Satellites screen.")
            return
        self._nextpass = {}
        rows = []
        for s in favs:
            p = self._pred_for(s)
            nxt = p.predict_passes(t - 600, self.store.min_el, 1,
                                   t + 6 * 86400)
            np_ = nxt[0] if nxt else None
            self._nextpass[s.norad] = np_
            rows.append((s, np_))
        # sort by soonest AOS (overhead first), None last
        rows.sort(key=lambda r: (r[1] is None,
                                 r[1].aos if r[1] else 1e18))
        self._row_norad = []
        for s, np_ in rows:
            self._row_norad.append(s.norad)
            if np_ is None:
                self.tree.insert("", "end", values=(
                    s.name, "\u2014", "\u2014", "\u2014", "no pass / 6 d"))
                continue
            self.tree.insert("", "end", values=(
                s.name, fmt_utc(np_.aos, "%m-%d %H:%M:%S"),
                "%.0f\u00b0" % np_.max_el, fmt_hms(np_.los - np_.aos),
                self._countdown_text(np_, t)),
                tags=("now",) if np_.aos <= t <= np_.los else ())
        self._pass_calc_at = t
        self.pass_info.set("%d favorites \u2014 soonest pass first. "
                           "Countdown updates live." % len(favs))

    def _countdown_text(self, p, t):
        if p.aos <= t <= p.los:
            return "OVERHEAD \u2014 LOS %s" % fmt_hms(p.los - t)
        return "AOS in %s" % fmt_hms(p.aos - t)

    def _update_countdowns(self, t):
        # recompute the underlying passes every ~5 min; refresh countdowns each
        # second by rewriting just the countdown cell
        if t - self._pass_calc_at > 300:
            self._rebuild_passes(t)
            return
        items = self.tree.get_children()
        for idx, item in enumerate(items):
            if idx >= len(self._row_norad):
                break
            np_ = self._nextpass.get(self._row_norad[idx])
            if np_ is None:
                continue
            self.tree.set(item, "count", self._countdown_text(np_, t))
            # promote to overhead styling if it just came into view
            self.tree.item(item, tags=("now",) if np_.aos <= t <= np_.los
                           else ())

    def _print_favorites_report(self):
        from tkinter import filedialog, messagebox
        from ..reports import generate_favorites_passes_report
        if not self.store.favorites:
            messagebox.showinfo("Favorites report", "No favorite satellites "
                                "yet. Mark some with the star on the Satellites "
                                "screen.")
            return
        path = filedialog.asksaveasfilename(
            title="Save favorites pass schedule", defaultextension=".pdf",
            initialfile="favorites_passes_7day.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_favorites_passes_report(path, self.store, days=7)
        except Exception as e:
            messagebox.showerror("Report", "Could not generate report:\n%s" % e)
            return
        self.app.set_status("Saved favorites pass schedule: %s" % path)
        messagebox.showinfo("Report", "Saved a 7-day pass schedule for all "
                            "favorite satellites.")
