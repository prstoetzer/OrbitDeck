"""learn.py - the "Learn" screen: a home for OrbitDeck's standalone teaching
tools, grouped as tabs so they don't clutter the operating screens.

Tabs are organised into four groups (a category selector over the tab strip):

  Orbits (how orbits work):
    * Kepler      - equal-areas two-body demonstration
    * Speed       - vis-viva orbital speed vs altitude (perigee/apogee marked)
    * Geometry    - slant range vs elevation
    * Horizon     - how far a satellite can see vs altitude
    * Track drift - westward ground-track shift per orbit; repeat tracks
    * Transfers   - Hohmann transfer delta-v; why plane changes are costly
    * Element age - element-set age and along-track drift
  Passes (observing from the ground):
    * Coverage    - accumulate a satellite's footprint over 24 h
    * Sunlight    - beta angle / eclipse threshold vs altitude
    * Eclipse     - lit/shadow timeline over the next several orbits
    * Pointing    - azimuth/elevation sky track of the next pass
    * Constellation - satellites needed for continuous coverage vs altitude
  Radio (working satellites):
    * Transponder - interactive uplink->downlink passband map (shows inversion)
    * Doppler     - both uplink and downlink legs across a pass
    * Link budget - free-space link sandbox with a per-mode workable verdict
    * Duplex practice - keep your own signal on a fixed downlink through a pass
    * Antenna     - interactive gain vs beamwidth pattern
  Reference:
    * Reference   - modes, polarization, subsystems, beacons, operating, bands,
                    modulation, noise, time/frames and constellations
    * Handouts    - print a four-page classroom handout

Each tool reuses the engine's existing models so the numbers match the rest of
the program.
"""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, TabBar, KVPanel, COL_TEXT, COL_MUTED,
               COL_ACCENT, COL_ACCENT2, COL_WARN, COL_GRID, COL_PANEL,
               now_unix, fmt_utc)
from ...engine import analysis as A
from ...engine import linkbudget as LB


class LearnScreen(Screen):
    def build(self):
        self.sat_header("Learn")
        # --- lab-orbit source toggle: run the orbit-based tools against a
        # user-designed lab satellite instead of the catalog selection, so a
        # student can design an orbit and immediately see its coverage/Doppler.
        from .. import lab as _lab
        self._lab_on = tk.BooleanVar(value=False)
        self._lab_elements = _lab.default_elements()
        self._lab_sat = None
        self._lab_pred = None
        self._lab_dialog = None
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=12, pady=(4, 0))
        ttk.Checkbutton(bar, text="Use a lab orbit (design your own)",
                        variable=self._lab_on,
                        command=self._on_lab_toggle).pack(side="left")
        self._lab_edit_btn = ttk.Button(bar, text="Edit lab orbit\u2026",
                                        command=self._open_lab_editor)
        self._lab_edit_btn.pack(side="left", padx=8)
        self._lab_status = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._lab_status,
                  style="Muted.TLabel").pack(side="left", padx=8)

        tabs = TabBar(self.frame, wrap=True, groups=True,
                      on_change=self._on_tab_change)
        self._tabs = tabs
        tabs.pack(fill="both", expand=True, padx=12, pady=4)

        # --- group: Orbits (how an orbit works) ---
        tabs.add_group("Orbits")
        self._t_kep = tabs.add("Kepler")
        self._t_anom = tabs.add("Anomalies")
        self._t_speed = tabs.add("Speed")
        self._t_transfer = tabs.add("Transfers")
        self._t_diff = tabs.add("Element age")
        self._t_decay = tabs.add("Decay")
        # --- group: Geometry (shape & reach) ---
        tabs.add_group("Geometry")
        self._t_geom = tabs.add("Slant range")
        self._t_horizon = tabs.add("Horizon")
        self._t_drift = tabs.add("Track drift")
        self._t_prec = tabs.add("Precession")
        self._t_constel = tabs.add("Constellation")
        # --- group: Passes (observing from the ground) ---
        tabs.add_group("Passes")
        self._t_cov = tabs.add("Coverage")
        self._t_sun = tabs.add("Sunlight")
        self._t_eclipse = tabs.add("Eclipse")
        self._t_point = tabs.add("Pointing")
        self._t_grid = tabs.add("Grid squares")
        # --- group: Radio (working satellites) ---
        tabs.add_group("Radio")
        self._t_xpdr = tabs.add("Transponder")
        self._t_dop = tabs.add("Doppler")
        self._t_link = tabs.add("Link budget")
        self._t_duplex = tabs.add("Duplex practice")
        self._t_ant = tabs.add("Antenna")
        # --- group: Reference ---
        tabs.add_group("Reference")
        self._t_radio = tabs.add("Reference")
        self._t_101 = tabs.add("Handouts")

        self._build_kepler(self._t_kep)
        self._build_anomalies(self._t_anom)
        self._build_speed(self._t_speed)
        self._build_transfer(self._t_transfer)
        self._build_diff(self._t_diff)
        self._build_decay(self._t_decay)
        self._build_geometry(self._t_geom)
        self._build_horizon(self._t_horizon)
        self._build_drift(self._t_drift)
        self._build_precession(self._t_prec)
        self._build_constellation(self._t_constel)
        self._build_coverage(self._t_cov)
        self._build_sunlight(self._t_sun)
        self._build_eclipse(self._t_eclipse)
        self._build_pointing(self._t_point)
        self._build_grid(self._t_grid)
        self._build_transponder(self._t_xpdr)
        self._build_doppler(self._t_dop)
        self._build_link(self._t_link)
        self._build_duplex(self._t_duplex)
        self._build_antenna(self._t_ant)
        self._build_radio101(self._t_radio)
        self._build_101(self._t_101)
        tabs.layout()

    # ---- lab-orbit source for the orbit-based tools ----
    def _lab_active(self):
        return getattr(self, "_lab_on", None) is not None and self._lab_on.get()

    def sat(self):
        if self._lab_active() and getattr(self, "_lab_sat", None) is not None:
            return self._lab_sat
        return self.store.selected_sat()

    def pred(self):
        if self._lab_active() and getattr(self, "_lab_pred", None) is not None:
            return self._lab_pred
        return self.store.pred

    def _ensure_lab_sat(self):
        from .. import lab as _lab
        from ...engine import Predictor
        self._lab_sat = _lab.make_lab_sat(self._lab_elements)
        if self._lab_pred is None:
            self._lab_pred = Predictor()
        self._lab_pred.set_site(self.store.obs)
        self._lab_pred.set_sat(self._lab_sat)

    def _on_lab_toggle(self):
        if self._lab_on.get():
            self._ensure_lab_sat()
            self._lab_status.set("Orbit tools now use the lab orbit (%s)."
                                 % self._lab_sat.name)
        else:
            self._lab_status.set("")
        self._rerender_current()

    def _open_lab_editor(self):
        if not self._lab_on.get():
            self._lab_on.set(True)
        self._ensure_lab_sat()
        if self._lab_dialog is not None:
            try:
                self._lab_dialog.focus()
                return
            except Exception:
                self._lab_dialog = None
        from ..labdialog import LabDialog
        self._lab_dialog = LabDialog(
            self.frame, self._lab_elements,
            on_change=self._on_lab_change, on_save=None,
            compare=None, on_compare=None)
        try:
            self._lab_dialog.win.protocol(
                "WM_DELETE_WINDOW", self._on_lab_dialog_close)
        except Exception:
            pass

    def _on_lab_dialog_close(self):
        try:
            self._lab_dialog.win.destroy()
        except Exception:
            pass
        self._lab_dialog = None

    def _on_lab_change(self, elements):
        self._lab_elements = elements
        self._ensure_lab_sat()
        self._lab_status.set("Orbit tools now use the lab orbit (%s)."
                             % self._lab_sat.name)
        self._rerender_current()

    def _rerender_current(self):
        """Re-render whichever orbit-based tab is active after a lab change."""
        for fn in (self._render_coverage, self._render_sunlight,
                   self._render_diff):
            try:
                fn()
            except Exception:
                pass



    def on_show(self):
        # render the first tab's content for the current satellite
        try:
            self._render_kepler()
        except Exception:
            pass

    def _on_tab_change(self, idx):
        """Render the newly-selected tab so it's never blank on first view.
        Tabs that need an expensive pass search (Doppler, Pointing, Eclipse)
        keep their explicit button instead of running on every tab click."""
        renderers = {
            self._t_cov: self._render_coverage,
            self._t_sun: self._render_sunlight,
            self._t_kep: self._render_kepler,
            self._t_anom: self._render_anomalies,
            self._t_speed: self._render_speed,
            self._t_diff: self._render_diff,
            self._t_decay: self._render_decay,
            self._t_geom: self._render_geometry,
            self._t_horizon: self._render_horizon,
            self._t_drift: self._render_drift,
            self._t_prec: self._render_precession,
            self._t_transfer: self._render_transfer,
            self._t_constel: self._render_constellation,
            self._t_grid: self._render_grid,
            self._t_xpdr: self._render_transponder,
            self._t_link: self._render_link,
            self._t_ant: self._render_antenna,
        }
        try:
            page = self._tabs._tabs[idx][2]
            fn = renderers.get(page)
            if fn:
                fn()
        except Exception:
            pass

    # ===================================================================== #5
    def _build_coverage(self, parent):
        ttk.Label(parent, text=(
            "Footprint coverage accumulated over 24 hours for the selected "
            "satellite. This shows WHY a polar orbit eventually sees the whole "
            "Earth while a low-inclination one only covers a band."),
            style="MutedBg.TLabel", wraplength=720,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10)
        ttk.Button(row, text="Compute 24 h coverage",
                   command=self._render_coverage).pack(side="left")
        self._cov_info = tk.StringVar(value="")
        ttk.Label(row, textvariable=self._cov_info,
                  style="Muted.TLabel").pack(side="left", padx=10)
        self.cov_map = MplPanel(parent, figsize=(7.0, 3.6), polar=False)
        self.cov_map.pack(fill="both", expand=True, padx=8, pady=6)

    def _render_coverage(self):
        s = self.sat()
        if not s:
            self._cov_info.set("Select a satellite first.")
            return
        pred = self.pred()
        ax = self.cov_map.ax
        ax.clear()
        self.cov_map._style_axes()
        # accumulate sub-points + footprint radius over 24 h
        t0 = now_unix()
        step = 180.0          # 3-min sampling
        lats, lons, rads = [], [], []
        for i in range(int(86400 / step)):
            la, lo, alt = pred.subpoint_at(t0 + i * step)
            lats.append(la)
            lons.append(lo)
            rads.append(A.footprint_radius_deg(alt))
        # accumulate coverage into a lat/lon grid: for each sub-point, mark every
        # grid cell within the footprint radius. This reads as a clean heat map
        # instead of thousands of overplotted circle outlines.
        import numpy as np
        nlon, nlat = 180, 90
        grid = np.zeros((nlat, nlon))
        lon_edges = np.linspace(-180, 180, nlon + 1)
        lat_edges = np.linspace(-90, 90, nlat + 1)
        lon_c = 0.5 * (lon_edges[:-1] + lon_edges[1:])
        lat_c = 0.5 * (lat_edges[:-1] + lat_edges[1:])
        LON, LAT = np.meshgrid(lon_c, lat_c)
        for la, lo, rad in zip(lats, lons, rads):
            # great-circle distance (deg) from this sub-point to every cell
            dlon = np.radians(LON - lo)
            a = (np.sin(np.radians(LAT)) * math.sin(math.radians(la))
                 + np.cos(np.radians(LAT)) * math.cos(math.radians(la))
                 * np.cos(dlon))
            d = np.degrees(np.arccos(np.clip(a, -1, 1)))
            grid[d <= rad] += 1
        # show the heat map (coverage minutes), masked where never covered
        masked = np.ma.masked_where(grid <= 0, grid)
        ax.pcolormesh(lon_edges, lat_edges, masked, cmap="viridis",
                      shading="auto", alpha=0.85, zorder=1)
        # coastline overlay on top for reference
        try:
            from ...data.worldmap_data import COASTLINES
            for seg in COASTLINES:
                xs = [p[1] for p in seg]
                ys = [p[0] for p in seg]
                ax.plot(xs, ys, color="#ffffff", linewidth=0.4, alpha=0.5,
                        zorder=2)
        except Exception:
            pass
        ax.plot(lons, lats, color=COL_WARN, linewidth=0.5, alpha=0.6, zorder=3)
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_xlabel("Longitude", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Latitude", color=COL_MUTED, fontsize=8)
        maxlat = max(abs(min(lats)), abs(max(lats)))
        covered = float((grid > 0).sum()) / (nlat * nlon) * 100.0
        self._cov_info.set(
            "%s: ground track reaches \u00b1%.0f\u00b0 latitude; covers ~%.0f%% "
            "of the Earth's surface over 24 h (brighter = revisited more often)."
            % (s.name, maxlat, covered))
        self.cov_map.draw()

    # ===================================================================== #1
    def _build_transponder(self, parent):
        ttk.Label(parent, text=(
            "How a transponder maps your uplink to the downlink. Pick a "
            "transponder; the bars show the uplink and downlink passbands. Drag "
            "the slider to move your transmit frequency and see where your "
            "signal comes out \u2014 on an INVERTING linear transponder, tuning "
            "your uplink UP moves your downlink DOWN."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10)
        ttk.Label(row, text="Transponder:", style="Muted.TLabel").pack(
            side="left")
        self._xpdr_pick = ttk.Combobox(row, state="readonly", width=46)
        self._xpdr_pick.pack(side="left", padx=6)
        self._xpdr_pick.bind("<<ComboboxSelected>>",
                             lambda _e: self._render_transponder())
        prow = ttk.Frame(parent, style="TFrame")
        prow.pack(fill="x", padx=10, pady=4)
        ttk.Label(prow, text="Your uplink position", style="Muted.TLabel").pack(
            side="left")
        self._xpdr_pos = tk.DoubleVar(value=0.5)
        ttk.Scale(prow, from_=0.0, to=1.0, variable=self._xpdr_pos,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_transponder()).pack(
            side="left", fill="x", expand=True, padx=8)
        self.xpdr_plot = MplPanel(parent, figsize=(7.2, 2.8), polar=False)
        self.xpdr_plot.pack(fill="x", padx=8, pady=6)
        self._xpdr_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._xpdr_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=4)

    def _xpdr_list(self):
        s = self.sat()
        out = []
        if s and getattr(s, "transponders", None):
            for i, tr in enumerate(s.transponders):
                kind = tr.kind() if hasattr(tr, "kind") else tr.mode
                out.append((i, "%s \u2014 %s" % (s.name, kind), tr))
        return out

    def _render_transponder(self):
        items = self._xpdr_list()
        names = [lbl for _i, lbl, _tr in items]
        cur = self._xpdr_pick.get()
        self._xpdr_pick["values"] = names
        if names and cur not in names:
            self._xpdr_pick.set(names[0])
        ax = self.xpdr_plot.ax
        ax.clear()
        self.xpdr_plot._style_axes()
        if not items:
            self._xpdr_info.set("This satellite has no transponder data loaded. "
                                "Try RS-44 (linear/inverting) or an FM bird.")
            self.xpdr_plot.draw()
            return
        idx = names.index(self._xpdr_pick.get()) if self._xpdr_pick.get() \
            in names else 0
        tr = items[idx][2]
        # passband extents (Hz); single-channel birds get a nominal 5 kHz width
        ul0 = tr.uplink
        ul1 = tr.uplink_high if tr.uplink_high > tr.uplink else tr.uplink + 5000
        dl0 = tr.downlink
        dl1 = tr.downlink_high if tr.downlink_high > tr.downlink \
            else tr.downlink + 5000
        # Plot each passband on its OWN normalised 0..1 scale (stacked), so both
        # render at a readable width regardless of how far apart the real uplink
        # and downlink frequencies are. Ticks show the true MHz at each end.
        ax.set_xlim(-0.04, 1.04)
        ax.broken_barh([(0.0, 1.0)], (3.0, 0.7), facecolors=COL_ACCENT2,
                       alpha=0.45)
        ax.broken_barh([(0.0, 1.0)], (0.8, 0.7), facecolors=COL_ACCENT,
                       alpha=0.45)
        # band names sit clearly above each bar; band-edge frequencies sit just
        # below each bar so neither overlaps the other
        ax.text(0.0, 3.85, "UPLINK", color=COL_TEXT, fontsize=9,
                fontweight="bold")
        ax.text(0.0, 2.74, "%.4f" % (ul0 / 1e6), color=COL_MUTED, fontsize=7,
                va="top")
        ax.text(1.0, 2.74, "%.4f MHz" % (ul1 / 1e6), color=COL_MUTED,
                fontsize=7, ha="right", va="top")
        ax.text(0.0, 1.65, "DOWNLINK", color=COL_TEXT, fontsize=9,
                fontweight="bold")
        ax.text(0.0, 0.54, "%.4f" % (dl0 / 1e6), color=COL_MUTED, fontsize=7,
                va="top")
        ax.text(1.0, 0.54, "%.4f MHz" % (dl1 / 1e6), color=COL_MUTED,
                fontsize=7, ha="right", va="top")
        # your uplink position (fraction) and where it lands on the downlink
        frac = self._xpdr_pos.get()
        up_hz = ul0 + frac * (ul1 - ul0)
        invert = bool(tr.invert)
        dl_frac = (1.0 - frac) if invert else frac
        dn_hz = dl0 + dl_frac * (dl1 - dl0)
        # markers on each normalised band + connector showing the mapping
        ax.plot([frac, frac], [3.0, 3.7], color=COL_WARN, lw=2.5)
        ax.plot([dl_frac, dl_frac], [0.8, 1.5], color=COL_WARN, lw=2.5)
        ax.annotate("", xy=(dl_frac, 1.5), xytext=(frac, 3.0),
                    arrowprops=dict(arrowstyle="->", color=COL_WARN, lw=1.4,
                                    alpha=0.9))
        ax.text(frac, 3.72, "%.4f" % (up_hz / 1e6), color=COL_WARN, fontsize=8,
                ha="center", va="bottom")
        ax.text(dl_frac, 0.78, "%.4f" % (dn_hz / 1e6), color=COL_WARN,
                fontsize=8, ha="center", va="top")
        ax.set_ylim(0.2, 4.2)
        ax.set_yticks([])
        ax.set_xticks([])
        self.xpdr_plot.fig.tight_layout()
        self.xpdr_plot.draw()
        kindtxt = ("an INVERTING linear transponder" if invert and tr.is_linear
                   else "a non-inverting linear transponder" if tr.is_linear
                   else "an FM/single-channel transmitter")
        if tr.is_linear:
            extra = ("Because it's %s, your signal lands at %.4f MHz on the "
                     "downlink. Slide your uplink up and watch the downlink "
                     "move %s." % (kindtxt, dn_hz / 1e6,
                                   "DOWN" if invert else "UP"))
        else:
            extra = ("This is %s: a single channel, no passband to tune "
                     "within \u2014 just one uplink and one downlink frequency."
                     % kindtxt)
        self._xpdr_info.set("Your uplink %.4f MHz \u2192 downlink %.4f MHz. %s"
                            % (up_hz / 1e6, dn_hz / 1e6, extra))

    # ===================================================================== #6
    def _build_doppler(self, parent):
        ttk.Label(parent, text=(
            "Full-pass Doppler. As a satellite approaches it shifts the "
            "received frequency high, then low as it recedes. For a linear bird "
            "both the uplink and the downlink are shifted; the curves below show "
            "each leg across the next pass. On a U/V inverting transponder you "
            "mostly retune the uplink while the downlink drifts the other way."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(parent, text="Plot next pass Doppler",
                   command=self._render_doppler).pack(anchor="w", padx=10)
        self._dop_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._dop_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)
        self.dop_plot = MplPanel(parent, figsize=(7.0, 3.4), polar=False)
        self.dop_plot.pack(fill="both", expand=True, padx=8, pady=6)

    def _render_doppler(self):
        s = self.sat()
        if not s:
            self._dop_info.set("Select a satellite first.")
            return
        pred = self.pred()
        t = now_unix()
        passes = pred.predict_passes(t, getattr(self.store, "min_el", 5), 1,
                                     t + 2 * 86400)
        if not passes:
            self._dop_info.set("No upcoming pass found in the next 2 days.")
            return
        p = passes[0]
        # find a transponder for both legs; fall back to a 2 m downlink
        dl_hz, ul_hz, is_lin = 145900000.0, 0.0, False
        if getattr(s, "transponders", None):
            for tr in s.transponders:
                dl = tr.downlink_center() if hasattr(tr, "downlink_center") \
                    else getattr(tr, "downlink", 0)
                if dl:
                    dl_hz = float(dl)
                    ul_hz = float(tr.uplink_center() if hasattr(
                        tr, "uplink_center") else getattr(tr, "uplink", 0))
                    is_lin = bool(tr.is_linear)
                    break
        ts, dn_sh, up_sh = [], [], []
        n = 100
        for i in range(n + 1):
            tt = p.aos + (p.los - p.aos) * i / n
            rr = pred.look(tt).range_rate
            ts.append((tt - p.aos) / 60.0)
            dn_sh.append(LB.doppler_shift_hz(dl_hz, rr))
            if ul_hz:
                up_sh.append(LB.doppler_shift_hz(ul_hz, rr))
        ax = self.dop_plot.ax
        ax.clear()
        self.dop_plot._style_axes()
        ax.plot(ts, [x / 1000.0 for x in dn_sh], color=COL_ACCENT, lw=1.6,
                label="Downlink %.3f MHz" % (dl_hz / 1e6))
        if up_sh:
            ax.plot(ts, [x / 1000.0 for x in up_sh], color=COL_ACCENT2, lw=1.6,
                    label="Uplink %.3f MHz" % (ul_hz / 1e6))
        ax.axhline(0, color=COL_GRID, lw=0.6)
        ax.legend(fontsize=7, loc="upper right", facecolor="none",
                  labelcolor=COL_TEXT, edgecolor=COL_GRID)
        ax.set_xlabel("Minutes into pass", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Doppler shift (kHz)", color=COL_MUTED, fontsize=8)
        if up_sh and is_lin:
            tip = ("The higher band swings more (%.1f kHz vs %.1f kHz peak). "
                   "Keep your downlink centred by retuning the uplink; on an "
                   "inverting bird the correction goes the opposite way."
                   % (max(abs(min(up_sh)), abs(max(up_sh))) / 1000.0,
                      max(abs(min(dn_sh)), abs(max(dn_sh))) / 1000.0))
        else:
            tip = "Tune DOWN through the pass as the downlink falls."
        self._dop_info.set("%s pass at %s UTC. %s"
                           % (s.name, fmt_utc(p.aos, "%H:%M"), tip))
        self.dop_plot.draw()

    # ===================================================================== #7
    def _build_sunlight(self, parent):
        ttk.Label(parent, text=(
            "Beta angle and eclipse. The beta angle is the angle between the "
            "orbit plane and the Sun; when |beta| exceeds the full-sun "
            "threshold beta* the satellite is in continuous sunlight (no "
            "eclipse). Higher orbits have a larger beta* so they're easier to "
            "keep in the Sun \u2014 relevant to power and to optical visibility."),
            style="MutedBg.TLabel", wraplength=720,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(parent, text="Show beta* vs altitude",
                   command=self._render_sunlight).pack(anchor="w", padx=10)
        self.sun_plot = MplPanel(parent, figsize=(7.0, 3.6), polar=False)
        self.sun_plot.pack(fill="both", expand=True, padx=8, pady=6)

    def _render_sunlight(self):
        ax = self.sun_plot.ax
        ax.clear()
        self.sun_plot._style_axes()
        alts = list(range(200, 40001, 200))
        betas = [A.beta_star_deg(a) for a in alts]
        ax.plot([a / 1000.0 for a in alts], betas, color=COL_ACCENT, lw=1.6)
        ax.set_ylim(0, 95)
        # mark a few reference orbits; stagger label heights so nearby ones
        # (ISS ~420, LEO ~550) don't overprint, and place each above the curve
        for name, a, dy in (("ISS", 420, 10), ("LEO", 550, 22),
                            ("MEO", 20200, 6), ("GEO", 35786, 6)):
            ax.axvline(a / 1000.0, color=COL_GRID, lw=0.5)
            y = min(A.beta_star_deg(a) + dy, 90)
            ax.text(a / 1000.0, y, name, color=COL_MUTED, fontsize=7,
                    ha="center", va="bottom", clip_on=True)
        ax.set_xlabel("Altitude (1000 km)", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Full-sun threshold beta* (deg)", color=COL_MUTED,
                      fontsize=8)
        # mark the current satellite's altitude (catalog or lab orbit)
        s = self.sat()
        if s is not None:
            try:
                alt_km = self.pred().subpoint_at(now_unix())[2]
                ax.axvline(alt_km / 1000.0, color=COL_WARN, lw=1.4)
                ax.text(alt_km / 1000.0, min(A.beta_star_deg(alt_km) + 30, 88),
                        "%s\n%.0f km" % (s.name, alt_km), color=COL_WARN,
                        fontsize=7, ha="center", va="bottom", clip_on=True)
            except Exception:
                pass
        self.sun_plot.fig.tight_layout()
        self.sun_plot.draw()

    # ===================================================================== #8
    def _build_link(self, parent):
        ttk.Label(parent, text=(
            "Link-budget sandbox. See why a 5 W handheld can work a LEO bird "
            "but not a distant one: free-space path loss grows with range and "
            "frequency. Adjust the inputs and read the received power."),
            style="MutedBg.TLabel", wraplength=720,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        form = ttk.Frame(parent, style="TFrame")
        form.pack(fill="x", padx=10, pady=4)
        self._lk = {}
        fields = [("Range (km)", "range", "1200"),
                  ("Frequency (MHz)", "freq", "435"),
                  ("TX power (W)", "pwr", "5"),
                  ("TX gain (dBi)", "txg", "0"),
                  ("RX gain (dBi)", "rxg", "12"),
                  ("Line loss (dB)", "loss", "1")]
        for i, (label, key, default) in enumerate(fields):
            ttk.Label(form, text=label, style="Muted.TLabel").grid(
                row=i // 3, column=(i % 3) * 2, sticky="e", padx=4, pady=3)
            var = tk.StringVar(value=default)
            ttk.Entry(form, textvariable=var, width=9).grid(
                row=i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=4)
            self._lk[key] = var
        mrow = ttk.Frame(parent, style="TFrame")
        mrow.pack(fill="x", padx=10, pady=2)
        ttk.Label(mrow, text="Mode:", style="Muted.TLabel").pack(side="left")
        self._lk_mode = ttk.Combobox(mrow, state="readonly", width=10,
                                     values=["FM", "SSB", "CW", "Digital"])
        self._lk_mode.set("SSB")
        self._lk_mode.pack(side="left", padx=6)
        ttk.Button(mrow, text="Compute link",
                   command=self._render_link).pack(side="left", padx=8)
        self.link_kv = KVPanel(parent, label_width=16)
        self.link_kv.pack(anchor="w", fill="x", padx=10, pady=6)
        self.link_plot = MplPanel(parent, figsize=(7.0, 2.4), polar=False)
        self.link_plot.pack(fill="x", padx=8, pady=4)

    def _render_link(self):
        try:
            rng = float(self._lk["range"].get())
            freq = float(self._lk["freq"].get()) * 1e6
            pwr = float(self._lk["pwr"].get())
            txg = float(self._lk["txg"].get())
            rxg = float(self._lk["rxg"].get())
            loss = float(self._lk["loss"].get())
        except ValueError:
            return
        from .. import radioedu as RE
        b = LB.link_budget(rng, freq, tx_power_w=pwr, tx_gain_dbi=txg,
                           rx_gain_dbi=rxg, line_loss_db=loss)
        margin, need, ok = RE.workable_verdict(b["rx_power_dbm"],
                                               self._lk_mode.get())
        k = self.link_kv
        k.begin()
        k.section("Link budget")
        k.row("EIRP", "%.1f dBm" % b["eirp_dbm"])
        k.row("Path loss", "%.1f dB" % b["fspl_db"], COL_WARN)
        k.row("RX power", "%.1f dBm" % b["rx_power_dbm"], COL_ACCENT, big=True)
        k.row("One-way delay", "%.1f ms" % b["delay_ms"])
        k.row("Verdict", ("workable (+%.0f dB)" % margin) if ok
              else ("marginal (%.0f dB)" % margin),
              COL_ACCENT if ok else COL_WARN, big=True)
        k.note("Required signal depends on mode (%s). FM needs a stronger "
               "signal to fully quiet than a narrow SSB/CW signal does. "
               "Doubling the range adds ~6 dB of loss; so does quadrupling the "
               "frequency." % need)
        k.end()
        # band-loss comparison at this range
        ax = self.link_plot.ax
        ax.clear()
        self.link_plot._style_axes()
        labels = [b[0] for b in RE.SAT_BANDS]
        losses = [RE.fspl_db(rng, f) for _l, f in RE.SAT_BANDS]
        ax.bar(labels, losses, color=COL_ACCENT2, alpha=0.7)
        ax.set_ylabel("Path loss (dB)", color=COL_MUTED, fontsize=8)
        ax.set_title("Free-space loss by band at %.0f km" % rng,
                     color=COL_MUTED, fontsize=8)
        for i, v in enumerate(losses):
            ax.text(i, v + 0.5, "%.0f" % v, ha="center", color=COL_MUTED,
                    fontsize=7)
        self.link_plot.draw()

    # ===================================================================== #9
    def _build_kepler(self, parent):
        ttk.Label(parent, text=(
            "Kepler's second law: a line from the planet to the satellite "
            "sweeps equal areas in equal times. The satellite moves fast near "
            "perigee and slow near apogee. The shaded wedges below each cover "
            "the same time interval \u2014 note they have equal area despite "
            "different shapes."),
            style="MutedBg.TLabel", wraplength=720,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10)
        ttk.Label(row, text="Eccentricity", style="Muted.TLabel").pack(
            side="left")
        self._kep_ecc = tk.DoubleVar(value=0.5)
        ttk.Scale(row, from_=0.0, to=0.8, variable=self._kep_ecc,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_kepler()).pack(
            side="left", fill="x", expand=True, padx=8)
        self.kep_plot = MplPanel(parent, figsize=(5.6, 4.6), polar=False)
        self.kep_plot.pack(fill="both", expand=True, padx=8, pady=6)

    def _render_kepler(self):
        e = self._kep_ecc.get()
        ax = self.kep_plot.ax
        ax.clear()
        self.kep_plot._style_axes()
        a = 1.0
        b = a * math.sqrt(1 - e * e)
        cx = a * e          # focus offset
        # ellipse
        th = [i * math.pi / 180.0 for i in range(361)]
        ex = [a * math.cos(t) - cx for t in th]
        ey = [b * math.sin(t) for t in th]
        ax.plot(ex, ey, color=COL_ACCENT, lw=1.4)
        ax.plot([0], [0], marker="o", color=COL_WARN, markersize=9)
        # two equal-time wedges via Kepler's equation: equal mean-anomaly spans
        import numpy as np
        def wedge(M0, M1, col):
            Ms = np.linspace(M0, M1, 24)
            xs, ys = [0.0], [0.0]
            for M in Ms:
                E = M
                for _ in range(40):
                    E = E - (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
                xv = a * (math.cos(E) - e)
                yv = b * math.sin(E)
                xs.append(xv)
                ys.append(yv)
            xs.append(0.0)
            ys.append(0.0)
            ax.fill(xs, ys, color=col, alpha=0.45)
        dM = 0.6
        wedge(0.0, dM, COL_ACCENT2)                 # near perigee
        wedge(math.pi - dM / 2, math.pi + dM / 2, COL_WARN)   # near apogee
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0, -b * 1.15, "equal areas swept in equal times",
                color=COL_MUTED, fontsize=8, ha="center")
        self.kep_plot.draw()

    # ==================================================================== #11
    def _build_diff(self, parent):
        ttk.Label(parent, text=(
            "Element-set age and drift. As a TLE/element set ages, the "
            "propagated position drifts from reality. This estimates the "
            "along-track error for the selected satellite's current element "
            "set and shows when it's worth refreshing."),
            style="MutedBg.TLabel", wraplength=720,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(parent, text="Analyse current element set",
                   command=self._render_diff).pack(anchor="w", padx=10)
        self.diff_kv = KVPanel(parent, label_width=16)
        self.diff_kv.pack(anchor="w", fill="x", padx=10, pady=6)
        self.diff_plot = MplPanel(parent, figsize=(7.0, 3.0), polar=False)
        self.diff_plot.pack(fill="both", expand=True, padx=8, pady=6)

    def _render_diff(self):
        s = self.sat()
        if not s:
            return
        age = LB.element_age_days(s.epoch_unix, now_unix())
        mm = s.mean_motion or 15.0
        err_now = LB.along_track_error_km(age, mm)
        lvl, conf = LB.trust_level(age)
        k = self.diff_kv
        k.begin()
        k.section(s.name)
        k.row("Epoch", fmt_utc(s.epoch_unix, "%Y-%m-%d %H:%M"))
        k.row("Age", "%.1f days" % age)
        k.row("Trust", lvl, COL_ACCENT if conf > 0.6 else COL_WARN)
        k.row("Along-track err", "~%.0f km" % err_now,
              COL_WARN if err_now > 10 else COL_TEXT)
        k.note("Along-track error grows roughly linearly with age; refresh "
               "elements (Update GP) when it exceeds a few km for accurate "
               "pass timing.")
        k.end()
        # projected error growth
        ax = self.diff_plot.ax
        ax.clear()
        self.diff_plot._style_axes()
        days = list(range(0, 31))
        errs = [LB.along_track_error_km(d, mm) for d in days]
        ax.plot(days, errs, color=COL_ACCENT, lw=1.6)
        ax.axvline(age, color=COL_WARN, lw=1.0)
        ax.text(age, max(errs) * 0.9, "now", color=COL_WARN, fontsize=8)
        ax.set_xlabel("Element-set age (days)", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Along-track error (km)", color=COL_MUTED, fontsize=8)
        self.diff_plot.draw()

    # =============================================== full-duplex tuning practice
    def _build_duplex(self, parent):
        ttk.Label(parent, text=(
            "Full-duplex practice. On a linear bird you hear your own downlink "
            "while you transmit, and you keep it on one spot by retuning the "
            "UPLINK as the satellite moves. Scrub through a simulated pass and "
            "adjust your uplink to keep your signal on the target downlink. The "
            "round-trip Doppler is modelled exactly \u2014 on an inverting "
            "transponder the correction goes the opposite way."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10, pady=2)
        ttk.Label(row, text="Transponder:", style="Muted.TLabel").pack(
            side="left")
        self._dx_pick = ttk.Combobox(row, state="readonly", width=34)
        self._dx_pick.pack(side="left", padx=6)
        self._dx_pick.bind("<<ComboboxSelected>>",
                           lambda _e: self._dx_reset())
        self._dx_auto = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Show ideal tuning", variable=self._dx_auto,
                        command=self._render_duplex).pack(side="left", padx=10)
        ttk.Button(row, text="New pass", command=self._dx_reset).pack(
            side="left")

        trow = ttk.Frame(parent, style="TFrame")
        trow.pack(fill="x", padx=10, pady=2)
        ttk.Label(trow, text="Time in pass", style="Muted.TLabel").pack(
            side="left")
        self._dx_t = tk.DoubleVar(value=0.0)
        ttk.Scale(trow, from_=0.0, to=1.0, variable=self._dx_t,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_duplex()).pack(
            side="left", fill="x", expand=True, padx=8)

        urow = ttk.Frame(parent, style="TFrame")
        urow.pack(fill="x", padx=10, pady=2)
        ttk.Label(urow, text="Your uplink (kHz offset)",
                  style="Muted.TLabel").pack(side="left")
        self._dx_uoff = tk.DoubleVar(value=0.0)
        ttk.Scale(urow, from_=-15.0, to=15.0, variable=self._dx_uoff,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_duplex()).pack(
            side="left", fill="x", expand=True, padx=8)

        self.dx_plot = MplPanel(parent, figsize=(7.2, 2.8), polar=False)
        self.dx_plot.pack(fill="x", padx=8, pady=6)
        self._dx_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._dx_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)
        # a simple synthetic pass range-rate profile, regenerated on reset
        self._dx_profile = None
        self._dx_reset()

    def _dx_linear_transponders(self):
        s = self.store.selected_sat()
        out = []
        if s and getattr(s, "transponders", None):
            for tr in s.transponders:
                if tr.is_linear and tr.uplink and tr.downlink:
                    out.append((s.name, tr))
        # always offer a generic inverting U/V bird so the tab works even with no
        # linear transponder in the catalog selection
        return out

    def _dx_reset(self):
        import math
        # synthesize a pass range-rate profile: approaches (negative), through
        # zero at TCA, recedes (positive). Peak rate scaled to a LEO bird.
        n = 60
        # approaches first (negative range-rate), through zero at TCA, then
        # recedes (positive) -- a realistic LEO pass.
        self._dx_profile = [
            -7.0 * math.cos(math.pi * (i / n)) for i in range(n + 1)]
        # transponder choices
        items = self._dx_linear_transponders()
        labels = ["%s \u2014 %s" % (nm, tr.kind() if hasattr(tr, "kind")
                                    else tr.mode) for nm, tr in items]
        labels.append("Generic U/V inverting (demo)")
        self._dx_items = items
        self._dx_pick["values"] = labels
        if self._dx_pick.get() not in labels:
            self._dx_pick.set(labels[0])
        self._dx_t.set(0.0)
        self._dx_uoff.set(0.0)
        self._render_duplex()

    def _dx_current_transponder(self):
        labels = list(self._dx_pick["values"])
        idx = labels.index(self._dx_pick.get()) if self._dx_pick.get() \
            in labels else len(labels) - 1
        if idx < len(self._dx_items):
            nm, tr = self._dx_items[idx]
            return (float(tr.uplink_center()), float(tr.downlink_center()),
                    bool(tr.invert))
        # generic inverting U/V demo bird
        return (145925000.0, 435625000.0, True)

    def _render_duplex(self):
        from .. import radioedu as RE
        prof = self._dx_profile or [0.0]
        ti = self._dx_t.get()
        n = len(prof) - 1
        rr = prof[int(round(ti * n))]
        ul_c, dl_c, invert = self._dx_current_transponder()
        beta = (rr * 1000.0) / RE.C_LIGHT
        sign = -1.0 if invert else 1.0
        # the IDEAL uplink to keep YOUR signal on the fixed downlink we HEAR:
        # work backwards so heard == dl_c after BOTH Doppler legs cancel.
        dl_satframe_target = dl_c / (1.0 - beta)
        u_heard_target = ul_c + sign * (dl_satframe_target - dl_c)
        ideal_ul = u_heard_target / (1.0 - beta)
        # the user's actual uplink = nominal uplink centre + their kHz offset
        user_ul = ul_c + self._dx_uoff.get() * 1000.0
        # where the USER's signal actually lands on the downlink we hear:
        u_heard = user_ul * (1.0 - beta)
        dl_satframe = dl_c + sign * (u_heard - ul_c)
        heard = dl_satframe * (1.0 - beta)
        err_khz = (heard - dl_c) / 1000.0

        ax = self.dx_plot.ax
        ax.clear()
        self.dx_plot._style_axes()
        # a downlink passband window +/- 12 kHz around centre
        ax.axvspan(-12, 12, color=COL_ACCENT, alpha=0.10)
        ax.axvline(0, color=COL_ACCENT, lw=1.4)           # target (fixed)
        ax.axvline(err_khz, color=COL_WARN, lw=2.4)        # your signal
        ax.text(0, 1.12, "target", color=COL_ACCENT, fontsize=8, ha="center")
        ax.text(err_khz, 0.86, " you", color=COL_WARN, fontsize=8)
        if self._dx_auto.get():
            ideal_off = (ideal_ul - ul_c) / 1000.0
            ax.text(-11.5, 0.5, "ideal uplink offset: %+.2f kHz" % ideal_off,
                    color=COL_ACCENT2, fontsize=8)
        ax.set_xlim(-15, 15)
        ax.set_ylim(0, 1.3)
        ax.set_yticks([])
        ax.set_xlabel("Downlink offset from target (kHz)", color=COL_MUTED,
                      fontsize=8)
        self.dx_plot.fig.tight_layout()
        self.dx_plot.draw()
        within = abs(err_khz) <= 1.0
        verdict = ("\u2713 on frequency" if within
                   else "off by %+.1f kHz \u2014 nudge your uplink %s"
                   % (err_khz, ("down" if (err_khz > 0) ^ invert else "up")))
        rate_txt = ("approaching" if rr < -0.2 else
                    "receding" if rr > 0.2 else "near TCA")
        self._dx_info.set(
            "Range-rate %+.2f km/s (%s). Your signal lands %+.1f kHz from the "
            "target. %s%s" % (rr, rate_txt, err_khz, verdict,
                              "  (inverting bird: tune the opposite way)"
                              if invert else ""))

    # =============================================== orbital speed (vis-viva)
    def _build_speed(self, parent):
        ttk.Label(parent, text=(
            "How fast does it move? Orbital speed follows the vis-viva law: a "
            "satellite is fastest at perigee (closest) and slowest at apogee "
            "(farthest), and lower orbits are faster overall. A LEO bird races "
            "at ~7.7 km/s; a geostationary one ambles at ~3 km/s. The curve "
            "shows circular-orbit speed versus altitude; the markers show a "
            "selected orbit's perigee and apogee speeds."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10, pady=2)
        ttk.Button(row, text="Use current orbit",
                   command=self._render_speed).pack(side="left")
        ttk.Label(row, text="  Eccentricity", style="Muted.TLabel").pack(
            side="left")
        self._spd_ecc = tk.DoubleVar(value=0.0)
        ttk.Scale(row, from_=0.0, to=0.7, variable=self._spd_ecc,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_speed()).pack(
            side="left", fill="x", expand=True, padx=8)
        self.spd_plot = MplPanel(parent, figsize=(7.0, 3.4), polar=False)
        self.spd_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._spd_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._spd_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_speed(self):
        RE = A.RE_KM
        ax = self.spd_plot.ax
        ax.clear()
        self.spd_plot._style_axes()
        alts = list(range(200, 40001, 200))
        speeds = [A.orbital_speed_kms(RE + a, RE + a) for a in alts]
        ax.plot([a / 1000.0 for a in alts], speeds, color=COL_ACCENT, lw=1.8)
        for name, a in (("LEO", 500), ("ISS", 420), ("MEO", 20200),
                        ("GEO", 35786)):
            ax.axvline(a / 1000.0, color=COL_GRID, lw=0.5)
            ax.text(a / 1000.0, A.orbital_speed_kms(RE + a, RE + a) + 0.2, name,
                    color=COL_MUTED, fontsize=7, rotation=90, va="bottom")
        # selected orbit perigee/apogee speeds
        s = self.sat()
        ecc = self._spd_ecc.get()
        info = ""
        if s is not None:
            try:
                alt = self.pred().subpoint_at(now_unix())[2]
            except Exception:
                alt = 600.0
            a_km = RE + alt
            rp = a_km * (1.0 - ecc)
            ra = a_km * (1.0 + ecc)
            vp = A.orbital_speed_kms(rp, a_km)
            va = A.orbital_speed_kms(ra, a_km)
            ax.plot([(rp - RE) / 1000.0], [vp], marker="o", color=COL_ACCENT2,
                    markersize=8)
            ax.plot([(ra - RE) / 1000.0], [va], marker="s", color=COL_WARN,
                    markersize=8)
            if ecc > 0.01:
                info = ("%s at this altitude with ecc %.2f: perigee %.2f km/s "
                        "(\u25cf), apogee %.2f km/s (\u25a0) \u2014 %.1fx faster "
                        "down low." % (s.name, ecc, vp, va, vp / va if va else 0))
            else:
                info = ("%s: ~%.2f km/s in this near-circular orbit. Raise the "
                        "eccentricity to see perigee speed up and apogee slow "
                        "down." % (s.name, vp))
        ax.set_xlabel("Altitude (1000 km)", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Orbital speed (km/s)", color=COL_MUTED, fontsize=8)
        self._spd_info.set(info)
        self.spd_plot.draw()

    # =============================================== slant-range geometry
    def _build_geometry(self, parent):
        ttk.Label(parent, text=(
            "Why low passes are far. A satellite directly overhead is only its "
            "altitude away; near the horizon you're looking across the curve of "
            "the Earth, so it's several times farther \u2014 weaker signal, more "
            "atmosphere, and more Doppler. This shows slant range versus "
            "elevation for the selected orbit's altitude."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(parent, text="Show range vs elevation",
                   command=self._render_geometry).pack(anchor="w", padx=10)
        self.geo_plot = MplPanel(parent, figsize=(7.0, 3.6), polar=False)
        self.geo_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._geo_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._geo_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_geometry(self):
        s = self.sat()
        ax = self.geo_plot.ax
        ax.clear()
        self.geo_plot._style_axes()
        alt = 600.0
        if s is not None:
            try:
                alt = self.pred().subpoint_at(now_unix())[2]
            except Exception:
                pass
        els = list(range(0, 91))
        ranges = [A.slant_range_km(e, alt) for e in els]
        ax.plot(els, ranges, color=COL_ACCENT, lw=1.8)
        # mark overhead and horizon
        r0 = A.slant_range_km(0, alt)
        r90 = A.slant_range_km(90, alt)
        ax.axhline(r90, color=COL_GRID, lw=0.5)
        ax.text(60, r90 + r0 * 0.02, "overhead = altitude (%.0f km)" % r90,
                color=COL_MUTED, fontsize=7)
        ax.set_xlabel("Elevation (deg)", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Slant range (km)", color=COL_MUTED, fontsize=8)
        ax.set_xlim(0, 90)
        nm = s.name if s else "this orbit"
        self._geo_info.set(
            "%s at ~%.0f km: directly overhead it's %.0f km away; at the horizon "
            "(0\u00b0) it's %.0f km \u2014 %.1fx farther, so the signal is much "
            "weaker on low passes." % (nm, alt, r90, r0, r0 / r90 if r90 else 0))
        self.geo_plot.draw()

    # =============================================== how far it sees / horizon
    def _build_horizon(self, parent):
        ttk.Label(parent, text=(
            "How far can it see? From altitude, a satellite's radio horizon is "
            "the edge of the Earth's curve \u2014 the higher it is, the farther "
            "it reaches. This is the same circle as its footprint: the curve "
            "shows horizon distance versus altitude."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(parent, text="Show horizon vs altitude",
                   command=self._render_horizon).pack(anchor="w", padx=10)
        self.hz_plot = MplPanel(parent, figsize=(7.0, 3.4), polar=False)
        self.hz_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._hz_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._hz_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_horizon(self):
        ax = self.hz_plot.ax
        ax.clear()
        self.hz_plot._style_axes()
        alts = list(range(200, 40001, 200))
        dists = [A.horizon_distance_km(a) for a in alts]
        ax.plot([a / 1000.0 for a in alts], dists, color=COL_ACCENT, lw=1.8)
        for name, a in (("LEO", 550), ("MEO", 20200), ("GEO", 35786)):
            ax.axvline(a / 1000.0, color=COL_GRID, lw=0.5)
            ax.text(a / 1000.0, A.horizon_distance_km(a) + 200, name,
                    color=COL_MUTED, fontsize=7, rotation=90, va="bottom")
        ax.set_xlabel("Altitude (1000 km)", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Horizon distance (km)", color=COL_MUTED, fontsize=8)
        s = self.sat()
        nm, alt = "this orbit", 600.0
        if s is not None:
            try:
                alt = self.pred().subpoint_at(now_unix())[2]
                nm = s.name
            except Exception:
                pass
        d = A.horizon_distance_km(alt)
        foot = A.footprint_radius_deg(alt)
        ax.plot([alt / 1000.0], [d], marker="o", color=COL_WARN, markersize=8)
        self._hz_info.set(
            "%s at ~%.0f km can see to about %.0f km in every direction "
            "(footprint half-angle %.0f\u00b0). Two satellites can relay only "
            "while each is above the other's horizon \u2014 the basis of "
            "cross-links and why higher orbits cover more at once."
            % (nm, alt, d, foot))
        self.hz_plot.draw()

    # =============================================== ground-track westward drift
    def _build_drift(self, parent):
        ttk.Label(parent, text=(
            "Why the ground track shifts west. While the satellite completes one "
            "orbit, the Earth turns eastward underneath it, so each pass crosses "
            "the equator farther west than the last. The shift per orbit depends "
            "on the period; when a whole number of orbits fits a (sidereal) day, "
            "the track repeats."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(parent, text="Show westward shift vs altitude",
                   command=self._render_drift).pack(anchor="w", padx=10)
        self.dr_plot = MplPanel(parent, figsize=(7.0, 3.4), polar=False)
        self.dr_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._dr_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._dr_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_drift(self):
        from .. import lab as _lab
        ax = self.dr_plot.ax
        ax.clear()
        self.dr_plot._style_axes()
        alts = list(range(200, 36001, 200))
        shifts = [abs(A.groundtrack_shift_deg(_lab.mean_motion_from_alt(
            float(a)))) for a in alts]
        ax.plot([a / 1000.0 for a in alts], shifts, color=COL_ACCENT, lw=1.8)
        ax.set_xlabel("Altitude (1000 km)", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Westward shift per orbit (deg)", color=COL_MUTED,
                      fontsize=8)
        s = self.sat()
        nm, alt = "this orbit", 600.0
        if s is not None:
            try:
                alt = self.pred().subpoint_at(now_unix())[2]
                nm = s.name
            except Exception:
                pass
        mmv = _lab.mean_motion_from_alt(float(alt))
        sh = abs(A.groundtrack_shift_deg(mmv))
        rep = A.repeat_ground_track(mmv)
        ax.plot([alt / 1000.0], [sh], marker="o", color=COL_WARN, markersize=8)
        rep_txt = ("the track repeats every %d revs / %d day%s"
                   % (rep[0], rep[1], "" if rep[1] == 1 else "s")) if rep \
            else "no short repeat cycle"
        km = sh * (math.pi / 180.0) * A.RE_KM
        self._dr_info.set(
            "%s at ~%.0f km shifts about %.1f\u00b0 west each orbit (~%.0f km "
            "at the equator); %s." % (nm, alt, sh, km, rep_txt))
        self.dr_plot.draw()

    # =============================================== constellation coverage
    def _build_constellation(self, parent):
        ttk.Label(parent, text=(
            "How many satellites for always-on coverage? A single low satellite "
            "is only in view for minutes, so continuous service needs many; the "
            "higher the orbit, the larger each footprint and the fewer you need. "
            "This estimates how many evenly-spaced satellites in one plane keep a "
            "point on the track continuously in view."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10, pady=2)
        ttk.Label(row, text="Min elevation", style="Muted.TLabel").pack(
            side="left")
        self._cn_el = tk.DoubleVar(value=5.0)
        ttk.Scale(row, from_=0.0, to=30.0, variable=self._cn_el,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_constellation()).pack(
            side="left", fill="x", expand=True, padx=8)
        self.cn_plot = MplPanel(parent, figsize=(7.0, 3.4), polar=False)
        self.cn_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._cn_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._cn_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_constellation(self):
        ax = self.cn_plot.ax
        ax.clear()
        self.cn_plot._style_axes()
        min_el = self._cn_el.get()
        alts = list(range(300, 36001, 200))
        ns = [A.sats_for_continuous_coverage(a, min_el) for a in alts]
        ax.plot([a / 1000.0 for a in alts], ns, color=COL_ACCENT, lw=1.8)
        ax.set_yscale("log")
        for name, a in (("LEO", 550), ("MEO", 20200), ("GEO", 35786)):
            ax.axvline(a / 1000.0, color=COL_GRID, lw=0.5)
            n = A.sats_for_continuous_coverage(a, min_el)
            ax.text(a / 1000.0, max(n, 1), " %s: %d" % (name, n),
                    color=COL_MUTED, fontsize=7, va="bottom")
        ax.set_xlabel("Altitude (1000 km)", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Satellites per plane", color=COL_MUTED, fontsize=8)
        n550 = A.sats_for_continuous_coverage(550, min_el)
        self._cn_info.set(
            "At %.0f\u00b0 minimum elevation, a 550 km LEO plane needs ~%d "
            "satellites for continuous coverage of the track, while three at "
            "geostationary altitude blanket nearly a whole hemisphere. That's "
            "why LEO internet constellations need thousands of satellites and "
            "navigation/GEO systems need only dozens." % (min_el, n550))
        self.cn_plot.recolor_ticks()
        self.cn_plot.draw()

    # =============================================== eclipse timeline
    def _build_eclipse(self, parent):
        ttk.Label(parent, text=(
            "Sunlight and shadow, orbit by orbit. Most satellites spend part of "
            "each orbit in the Earth's shadow, running on battery, then recharge "
            "in sunlight. How much shadow depends on the beta angle (see "
            "Sunlight): when the orbit plane is tilted enough toward the Sun, "
            "the satellite stays lit the whole way around. This shows the "
            "lit/shadow pattern over the next several orbits."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(parent, text="Show eclipse timeline",
                   command=self._render_eclipse).pack(anchor="w", padx=10)
        self.ecl_plot = MplPanel(parent, figsize=(7.2, 2.8), polar=False)
        self.ecl_plot.pack(fill="x", padx=8, pady=6)
        self._ecl_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._ecl_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_eclipse(self):
        s = self.sat()
        ax = self.ecl_plot.ax
        ax.clear()
        self.ecl_plot._style_axes()
        if not s:
            self._ecl_info.set("Select a satellite first.")
            self.ecl_plot.draw()
            return
        pred = self.pred()
        t0 = now_unix()
        # window of a few orbits
        try:
            mm = s.mean_motion
        except Exception:
            mm = 15.0
        period_min = 1440.0 / mm if mm else 95.0
        span_s = min(6.0, max(3.0, 360.0 / period_min)) * period_min * 60.0
        span_s = max(span_s, 4 * period_min * 60.0)
        ecls = pred.predict_eclipses(t0, max_n=20,
                                     horizon_days=span_s / 86400.0)
        # draw a lit bar with shadow segments overlaid
        ax.axhspan(0.0, 1.0, xmin=0, xmax=1, color=COL_ACCENT2, alpha=0.25)
        total_ecl = 0.0
        for e in ecls:
            x0 = (e.enter - t0) / 60.0
            x1 = (e.exit - t0) / 60.0
            ax.axvspan(x0, x1, color=COL_WARN, alpha=0.55)
            total_ecl += (e.exit - e.enter)
        ax.set_xlim(0, span_s / 60.0)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_xlabel("Minutes from now", color=COL_MUTED, fontsize=8)
        ax.text(0.01, 1.06, "sunlit", color=COL_ACCENT2, fontsize=8,
                transform=ax.transAxes)
        ax.text(0.12, 1.06, "shadow", color=COL_WARN, fontsize=8,
                transform=ax.transAxes)
        self.ecl_plot.draw()
        if ecls:
            avg = total_ecl / len(ecls) / 60.0
            beta = ecls[0].sun_angle
            self._ecl_info.set(
                "%s: %d eclipse(s) in the next %.0f min, averaging %.1f min in "
                "shadow each orbit (beta \u2248 %.0f\u00b0). The satellite runs "
                "on battery through each shadow and recharges in sunlight."
                % (s.name, len(ecls), span_s / 60.0, avg, beta))
        else:
            self._ecl_info.set(
                "%s appears to be in continuous sunlight over this window \u2014 "
                "its orbit plane is tilted enough toward the Sun (high beta) that "
                "it never enters the Earth's shadow right now." % s.name)

    # =============================================== orbit transfers (delta-v)
    def _build_transfer(self, parent):
        ttk.Label(parent, text=(
            "Changing orbits costs energy. To raise an orbit you speed up at one "
            "point (raising the opposite side), coast halfway round, then speed "
            "up again to circularise \u2014 a Hohmann transfer. This shows the "
            "two burns needed to move between two circular altitudes, and why "
            "changing the orbit's tilt (inclination) is so expensive."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        form = ttk.Frame(parent, style="TFrame")
        form.pack(fill="x", padx=10, pady=4)
        ttk.Label(form, text="From altitude (km)", style="Muted.TLabel").grid(
            row=0, column=0, sticky="e", padx=4, pady=3)
        self._tr_from = tk.StringVar(value="400")
        ttk.Entry(form, textvariable=self._tr_from, width=9).grid(
            row=0, column=1, sticky="w", padx=4)
        ttk.Label(form, text="To altitude (km)", style="Muted.TLabel").grid(
            row=0, column=2, sticky="e", padx=4, pady=3)
        self._tr_to = tk.StringVar(value="35786")
        ttk.Entry(form, textvariable=self._tr_to, width=9).grid(
            row=0, column=3, sticky="w", padx=4)
        ttk.Label(form, text="Plane change (deg)", style="Muted.TLabel").grid(
            row=0, column=4, sticky="e", padx=4, pady=3)
        self._tr_inc = tk.StringVar(value="0")
        ttk.Entry(form, textvariable=self._tr_inc, width=6).grid(
            row=0, column=5, sticky="w", padx=4)
        ttk.Button(parent, text="Compute transfer",
                   command=self._render_transfer).pack(anchor="w", padx=10,
                                                       pady=2)
        self.tr_kv = KVPanel(parent, label_width=22)
        self.tr_kv.pack(anchor="w", fill="x", padx=10, pady=6)

    def _render_transfer(self):
        RE = A.RE_KM
        try:
            r1 = RE + float(self._tr_from.get())
            r2 = RE + float(self._tr_to.get())
            dinc = abs(float(self._tr_inc.get()))
        except ValueError:
            return
        if r1 <= 0 or r2 <= 0:
            return
        # circular speeds
        v1 = A.orbital_speed_kms(r1, r1)
        v2 = A.orbital_speed_kms(r2, r2)
        # transfer ellipse: semi-major axis = (r1+r2)/2
        a_t = (r1 + r2) / 2.0
        v_peri = A.orbital_speed_kms(r1, a_t)   # speed on transfer at r1
        v_apo = A.orbital_speed_kms(r2, a_t)    # speed on transfer at r2
        dv1 = abs(v_peri - v1)
        dv2 = abs(v2 - v_apo)
        # plane change at the higher (slower) end is cheaper; approximate at apoapsis
        v_for_plane = min(v1, v2)
        dv_plane = 2.0 * v_for_plane * math.sin(math.radians(dinc) / 2.0) \
            if dinc > 0 else 0.0
        total = dv1 + dv2 + dv_plane
        k = self.tr_kv
        k.begin()
        k.section("Hohmann transfer")
        k.row("Start circular speed", "%.3f km/s" % v1)
        k.row("End circular speed", "%.3f km/s" % v2)
        k.row("Burn 1 (depart)", "%.3f km/s" % dv1, COL_ACCENT)
        k.row("Burn 2 (arrive)", "%.3f km/s" % dv2, COL_ACCENT)
        if dinc > 0:
            k.row("Plane change %.0f\u00b0" % dinc, "%.3f km/s" % dv_plane,
                  COL_WARN)
        k.row("Total \u0394v", "%.3f km/s" % total, COL_ACCENT2, big=True)
        updown = "Raising" if r2 > r1 else "Lowering"
        note = ("%s the orbit takes two burns totalling %.2f km/s of \u0394v. "
                % (updown, dv1 + dv2))
        if dinc > 0:
            note += ("Rotating the orbit %.0f\u00b0 adds %.2f km/s by itself "
                     "\u2014 plane changes are costly because you must redirect "
                     "the whole orbital velocity, which is why satellites launch "
                     "into their target inclination rather than change it later."
                     % (dinc, dv_plane))
        else:
            note += ("Try a plane change to see why changing an orbit's tilt "
                     "costs far more than changing its altitude.")
        k.note(note)
        k.end()

    # =============================================== nodal precession / sun-sync
    def _build_precession(self, parent):
        ttk.Label(parent, text=(
            "Why orbit planes drift, and sun-synchronous orbits. The Earth's "
            "equatorial bulge tugs on an orbit and slowly rotates its plane "
            "(nodal precession). The rate depends on altitude and inclination. "
            "At one special combination the plane turns about 0.986\u00b0 per day "
            "\u2014 exactly keeping pace with the Earth's march around the Sun, "
            "so the satellite crosses the equator at the same local (sun) time "
            "every day. That's a sun-synchronous orbit, used by imaging and "
            "weather satellites for consistent lighting."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10, pady=2)
        ttk.Label(row, text="Altitude (km)", style="Muted.TLabel").pack(
            side="left")
        self._pr_alt = tk.DoubleVar(value=700.0)
        ttk.Scale(row, from_=300.0, to=2000.0, variable=self._pr_alt,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_precession()).pack(
            side="left", fill="x", expand=True, padx=8)
        self.pr_plot = MplPanel(parent, figsize=(7.0, 3.4), polar=False)
        self.pr_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._pr_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._pr_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_precession(self):
        from .. import lab as _lab
        ax = self.pr_plot.ax
        ax.clear()
        self.pr_plot._style_axes()
        alt = self._pr_alt.get()
        mm = _lab.mean_motion_from_alt(alt)
        incs = list(range(0, 181, 2))
        drifts = [A.j2_rates(mm, i, 0.0)[0] for i in incs]
        ax.plot(incs, drifts, color=COL_ACCENT, lw=1.8)
        ax.axhline(0, color=COL_GRID, lw=0.6)
        # the sun-synchronous line: node drift = +0.9856 deg/day
        ax.axhline(0.98565, color=COL_ACCENT2, lw=1.0, ls="--")
        ax.text(2, 0.98565, " sun-synchronous (+0.986\u00b0/day)",
                color=COL_ACCENT2, fontsize=7, va="bottom")
        # find the sun-sync inclination at this altitude (it's retrograde, >90)
        ss_inc = None
        for i in range(900, 1801):
            d = A.j2_rates(mm, i / 10.0, 0.0)[0]
            if abs(d - 0.98565) < 0.01:
                ss_inc = i / 10.0
                break
        if ss_inc:
            ax.axvline(ss_inc, color=COL_WARN, lw=1.0)
            ax.plot([ss_inc], [0.98565], marker="o", color=COL_WARN,
                    markersize=8)
        ax.set_xlabel("Inclination (deg)", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Nodal drift (deg/day)", color=COL_MUTED, fontsize=8)
        ax.set_xlim(0, 180)
        self.pr_plot.draw()
        if ss_inc:
            self._pr_info.set(
                "At %.0f km, a sun-synchronous orbit needs about %.1f\u00b0 "
                "inclination (slightly retrograde). Note the plane barely drifts "
                "near 90\u00b0 (polar) and drifts fastest near 0\u00b0/180\u00b0; "
                "the bulge can only torque an inclined orbit." % (alt, ss_inc))
        else:
            self._pr_info.set(
                "At %.0f km the sun-synchronous inclination is off this chart; "
                "lower the altitude. The plane barely drifts near 90\u00b0 and "
                "fastest near the equatorial planes." % alt)

    # =============================================== orbital decay / lifetime
    def _build_decay(self, parent):
        ttk.Label(parent, text=(
            "How long until it falls? Atmospheric drag slowly saps a satellite's "
            "energy; the lower it is, the thicker the air and the faster it "
            "decays. Below a few hundred km a satellite reenters in weeks to "
            "months; higher up it can last centuries. The curve shows estimated "
            "lifetime versus altitude for a typical small satellite (drag "
            "depends on mass and area, and rises with solar activity, so treat "
            "this as a guide)."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10, pady=2)
        ttk.Label(row, text="Solar activity", style="Muted.TLabel").pack(
            side="left")
        self._dc_solar = tk.DoubleVar(value=1.0)
        ttk.Scale(row, from_=0.5, to=2.5, variable=self._dc_solar,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_decay()).pack(
            side="left", fill="x", expand=True, padx=8)
        self.dc_plot = MplPanel(parent, figsize=(7.0, 3.4), polar=False)
        self.dc_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._dc_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._dc_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_decay(self):
        from .. import lab as _lab
        ax = self.dc_plot.ax
        ax.clear()
        self.dc_plot._style_axes()
        dens = self._dc_solar.get()
        bstar = 0.0001                  # representative small-sat drag term
        alts = list(range(200, 1201, 20))
        days = []
        for a in alts:
            mm = _lab.mean_motion_from_alt(float(a))
            d = A.estimate_decay_days(bstar, mm, 0.0, dens_scale=dens)
            days.append(min(max(d, 0.1), 3.65e6) if d > 0 else 3.65e6)
        ax.plot(alts, [d / 365.0 for d in days], color=COL_ACCENT, lw=1.8)
        ax.set_yscale("log")
        ax.set_xlabel("Altitude (km)", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Estimated lifetime (years)", color=COL_MUTED, fontsize=8)
        for name, a in (("ISS", 420), ("Sun-sync", 700), ("upper LEO", 1000)):
            ax.axvline(a, color=COL_GRID, lw=0.5)
            ax.text(a, ax.get_ylim()[0], " " + name, color=COL_MUTED,
                    fontsize=7, rotation=90, va="bottom")
        self.dc_plot.recolor_ticks()
        self.dc_plot.draw()
        # readout for ISS-like 420 km and the selected satellite
        mm420 = _lab.mean_motion_from_alt(420.0)
        d420 = A.estimate_decay_days(bstar, mm420, 0.0, dens_scale=dens)
        act = ("low" if dens < 0.9 else "high" if dens > 1.3 else "average")
        self._dc_info.set(
            "With %s solar activity, a small satellite at the ISS's ~420 km "
            "would decay in %s without reboosts \u2014 which is why the ISS fires "
            "its engines periodically. Every ~150 km of altitude multiplies the "
            "lifetime enormously." % (act, A.fmt_decay(d420)))

    # =============================================== the three anomalies
    def _build_anomalies(self, parent):
        ttk.Label(parent, text=(
            "Where is it in the orbit? Three 'anomalies' locate a satellite "
            "along its ellipse. The MEAN anomaly ticks evenly with time; the "
            "TRUE anomaly is the real angle from perigee; they differ on an "
            "eccentric orbit because the satellite speeds up near perigee and "
            "slows near apogee. Drag the mean anomaly and eccentricity to see "
            "the gap."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10, pady=2)
        ttk.Label(row, text="Mean anomaly", style="Muted.TLabel").pack(
            side="left")
        self._an_m = tk.DoubleVar(value=90.0)
        ttk.Scale(row, from_=0.0, to=360.0, variable=self._an_m,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_anomalies()).pack(
            side="left", fill="x", expand=True, padx=8)
        row2 = ttk.Frame(parent, style="TFrame")
        row2.pack(fill="x", padx=10, pady=2)
        ttk.Label(row2, text="Eccentricity ", style="Muted.TLabel").pack(
            side="left")
        self._an_e = tk.DoubleVar(value=0.4)
        ttk.Scale(row2, from_=0.0, to=0.8, variable=self._an_e,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_anomalies()).pack(
            side="left", fill="x", expand=True, padx=8)
        self.an_plot = MplPanel(parent, figsize=(4.4, 4.4), polar=False)
        self.an_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._an_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._an_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_anomalies(self):
        ax = self.an_plot.ax
        ax.clear()
        self.an_plot._style_axes()
        e = self._an_e.get()
        M = self._an_m.get()
        nu = A.true_anomaly_deg(M, e) % 360.0
        a = 1.0
        b = a * math.sqrt(1.0 - e * e)
        c = a * e
        # draw the ellipse (focus at origin = Earth)
        th = [2 * math.pi * i / 200 for i in range(201)]
        ex = [a * math.cos(t) - c for t in th]
        ey = [b * math.sin(t) for t in th]
        ax.plot(ex, ey, color=COL_GRID, lw=1.2)
        ax.plot([0], [0], marker="o", color=COL_ACCENT2, markersize=7)
        ax.text(0.04, 0.02, "Earth", color=COL_ACCENT2, fontsize=8)
        # satellite at true anomaly nu (measured from perigee, +x direction)
        r = a * (1 - e * e) / (1 + e * math.cos(nu * math.pi / 180.0))
        sx = r * math.cos(nu * math.pi / 180.0)
        sy = r * math.sin(nu * math.pi / 180.0)
        ax.plot([0, sx], [0, sy], color=COL_ACCENT, lw=1.2)
        ax.plot([sx], [sy], marker="o", color=COL_ACCENT, markersize=9)
        # perigee marker (closest point, +x toward perigee here at nu=0)
        ax.plot([a - c], [0], marker="x", color=COL_WARN, markersize=8)
        ax.text(a - c, -0.06, "perigee", color=COL_WARN, fontsize=7,
                ha="center", va="top")
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlim(-a - c - 0.2, a - c + 0.3)
        ax.set_ylim(-b - 0.2, b + 0.2)
        self.an_plot.draw()
        diff = (nu - M + 180.0) % 360.0 - 180.0
        self._an_info.set(
            "Mean anomaly %.0f\u00b0 \u2192 true anomaly %.0f\u00b0 (a "
            "%+.0f\u00b0 difference at eccentricity %.2f). On a circle (e=0) "
            "they're identical; the more eccentric the orbit, the more the "
            "satellite races through perigee and lingers at apogee."
            % (M, nu, diff, e))

    # =============================================== Maidenhead grid squares
    def _build_grid(self, parent):
        ttk.Label(parent, text=(
            "Maidenhead grid squares. Operators exchange short location codes "
            "(like FN20 or IO91wm) instead of latitude and longitude. The world "
            "is divided into 18\u00d718 'fields' (two letters), each into 10\u00d710 "
            "'squares' (two digits), each into 24\u00d724 'subsquares' (two "
            "letters). Chasing grid squares worked via satellite is a popular "
            "activity. Enter a location to see its grid."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        form = ttk.Frame(parent, style="TFrame")
        form.pack(fill="x", padx=10, pady=4)
        ttk.Label(form, text="Latitude", style="Muted.TLabel").grid(
            row=0, column=0, sticky="e", padx=4)
        self._gr_lat = tk.StringVar(value="39.93")
        ttk.Entry(form, textvariable=self._gr_lat, width=10).grid(
            row=0, column=1, padx=4)
        ttk.Label(form, text="Longitude", style="Muted.TLabel").grid(
            row=0, column=2, sticky="e", padx=4)
        self._gr_lon = tk.StringVar(value="-74.89")
        ttk.Entry(form, textvariable=self._gr_lon, width=10).grid(
            row=0, column=3, padx=4)
        ttk.Button(form, text="My location",
                   command=self._grid_my_loc).grid(row=0, column=4, padx=6)
        ttk.Button(parent, text="Show grid",
                   command=self._render_grid).pack(anchor="w", padx=10, pady=2)
        self.gr_plot = MplPanel(parent, figsize=(7.0, 3.4), polar=False)
        self.gr_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._gr_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._gr_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _grid_my_loc(self):
        try:
            o = self.store.obs
            self._gr_lat.set("%.4f" % o.lat)
            self._gr_lon.set("%.4f" % o.lon)
        except Exception:
            pass
        self._render_grid()

    def _render_grid(self):
        try:
            lat = float(self._gr_lat.get())
            lon = float(self._gr_lon.get())
        except ValueError:
            return
        lat = max(-90.0, min(89.99, lat))
        lon = max(-180.0, min(179.99, lon))
        grid = A.latlon_to_grid6(lat, lon)
        ax = self.gr_plot.ax
        ax.clear()
        self.gr_plot._style_axes()
        # draw the enclosing field (20 deg lon x 10 deg lat) and the square
        field_lon = int((lon + 180.0) / 20.0) * 20.0 - 180.0
        field_lat = int((lat + 90.0) / 10.0) * 10.0 - 90.0
        # highlight the square the point falls in
        sq_lon = field_lon + int((lon - field_lon) / 2.0) * 2.0
        sq_lat = field_lat + int((lat - field_lat) / 1.0) * 1.0
        # centre the view on the highlighted square (with margin) so the label
        # sits in the middle of the view rather than against the field edge
        cx, cy = sq_lon + 1.0, sq_lat + 0.5
        ax.set_xlim(cx - 7.0, cx + 7.0)
        ax.set_ylim(cy - 3.5, cy + 3.5)
        # field grid lines (drawn across the whole field; view is clipped)
        for i in range(11):
            ax.axvline(field_lon + i * 2.0, color=COL_GRID, lw=0.4)
        for j in range(11):
            ax.axhline(field_lat + j * 1.0, color=COL_GRID, lw=0.4)
        ax.add_patch(__import__("matplotlib").patches.Rectangle(
            (sq_lon, sq_lat), 2.0, 1.0, facecolor=COL_ACCENT, alpha=0.25,
            edgecolor=COL_ACCENT, lw=1.2))
        ax.plot([lon], [lat], marker="o", color=COL_WARN, markersize=9)
        ax.text(cx, cy, grid[:4], color=COL_TEXT,
                fontsize=11, ha="center", va="center", fontweight="bold")
        ax.set_xlabel("Longitude", color=COL_MUTED, fontsize=8)
        ax.set_ylabel("Latitude", color=COL_MUTED, fontsize=8)
        self.gr_plot.fig.tight_layout()
        self.gr_plot.draw()
        self._gr_info.set(
            "%.4f, %.4f is grid %s. The first two letters (%s) are the field, "
            "the two digits (%s) the square, and the last two letters (%s) the "
            "subsquare \u2014 each level pinpoints the location more finely."
            % (lat, lon, grid, grid[:2], grid[2:4], grid[4:6]))

    # =============================================== antenna pointing / geometry
    def _build_pointing(self, parent):
        ttk.Label(parent, text=(
            "Where to point. This traces the next pass across the sky as "
            "azimuth (compass bearing) and elevation (angle above the horizon). "
            "Low passes hug the horizon \u2014 longer slant range, more terrain "
            "and building blockage, and more atmosphere to punch through \u2014 "
            "while a high pass climbs near overhead where signals are strongest."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(parent, text="Plot next pass sky track",
                   command=self._render_pointing).pack(anchor="w", padx=10)
        self._pt_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._pt_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)
        self.pt_plot = MplPanel(parent, figsize=(4.6, 4.6), polar=True)
        self.pt_plot.pack(fill="both", expand=True, padx=8, pady=6)

    def _render_pointing(self):
        s = self.sat()
        if not s:
            self._pt_info.set("Select a satellite first.")
            return
        pred = self.pred()
        t = now_unix()
        passes = pred.predict_passes(t, getattr(self.store, "min_el", 5), 1,
                                     t + 2 * 86400)
        ax = self.pt_plot.ax
        ax.clear()
        self.pt_plot._style_axes()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(90, 0)              # zenith at centre, horizon at rim
        ax.set_rgrids([0, 30, 60, 90], labels=["0", "30", "60", "90"],
                      color=COL_MUTED, fontsize=7)
        ax.set_thetagrids(range(0, 360, 45),
                          labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                          color=COL_MUTED, fontsize=8)
        ax.grid(True, color=COL_GRID, linewidth=0.6)
        if not passes:
            self._pt_info.set("No upcoming pass found in the next 2 days.")
            self.pt_plot.draw()
            return
        p = passes[0]
        az_r, el_r = [], []
        n = 90
        for i in range(n + 1):
            tt = p.aos + (p.los - p.aos) * i / n
            a, e = pred.azel_at(tt)
            az_r.append(math.radians(a))
            el_r.append(max(e, 0.0))
        ax.plot(az_r, el_r, color=COL_ACCENT, lw=2)
        ax.plot([az_r[0]], [el_r[0]], marker="o", color=COL_ACCENT2,
                markersize=7)               # AOS
        ax.plot([az_r[-1]], [el_r[-1]], marker="s", color=COL_WARN,
                markersize=7)               # LOS
        from . import compass
        quality = ("a high, easy pass" if p.max_el >= 60 else
                   "a decent pass" if p.max_el >= 30 else
                   "a low pass \u2014 watch for obstructions")
        self._pt_info.set(
            "Next pass at %s UTC: rises in the %s, peaks at %.0f\u00b0 "
            "elevation, sets in the %s. That's %s. Circle = AOS, square = LOS."
            % (fmt_utc(p.aos, "%H:%M"), compass(p.az_aos), p.max_el,
               compass(p.az_los), quality))
        self.pt_plot.draw()

    # =============================================== antenna gain / beamwidth
    def _build_antenna(self, parent):
        ttk.Label(parent, text=(
            "Antenna gain vs beamwidth. Gain concentrates your signal in one "
            "direction \u2014 but the more gain, the narrower the beam, so a "
            "high-gain antenna must be aimed and tracked while a low-gain omni "
            "hears the whole sky weakly. Drag the gain to see the trade-off."),
            style="MutedBg.TLabel", wraplength=760,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10, pady=2)
        ttk.Label(row, text="Boresight gain (dBi)",
                  style="Muted.TLabel").pack(side="left")
        self._ant_gain = tk.DoubleVar(value=12.0)
        ttk.Scale(row, from_=0.0, to=20.0, variable=self._ant_gain,
                  style="Accent.Horizontal.TScale",
                  command=lambda *_: self._render_antenna()).pack(
            side="left", fill="x", expand=True, padx=8)
        self.ant_plot = MplPanel(parent, figsize=(4.6, 4.6), polar=True)
        self.ant_plot.pack(fill="both", expand=True, padx=8, pady=6)
        self._ant_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._ant_info, style="MutedBg.TLabel",
                  wraplength=760, justify="left").pack(anchor="w", padx=10,
                                                       pady=2)

    def _render_antenna(self):
        from .. import radioedu as RE
        gain = self._ant_gain.get()
        thetas, gains = RE.antenna_gain_pattern(gain)
        bw = RE.beamwidth_deg(gain)
        ax = self.ant_plot.ax
        ax.clear()
        self.ant_plot._style_axes()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        # plot relative to boresight, floored so the lobe shape is visible
        rel = [g - gain for g in gains]
        rr = [max(r + 30.0, 0.0) for r in rel]     # shift so -30 dB = centre
        th = [math.radians(t) for t in thetas]
        ax.plot(th, rr, color=COL_ACCENT, lw=1.8)
        ax.fill(th, rr, color=COL_ACCENT, alpha=0.15)
        ax.set_rlim(0, 32)
        ax.set_rgrids([10, 20, 30], labels=["-20", "-10", "0 dB"],
                      color=COL_MUTED, fontsize=7)
        ax.set_thetagrids(range(0, 360, 45),
                          labels=["boresight", "", "", "", "back", "", "", ""],
                          color=COL_MUTED, fontsize=7)
        ax.grid(True, color=COL_GRID, linewidth=0.5)
        kind = ("nearly omnidirectional \u2014 hears the whole sky, no aiming"
                if gain < 3 else
                "a modest beam \u2014 point it roughly at the satellite"
                if gain < 10 else
                "a sharp beam \u2014 must be aimed and tracked through the pass")
        self._ant_info.set(
            "Gain %.0f dBi \u2192 about %.0f\u00b0 \u22123 dB beamwidth: %s."
            % (gain, bw, kind))
        self.ant_plot.draw()

    # =============================================== #2/#5/#7/#8 radio reference
    def _build_radio101(self, parent):
        from .. import radioedu as RE
        canvas = tk.Canvas(parent, bg=COL_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="Panel.TFrame")
        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=6)
        sb.pack(side="right", fill="y", pady=6)

        def heading(txt):
            ttk.Label(inner, text=txt, style="TLabel",
                      font=("DejaVu Sans", 12, "bold")).pack(
                anchor="w", padx=12, pady=(14, 4))

        def para(txt):
            ttk.Label(inner, text=txt, style="MutedBg.TLabel", wraplength=720,
                      justify="left").pack(anchor="w", padx=14, pady=2)

        def item(term, desc):
            ttk.Label(inner, text=term, style="TLabel",
                      font=("DejaVu Sans", 10, "bold")).pack(
                anchor="w", padx=14, pady=(8, 1))
            ttk.Label(inner, text=desc, style="MutedBg.TLabel", wraplength=700,
                      justify="left").pack(anchor="w", padx=20)

        heading("Modes (which band is up, which is down)")
        para("A satellite's \u201cmode\u201d names the uplink band first, then "
             "the downlink band. The band letters: " +
             ", ".join("%s = %s" % (k, v) for k, v in RE.MODE_BANDS.items()
                       if k != "S2"))
        for term, desc in RE.MODE_EXPLAINERS:
            item(term, desc)

        heading("Why circular polarization?")
        para(RE.POLARIZATION_TEXT)

        heading("What's inside a satellite")
        for term, desc in RE.SUBSYSTEMS:
            item(term, desc)

        heading("Beacons & telemetry")
        para(RE.BEACON_TEXT)

        heading("Operating practice & etiquette")
        for term, desc in RE.OPERATING_PRACTICE:
            item(term, desc)

        heading("Bands & licensing")
        for term, desc in RE.BANDS_LICENSING:
            item(term, desc)

        heading("Modulation modes")
        for term, desc in RE.MODULATION_MODES:
            item(term, desc)

        heading("Noise, sensitivity & the downlink")
        for term, desc in RE.NOISE_SENSITIVITY:
            item(term, desc)

        heading("Time & reference frames")
        for term, desc in RE.TIME_FRAMES:
            item(term, desc)

        heading("The bigger picture: constellations")
        for term, desc in RE.CONSTELLATIONS:
            item(term, desc)

        heading("Coordinate frames (where 'where' is measured)")
        for term, desc in RE.COORDINATE_FRAMES:
            item(term, desc)

        heading("A short history of amateur satellites")
        for term, desc in RE.SAT_HISTORY:
            item(term, desc)

    # ==================================================================== #12
    def _build_101(self, parent):
        ttk.Label(parent, text=(
            "Print the \u201cOrbits 101\u201d handout \u2014 a four-page classroom "
            "reference: page 1 the orbital elements, families, and formulas; "
            "page 2 transponders, modes, Doppler, and the link; page 3 "
            "operating practice, bands, and antennas; page 4 orbit geometry, "
            "drift, and constellations. Generated through OrbitDeck's PDF "
            "pipeline."),
            style="MutedBg.TLabel", wraplength=720,
            justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(parent, text="Save Orbits 101 PDF\u2026",
                   command=self._export_101).pack(anchor="w", padx=10, pady=4)
        self._101_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._101_info,
                  style="MutedBg.TLabel", wraplength=720,
                  justify="left").pack(anchor="w", padx=10, pady=4)

    def _export_101(self):
        from tkinter import filedialog, messagebox
        path = filedialog.asksaveasfilename(
            title="Save Orbits 101 handout", defaultextension=".pdf",
            initialfile="orbits_101.pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            from ..learnsheet import generate_orbits_101_pdf
            generate_orbits_101_pdf(path, page=self.store)
        except Exception as e:
            messagebox.showerror("Orbits 101", "Could not generate PDF:\n%s" % e)
            return
        self._101_info.set("Saved: %s" % path)
        self.app.set_status("Saved Orbits 101 handout: %s" % path)
