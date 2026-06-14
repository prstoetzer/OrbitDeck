"""spacewx.py (screen) - solar/geomagnetic indices for propagation planning."""

import threading
import datetime as dt
import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, FONT_MONO, now_unix)
from .. import spacewx as WX


def _color_for(level):
    return {
        "low": COL_WARN, "weak": COL_WARN,
        "moderate": COL_TEXT, "unsettled": COL_TEXT, "active": COL_WARN,
        "good": COL_ACCENT2, "quiet": COL_ACCENT2, "high": COL_ACCENT2,
        "minor": COL_WARN, "moderate": COL_WARN,
        "major": "#f85149", "storm": "#f85149",
    }.get(level, COL_TEXT)


class SpaceWxScreen(Screen):
    def build(self):
        self.header("Space Weather \u2014 solar & geomagnetic indices")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(bar, text="Refresh (online)",
                   command=self._refresh).pack(side="left")
        self.status = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.status, style="TLabel").pack(
            side="left", padx=12)

        self.kv = KVPanel(self.frame, label_width=16)
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
                data = self.store.update_spacewx()
                self._data = data
                self.app.root.after(0, lambda: (self._render(),
                                                self.status.set("")))
            except Exception as e:
                self.app.root.after(
                    0, lambda: self.status.set("fetch failed: %s" % e))
        threading.Thread(target=work, daemon=True).start()

    def _render(self):
        k = self.kv
        k.begin()
        d = self._data
        if not d:
            k.section("Space weather")
            k.note("No data yet. Click Refresh (needs internet). Indices come "
                   "from NOAA SWPC; the last result is cached for offline use.")
            k.end()
            return

        flux = d.get("flux")
        kp = d.get("kp")
        a = d.get("a_index")
        fl_txt, fl_lvl = WX.flux_label(flux)
        kp_txt, kp_lvl = WX.kp_label(kp)
        a_txt, a_lvl = WX.a_label(a)

        k.section("Solar activity")
        k.row("F10.7 flux",
              ("%.0f sfu" % flux) if flux is not None else "\u2014",
              COL_ACCENT, big=True)
        k.row("Level", fl_txt, _color_for(fl_lvl))

        k.section("Geomagnetic field")
        k.row("Kp index",
              ("%.1f" % kp) if kp is not None else "\u2014",
              _color_for(kp_lvl), big=True)
        k.row("Condition", kp_txt, _color_for(kp_lvl))
        k.row("A index",
              ("%.0f" % a) if a is not None else "\u2014")
        k.row("A condition", a_txt, _color_for(a_lvl))

        k.section("Operating outlook")
        k.note(WX.outlook(flux, kp), COL_TEXT)

        ts = d.get("ts")
        if ts:
            age = (now_unix() - ts) / 3600.0
            when = dt.datetime.fromtimestamp(
                ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            k.row("Data age", "%s  (%.1f h ago)" % (when, age),
                  COL_MUTED)
        k.note("Planning cue, not a forecast: F10.7 and Kp are observed values "
               "and the outlook is a simple heuristic. A high Kp (storm) is the "
               "main thing to watch \u2014 it warns of auroral flutter on VHF "
               "and disturbed high-latitude HF.")
        k.note("Space weather data from NOAA SWPC (services.swpc.noaa.gov).",
               COL_MUTED)
        k.end()
