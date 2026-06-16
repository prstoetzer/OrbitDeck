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
        ttk.Button(selrow, text="+", width=2,
                   command=self._add_manual_tp).pack(side="left", padx=(4, 0))
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
        r.pack(fill="x", padx=14, pady=(8, 6))
        ttk.Label(r, text="Next event", style="Muted.TLabel", width=12,
                  anchor="w").pack(side="left")
        self.vars["nextev"] = tk.StringVar(value="\u2014")
        ttk.Label(r, textvariable=self.vars["nextev"],
                  style="Mono.TLabel").pack(side="left")

        # transponder details panel
        sep2 = tk.Frame(left, bg=COL_GRID, height=1)
        sep2.pack(fill="x", padx=14, pady=(8, 4))
        ttk.Label(left, text="TRANSPONDER", style="Muted.TLabel").pack(
            anchor="w", padx=14)
        tpd = ttk.Frame(left, style="Panel.TFrame")
        tpd.pack(fill="x", padx=14, pady=(2, 12))
        self.tpd_vars = {}
        for label, key in (("Type", "type"), ("Mode", "mode"),
                           ("Passband", "band"), ("Baud", "baud"),
                           ("Service", "svc"), ("Notes", "notes")):
            row = ttk.Frame(tpd, style="Panel.TFrame")
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label, style="Muted.TLabel", width=10,
                      anchor="w").pack(side="left")
            v = tk.StringVar(value="\u2014")
            self.tpd_vars[key] = v
            ttk.Label(row, textvariable=v, style="Mono.TLabel",
                      wraplength=300, justify="left").pack(side="left")

        # printable OSCARLOCATOR sheets for the selected satellite
        act = ttk.Frame(left, style="Panel.TFrame")
        act.pack(fill="x", padx=14, pady=(8, 12))
        ttk.Button(act, text="Make OSCARLOCATOR PDF\u2026",
                   command=self.make_oscarlocator_pdf).pack(side="left")

        right = ttk.Frame(body, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.mpl = MplPanel(right, figsize=(4.8, 4.8), polar=True)
        self.mpl.pack(fill="both", expand=True, padx=6, pady=6)
        self._sky_sat = None
        # redraw throttling (full plot + pass search are expensive; see _refresh)
        self._cached_pass = None
        self._pass_at = 0.0
        self._sky_at = 0.0

    def _update_tp_details(self, tp):
        v = self.tpd_vars
        if tp is None:
            v["type"].set("default (145.800 MHz FM beacon)")
            for k in ("mode", "band", "baud", "svc", "notes"):
                v[k].set("\u2014")
            return
        v["type"].set(tp.kind())
        v["mode"].set(tp.mode or "\u2014")
        if tp.is_linear and tp.downlink_high:
            bw = tp.bandwidth() / 1000.0
            v["band"].set("%.3f\u2013%.3f MHz (%.0f kHz%s)" % (
                tp.downlink / 1e6, tp.downlink_high / 1e6, bw,
                ", inverting" if tp.invert else ""))
        else:
            v["band"].set("single channel")
        v["baud"].set(("%g bps" % tp.baud) if tp.baud else "\u2014")
        v["svc"].set(tp.service or "\u2014")
        v["notes"].set(tp.desc or "\u2014")

    # ---- transponder list management ----
    def _sync_tp_list(self, s):
        self.store.ensure_transponders(s)
        names = []
        self._tp_list = list(s.transponders) if s.transponders else []
        for tp in self._tp_list:
            # show the center frequency (midpoint for a linear passband)
            dl = ("%.3f" % (tp.downlink_center() / 1e6)) if tp.downlink else "?"
            label = tp.desc or tp.kind() or "transponder"
            names.append("%s  [%s]  DL %s MHz" % (label, tp.kind(), dl))
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
        self._refresh(now_unix(), force_plot=True)

    def _add_manual_tp(self):
        s = self.sat()
        if not s:
            return
        from ..dialogs import FormDialog, Field
        from ...engine.satdb import make_manual_transponder

        def hz(v):
            return int(float(v))

        fields = [
            Field("dl", "Downlink low (Hz)", "", "e.g. 145800000", hz),
            Field("ul", "Uplink low (Hz)", "0", "0 = none / beacon", hz,
                  required=False),
            Field("dlh", "Downlink high (Hz)", "0",
                  "0 = single channel / FM", hz, required=False),
            Field("ulh", "Uplink high (Hz)", "0",
                  "linear only; 0 = same bandwidth", hz, required=False),
            Field("inv", "Inverting? (y/n)", "n",
                  "linear only", lambda v: v.strip().lower().startswith("y"),
                  required=False),
            Field("mode", "Mode", "", "e.g. FM, SSB, CW", None,
                  required=False),
        ]
        res = FormDialog(self.frame, "Add manual transponder", fields,
                         intro="For a linear transponder, give a downlink high "
                               "above the low AND an uplink. Single-channel "
                               "entries leave downlink high = 0. Stored "
                               "separately so a refresh won't erase them.").show()
        if not res:
            return
        tp = make_manual_transponder(
            res["dl"], res["ul"], res["dlh"], res["ulh"], res["inv"],
            res["mode"], desc="Manual")
        self.store.add_manual_transponder(s.norad, tp)
        self._sync_tp_list(s)
        # select the newly added transponder (last in the list)
        self._tp_index = len(self._tp_list) - 1
        self.tp_combo.current(self._tp_index)
        self._refresh(now_unix(), force_plot=True)

    def on_show(self):
        s = self.sat()
        if s is not self._sky_sat:
            self._tp_index = 0
            self._sky_sat = s
            self._cached_pass = None        # new sat -> recompute pass + plot
        if s:
            self._sync_tp_list(s)
        self._refresh(now_unix(), force_plot=True)

    def on_tick(self, now_dt):
        self._refresh(now_dt.timestamp())

    def _refresh(self, t, force_plot=False):
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
        # use the passband CENTER for linear transponders, not the low edge
        dl = tp.downlink_center() if (tp and tp.downlink) else 145_800_000
        ul = tp.uplink_center() if (tp and tp.uplink) else 0
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
        self._update_tp_details(tp)

        # The forward pass search is relatively expensive; cache it and recompute
        # only every ~15 s (or when forced on show). The countdown text below is
        # derived from the cached pass each second, so it still ticks smoothly.
        if force_plot or self._cached_pass is None or (t - self._pass_at) > 15:
            self._cached_pass = self.pred().predict_passes(
                t - 1800, self.store.min_el, 1, t + 6 * 86400)
            self._pass_at = t
        self._update_next_event(t, L)

        # The sky plot changes slowly; a full matplotlib redraw is the main cause
        # of stutter (especially on macOS), so redraw at most every ~3 s, or when
        # forced (on show / satellite or transponder change).
        if force_plot or (t - self._sky_at) > 3:
            self._draw_sky(t, L)
            self._sky_at = t

    def _update_next_event(self, t, L):
        cp = self._cached_pass or []
        if L.visible:
            los = None
            for p in cp:
                if p.aos <= t <= p.los:
                    los = p.los
            self.vars["nextev"].set(
                ("LOS in %s @ %s" % (fmt_hms(los - t), fmt_utc(los, "%H:%M:%S")))
                if los else "in view")
        else:
            if cp:
                p = cp[0]
                self.vars["nextev"].set("AOS in %s (maxEl %.0f\u00b0)" %
                                        (fmt_hms(max(0, p.aos - t)), p.max_el))
            else:
                self.vars["nextev"].set("no pass in 6 days")

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
        # reuse the cached next pass (already computed in _refresh)
        passes = self._cached_pass or []
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
