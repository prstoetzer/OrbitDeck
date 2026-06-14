"""dialogs.py - small modal form dialogs for manual data entry.

FormDialog presents a set of labelled fields in one modal window (friendlier on
the desktop than CardSat's one-field-at-a-time prompts) and returns a dict of the
entered values, or None if cancelled. Fields can carry a help hint and a parser
so values come back typed and validated.
"""

import tkinter as tk
from tkinter import ttk

from .screens import (COL_BG, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
                      COL_WARN, COL_GRID)


class Field:
    def __init__(self, key, label, default="", hint="", parser=None,
                 required=True):
        self.key = key
        self.label = label
        self.default = default
        self.hint = hint
        self.parser = parser          # callable(str) -> value, or None for str
        self.required = required


class FormDialog:
    def __init__(self, parent, title, fields, intro=""):
        self.fields = fields
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.configure(bg=COL_BG)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.resizable(False, False)

        if intro:
            tk.Label(self.win, text=intro, bg=COL_BG, fg=COL_MUTED,
                     font=("DejaVu Sans", 9), wraplength=420,
                     justify="left").grid(row=0, column=0, columnspan=2,
                                          sticky="w", padx=14, pady=(12, 6))
        self._vars = {}
        r = 1
        for f in fields:
            tk.Label(self.win, text=f.label, bg=COL_BG, fg=COL_TEXT,
                     font=("DejaVu Sans", 10), anchor="e").grid(
                row=r, column=0, sticky="e", padx=(14, 6), pady=3)
            var = tk.StringVar(value=str(f.default))
            self._vars[f.key] = var
            ent = ttk.Entry(self.win, textvariable=var, width=30)
            ent.grid(row=r, column=1, sticky="w", padx=(0, 14), pady=3)
            if r == 1:
                ent.focus_set()
            if f.hint:
                tk.Label(self.win, text=f.hint, bg=COL_BG, fg=COL_MUTED,
                         font=("DejaVu Sans", 8), anchor="w").grid(
                    row=r + 1, column=1, sticky="w", padx=(0, 14))
                r += 1
            r += 1

        self.err = tk.Label(self.win, text="", bg=COL_BG, fg=COL_WARN,
                            font=("DejaVu Sans", 9), wraplength=420,
                            justify="left")
        self.err.grid(row=r, column=0, columnspan=2, sticky="w", padx=14)
        r += 1

        btns = tk.Frame(self.win, bg=COL_BG)
        btns.grid(row=r, column=0, columnspan=2, sticky="e", padx=14,
                  pady=(8, 12))
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(
            side="right", padx=4)
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right")
        self.win.bind("<Return>", lambda _e: self._ok())
        self.win.bind("<Escape>", lambda _e: self._cancel())

    def _ok(self):
        out = {}
        for f in self.fields:
            raw = self._vars[f.key].get().strip()
            if not raw and f.required and f.default == "":
                self.err.configure(text="'%s' is required." % f.label)
                return
            if f.parser is not None:
                try:
                    out[f.key] = f.parser(raw) if raw else f.parser(
                        str(f.default))
                except Exception:
                    self.err.configure(
                        text="'%s' is not valid (%s)." % (f.label,
                                                          f.hint or "check format"))
                    return
            else:
                out[f.key] = raw
        self.result = out
        self.win.destroy()

    def _cancel(self):
        self.result = None
        self.win.destroy()

    def show(self):
        self.win.wait_window()
        return self.result
