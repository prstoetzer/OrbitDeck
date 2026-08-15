"""amsatstatus.py (screen) - AMSAT community status board, and reporting.

Reads the AMSAT status API (who has heard what in the last N hours) and lets you
post your own observation for the selected satellite.

Submitting is public and attributed - the report carries your callsign and grid
and appears on amsat.org - so the send button asks for confirmation and the
screen refuses to send without a callsign set.
"""

import threading
import tkinter as tk
from tkinter import ttk

from . import (Screen, TabBar, fmt_utc, now_unix, make_scrolled_tree)
from ...engine import amsatstatus as AS
from ..store import _http_get


class AmsatStatusScreen(Screen):
    def build(self):
        self.header("AMSAT status \u2014 community reports")
        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        self._build_board(tabs.add("Status board"))
        self._build_report(tabs.add("Report status"))

    # ---- board ----
    def _build_board(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=6)
        ttk.Button(bar, text="Refresh",
                   command=self._fetch_summary).pack(side="left")
        ttk.Label(bar, text="Window:", style="TLabel").pack(side="left",
                                                             padx=(12, 2))
        self.hours = tk.IntVar(value=AS.DEFAULT_WINDOW_H)
        for v in (6, 24, 48):
            ttk.Radiobutton(bar, text="%dh" % v, value=v,
                            variable=self.hours).pack(side="left")
        self.binfo = tk.StringVar(
            value="Who has heard what, from amsat.org.")
        ttk.Label(bar, textvariable=self.binfo, style="Muted.TLabel").pack(
            side="left", padx=10)
        cols = ("sat", "reports", "heard", "last")
        heads = ("Satellite", "Reports", "Heard", "Last report")
        wrap, self.btree = make_scrolled_tree(parent, cols, show="headings",
                                              height=14)
        for c, h, w in zip(cols, heads, (220, 90, 90, 180)):
            self.btree.heading(c, text=h)
            self.btree.column(c, width=w,
                              anchor="w" if c in ("sat", "last") else "center")
        wrap.pack(fill="both", expand=True, padx=4, pady=6)

    def _fetch_summary(self):
        self.binfo.set("Fetching\u2026")

        def work():
            try:
                try:
                    body = _http_get(AS.summary_url(self.hours.get()), 25)
                    rows = AS.parse_summary(body)
                except Exception as e:
                    self._ui(lambda e=e: self.binfo.set(str(e)[:90]))
                    return
                self._ui(lambda: self._show_summary(rows))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _show_summary(self, rows):
        self.btree.delete(*self.btree.get_children())
        for r in rows:
            self.btree.insert("", "end", values=(
                r["pretty"], r["reports"], r["heard"], r["last_report"]))
        self.binfo.set("%d satellite(s) reported in the last %dh."
                       % (len(rows), self.hours.get())
                       if rows else "No reports (or the feed was unreachable).")

    # ---- reporting ----
    def _build_report(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=6)
        ttk.Label(bar, text="AMSAT name:", style="TLabel").pack(side="left")
        self.apiname = tk.StringVar(value="")
        self._user_edited = False
        self._resolved_for = None
        _ent = ttk.Entry(bar, textvariable=self.apiname, width=18)
        # A name the operator typed themselves survives a satellite change;
        # one we resolved does not. Bound to the KEY event, not the variable,
        # so our own programmatic sets do not look like an edit.
        _ent.bind("<KeyRelease>",
                  lambda _e: setattr(self, "_user_edited", True))
        _ent.pack(side="left", padx=6)
        ttk.Label(bar, text="Status:", style="TLabel").pack(side="left",
                                                             padx=(10, 2))
        self.status = tk.StringVar(value=AS.STATUSES[0])
        ttk.Combobox(bar, textvariable=self.status, state="readonly", width=16,
                     values=AS.STATUSES).pack(side="left")
        self.sendbtn = ttk.Button(bar, text="Send report\u2026",
                                  command=self._send)
        self.sendbtn.pack(side="left", padx=10)
        self.rinfo = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.rinfo, style="Muted.TLabel").pack(
            anchor="w", padx=8, pady=(0, 4))

        cols = ("call", "grid", "status", "when")
        heads = ("Callsign", "Grid", "Status", "When")
        wrap, self.rtree = make_scrolled_tree(parent, cols, show="headings",
                                              height=11)
        for c, h, w in zip(cols, heads, (110, 90, 130, 180)):
            self.rtree.heading(c, text=h)
            self.rtree.column(c, width=w,
                              anchor="w" if c == "when" else "center")
        wrap.pack(fill="both", expand=True, padx=4, pady=6)
        ttk.Button(parent, text="Load recent reports for this name",
                   command=self._fetch_reports).pack(anchor="w", padx=8,
                                                     pady=(0, 6))
        note = ("A report is public and attributed: it carries your callsign "
                "and grid and appears on amsat.org. Set your callsign in "
                "Settings first.")
        ttk.Label(parent, text=note, style="Muted.TLabel",
                  wraplength=880).pack(anchor="w", padx=8, pady=(0, 6))

    def on_show(self):
        sat = self.store.selected_sat()
        # Re-resolve when the SATELLITE changes, not only when the box is
        # empty: switching birds used to leave the previous one's API name in
        # place, so the screen quietly reported the wrong satellite's status.
        # A name the operator typed themselves is still respected.
        changed = sat is not None and getattr(sat, "norad", None) != \
            getattr(self, "_resolved_for", None)
        if changed and not getattr(self, "_user_edited", False):
            self.apiname.set("")
        if sat is not None:
            self._resolved_for = getattr(sat, "norad", None)
        if sat and not self.apiname.get():
            # A catalog name is not an API name ("ISS (ZARYA)" is "ISS_[FM]"),
            # so resolve it through the API's own catalog. Falls back to the
            # raw name, which the user can still correct by hand.
            self.apiname.set(self._resolve(sat) or getattr(sat, "name", ""))

    def _resolve(self, sat):
        """First API name for this satellite, via the catalog matcher."""
        try:
            body = _http_get(AS.CATALOG_URL, 25)
            names = AS.resolve_names(AS.parse_catalog(body),
                                     getattr(sat, "name", ""))
            if names:
                self.rinfo.set("Matched %s to %s" % (
                    sat.name, ", ".join(names)))
                return names[0]
        except Exception as exc:
            self.rinfo.set("Could not fetch the AMSAT catalog: %s"
                           % str(exc)[:60])
        return None

    def _fetch_reports(self):
        name = self.apiname.get().strip()
        if not name:
            self.rinfo.set("Enter the AMSAT catalog name (e.g. AO-91[FM]).")
            return
        self.rinfo.set("Fetching reports for %s\u2026" % name)

        def work():
            try:
                try:
                    body = _http_get(AS.reports_url(name, self.hours.get()), 25)
                    rows = AS.parse_reports(body)
                except Exception as e:
                    self._ui(lambda e=e: self.rinfo.set(str(e)[:90]))
                    return
                self._ui(lambda: self._show_reports(rows, name))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _show_reports(self, rows, name):
        self.rtree.delete(*self.rtree.get_children())
        for r in rows:
            when = fmt_utc(r["unix"], "%Y-%m-%d %H:%M") if r["unix"] else \
                r["time"]
            self.rtree.insert("", "end", values=(
                r["callsign"], r["grid"], r["status"], when))
        grids, heard = AS.grid_counts(rows)
        self.rinfo.set("%s: %d report(s), %d heard, %d grid(s)."
                       % (AS.pretty_name(name), len(rows), heard, grids)
                       if rows else "No reports for %s in the window." % name)

    def _send(self):
        from tkinter import messagebox
        name = self.apiname.get().strip()
        status = self.status.get()
        call = self.store.config.get("callsign", "") or \
            self.store.config.get("my_call", "")
        if not call:
            self.rinfo.set("Set your callsign in Settings before reporting.")
            return
        if not name:
            self.rinfo.set("Enter the AMSAT catalog name first.")
            return
        grid = getattr(self.store, "grid", "") or ""
        if not messagebox.askyesno(
                "Send public report",
                "Post \u201c%s\u201d for %s to amsat.org as %s%s?\n\n"
                "This is public and attributed."
                % (status, AS.pretty_name(name), call,
                   (" / " + grid) if grid else ""),
                parent=self.frame):
            return
        self.sendbtn.state(["disabled"])
        self.rinfo.set("Sending\u2026")

        def work():
            try:
                def post(url, body):
                    from ..store import _http_post
                    return _http_post(url, body, 25)
                ok, msg = AS.submit_report(post, name, status, call, grid,
                                           now_unix())
                self._ui(lambda: self._sent(ok, msg))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _sent(self, ok, msg):
        self.sendbtn.state(["!disabled"])
        self.rinfo.set(msg)
        if ok:
            self._fetch_reports()
