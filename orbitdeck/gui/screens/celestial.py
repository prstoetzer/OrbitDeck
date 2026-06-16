"""celestial.py (screen) - track celestial bodies and analyze EME.

Two tabs:
  Bodies - live az/el of the Sun, Moon, planets, and cosmic radio sources
           (Cas A, Cyg A, etc.) plus a "cold sky" reference, on a sky polar
           plot and in a table. For antenna calibration and radio astronomy.
  EME    - Earth-Moon-Earth analysis: Moon az/el, distance, self-echo Doppler,
           total path loss by band, sky temperature, and common-Moon-visibility
           windows with a chosen second station.
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox

from . import (Screen, MplPanel, KVPanel, TabBar, COL_PANEL, COL_TEXT,
               COL_MUTED, COL_ACCENT, COL_ACCENT2, COL_WARN, now_unix, fmt_utc,
               make_scrolled_tree, autohide_scrollbar)
from ...engine import celestial as CE
from ...engine.predict import grid_to_latlon
from ...engine.predict import _sun_eci_unit, _gmst_rad, jd_of, DEG
from .. import exports as EX


def _sun_azel(lat, lon, t):
    jd = jd_of(t)
    sx, sy, sz = _sun_eci_unit(jd)
    th = _gmst_rad(jd)
    lst = th + lon * DEG
    ss, cs = math.sin(lst), math.cos(lst)
    slat, clat = math.sin(lat * DEG), math.cos(lat * DEG)
    e = -ss * sx + cs * sy
    n = -slat * cs * sx - slat * ss * sy + clat * sz
    u = clat * cs * sx + clat * ss * sy + slat * sz
    el = math.degrees(math.atan2(u, math.hypot(e, n)))
    az = math.degrees(math.atan2(e, n)) % 360
    return az, el


class CelestialScreen(Screen):
    live = True

    def build(self):
        self.sat_header("Celestial \u2014 Bodies & EME")
        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=8)
        self._t_bodies = tabs.add("Bodies")
        self._t_eme = tabs.add("EME")
        self._build_bodies(self._t_bodies)
        self._build_eme(self._t_eme)

    # ---- bodies ----
    def _build_bodies(self, parent):
        left = ttk.Frame(parent, style="TFrame")
        left.pack(side="left", fill="y", padx=(8, 4), pady=6)
        ttk.Button(left, text="Export CSV\u2026",
                   command=self._export_bodies).pack(anchor="w", pady=(0, 4))
        cols = ("body", "az", "el")
        heads = ("Body", "Az", "El")
        _btw = ttk.Frame(left, style="TFrame")
        _btw.pack(fill="y", expand=True)
        self.btree = ttk.Treeview(_btw, columns=cols, show="headings",
                                  height=18)
        for c, h in zip(cols, heads):
            self.btree.heading(c, text=h)
            self.btree.column(c, width=180 if c == "body" else 60,
                              minwidth=60,
                              anchor="w" if c == "body" else "center")
        _btsb = ttk.Scrollbar(_btw, orient="vertical",
                              command=self.btree.yview)
        self.btree.configure(
            yscrollcommand=autohide_scrollbar(_btsb, "right",
                                              before=self.btree))
        _btsb.pack(side="right", fill="y")
        self.btree.pack(side="left", fill="y", expand=False)
        self.bpanel = MplPanel(parent, figsize=(5.2, 5.2), polar=True)
        self.bpanel.pack(side="left", fill="both", expand=True, padx=4, pady=6)

    def _body_entries(self, t):
        lat, lon = self.store.obs.lat, self.store.obs.lon
        entries = []
        saz, sel = _sun_azel(lat, lon, t)
        entries.append(("Sun", saz, sel, "star"))
        maz, mel = CE.moon_azel(lat, lon, t)
        entries.append(("Moon", maz, mel, "moon"))
        for p in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
            ae = CE.planet_azel(p, lat, lon, t)
            if ae:
                entries.append((p, ae[0], ae[1], "planet"))
        for src in CE.RADIO_SOURCES:
            if src == "Sun":
                continue
            ae = CE.source_azel(src, lat, lon, t)
            if ae:
                entries.append((src, ae[0], ae[1], "radio source"))
        # cold sky reference
        cs = CE.radec_to_azel(CE.COLD_SKY_RADEC[0], CE.COLD_SKY_RADEC[1],
                              lat, lon, t)
        entries.append(("Cold sky (ref)", cs[0], cs[1], "reference"))
        return entries

    def _render_bodies(self):
        t = now_unix()
        entries = self._body_entries(t)
        for i in self.btree.get_children():
            self.btree.delete(i)
        for name, az, el, kind in entries:
            self.btree.insert("", "end", values=(
                name, "%.1f\u00b0" % az,
                "%.1f\u00b0" % el if el >= 0 else "(down)"))
        self._bodies_cache = entries
        # polar sky plot of bodies above the horizon
        self.bpanel.clear(polar=True)
        ax = self.bpanel.ax
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(0, 90)
        ax.set_rgrids([0, 30, 60, 90], labels=["90", "60", "30", "0"],
                      color=COL_MUTED, fontsize=7)
        ax.set_thetagrids(range(0, 360, 45),
                          labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                          color=COL_MUTED, fontsize=8)
        colors = {"star": COL_WARN, "moon": "#cfd8e3", "planet": COL_ACCENT2,
                  "radio source": COL_ACCENT, "reference": COL_MUTED}
        for name, az, el, kind in entries:
            if el < 0:
                continue
            ax.plot([az * DEG], [90 - el], marker="o",
                    color=colors.get(kind, COL_TEXT), markersize=8, zorder=6)
            ax.annotate(name, (az * DEG, 90 - el), color=COL_TEXT, fontsize=7,
                        xytext=(4, 3), textcoords="offset points", zorder=7)
        self.bpanel.draw()

    def _export_bodies(self):
        ents = getattr(self, "_bodies_cache", None)
        if not ents:
            return
        rows = [(n, az, el, kind) for (n, az, el, kind) in ents]
        headers, out = EX.celestial_rows(rows)
        self.save_text_dialog(EX.rows_to_csv(headers, out),
                              "celestial_bodies.csv",
                              title="Export celestial bodies", ext=".csv",
                              filetypes=[("CSV", "*.csv")])

    # ---- EME ----
    def _build_eme(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Band:", style="TLabel").pack(side="left")
        self._band = tk.StringVar(value="144")
        for lab, v in (("6m", "50"), ("2m", "144"), ("70cm", "432"),
                       ("23cm", "1296"), ("3cm", "10368")):
            ttk.Radiobutton(bar, text=lab, value=v, variable=self._band,
                            command=self._render_eme).pack(side="left")
        ttk.Label(bar, text="  Other station (grid/lat,lon):",
                  style="TLabel").pack(side="left", padx=(10, 2))
        self._dx = tk.StringVar(value="")
        ttk.Entry(bar, textvariable=self._dx, width=14).pack(side="left")
        ttk.Button(bar, text="Common-Moon windows",
                   command=self._render_eme).pack(side="left", padx=6)
        ttk.Button(bar, text="Export windows\u2026",
                   command=self._export_eme).pack(side="right", padx=2)

        self.eme_kv = KVPanel(parent, label_width=22)
        self.eme_kv.pack(fill="x", padx=8, pady=6)
        cols = ("start", "end", "dur")
        heads = ("Window start (UTC)", "End (UTC)", "Duration (min)")
        treewrap, self.eme_tree = make_scrolled_tree(
            parent, cols, show="headings", height=8)
        for c, h in zip(cols, heads):
            self.eme_tree.heading(c, text=h)
            self.eme_tree.column(c, width=180, anchor="center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        self._eme_windows = []

    def _render_eme(self):
        lat, lon = self.store.obs.lat, self.store.obs.lon
        t = now_unix()
        freq = float(self._band.get()) * 1e6
        maz, mel = CE.moon_azel(lat, lon, t)
        dist = CE.moon_distance_km(t)
        dop = CE.eme_doppler_hz(freq, lat, lon, t)
        loss = CE.eme_path_loss_db(freq, t)
        skyt = CE.sky_temperature_k(freq_mhz=freq / 1e6)
        self.eme_kv.begin()
        self.eme_kv.section("Moon now (from %s)" % self.store.obs_name)
        self.eme_kv.row("Azimuth / Elevation",
                        "%.1f\u00b0 / %.1f\u00b0%s"
                        % (maz, mel, "" if mel >= 0 else "  (below horizon)"))
        self.eme_kv.row("Distance", "%.0f km" % dist)
        self.eme_kv.section("EME path on %s"
                            % ({"50": "6 m", "144": "2 m", "432": "0.7 m",
                                "1296": "0.23 m",
                                "10368": "0.03 m (3 cm)"}.get(
                                    self._band.get(),
                                    self._band.get() + " m")))
        self.eme_kv.row("Total path loss", "%.1f dB" % loss)
        self.eme_kv.row("Self-echo Doppler", "%+.0f Hz" % dop)
        self.eme_kv.row("Echo delay", "~2.5 s round trip")
        self.eme_kv.row("Cold-sky temperature", "~%.0f K" % skyt)
        self.eme_kv.note("Path loss and Doppler are estimates; sky temperature "
                         "is a cold-sky reference (the galactic plane is far "
                         "hotter). EME needs the Moon up at both stations.")
        self.eme_kv.end()
        # common-Moon windows with the other station
        for i in self.eme_tree.get_children():
            self.eme_tree.delete(i)
        self._eme_windows = []
        dx = self._dx.get().strip()
        if dx:
            ll = None
            if "," in dx:
                try:
                    a, b = dx.split(",")
                    ll = (float(a), float(b))
                except Exception:
                    ll = None
            else:
                ll = grid_to_latlon(dx)
            if ll:
                wins = CE.eme_window(lat, lon, ll[0], ll[1], t, hours=48,
                                     min_el=0.0)
                self._eme_windows = wins
                self._dx_ll = ll
                for (start, end) in wins:
                    self.eme_tree.insert("", "end", values=(
                        fmt_utc(start), fmt_utc(end),
                        "%.0f" % ((end - start) / 60.0)))

    def _export_eme(self):
        if not self._eme_windows:
            messagebox.showinfo("EME windows",
                                "Enter a second station and compute windows "
                                "first.")
            return
        headers, rows = EX.eme_window_rows(self.store.obs_name, self._dx.get(),
                                           self._eme_windows)
        self.save_text_dialog(EX.rows_to_csv(headers, rows), "eme_windows.csv",
                              title="Export EME windows", ext=".csv",
                              filetypes=[("CSV", "*.csv")])

    def on_show(self):
        self._render_bodies()
        self._render_eme()

    def on_tick(self, now=None):
        # bodies move slowly; refresh the live readout each tick
        try:
            self._render_bodies()
        except Exception:
            pass
