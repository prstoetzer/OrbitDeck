"""track.py - live tracking: az/el/range/range-rate, Doppler, next AOS/LOS."""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, FONT_MONO, FONT_BIG,
               fmt_hms, fmt_utc, now_unix, compass)


class TrackScreen(Screen):
    live = True

    def build(self):
        self.header("Track \u2014 live look angles & Doppler")
        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        # left: big readouts
        left = ttk.Frame(body, style="Panel.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.vars = {}
        rows = [
            ("Azimuth", "az"), ("Elevation", "el"), ("Range", "range"),
            ("Range rate", "rr"), ("Sub-point", "sub"), ("Altitude", "alt"),
            ("Doppler (down)", "dop"), ("Sunlit", "sun"),
            ("Next event", "nextev"),
        ]
        for i, (label, key) in enumerate(rows):
            r = ttk.Frame(left, style="Panel.TFrame")
            r.pack(fill="x", padx=14, pady=(8 if i == 0 else 3, 3))
            ttk.Label(r, text=label, style="Muted.TLabel", width=14,
                      anchor="w").pack(side="left")
            v = tk.StringVar(value="\u2014")
            self.vars[key] = v
            big = key in ("az", "el")
            ttk.Label(r, textvariable=v, style="Mono.TLabel",
                      font=FONT_BIG if big else FONT_MONO).pack(side="left")

        # transponder line
        self.tx_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.tx_var, style="Muted.TLabel",
                  wraplength=420, justify="left").pack(
            side="top", anchor="w", padx=14, pady=(10, 12))

        # right: live sky polar
        right = ttk.Frame(body, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.mpl = MplPanel(right, figsize=(4.6, 4.6), polar=True)
        self.mpl.pack(fill="both", expand=True, padx=6, pady=6)

    def on_show(self):
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
        up = L.visible
        self.vars["az"].set("%.1f\u00b0 %s" % (L.az, compass(L.az)))
        self.vars["el"].set("%+.1f\u00b0" % L.el)
        self.vars["range"].set("%.0f km" % L.range_km)
        self.vars["rr"].set("%+.3f km/s %s" %
                            (L.range_rate, "receding" if L.range_rate > 0
                             else "approaching"))
        self.vars["sub"].set("%.2f, %.2f" % (L.sub_lat, L.sub_lon))
        self.vars["alt"].set("%.0f km" % L.alt_km)
        self.vars["sun"].set("yes" if L.sunlit else "ECLIPSE")

        # doppler on the first transponder downlink (or 145.825 default)
        self.store.ensure_transponders(s)
        dl = 145825000
        tx = s.transponders[0] if s.transponders else None
        if tx and tx.downlink:
            dl = tx.downlink
        rx, _ = self.pred().doppler_freqs(dl, 0, L.range_rate)
        self.vars["dop"].set("%.4f MHz (%+d Hz)" % (rx / 1e6, rx - dl))
        if tx:
            self.tx_var.set("TX: %s  %s  DL %.4f MHz%s" % (
                tx.desc or "(transponder)", tx.mode,
                (tx.downlink / 1e6) if tx.downlink else 0.0,
                ("  UL %.4f MHz" % (tx.uplink / 1e6)) if tx.uplink else ""))
        else:
            self.tx_var.set("No transponder data (showing 145.825 MHz default).")

        # next AOS or LOS
        if up:
            passes = self.pred().predict_passes(t - 1200, self.store.min_el, 1,
                                                t + 7200)
            los = None
            for p in passes:
                if p.aos <= t <= p.los:
                    los = p.los
            if los:
                self.vars["nextev"].set("LOS in %s @ %s" %
                                        (fmt_hms(los - t), fmt_utc(los, "%H:%M:%S")))
            else:
                self.vars["nextev"].set("in view")
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

        # draw the current/next pass arc
        passes = self.pred().predict_passes(t - 1800, self.store.min_el, 1,
                                            t + 6 * 86400)
        if passes:
            p = passes[0]
            azs, els = [], []
            n = 60
            for i in range(n + 1):
                tt = p.aos + (p.los - p.aos) * i / n
                a, e = self.pred().azel_at(tt)
                if e >= 0:
                    azs.append(math.radians(a))
                    els.append(e)
            if azs:
                ax.plot(azs, els, color=COL_ACCENT, linewidth=1.8)
        # current marker
        if L.visible:
            ax.plot([math.radians(L.az)], [L.el], "o", color=COL_ACCENT2,
                    markersize=9)
        # sun
        if L.sun_el > 0:
            ax.plot([math.radians(L.sun_az)], [L.sun_el], "o",
                    color=COL_WARN, markersize=7)
        self.mpl.draw()
