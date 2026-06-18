"""dialogs.py - small modal form dialogs for manual data entry.

FormDialog presents a set of labelled fields in one modal window (friendlier on
the desktop than CardSat's one-field-at-a-time prompts) and returns a dict of the
entered values, or None if cancelled. Fields can carry a help hint and a parser
so values come back typed and validated.
"""

import tkinter as tk
from tkinter import ttk

from .screens import (COL_BG, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
                      COL_WARN)


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


class OscarlocatorOptionsDialog:
    """A single modal dialog gathering all OSCARLOCATOR print options (base-map
    style, whether the range circle is drawn on the QTH map, and reduced-text
    transparencies), replacing the old chain of yes/no questions. Returns a dict
    {projection, footprint_on_qth, reduced_text} or None if cancelled."""

    def __init__(self, parent, sat_name=""):
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title("OSCARLOCATOR options")
        self.win.configure(bg=COL_BG)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.resizable(False, False)

        pad = {"padx": 14}
        row = 0
        tk.Label(self.win,
                 text="OSCARLOCATOR print options" + (
                     " \u2014 %s" % sat_name if sat_name else ""),
                 bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", 12, "bold")).grid(
            row=row, column=0, sticky="w", pady=(12, 2), **pad)
        row += 1

        # --- base-map style ---
        tk.Label(self.win, text="Base map", bg=COL_BG, fg=COL_ACCENT,
                 font=("DejaVu Sans", 10, "bold")).grid(
            row=row, column=0, sticky="w", pady=(8, 0), **pad)
        row += 1
        self._proj = tk.StringVar(value="polar-auto")
        for val, label in (
                ("polar-auto", "Polar (generic \u2014 works for any QTH via "
                               "the equator-crossing list)"),
                ("qth", "QTH-centred (personalised to your station: "
                        "azimuth/range from your location)")):
            tk.Radiobutton(
                self.win, text=label, value=val, variable=self._proj,
                bg=COL_BG, fg=COL_TEXT, selectcolor=COL_PANEL,
                activebackground=COL_BG, activeforeground=COL_TEXT,
                font=("DejaVu Sans", 9), anchor="w", highlightthickness=0,
                wraplength=440, justify="left").grid(
                row=row, column=0, sticky="w", padx=(28, 14))
            row += 1

        # --- range circle placement ---
        tk.Label(self.win, text="Range circle", bg=COL_BG, fg=COL_ACCENT,
                 font=("DejaVu Sans", 10, "bold")).grid(
            row=row, column=0, sticky="w", pady=(8, 0), **pad)
        row += 1
        self._fp = tk.BooleanVar(value=False)
        for val, label in (
                (False, "Separate transparency (3-page set: map, range circle, "
                        "path arc)"),
                (True, "Drawn on the base map at my QTH (2-page set: map + "
                       "range circle, path arc)")):
            tk.Radiobutton(
                self.win, text=label, value=val, variable=self._fp,
                bg=COL_BG, fg=COL_TEXT, selectcolor=COL_PANEL,
                activebackground=COL_BG, activeforeground=COL_TEXT,
                font=("DejaVu Sans", 9), anchor="w", highlightthickness=0,
                wraplength=440, justify="left").grid(
                row=row, column=0, sticky="w", padx=(28, 14))
            row += 1

        # --- reduced-text option ---
        tk.Label(self.win, text="Style", bg=COL_BG, fg=COL_ACCENT,
                 font=("DejaVu Sans", 10, "bold")).grid(
            row=row, column=0, sticky="w", pady=(8, 0), **pad)
        row += 1
        self._reduced = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.win,
            text="Reduced-text transparencies (all instructions on the base "
                 "map; overlays kept clean for a reusable set)",
            variable=self._reduced, bg=COL_BG, fg=COL_TEXT,
            selectcolor=COL_PANEL, activebackground=COL_BG,
            activeforeground=COL_TEXT, font=("DejaVu Sans", 9), anchor="w",
            highlightthickness=0, wraplength=440, justify="left").grid(
            row=row, column=0, sticky="w", padx=(28, 14))
        row += 1

        btns = tk.Frame(self.win, bg=COL_BG)
        btns.grid(row=row, column=0, sticky="e", padx=14, pady=(14, 12))
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(
            side="right", padx=4)
        ttk.Button(btns, text="Generate\u2026", command=self._ok).pack(
            side="right")
        self.win.bind("<Return>", lambda _e: self._ok())
        self.win.bind("<Escape>", lambda _e: self._cancel())

    def _ok(self):
        self.result = {
            "projection": self._proj.get(),
            "footprint_on_qth": bool(self._fp.get()),
            "reduced_text": bool(self._reduced.get()),
        }
        self.win.destroy()

    def _cancel(self):
        self.result = None
        self.win.destroy()

    def show(self):
        self.win.wait_window()
        return self.result
