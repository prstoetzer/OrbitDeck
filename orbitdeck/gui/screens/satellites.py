"""satellites.py - the catalog: list, select, favorite, fetch transponders."""

import tkinter as tk
from tkinter import ttk

from . import Screen, COL_TEXT, COL_MUTED, COL_ACCENT, FONT_MONO, now_unix


class SatellitesScreen(Screen):
    def build(self):
        self.header("Satellites")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
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
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings",
                                 height=18)
        widths = {"fav": 36, "name": 150, "norad": 80, "period": 90,
                  "incl": 80, "apo": 90, "tx": 60}
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c],
                             anchor="w" if c == "name" else "center")
        self.tree.pack(fill="both", expand=True, padx=16, pady=10)
        self.tree.bind("<Double-Button-1>", self._select)
        self.tree.bind("<space>", self._toggle_fav)

        btns = ttk.Frame(self.frame, style="TFrame")
        btns.pack(fill="x", padx=16, pady=(0, 8))
        ttk.Button(btns, text="Select (double-click)",
                   command=self._select).pack(side="left")
        ttk.Button(btns, text="Toggle favorite (space)",
                   command=self._toggle_fav).pack(side="left", padx=8)
        self.info = tk.StringVar(value="")
        ttk.Label(btns, textvariable=self.info, style="Muted.TLabel").pack(
            side="left", padx=12)

    def on_show(self):
        self._reload()

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
