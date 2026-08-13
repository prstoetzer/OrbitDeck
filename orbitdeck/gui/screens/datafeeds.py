"""datafeeds.py (screen) - upcoming activations + QRZ callsign lookup.

Two tabs:
  * Activations - the public hams.at upcoming-activations feed (scheduled roves
    and grid activations), with a one-click add of the activation's satellite to
    favorites via CelesTrak search.
  * QRZ lookup - resolve a callsign to name / location / grid / class over the
    QRZ XML API (needs the user's QRZ XML-subscription credentials, entered here
    and kept in prefs).

Fetches run off-thread so the UI never blocks; both degrade gracefully offline.
"""

import threading
import tkinter as tk
from tkinter import ttk

from . import (fmt_utc, Screen, TabBar, make_scrolled_tree)
from .. import datafeeds as DF
from ..store import _http_get
from ..datafeeds import strip_utc as _clock


class DataFeedsScreen(Screen):
    def build(self):
        self.header("Data feeds \u2014 activations & QRZ")
        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        self._build_acts(tabs.add("Activations"))
        self._build_qrz(tabs.add("QRZ lookup"))

    # ---- activations ----
    def _build_acts(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=6)
        ttk.Button(bar, text="Print screen\u2026",

                   command=self._report).pack(side="right", padx=4)
        ttk.Button(bar, text="Refresh feed",
                   command=self._fetch_acts).pack(side="left")
        ttk.Button(bar, text="Can I work it?\u2026",
                   command=self._check_act).pack(side="left", padx=6)
        ttk.Button(bar, text="Add satellite",
                   command=self._add_act_sat).pack(side="left")
        self.ainfo = tk.StringVar(
            value="Upcoming satellite activations from hams.at (public feed).")
        ttk.Label(bar, textvariable=self.ainfo, style="Muted.TLabel").pack(
            side="left", padx=8)

        cols = ("date", "start", "call", "sat", "grid", "el", "mode", "freq")
        heads = ("Date", "Start", "Call", "Satellite", "Grid", "My max el",
                 "Mode", "Freq")
        wrap, self.atree = make_scrolled_tree(parent, cols, show="headings",
                                              height=13)
        widths = {"date": 100, "start": 90, "call": 90, "sat": 110,
                  "grid": 70, "el": 70, "mode": 70, "freq": 100}
        for c, h in zip(cols, heads):
            self.atree.heading(c, text=h)
            self.atree.column(c, width=widths[c],
                              anchor="w" if c in ("date", "sat") else "center")
        wrap.pack(fill="both", expand=True, padx=4, pady=8)
        # Bound at build time, not after a fetch: binding inside the refresh
        # handler meant double-click did nothing until a feed had loaded.
        # Double-click opens the mutual-window / Doppler detail, which is the
        # primary thing you want from an activation; adding the satellite is an
        # explicit button since it changes your catalog.
        self.atree.bind("<Double-Button-1>", lambda _e: self._check_act())
        self._acts = []

    def _fetch_acts(self):
        self.ainfo.set("Fetching hams.at feed\u2026")

        def work():
            try:
                try:
                    acts = DF.fetch_activations(
                        lambda url, timeout=25: _http_get(url, timeout))
                except Exception as exc:
                    self.app.root.after(
                        0, lambda e=exc: self.ainfo.set(str(e)[:110]))
                    return
                self._ui(lambda: self._show_acts(acts))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _show_acts(self, acts):
        self._acts = acts
        self.atree.delete(*self.atree.get_children())
        for a in acts:
            # The feed's "Max elevation" is the ACTIVATOR's and is usually
            # absent, so the column read "None" for every row. Compute the
            # elevation from YOUR station - that is the number that decides
            # whether the activation is workable at all.
            from ...engine import activations as _ACT
            try:
                mine = _ACT.max_elevation(self.store, a)
            except Exception:
                mine = None
            el = "%d\u00b0" % mine if mine is not None else "\u2014"
            self.atree.insert("", "end", values=(
                a.get("date", ""), _clock(a["start"]), a["callsign"],
                a["sat"], a["grid"], el, a["mode"], a["freq"]))
        if acts:
            self.ainfo.set("%d upcoming activation(s). Double-click one for "
                           "its mutual window and DX Doppler." % len(acts))
        else:
            self.ainfo.set("No activations (or the feed was unreachable "
                           "offline).")
    def _check_act(self):
        """Can you and the activator both see the satellite at the listed time?

        That is the question the entry exists to answer, and CardSat answers it
        on ENTER. Distinguishes *why* it cannot be worked - an unusable grid,
        an unparseable feed time and a genuinely absent satellite are different
        problems, and reporting them all as "not in your list" sends you
        hunting for a satellite that was there all along.
        """
        import threading
        from ...engine import activations as ACT
        sel = self.atree.selection()
        if not sel:
            self.ainfo.set("Select an activation first.")
            return
        idx = self.atree.index(sel[0])
        if idx >= len(self._acts):
            return
        act = self._acts[idx]
        self.ainfo.set("Checking mutual visibility\u2026")

        def work():
            try:
                try:
                    state, info = ACT.check_activation(self.store, act)
                except Exception as exc:
                    self.app.root.after(
                        0, lambda e=exc: self.ainfo.set(str(e)[:110]))
                    return
                self._ui(lambda: self._show_check(act, state, info))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _show_check(self, act, state, info):
        """Open the full workflow on success; explain precisely on failure.

        CardSat does not stop at a yes/no - the activation leads to the mutual
        window and from there to a DX Doppler table seeded with that window and
        the activation's own satellite. This opens that.
        """
        from ...engine import activations as ACT
        base = "%s on %s" % (act.get("callsign", "?"), act.get("sat", "?"))
        if state != ACT.FP_OK:
            self.ainfo.set("%s \u2014 %s." % (base, ACT.FP_TEXT[state]))
            return
        a, b = info["window"]
        self.ainfo.set("%s \u2014 workable: mutual window %s to %s UTC."
                       % (base, fmt_utc(a, "%Y-%m-%d %H:%M"),
                          fmt_utc(b, "%H:%M")))
        from .actdetail import ActivationDetail
        ActivationDetail(self.frame.winfo_toplevel(), self.store, act, info)

    def _add_act_sat(self, _evt=None):
        sel = self.atree.selection()
        if not sel:
            return
        idx = self.atree.index(sel[0])
        if idx >= len(self._acts):
            return
        sat = self._acts[idx]["sat"]
        if not sat:
            return
        # Look locally FIRST. The feed uses operating names ("AO-91") while the
        # catalog carries "AO-91 (RADFXSAT)", so a plain name compare missed
        # and every add went to CelesTrak - re-fetching satellites already in
        # the catalog and adding duplicates.
        from ...engine import activations as ACT
        have = ACT.find_local(self.store.db, sat)
        if have is not None:
            if have.norad in self.store.favorites:
                self.ainfo.set("%s (NORAD %d) is already a favorite."
                               % (have.name, have.norad))
            else:
                self.store.favorites.add(have.norad)
                self.store.save_config()
                self.ainfo.set("%s (NORAD %d) was already in your catalog "
                               "\u2014 starred it." % (have.name, have.norad))
            return
        self.ainfo.set("Searching CelesTrak for %s\u2026" % sat)

        def work():
            try:
                try:
                    hits = self.store.search_celestrak(sat)
                except Exception as e:
                    self._ui(lambda e=e: self.ainfo.set(str(e)))
                    return
                self._ui(lambda: self._got_act_sat(sat, hits))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _got_act_sat(self, sat, hits):
        if not hits:
            self.ainfo.set("No CelesTrak match for \u201c%s\u201d." % sat)
            return
        # Guard again on NORAD: a search can return an object already present
        # under a different name.
        norad = hits[0].get("norad")
        existing = self.store.db.get(norad) if norad else None
        if existing is not None:
            self.store.favorites.add(existing.norad)
            self.store.save_config()
            self.ainfo.set("%s (NORAD %d) was already in your catalog "
                           "\u2014 starred it." % (existing.name,
                                                   existing.norad))
            return
        self.store.add_extra_sat(hits[0], make_favorite=True)
        self.ainfo.set("Added %s (NORAD %d) as a favorite."
                       % (hits[0]["name"], hits[0]["norad"]))

    # ---- QRZ ----
    def _build_qrz(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=4, pady=6)
        ttk.Label(bar, text="Callsign:", style="TLabel").pack(side="left")
        self.callvar = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.callvar, width=14)
        ent.pack(side="left", padx=6)
        ent.bind("<Return>", lambda _e: self._qrz_lookup())
        ttk.Button(bar, text="Look up",
                   command=self._qrz_lookup).pack(side="left")
        ttk.Button(bar, text="QRZ credentials\u2026",
                   command=self._qrz_creds).pack(side="left", padx=8)

        self.qrzout = tk.Text(parent, height=12, width=60, bg="#0d1117",
                              fg="#e6edf3", insertbackground="#e6edf3",
                              relief="flat", font=("DejaVu Sans Mono", 11),
                              wrap="word")
        self.qrzout.pack(fill="both", expand=True, padx=8, pady=8)
        self.qrzout.insert("1.0",
                           "Enter a callsign and press Look up.\n\n"
                           "QRZ's XML API needs an XML-subscription account; "
                           "set your QRZ username/password with \u201cQRZ "
                           "credentials\u2026\u201d. They're stored locally in "
                           "your OrbitDeck config.")
        self.qrzout.configure(state="disabled")
        self._qrz_key = None

    def _qrz_creds(self):
        from tkinter import simpledialog
        user = simpledialog.askstring("QRZ credentials", "QRZ username:",
                                      parent=self.frame,
                                      initialvalue=self.store.config.get(
                                          "qrz_user", ""))
        if user is None:
            return
        pw = simpledialog.askstring("QRZ credentials", "QRZ password:",
                                    parent=self.frame, show="*")
        if pw is None:
            return
        self.store.prefs["qrz_user"] = user
        self.store.prefs["qrz_pass"] = pw
        self.store.save_config()
        self._qrz_key = None
        self._set_qrz("Saved QRZ credentials for %s." % user)

    def _set_qrz(self, text):
        self.qrzout.configure(state="normal")
        self.qrzout.delete("1.0", "end")
        self.qrzout.insert("1.0", text)
        self.qrzout.configure(state="disabled")

    def _qrz_lookup(self):
        call = self.callvar.get().strip().upper()
        if not call:
            return
        user = self.store.config.get("qrz_user", "")
        pw = self.store.config.get("qrz_pass", "")
        if not user or not pw:
            self._set_qrz("Set your QRZ credentials first "
                          "(\u201cQRZ credentials\u2026\u201d).")
            return
        self._set_qrz("Looking up %s\u2026" % call)

        def work():
            try:
                res, key, err = DF.qrz_lookup(
                    lambda url, timeout=15: _http_get(url, timeout),
                    user, pw, call, session_key=self._qrz_key)
                self._ui(lambda: self._show_qrz(res, key, err, call))
            except Exception as _exc:
                self._ui(lambda e=_exc: self._worker_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _show_qrz(self, res, key, err, call):
        if key:
            self._qrz_key = key
        if res is None:
            self._set_qrz("%s: %s" % (call, err or "not found"))
            return
        lines = [
            "%s   (%s)" % (res["call"], res["class"] or "?"),
            res["name"] or "",
            res["addr"] or "",
            res["country"] or "",
            "",
            "Grid: %s" % (res["grid"] or "unknown"),
        ]
        self._set_qrz("\n".join(x for x in lines if x is not None))

    def _report(self):
        """Print whatever this screen is currently showing."""
        from ..reports import save_report_dialog
        tree = self.atree
        cols = [tree.heading(c)["text"] for c in tree["columns"]]
        rows = [list(tree.item(i)["values"]) for i in tree.get_children()]
        if not rows:
            from tkinter import messagebox
            messagebox.showinfo("Report", "Nothing to print yet.",
                                parent=self.frame)
            return
        save_report_dialog(self, "datafeeds", title="Activations", subtitle="Upcoming activations from hams.at",
                           sections=[("", "table", (cols, rows))])
