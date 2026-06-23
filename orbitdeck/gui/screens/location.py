"""location.py - set the observer site by lat/lon/alt or Maidenhead grid,
plus an About tab with credits and project/AMSAT links."""

import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

from . import Screen, TabBar, COL_ACCENT


GITHUB_URL = "https://github.com/prstoetzer/OrbitDeck"
AMSAT_URL = "https://www.amsat.org"


class LocationScreen(Screen):
    def build(self):
        self.header("Settings")
        tabs = TabBar(self.frame)
        self._t_settings = tabs.add("Observer & preferences")
        self._t_about = tabs.add("About")
        tabs.pack(fill="both", expand=True)
        # the settings form is tall; wrap it in a vertical scroller so the
        # bottom (pass-prediction + printing prefs) is never clipped on short
        # displays (e.g. a MacBook Air at its default resolution).
        from . import make_vscroll_frame
        sc, settings_body = make_vscroll_frame(self._t_settings)
        sc.pack(fill="both", expand=True)
        self._build_settings(settings_body)
        self._build_about(self._t_about)

    def _build_settings(self, parent):
        self._parent = parent
        ttk.Label(parent, text="Observer site", style="TLabel",
                  font=("DejaVu Sans", 12, "bold")).pack(
            anchor="w", padx=16, pady=(10, 2))
        panel = ttk.Frame(parent, style="Panel.TFrame")
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

        btns = ttk.Frame(parent, style="TFrame")
        btns.pack(fill="x", padx=16, pady=8)
        ttk.Button(btns, text="Apply lat/lon/alt",
                   command=self._apply_latlon).pack(side="left")
        ttk.Button(btns, text="Apply grid",
                   command=self._apply_grid).pack(side="left", padx=8)
        self.info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.info,
                  style="MutedBg.TLabel").pack(
            anchor="w", padx=16, pady=6)

        self._build_gp_source(parent)
        self._build_pass_prefs(parent)
        self._build_print_prefs(parent)

    def _build_about(self, parent):
        wrap = ttk.Frame(parent, style="TFrame")
        wrap.pack(fill="both", expand=True, padx=20, pady=16)

        ttk.Label(wrap, text="OrbitDeck", style="TLabel",
                  font=("DejaVu Sans", 18, "bold")).pack(anchor="w")
        from ... import __version__
        ttk.Label(wrap, text="Version %s" % __version__,
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Label(wrap,
                  text="A cross-platform desktop tracker and orbital-analysis "
                       "tool for amateur radio satellites.",
                  style="TLabel", wraplength=560, justify="left").pack(
            anchor="w", pady=(0, 12))

        ttk.Label(wrap, text="Author", style="TLabel",
                  font=("DejaVu Sans", 11, "bold")).pack(anchor="w")
        ttk.Label(wrap, text="Paul Stoetzer, N8HM",
                  style="TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Label(wrap, text="Project", style="TLabel",
                  font=("DejaVu Sans", 11, "bold")).pack(anchor="w")
        self._link(wrap, GITHUB_URL, GITHUB_URL)
        ttk.Label(wrap,
                  text="Source code, issue tracker, and releases.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        ttk.Separator(wrap, orient="horizontal").pack(fill="x", pady=8)

        ttk.Label(wrap, text="Support AMSAT", style="TLabel",
                  font=("DejaVu Sans", 11, "bold")).pack(anchor="w",
                                                         pady=(4, 2))
        ttk.Label(
            wrap,
            text="If you find OrbitDeck useful, please consider joining and/or "
                 "donating to AMSAT \u2014 the Radio Amateur Satellite "
                 "Corporation. AMSAT is a volunteer, member-supported non-profit "
                 "that designs, builds, and helps launch the amateur radio "
                 "satellites this program is built to track, and works to keep "
                 "amateur radio in space. Your membership and donations directly "
                 "fund the next generation of satellites.",
            style="TLabel", wraplength=560, justify="left").pack(
            anchor="w", pady=(0, 6))
        self._link(wrap, "www.amsat.org", AMSAT_URL)

    def _link(self, parent, text, url):
        from . import COL_BG
        lbl = tk.Label(parent, text=text, fg=COL_ACCENT, bg=COL_BG,
                       cursor="hand2",
                       font=("DejaVu Sans", 10, "underline"))
        lbl.pack(anchor="w", pady=(0, 2))
        lbl.bind("<Button-1>", lambda _e: self._open(url))

    def _open(self, url):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _build_print_prefs(self, parent=None):
        parent = parent or self.frame
        from ..pagesize import normalize, PAGE_LABELS
        ttk.Label(parent, text="Printing", style="TLabel",
                  font=("DejaVu Sans", 12, "bold")).pack(
            anchor="w", padx=16, pady=(10, 2))
        panel = ttk.Frame(parent, style="Panel.TFrame")
        panel.pack(fill="x", padx=16, pady=10)
        r = ttk.Frame(panel, style="Panel.TFrame")
        r.pack(fill="x", padx=14, pady=6)
        ttk.Label(r, text="Page size", style="Muted.TLabel", width=16,
                  anchor="w").pack(side="left")
        self._page_labels = [PAGE_LABELS["letter"], PAGE_LABELS["a4"]]
        cur = normalize(self.store.config.get("page_size"))
        self.page_size_var = tk.StringVar(value=PAGE_LABELS[cur])
        pc = ttk.Combobox(r, textvariable=self.page_size_var, state="readonly",
                          values=self._page_labels, width=24)
        pc.pack(side="left")
        pc.bind("<<ComboboxSelected>>", lambda _e: self._apply_page_size())
        ttk.Label(panel, text="Applies to every printable PDF \u2014 the "
                            "OSCARLOCATOR, reports, reference sheets and "
                            "handouts.",
                  style="Muted.TLabel").pack(anchor="w", padx=14, pady=(0, 8))
        self.page_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.page_info,
                  style="MutedBg.TLabel").pack(anchor="w", padx=16, pady=(0, 6))

    def _apply_page_size(self):
        label = self.page_size_var.get()
        key = "a4" if label.lower().startswith("a4") else "letter"
        self.store.save_config(page_size=key)
        self.page_info.set("Page size set to %s. New PDFs will use it." % label)

    def _build_pass_prefs(self, parent=None):
        parent = parent or self.frame
        ttk.Label(parent, text="Pass prediction", style="TLabel",
                  font=("DejaVu Sans", 12, "bold")).pack(
            anchor="w", padx=16, pady=(10, 2))
        panel = ttk.Frame(parent, style="Panel.TFrame")
        panel.pack(fill="x", padx=16, pady=10)
        r = ttk.Frame(panel, style="Panel.TFrame")
        r.pack(fill="x", padx=14, pady=6)
        ttk.Label(r, text="Min. elevation (\u00b0)", style="Muted.TLabel",
                  width=18, anchor="w").pack(side="left")
        self.minel_var = tk.StringVar(value="%g" % self.store.min_el)
        ttk.Entry(r, textvariable=self.minel_var, width=8).pack(side="left")
        ttk.Label(r, text="passes below this elevation are hidden everywhere "
                          "(screens and reports)",
                  style="Muted.TLabel").pack(side="left", padx=10)
        ttk.Button(panel, text="Apply min. elevation",
                   command=self._apply_minel).pack(side="left", padx=14,
                                                   pady=(2, 10))
        self.minel_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.minel_info,
                  style="MutedBg.TLabel").pack(anchor="w", padx=16, pady=(0, 6))

    def _apply_minel(self):
        try:
            v = float(self.minel_var.get())
        except (TypeError, ValueError):
            self.minel_info.set("Enter a number between 0 and 89.")
            return
        if not (0 <= v <= 89):
            self.minel_info.set("Minimum elevation must be between 0 and 89\u00b0.")
            return
        self.store.min_el = v
        self.store.save_config()
        self.minel_info.set("Minimum elevation set to %g\u00b0. Applied to pass "
                            "tables and reports." % v)

    def _build_gp_source(self, parent=None):
        parent = parent or self.frame
        from ..store import CELESTRAK_GROUPS
        ttk.Label(parent, text="GP element source", style="TLabel",
                  font=("DejaVu Sans", 12, "bold")).pack(
            anchor="w", padx=16, pady=(10, 2))
        panel = ttk.Frame(parent, style="Panel.TFrame")
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

        b = ttk.Frame(parent, style="TFrame")
        b.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(b, text="Save GP source",
                   command=self._save_gp_source).pack(side="left")
        self.gp_info = tk.StringVar(value="")
        ttk.Label(b, textvariable=self.gp_info, style="MutedBg.TLabel").pack(
            side="left", padx=12)
        ttk.Label(parent,
                  text="Note: CelesTrak rate-limits requests and updates data "
                       "at most every 2 hours. If an update fails, wait a while "
                       "or use AMSAT.",
                  style="MutedBg.TLabel", wraplength=560).pack(
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
