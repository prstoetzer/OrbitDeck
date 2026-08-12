"""references.py (screen) - static reference-table browser.

A simple two-pane browser (table list on the left, rows on the right) over the
static reference data in engine.refdata: CTCSS tones, Q-codes, CQ/ITU zones and
an ASCII table. Ported from CardSat's reference browsers.
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT, COL_ACCENT2,
               make_scrolled_tree)
from ...engine import refdata as RD


class ReferencesScreen(Screen):
    def build(self):
        self.header("References \u2014 tables & lookups")
        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=(2, 10))

        # 200 px clipped the longer table names ("Phonetic alphabet",
        # "Satellite history") mid-word.
        left = tk.Frame(body, bg=COL_PANEL, width=290)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)
        ttk.Button(left, text="Report\u2026",
                   command=self._report).pack(side="right", padx=4)
        tk.Label(left, text="TABLES", bg=COL_PANEL, fg=COL_ACCENT,
                 font=("DejaVu Sans", 9, "bold"), anchor="w").pack(
            fill="x", padx=8, pady=(6, 4))
        self._btns = {}
        for i, (name, _desc, _fn) in enumerate(RD.TABLES):
            b = tk.Label(left, text="  " + name, bg=COL_PANEL, fg=COL_TEXT,
                         font=("DejaVu Sans", 11), anchor="w", cursor="hand2")
            b.pack(fill="x", padx=6, pady=1)
            b.bind("<Button-1>", lambda _e, k=i: self._select(k))
            self._btns[i] = b

        right = ttk.Frame(body, style="TFrame")
        right.pack(side="left", fill="both", expand=True)
        self._desc = tk.Label(right, text="", bg="#0d1117", fg=COL_MUTED,
                              font=("DejaVu Sans", 10), anchor="w")
        self._desc.pack(fill="x", pady=(0, 6))
        cols = ("a", "b", "c")
        wrap, self.tree = make_scrolled_tree(right, cols, show="headings",
                                             height=16)
        for c, w in (("a", 90), ("b", 200), ("c", 320)):
            self.tree.column(c, width=w, anchor="w")
        wrap.pack(fill="both", expand=True)
        self._select(0)

    def _select(self, idx):
        for i, b in self._btns.items():
            b.configure(fg=COL_ACCENT2 if i == idx else COL_TEXT)
        name, desc, fn = RD.TABLES[idx]
        self._desc.configure(text=desc)
        # column headers differ per table
        headers = {
            "CTCSS tones": ("#", "Tone", "Group"),
            "Q-codes": ("Code", "", "Meaning"),
            "CQ zones": ("Zones", "Region", ""),
            "ITU zones": ("Zones", "Region", ""),
            "ASCII table": ("Dec", "Char", "Hex"),
        }.get(name, ("", "", ""))
        for c, h in zip(("a", "b", "c"), headers):
            self.tree.heading(c, text=h)
        self.tree.delete(*self.tree.get_children())
        for rowvals in fn():
            self.tree.insert("", "end", values=rowvals)
