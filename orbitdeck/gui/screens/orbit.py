"""orbit.py - orbital analysis with 9 pages (mirrors CardSat's drawOrbit).

Pages: Info, Live, Pass, Track, Doppler, Nodal, Sun/Beta, Pass Outlook,
Orbit Position.
"""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, FONT_MONO,
               fmt_hms, fmt_utc, now_unix, compass)

PAGES = ["Info", "Live", "Pass", "Track", "Doppler", "Nodal",
         "Sun/Beta", "Pass Outlook", "Orbit Position"]


class OrbitScreen(Screen):
    live = True

    def build(self):
        self.header("Orbital Analysis")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16)
        self.page = tk.IntVar(value=0)
        for i, name in enumerate(PAGES):
            ttk.Radiobutton(bar, text="%d %s" % (i + 1, name), value=i,
                            variable=self.page,
                            command=self._switch).pack(side="left", padx=1)

        self.text = tk.Text(self.frame, bg=COL_PANEL, fg=COL_TEXT,
                            font=FONT_MONO, borderwidth=0, height=12,
                            insertbackground=COL_TEXT, wrap="word")
        self.text.pack(fill="x", padx=16, pady=8)
        self.plotwrap = ttk.Frame(self.frame, style="Panel.TFrame")
        self.plotwrap.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.mpl = None

    def _ensure_plot(self, polar=False):
        if self.mpl is None:
            self.mpl = MplPanel(self.plotwrap, figsize=(7.5, 3.6), polar=polar)
            self.mpl.pack(fill="both", expand=True, padx=8, pady=8)

    def _switch(self):
        self.on_show()

    def on_show(self):
        self._render(now_unix())

    def on_tick(self, now_dt):
        # only the live-ish pages need per-second refresh
        if self.page.get() in (1, 3, 4, 8):
            self._render(now_dt.timestamp())

    def _set(self, lines):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))

    def _render(self, t):
        s = self.sat()
        if not s:
            self._set(["No satellite selected."])
            return
        pg = self.page.get()
        pred = self.pred()
        if self.mpl is not None:
            self.mpl.ax.clear()
        if pg == 0:
            self._page_info(s, t)
        elif pg == 1:
            self._page_live(s, t)
        elif pg == 2:
            self._page_pass(s, t)
        elif pg == 3:
            self._page_track(s, t)
        elif pg == 4:
            self._page_doppler(s, t)
        elif pg == 5:
            self._page_nodal(s, t)
        elif pg == 6:
            self._page_sunbeta(s, t)
        elif pg == 7:
            self._page_outlook(s, t)
        elif pg == 8:
            self._page_orbitpos(s, t)

    # ---------- pages ----------
    def _page_info(self, s, t):
        if self.mpl:
            self.mpl.widget.pack_forget()
            self.mpl = None
        age = (now_unix() - s.epoch_unix) / 86400.0
        self._set([
            "%s   (NORAD %d   %s)" % (s.name, s.norad, s.intl_des),
            "",
            "Epoch         %s  (%.1f days old)" % (fmt_utc(s.epoch_unix), age),
            "Inclination   %.4f\u00b0" % s.incl,
            "Eccentricity  %.7f" % s.ecc,
            "RAAN          %.4f\u00b0" % s.raan,
            "Arg perigee   %.4f\u00b0" % s.argp,
            "Mean anomaly  %.4f\u00b0" % s.ma,
            "Mean motion   %.8f rev/day" % s.mean_motion,
            "Period        %.2f min" % s.period_min,
            "Apogee        %.0f km    Perigee %.0f km" % (s.apogee_km, s.perigee_km),
            "B*            %.6f" % s.bstar,
        ])

    def _page_live(self, s, t):
        if self.mpl:
            self.mpl.widget.pack_forget()
            self.mpl = None
        L = self.pred().look(t)
        self._set([
            "Live geometry @ %s" % fmt_utc(t, "%H:%M:%S"),
            "",
            "Azimuth     %.1f\u00b0 %s" % (L.az, compass(L.az)),
            "Elevation   %+.1f\u00b0  (%s)" % (L.el, "VISIBLE" if L.visible
                                               else "below horizon"),
            "Range       %.0f km" % L.range_km,
            "Range rate  %+.4f km/s" % L.range_rate,
            "Sub-point   %.3f, %.3f" % (L.sub_lat, L.sub_lon),
            "Altitude    %.1f km" % L.alt_km,
            "Footprint   %.0f km radius" % self.pred().footprint_radius_km(L.alt_km),
            "Sunlit      %s" % ("yes" if L.sunlit else "ECLIPSE"),
        ])

    def _page_pass(self, s, t):
        if self.mpl:
            self.mpl.widget.pack_forget()
            self.mpl = None
        nxt = self.pred().predict_passes(t, self.store.min_el, 1, t + 6 * 86400)
        if not nxt:
            self._set(["No pass in the next 6 days above %.0f\u00b0." %
                       self.store.min_el])
            return
        p = nxt[0]
        in_view = p.aos <= t <= p.los
        self._set([
            "Next pass (min %.0f\u00b0)" % self.store.min_el,
            "",
            "AOS    %s   az %.0f\u00b0 %s" % (fmt_utc(p.aos), p.az_aos,
                                              compass(p.az_aos)),
            "TCA    %s   max el %.1f\u00b0" % (fmt_utc(p.tca, "%H:%M:%S"),
                                               p.max_el),
            "LOS    %s   az %.0f\u00b0 %s" % (fmt_utc(p.los, "%H:%M:%S"),
                                              p.az_los, compass(p.az_los)),
            "Dur    %s" % fmt_hms(p.los - p.aos),
            "",
            ("IN VIEW \u2014 LOS in %s" % fmt_hms(p.los - t)) if in_view
            else ("AOS in %s" % fmt_hms(p.aos - t)),
        ])

    def _page_track(self, s, t):
        self._ensure_plot(polar=True)
        self.mpl.widget.pack(fill="both", expand=True, padx=8, pady=8)
        self._set(["Forward sky track of the next pass."])
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(90, 0)
        ax.set_thetagrids(range(0, 360, 45),
                          labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                          color=COL_MUTED, fontsize=8)
        ax.grid(True, color=COL_GRID, linewidth=0.6)
        nxt = self.pred().predict_passes(t - 1800, self.store.min_el, 1,
                                         t + 6 * 86400)
        if nxt:
            p = nxt[0]
            azs, els = [], []
            for i in range(81):
                tt = p.aos + (p.los - p.aos) * i / 80
                a, e = self.pred().azel_at(tt)
                if e >= 0:
                    azs.append(math.radians(a))
                    els.append(e)
            if azs:
                ax.plot(azs, els, color=COL_ACCENT, linewidth=2)
        L = self.pred().look(t)
        if L.visible:
            ax.plot([math.radians(L.az)], [L.el], "o", color=COL_ACCENT2,
                    markersize=10)
        self.mpl.draw()

    def _page_doppler(self, s, t):
        self._ensure_plot(polar=False)
        self.mpl.widget.pack(fill="both", expand=True, padx=8, pady=8)
        self.store.ensure_transponders(s)
        dl = 145825000
        if s.transponders and s.transponders[0].downlink:
            dl = s.transponders[0].downlink
        nxt = self.pred().predict_passes(t - 1800, self.store.min_el, 1,
                                         t + 6 * 86400)
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        if not nxt:
            self._set(["No upcoming pass to model Doppler for."])
            self.mpl.draw()
            return
        p = nxt[0]
        ts, shifts = [], []
        for i in range(121):
            tt = p.aos + (p.los - p.aos) * i / 120
            L = self.pred().look(tt)
            rx, _ = self.pred().doppler_freqs(dl, 0, L.range_rate)
            ts.append((tt - p.aos) / 60.0)
            shifts.append((rx - dl))
        ax.plot(ts, shifts, color=COL_ACCENT, linewidth=2)
        ax.axhline(0, color=COL_MUTED, linewidth=0.6)
        ax.set_xlabel("minutes after AOS")
        ax.set_ylabel("Doppler shift (Hz)")
        ax.grid(True, color=COL_GRID, linewidth=0.5)
        self._set([
            "Doppler curve for %.4f MHz downlink" % (dl / 1e6),
            "Max shift  %+d Hz   Min shift %+d Hz" % (max(shifts), min(shifts)),
            "Total swing %.0f Hz across the pass" % (max(shifts) - min(shifts)),
        ])
        self.mpl.draw()

    def _page_nodal(self, s, t):
        if self.mpl:
            self.mpl.widget.pack_forget()
            self.mpl = None
        # nodal period & equator crossings (ascending node) over next 24h
        period = s.period_min
        crossings = []
        tt = t
        prev_lat = self.pred().subpoint_at(tt)[0]
        step = 30.0
        while tt < t + 24 * 3600 and len(crossings) < 8:
            tt += step
            lat = self.pred().subpoint_at(tt)[0]
            if prev_lat < 0 <= lat:
                lo = self.pred().subpoint_at(tt)[1]
                crossings.append((tt, lo))
            prev_lat = lat
        lines = ["Nodal period  %.2f min" % period,
                 "Mean motion   %.6f rev/day" % s.mean_motion,
                 "",
                 "Ascending node crossings (next 24h):"]
        for ct, lo in crossings:
            lines.append("  %s   lon %.1f\u00b0" % (fmt_utc(ct, "%H:%M:%S"), lo))
        self._set(lines)

    def _page_sunbeta(self, s, t):
        self._ensure_plot(polar=False)
        self.mpl.widget.pack(fill="both", expand=True, padx=8, pady=8)
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        days, betas = [], []
        for d in range(0, 60):
            tt = t + d * 86400
            betas.append(self.pred().beta_angle_deg(tt))
            days.append(d)
        ax.plot(days, betas, color=COL_ACCENT, linewidth=2)
        ax.axhline(0, color=COL_MUTED, linewidth=0.6)
        ax.set_xlabel("days from now")
        ax.set_ylabel("beta angle (\u00b0)")
        ax.grid(True, color=COL_GRID, linewidth=0.5)
        beta_now = self.pred().beta_angle_deg(t)
        sunlit = self.pred().sunlit_at(t)
        self._set([
            "Solar beta angle  %.2f\u00b0  (now)" % beta_now,
            "Currently %s" % ("SUNLIT" if sunlit else "in ECLIPSE"),
            "High |beta| \u2192 longer sunlit fraction / full-sun seasons.",
        ])
        self.mpl.draw()

    def _page_outlook(self, s, t):
        if self.mpl:
            self.mpl.widget.pack_forget()
            self.mpl = None
        passes = self.pred().predict_passes(t, self.store.min_el, 12,
                                            t + 4 * 86400)
        lines = ["Pass outlook (next 4 days, min %.0f\u00b0):" % self.store.min_el,
                 ""]
        for p in passes:
            lines.append("  %s  el %4.1f\u00b0  %s  %s\u2192%s" % (
                fmt_utc(p.aos, "%m-%d %H:%M"), p.max_el,
                fmt_hms(p.los - p.aos), compass(p.az_aos), compass(p.az_los)))
        if not passes:
            lines.append("  (none)")
        self._set(lines)

    def _page_orbitpos(self, s, t):
        self._ensure_plot(polar=False)
        self.mpl.widget.pack(fill="both", expand=True, padx=8, pady=8)
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        from ..mapdraw import draw_basemap
        draw_basemap(ax)
        period = s.period_min * 60.0 if s.period_min else 5400.0
        track = []
        for k in range(-30, 31):
            tt = t + (k / 30.0) * period * 0.5
            lat, lon, alt = self.pred().subpoint_at(tt)
            track.append((lon, lat))
        seg_lon, seg_lat, prev = [], [], None
        for lon, lat in track:
            if prev is not None and abs(lon - prev) > 180:
                ax.plot(seg_lon, seg_lat, color=COL_ACCENT, linewidth=1.2)
                seg_lon, seg_lat = [], []
            seg_lon.append(lon)
            seg_lat.append(lat)
            prev = lon
        if seg_lon:
            ax.plot(seg_lon, seg_lat, color=COL_ACCENT, linewidth=1.2)
        lat0, lon0, alt0 = self.pred().subpoint_at(t)
        ax.plot([lon0], [lat0], "o", color=COL_ACCENT2, markersize=9)
        self._set([
            "Instantaneous orbit position",
            "Sub-point  %.2f, %.2f   alt %.0f km" % (lat0, lon0, alt0),
        ])
        self.mpl.draw()
