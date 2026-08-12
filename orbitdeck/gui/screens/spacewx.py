"""spacewx.py (screen) - solar/geomagnetic indices for propagation planning."""

import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, COL_TEXT, COL_MUTED, COL_ACCENT2,
               COL_WARN)


def _color_for(level):
    # Single mapping per level (no duplicate keys). "moderate" is treated as a
    # storm-severity level (warning colour), consistent with NOAA G/R/S scales.
    return {
        "low": COL_WARN, "weak": COL_WARN,
        "unsettled": COL_TEXT, "active": COL_WARN,
        "good": COL_ACCENT2, "quiet": COL_ACCENT2, "high": COL_ACCENT2,
        "minor": COL_WARN, "moderate": COL_WARN,
        "major": "#f85149", "storm": "#f85149",
    }.get(level, COL_TEXT)


class SpaceWxScreen(Screen):
    def build(self):
        self.header("Space Weather \u2014 solar & geomagnetic indices")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(bar, text="Report\u2026",

                   command=self._report).pack(side="right", padx=4)
        ttk.Button(bar, text="Refresh",
                   command=self._refresh).pack(side="left")
        self.status = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.status, style="TLabel").pack(
            side="left", padx=12)

        self.outlook_var = tk.StringVar(value="")
        self.kv = KVPanel(self.frame, label_width=20)
        ttk.Label(self.frame, textvariable=self.outlook_var,
                  style="Muted.TLabel", wraplength=900).pack(
            anchor="w", padx=16, pady=(4, 8))
        self.kv.pack(fill="both", expand=True, padx=16, pady=8)
        self._data = None

    def on_show(self):
        if self._data is None:
            self._data = self.store.load_spacewx_cache()
        self._render()
        # auto-refresh once on entry (non-blocking)
        self._refresh()

    def _refresh(self):
        self.status.set("fetching\u2026")

        def work():
            try:
                try:
                    data = self.store.update_spacewx()
                    self._data = data
                    self._ui(lambda: (self._render(),
                                                    self.status.set("")))
                except Exception as e:
                    self.app.root.after(
                        0, lambda e=e: self.status.set("fetch failed: %s" % e))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _render(self):
        """Interpreted rows plus a plain-language outlook.

        Raw indices alone leave the operator to remember what Kp 6 means; the
        labels, aurora likelihood and outlook are what make the screen useful,
        and they come from the shared engine module so the TUI and the report
        agree with this screen.
        """
        from ...engine import spacewx_interp as SI
        d = self._data or {}
        self.kv.begin()
        if not d:
            self.kv.row("No data yet", "press Update", COL_WARN)
            self.kv.end()
            self.outlook_var.set("")
            return
        colours = {0: COL_MUTED, 1: COL_TEXT, 2: COL_ACCENT2,
                   3: COL_WARN, 4: COL_WARN}
        for label, value, sev in SI.rows(d):
            self.kv.row(label, value, colours.get(sev, COL_TEXT))
        self.kv.end()
        self.outlook_var.set("Operating outlook:  "
                             + SI.outlook(d.get("flux"), d.get("kp")))

