"""illum.py - illumination raster plus eclipse ephemeris tables.

Tab 1 (Illumination raster): days on X (today at left), one orbital period on Y.
Scroll forward/back through the timeline indefinitely; the eclipse band widens
and narrows as the orbit plane precesses relative to the Sun.

Tab 2 (Eclipse table): Nova-style umbral-eclipse ephemeris for the selected
satellite -- an orbit-by-orbit list (enter / exit / duration / interval) and a
daily summary (total, longest, percent of day, sun/beta angle). Useful for
spacecraft power-budget planning. Both sub-tables are CSV-exportable.
"""

import tkinter as tk
from tkinter import ttk
import numpy as np

from . import (Screen, MplPanel, TabBar, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, now_unix, fmt_utc)
from .. import exports as EX

WINDOW_DAYS = 30          # days shown at once in the raster
PHASE_ROWS = 96           # vertical resolution (one period)
ECLIPSE_DAYS = 7          # span of the eclipse tables


class IllumScreen(Screen):
    def build(self):
        self.sat_header("Illumination \u2014 sunlit / eclipse")
        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        self._tab_raster = tabs.add("Illumination raster")
        self._tab_ecl = tabs.add("Eclipse table")
        tabs.on_change = self._on_tab
        self._build_raster(self._tab_raster)
        self._build_eclipse(self._tab_ecl)

    def on_show(self):
        self._render()

    def _on_tab(self, idx):
        if idx == 1:
            self._render_eclipse()

    # ------------------------------------------------------------------
    # Tab 1: illumination raster (unchanged behaviour)
    # ------------------------------------------------------------------
    def _build_raster(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=(0, 2))
        ttk.Button(bar, text="\u25c0 back",
                   command=lambda: self._scroll(-7)).pack(side="left", padx=2)
        ttk.Button(bar, text="forward \u25b6",
                   command=lambda: self._scroll(7)).pack(side="left", padx=2)
        ttk.Button(bar, text="\u23ce today", command=self._reset).pack(
            side="left", padx=8)
        ttk.Button(bar, text="Print 60-day\u2026",
                   command=self._print_report).pack(side="left", padx=4)
        self.range_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.range_var, style="TLabel").pack(
            side="left", padx=12)
        self.frac_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.frac_var, style="TLabel").pack(
            side="right", padx=12)

        wrap = ttk.Frame(parent, style="Panel.TFrame")
        wrap.pack(fill="both", expand=True, padx=4, pady=8)
        self.mpl = MplPanel(wrap, figsize=(9, 4.6), polar=False)
        self.mpl.pack(fill="both", expand=True, padx=8, pady=8)
        self.mpl.widget.bind("<Button-4>", lambda e: self._scroll(-3))
        self.mpl.widget.bind("<Button-5>", lambda e: self._scroll(3))
        self.mpl.widget.bind("<MouseWheel>",
                             lambda e: self._scroll(-3 if e.delta > 0 else 3))
        self._day0 = 0

    def _scroll(self, ddays):
        self._day0 = max(0, self._day0 + ddays)
        self._render()

    def _reset(self):
        self._day0 = 0
        self._render()

    def _render(self):
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        s = self.sat()
        if not s:
            self.range_var.set("")
            self.frac_var.set("No satellite selected.")
            self.mpl.draw()
            return
        self.pred().set_sat(s)
        period = s.period_min if s.period_min else 95.0
        t0 = now_unix() + self._day0 * 86400
        grid = np.zeros((PHASE_ROWS, WINDOW_DAYS))
        for d in range(WINDOW_DAYS):
            for r in range(PHASE_ROWS):
                tt = t0 + d * 86400 + (r / PHASE_ROWS) * period * 60.0
                grid[r, d] = 1.0 if self.pred().sunlit_at(tt) else 0.0
        ax.imshow(grid, aspect="auto", origin="lower",
                  extent=[self._day0, self._day0 + WINDOW_DAYS, 0, period],
                  cmap="cividis", interpolation="nearest", vmin=0, vmax=1)
        ax.set_xlabel("days from now")
        ax.set_ylabel("minutes into orbit (one period)")
        ax.set_title("%s \u2014 bright = sunlit, dark = eclipse" % s.name,
                     color=COL_TEXT, fontsize=10)
        self.mpl.draw()
        frac = 1.0 - grid.mean()
        self.frac_var.set("mean eclipse %.0f%% / orbit" % (frac * 100))
        self.range_var.set("%s  \u2192  %s" % (
            fmt_utc(t0, "%Y-%m-%d"),
            fmt_utc(t0 + WINDOW_DAYS * 86400, "%Y-%m-%d")))

    def _print_report(self):
        s = self.sat()
        if not s:
            return
        from tkinter import filedialog, messagebox
        from ..reports import generate_illumination_report
        default = "illumination_%s.pdf" % s.name.replace("/", "-").replace(
            " ", "_")
        path = filedialog.asksaveasfilename(
            title="Save illumination report", defaultextension=".pdf",
            initialfile=default, filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_illumination_report(path, self.store, s, days=60)
        except Exception as e:
            messagebox.showerror("Report", "Could not generate report:\n%s" % e)
            return
        self.app.set_status("Saved illumination report: %s" % path)
        messagebox.showinfo("Report", "Saved a 60-day illumination report for "
                            "%s." % s.name)

    # ------------------------------------------------------------------
    # Tab 2: eclipse ephemeris tables
    # ------------------------------------------------------------------
    def _build_eclipse(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=(0, 2))
        ttk.Label(bar, text="Span:", style="TLabel").pack(side="left")
        self._ecl_days = tk.IntVar(value=ECLIPSE_DAYS)
        for v in (1, 3, 7, 14):
            ttk.Radiobutton(bar, text="%dd" % v, value=v,
                            variable=self._ecl_days,
                            command=self._render_eclipse).pack(side="left")
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._export_eclipse).pack(side="right", padx=2)
        ttk.Button(bar, text="Print report\u2026",
                   command=self._print_eclipse).pack(side="right", padx=2)
        self._ecl_info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._ecl_info, style="TLabel").pack(
            side="left", padx=12)

        sub = TabBar(parent)
        sub.pack(fill="both", expand=True, padx=2, pady=(2, 2))
        page_orbit = sub.add("Every orbit")
        page_daily = sub.add("Daily summary")

        cols = ("enter", "exit", "dur", "intvl", "beta")
        heads = ("Enter (UTC)", "Exit (UTC)", "Duration",
                 "Interval between", "Sun angle")
        self._tree_orbit = ttk.Treeview(page_orbit, columns=cols,
                                        show="headings", height=18)
        widths = (170, 170, 100, 130, 90)
        for c, h, w in zip(cols, heads, widths):
            self._tree_orbit.heading(c, text=h)
            self._tree_orbit.column(c, width=w, anchor="center")
        self._tree_orbit.pack(fill="both", expand=True, padx=6, pady=6)

        cols2 = ("date", "n", "total", "longest", "pct", "beta")
        heads2 = ("Date", "Eclipses", "Total", "Longest",
                  "% of day", "Sun angle")
        self._tree_daily = ttk.Treeview(page_daily, columns=cols2,
                                        show="headings", height=18)
        widths2 = (110, 90, 100, 100, 90, 90)
        for c, h, w in zip(cols2, heads2, widths2):
            self._tree_daily.heading(c, text=h)
            self._tree_daily.column(c, width=w, anchor="center")
        self._tree_daily.pack(fill="both", expand=True, padx=6, pady=6)

        note = ("Umbral eclipse (Earth's shadow). Sun angle is the orbit-plane "
                "beta angle \u2014 high beta means shallow, short eclipses (or "
                "none in continuous sunlight).")
        ttk.Label(parent, text=note, style="Muted.TLabel",
                  wraplength=820, justify="left").pack(anchor="w", padx=8,
                                                       pady=(0, 6))
        self._ecl_periods = []
        self._ecl_summary = []

    def _render_eclipse(self):
        for t in (self._tree_orbit, self._tree_daily):
            for i in t.get_children():
                t.delete(i)
        s = self.sat()
        if not s:
            self._ecl_info.set("No satellite selected.")
            self._ecl_periods, self._ecl_summary = [], []
            return
        self.pred().set_sat(s)
        days = self._ecl_days.get()
        t0 = now_unix()
        periods = self.pred().predict_eclipses(t0, max_n=10000,
                                               horizon_days=float(days))
        summary = self.pred().eclipse_daily_summary(t0, days=days)
        self._ecl_periods, self._ecl_summary = periods, summary

        prev_exit = None
        for e in periods:
            intvl = EX._hms(e.enter - prev_exit) if prev_exit is not None \
                else "\u2014"
            self._tree_orbit.insert("", "end", values=(
                fmt_utc(e.enter, "%m-%d %H:%M:%S"),
                fmt_utc(e.exit, "%m-%d %H:%M:%S"),
                EX._hms(e.duration_s), intvl,
                "%+.1f\u00b0" % e.sun_angle))
            prev_exit = e.exit
        for r in summary:
            self._tree_daily.insert("", "end", values=(
                fmt_utc(r["date"], "%Y-%m-%d"), r["count"],
                EX._hms(r["total_s"]), EX._hms(r["longest_s"]),
                "%.1f%%" % r["percent"], "%+.1f\u00b0" % r["sun_angle"]))
        if periods:
            mean_min = sum(e.duration_s for e in periods) / len(periods) / 60.0
            self._ecl_info.set("%d eclipses over %d days, mean %.1f min"
                               % (len(periods), days, mean_min))
        else:
            self._ecl_info.set("No eclipses in the next %d days "
                               "(continuous sunlight)." % days)

    def _export_eclipse(self):
        s = self.sat()
        if not s or not self._ecl_periods:
            return
        h1, r1 = EX.eclipse_periods_rows(self._ecl_periods, s.name)
        h2, r2 = EX.eclipse_daily_rows(self._ecl_summary, s.name)
        csv = EX.rows_to_csv(h1, r1) + "\n" + EX.rows_to_csv(h2, r2)
        self.save_text_dialog(
            csv, "eclipses_%s.csv" % s.name.replace("/", "-").replace(" ", "_"),
            title="Export eclipse ephemeris", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    def _print_eclipse(self):
        s = self.sat()
        if not s or not self._ecl_periods:
            return
        from tkinter import filedialog, messagebox
        from ..reports import generate_eclipse_report
        default = "eclipses_%s.pdf" % s.name.replace("/", "-").replace(" ", "_")
        path = filedialog.asksaveasfilename(
            title="Save eclipse report", defaultextension=".pdf",
            initialfile=default, filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_eclipse_report(path, self.store, s,
                                    self._ecl_periods, self._ecl_summary)
        except Exception as e:
            messagebox.showerror("Report", "Could not generate report:\n%s" % e)
            return
        self.app.set_status("Saved eclipse report: %s" % path)
        messagebox.showinfo("Report", "Saved an eclipse report for %s."
                            % s.name)
