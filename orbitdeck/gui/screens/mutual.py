"""mutual.py - mutual (co-visibility) windows with a DX station."""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, TabBar, COL_BG, COL_TEXT, COL_MUTED,
               COL_ACCENT, COL_WARN, COL_GRID, fmt_hms, fmt_utc, now_unix, make_scrolled_tree)
from ...engine import Observer, grid_to_latlon
from ...engine.predict import Predictor


def _mhz(hz):
    """Format a dial frequency (Hz) as MHz to 3 decimals, or a dash for 0."""
    return "%.3f" % (hz / 1e6) if hz else "\u2014"


class MutualScreen(Screen):
    def build(self):
        self.sat_header("Mutual Windows \u2014 co-visibility with a DX station")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(bar, text="DX grid or lat,lon:", style="TLabel").pack(side="left")
        self.dx = tk.StringVar(value="IO91")
        ttk.Entry(bar, textvariable=self.dx, width=18).pack(side="left", padx=6)
        ttk.Label(bar, text="Min el:", style="TLabel").pack(side="left", padx=(12, 2))
        self.minel = tk.IntVar(value=0)
        for v in (0, 5, 10):
            ttk.Radiobutton(bar, text="%d\u00b0" % v, value=v, variable=self.minel,
                            command=self._reload).pack(side="left")
        ttk.Label(bar, text="Satellite:", style="TLabel").pack(
            side="left", padx=(12, 2))
        self.scope = tk.StringVar(value="selected")
        ttk.Radiobutton(bar, text="Selected", value="selected",
                        variable=self.scope, command=self._reload).pack(
            side="left")
        ttk.Radiobutton(bar, text="All favorites", value="favorites",
                        variable=self.scope, command=self._reload).pack(
            side="left", padx=(0, 4))
        # second row: actions, so a narrow window never clips the buttons
        bar2 = ttk.Frame(self.frame, style="TFrame")
        bar2.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(bar2, text="Compute", command=self._reload).pack(side="left")
        ttk.Button(bar2, text="Print mutual\u2026",
                   command=self._print_report).pack(side="left", padx=6)
        ttk.Button(bar2, text="Export CSV\u2026",
                   command=self._export_csv).pack(side="left")
        cols = ("sat", "start", "end", "dur", "myel", "dxel")
        heads = ("Satellite", "Start (UTC)", "End", "Duration", "My max el",
                 "DX max el")
        treewrap, self.tree = make_scrolled_tree(
            self.frame, cols, show="headings", height=16)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=150 if c == "start" else
                             (130 if c == "sat" else 105), anchor="center")
        treewrap.pack(fill="both", expand=True, padx=16, pady=10)
        self.tree.bind("<Double-1>", self._open_detail)
        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info, style="Muted.TLabel").pack(
            anchor="w", padx=16, pady=(0, 8))
        self._win_by_row = {}      # tree row id -> (MutualWindow, sat)
        self._dx_ll = None         # (lat, lon) of the DX station for detail
        self._all_rows = []        # [(sat, MutualWindow), ...] for export

    def on_show(self):
        pass

    def _parse_dx(self):
        txt = self.dx.get().strip()
        if "," in txt:
            try:
                a, b = txt.split(",")
                return float(a), float(b)
            except Exception:
                return None
        ll = grid_to_latlon(txt)
        return ll

    def _pred_for(self, s):
        """A Predictor pointed at satellite ``s`` from the primary station."""
        p = Predictor()
        p.set_site(self.store.obs)
        p.set_sat(s)
        return p

    def _reload(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._win_by_row = {}
        self._all_rows = []
        ll = self._parse_dx()
        if not ll:
            self.info.set("Could not parse DX location. Use a grid (IO91) or "
                          "lat,lon.")
            return
        self._dx_ll = ll
        dx = Observer(lat=ll[0], lon=ll[1], alt_m=0, valid=True)
        t = now_unix()
        min_el = float(self.minel.get())

        if self.scope.get() == "favorites":
            favs = [s for s in self.store.db.sats
                    if s.norad in self.store.favorites]
            if not favs:
                self.info.set("No favorites set. Star some satellites on the "
                              "Satellites screen, or switch to Selected.")
                return
            results = []          # (sat, window)
            for s in favs:
                pred = self._pred_for(s)
                wins = pred.mutual_windows(t, dx, min_el, 30, horizon_days=10)
                for w in wins:
                    results.append((s, w))
            # show every favorite's windows in one chronological list
            results.sort(key=lambda sw: sw[1].start)
            for s, w in results:
                row = self.tree.insert("", "end", values=(
                    s.name,
                    fmt_utc(w.start, "%m-%d %H:%M:%S"),
                    fmt_utc(w.end, "%H:%M:%S"),
                    fmt_hms(w.end - w.start),
                    "%.0f\u00b0" % w.my_max_el,
                    "%.0f\u00b0" % w.dx_max_el))
                self._win_by_row[row] = (w, s)
            self._all_rows = results
            self.info.set("%d mutual windows over 10 days across %d favorites "
                          "with DX at %.2f,%.2f. Double-click a window to see "
                          "the pass from each station."
                          % (len(results), len(favs), ll[0], ll[1]))
            return

        # selected-satellite mode (the original behaviour)
        s = self.sat()
        if not s:
            self.info.set("No satellite selected.")
            return
        wins = self.pred().mutual_windows(t, dx, min_el, 30, horizon_days=10)
        for w in wins:
            row = self.tree.insert("", "end", values=(
                s.name,
                fmt_utc(w.start, "%m-%d %H:%M:%S"),
                fmt_utc(w.end, "%H:%M:%S"),
                fmt_hms(w.end - w.start),
                "%.0f\u00b0" % w.my_max_el,
                "%.0f\u00b0" % w.dx_max_el))
            self._win_by_row[row] = (w, s)
            self._all_rows.append((s, w))
        self.info.set("%s: %d mutual windows over 10 days with DX at %.2f,%.2f. "
                      "Double-click a window to see the pass from each station."
                      % (s.name, len(wins), ll[0], ll[1]))

    def _print_report(self):
        s = self.sat()
        if not s:
            self.info.set("No satellite selected.")
            return
        ll = self._parse_dx()
        if not ll:
            self.info.set("Could not parse DX location. Use a grid (IO91) or "
                          "lat,lon.")
            return
        from tkinter import filedialog, messagebox
        from ..reports import generate_mutual_passes_report
        dx = Observer(lat=ll[0], lon=ll[1], alt_m=0, valid=True)
        default = "mutual_%s.pdf" % s.name.replace("/", "-").replace(" ", "_")
        path = filedialog.asksaveasfilename(
            title="Save mutual-windows report", defaultextension=".pdf",
            initialfile=default, filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_mutual_passes_report(path, self.store, s, dx,
                                          days=10,
                                          min_el=float(self.minel.get()))
        except Exception as e:
            messagebox.showerror("Report", "Could not generate report:\n%s" % e)
            return
        self.app.set_status("Saved mutual-windows report: %s" % path)
        messagebox.showinfo("Report", "Saved a mutual-windows report for %s "
                            "with the DX station." % s.name)

    # ---- pass detail from both stations ----
    def _open_detail(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        entry = self._win_by_row.get(sel[0])
        if not entry or not self._dx_ll:
            return
        w, s = entry
        if not s:
            return
        try:
            self._show_detail_window(s, w)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Pass detail",
                                 "Could not build the pass detail:\n%s" % e)

    def _export_csv(self):
        if not self._all_rows:
            self.info.set("Nothing to export \u2014 compute windows first.")
            return
        from .. import exports as EX
        ll = self._dx_ll or (0.0, 0.0)
        headers = ["satellite", "start_utc", "end_utc", "duration",
                   "my_max_el_deg", "dx_max_el_deg", "dx_lat", "dx_lon"]
        rows = []
        for s, w in self._all_rows:
            rows.append([
                s.name, fmt_utc(w.start), fmt_utc(w.end),
                fmt_hms(w.end - w.start), round(w.my_max_el, 1),
                round(w.dx_max_el, 1), round(ll[0], 3), round(ll[1], 3)])
        scope = "favorites" if self.scope.get() == "favorites" else "selected"
        self.save_text_dialog(
            EX.rows_to_csv(headers, rows), "mutual_windows_%s.csv" % scope,
            title="Export mutual windows", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    def _full_pass_bounds(self, my_pred, w):
        """Find the AOS/LOS of the full pass (>= 0 deg) that contains the
        mutual window, by walking outward from the window edges until each
        station's-independent elevation (my own) drops below the horizon."""
        step = 10.0
        # walk back from start while I'm above the horizon
        aos = w.start
        t = w.start
        while my_pred.azel_at(t)[1] >= 0 and t > w.start - 3600:
            aos = t
            t -= step
        # walk forward from end while I'm above the horizon
        los = w.end
        t = w.end
        while my_pred.azel_at(t)[1] >= 0 and t < w.end + 3600:
            los = t
            t += step
        return aos, los

    def _sample_track(self, pred, aos, los, step=10.0):
        """Return [(t, az, el), ...] for el >= 0 across [aos, los]."""
        pts = []
        t = aos
        while t <= los:
            az, el = pred.azel_at(t)
            if el >= 0:
                pts.append((t, az, el))
            t += step
        return pts

    def _show_detail_window(self, s, w):
        # build a predictor for THIS window's satellite from the primary station
        # (in all-favorites mode it may not be the currently-selected satellite)
        my_pred = self._pred_for(s)
        dx_obs = Observer(lat=self._dx_ll[0], lon=self._dx_ll[1], alt_m=0,
                          valid=True)
        dx_pred = Predictor()
        dx_pred.set_site(dx_obs)
        dx_pred.set_sat(s)

        aos, los = self._full_pass_bounds(my_pred, w)
        my_track = self._sample_track(my_pred, aos, los)
        # for the DX station, sample over the same time span but keep only the
        # part where the DX station itself sees the satellite above 0 deg
        dx_track = self._sample_track(dx_pred, aos, los)

        win = tk.Toplevel(self.app.root)
        win.title("Mutual pass \u2014 %s" % s.name)
        win.configure(bg=COL_BG)
        win.geometry("900x620")
        header = ("%s \u2014 mutual pass starting %s UTC  (mutual %s)"
                  % (s.name, fmt_utc(w.start, "%Y-%m-%d %H:%M:%S"),
                     fmt_hms(w.end - w.start)))
        tk.Label(win, text=header, bg=COL_BG, fg=COL_TEXT,
                 font=("TkDefaultFont", 11, "bold")).pack(anchor="w",
                                                          padx=14, pady=(10, 2))

        tabs = TabBar(win)
        t_sky = tabs.add("Sky tracks")
        t_dop = tabs.add("DX Doppler")
        tabs.pack(fill="both", expand=True, padx=8, pady=4)
        self._detail_tabs = tabs

        self._build_sky_tab(t_sky, s, w, my_track, dx_track)
        self._build_dxdoppler_tab(t_dop, s, w, dx_obs)

    def _build_sky_tab(self, parent, s, w, my_track, dx_track):
        tk.Label(parent, text="The grey arc is the full pass from that station; "
                 "the bold orange arc is the mutually-visible portion. "
                 "Circle = AOS, square = LOS.", bg=COL_BG, fg=COL_MUTED).pack(
            anchor="w", padx=14, pady=(8, 6))
        body = tk.Frame(parent, bg=COL_BG)
        body.pack(fill="both", expand=True, padx=8, pady=4)
        my_name = getattr(self.store, "obs_name", "My station")
        self._draw_station_polar(
            body, "left", "%s  (max el %.0f\u00b0)" % (my_name, w.my_max_el),
            my_track, w.start, w.end)
        self._draw_station_polar(
            body, "right",
            "DX %.2f,%.2f  (max el %.0f\u00b0)"
            % (self._dx_ll[0], self._dx_ll[1], w.dx_max_el),
            dx_track, w.start, w.end)

    def _build_dxdoppler_tab(self, parent, s, w, dx_obs):
        from ...engine import dxdoppler as DX
        tps = [tp for tp in (s.transponders or []) if tp.downlink]
        if not tps:
            tk.Label(parent, text="This satellite has no transponder data, so "
                     "DX Doppler dial frequencies can't be computed.",
                     bg=COL_BG, fg=COL_MUTED, wraplength=820,
                     justify="left").pack(anchor="w", padx=14, pady=14)
            return

        me_obs = self.store.obs
        my_name = getattr(self.store, "obs_name", "My station")
        st = {"sat": s, "w": w, "me": me_obs, "dx": dx_obs, "tps": tps}

        tk.Label(parent, text="Dial frequencies for both stations across the "
                 "mutual window. \u201cTrue rule\u201d holds the same spot in the "
                 "satellite passband (all four dials move). \u201cFixed\u201d locks "
                 "one dial for the whole window (the other three drift).",
                 bg=COL_BG, fg=COL_MUTED, wraplength=840, justify="left").pack(
            anchor="w", padx=14, pady=(8, 4))

        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=12, pady=4)

        # transponder picker (only if more than one)
        self._dxd_tp = tk.IntVar(value=0)
        if len(tps) > 1:
            ttk.Label(bar, text="Transponder:", style="TLabel").pack(
                side="left")
            names = []
            for i, tp in enumerate(tps):
                kind = "lin" if tp.is_linear else "FM"
                names.append("%d: %.3f/%.3f %s" % (
                    i + 1, tp.downlink / 1e6,
                    (tp.uplink / 1e6) if tp.uplink else 0.0, kind))
            cb = ttk.Combobox(bar, state="readonly", width=22, values=names)
            cb.current(0)
            cb.pack(side="left", padx=(2, 10))
            cb.bind("<<ComboboxSelected>>",
                    lambda _e: (self._dxd_tp.set(cb.current()),
                                self._dxd_render()))

        ttk.Label(bar, text="Mode:", style="TLabel").pack(side="left")
        self._dxd_mode = tk.StringVar(value=DX.TRUE_RULE)
        for lab, val in (("True rule", DX.TRUE_RULE),
                         ("Fixed downlink", DX.FIXED_DL),
                         ("Fixed uplink", DX.FIXED_UL)):
            ttk.Radiobutton(bar, text=lab, value=val, variable=self._dxd_mode,
                            command=lambda: self._dxd_render()).pack(
                side="left", padx=(2, 0))

        bar2 = ttk.Frame(parent, style="TFrame")
        bar2.pack(fill="x", padx=12, pady=2)
        # anchor: which station's dial is locked (fixed modes only)
        ttk.Label(bar2, text="Lock:", style="TLabel").pack(side="left")
        self._dxd_anchor = tk.StringVar(value=DX.ME_TX)
        anchor_opts = (("My TX", DX.ME_TX), ("My RX", DX.ME_RX),
                       ("DX TX", DX.DX_TX), ("DX RX", DX.DX_RX))
        self._dxd_anchor_lbls = {v: k for k, v in anchor_opts}
        self._dxd_anchor_btns = []
        for lab, val in anchor_opts:
            rb = ttk.Radiobutton(bar2, text=lab, value=val,
                                 variable=self._dxd_anchor,
                                 command=lambda: self._dxd_render())
            rb.pack(side="left", padx=(2, 0))
            self._dxd_anchor_btns.append(rb)

        # passband offset (linear only), as a percent of the downlink passband
        self._dxd_pb = tk.DoubleVar(value=50.0)
        self._dxd_pb_scale = ttk.Scale(bar2, from_=0.0, to=100.0,
                                       variable=self._dxd_pb,
                                       command=lambda _v: self._dxd_render())
        self._dxd_pb_lbl = ttk.Label(bar2, text="  Passband:", style="TLabel")

        cols = ("t", "myrx", "mytx", "dxrx", "dxtx")
        heads = ("UTC", "%s RX" % my_name, "%s TX" % my_name, "DX RX", "DX TX")
        treewrap, tree = make_scrolled_tree(parent, cols, show="headings",
                                            height=14)
        for c, h in zip(cols, heads):
            tree.heading(c, text=h)
            tree.column(c, width=150, anchor="center")
        treewrap.pack(fill="both", expand=True, padx=12, pady=(6, 2))
        info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=info, style="Muted.TLabel").pack(
            anchor="w", padx=14, pady=(0, 6))
        btnrow = ttk.Frame(parent, style="TFrame")
        btnrow.pack(fill="x", padx=12, pady=(0, 8))

        def render():
            tp = st["tps"][self._dxd_tp.get()]
            mode = self._dxd_mode.get()
            anchor = self._dxd_anchor.get()
            fixed = mode in (DX.FIXED_DL, DX.FIXED_UL)
            for rb in self._dxd_anchor_btns:
                rb.configure(state=("normal" if fixed else "disabled"))
            # passband control only for a linear transponder
            if tp.is_linear and tp.bandwidth() > 0:
                self._dxd_pb_lbl.pack(side="left", padx=(10, 0))
                self._dxd_pb_scale.pack(side="left", fill="x", expand=True,
                                        padx=(2, 8))
                pb_off = int(round(self._dxd_pb.get() / 100.0 * tp.bandwidth()))
            else:
                self._dxd_pb_lbl.pack_forget()
                self._dxd_pb_scale.pack_forget()
                pb_off = 0
            for i in tree.get_children():
                tree.delete(i)
            rows = DX.dx_doppler_table(
                st["w"].start, st["w"].end, st["sat"], st["me"], st["dx"], tp,
                pb_offset=pb_off, mode=mode, anchor=anchor, step_s=30.0)
            self._dxd_rows = rows
            for (t, my_rx, my_tx, dx_rx, dx_tx) in rows:
                tree.insert("", "end", values=(
                    fmt_utc(t, "%H:%M:%S"),
                    _mhz(my_rx), _mhz(my_tx), _mhz(dx_rx), _mhz(dx_tx)))
            if fixed:
                info.set("%d steps every 30 s. Locked dial: %s (held constant "
                         "for the whole window); the other three drift with "
                         "Doppler. 0.000 means no uplink."
                         % (len(rows), self._dxd_anchor_lbls.get(anchor,
                                                                 anchor)))
            else:
                info.set("%d steps every 30 s. Both stations hold the same spot "
                         "in the passband; all four dials move with each "
                         "station's own Doppler." % len(rows))

        ttk.Button(btnrow, text="Export CSV\u2026",
                   command=lambda: self._export_dxdoppler(s)).pack(side="right")
        self._dxd_render = render
        render()

    def _export_dxdoppler(self, s):
        rows = getattr(self, "_dxd_rows", None)
        if not rows:
            return
        from .. import exports as EX
        headers = ["utc", "my_rx_hz", "my_tx_hz", "dx_rx_hz", "dx_tx_hz"]
        out = [[fmt_utc(t), my_rx, my_tx, dx_rx, dx_tx]
               for (t, my_rx, my_tx, dx_rx, dx_tx) in rows]
        self.save_text_dialog(
            EX.rows_to_csv(headers, out),
            "dx_doppler_%s.csv" % s.name.replace("/", "-").replace(" ", "_"),
            title="Export DX Doppler", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    def _draw_station_polar(self, parent, side, title, track, mstart, mend):
        panel = MplPanel(parent, figsize=(4.3, 4.3), polar=True)
        panel.pack(side=side, fill="both", expand=True, padx=6, pady=4)
        ax = panel.ax
        ax.clear()
        panel._style_axes()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rgrids([0, 30, 60, 90], labels=["0", "30", "60", "90"],
                      color=COL_MUTED, fontsize=7)
        ax.set_thetagrids(range(0, 360, 45),
                          labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                          color=COL_MUTED, fontsize=8)
        ax.set_rlim(90, 0)
        ax.grid(True, color=COL_GRID, linewidth=0.6)
        if not track:
            ax.set_title(title + "\n(not visible)", color=COL_MUTED,
                         fontsize=9)
            panel.draw()
            return
        az = [math.radians(p[1]) for p in track]
        el = [p[2] for p in track]
        # full pass drawn muted, so the highlighted mutual portion stands out
        ax.plot(az, el, color=COL_MUTED, linewidth=1.6, alpha=0.9)
        # mutual portion (bold orange) -- the samples whose time is within
        # [mstart, mend]
        maz = [math.radians(p[1]) for p in track if mstart <= p[0] <= mend]
        mel = [p[2] for p in track if mstart <= p[0] <= mend]
        if maz:
            ax.plot(maz, mel, color=COL_WARN, linewidth=3.2, zorder=5)
        # AOS circle / LOS square (of the full pass)
        ax.plot([az[0]], [el[0]], "o", color=COL_ACCENT, markersize=7,
                zorder=6)
        ax.plot([az[-1]], [el[-1]], "s", color=COL_ACCENT, markersize=7,
                zorder=6)
        ax.set_title(title, color=COL_TEXT, fontsize=9.5)
        panel.draw()
