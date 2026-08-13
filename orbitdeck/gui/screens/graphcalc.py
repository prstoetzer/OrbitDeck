"""graphcalc.py (screen) - the graphing calculator.

Plots one or more functions of x using the same safe expression evaluator the
scientific calculator uses (``orbitdeck.engine.calc``), so nothing here can
execute arbitrary code. Domain and range are settable; range auto-fits by
default. Ported from CardSat 0.9.75's SCR_GRAPH.
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_MUTED, COL_ACCENT, COL_ACCENT2, COL_WARN)
from ...engine import calc as C

TRACE_COLORS = [COL_ACCENT2, COL_ACCENT, COL_WARN, "#c678dd"]
SAMPLES = 800          # desktop: sample densely, no device pixel budget


def sample(expr, xmin, xmax, n=SAMPLES):
    """Evaluate ``expr`` over [xmin, xmax], returning (xs, ys).

    Points where the expression is undefined (division by zero, domain errors)
    become None so the plot breaks the line rather than drawing through them.
    """
    xs, ys = [], []
    if xmax <= xmin or n < 2:
        return xs, ys
    step = (xmax - xmin) / (n - 1)
    for i in range(n):
        x = xmin + i * step
        xs.append(x)
        try:
            v = C.evaluate_with(expr, {"x": x})
            ys.append(float(v) if abs(float(v)) < 1e12 else None)
        except Exception:
            ys.append(None)
    return xs, ys


class GraphCalcScreen(Screen):
    def build(self):
        self.header("Graphing calculator")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=(2, 4))
        ttk.Label(bar, text="y =", style="TLabel").pack(side="left")
        self.f1 = tk.StringVar(value="sin(x)")
        e1 = ttk.Entry(bar, textvariable=self.f1, width=24)
        e1.pack(side="left", padx=4)
        ttk.Label(bar, text="y =", style="TLabel").pack(side="left", padx=(8, 0))
        self.f2 = tk.StringVar(value="")
        e2 = ttk.Entry(bar, textvariable=self.f2, width=24)
        e2.pack(side="left", padx=4)
        for e in (e1, e2):
            e.bind("<Return>", lambda _ev: self._redraw())
        ttk.Button(bar, text="Plot", command=self._redraw).pack(side="left",
                                                                 padx=8)

        bar2 = ttk.Frame(self.frame, style="TFrame")
        bar2.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Label(bar2, text="x from", style="TLabel").pack(side="left")
        self.xmin = tk.StringVar(value="-6.283")
        ttk.Entry(bar2, textvariable=self.xmin, width=9).pack(side="left",
                                                              padx=3)
        ttk.Label(bar2, text="to", style="TLabel").pack(side="left")
        self.xmax = tk.StringVar(value="6.283")
        ttk.Entry(bar2, textvariable=self.xmax, width=9).pack(side="left",
                                                              padx=3)
        self.autoy = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar2, text="auto y", variable=self.autoy,
                        command=self._redraw).pack(side="left", padx=8)
        ttk.Label(bar2, text="y from", style="TLabel").pack(side="left")
        self.ymin = tk.StringVar(value="-2")
        ttk.Entry(bar2, textvariable=self.ymin, width=8).pack(side="left",
                                                              padx=3)
        ttk.Label(bar2, text="to", style="TLabel").pack(side="left")
        self.ymax = tk.StringVar(value="2")
        ttk.Entry(bar2, textvariable=self.ymax, width=8).pack(side="left",
                                                              padx=3)
        self.info = tk.StringVar(value="")
        ttk.Label(bar2, textvariable=self.info, style="Muted.TLabel").pack(
            side="left", padx=10)

        self.panel = MplPanel(self.frame, figsize=(8, 4.8))
        self.panel.widget.pack(fill="both", expand=True, padx=10, pady=6)
        note = ("Use x as the variable; the same functions as the scientific "
                "calculator are available (sin, cos, log, sqrt, exp, deg/rad, "
                "pi, e). Undefined points break the trace.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))

    def on_show(self):
        self._redraw()

    def _redraw(self):
        self.panel.fig.clf()
        ax = self.panel.fig.add_subplot(111)
        self.panel.ax = ax
        ax.set_facecolor("#0d1117")
        for s in ax.spines.values():
            s.set_color(COL_MUTED)
        ax.tick_params(colors=COL_MUTED, labelsize=8)
        ax.grid(True, color="#20304a", lw=0.5)
        try:
            xmin = float(self.xmin.get())
            xmax = float(self.xmax.get())
        except ValueError:
            self.info.set("x range must be numeric.")
            self.panel.canvas.draw_idle()
            return
        if xmax <= xmin:
            self.info.set("x max must exceed x min.")
            self.panel.canvas.draw_idle()
            return
        ax.axhline(0, color=COL_MUTED, lw=0.8)
        ax.axvline(0, color=COL_MUTED, lw=0.8)
        plotted, errs = 0, []
        for i, var in enumerate((self.f1, self.f2)):
            expr = var.get().strip()
            if not expr:
                continue
            xs, ys = sample(expr, xmin, xmax)
            if not any(y is not None for y in ys):
                errs.append(expr)
                continue
            ax.plot(xs, ys, "-", color=TRACE_COLORS[i % len(TRACE_COLORS)],
                    lw=1.3, label="y = " + expr)
            plotted += 1
        if not self.autoy.get():
            try:
                ax.set_ylim(float(self.ymin.get()), float(self.ymax.get()))
            except ValueError:
                pass
        ax.set_xlim(xmin, xmax)
        if plotted:
            leg = ax.legend(loc="best", fontsize=8, facecolor="#161b22",
                            edgecolor="#30363d")
            for t in leg.get_texts():
                t.set_color(COL_MUTED)
        self.info.set("%d trace(s)%s" % (
            plotted, ("; couldn't evaluate: " + ", ".join(errs)) if errs else ""))
        self.panel.fig.tight_layout()
        self.panel.canvas.draw_idle()
