"""passes.py - upcoming passes for the selected satellite."""

import tkinter as tk
from tkinter import ttk

from . import (Screen, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT, FONT_MONO,
               fmt_hms, fmt_utc, now_unix, compass)


class PassesScreen(Screen):
    def build(self):
        self.header("Next Passes")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16)
        ttk.Label(bar, text="Min elevation:", style="TLabel").pack(side="left")
        self.minel = tk.IntVar(value=int(self.store.min_el))
        for v in (0, 5, 10, 20, 30):
            ttk.Radiobutton(bar, text="%d\u00b0" % v, value=v, variable=self.minel,
                            command=self._reload).pack(side="left", padx=2)

        cols = ("aos", "tca", "los", "dur", "maxel", "azaos", "azlos")
        heads = ("AOS (UTC)", "TCA", "LOS", "Dur", "Max El",
                 "AOS Az", "LOS Az")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings",
                                 height=18)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=130 if c in ("aos",) else 95,
                             anchor="center")
        self.tree.pack(fill="both", expand=True, padx=16, pady=10)
        self.tree.bind("<Double-Button-1>", self._open_detail)
        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info, style="Muted.TLabel").pack(
            anchor="w", padx=16, pady=(0, 8))

    def on_show(self):
        self.minel.set(int(self.store.min_el))
        self._reload()

    def _reload(self):
        self.store.min_el = float(self.minel.get())
        self.store.save_config()
        for i in self.tree.get_children():
            self.tree.delete(i)
        s = self.sat()
        if not s:
            self.info.set("No satellite selected.")
            return
        t = now_unix()
        passes = self.pred().predict_passes(t, self.store.min_el, 30,
                                            t + 7 * 86400)
        for p in passes:
            self.tree.insert("", "end", values=(
                fmt_utc(p.aos, "%m-%d %H:%M:%S"),
                fmt_utc(p.tca, "%H:%M:%S"),
                fmt_utc(p.los, "%H:%M:%S"),
                fmt_hms(p.los - p.aos),
                "%.1f\u00b0" % p.max_el,
                "%.0f\u00b0 %s" % (p.az_aos, compass(p.az_aos)),
                "%.0f\u00b0 %s" % (p.az_los, compass(p.az_los)),
            ), tags=(str(p.aos),))
        self.info.set("%s: %d passes over 7 days (min %.0f\u00b0). "
                      "Double-click a pass for the polar detail." %
                      (s.name, len(passes), self.store.min_el))
        self._passes = passes

    def _open_detail(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self._passes):
            self.app._screen_cache.pop("passdetail", None)
            self.app.show("passdetail")
            scr = self.app.current
            scr.set_pass(self._passes[idx])
