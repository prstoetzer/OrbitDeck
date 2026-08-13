"""astronomy.py - the observing-astronomy hub.

Meteor showers, Jupiter decametric windows, aurora, twilight, EME conditions,
lunar occultations and planetary appulses. Everything runs on the same Sun,
Moon and planet models the rest of OrbitDeck uses, so these screens agree with
Sun/Moon and EME rather than offering a second opinion.

A planning tool, not an almanac: times land within a few minutes, which is
enough to decide whether to set an alarm.
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, MplPanel, TabBar, COL_ACCENT2, COL_MUTED,
               COL_WARN,
               fmt_utc, make_scrolled_tree, now_unix)
from ..mapdraw import draw_basemap
from ...engine import astronomy as AS

TABS = ["Meteor showers", "Jupiter", "Aurora", "Twilight", "EME conditions",
        "Occultations", "Appulses", "Eclipses"]


class AstronomyScreen(Screen):
    REPORT_TITLE = "Astronomy"

    def build(self):
        self.header("Astronomy")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(bar, text="Refresh",
                   command=self._render).pack(side="left")
        ttk.Button(bar, text="Print screen\u2026",
                   command=self._report).pack(side="right", padx=4)
        self.info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel",
                  wraplength=780).pack(side="left", padx=12)

        self.tabs = TabBar(self.frame, TABS, self._on_tab)
        self.body = ttk.Frame(self.frame, style="TFrame")
        self.body.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self._tab = 0
        self._rows = []
        self._render()

    def on_show(self):
        self._render()

    def _on_tab(self, idx):
        self._tab = idx
        self._render()

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    # ---- rendering -------------------------------------------------------
    def _render(self):
        self._clear()
        obs = self.store.obs
        if obs is None or not getattr(obs, "valid", True):
            self.info.set("Set your QTH first (Settings).")
            return
        t = now_unix()
        name = TABS[self._tab]
        try:
            getattr(self, "_tab_%d" % self._tab)(obs, t)
        except Exception as exc:
            self.info.set("%s failed: %s" % (name, str(exc)[:90]))

    def _tree(self, cols, heads, widths):
        wrap, tree = make_scrolled_tree(self.body, cols, show="headings",
                                        height=15)
        for c, h, w in zip(cols, heads, widths):
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="w")
        wrap.pack(fill="both", expand=True)
        return tree

    def _tab_0(self, obs, t):
        rows = AS.meteor_showers(obs.lat, obs.lon, t)
        tree = self._tree(
            ("name", "peak", "days", "zhr", "el", "moon", "verdict"),
            ("Shower", "Peak (02:00 UTC)", "In", "ZHR", "Radiant el",
             "Moon", "For meteor scatter"),
            (130, 150, 70, 60, 90, 80, 380))
        for r in rows:
            tree.insert("", "end", values=(
                r["name"], fmt_utc(r["peak"]),
                "%.0f d" % r["days"] if r["days"] >= 0 else "now",
                r["zhr"], "%+.0f\u00b0" % r["radiant_el"],
                "%.0f%%" % (r["moon_illum"] * 100), r["verdict"]))
        self._rows = [("Meteor showers", "tree", tree)]
        self.info.set("Radiant elevation is taken at 02:00 UTC on peak night "
                      "\u2014 meteor-scatter prime time. A bright Moon spoils "
                      "the visual show but not the radio.")

    def _tab_1(self, obs, t):
        st = AS.jupiter_status(obs.lat, obs.lon, t)
        kv = KVPanel(self.body, label_width=22)
        kv.pack(fill="x")
        kv.row("CML (System III)", "%.1f\u00b0" % st["cml_deg"])
        kv.row("Io phase", "%.1f\u00b0" % st["io_phase_deg"])
        kv.row("Jupiter az / el", "%.1f\u00b0 / %+.1f\u00b0"
               % (st["az"], st["el"]),
               COL_ACCENT2 if st["up"] else COL_MUTED)
        kv.row("Status", st["verdict"],
               COL_ACCENT2 if st["active"] and st["up"] else COL_MUTED)
        wins = AS.jupiter_windows(obs.lat, obs.lon, t)
        tree = self._tree(("src", "start", "end", "el"),
                          ("Source", "Start", "End", "Max el"),
                          (100, 170, 170, 90))
        for w in wins:
            tree.insert("", "end", values=(
                w["source"], fmt_utc(w["start"]), fmt_utc(w["end"]),
                "%+.0f\u00b0" % w["max_el"]))
        self._rows = [("Jupiter now", "kv", kv), ("Io windows", "tree", tree)]
        self.info.set("Io-controlled decametric storms, 15\u201330 MHz. Only "
                      "windows with Jupiter above the horizon are listed \u2014 "
                      "a storm you cannot hear is not a window.")

    def _tab_2(self, obs, t):
        kp = None
        try:
            kp = (self.store.load_spacewx_cache() or {}).get("kp")
        except Exception:
            pass
        a = AS.aurora_outlook(obs.lat, obs.lon, kp)
        kv = KVPanel(self.body, label_width=24)
        kv.pack(fill="x")
        kv.row("Magnetic latitude", "%.1f\u00b0" % a["mag_lat"])
        kv.row("Kp", "%.1f" % a["kp"] if a["kp"] is not None else "\u2014")
        if a["boundary"] is not None:
            kv.row("Oval boundary", "%.1f\u00b0 magnetic" % a["boundary"])
            kv.row("Margin", "%+.1f\u00b0" % a["margin"],
                   COL_ACCENT2 if a["margin"] >= 0 else COL_MUTED)
        kv.row("Visual", a["visual"],
               COL_ACCENT2 if "likely" in a["visual"] else COL_MUTED)
        kv.row("Radio", a["radio"],
               COL_ACCENT2 if "likely" in a["radio"] else COL_MUTED)
        self._rows = [("Aurora", "kv", kv)]
        self.info.set("Magnetic latitude, not geographic \u2014 the oval "
                      "follows the dipole, which is why the UK and Labrador "
                      "see very different aurora at the same latitude."
                      + ("" if kp is not None
                         else "  Update Space Wx for a Kp value."))

    def _tab_3(self, obs, t):
        rows = AS.twilight_times(obs.lat, obs.lon)
        tree = self._tree(("phase", "alt", "am", "pm"),
                          ("Phase", "Sun altitude", "Morning", "Evening"),
                          (180, 110, 150, 150))
        for r in rows:
            tree.insert("", "end", values=(
                r["label"], "%+.1f\u00b0" % r["altitude"],
                fmt_utc(r["morning"]) if r["morning"] else "\u2014",
                fmt_utc(r["evening"]) if r["evening"] else "\u2014"))
        self._rows = [("Twilight", "tree", tree)]
        self.info.set("Today's UTC day. West of Greenwich the evening "
                      "crossing falls earlier in the UTC day than the morning "
                      "one \u2014 that is the calendar, not an error. A dash "
                      "means the Sun never reaches that altitude today.")

    def _tab_4(self, obs, t):
        c = AS.eme_conditions(t)
        kv = KVPanel(self.body, label_width=24)
        kv.pack(fill="x")
        kv.row("Moon distance", "%.0f km" % c["distance_km"])
        kv.row("Perigee (30 d)", "%.0f km on %s"
               % (c["perigee_km"], fmt_utc(c["perigee_time"])))
        kv.row("Apogee (30 d)", "%.0f km on %s"
               % (c["apogee_km"], fmt_utc(c["apogee_time"])))
        kv.row("Path degradation", "%.2f dB vs perigee"
               % c["degradation_db"],
               COL_WARN if c["degradation_db"] > 1.5 else COL_ACCENT2)
        kv.row("Perigee-apogee swing", "%.2f dB" % c["swing_db"])
        kv.row("Declination", "%+.1f\u00b0" % c["declination_deg"])
        self._rows = [("EME conditions", "kv", kv)]
        self.info.set("Two-way path loss goes as 40\u00b7log\u2081\u2080 of "
                      "range, so the monthly swing is worth about 2 dB \u2014 "
                      "the difference between a marginal schedule and a "
                      "comfortable one. The EME screen plans the windows.")

    def _tab_5(self, obs, t):
        rows = AS.occultations(obs.lat, obs.lon, t, days=365)
        tree = self._tree(("target", "when", "sep", "limb", "el", "kind"),
                          ("Target", "Closest approach", "Separation",
                           "Lunar limb", "Moon el", "Event"),
                          (140, 170, 110, 110, 90, 150))
        for r in rows:
            tree.insert("", "end", values=(
                r["target"], fmt_utc(r["time"]),
                "%.3f\u00b0" % r["separation_deg"],
                "%.3f\u00b0" % r["semidiameter_deg"],
                "%+.0f\u00b0" % r["moon_el"],
                "occultation" if r["occultation"] else "close approach"))
        self._rows = [("Occultations", "tree", tree)]
        self.info.set("A year ahead, Moon above the horizon only. An event is "
                      "an occultation when the separation falls inside the "
                      "lunar limb; anything wider is a close approach and is "
                      "labeled as one.")

    def _tab_7(self, obs, t):
        rows = AS.eclipses(obs.lat, obs.lon, t, days=730)
        tree = self._tree(("kind", "cls", "when", "mag", "el", "vis"),
                          ("Eclipse", "Class", "Maximum (UTC)", "Magnitude",
                           "Altitude", "From here"),
                          (100, 110, 170, 110, 90, 130))
        for r in rows:
            tree.insert("", "end", values=(
                r["kind"].title(), r["class_name"], fmt_utc(r["max_time"]),
                "%.3f" % r["magnitude"], "%+.0f\u00b0" % r["elevation"],
                "visible" if r["visible"] else "below the horizon"))
        tree.bind("<<TreeviewSelect>>",
                  lambda _e: self._draw_track(tree, rows))
        self._ecl_panel = MplPanel(self.body, figsize=(8.6, 3.4))
        self._ecl_panel.widget.pack(fill="both", expand=True, pady=(6, 0))
        self._ecl_note = tk.StringVar(
            value="Select a solar eclipse to plot its central line.")
        ttk.Label(self.body, textvariable=self._ecl_note,
                  style="Muted.TLabel", wraplength=880).pack(anchor="w")
        self._draw_track(tree, rows)
        self._rows = [("Eclipses", "tree", tree)]
        self.info.set("Two years ahead. Solar eclipses are computed "
                      "topocentrically \u2014 the Moon's parallax is what "
                      "makes them local \u2014 and listed only when the Sun is "
                      "up here. Lunar eclipses are the same event for everyone "
                      "who can see the Moon, so all are listed with a "
                      "visibility flag. Contacts land within a few minutes.")

    def _draw_track(self, tree, rows):
        """Plot the shadow-axis central line for the selected eclipse."""
        sel = tree.selection()
        idx = tree.index(sel[0]) if sel else 0
        if not rows:
            return
        ev = rows[min(idx, len(rows) - 1)]
        fig = self._ecl_panel.fig
        fig.clf()
        ax = fig.add_subplot(111)
        ax.set_facecolor("#0d1117")
        draw_basemap(ax, graticule=True)
        segs = AS.eclipse_ground_track(ev)
        for seg in segs:
            ax.plot([p[1] for p in seg], [p[0] for p in seg],
                    color="#ff4136", lw=2.0, zorder=5)
        obs = self.store.obs
        ax.plot([obs.lon], [obs.lat], "o", color=COL_ACCENT2, ms=6, zorder=6)
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.tick_params(colors=COL_MUTED, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color(COL_MUTED)
        fig.tight_layout()
        self._ecl_panel.canvas.draw_idle()
        self._ecl_note.set(AS.eclipse_track_summary(ev))

    def _tab_6(self, obs, t):
        rows = AS.appulses(t, days=365)
        tree = self._tree(("pair", "when", "sep"),
                          ("Pair", "Closest", "Separation"),
                          (220, 180, 120))
        for r in rows:
            tree.insert("", "end", values=(
                "%s \u2013 %s" % (r["a"], r["b"]), fmt_utc(r["time"]),
                "%.2f\u00b0" % r["separation_deg"]))
        self._rows = [("Appulses", "tree", tree)]
        self.info.set("Close pairings of the planets and Moon within "
                      "2\u00b0, a year ahead. Called appulses to keep them "
                      "clear of the satellite conjunction screener, which "
                      "answers a different question.")


