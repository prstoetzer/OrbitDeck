"""orbithistory.py (screen) - Space-Track orbital history.

Plots a satellite's historical mean elements (semi-major axis, eccentricity,
inclination, period, apogee/perigee, B*) from Space-Track's gp_history archive,
so you can see an orbit's whole life: launch, drift, manoeuvres and drag decay.

Unlike CardSat - which decimates into 120-240 bins to fit the ESP32's heap -
this keeps every row at full resolution. Binning is offered only as a display
option for very long spans.

gp_history is archival data, so a fetched history is cached to
~/.orbitdeck/sthist/<norad>.json and reused instead of re-queried.
"""

import json
import os
import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, TabBar, COL_MUTED, COL_ACCENT, COL_ACCENT2,
               fmt_utc, make_scrolled_tree)
from ...engine import spacetrack as ST


CACHE_DIR = os.path.join(os.path.expanduser("~"), ".orbitdeck", "sthist")


class OrbitHistoryScreen(Screen):
    sat_scoped = ("samples",)
    def build(self):
        self.sat_header("Orbital History \u2014 Space-Track archive")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        self.fetchbtn = ttk.Button(bar, text="Fetch history",
                                   command=self._fetch)
        self.fetchbtn.pack(side="left")
        ttk.Button(bar, text="Report\u2026",

                   command=self._report).pack(side="right", padx=4)
        ttk.Button(bar, text="Space-Track credentials\u2026",
                   command=self._creds).pack(side="left", padx=8)
        ttk.Label(bar, text="Plot:", style="TLabel").pack(side="left",
                                                          padx=(12, 2))
        self.col = tk.StringVar(value="APOAPSIS")
        self.colbox = ttk.Combobox(
            bar, textvariable=self.col, state="readonly", width=18,
            values=[ST.COLUMN_LABELS[c][0] for c in ST.COLUMNS])
        self.colbox.current(4)
        self.colbox.pack(side="left")
        self.colbox.bind("<<ComboboxSelected>>", lambda _e: self._redraw())
        self.showboth = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Apogee+perigee", variable=self.showboth,
                        command=self._redraw).pack(side="left", padx=8)
        self.info = tk.StringVar(value="No history loaded.")
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel", wraplength=760).pack(
            side="left", padx=10)

        # zoom is a window over the TIME axis; the value/rate/table views all
        # honour it, the analysis view deliberately does not - its question is
        # about the whole record.
        self.zoom = (0.0, 1.0)
        zb = ttk.Frame(self.frame, style="TFrame")
        zb.pack(fill="x", padx=16, pady=(0, 2))
        ttk.Label(zb, text="Time window:", style="TLabel").pack(side="left")
        for label, cmd in (("\u2212 wider", "out"), ("+ closer", "in"),
                           ("\u25c0 pan", "left"), ("pan \u25b6", "right"),
                           ("reset", "reset")):
            ttk.Button(zb, text=label, width=9,
                       command=lambda c=cmd: self._zoom(c)).pack(side="left",
                                                                 padx=2)
        self.zinfo = tk.StringVar(value="full record")
        ttk.Label(zb, textvariable=self.zinfo, style="Muted.TLabel").pack(
            side="left", padx=10)

        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        t_plot = tabs.add("Value")
        t_rate = tabs.add("Rate")
        t_an = tabs.add("Analysis")
        t_table = tabs.add("Summary")
        self.ratepanel = MplPanel(t_rate, figsize=(8, 4.6))
        self.ratepanel.widget.pack(fill="both", expand=True)
        self.antext = tk.StringVar(value="")
        ttk.Label(t_an, textvariable=self.antext, style="TLabel",
                  justify="left", anchor="nw").pack(fill="both", expand=True,
                                                     padx=12, pady=10)
        self.panel = MplPanel(t_plot, figsize=(8, 4.6))
        self.panel.widget.pack(fill="both", expand=True)

        cols = ("elem", "first", "last", "delta", "rate", "min", "max", "n")
        heads = ("Element", "First", "Last", "Change", "Per year", "Min",
                 "Max", "Samples")
        wrap, self.tree = make_scrolled_tree(t_table, cols, show="headings",
                                             height=10)
        for c, h, wdt in zip(cols, heads, (150, 110, 110, 110, 110, 100, 100,
                                           80)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=wdt,
                             anchor="w" if c == "elem" else "center")
        wrap.pack(fill="both", expand=True)

        note = ("Historical mean elements from Space-Track's gp_history "
                "archive (your own login required). Archival data: a fetched "
                "history is cached locally and not re-queried.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))
        self.samples = []

    # ---- credentials ----
    def _creds(self):
        from tkinter import simpledialog
        user = simpledialog.askstring(
            "Space-Track", "Space-Track user (email):", parent=self.frame,
            initialvalue=self.store.config.get("spacetrack_user", ""))
        if user is None:
            return
        pw = simpledialog.askstring("Space-Track", "Space-Track password:",
                                    parent=self.frame, show="*")
        if pw is None:
            return
        self.store.prefs["spacetrack_user"] = user
        self.store.prefs["spacetrack_pass"] = pw
        self.store.save_config()
        self.info.set("Saved Space-Track credentials for %s." % user)

    # ---- cache ----
    #: overridable so tests can point at a scratch directory
    CACHE = CACHE_DIR

    def _cache_path(self, norad):
        return os.path.join(self.CACHE, "%d.json" % int(norad))

    def _load_cache(self, norad):
        try:
            with open(self._cache_path(norad)) as f:
                return json.load(f)
        except Exception:
            return None

    def _save_cache(self, norad, samples):
        try:
            os.makedirs(self.CACHE, exist_ok=True)
            with open(self._cache_path(norad), "w") as f:
                json.dump(samples, f)
        except Exception:
            pass

    def on_sat_changed(self):
        """The satellite moved on: the previous bird's archive must not stay on
        screen under the new name. Reset the view state too - a zoom window and
        a chosen element belong to the record they were chosen for."""
        self.zoom = (0.0, 1.0)
        self.zinfo.set("full record")
        self.info.set("No history loaded.")
        self.antext.set("")
        try:
            self._redraw()
            self._fill_table()
        except Exception:
            pass

    def on_show(self):
        self.refresh_sat_header()
        sat = self.store.selected_sat()
        if not sat:
            self.info.set("No satellite selected.")
            return
        if not self.samples:
            cached = self._load_cache(sat.norad)
            if cached:
                self.samples = cached
                self.info.set("%d archived element sets for %s (cached)."
                              % (len(cached), sat.name))
            else:
                self.info.set("No cached history for %s \u2014 fetch it."
                              % sat.name)
        self._redraw()
        self._fill_table()

    # ---- fetch ----
    def _fetch(self):
        sat = self.store.selected_sat()
        if not sat:
            self.info.set("No satellite selected.")
            return
        user = self.store.config.get("spacetrack_user", "")
        pw = self.store.config.get("spacetrack_pass", "")
        if not user or not pw:
            self.info.set("Set your Space-Track credentials first.")
            return
        self.info.set("Fetching history for %s\u2026" % sat.name)
        self.fetchbtn.state(["disabled"])
        norad = sat.norad

        def work():
            try:
                try:
                    cli = ST.SpaceTrackClient(user, pw)
                    samples = cli.fetch_history(norad)
                except Exception as e:
                    self._ui(lambda e=e: self._failed(str(e)))
                    return
                self._ui(lambda: self._loaded(norad, samples))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _failed(self, msg):
        self.fetchbtn.state(["!disabled"])
        self.info.set(msg[:110])

    def _loaded(self, norad, samples):
        self.fetchbtn.state(["!disabled"])
        self.samples = samples
        if not samples:
            self.info.set("No archived elements returned for this object.")
            return
        self._save_cache(norad, samples)
        span = (samples[-1]["epoch"] - samples[0]["epoch"]) / 86400.0 / 365.25
        self.info.set("%d element sets over %.1f years (full resolution)."
                      % (len(samples), span))
        self._redraw()
        self._fill_table()

    # ---- rendering ----
    def _zoom(self, cmd):
        lo, hi = self.zoom
        span = hi - lo
        ctr = 0.5 * (lo + hi)
        if cmd == "reset":
            lo, hi = 0.0, 1.0
        elif cmd == "in":
            span = max(0.02, span / 2.0)
            lo, hi = ctr - span / 2, ctr + span / 2
        elif cmd == "out":
            span = min(1.0, span * 2.0)
            lo, hi = ctr - span / 2, ctr + span / 2
        else:
            step = span / 4.0 * (1 if cmd == "right" else -1)
            lo, hi = lo + step, hi + step
        if lo < 0:
            hi -= lo
            lo = 0.0
        if hi > 1:
            lo -= hi - 1
            hi = 1.0
        self.zoom = (max(0.0, lo), min(1.0, hi))
        self.zinfo.set("full record" if self.zoom == (0.0, 1.0)
                       else "showing %.0f%%-%.0f%% of the record"
                       % (self.zoom[0] * 100, self.zoom[1] * 100))
        self._redraw()
        self._fill_table()

    def _visible(self):
        return ST.window(self.samples, *self.zoom)

    def _sel_column(self):
        label = self.col.get()
        for c in ST.COLUMNS:
            if ST.COLUMN_LABELS[c][0] == label:
                return c
        return "APOAPSIS"

    def _redraw(self):
        import datetime as dt
        self.panel.fig.clf()
        ax = self.panel.fig.add_subplot(111)
        self.panel.ax = ax
        ax.set_facecolor("#0d1117")
        for s in ax.spines.values():
            s.set_color(COL_MUTED)
        ax.tick_params(colors=COL_MUTED, labelsize=8)
        if not self.samples:
            self.antext.set("No history loaded.")
            ax.text(0.5, 0.5, "No history loaded", color=COL_MUTED,
                    ha="center", va="center", transform=ax.transAxes)
            self.panel.canvas.draw_idle()
            return
        col = self._sel_column()
        self._draw_rate(col)
        self._draw_analysis(col)
        pairs = [(col, COL_ACCENT2)]
        if self.showboth.get() and col in ("APOAPSIS", "PERIAPSIS"):
            pairs = [("APOAPSIS", COL_ACCENT2), ("PERIAPSIS", COL_ACCENT)]
        vis = self._visible()
        for c, colour in pairs:
            ts, vs = ST.series(vis, c)
            if not vs:
                continue
            xs = [dt.datetime.fromtimestamp(t, dt.timezone.utc) for t in ts]
            ax.plot(xs, vs, "-", color=colour, lw=1.0,
                    label=ST.COLUMN_LABELS[c][0])
        label, unit = ST.COLUMN_LABELS[col]
        ax.set_ylabel(("%s (%s)" % (label, unit)) if unit else label,
                      color=COL_MUTED, fontsize=9)
        ax.grid(True, color="#20304a", lw=0.5)
        leg = ax.legend(loc="best", fontsize=8, facecolor="#161b22",
                        edgecolor="#30363d")
        for t in leg.get_texts():
            t.set_color(COL_MUTED)
        self.panel.fig.autofmt_xdate()
        self.panel.fig.tight_layout()
        self.panel.canvas.draw_idle()

    def _draw_rate(self, col):
        """Rate of change: drag and manoeuvres read directly off this."""
        import datetime as dt
        self.ratepanel.fig.clf()
        ax = self.ratepanel.fig.add_subplot(111)
        ax.set_facecolor("#0d1117")
        for sp in ax.spines.values():
            sp.set_color(COL_MUTED)
        ax.tick_params(colors=COL_MUTED, labelsize=8)
        ts, rr = ST.rate_series(self._visible(), col)
        if not rr:
            ax.text(0.5, 0.5, "not enough data for a rate", color=COL_MUTED,
                    ha="center", va="center", transform=ax.transAxes)
        else:
            xs = [dt.datetime.fromtimestamp(t, dt.timezone.utc) for t in ts]
            ax.plot(xs, rr, "-", color=COL_ACCENT2, lw=0.9)
            ax.axhline(0, color=COL_MUTED, lw=0.8)
            label, unit = ST.COLUMN_LABELS[col]
            ax.set_ylabel("%s per year%s" % (label,
                                             (" (%s)" % unit) if unit else ""),
                          color=COL_MUTED, fontsize=9)
            ax.grid(True, color="#20304a", lw=0.5)
            self.ratepanel.fig.autofmt_xdate()
        self.ratepanel.fig.tight_layout()
        self.ratepanel.canvas.draw_idle()

    def _draw_analysis(self, col):
        """Has the rate itself changed? Whole record, ignoring the zoom."""
        a = ST.analyse_rate(self.samples, col)
        label, unit = ST.COLUMN_LABELS[col]
        if a is None:
            self.antext.set("%s\n\nNot enough data for analysis "
                            "(needs at least four usable intervals)." % label)
            return
        per = "%s/yr" % (unit or "units")
        lines = [
            "%s \u2014 rate analysis over the whole record" % label,
            "",
            "  Verdict            %s" % a["verdict"],
            "",
            "  Early era mean     %.4g %s" % (a["early_mean"], per),
            "  Late era mean      %.4g %s" % (a["late_mean"], per),
            "  Acceleration       %.4g %s per year" % (a["accel_per_year"],
                                                       per),
            "  Median |rate|      %.4g %s" % (a["median_abs"], per),
            "  Peak |rate|        %.4g %s  on %s" % (
                a["peak_rate"], per, fmt_utc(a["peak_time"], "%Y-%m-%d")),
            "  Jumps (>5x median) %d" % a["n_jumps"],
            "  Intervals used     %d" % a["n"],
            "",
            "  Span               %s to %s" % (
                fmt_utc(a["t_first"], "%Y-%m-%d"),
                fmt_utc(a["t_last"], "%Y-%m-%d")),
        ]
        if a["jumps"]:
            lines.append("")
            lines.append("  Largest jumps:")
            for t, r in sorted(a["jumps"], key=lambda j: -abs(j[1]))[:5]:
                lines.append("    %s   %+.4g %s" % (
                    fmt_utc(t, "%Y-%m-%d"), r, per))
            lines.append("")
            lines.append("  A jump is a rate far above this object's own "
                         "normal - a manoeuvre, a drag event, or an element-set "
                         "discontinuity.")
        self.antext.set("\n".join(lines))

    def _fill_table(self):
        self.tree.delete(*self.tree.get_children())
        for r in ST.summarize(self._visible()):
            self.tree.insert("", "end", values=(
                "%s%s" % (r["label"],
                          (" (%s)" % r["unit"]) if r["unit"] else ""),
                "%.5g" % r["first"], "%.5g" % r["last"],
                "%+.4g" % r["delta"], "%+.4g" % r["rate_per_year"],
                "%.5g" % r["min"], "%.5g" % r["max"], r["n"]))
        vis = self._visible()
        if vis:
            self.tree.insert("", "end", values=(
                "span", fmt_utc(vis[0]["epoch"], "%Y-%m-%d"),
                fmt_utc(vis[-1]["epoch"], "%Y-%m-%d"),
                "", "", "", "", len(vis)))

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
        save_report_dialog(self, "orbithistory", title="Orbital history", subtitle="Space-Track element archive",
                           sections=[("", "table", (cols, rows))])
