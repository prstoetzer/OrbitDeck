"""mutual.py - mutual (co-visibility) windows with a DX station."""

import tkinter as tk
from tkinter import ttk

from . import (Screen, COL_TEXT, COL_MUTED, COL_ACCENT, FONT_MONO,
               fmt_hms, fmt_utc, now_unix)
from ...engine import Observer, grid_to_latlon


class MutualScreen(Screen):
    def build(self):
        self.sat_header("Mutual Windows \u2014 co-visibility with a DX station")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(bar, text="DX grid or lat,lon:", style="TLabel").pack(side="left")
        self.dx = tk.StringVar(value="IO91")
        ttk.Entry(bar, textvariable=self.dx, width=18).pack(side="left", padx=6)
        ttk.Label(bar, text="Min el:", style="TLabel").pack(side="left", padx=(12, 2))
        self.minel = tk.IntVar(value=0)
        for v in (0, 5, 10):
            ttk.Radiobutton(bar, text="%d\u00b0" % v, value=v, variable=self.minel,
                            command=self._reload).pack(side="left")
        ttk.Button(bar, text="Compute", command=self._reload).pack(side="left",
                                                                    padx=10)
        cols = ("start", "end", "dur", "myel", "dxel")
        heads = ("Start (UTC)", "End", "Duration", "My max el", "DX max el")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings",
                                 height=16)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=150 if c == "start" else 110,
                             anchor="center")
        self.tree.pack(fill="both", expand=True, padx=16, pady=10)
        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info, style="Muted.TLabel").pack(
            anchor="w", padx=16, pady=(0, 8))

    def on_show(self):
        pass

    def _parse_dx(self):
        txt = self.dx.get().strip()
        if "," in txt:
            try:
                a, b = txt.split(",")
                return float(a), float(b)
            except Exception:
                return None
        ll = grid_to_latlon(txt)
        return ll

    def _reload(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        s = self.sat()
        if not s:
            self.info.set("No satellite selected.")
            return
        ll = self._parse_dx()
        if not ll:
            self.info.set("Could not parse DX location. Use a grid (IO91) or "
                          "lat,lon.")
            return
        dx = Observer(lat=ll[0], lon=ll[1], alt_m=0, valid=True)
        t = now_unix()
        wins = self.pred().mutual_windows(t, dx, float(self.minel.get()), 30,
                                          horizon_days=10)
        for w in wins:
            self.tree.insert("", "end", values=(
                fmt_utc(w.start, "%m-%d %H:%M:%S"),
                fmt_utc(w.end, "%H:%M:%S"),
                fmt_hms(w.end - w.start),
                "%.0f\u00b0" % w.my_max_el,
                "%.0f\u00b0" % w.dx_max_el))
        self.info.set("%s: %d mutual windows over 10 days with DX at %.2f,%.2f."
                      % (s.name, len(wins), ll[0], ll[1]))
