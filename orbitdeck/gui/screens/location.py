"""location.py - set the observer site by lat/lon/alt or Maidenhead grid."""

import tkinter as tk
from tkinter import ttk, messagebox

from . import Screen, COL_TEXT, COL_MUTED, COL_ACCENT, FONT_MONO


class LocationScreen(Screen):
    def build(self):
        self.header("Settings \u2014 observer site")
        panel = ttk.Frame(self.frame, style="Panel.TFrame")
        panel.pack(fill="x", padx=16, pady=10)

        self.lat = tk.StringVar()
        self.lon = tk.StringVar()
        self.alt = tk.StringVar()
        self.grid = tk.StringVar()

        def row(label, var, hint=""):
            r = ttk.Frame(panel, style="Panel.TFrame")
            r.pack(fill="x", padx=14, pady=6)
            ttk.Label(r, text=label, style="Muted.TLabel", width=16,
                      anchor="w").pack(side="left")
            ttk.Entry(r, textvariable=var, width=20).pack(side="left")
            if hint:
                ttk.Label(r, text=hint, style="Muted.TLabel").pack(side="left",
                                                                   padx=10)
        row("Latitude (\u00b0N)", self.lat, "e.g. 39.93")
        row("Longitude (\u00b0E)", self.lon, "e.g. -74.89 (west is negative)")
        row("Altitude (m)", self.alt, "e.g. 20")
        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=8)
        row("Maidenhead grid", self.grid, "e.g. FM29nw")

        btns = ttk.Frame(self.frame, style="TFrame")
        btns.pack(fill="x", padx=16, pady=8)
        ttk.Button(btns, text="Apply lat/lon/alt",
                   command=self._apply_latlon).pack(side="left")
        ttk.Button(btns, text="Apply grid",
                   command=self._apply_grid).pack(side="left", padx=8)
        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info, style="Muted.TLabel").pack(
            anchor="w", padx=16, pady=6)

        self._build_gp_source()

    def _build_gp_source(self):
        from ..store import CELESTRAK_GROUPS
        self.header("GP element source")
        panel = ttk.Frame(self.frame, style="Panel.TFrame")
        panel.pack(fill="x", padx=16, pady=10)

        r1 = ttk.Frame(panel, style="Panel.TFrame")
        r1.pack(fill="x", padx=14, pady=6)
        ttk.Label(r1, text="Source", style="Muted.TLabel", width=16,
                  anchor="w").pack(side="left")
        self.gp_kind = tk.StringVar(value="AMSAT (amateur)")
        self._kind_labels = ["AMSAT (amateur)", "CelesTrak category",
                             "Custom URL"]
        kc = ttk.Combobox(r1, textvariable=self.gp_kind, state="readonly",
                          values=self._kind_labels, width=24)
        kc.pack(side="left")
        kc.bind("<<ComboboxSelected>>", lambda _e: self._gp_kind_changed())

        r2 = ttk.Frame(panel, style="Panel.TFrame")
        r2.pack(fill="x", padx=14, pady=6)
        ttk.Label(r2, text="CelesTrak group", style="Muted.TLabel", width=16,
                  anchor="w").pack(side="left")
        self._ct_groups = CELESTRAK_GROUPS
        self.gp_group = tk.StringVar(value=CELESTRAK_GROUPS[0][0])
        self.gp_group_combo = ttk.Combobox(
            r2, textvariable=self.gp_group, state="readonly",
            values=[g[0] for g in CELESTRAK_GROUPS], width=24)
        self.gp_group_combo.pack(side="left")

        r3 = ttk.Frame(panel, style="Panel.TFrame")
        r3.pack(fill="x", padx=14, pady=6)
        ttk.Label(r3, text="Custom URL", style="Muted.TLabel", width=16,
                  anchor="w").pack(side="left")
        self.gp_url = tk.StringVar(value="")
        self.gp_url_entry = ttk.Entry(r3, textvariable=self.gp_url, width=40)
        self.gp_url_entry.pack(side="left")

        b = ttk.Frame(self.frame, style="TFrame")
        b.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(b, text="Save GP source",
                   command=self._save_gp_source).pack(side="left")
        self.gp_info = tk.StringVar(value="")
        ttk.Label(b, textvariable=self.gp_info, style="Muted.TLabel").pack(
            side="left", padx=12)
        ttk.Label(self.frame,
                  text="Note: CelesTrak rate-limits requests and updates data "
                       "at most every 2 hours. If an update fails, wait a while "
                       "or use AMSAT.",
                  style="Muted.TLabel", wraplength=560).pack(
            anchor="w", padx=16, pady=(0, 8))

    def _gp_kind_changed(self):
        kind = self.gp_kind.get()
        # enable/disable the dependent inputs for clarity
        self.gp_group_combo.configure(
            state="readonly" if kind == "CelesTrak category" else "disabled")
        self.gp_url_entry.configure(
            state="normal" if kind == "Custom URL" else "disabled")

    def _save_gp_source(self):
        kind = self.gp_kind.get()
        if kind == "CelesTrak category":
            grp = dict(self._ct_groups).get(self.gp_group.get(), "amateur")
            self.store.gp_source = {"kind": "celestrak", "group": grp}
            msg = "GP source: CelesTrak (%s)" % grp
        elif kind == "Custom URL":
            url = self.gp_url.get().strip()
            if not url:
                self.gp_info.set("Enter a URL first.")
                return
            self.store.gp_source = {"kind": "custom", "url": url}
            msg = "GP source: custom URL"
        else:
            self.store.gp_source = {"kind": "amsat"}
            msg = "GP source: AMSAT (amateur)"
        self.store.save_config()
        self.gp_info.set(msg + " \u2014 used by the next Update GP.")
        self.app.set_status(msg)

    def _load_gp_source_ui(self):
        src = self.store.gp_source or {"kind": "amsat"}
        kind = src.get("kind", "amsat")
        if kind == "celestrak":
            self.gp_kind.set("CelesTrak category")
            label = next((g[0] for g in self._ct_groups
                          if g[1] == src.get("group")), self._ct_groups[0][0])
            self.gp_group.set(label)
        elif kind == "custom":
            self.gp_kind.set("Custom URL")
            self.gp_url.set(src.get("url", ""))
        else:
            self.gp_kind.set("AMSAT (amateur)")
        self._gp_kind_changed()

    def on_show(self):
        o = self.store.obs
        self.lat.set("%.4f" % o.lat)
        self.lon.set("%.4f" % o.lon)
        self.alt.set("%.0f" % o.alt_m)
        self.grid.set(self.store.my_grid())
        self.info.set("Current: %.4f, %.4f  alt %.0f m  grid %s" %
                      (o.lat, o.lon, o.alt_m, self.store.my_grid()))
        self._load_gp_source_ui()

    def _apply_latlon(self):
        try:
            lat = float(self.lat.get())
            lon = float(self.lon.get())
            alt = float(self.alt.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid", "Latitude, longitude and altitude "
                                 "must be numbers.")
            return
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            messagebox.showerror("Invalid", "Latitude must be -90..90 and "
                                 "longitude -180..180.")
            return
        self.store.set_site(lat, lon, alt)
        self.on_show()
        self.app.set_status("Observer set to %.4f, %.4f" % (lat, lon))

    def _apply_grid(self):
        g = self.grid.get().strip()
        if self.store.set_site_from_grid(g):
            self.on_show()
            self.app.set_status("Observer set from grid %s" % g.upper())
        else:
            messagebox.showerror("Invalid", "Could not parse Maidenhead grid "
                                 "'%s'. Use a 4- or 6-character locator." % g)
