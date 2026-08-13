"""tools.py (screen) - the Tools hub: bench calculators as live-recalc forms.

Mirrors CardSat's Tools menu: a categorised list of calculators on the left, and
a live-updating form on the right (input fields + a result readout that
recomputes as you type). Every calculator is a pure function in
orbitdeck.engine.toolcalc; this screen is only the form/plumbing.

Radio- and rotator-control tools are intentionally not included (out of scope);
these are the pure computational tools.
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, COL_BG, COL_PANEL, COL_TEXT, COL_MUTED,
               COL_ACCENT, COL_ACCENT2, COL_WARN, COL_GRID,
               make_vscroll_frame)
from .. import tools_registry as REG


class ToolsScreen(Screen):
    def build(self):
        self.header("Tools \u2014 bench & satellite calculators")
        sub = ttk.Label(
            self.frame,
            text="Antenna, feedline, RF, electronics, terrestrial and orbital "
                 "calculators. Values update as you type.",
            style="Muted.TLabel")
        sub.pack(side="top", anchor="w", padx=16, pady=(0, 6))

        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # ---- left: categorised tool list ----
        # 250 px could not hold this list's own longest entries
        # ("Microstrip/stripline Z0"), so they were clipped mid-word.
        left = tk.Frame(body, bg=COL_PANEL, width=330)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)
        tk.Label(left, text="TOOLS", bg=COL_PANEL, fg=COL_ACCENT,
                 font=("DejaVu Sans", 9, "bold"), anchor="w").pack(
            fill="x", padx=8, pady=(6, 2))

        holder, inner = make_vscroll_frame(left)
        holder.pack(fill="both", expand=True)
        self._list_inner = inner
        self._buttons = {}
        for cat, tools in REG.CATEGORIES:
            tk.Label(inner, text=cat, bg=COL_PANEL, fg=COL_MUTED,
                     font=("DejaVu Sans", 8, "bold"), anchor="w").pack(
                fill="x", padx=8, pady=(8, 1))
            for key in tools:
                spec = REG.TOOLS[key]
                b = tk.Label(inner, text="  " + spec["name"], bg=COL_PANEL,
                             fg=COL_TEXT, font=("DejaVu Sans", 10), anchor="w",
                             cursor="hand2")
                b.pack(fill="x", padx=6)
                b.bind("<Button-1>", lambda _e, k=key: self._select(k))
                self._buttons[key] = b

        # ---- right: form + results ----
        right = ttk.Frame(body, style="TFrame")
        right.pack(side="left", fill="both", expand=True)

        self._title = tk.Label(right, text="", bg=COL_BG, fg=COL_ACCENT2,
                               font=("DejaVu Sans", 13, "bold"), anchor="w")
        self._title.pack(fill="x", pady=(0, 2))
        self._desc = tk.Label(right, text="", bg=COL_BG, fg=COL_MUTED,
                              font=("DejaVu Sans", 9), anchor="w",
                              wraplength=560, justify="left")
        self._desc.pack(fill="x", pady=(0, 8))

        self._form = tk.Frame(right, bg=COL_BG)
        self._form.pack(fill="x", pady=(0, 8))

        tk.Frame(right, bg=COL_GRID, height=1).pack(fill="x", pady=4)
        tk.Label(right, text="RESULT", bg=COL_BG, fg=COL_ACCENT,
                 font=("DejaVu Sans", 9, "bold"), anchor="w").pack(fill="x")
        self.kv = KVPanel(right, label_width=16)
        self.kv.pack(fill="both", expand=True, pady=(4, 0))

        self._fields = []          # list of dicts describing active inputs
        self._active = None
        # open the first tool by default
        first = REG.CATEGORIES[0][1][0]
        self._select(first)

    # ------------------------------------------------------------------
    def _select(self, key):
        # highlight the chosen tool in the list
        for k, b in self._buttons.items():
            b.configure(fg=COL_ACCENT2 if k == key else COL_TEXT,
                        bg=COL_GRID if k == key else COL_PANEL)
        self._active = key
        spec = REG.TOOLS[key]
        self._title.configure(text=spec["name"])
        self._desc.configure(text=spec.get("desc", ""))
        self._build_form(spec)
        self._recompute()

    def _build_form(self, spec):
        for w in self._form.winfo_children():
            w.destroy()
        self._fields = []
        for i, fld in enumerate(spec["fields"]):
            rowf = tk.Frame(self._form, bg=COL_BG)
            rowf.pack(fill="x", pady=2)
            tk.Label(rowf, text=fld["label"], bg=COL_BG, fg=COL_TEXT,
                     font=("DejaVu Sans", 10), width=18, anchor="w").pack(
                side="left")
            if fld.get("choices"):
                var = tk.StringVar(value=fld["choices"][fld.get("default", 0)])
                combo = ttk.Combobox(rowf, textvariable=var, state="readonly",
                                     values=fld["choices"], width=22)
                combo.pack(side="left")
                combo.bind("<<ComboboxSelected>>",
                           lambda _e: self._recompute())
                self._fields.append({"kind": "choice", "var": var,
                                     "choices": fld["choices"]})
            else:
                var = tk.StringVar(value=str(fld["default"]))
                is_text = bool(fld.get("text"))
                ent = tk.Entry(rowf, textvariable=var, width=14,
                               bg=COL_PANEL, fg=COL_TEXT,
                               insertbackground=COL_TEXT,
                               font=("DejaVu Sans Mono", 10),
                               relief="flat", highlightthickness=1,
                               highlightbackground=COL_GRID,
                               highlightcolor=COL_ACCENT)
                ent.pack(side="left")
                var.trace_add("write", lambda *_a: self._recompute())
                unit = fld.get("unit", "")
                if unit:
                    tk.Label(rowf, text=unit, bg=COL_BG, fg=COL_MUTED,
                             font=("DejaVu Sans", 9)).pack(side="left",
                                                           padx=(6, 0))
                self._fields.append(
                    {"kind": "text" if is_text else "num", "var": var})

    def _recompute(self):
        spec = REG.TOOLS[self._active]
        args = []
        ok = True
        for fld, meta in zip(spec["fields"], self._fields):
            if meta["kind"] == "choice":
                args.append(meta["choices"].index(meta["var"].get()))
            elif meta["kind"] == "text":
                args.append(meta["var"].get())
            else:
                txt = meta["var"].get().strip()
                try:
                    args.append(float(txt))
                except ValueError:
                    ok = False
                    args.append(fld["default"])
        self.kv.begin()
        if not ok:
            self.kv.row("input", "enter numbers", COL_WARN)
        else:
            try:
                rows = spec["fn"](*args)
                for label, value, note in rows:
                    color = COL_TEXT
                    low = (value + " " + note).lower()
                    if any(w in low for w in ("in", "exceeds", "over",
                                              "too low", "error", "need")):
                        color = COL_WARN
                    if any(w in low for w in ("ok", "workable")):
                        color = COL_ACCENT2
                    self.kv.row(label, value + (
                        "   " + note if note else ""), color)
            except Exception as e:            # never let a bad input crash UI
                self.kv.row("error", str(e), COL_WARN)
        self.kv.end()
