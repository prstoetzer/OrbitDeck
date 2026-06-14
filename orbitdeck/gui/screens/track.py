"""track.py - live tracking: look angles, transponder selection, full Doppler.

Shows azimuth/elevation/range/range-rate plus, for the selected transponder,
the live downlink (DN) and Doppler-corrected receive (RX) frequencies and the
uplink (UP) and Doppler-corrected transmit (TX) frequencies -- the numbers you
actually tune. A live sky polar plot sits on the right.
"""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, FONT_MONO, FONT_BIG,
               fmt_hms, fmt_utc, now_unix, compass)


class TrackScreen(Screen):
    live = True

    def build(self):
        self.sat_header("Track \u2014 live look angles, transponder & Doppler")
        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        left = ttk.Frame(body, style="Panel.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # transponder selector
        selrow = ttk.Frame(left, style="Panel.TFrame")
        selrow.pack(fill="x", padx=14, pady=(12, 6))
        ttk.Label(selrow, text="Transponder", style="Muted.TLabel",
                  width=12, anchor="w").pack(side="left")
        self.tp_var = tk.StringVar()
        self.tp_combo = ttk.Combobox(selrow, textvariable=self.tp_var,
                                     state="readonly", width=34)
        self.tp_combo.pack(side="left", fill="x", expand=True)
        self.tp_combo.bind("<<ComboboxSelected>>", self._on_tp_change)
        self._tp_list = []
        self._tp_index = 0

        self.vars = {}
        rows = [
            ("Azimuth", "az", True), ("Elevation", "el", True),
            ("Range", "range", False), ("Range rate", "rr", False),
            ("Sub-point", "sub", False), ("Altitude", "alt", False),
            ("Sunlit", "sun", False),
        ]
        for label, key, big in rows:
            r = ttk.Frame(left, style="Panel.TFrame")
            r.pack(fill="x", padx=14, pady=2)
            ttk.Label(r, text=label, style="Muted.TLabel", width=12,
                      anchor="w").pack(side="left")
            v = tk.StringVar(value="\u2014")
            self.vars[key] = v
            ttk.Label(r, textvariable=v, style="Mono.TLabel",
                      font=FONT_BIG if big else FONT_MONO).pack(side="left")

        # frequency block (DN/RX and UP/TX)
        sep = tk.Frame(left, bg=COL_GRID, height=1)
        sep.pack(fill="x", padx=14, pady=(10, 6))
        freqrows = [
            ("Downlink", "dn"), ("RX (tune here)", "rx"),
            ("Uplink", "up"), ("TX (tune here)", "tx"),
            ("Doppler DN", "ddn"), ("Doppler UP", "dup"),
        ]
        for label, key in freqrows:
            r = ttk.Frame(left, style="Panel.TFrame")
            r.pack(fill="x", padx=14, pady=2)
            ttk.Label(r, text=label, style="Muted.TLabel", width=12,
                      anchor="w").pack(side="left")
            v = tk.StringVar(value="\u2014")
            self.vars[key] = v
            accent = key in ("rx", "tx")
            lbl = ttk.Label(r, textvariable=v, style="Mono.TLabel",
                            font=("DejaVu Sans Mono", 12, "bold") if accent
                            else FONT_MONO)
            lbl.pack(side="left")

        # next event
        r = ttk.Frame(left, style="Panel.TFrame")
        r.pack(fill="x", padx=14, pady=(8, 12))
        ttk.Label(r, text="Next event", style="Muted.TLabel", width=12,
                  anchor="w").pack(side="left")
        self.vars["nextev"] = tk.StringVar(value="\u2014")
        ttk.Label(r, textvariable=self.vars["nextev"],
                  style="Mono.TLabel").pack(side="left")

        right = ttk.Frame(body, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.mpl = MplPanel(right, figsize=(4.8, 4.8), polar=True)
        self.mpl.pack(fill="both", expand=True, padx=6, pady=6)
        self._sky_sat = None

    # ---- transponder list management ----
    def _sync_tp_list(self, s):
        self.store.ensure_transponders(s)
        names = []
        self._tp_list = list(s.transponders) if s.transponders else []
        for tp in self._tp_list:
            tag = tp.mode or ""
            if tp.is_linear:
                tag += " linear"
            dl = ("%.3f" % (tp.downlink / 1e6)) if tp.downlink else "?"
            names.append("%s  DL %s MHz" % (tp.desc or tag or "transponder", dl))
        if not names:
            names = ["(no transponder data \u2014 145.800 MHz default)"]
            self._tp_list = []
        self.tp_combo.configure(values=names)
        if self._tp_index >= len(names):
            self._tp_index = 0
        self.tp_combo.current(self._tp_index)

    def _on_tp_change(self, _evt=None):
        self._tp_index = self.tp_combo.current()
        # clear the persistent text selection/highlight and drop focus so the
        # combobox doesn't stay visually "selected" after a pick
        self.tp_combo.selection_clear()
        self.frame.focus_set()
        self._refresh(now_unix())

    def on_show(self):
        s = self.sat()
        if s is not self._sky_sat:
            self._tp_index = 0
            self._sky_sat = s
        if s:
            self._sync_tp_list(s)
        self._refresh(now_unix())

    def on_tick(self, now_dt):
        self._refresh(now_dt.timestamp())

    def _refresh(self, t):
        s = self.sat()
        if not s:
            for v in self.vars.values():
                v.set("\u2014")
            return
        L = self.pred().look(t)
        self.vars["az"].set("%.1f\u00b0 %s" % (L.az, compass(L.az)))
        self.vars["el"].set("%+.1f\u00b0" % L.el)
        self.vars["range"].set("%.0f km" % L.range_km)
        self.vars["rr"].set("%+.3f km/s (%s)" %
                            (L.range_rate, "receding" if L.range_rate > 0
                             else "approaching"))
        self.vars["sub"].set("%.2f, %.2f" % (L.sub_lat, L.sub_lon))
        self.vars["alt"].set("%.0f km" % L.alt_km)
        self.vars["sun"].set("yes" if L.sunlit else "ECLIPSE")

        # selected transponder (or 145.8 default)
        tp = self._tp_list[self._tp_index] if (
            self._tp_list and self._tp_index < len(self._tp_list)) else None
        dl = tp.downlink if (tp and tp.downlink) else 145_800_000
        ul = tp.uplink if (tp and tp.uplink) else 0
        rx, tx = self.pred().doppler_freqs(dl, ul, L.range_rate)
        self.vars["dn"].set("%.4f MHz" % (dl / 1e6))
        self.vars["rx"].set("%.4f MHz" % (rx / 1e6))
        self.vars["ddn"].set("%+d Hz" % (rx - dl))
        if ul:
            self.vars["up"].set("%.4f MHz" % (ul / 1e6))
            self.vars["tx"].set("%.4f MHz" % (tx / 1e6))
            self.vars["dup"].set("%+d Hz" % (tx - ul))
        else:
            self.vars["up"].set("\u2014")
            self.vars["tx"].set("\u2014")
            self.vars["dup"].set("\u2014")

        # next AOS or LOS
        if L.visible:
            passes = self.pred().predict_passes(t - 1200, self.store.min_el, 1,
                                                t + 7200)
            los = None
            for p in passes:
                if p.aos <= t <= p.los:
                    los = p.los
            self.vars["nextev"].set(
                ("LOS in %s @ %s" % (fmt_hms(los - t), fmt_utc(los, "%H:%M:%S")))
                if los else "in view")
        else:
            nxt = self.pred().predict_passes(t, self.store.min_el, 1,
                                             t + 6 * 86400)
            if nxt:
                p = nxt[0]
                self.vars["nextev"].set("AOS in %s (maxEl %.0f\u00b0)" %
                                        (fmt_hms(p.aos - t), p.max_el))
            else:
                self.vars["nextev"].set("no pass in 6 days")

        self._draw_sky(t, L)

    def _draw_sky(self, t, L):
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(90, 0)
        ax.set_rgrids([0, 30, 60, 90], labels=["90", "60", "30", "0"],
                      color=COL_MUTED, fontsize=7)
        ax.set_thetagrids(range(0, 360, 45),
                          labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                          color=COL_MUTED, fontsize=8)
        ax.grid(True, color=COL_GRID, linewidth=0.6)
        passes = self.pred().predict_passes(t - 1800, self.store.min_el, 1,
                                            t + 6 * 86400)
        if passes:
            p = passes[0]
            azs, els = [], []
            for i in range(61):
                tt = p.aos + (p.los - p.aos) * i / 60
                a, e = self.pred().azel_at(tt)
                if e >= 0:
                    azs.append(math.radians(a))
                    els.append(e)
            if azs:
                ax.plot(azs, els, color=COL_ACCENT, linewidth=1.8)
        if L.visible:
            ax.plot([math.radians(L.az)], [L.el], "o", color=COL_ACCENT2,
                    markersize=9)
        if L.sun_el > 0:
            ax.plot([math.radians(L.sun_az)], [L.sun_el], "o",
                    color=COL_WARN, markersize=7)
        self.mpl.draw()
