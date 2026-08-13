"""eme.py (screen) - EME (moonbounce) planning.

Surfaces the EME engine that already lives in ``orbitdeck.engine.celestial``:
Moon position and distance, round-trip path loss, self-echo Doppler, and the
common-Moon windows between your station and a remote one - the times you can
both see the Moon at once, which is what an EME schedule needs.
"""

import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, TabBar, COL_ACCENT2, COL_WARN, COL_TEXT,
               fmt_utc, fmt_hms, now_unix, make_scrolled_tree)
from ...engine import celestial as CE
from ...engine.predict import grid_to_latlon

BANDS = [("50 MHz (6 m)", 50.2e6), ("144 MHz (2 m)", 144.1e6),
         ("222 MHz", 222.1e6), ("432 MHz (70 cm)", 432.1e6),
         ("1296 MHz (23 cm)", 1296.0e6), ("2304 MHz (13 cm)", 2304.1e6),
         ("10368 MHz (3 cm)", 10368.1e6)]


class EmeScreen(Screen):
    def build(self):
        self.header("EME \u2014 moonbounce planning")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(bar, text="Band:", style="TLabel").pack(side="left")
        self.band = tk.StringVar(value=BANDS[1][0])
        cb = ttk.Combobox(bar, textvariable=self.band, state="readonly",
                          width=18, values=[b[0] for b in BANDS])
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh())
        ttk.Label(bar, text="Remote grid:", style="TLabel").pack(
            side="left", padx=(12, 2))
        self.grid = tk.StringVar(value="JO65")
        ent = ttk.Entry(bar, textvariable=self.grid, width=8)
        ent.pack(side="left")
        ent.bind("<Return>", lambda _e: self._scan())
        ttk.Label(bar, text="Hours:", style="TLabel").pack(side="left",
                                                            padx=(12, 2))
        self.hours = tk.IntVar(value=48)
        for v in (24, 48, 72):
            ttk.Radiobutton(bar, text="%d" % v, value=v,
                            variable=self.hours).pack(side="left")
        self.scanbtn = ttk.Button(bar, text="Find windows",
                                  command=self._scan)
        self.scanbtn.pack(side="left", padx=10)
        self.info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel").pack(
            side="left", padx=8)

        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        t_now = tabs.add("Moon now")
        t_band = tabs.add("Per-band analysis")
        t_plan = tabs.add("90-day plan")
        t_win = tabs.add("Common windows")

        # --- per-band analysis: what actually decides tonight ---
        bcols = ("band", "dop", "far", "sky", "spread", "loss")
        bheads = ("Band", "Self Doppler", "Faraday", "Sky temp",
                  "Libration spread", "Path loss (2-way)")
        bwrap, self.btree = make_scrolled_tree(t_band, bcols,
                                               show="headings", height=6)
        for c, h, w in zip(bcols, bheads, (110, 120, 100, 110, 140, 150)):
            self.btree.heading(c, text=h)
            self.btree.column(c, width=w,
                              anchor="w" if c == "band" else "center")
        bwrap.pack(fill="x", padx=6, pady=6)
        self.bnote = tk.StringVar(value="")
        ttk.Label(t_band, textvariable=self.bnote, style="Muted.TLabel",
                  justify="left", wraplength=900).pack(anchor="w", padx=8,
                                                        pady=6)

        # --- 90-day plan ---
        pcols = ("date", "dec", "degr", "dist", "flag")
        pheads = ("Date", "Moon dec", "Degradation", "Distance", "")
        pwrap, self.ptree = make_scrolled_tree(t_plan, pcols,
                                               show="headings", height=14)
        for c, h, w in zip(pcols, pheads, (120, 100, 120, 120, 120)):
            self.ptree.heading(c, text=h)
            self.ptree.column(c, width=w,
                              anchor="w" if c == "date" else "center")
        pwrap.pack(fill="both", expand=True, padx=6, pady=6)
        ttk.Label(t_plan, text="Sampled at 12:00 UTC each day so rows compare "
                               "like with like. A day is flagged when the Moon "
                               "is well north (long window from the northern "
                               "hemisphere) and near perigee.",
                  style="Muted.TLabel", wraplength=900).pack(anchor="w",
                                                             padx=8, pady=4)

        self.kv = KVPanel(t_now, label_width=20)
        self.kv.pack(fill="both", expand=True, padx=4, pady=6)

        cols = ("start", "end", "dur")
        heads = ("Window start", "End", "Duration")
        wrap, self.tree = make_scrolled_tree(t_win, cols, show="headings",
                                             height=12)
        for c, h, w in zip(cols, heads, (200, 200, 120)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c != "dur" else "center")
        wrap.pack(fill="both", expand=True, padx=4, pady=6)

        note = ("Path loss is the round-trip Earth-Moon-Earth figure; Doppler is "
                "the self-echo shift on your own signal. Common windows are when "
                "the Moon is up at both stations \u2014 the requirement for a QSO.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))

    def on_show(self):
        self._refresh()
        self._fill_plan()

    def on_tick(self, _now_dt):
        self._refresh()

    def _freq(self):
        for name, hz in BANDS:
            if name == self.band.get():
                return hz
        return 144.1e6

    def _refresh(self):
        obs = self.store.obs
        t = now_unix()
        f = self._freq()
        az, el = CE.moon_azel(obs.lat, obs.lon, t)
        dist = CE.moon_distance_km(t)
        loss = CE.eme_path_loss_db(f, t)
        dop = CE.eme_doppler_hz(f, obs.lat, obs.lon, t)
        sky = CE.sky_temperature_k(freq_mhz=f / 1e6)
        self.kv.begin()
        self.kv.row("Moon azimuth", "%.1f\u00b0" % az)
        self.kv.row("Moon elevation", "%.1f\u00b0" % el,
                    COL_ACCENT2 if el > 0 else COL_WARN)
        self.kv.row("Moon distance", "%.0f km" % dist)
        self.kv.row("Band", self.band.get())
        self.kv.row("Path loss (2-way)", "%.1f dB" % loss)
        self.kv.row("Self-echo Doppler", "%+.0f Hz" % dop)
        self.kv.row("Echo delay", "%.2f s" % (2.0 * dist / 299792.458))
        self.kv.row("Sky temperature", "%.0f K" % sky)
        self.kv.row("Moon up here", "yes" if el > 0 else "no",
                    COL_ACCENT2 if el > 0 else COL_TEXT)
        self.kv.row("Declination", "%+.1f\u00b0" % CE.moon_dec_deg(t))
        self.kv.row("Path degradation", "%.2f dB"
                    % CE.eme_path_degradation_db(t))
        sep = CE.eme_sun_separation_deg(obs.lat, obs.lon, t)
        self.kv.row("Sun separation", "%.0f\u00b0" % sep,
                    COL_WARN if (sep < 10 and el > 0) else COL_TEXT)
        self.kv.row("Ground gain", CE.eme_ground_gain(el)[1])
        self.kv.end()
        self._fill_bands()

    def _fill_bands(self):
        obs = self.store.obs
        t = now_unix()
        flux = None
        try:
            flux = (self.store.load_spacewx_cache() or {}).get("flux")
        except Exception:
            flux = None
        self.btree.delete(*self.btree.get_children())
        for b in CE.eme_band_analysis(t, obs.lat, obs.lon, solar_flux=flux):
            self.btree.insert("", "end", values=(
                b["band"], "%+.0f Hz" % b["doppler_hz"],
                "%.0f\u00b0" % b["faraday_deg"],
                "%.0f K" % b["sky_temp_k"],
                "%.1f Hz" % b["spread_hz"],
                "%.1f dB" % b["path_loss_db"]))
        _az, el = CE.moon_azel(obs.lat, obs.lon, t)
        _gg, gg_text = CE.eme_ground_gain(el)
        sep = CE.eme_sun_separation_deg(obs.lat, obs.lon, t)
        degr = CE.eme_path_degradation_db(t)
        parts = ["Path degradation %.2f dB vs perigee." % degr, gg_text + "."]
        if sep < 10.0 and el > 0:
            parts.append("Moon is %.0f\u00b0 from the Sun \u2014 solar noise "
                         "will swamp a weak echo." % sep)
        else:
            parts.append("Sun %.0f\u00b0 away." % sep)
        parts.append("Faraday is a coarse model and drops as 1/f\u00b2, so it "
                     "matters on 50/144 and not above 1296.")
        self.bnote.set("  ".join(parts))

    def _fill_plan(self):
        self.ptree.delete(*self.ptree.get_children())
        for r in CE.eme_plan(now_unix(), days=90):
            self.ptree.insert("", "end", values=(
                r["date"], "%+.1f\u00b0" % r["dec_deg"],
                "%.2f dB" % r["degradation_db"],
                "%.0f km" % r["distance_km"],
                "\u2605 good" if r["good"] else ""))

    def _scan(self):
        g = self.grid.get().strip()
        try:
            lat2, lon2 = grid_to_latlon(g)
        except Exception:
            self.info.set("Enter a valid Maidenhead grid.")
            return
        obs = self.store.obs
        hours = self.hours.get()
        self.info.set("Scanning %d h\u2026" % hours)
        self.scanbtn.state(["disabled"])

        def work():
            try:
                wins = CE.eme_window(obs.lat, obs.lon, lat2, lon2, now_unix(),
                                     hours=hours)
                self._ui(lambda: self._show(wins, g))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _show(self, wins, g):
        self.scanbtn.state(["!disabled"])
        self.tree.delete(*self.tree.get_children())
        for a, b in wins:
            self.tree.insert("", "end", values=(
                fmt_utc(a, "%Y-%m-%d %H:%M"), fmt_utc(b, "%Y-%m-%d %H:%M"),
                fmt_hms(b - a)))
        self.info.set("%d common-Moon window(s) with %s over %d h."
                      % (len(wins), g.upper(), self.hours.get()))

    def _report(self):
        """Print whatever this screen is currently showing."""
        from ..reports import save_report_dialog
        tree = self.btree
        cols = [tree.heading(c)["text"] for c in tree["columns"]]
        rows = [list(tree.item(i)["values"]) for i in tree.get_children()]
        if not rows:
            from tkinter import messagebox
            messagebox.showinfo("Report", "Nothing to print yet.",
                                parent=self.frame)
            return
        save_report_dialog(self, "eme", title="EME", subtitle="Moonbounce analysis and planning",
                           sections=[("", "table", (cols, rows))])
