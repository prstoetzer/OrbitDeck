"""satellites.py - the catalog (list / select / favorite / fetch transponders)
plus a Who's-up-now quick-visibility scan of the whole database."""

import tkinter as tk
from tkinter import ttk

from . import (Screen, TabBar, COL_TEXT, COL_MUTED, COL_ACCENT, FONT_MONO,
               now_unix, fmt_utc, make_scrolled_tree)
from .. import exports as EX
from ...engine.predict import whos_up
from ...engine.satdb import satellite_category, CATEGORIES


class SatellitesScreen(Screen):
    def build(self):
        self.header("Satellites")
        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        self._t_cat = tabs.add("Catalog")
        self._t_type = tabs.add("By type")
        self._t_up = tabs.add("Who's up now")
        tabs.on_change = self._on_tab
        self._build_catalog(self._t_cat)
        self._build_bytype(self._t_type)
        self._build_whosup(self._t_up)

    def on_show(self):
        self._reload()

    def _on_tab(self, idx):
        if idx == 1:
            self._reload_bytype()
        elif idx == 2:
            self._scan_up()

    # ---- catalog ----
    def _build_catalog(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=4)
        ttk.Label(bar, text="Filter:", style="TLabel").pack(side="left")
        self.filter = tk.StringVar(value="")
        e = ttk.Entry(bar, textvariable=self.filter, width=24)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda _e: self._reload())
        self.favonly = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Favorites only", variable=self.favonly,
                        command=self._reload).pack(side="left", padx=10)

        cols = ("fav", "name", "norad", "period", "incl", "apo", "tx")
        heads = ("\u2605", "Name", "NORAD", "Period", "Incl", "Apogee", "TX")
        treewrap, self.tree = make_scrolled_tree(
            parent, cols, show="headings", height=18)
        widths = {"fav": 36, "name": 150, "norad": 80, "period": 90,
                  "incl": 80, "apo": 90, "tx": 60}
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c],
                             anchor="w" if c == "name" else "center")
        treewrap.pack(fill="both", expand=True, padx=4, pady=10)
        self.tree.bind("<Double-Button-1>", self._select)
        self.tree.bind("<space>", self._toggle_fav)

        btns = ttk.Frame(parent, style="TFrame")
        btns.pack(fill="x", padx=4, pady=(0, 8))
        ttk.Button(btns, text="Select (double-click)",
                   command=self._select).pack(side="left")
        ttk.Button(btns, text="Toggle favorite (space)",
                   command=self._toggle_fav).pack(side="left", padx=8)
        ttk.Button(btns, text="Add manual satellite\u2026",
                   command=self._add_manual_sat).pack(side="left", padx=8)
        self.info = tk.StringVar(value="")
        ttk.Label(btns, textvariable=self.info, style="Muted.TLabel").pack(
            side="left", padx=12)

    def _add_manual_sat(self):
        from ..dialogs import FormDialog, Field
        from ...engine.satdb import make_manual_sat
        import datetime as _dt

        def parse_epoch(s):
            d = _dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            return d.replace(tzinfo=_dt.timezone.utc).timestamp()

        now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        fields = [
            Field("name", "Name", "", "e.g. MYSAT"),
            Field("norad", "NORAD ID", "", "catalog number", int),
            Field("epoch", "Epoch (UTC)", now,
                  "YYYY-MM-DD HH:MM:SS", parse_epoch),
            Field("incl", "Inclination", "", "degrees", float),
            Field("raan", "RAAN", "", "deg (right ascension of node)", float),
            Field("ecc", "Eccentricity", "", "e.g. 0.0006190", float),
            Field("argp", "Arg of perigee", "", "degrees", float),
            Field("ma", "Mean anomaly", "", "degrees", float),
            Field("mm", "Mean motion", "", "rev/day", float),
            Field("bstar", "BSTAR", "0", "drag; 0 if unknown", float,
                  required=False),
        ]
        res = FormDialog(self.frame, "Add manual satellite", fields,
                         intro="Enter GP mean elements. The satellite is stored "
                               "with the downloaded ones and persists across GP "
                               "refreshes.").show()
        if not res:
            return
        entry = make_manual_sat(
            res["name"], res["norad"], res["epoch"], res["incl"], res["raan"],
            res["ecc"], res["argp"], res["ma"], res["mm"], res["bstar"])
        self.store.add_manual_sat(entry)
        self.store.save_config()
        self._reload()
        self.info.set("Added manual satellite %s (NORAD %d)." %
                      (entry.name, entry.norad))

    def _reload(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        flt = self.filter.get().strip().lower()
        self._rows = []
        for s in self.store.db.sats:
            if self.favonly.get() and s.norad not in self.store.favorites:
                continue
            if flt and flt not in s.name.lower() and flt not in str(s.norad):
                continue
            star = "\u2605" if s.norad in self.store.favorites else ""
            sel = " \u25c0" if s.norad == self.store.selected_norad else ""
            self.tree.insert("", "end", values=(
                star, s.name + sel, s.norad, "%.1f min" % s.period_min,
                "%.1f\u00b0" % s.incl, "%.0f km" % s.apogee_km,
                "yes" if s.transponders else ""))
            self._rows.append(s)
        self.info.set("%d satellites" % len(self._rows))

    def _current(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self._rows):
            return self._rows[idx]
        return None

    def _select(self, _evt=None):
        s = self._current()
        if s:
            self.store.select(s.norad)
            self.store.ensure_transponders(s, online=True)
            self.store.save_config()
            self._reload()
            self.app.set_status("Selected %s" % s.name)

    def _toggle_fav(self, _evt=None):
        s = self._current()
        if s:
            self.store.toggle_fav(s.norad)
            self._reload()

    # ---- by type (grouped by transponder kind) ----
    def _build_bytype(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=4)
        ttk.Label(bar, text="Show:", style="TLabel").pack(side="left")
        self._bt_cat = tk.StringVar(value="(all)")
        self._bt_combo = ttk.Combobox(
            bar, textvariable=self._bt_cat, state="readonly", width=24,
            values=("(all)",) + CATEGORIES)
        self._bt_combo.pack(side="left", padx=6)
        self._bt_combo.bind("<<ComboboxSelected>>",
                            lambda _e: self._reload_bytype())
        self._bt_sort = tk.StringVar(value="name")
        ttk.Label(bar, text="  Sort:", style="TLabel").pack(side="left")
        for label, v in (("Name", "name"), ("NORAD", "norad"),
                         ("Period", "period")):
            ttk.Radiobutton(bar, text=label, value=v, variable=self._bt_sort,
                            command=self._reload_bytype).pack(side="left")
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._export_bytype).pack(side="right", padx=2)

        cols = ("norad", "period", "incl", "downlink", "tp")
        heads = ("NORAD", "Period", "Incl", "Downlink", "Transponder(s)")
        treewrap, self._bt_tree = make_scrolled_tree(
            parent, cols, show="tree headings", height=18)
        self._bt_tree.heading("#0", text="Satellite / group")
        self._bt_tree.column("#0", width=240, anchor="w")
        widths = {"norad": 80, "period": 90, "incl": 70, "downlink": 110,
                  "tp": 200}
        for c, h in zip(cols, heads):
            self._bt_tree.heading(c, text=h)
            self._bt_tree.column(c, width=widths[c],
                                 anchor="w" if c == "tp" else "center")
        treewrap.pack(fill="both", expand=True, padx=4, pady=10)
        self._bt_tree.bind("<Double-Button-1>", self._select_bytype)

        btns = ttk.Frame(parent, style="TFrame")
        btns.pack(fill="x", padx=4, pady=(0, 8))
        ttk.Button(btns, text="Track this satellite (double-click)",
                   command=self._select_bytype).pack(side="left")
        self._bt_info = tk.StringVar(value="")
        ttk.Label(btns, textvariable=self._bt_info,
                  style="Muted.TLabel").pack(side="left", padx=12)
        self._bt_rows = {}        # tree-item id -> SatEntry

    def _bt_grouped(self):
        """Return {category: [sat, ...]} for the catalog, transponders ensured,
        each list sorted by the chosen key."""
        groups = {c: [] for c in CATEGORIES}
        for s in self.store.db.sats:
            self.store.ensure_transponders(s)
            groups[satellite_category(s)].append(s)
        key = self._bt_sort.get()
        if key == "norad":
            sk = lambda s: s.norad
        elif key == "period":
            sk = lambda s: s.period_min
        else:
            sk = lambda s: s.name.lower()
        for c in groups:
            groups[c].sort(key=sk)
        return groups

    def _reload_bytype(self):
        for i in self._bt_tree.get_children():
            self._bt_tree.delete(i)
        self._bt_rows = {}
        groups = self._bt_grouped()
        want = self._bt_cat.get()
        total = 0
        for cat in CATEGORIES:
            sats = groups.get(cat, [])
            if want != "(all)" and want != cat:
                continue
            if not sats:
                continue
            parent = self._bt_tree.insert(
                "", "end", text="%s  (%d)" % (cat, len(sats)),
                open=(want != "(all)" or len(sats) <= 40),
                values=("", "", "", "", ""))
            for s in sats:
                dl = ""
                tplabel = ""
                if s.transponders:
                    c0 = s.transponders[0]
                    dlhz = c0.downlink_center()
                    dl = "%.3f MHz" % (dlhz / 1e6) if dlhz else ""
                    tplabel = ", ".join(t.kind() for t in s.transponders[:3])
                    if len(s.transponders) > 3:
                        tplabel += ", \u2026"
                iid = self._bt_tree.insert(
                    parent, "end", text=s.name,
                    values=(s.norad, "%.1f min" % s.period_min,
                            "%.1f\u00b0" % s.incl, dl, tplabel))
                self._bt_rows[iid] = s
                total += 1
        self._bt_info.set("%d satellites%s. Transponder data is from SatNOGS; "
                          "use \u201cUpdate Transponders\u201d for the full "
                          "database." % (
                              total, "" if want == "(all)"
                              else " in %s" % want))

    def _select_bytype(self, _evt=None):
        sel = self._bt_tree.selection()
        if not sel:
            return
        s = self._bt_rows.get(sel[0])
        if not s:
            return                # a category header row, not a satellite
        self.store.select(s.norad)
        self.store.ensure_transponders(s, online=True)
        self.store.save_config()
        self.app.set_status("Selected %s" % s.name)
        self._reload()

    def _export_bytype(self):
        groups = self._bt_grouped()
        want = self._bt_cat.get()
        headers = ["category", "name", "norad", "period_min", "incl_deg",
                   "downlink_mhz", "transponders"]
        rows = []
        for cat in CATEGORIES:
            if want != "(all)" and want != cat:
                continue
            for s in groups.get(cat, []):
                dl = ""
                tplabel = ""
                if s.transponders:
                    dlhz = s.transponders[0].downlink_center()
                    dl = round(dlhz / 1e6, 3) if dlhz else ""
                    tplabel = "; ".join(t.kind() for t in s.transponders)
                rows.append([cat, s.name, s.norad, round(s.period_min, 1),
                             round(s.incl, 1), dl, tplabel])
        if not rows:
            return
        self.save_text_dialog(
            EX.rows_to_csv(headers, rows), "satellites_by_type.csv",
            title="Export satellites by type", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    # ---- who's up now ----
    def _build_whosup(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=4)
        ttk.Label(bar, text="Min elevation:", style="TLabel").pack(side="left")
        self._up_minel = tk.IntVar(value=0)
        for v in (0, 5, 10, 20):
            ttk.Radiobutton(bar, text="%d\u00b0" % v, value=v,
                            variable=self._up_minel,
                            command=self._scan_up).pack(side="left")
        ttk.Button(bar, text="Rescan", command=self._scan_up).pack(
            side="left", padx=8)
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._export_up).pack(side="right", padx=2)
        self._up_info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._up_info, style="Muted.TLabel").pack(
            side="left", padx=12)

        cols = ("name", "el", "az", "rng", "sub", "alt", "sun")
        heads = ("Satellite", "El", "Az", "Range km", "Sub-point",
                 "Alt km", "Sun")
        treewrap, self._up_tree = make_scrolled_tree(
            parent, cols, show="headings", height=18)
        widths = {"name": 160, "el": 70, "az": 70, "rng": 100, "sub": 140,
                  "alt": 80, "sun": 50}
        for c, h in zip(cols, heads):
            self._up_tree.heading(c, text=h)
            self._up_tree.column(c, width=widths[c],
                                 anchor="w" if c == "name" else "center")
        treewrap.pack(fill="both", expand=True, padx=4, pady=10)
        self._up_tree.bind("<Double-Button-1>", self._select_up)

        btns = ttk.Frame(parent, style="TFrame")
        btns.pack(fill="x", padx=4, pady=(0, 8))
        ttk.Button(btns, text="Track this satellite (double-click)",
                   command=self._select_up).pack(side="left")
        ttk.Label(btns, text="Scans the whole catalog for satellites above "
                  "your horizon right now.", style="Muted.TLabel").pack(
            side="left", padx=12)
        self._up_rows = []

    def _scan_up(self):
        for i in self._up_tree.get_children():
            self._up_tree.delete(i)
        up = whos_up(self.store.obs, self.store.db.sats, now_unix(),
                     min_el=float(self._up_minel.get()))
        self._up_rows = up
        for d in up:
            self._up_tree.insert("", "end", values=(
                d["name"], "%.1f\u00b0" % d["el"], "%.0f\u00b0" % d["az"],
                "%.0f" % d["range_km"],
                "%.1f, %.1f" % (d["sub_lat"], d["sub_lon"]),
                "%.0f" % d["alt_km"],
                "\u2600" if d["sunlit"] else "\u263d"))
        self._up_info.set("%d of %d satellites above %d\u00b0 at %s UTC"
                          % (len(up), len(self.store.db.sats),
                             self._up_minel.get(), fmt_utc(now_unix(),
                                                           "%H:%M:%S")))

    def _select_up(self, _evt=None):
        sel = self._up_tree.selection()
        if not sel:
            return
        idx = self._up_tree.index(sel[0])
        if not (0 <= idx < len(self._up_rows)):
            return
        norad = self._up_rows[idx]["norad"]
        s = self.store.db.get(norad)
        if s:
            self.store.select(norad)
            self.store.ensure_transponders(s, online=True)
            self.store.save_config()
            self.app.set_status("Selected %s" % s.name)
            self._reload()

    def _export_up(self):
        if not self._up_rows:
            return
        headers = ["name", "norad", "el_deg", "az_deg", "range_km",
                   "sub_lat", "sub_lon", "alt_km", "sunlit"]
        rows = [[d["name"], d["norad"], round(d["el"], 1), round(d["az"], 0),
                 round(d["range_km"], 0), round(d["sub_lat"], 2),
                 round(d["sub_lon"], 2), round(d["alt_km"], 0),
                 "yes" if d["sunlit"] else "no"] for d in self._up_rows]
        self.save_text_dialog(
            EX.rows_to_csv(headers, rows), "whos_up.csv",
            title="Export who's-up list", ext=".csv",
            filetypes=[("CSV", "*.csv")])
