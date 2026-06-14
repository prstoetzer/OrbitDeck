"""location.py - set the observer site by lat/lon/alt or Maidenhead grid."""

import tkinter as tk
from tkinter import ttk, messagebox

from . import Screen, COL_TEXT, COL_MUTED, COL_ACCENT, FONT_MONO


class LocationScreen(Screen):
    def build(self):
        self.header("Location \u2014 observer site")
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

    def on_show(self):
        o = self.store.obs
        self.lat.set("%.4f" % o.lat)
        self.lon.set("%.4f" % o.lon)
        self.alt.set("%.0f" % o.alt_m)
        self.grid.set(self.store.my_grid())
        self.info.set("Current: %.4f, %.4f  alt %.0f m  grid %s" %
                      (o.lat, o.lon, o.alt_m, self.store.my_grid()))

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
