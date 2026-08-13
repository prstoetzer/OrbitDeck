"""newlaunch.py - "what went up this month that I can actually work?"

Crosses the recently cataloged objects against the SatNOGS transmitter
database and offers the intersection as an add-to-favorites list.

The scan is user-initiated, never automatic: it is a network operation, and a
screen that reaches for the network the moment you open it is a screen you
learn to avoid.
"""

import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, make_scrolled_tree)
from ..store import _http_get
from ...engine import newlaunch as NL

IDLE_TEXT = (
    "Fetches the objects cataloged in the last 30 days \u2014 the only "
    "recency window CelesTrak publishes \u2014 sets aside the rocket "
    "bodies, debris and constellation batches, and checks what remains "
    "against the SatNOGS transmitter database. What comes back is the handful "
    "of new objects with a transmitter someone has documented \u2014 the ones "
    "worth adding.\n\n"
    "Needs network. Usually a few seconds, since the transmitter database is "
    "fetched once in bulk rather than one object at a time.\n\n"
    "A satellite missing from the results is not necessarily silent: SatNOGS "
    "coverage lags a launch by days to weeks."
)


class NewLaunchScreen(Screen):
    REPORT_TITLE = "New launches"

    def build(self):
        self.header("New launches")

        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=(0, 4))
        # CelesTrak publishes only a 30-day recency group; there is no 60-day
        # one, and asking for it returns an empty list that reads like a quiet
        # two months.
        self.scan_btn = ttk.Button(bar, text="Scan last 30 days",
                                   command=self._scan)
        self.scan_btn.pack(side="left")
        self.filter_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Filter rocket bodies, debris "
                                  "and constellations",
                        variable=self.filter_var,
                        command=self._refilter).pack(side="left", padx=16)
        self.add_btn = ttk.Button(bar, text="Add to my satellites",
                                  command=self._add, state="disabled")
        self.add_btn.pack(side="right", padx=4)

        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info, style="Muted.TLabel",
                  wraplength=900, justify="left").pack(anchor="w", padx=16)

        cols = ("name", "norad", "downlink", "mode", "tx", "have")
        wrap, self.tree = make_scrolled_tree(self.frame, cols,
                                             show="headings", height=16)
        for c, h, w in zip(cols,
                           ("Object", "NORAD", "Downlink", "Mode",
                            "Transmitters", "Status"),
                           (240, 90, 130, 110, 110, 160)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        wrap.pack(fill="both", expand=True, padx=16, pady=(4, 4))
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select())
        self.tree.bind("<Double-1>", lambda _e: self._add())

        self.detail = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.detail, style="Muted.TLabel",
                  wraplength=900).pack(anchor="w", padx=16, pady=(0, 8))

        self._entries = []
        self._hits = []
        self._stats = None
        self._busy = False
        self.info.set(IDLE_TEXT)

    # ---- scanning --------------------------------------------------------
    def _scan(self):
        if self._busy:
            return
        self._busy = True
        self.scan_btn.configure(state="disabled")
        self.info.set("Fetching the last 30 days from CelesTrak\u2026")
        url = NL.LAST_30_URL

        def work():
            try:
                text = _http_get(url, timeout=60)
                entries = NL.parse_gp(text)
                # The bulk transmitter database is one request and is cached,
                # so the whole scan is two round-trips rather than a hundred.
                tx = self.store.load_tx_cache()
                if not tx:
                    self._ui(lambda: self.info.set(
                        "Fetching the SatNOGS transmitter database\u2026"))
                    self.store.update_transponders_online()
                    tx = self.store.load_tx_cache()
                self._ui(lambda: self._done(entries, tx))
            except Exception as exc:
                self._ui(lambda e=exc: self._failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _failed(self, exc):
        self._busy = False
        self.scan_btn.configure(state="normal")
        self.info.set("Scan failed: %s" % str(exc)[:150])

    def _done(self, entries, tx):
        self._busy = False
        self.scan_btn.configure(state="normal")
        self._entries = entries
        self._tx = tx
        self._render()

    def _refilter(self):
        if self._entries:
            self._render()

    def _render(self):
        known = {s.norad for s in self.store.db.sats}
        hits, stats = NL.discover(self._entries, getattr(self, "_tx", {}),
                                  filter_noise=self.filter_var.get(),
                                  known_norads=known)
        self._hits, self._stats = hits, stats
        self.tree.delete(*self.tree.get_children())
        favorites = self.store.favorites
        for h in hits:
            if h["norad"] in favorites:
                status = "already a favorite"
            elif h["in_catalog"]:
                status = "in catalog"
            else:
                status = "new"
            self.tree.insert("", "end", values=(
                h["name"], h["norad"], NL.fmt_downlink(h["downlink_hz"]),
                h["mode"] or "\u2014", h["tx_count"], status))
        if hits:
            self.info.set("%s \u2014 select one and add it, or double-click."
                          % NL.provenance(stats))
        else:
            self.info.set("%s\n\n%s" % (NL.provenance(stats),
                                        NL.empty_message(stats)))
        self.add_btn.configure(state="disabled")
        self.detail.set("")

    # ---- selection and adding -------------------------------------------
    def _selected(self):
        sel = self.tree.selection()
        if not sel or not self._hits:
            return None
        idx = self.tree.index(sel[0])
        return self._hits[idx] if idx < len(self._hits) else None

    def _on_select(self):
        h = self._selected()
        if h is None:
            return
        self.add_btn.configure(state="normal")
        modes = ", ".join(sorted({str(r.get("mode")) for r in h["records"]
                                  if r.get("mode")})) or "unknown"
        self.detail.set("NORAD %d \u2014 %d transmitter(s) known to SatNOGS; "
                        "modes: %s." % (h["norad"], h["tx_count"], modes))

    def _add(self):
        h = self._selected()
        if h is None:
            return
        from tkinter import messagebox
        existing = self.store.db.get(h["norad"])
        if existing is not None:
            self.store.favorites.add(existing.norad)
            self.store.save_config()
            msg = "%s was already in the catalog \u2014 starred." % \
                existing.name
        else:
            try:
                # Keyed by NORAD and sourced from the GP entry already in hand,
                # so the routine element update keeps it current instead of
                # freezing today's elements.
                self.store.add_extra_sat({"norad": h["norad"],
                                          "name": h["name"],
                                          "omm": h["omm"]},
                                         make_favorite=True)
            except Exception as exc:
                messagebox.showerror("Add", str(exc)[:200], parent=self.frame)
                return
            msg = "Added %s (NORAD %d); its elements will refresh with the " \
                  "rest." % (h["name"], h["norad"])
        # The probe response IS the transponder record, and it is already in
        # hand - caching it here means adding needs no further network.
        try:
            self.store.cache_transmitters(h["norad"], h["records"])
        except Exception:
            pass
        self._render()
        self.info.set(msg)

    def _report(self):
        from ..reports import save_report_dialog
        rows = [(h["name"], str(h["norad"]),
                 NL.fmt_downlink(h["downlink_hz"]), h["mode"] or "-",
                 str(h["tx_count"])) for h in self._hits]
        save_report_dialog(
            self, "newlaunch", title="New launches with transmitters",
            subtitle=NL.provenance(self._stats) if self._stats else None,
            sections=[("Hits", "table",
                       (("Object", "NORAD", "Downlink", "Mode", "Tx"), rows))])
