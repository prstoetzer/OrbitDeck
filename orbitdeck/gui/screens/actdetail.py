"""actdetail.py - the activation detail window.

CardSat's activation workflow does not stop at "there is a window": from the
activation you get the **mutual window** itself, and from that a **DX Doppler**
table tailored to it - dial frequencies for both stations across the window, for
the activation's own satellite and transponder.

This is that workflow as a dialog: pick a window, pick a transponder, then read
the table. Mode and anchor are the same set the standalone DX Doppler screen
offers, because it is the same engine underneath - the point of this screen is
the *seeding*, not a differentcalculation.
"""

import tkinter as tk
from tkinter import ttk

from . import (COL_MUTED, MplPanel, fmt_utc,
               fmt_hms, make_scrolled_tree)
from ...engine import dxdoppler as DXD

MODES = [("True rule (both track)", DXD.TRUE_RULE),
         ("Fixed downlink", DXD.FIXED_DL),
         ("Fixed uplink", DXD.FIXED_UL)]
ANCHORS = [("My RX", DXD.ME_RX), ("My TX", DXD.ME_TX),
           ("DX RX", DXD.DX_RX), ("DX TX", DXD.DX_TX)]


class ActivationDetail(tk.Toplevel):
    """Mutual window + DX Doppler for one activation."""

    def __init__(self, parent, store, act, info):
        super().__init__(parent)
        self.title("Activation \u2014 %s on %s"
                   % (act.get("callsign", "?"), act.get("sat", "?")))
        self.geometry("980x620")
        self.configure(bg="#0d1117")
        self.store = store
        self.act = act
        self.info = info
        self.windows = info.get("windows") or []
        self.sat = info.get("sat")
        self.dx = info.get("dx")

        head = ttk.Frame(self, style="TFrame")
        head.pack(fill="x", padx=12, pady=8)
        ttk.Label(head, text="%s on %s from %s" % (
            act.get("callsign", "?"), act.get("sat", "?"),
            info.get("grid", "?")), style="TLabel").pack(side="left")
        if act.get("mode"):
            ttk.Label(head, text="   mode %s" % act["mode"],
                      style="Muted.TLabel").pack(side="left")
        if act.get("freq"):
            ttk.Label(head, text="   %s" % act["freq"],
                      style="Muted.TLabel").pack(side="left")

        # --- mutual windows ---
        ttk.Label(self, text="Mutual windows (both stations see the "
                             "satellite)", style="TLabel").pack(
            anchor="w", padx=14)
        cols = ("start", "end", "dur", "myel", "dxel")
        heads = ("Start", "End", "Duration", "My max el",
                 "DX max el")
        wrap, self.wtree = make_scrolled_tree(self, cols, show="headings",
                                              height=4)
        for c, h, w in zip(cols, heads, (170, 110, 100, 100, 100)):
            self.wtree.heading(c, text=h)
            self.wtree.column(c, width=w, anchor="w" if c == "start"
                              else "center")
        wrap.pack(fill="x", expand=False, padx=12, pady=4)
        for wm in self.windows:
            self.wtree.insert("", "end", values=(
                fmt_utc(wm["start"], "%Y-%m-%d %H:%M:%S"),
                fmt_utc(wm["end"], "%H:%M:%S"),
                fmt_hms(wm["end"] - wm["start"]),
                "%.0f\u00b0" % wm["my_max_el"],
                "%.0f\u00b0" % wm["dx_max_el"]))
        if self.wtree.get_children():
            self.wtree.selection_set(self.wtree.get_children()[0])
        self.wtree.bind("<<TreeviewSelect>>", lambda _e: self._rebuild())

        # --- sky tracks for the selected window ---
        # A mutual window is a geometry question; two polar plots answer it far
        # faster than a start/end pair. Left is this station, right is the
        # activator, with the mutually-visible arc highlighted on both.
        polar = ttk.Frame(self, style="TFrame")
        polar.pack(fill="both", expand=False, padx=12, pady=(4, 0))
        self.my_panel = MplPanel(polar, figsize=(3.1, 3.1), polar=True)
        self.my_panel.widget.pack(side="left", expand=True)
        self.dx_panel = MplPanel(polar, figsize=(3.1, 3.1), polar=True)
        self.dx_panel.widget.pack(side="left", expand=True)

        # --- controls ---
        bar = ttk.Frame(self, style="TFrame")
        bar.pack(fill="x", padx=12, pady=(8, 2))
        ttk.Label(bar, text="Transponder:", style="TLabel").pack(side="left")
        self.tp_var = tk.StringVar()
        self.tp_box = ttk.Combobox(bar, textvariable=self.tp_var,
                                   state="readonly", width=30)
        self.tp_box.pack(side="left", padx=6)
        self.tp_box.bind("<<ComboboxSelected>>", lambda _e: self._rebuild())
        ttk.Label(bar, text="Mode:", style="TLabel").pack(side="left",
                                                          padx=(12, 2))
        self.mode_var = tk.StringVar(value=MODES[0][0])
        mb = ttk.Combobox(bar, textvariable=self.mode_var, state="readonly",
                          width=22, values=[m[0] for m in MODES])
        mb.pack(side="left")
        mb.bind("<<ComboboxSelected>>", lambda _e: self._rebuild())
        ttk.Label(bar, text="Anchor:", style="TLabel").pack(side="left",
                                                            padx=(12, 2))
        self.anchor_var = tk.StringVar(value=ANCHORS[1][0])
        ab = ttk.Combobox(bar, textvariable=self.anchor_var, state="readonly",
                          width=8, values=[a[0] for a in ANCHORS])
        ab.pack(side="left")
        ab.bind("<<ComboboxSelected>>", lambda _e: self._rebuild())
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Notes\u2026",
                   command=self._show_notes).pack(side="right", padx=6)

        self._seeded = ""
        self._seed_hz = 0
        self._seed_anchor = None
        self._seed_mode = None
        self.note = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.note, style="Muted.TLabel",
                  wraplength=940).pack(anchor="w", padx=14, pady=(2, 0))

        # --- doppler table ---
        dcols = ("t", "myrx", "mytx", "dxrx", "dxtx")
        dheads = ("UTC", "My RX", "My TX", "DX RX", "DX TX")
        dwrap, self.dtree = make_scrolled_tree(self, dcols, show="headings",
                                               height=12)
        for c, h, w in zip(dcols, dheads, (110, 150, 150, 150, 150)):
            self.dtree.heading(c, text=h)
            self.dtree.column(c, width=w, anchor="center")
        dwrap.pack(fill="both", expand=True, padx=12, pady=6)

        self._load_transponders()
        self._seed_from_activation()
        self._rebuild()

    # ---- helpers ----
    def _load_transponders(self):
        """Transponders of the ACTIVATION's satellite, not whatever was
        selected - the whole point is that the table matches this bird."""
        self._tps = []
        if self.sat is None:
            return
        self._tps = list(getattr(self.sat, "transponders", []) or [])
        # The Transponder attribute is `desc` - `description`/`name` do not
        # exist, so the label fell through to "?" for every entry.
        labels = [_tp_label(t) for t in self._tps]
        self.tp_box.configure(values=labels)
        if labels:
            self.tp_box.current(0)

    def _seed_from_activation(self):
        """Preselect the transponder the activation's frequency names.

        The operator has said which frequency they will be on; defaulting to
        the first transponder ignores that and can show the wrong passband.
        A downlink match fixes the downlink, an uplink match the uplink.
        """
        from ...engine import activations as ACT
        if self.sat is None or not self._tps:
            return
        idx, leg, hz = ACT.match_transponder(self.sat, self.act)
        if idx is None:
            if hz:
                self.note.set("Stated frequency %.4f MHz did not match a "
                              "two-way transponder." % (hz / 1e6))
            return
        self.tp_box.current(idx)
        tp = self._tps[idx]
        linear = False
        try:
            linear = bool(getattr(tp, "is_linear", False)) and \
                tp.bandwidth() > 0
        except Exception:
            linear = False
        if not linear:
            # An FM or single-channel transponder has no passband to move, so
            # a "fixed" mode cannot hold a dial anywhere meaningful - it would
            # just display the stated frequency plus that station's Doppler and
            # call it held. True rule is the honest reading: every dial tracks
            # its own station.
            self.mode_var.set(MODES[0][0])
            self._seeded = ("activation names %.4f MHz on the %s; %s is "
                            "single-channel, so every dial Doppler-tracks"
                            % (hz / 1e6, leg, _tp_label(tp)))
            return
        if leg == "downlink":
            self.mode_var.set(MODES[1][0])          # fixed downlink
            self.anchor_var.set(ANCHORS[2][0])      # DX RX
        else:
            self.mode_var.set(MODES[2][0])          # fixed uplink
            self.anchor_var.set(ANCHORS[3][0])      # DX TX
        self._seed_hz = hz
        self._seed_anchor = (DXD.DX_RX if leg == "downlink" else DXD.DX_TX)
        self._seed_mode = (DXD.FIXED_DL if leg == "downlink"
                           else DXD.FIXED_UL)
        self._seeded = "seeded from the activation: %.4f MHz (%s)" % (
            hz / 1e6, leg)

    def _selected_window(self):
        sel = self.wtree.selection()
        if not sel or not self.windows:
            return None
        idx = self.wtree.index(sel[0])
        return self.windows[idx] if idx < len(self.windows) else None

    def _show_notes(self):
        """The activation's own comment and detail fields.

        The feed carries a comment - what the activator is doing, which pass,
        any conditions - and there was no way to read it.
        """
        from tkinter import messagebox
        a = self.act
        lines = []
        for label, key in (("Satellite", "sat"), ("Callsign", "callsign"),
                           ("Grid", "grid"), ("Date", "date"),
                           ("Start", "start"), ("End", "end"),
                           ("Mode", "mode"), ("Frequency", "freq"),
                           ("Max elevation", "max_el")):
            val = a.get(key)
            if val:
                lines.append("%-14s %s" % (label + ":", val))
        comment = (a.get("comment") or "").strip()
        body = "\n".join(lines)
        if comment:
            body += "\n\nNotes:\n" + comment
        elif a.get("title"):
            body += "\n\n" + a["title"]
        messagebox.showinfo("Activation detail", body or "No detail.",
                            parent=self)

    def _draw_polars(self, wm):
        """Both stations' sky tracks for this window."""
        from ..reports import _draw_mutual_station_polar
        from ...engine.predict import Predictor
        for panel, site, title in ((self.my_panel, self.store.obs, "My sky"),
                                   (self.dx_panel, self.dx, "DX sky")):
            panel.fig.clf()
            ax = panel.fig.add_subplot(111, projection="polar")
            ax.set_facecolor("#0d1117")
            if wm is not None and self.sat is not None and site is not None:
                pred = Predictor()
                pred.set_site(site)
                if pred.set_sat(self.sat):
                    try:
                        _draw_mutual_station_polar(ax, pred, _W(wm))
                    except Exception:
                        pass
            ax.set_title(title, color=COL_MUTED, fontsize=9)
            panel.fig.tight_layout()
            panel.canvas.draw_idle()

    def _rebuild(self):
        self.dtree.delete(*self.dtree.get_children())
        wm = self._selected_window()
        self._draw_polars(wm)
        if wm is None:
            self.note.set("No mutual window to tabulate.")
            return
        if not self._tps:
            self.note.set("No transponder data for %s \u2014 update the "
                          "transponder database to get dial frequencies."
                          % getattr(self.sat, "name", "this satellite"))
            return
        tp = self._tps[max(0, self.tp_box.current())]
        mode = dict(MODES)[self.mode_var.get()]
        anchor = dict(ANCHORS)[self.anchor_var.get()]
        # If the activation named a frequency, solve the passband so the
        # ANCHORED dial actually reads it. Opening mid-passband and calling that
        # "seeded" leaves the dial wherever the transponder center happens to
        # fall - not on the frequency the operator said they would use.
        pb = 0
        seeded_now = (self._seed_hz and self._seed_anchor == anchor
                      and self._seed_mode == mode)
        if seeded_now:
            try:
                pb = DXD.solve_pb_for_dial(wm["start"], self.sat,
                                           self.store.obs, self.dx, tp,
                                           self._seed_hz, anchor, mode)
            except Exception:
                pb = 0
        else:
            try:
                if getattr(tp, "is_linear", False) and tp.bandwidth() > 0:
                    pb = int(tp.bandwidth() / 2)
            except Exception:
                pb = 0
        try:
            rows = DXD.dx_doppler_table(wm["start"], wm["end"], self.sat,
                                        self.store.obs, self.dx, tp, pb,
                                        mode=mode, anchor=anchor)
        except Exception as exc:
            self.note.set("Could not build the table: %s" % str(exc)[:90])
            return
        for t, my_rx, my_tx, dx_rx, dx_tx in rows:
            self.dtree.insert("", "end", values=(
                fmt_utc(t, "%H:%M:%S"),
                _mhz(my_rx), _mhz(my_tx), _mhz(dx_rx), _mhz(dx_tx)))
        if seeded_now:
            self.note.set("%s \u2014 the %s dial is held there; %d rows every "
                          "30 s across the window."
                          % (self._seeded, self.anchor_var.get(), len(rows)))
            return
        self.note.set(
            "%d rows every 30 s across the window. %s"
            % (len(rows),
               "Every dial Doppler-tracks its own station."
               if mode == DXD.TRUE_RULE else
               "The anchor dial (%s) is held in real RF; the passband drifts "
               "to absorb its Doppler and the other three follow."
               % self.anchor_var.get()))


class _W:
    """Adapter: the polar helper wants .start/.end attributes."""

    def __init__(self, wm):
        self.start = wm["start"]
        self.end = wm["end"]


def _tp_label(tp):
    """A readable transponder name from whatever the entry carries."""
    for attr in ("desc", "description", "name", "service", "mode"):
        val = getattr(tp, attr, None)
        if val:
            return str(val)
    up = getattr(tp, "uplink", None)
    dn = getattr(tp, "downlink", None)
    if up and dn:
        return "%.3f / %.3f MHz" % (up / 1e6, dn / 1e6)
    return "transponder"


def _mhz(hz):
    try:
        return "%.4f MHz" % (float(hz) / 1e6)
    except (TypeError, ValueError):
        return "--"
