"""muf.py (screen) - HF MUF from your QTH to world regions.

Runs MINIMUF-3.5 from the station location to two dozen world regions and shows
the maximum usable frequency, the band that implies, and the path geometry.
Sunspot number comes from the Space Wx screen's solar data when available, and
is editable here.
"""

import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_ACCENT, COL_ACCENT2, COL_MUTED,
               COL_WARN, now_unix, make_scrolled_tree)
from ..mapdraw import draw_basemap
from ...engine import muf as MUF

QUALITY_TAGS = {"low": COL_WARN, "fair": COL_WARN, "good": COL_ACCENT2,
                "high": COL_ACCENT}


class MufScreen(Screen):
    def build(self):
        self.header("MUF \u2014 HF propagation to world regions")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(bar, text="Sunspot number:", style="TLabel").pack(side="left")
        self._ssn_src = ""
        self.ssn = tk.StringVar(value=str(self._default_ssn()))
        ent = ttk.Entry(bar, textvariable=self.ssn, width=7)
        ent.pack(side="left", padx=6)
        ent.bind("<Return>", lambda _e: self._compute())
        ttk.Button(bar, text="Print screen\u2026",

                   command=self._report).pack(side="right", padx=4)
        ttk.Button(bar, text="Compute",
                   command=self._compute).pack(side="left", padx=6)
        self.sortvar = tk.StringVar(value="region")
        ttk.Label(bar, text="Sort:", style="TLabel").pack(side="left",
                                                           padx=(12, 2))
        for label, val in (("Region", "region"), ("MUF", "muf"),
                           ("Distance", "dist")):
            ttk.Radiobutton(bar, text=label, value=val, variable=self.sortvar,
                            command=self._render).pack(side="left")
        ttk.Label(bar, text="DXCC:", style="TLabel").pack(side="left",
                                                           padx=(12, 2))
        self.dxq = tk.StringVar(value="")
        ent = ttk.Entry(bar, textvariable=self.dxq, width=10)
        ent.pack(side="left")
        ent.bind("<Return>", lambda _e: self._lookup_dxcc())
        ttk.Button(bar, text="Look up",
                   command=self._lookup_dxcc).pack(side="left", padx=4)
        ttk.Button(bar, text="Seed SSN",
                   command=self._seed_from_spacewx).pack(side="left", padx=4)
        self.info = tk.StringVar(value=self._ssn_src)
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel").pack(
            side="left", padx=10)

        cols = ("region", "muf", "workable", "band", "dist", "brg")
        heads = ("Region", "MUF", "Workable", "Best band", "Distance",
                 "Bearing")
        wrap, self.tree = make_scrolled_tree(self.frame, cols, show="headings",
                                             height=16)
        for c, h, w in zip(cols, heads, (150, 90, 100, 90, 100, 80)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w,
                             anchor="w" if c == "region" else "center")
        wrap.pack(fill="both", expand=True, padx=16, pady=8)

        # A shaded map shows the SHAPE of the opening - where the band edge
        # actually falls - which 24 representative region rows cannot.
        self.map = MplPanel(self.frame, figsize=(8.4, 3.6))
        self.map.widget.pack(fill="both", expand=True, padx=16,
                             pady=(0, 8))
        for name, color in QUALITY_TAGS.items():
            self.tree.tag_configure(name, foreground=color)

        note = ("MINIMUF-3.5 is a monthly-median model driven by sunspot number, "
                "not a live ionosonde: weakest on very short and antipodal paths, "
                "and it says nothing about absorption. \u201cWorkable\u201d is the "
                "usual ~85% of MUF.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))
        self._rows = []

    def _default_ssn(self):
        """Sunspot number from the Space Wx cache, via the shared seed helper.

        Kept in the engine so the desktop and the TUI cannot disagree about
        what the current SSN is.
        """
        from ...engine.spacewx_interp import seed_ssn
        try:
            cache = self.store.load_spacewx_cache()
        except Exception:
            cache = None
        val, src = seed_ssn(cache)
        self._ssn_src = src
        return int(round(val))


    def _draw_map(self, ssn):
        """MUF to a grid of destinations, shaded."""
        import numpy as np
        self.map.fig.clf()
        ax = self.map.fig.add_subplot(111)
        ax.set_facecolor("#0d1117")
        try:
            lats, lons, vals = MUF.muf_grid(self.store.obs.lat,
                                            self.store.obs.lon,
                                            now_unix(), ssn)
        except Exception:
            return
        grid = np.array([[(v if v else np.nan) for v in row] for row in vals],
                        dtype=float)
        im = ax.imshow(grid, origin="lower", aspect="auto", cmap="viridis",
                       extent=[lons[0], lons[-1], lats[0], lats[-1]])
        draw_basemap(ax, graticule=False)
        ax.plot([self.store.obs.lon], [self.store.obs.lat], "o",
                color=COL_WARN, ms=5)
        ax.set_xlim(-180, 180)
        ax.set_ylim(-80, 80)
        ax.tick_params(colors=COL_MUTED, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color(COL_MUTED)
        cb = self.map.fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
        cb.set_label("MUF (MHz)", color=COL_MUTED, fontsize=8)
        cb.ax.tick_params(colors=COL_MUTED, labelsize=7)
        self.map.fig.tight_layout()
        self.map.canvas.draw_idle()

    def _lookup_dxcc(self):
        """MUF to a named DXCC entity.

        The region table answers "how is Europe"; this answers "can I work JA
        right now", which is the question actually being asked.
        """
        q = self.dxq.get().strip()
        if not q:
            self._render()
            return
        try:
            ssn = float(self.ssn.get())
        except ValueError:
            ssn = 100.0
        hits = MUF.muf_to_dxcc(self.store.obs.lat, self.store.obs.lon,
                               now_unix(), ssn, q)
        self.tree.delete(*self.tree.get_children())
        if not hits:
            self.info.set("No DXCC entity matching \u201c%s\u201d." % q)
            return
        for h in hits:
            self.tree.insert("", "end", tags=(h["quality"],), values=(
                "%s  %s" % (h["prefix"], h["name"]),
                "%.1f MHz" % h["muf_mhz"], "%.1f MHz" % h["workable_mhz"],
                h["band"], "%.0f km" % h["distance_km"],
                "%03.0f\u00b0" % h["bearing_deg"]))
        self.info.set("%d DXCC match(es) for \u201c%s\u201d \u2014 clear the "
                      "box and re-sort for the region table." % (len(hits), q))

    def _seed_from_spacewx(self):
        self.ssn.set(str(self._default_ssn()))
        self.info.set("SSN %s \u2014 %s" % (self.ssn.get(), self._ssn_src))
        self._compute()

    def on_show(self):
        if not self._rows:
            self._compute()

    def _compute(self):
        obs = self.store.obs
        if not getattr(obs, "valid", True):
            self.info.set("Set your QTH first (Settings).")
            return
        try:
            ssn = float(self.ssn.get())
        except ValueError:
            self.info.set("Sunspot number must be numeric.")
            return
        self.info.set("Computing\u2026")
        t = now_unix()

        def work():
            try:
                rows = MUF.muf_to_regions(obs.lat, obs.lon, t, ssn)
                self._ui(lambda: self._done(rows, ssn))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _done(self, rows, ssn):
        self._rows = rows
        self._render()
        best = max(rows, key=lambda r: r["muf_mhz"])
        self.info.set("SSN %d \u2014 best path %s at %.1f MHz."
                      % (int(ssn), best["name"], best["muf_mhz"]))

        try:

            self._draw_map(ssn)

        except Exception:

            pass


    def _render(self):
        self.tree.delete(*self.tree.get_children())
        rows = list(self._rows)
        mode = self.sortvar.get()
        if mode == "muf":
            rows.sort(key=lambda r: -r["muf_mhz"])
        elif mode == "dist":
            rows.sort(key=lambda r: r["distance_km"])
        for r in rows:
            self.tree.insert("", "end", tags=(r["quality"],), values=(
                r["name"], "%.1f MHz" % r["muf_mhz"],
                "%.1f MHz" % r["workable_mhz"], r["band"],
                "%.0f km" % r["distance_km"], "%03.0f\u00b0" % r["bearing_deg"]))

    def _report(self):
        """Print whatever this screen is currently showing."""
        from ..reports import save_report_dialog
        tree = self.tree
        cols = [tree.heading(c)["text"] for c in tree["columns"]]
        rows = [list(tree.item(i)["values"]) for i in tree.get_children()]
        if not rows:
            from tkinter import messagebox
            messagebox.showinfo("Report", "Nothing to print yet.",
                                parent=self.frame)
            return
        save_report_dialog(self, "muf", title="MUF to world regions", subtitle="MINIMUF path MUF from your QTH",
                           sections=[("", "table", (cols, rows))])
