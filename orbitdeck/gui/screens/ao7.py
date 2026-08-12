"""ao7.py (screen) - the AO-7 mode-switch calculator.

AO-7 runs straight off its solar panels, so its Mode A / Mode B timer only
alternates while the spacecraft is in continuous sunlight. This screen shows
that illumination verdict, and - when the timer is running - estimates where in
the cycle it currently is by fitting a square wave to AMSAT status reports.
"""

import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, COL_ACCENT2, COL_WARN, COL_TEXT, COL_MUTED,
               fmt_utc, fmt_hms, now_unix)
from ...engine.predict import Predictor
from ..store import _http_get
from ...engine import ao7 as A7


class Ao7Screen(Screen):
    def build(self):
        self.header("AO-7 mode switch")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        self.fetchbtn = ttk.Button(bar, text="Fetch AMSAT reports & estimate",
                                   command=self._fetch)
        self.fetchbtn.pack(side="left")
        ttk.Label(bar, text="Window:", style="TLabel").pack(side="left",
                                                             padx=(12, 2))
        self.days = tk.IntVar(value=30)
        for v in (14, 30, 60):
            ttk.Radiobutton(bar, text="%dd" % v, value=v,
                            variable=self.days).pack(side="left")
        self.info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.info, style="Muted.TLabel").pack(
            side="left", padx=10)

        self.kv = KVPanel(self.frame, label_width=22)
        self.kv.pack(fill="both", expand=True, padx=16, pady=8)

        note = ("AO-7 has no batteries: the 24 h-ish timer only alternates while "
                "the spacecraft is in continuous sunlight. The phase estimate is "
                "fitted to crowd-sourced AMSAT status reports, so it is an "
                "estimate \u2014 the confidence line says how good.")
        ttk.Label(self.frame, text=note, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))
        self._show_illumination()

    def _sat(self):
        """AO-7 from the catalog, whatever it's named locally."""
        s = self.store.db.get(A7.AO7_NORAD)
        if s:
            return s
        for cand in self.store.db.sats:
            if "AO-7" in getattr(cand, "name", "").upper():
                return cand
        return None

    def on_show(self):
        self._show_illumination()

    def _show_illumination(self):
        sat = self._sat()
        self.kv.begin()
        if not sat:
            self.kv.row("AO-7", "not in catalog", COL_WARN)
            self.kv.row("hint", "load GP data including NORAD 7530", COL_MUTED)
            self.kv.end()
            return
        pred = Predictor()
        pred.set_site(self.store.obs)
        t = now_unix()
        found = A7.illumination_since(pred, sat, t)
        since, since_exact = (found if found else (None, True))
        self.kv.row("Satellite", sat.name)
        if since is None:
            self.kv.row("Illumination", "eclipsing each orbit", COL_WARN)
            self.kv.row("Timer", "not running \u2014 mode follows power",
                        COL_TEXT)
            self.kv.row("hint", "no fixed daily switch while eclipsing",
                        COL_MUTED)
        else:
            self.kv.row("Illumination", "continuous sunlight", COL_ACCENT2)
            self.kv.row("Timer", "running \u2014 mode alternates", COL_ACCENT2)
            self.kv.row("Since", fmt_utc(since, "%Y-%m-%d %H:%M"),
                        COL_TEXT if since_exact else COL_MUTED)
            if not since_exact:
                self.kv.row("", "at least this long \u2014 search window edge",
                            COL_MUTED)
            self.kv.row("hint", "fetch reports to estimate the phase",
                        COL_MUTED)
        self.kv.end()

    def _fetch(self):
        sat = self._sat()
        if not sat:
            self.info.set("AO-7 is not in the catalog.")
            return
        self.info.set("Fetching AMSAT status reports\u2026")
        self.fetchbtn.state(["disabled"])
        hours = self.days.get() * 24

        def work():
            try:
                pred = Predictor()
                pred.set_site(self.store.obs)
                try:
                    res = A7.fetch_and_fit(
                        lambda url: _http_get(url, 30),
                        pred=pred, sat=sat, now=now_unix(), hours=hours)
                except Exception as e:
                    self._ui(lambda e=e: self._failed(str(e)))
                    return
                self._ui(lambda: self._show(res, sat))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _failed(self, msg):
        self.fetchbtn.state(["!disabled"])
        self.info.set(msg[:110])

    def _show(self, res, sat):
        self.fetchbtn.state(["!disabled"])
        self.kv.begin()
        self.kv.row("Satellite", sat.name)
        if not res.get("continuous_sun", False):
            self.kv.row("Illumination", "eclipsing each orbit", COL_WARN)
            self.kv.row("Timer", "not running", COL_TEXT)
            self.kv.row("Note", res.get("note", ""), COL_MUTED)
            self.kv.end()
            self.info.set(res.get("note", ""))
            return
        self.kv.row("Illumination", "continuous sunlight", COL_ACCENT2)
        if res.get("since"):
            self.kv.row("Timer running since",
                        fmt_utc(res["since"], "%Y-%m-%d %H:%M"))
        if "period_s" not in res:
            self.kv.row("Estimate", res.get("note", "no data"), COL_WARN)
            self.kv.end()
            self.info.set(res.get("note", ""))
            return
        near = res.get("near_boundary")
        self.kv.row("Mode now", res["mode_now_name"],
                    COL_WARN if near else COL_ACCENT2)
        self.kv.row("Next switch", fmt_utc(res["next_switch"],
                                           "%Y-%m-%d %H:%M"))
        self.kv.row("Time to switch", fmt_hms(res["to_switch_s"]))
        self.kv.row("Fitted period", "%.2f h" % (res["period_s"] / 3600.0))
        self.kv.row("Phase uncertainty", "\u00b1%.0f min"
                    % (res["phase_rms_s"] / 60.0))
        self.kv.row("Report agreement", "%.0f %%" % res["agree_pct"],
                    COL_ACCENT2 if res["agree_pct"] >= 75 else COL_WARN)
        self.kv.row("Reports used", "%d (%d heard, %d not)"
                    % (res["n_obs"], res["n_pos"], res["n_neg"]))
        self.kv.row("Mode changes seen", "%d" % res["n_switch"])
        self.kv.row("Confidence", res["note"],
                    COL_WARN if near or res["agree_pct"] < 75 else COL_TEXT)
        self.kv.end()
        self.info.set("Fitted %.2f h period from %d reports."
                      % (res["period_s"] / 3600.0, res["n_obs"]))
