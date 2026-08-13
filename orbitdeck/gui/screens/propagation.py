"""propagation.py (screen) - HF / 6 m operating outlook.

Space Wx gives the indices and the MUF screen gives path MUF to world regions.
This answers the question before either: is anything open right now, is 6 m
worth watching, and will the low bands be absorbed.
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, COL_ACCENT2, COL_MUTED, COL_TEXT, COL_WARN,
               now_unix, make_scrolled_tree)
from ...engine import propagation as PROP

SEV_COLOR = {0: COL_MUTED, 1: COL_TEXT, 2: COL_ACCENT2, 3: COL_WARN}
STATE_COLOR = {"open": COL_ACCENT2, "fair": COL_TEXT, "weak": COL_WARN,
                "shut": COL_MUTED, "unknown": COL_MUTED}


class PropagationScreen(Screen):
    def build(self):
        self.header("HF / 6 m propagation outlook")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        ttk.Button(bar, text="Refresh",
                   command=self._reload).pack(side="left")
        self.summary = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.summary, style="Muted.TLabel",
                  wraplength=760).pack(side="left", padx=10)

        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self.kv = KVPanel(body, label_width=18)
        self.kv.pack(side="left", fill="y", padx=(0, 12))

        cols = ("band", "day", "night")
        wrap, self.tree = make_scrolled_tree(body, cols, show="headings",
                                             height=10)
        for c, h, w in zip(cols, ("Band", "By day", "At night"),
                           (120, 120, 120)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w,
                             anchor="w" if c == "band" else "center")
        wrap.pack(side="left", fill="both", expand=True)
        for name, color in STATE_COLOR.items():
            self.tree.tag_configure(name, foreground=color)

        note = ("Rules of thumb driven by solar flux and Kp, not a path "
                "calculation \u2014 use the MUF screen for a specific path. "
                "Sporadic-E and meteor scatter are seasonal, so those lines "
                "are about the calendar rather than today's indices.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))
        self._res = None

    def on_show(self):
        self._reload()

    def _cache(self):
        try:
            return self.store.load_spacewx_cache() or {}
        except Exception:
            return {}

    def _reload(self):
        res = PROP.outlook(self._cache(), now_unix())
        self._res = res
        self.summary.set(PROP.summary_line(res))
        self.kv.begin()
        if res["flux"] is not None:
            self.kv.row("Solar flux", "%.0f sfu" % res["flux"])
        if res["kp"] is not None:
            self.kv.row("Kp", "%.1f" % res["kp"])
        if res["muf_day"]:
            self.kv.row("MUF (day)", "%.0f MHz" % res["muf_day"])
            self.kv.row("MUF (night)", "%.0f MHz" % res["muf_night"])
        for label, key in (("Geomagnetic", "geomagnetic"),
                           ("Aurora (VHF)", "aurora"),
                           ("Absorption", "absorption"),
                           ("Meteor scatter", "meteor"),
                           ("Sporadic E", "sporadic_e")):
            text, sev = res[key]
            self.kv.row(label, text, SEV_COLOR.get(sev, COL_TEXT))
        self.kv.end()

        self.tree.delete(*self.tree.get_children())
        night = {b: s for b, s, _sv in res["bands_night"]}
        for band, state, _sev in res["bands_day"]:
            self.tree.insert("", "end", tags=(state,),
                             values=(band, state, night.get(band, "?")))

    def _report(self):
        from ..reports import save_report_dialog
        res = self._res or PROP.outlook(self._cache(), now_unix())
        kv = []
        if res["flux"] is not None:
            kv.append(("Solar flux", "%.0f sfu" % res["flux"]))
        if res["kp"] is not None:
            kv.append(("Kp", "%.1f" % res["kp"]))
        if res["muf_day"]:
            kv.append(("MUF (day)", "%.0f MHz" % res["muf_day"]))
            kv.append(("MUF (night)", "%.0f MHz" % res["muf_night"]))
        for label, key in (("Geomagnetic", "geomagnetic"),
                           ("Aurora (VHF)", "aurora"),
                           ("Absorption", "absorption"),
                           ("Meteor scatter", "meteor"),
                           ("Sporadic E", "sporadic_e")):
            kv.append((label, res[key][0]))
        night = {b: s for b, s, _sv in res["bands_night"]}
        rows = [[b, s, night.get(b, "?")] for b, s, _sv in res["bands_day"]]
        save_report_dialog(
            self, "propagation",
            title="HF / 6 m propagation outlook",
            subtitle=PROP.summary_line(res),
            sections=[("Conditions", "kv", kv),
                      ("Band outlook", "table",
                       (["Band", "By day", "At night"], rows)),
                      ("About these figures", "text",
                       "Rules of thumb driven by solar flux and Kp, not a "
                       "path calculation. Sporadic-E and meteor scatter are "
                       "seasonal.")])
