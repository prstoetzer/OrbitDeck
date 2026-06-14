"""orbit.py - orbital analysis with 9 pages, matching CardSat's drawOrbit.

Pages: Info, Live, Next Pass, Ground Track, Doppler, Nodal (J2), Sun/Beta,
Pass Outlook, Orbit Position. Data pages use a formatted key/value card; the
Ground Track and Doppler pages use an embedded plot.
"""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, KVPanel, COL_PANEL, COL_TEXT, COL_MUTED,
               COL_ACCENT, COL_ACCENT2, COL_WARN, COL_GRID, FONT_MONO,
               fmt_hms, fmt_utc, now_unix, compass)
from ...engine import analysis as A
from ..mapdraw import draw_basemap

PAGES = ["Info", "Live", "Next Pass", "Ground Track", "Doppler", "Nodal",
         "Sun/Beta", "Pass Outlook", "Orbit Position"]
C_KM = 299792.458


def _hm(seconds):
    seconds = int(max(0, seconds))
    return "%d:%02d" % (seconds // 60, seconds % 60)


class OrbitScreen(Screen):
    live = True

    def build(self):
        self.header("Orbital Analysis")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=(0, 4))
        self.page = tk.IntVar(value=0)
        for i, name in enumerate(PAGES):
            ttk.Radiobutton(bar, text=name, value=i, variable=self.page,
                            command=self._switch).pack(side="left", padx=1)

        # two presentation surfaces: a KV card (data pages) and a plot (graph
        # pages). We show whichever the active page needs.
        self.kv = KVPanel(self.frame, label_width=15)
        self.kv.pack(fill="both", expand=True, padx=16, pady=8)
        self.plotwrap = ttk.Frame(self.frame, style="Panel.TFrame")
        self.mpl = None
        self._plot_shown = False

    # ---- surface management ----
    def _show_kv(self):
        if self._plot_shown:
            self.plotwrap.pack_forget()
            self._plot_shown = False
        if not self.kv.outer.winfo_ismapped():
            self.kv.pack(fill="both", expand=True, padx=16, pady=8)

    def _show_plot(self, polar=False):
        self.kv.outer.pack_forget()
        if not self._plot_shown:
            self.plotwrap.pack(fill="both", expand=True, padx=12, pady=8)
            self._plot_shown = True
        if self.mpl is None:
            self.mpl = MplPanel(self.plotwrap, figsize=(8, 4.2), polar=polar)
            self.mpl.pack(fill="both", expand=True, padx=8, pady=8)

    def _switch(self):
        self.on_show()

    def on_show(self):
        self._render(now_unix())

    def on_tick(self, now_dt):
        if self.page.get() in (1, 2, 8):       # live-ish data pages
            self._render(now_dt.timestamp())

    def _render(self, t):
        s = self.sat()
        if not s:
            self._show_kv()
            self.kv.begin()
            self.kv.section("Orbital analysis")
            self.kv.note("No satellite selected. Choose one from the "
                         "Satellites screen.")
            self.kv.end()
            return
        pg = self.page.get()
        dispatch = [self._info, self._live, self._nextpass, self._groundtrack,
                    self._doppler, self._nodal, self._sunbeta, self._outlook,
                    self._orbitpos]
        dispatch[pg](s, t)

    # ================= data pages =================
    def _info(self, s, t):
        self._show_kv()
        k = self.kv
        k.begin()
        mm = s.mean_motion
        a = A.semi_major_axis_km(mm)
        alt_now = self.pred().subpoint_at(t)[2]
        foot_now = A.footprint_diameter_km(alt_now)
        foot_apo = A.footprint_diameter_km(s.apogee_km)
        foot_per = A.footprint_diameter_km(s.perigee_km)
        age = (now_unix() - s.epoch_unix) / 86400.0
        decay = A.estimate_decay_days(s.bstar, mm, s.ecc)

        k.section("Identity")
        k.row("Name", s.name, COL_TEXT, big=True)
        k.row("NORAD", str(s.norad))
        k.row("Int'l desig", s.intl_des or "\u2014")

        k.section("Size & shape")
        k.row("Period", "%.2f min" % s.period_min, COL_ACCENT)
        k.row("Semi-major a", "%.1f km" % a)
        k.row("Apogee alt", "%.0f km" % s.apogee_km)
        k.row("Perigee alt", "%.0f km" % s.perigee_km)
        k.row("Inclination", "%.4f\u00b0" % s.incl)
        k.row("Eccentricity", "%.7f" % s.ecc)

        k.section("Coverage (footprint diameter)")
        k.row("Now", "%.0f km" % foot_now, COL_ACCENT2)
        k.row("At apogee", "%.0f km" % foot_apo)
        k.row("At perigee", "%.0f km" % foot_per)

        k.section("Drag & lifetime")
        k.row("B*", "%.6f" % s.bstar)
        k.row("Decay est.", A.fmt_decay(decay),
              COL_WARN if (0 <= decay < 3650) else COL_TEXT)

        k.section("Element set")
        k.row("Epoch", fmt_utc(s.epoch_unix, "%Y-%m-%d %H:%M"))
        k.row("Age", "%.2f days" % age,
              COL_WARN if age > 14 else COL_MUTED)
        k.row("Rev @ epoch", str(s.rev_at_epoch))
        if age > 14:
            k.note("\u26a0 Elements are %.0f days old \u2014 positions drift. "
                   "Update GP for accuracy." % age, COL_WARN)
        k.note("Footprint diameter is the widest two-station separation that "
               "can both see the bird at once (the longest possible QSO). "
               "Decay is an order-of-magnitude King-Hele estimate, not a "
               "reentry prediction.")
        k.end()

    def _live(self, s, t):
        self._show_kv()
        k = self.kv
        L = self.pred().look(t)
        self.store.ensure_transponders(s)
        rx2m, _ = self.pred().doppler_freqs(145_800_000, 0, L.range_rate)
        rx70, _ = self.pred().doppler_freqs(435_000_000, 0, L.range_rate)
        depth = self.pred().eclipse_depth_deg(t)
        ma = A.mean_anomaly_now_deg(s.ma, s.mean_motion, t, s.epoch_unix)

        k.begin()
        k.section("Look angles @ %s" % fmt_utc(t, "%H:%M:%S"))
        k.row("Azimuth", "%.1f\u00b0 %s" % (L.az, compass(L.az)),
              COL_ACCENT, big=True)
        k.row("Elevation", "%+.1f\u00b0" % L.el,
              COL_ACCENT2 if L.visible else COL_MUTED, big=True)
        k.row("Status", "VISIBLE" if L.visible else "below horizon",
              COL_ACCENT2 if L.visible else COL_MUTED)

        k.section("Range & Doppler")
        k.row("Range", "%.0f km" % L.range_km)
        k.row("Range rate", "%+.4f km/s" % L.range_rate,
              COL_WARN if L.range_rate > 0 else COL_ACCENT2)
        k.row("Doppler 145.8", "%+d Hz" % (rx2m - 145_800_000))
        k.row("Doppler 435", "%+d Hz" % (rx70 - 435_000_000))

        k.section("Position")
        k.row("Sub-point", "%.2f, %.2f" % (L.sub_lat, L.sub_lon))
        k.row("Altitude", "%.1f km" % L.alt_km)
        k.row("Mean anomaly", "%.1f\u00b0" % ma)

        k.section("Illumination")
        k.row("Sunlit", "yes" if L.sunlit else "ECLIPSE",
              COL_ACCENT2 if L.sunlit else COL_WARN)
        k.row("Eclipse depth", "%+.2f\u00b0" % depth,
              COL_WARN if depth > 0 else COL_MUTED)
        k.note("Eclipse depth is the PREDICT-style angle inside Earth's shadow "
               "(positive = eclipsed). It crosses 0\u00b0 at the terminator, so "
               "a value near zero means a sunrise/sunset is imminent.")
        k.end()

    def _nextpass(self, s, t):
        self._show_kv()
        k = self.kv
        k.begin()
        nxt = self.pred().predict_passes(t - 600, self.store.min_el, 1,
                                         t + 6 * 86400)
        if not nxt:
            k.section("Next pass")
            k.note("No pass above %.0f\u00b0 in the next 6 days."
                   % self.store.min_el)
            k.end()
            return
        p = nxt[0]
        in_view = p.aos <= t <= p.los
        # slant ranges at AOS/TCA/LOS
        r_aos = self.pred().look(p.aos).range_km
        r_tca = self.pred().look(p.tca).range_km
        r_los = self.pred().look(p.los).range_km
        delay = r_tca / C_KM * 1000.0      # ms one-way at TCA

        k.section("Next pass (min %.0f\u00b0)" % self.store.min_el)
        if in_view:
            k.row("Status", "IN VIEW", COL_ACCENT2, big=True)
            k.row("LOS in", fmt_hms(p.los - t), COL_ACCENT2)
        else:
            k.row("AOS in", fmt_hms(p.aos - t), COL_ACCENT, big=True)
        k.row("Max elevation", "%.1f\u00b0" % p.max_el, COL_ACCENT)
        k.row("Duration", fmt_hms(p.los - p.aos))

        k.section("Timing")
        k.row("AOS", "%s  az %.0f\u00b0 %s" %
              (fmt_utc(p.aos, "%H:%M:%S"), p.az_aos, compass(p.az_aos)))
        k.row("TCA", fmt_utc(p.tca, "%H:%M:%S"))
        k.row("LOS", "%s  az %.0f\u00b0 %s" %
              (fmt_utc(p.los, "%H:%M:%S"), p.az_los, compass(p.az_los)))

        k.section("Geometry")
        k.row("Range AOS", "%.0f km" % r_aos)
        k.row("Range TCA", "%.0f km" % r_tca)
        k.row("Range LOS", "%.0f km" % r_los)
        k.row("Path delay", "%.2f ms" % delay)
        k.note("Path delay is the one-way light-time at closest approach "
               "(range \u00f7 c).")
        k.end()

    def _nodal(self, s, t):
        self._show_kv()
        k = self.kv
        k.begin()
        mm = s.mean_motion
        node, perig = A.j2_rates(mm, s.incl, s.ecc)
        sunsync = A.is_sun_synchronous(node)
        rep = A.repeat_ground_track(mm)
        maxpass = A.longest_possible_pass_min(mm, s.ecc)

        k.section("Orbit-plane dynamics (J2 secular)")
        k.row("Revs/day", "%.4f" % mm, COL_ACCENT)
        k.row("Node drift", "%+.3f\u00b0/day" % node)
        k.row("Perigee drift", "%+.3f\u00b0/day" % perig)
        k.row("Sun-synchronous", "yes" if sunsync else "no",
              COL_ACCENT2 if sunsync else COL_MUTED)

        k.section("Local time & repeat")
        ltan = A.ltan_hours(s.raan, t)
        hh = int(ltan)
        mi = int((ltan - hh) * 60 + 0.5)
        if mi >= 60:
            mi -= 60
            hh = (hh + 1) % 24
        k.row("LTAN", "%02d:%02d" % (hh, mi))
        k.row("Repeat track", ("%d rev / %d d" % (rep[0], rep[1])) if rep
              else "none < 30 d")
        k.row("Longest pass", "%.1f min" % maxpass, COL_ACCENT2)
        k.note("Node regression walks pass times earlier each day; when it "
               "equals +0.986\u00b0/day the orbit is sun-synchronous (fixed "
               "LTAN). Perigee drift goes to zero at the 63.4\u00b0 critical "
               "inclination (the Molniya trick). 'Longest pass' is an overhead "
               "pass at apogee \u2014 the best case.")
        k.end()

    def _sunbeta(self, s, t):
        # data card on top with a 60-day beta plot beneath via plot surface
        self._show_plot(polar=False)
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        days, betas = [], []
        for d in range(0, 60):
            betas.append(self.pred().beta_angle_deg(t + d * 86400))
            days.append(d)
        ax.plot(days, betas, color=COL_ACCENT, linewidth=2)
        ax.axhline(0, color=COL_MUTED, linewidth=0.6)
        # beta* band
        alt = self.pred().subpoint_at(t)[2]
        bstar = A.beta_star_deg(alt)
        ax.axhline(bstar, color=COL_ACCENT2, linewidth=0.8, linestyle="--")
        ax.axhline(-bstar, color=COL_ACCENT2, linewidth=0.8, linestyle="--")
        ax.set_xlabel("days from now")
        ax.set_ylabel("solar beta (\u00b0)")
        ax.grid(True, color=COL_GRID, linewidth=0.5)

        # eclipse fraction over one orbit (geometric sampling)
        period = s.period_min
        ecl = 0
        N = 120
        for kk in range(N):
            if not self.pred().sunlit_at(t + period * 60.0 * kk / N):
                ecl += 1
        frac = ecl / N
        full = ecl == 0
        beta_now = self.pred().beta_angle_deg(t)
        ax.set_title(
            "beta now %.1f\u00b0   beta* \u00b1%.1f\u00b0   %s   "
            "eclipse %.0f%%/orbit (%.1f min)" %
            (beta_now, bstar, "FULL SUN" if full else "eclipsed each rev",
             frac * 100, frac * period),
            color=COL_TEXT, fontsize=10)
        self.mpl.draw()

    def _outlook(self, s, t):
        self._show_kv()
        k = self.kv
        k.begin()
        passes = self.pred().predict_passes(t, self.store.min_el, 60,
                                            t + 7 * 86400)
        k.section("7-day outlook (min %.0f\u00b0)" % self.store.min_el)
        if not passes:
            k.note("No passes above the mask in the next 7 days.")
            k.end()
            return
        over30 = [p for p in passes if p.max_el >= 30]
        best = max(passes, key=lambda p: p.max_el)
        longest = max(passes, key=lambda p: p.los - p.aos)
        gaps = [passes[i + 1].aos - passes[i].aos
                for i in range(len(passes) - 1)]
        mean_gap = sum(gaps) / len(gaps) if gaps else 0
        k.row("Total passes", str(len(passes)), COL_ACCENT)
        k.row("Above 30\u00b0", str(len(over30)))
        k.row("Longest", fmt_hms(longest.los - longest.aos))
        k.row("Mean gap", fmt_hms(mean_gap))

        k.section("Best pass this week")
        k.row("Peak elevation", "%.1f\u00b0" % best.max_el, COL_ACCENT2, big=True)
        k.row("When", fmt_utc(best.aos, "%a %m-%d %H:%M"))
        k.row("Countdown", fmt_hms(best.aos - t))
        k.row("Duration", fmt_hms(best.los - best.aos))
        k.note("Answers \"when this week is worth operating this bird\" at a "
               "glance.")
        k.end()

    def _orbitpos(self, s, t):
        self._show_kv()
        k = self.kv
        k.begin()
        mm = s.mean_motion
        ma = A.mean_anomaly_now_deg(s.ma, mm, t, s.epoch_unix)
        nu = A.true_anomaly_deg(ma, s.ecc)
        u = A.arg_of_latitude_deg(s.argp, nu)
        to_peri, to_apo = A.time_to_perigee_apogee_s(ma, mm)
        period_s = 86400.0 / mm if mm else 0
        rev = s.rev_at_epoch + int((t - s.epoch_unix) / period_s) if period_s else 0
        age = (t - s.epoch_unix) / 86400.0

        k.section("Position in orbit (now)")
        k.row("Mean anomaly", "%.1f\u00b0" % ma)
        k.row("True anomaly", "%.1f\u00b0" % nu)
        k.row("Arg of latitude", "%.1f\u00b0" % u, COL_ACCENT)

        k.section("Perigee / apogee")
        k.row("To perigee", _hm(to_peri))
        k.row("To apogee", _hm(to_apo))
        k.row("Arg of perigee", "%.1f\u00b0" % s.argp)
        k.row("RAAN", "%.1f\u00b0" % s.raan)

        k.section("Bookkeeping")
        k.row("Rev now", str(rev))
        k.row("Epoch age", "%.2f days" % age,
              COL_WARN if age > 14 else COL_MUTED)
        k.note("Mean anomaly is the uniform orbit clock; true anomaly is the "
               "real angle from perigee (ahead near perigee, behind near "
               "apogee); argument of latitude (\u03c9 + \u03bd) is the angle up "
               "from the equator.")
        k.end()

    # ================= graphical pages =================
    def _groundtrack(self, s, t):
        self._show_plot(polar=False)
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        draw_basemap(ax)
        period = s.period_min * 60.0 if s.period_min else 5400.0
        track = []
        for i in range(161):
            tt = t + period * 2 * i / 160
            lat, lon, _ = self.pred().subpoint_at(tt)
            track.append((lon, lat))
        seg_lo, seg_la, prev = [], [], None
        for lon, lat in track:
            if prev is not None and abs(lon - prev) > 180:
                ax.plot(seg_lo, seg_la, color=COL_ACCENT, linewidth=1.4)
                seg_lo, seg_la = [], []
            seg_lo.append(lon)
            seg_la.append(lat)
            prev = lon
        if seg_lo:
            ax.plot(seg_lo, seg_la, color=COL_ACCENT, linewidth=1.4)
        lat0, lon0, _ = self.pred().subpoint_at(t)
        ax.plot([lon0], [lat0], "o", color=COL_ACCENT2, markersize=8, zorder=6)
        ax.plot([self.store.obs.lon], [self.store.obs.lat], "^",
                color=COL_WARN, markersize=9, zorder=6)
        ax.set_title("%s \u2014 ground track, next 2 orbits" % s.name,
                     color=COL_TEXT, fontsize=10)
        self.mpl.draw()

    def _doppler(self, s, t):
        self._show_plot(polar=False)
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        self.store.ensure_transponders(s)
        dl = 145_800_000
        if s.transponders and s.transponders[0].downlink:
            dl = s.transponders[0].downlink
        nxt = self.pred().predict_passes(t - 1800, self.store.min_el, 1,
                                         t + 6 * 86400)
        if not nxt:
            ax.set_title("No upcoming pass to model Doppler for.",
                         color=COL_TEXT, fontsize=10)
            self.mpl.draw()
            return
        p = nxt[0]
        ts, shifts = [], []
        maxrr = 0.0
        for i in range(121):
            tt = p.aos + (p.los - p.aos) * i / 120
            L = self.pred().look(tt)
            maxrr = max(maxrr, abs(L.range_rate))
            rx, _ = self.pred().doppler_freqs(dl, 0, L.range_rate)
            ts.append((tt - p.aos) / 60.0)
            shifts.append(rx - dl)
        ax.plot(ts, shifts, color=COL_ACCENT, linewidth=2)
        ax.axhline(0, color=COL_MUTED, linewidth=0.6)
        ax.set_xlabel("minutes after AOS")
        ax.set_ylabel("Doppler shift (Hz)")
        ax.grid(True, color=COL_GRID, linewidth=0.5)
        ax.set_title("%.4f MHz downlink   peak %+d Hz   max range-rate "
                     "%.3f km/s" % (dl / 1e6, max(shifts, key=abs), maxrr),
                     color=COL_TEXT, fontsize=10)
        self.mpl.draw()
