"""radio.py - link budget and the Doppler tuning playbook.

Link budget: free-space path loss, propagation delay, and an estimated received
power from user-supplied EIRP / gains, for the current geometry.

Doppler playbook: a per-pass table of corrected RX/TX frequencies at chosen
intervals, for printing or export. For a linear transponder worked full duplex,
the operator can hold one leg fixed (uplink OR downlink) and the table applies
the round-trip correction so they keep hearing themselves (see CardSat v0.9.16).
"""

import tkinter as tk
from tkinter import ttk

from . import (Screen, KVPanel, TabBar, COL_PANEL, COL_TEXT, COL_MUTED,
               COL_ACCENT, COL_WARN, now_unix, fmt_utc, make_scrolled_tree)
from ...engine import linkbudget as LB
from .. import exports as EX


class RadioScreen(Screen):
    def build(self):
        self.sat_header("Radio \u2014 Link Budget & Doppler Playbook")
        # shared upcoming-pass picker: both tabs plan against the chosen pass
        picker = ttk.Frame(self.frame, style="TFrame")
        picker.pack(fill="x", padx=12, pady=(0, 2))
        ttk.Label(picker, text="Plan for pass:", style="TLabel").pack(
            side="left")
        self._pass_var = tk.StringVar()
        self._pass_combo = ttk.Combobox(picker, textvariable=self._pass_var,
                                        state="readonly", width=46)
        self._pass_combo.pack(side="left", padx=6)
        self._pass_combo.bind("<<ComboboxSelected>>", self._on_pass_change)
        ttk.Button(picker, text="Refresh passes",
                   command=self._reload_passes).pack(side="left", padx=4)
        self._passes = []          # parallel list of PassPredict
        self._pass_index = 0

        tabs = TabBar(self.frame)
        tabs.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        self._tab_link = tabs.add("Link budget")
        self._tab_pb = tabs.add("Doppler playbook")
        self._build_link(self._tab_link)
        self._build_playbook(self._tab_pb)

    # ---- pass picker ----
    def _reload_passes(self):
        s = self.sat()
        self._passes = []
        if s:
            pred = self.pred()
            self._passes = pred.predict_passes(
                now_unix(), getattr(self.store, "min_el", 5.0), 12)
        labels = []
        for p in self._passes:
            labels.append("%s  \u2191%s  max el %.0f\u00b0  %.0f min"
                          % (fmt_utc(p.aos, "%a %m-%d %H:%M"),
                             fmt_utc(p.aos, "%H:%M"), p.max_el,
                             (p.los - p.aos) / 60.0))
        if not labels:
            labels = ["(no upcoming pass above min elevation)"]
        self._pass_combo.configure(values=labels)
        if self._pass_index >= len(self._passes):
            self._pass_index = 0
        self._pass_combo.current(self._pass_index if self._passes else 0)
        self._render_link()
        self._render_pb()

    def _on_pass_change(self, _evt=None):
        self._pass_index = self._pass_combo.current()
        self._pass_combo.selection_clear()
        self.frame.focus_set()
        self._render_link()
        self._render_pb()

    def _selected_pass(self):
        if self._passes and 0 <= self._pass_index < len(self._passes):
            return self._passes[self._pass_index]
        return None

    # ---- link budget ----
    def _build_link(self, parent):
        self._vars = {}

        def field(bar, lab, key, dflt, width=6):
            ttk.Label(bar, text=lab, style="TLabel").pack(side="left")
            v = tk.StringVar(value=dflt)
            e = ttk.Entry(bar, textvariable=v, width=width)
            e.pack(side="left", padx=(2, 10))
            v.trace_add("write", lambda *a: self._render_link())
            self._vars[key] = v

        # your ground station (drives the uplink, and your receive gain)
        row1 = ttk.Frame(parent, style="TFrame")
        row1.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Label(row1, text="Your station:", style="Muted.TLabel",
                  width=13, anchor="w").pack(side="left")
        field(row1, "TX power (W)", "pw", "5")
        field(row1, "TX gain (dBi)", "txg", "0")
        field(row1, "RX gain (dBi)", "rxg", "12")
        field(row1, "Line loss (dB)", "ll", "1.5")

        # the satellite (drives the downlink received power)
        row2 = ttk.Frame(parent, style="TFrame")
        row2.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(row2, text="Satellite:", style="Muted.TLabel",
                  width=13, anchor="w").pack(side="left")
        # default ~1 W transmitter, ~2 dBi (a simple monopole whip)
        field(row2, "TX power (W)", "spw", "1")
        field(row2, "Antenna gain (dBi)", "sg", "2")
        ttk.Label(row2, text="(\u2248 a simple monopole whip)",
                  style="Muted.TLabel").pack(side="left", padx=(0, 8))

        # passband-position control, shown only for a linear transponder
        self._pbbar = ttk.Frame(parent, style="TFrame")
        self._pbbar.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(self._pbbar, text="Passband position:",
                  style="TLabel").pack(side="left")
        self._pb_frac = tk.DoubleVar(value=50.0)   # percent across the passband
        self._pb_scale = ttk.Scale(self._pbbar, from_=0, to=100, style="Accent.Horizontal.TScale",
                                   orient="horizontal", variable=self._pb_frac,
                                   command=lambda _v: self._render_link())
        self._pb_scale.pack(side="left", fill="x", expand=True, padx=8)
        self._pb_lbl = tk.StringVar(value="")
        ttk.Label(self._pbbar, textvariable=self._pb_lbl,
                  style="Muted.TLabel").pack(side="left", padx=6)
        self._pbbar_visible = True

        # pass-time scrubber: evaluate the link geometry anywhere from AOS to LOS
        # (not just TCA), so the operator can see how range / path loss / Doppler
        # change through the pass. 0% = AOS, 100% = LOS; defaults to TCA.
        self._timebar = ttk.Frame(parent, style="TFrame")
        self._timebar.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(self._timebar, text="Time in pass:",
                  style="TLabel").pack(side="left")
        self._t_frac = tk.DoubleVar(value=-1.0)    # -1 => snap to TCA
        self._t_scale = ttk.Scale(self._timebar, from_=0, to=100, style="Accent.Horizontal.TScale",
                                  orient="horizontal", variable=self._t_frac,
                                  command=lambda _v: self._render_link())
        self._t_scale.pack(side="left", fill="x", expand=True, padx=8)
        self._t_lbl = tk.StringVar(value="")
        ttk.Label(self._timebar, textvariable=self._t_lbl,
                  style="Muted.TLabel").pack(side="left", padx=6)
        ttk.Button(self._timebar, text="TCA",
                   command=self._snap_tca).pack(side="left", padx=2)

        self.kv = KVPanel(parent, label_width=22)
        self.kv.pack(fill="both", expand=True, padx=8, pady=6)

    def _snap_tca(self):
        # re-centre the scrubber on closest approach
        self._t_frac.set(-1.0)
        self._render_link()

    def _show_pbbar(self, show):
        # keep the bar in place (preserving layout order); just enable/disable
        # the scale, and grey the label, when there's no linear passband
        state = "normal" if show else "disabled"
        try:
            self._pb_scale.configure(state=state)
        except Exception:
            pass
        if not show:
            self._pb_lbl.set("(linear transponder only)")

    def _fnum(self, key, dflt):
        try:
            return float(self._vars[key].get())
        except Exception:
            return dflt

    def _render_link(self):
        s = self.sat()
        self.kv.begin()
        if not s:
            self.kv.note("No satellite selected.")
            self.kv.end()
            return
        pred = self.pred()
        p = self._selected_pass()
        # choose the epoch to evaluate the geometry at. If a pass is selected,
        # the time-in-pass scrubber picks any instant from AOS to LOS; a value
        # of -1 snaps to TCA (closest approach / best-case geometry). Without a
        # selected pass we fall back to "now".
        if p is not None:
            frac = self._t_frac.get()
            if frac < 0:
                t = p.tca
                where = "TCA"
            else:
                frac = max(0.0, min(1.0, frac / 100.0))
                t = p.aos + (p.los - p.aos) * frac
                where = "T%+.1f min from AOS" % ((t - p.aos) / 60.0)
            look = pred.look(t)
            geo_head = "Geometry at %s (%s UTC)" % (where, fmt_utc(t, "%H:%M:%S"))
            self._t_lbl.set("%s  el %.0f\u00b0" % (fmt_utc(t, "%H:%M:%S"),
                                                   look.el))
            try:
                self._t_scale.configure(state="normal")
            except Exception:
                pass
        else:
            t = now_unix()
            look = pred.look(t)
            geo_head = "Geometry (now)"
            self._t_lbl.set("(no pass selected)")
            try:
                self._t_scale.configure(state="disabled")
            except Exception:
                pass
        rng = look.range_km
        if rng <= 0 or look.el < 0:
            self.kv.section("Geometry")
            self.kv.row("Satellite", "below horizon \u2014 showing nominal")
            rng = look.range_km or (look.alt_km or 700.0)
        s.transponders = getattr(s, "transponders", []) or []
        self.store.ensure_transponders(s)
        tp = self.store.selected_transponder(s)
        # passband position (linear transponders): 0..100% across the band
        is_linear = bool(tp and tp.is_linear and tp.bandwidth() > 0)
        self._show_pbbar(is_linear)
        if tp:
            if is_linear:
                frac = max(0.0, min(1.0, self._pb_frac.get() / 100.0))
                off = int(frac * tp.bandwidth())
                dl, ul = pred.passband_freqs(tp, off)
                self._pb_lbl.set("%.0f%% \u2014 DL %.4f MHz"
                                 % (self._pb_frac.get(), dl / 1e6))
            else:
                dl = tp.downlink_center() or 145_800_000
                ul = tp.uplink_center() or 0
        else:
            dl, ul = 145_800_000, 0
        if p is not None:
            self.kv.section("Pass")
            self.kv.row("AOS", "%s UTC" % fmt_utc(p.aos, "%a %m-%d %H:%M:%S"))
            self.kv.row("TCA", "%s UTC  (max el %.0f\u00b0)"
                        % (fmt_utc(p.tca, "%H:%M:%S"), p.max_el))
            self.kv.row("LOS", "%s UTC" % fmt_utc(p.los, "%H:%M:%S"))
            self.kv.row("Duration", "%.1f min" % ((p.los - p.aos) / 60.0))
        self.kv.section(geo_head)
        self.kv.row("Slant range", "%.0f km" % rng)
        self.kv.row("Elevation", "%.1f\u00b0" % look.el)
        self.kv.row("Range rate", "%+.3f km/s" % look.range_rate)
        self.kv.row("Propagation delay",
                    "%.2f ms (1-way)" % LB.propagation_delay_ms(rng))
        if tp:
            self.kv.row("Transponder", "%s [%s]"
                        % (tp.desc or "transponder", tp.kind()))
        self.kv.section("Downlink %.3f MHz" % (dl / 1e6))
        # on the downlink the SATELLITE is the transmitter; your station receives
        lbk = LB.link_budget(rng, dl, tx_power_w=self._fnum("spw", 1.0),
                             tx_gain_dbi=self._fnum("sg", 2.0),
                             rx_gain_dbi=self._fnum("rxg", 12),
                             line_loss_db=self._fnum("ll", 1.5))
        self.kv.row("Sat EIRP", "%.1f dBm" % lbk["eirp_dbm"])
        self.kv.row("Free-space path loss", "%.1f dB" % lbk["fspl_db"])
        self.kv.row("Est. received power", "%.1f dBm" % lbk["rx_power_dbm"])
        # Doppler at this instant on the downlink (what you'd actually hear)
        dop_dl = LB.doppler_shift_hz(dl, look.range_rate)
        self.kv.row("Downlink Doppler", "%+.0f Hz  (rx %.4f MHz)"
                    % (dop_dl, (dl + dop_dl) / 1e6))
        if ul:
            self.kv.section("Uplink %.3f MHz" % (ul / 1e6))
            # on the uplink YOUR station is the transmitter
            lbu = LB.link_budget(rng, ul, tx_power_w=self._fnum("pw", 5),
                                 tx_gain_dbi=self._fnum("txg", 0),
                                 rx_gain_dbi=0.0,
                                 line_loss_db=self._fnum("ll", 1.5))
            self.kv.row("Free-space path loss", "%.1f dB" % lbu["fspl_db"])
            self.kv.row("Your EIRP", "%.1f dBm" % lbu["eirp_dbm"])
        if p is not None:
            self.kv.note("Link budget shown at TCA (closest approach \u2014 the "
                         "best-case geometry of the pass). An estimate for pass "
                         "planning, not a calibrated measurement; override the "
                         "station parameters above.")
        else:
            self.kv.note("Estimate for pass planning, not a calibrated "
                         "measurement. Override station parameters above.")
        self.kv.end()

    # ---- Doppler playbook ----
    def _build_playbook(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Interval:", style="TLabel").pack(side="left")
        self._interval = tk.IntVar(value=60)
        for v in (30, 60, 120):
            ttk.Radiobutton(bar, text="%ds" % v, value=v,
                            variable=self._interval,
                            command=self._render_pb).pack(side="left")
        ttk.Label(bar, text="  Linear hold:", style="TLabel").pack(side="left")
        self._hold = tk.StringVar(value="downlink")
        ttk.Radiobutton(bar, text="Fixed downlink", value="downlink",
                        variable=self._hold, command=self._render_pb).pack(
            side="left")
        ttk.Radiobutton(bar, text="Fixed uplink", value="uplink",
                        variable=self._hold, command=self._render_pb).pack(
            side="left")
        ttk.Button(bar, text="Export CSV\u2026",
                   command=self._export_csv).pack(side="right", padx=2)
        ttk.Button(bar, text="Print sheet\u2026",
                   command=self._print_sheet).pack(side="right", padx=2)

        # passband-position control for linear transponders: the playbook is
        # built around the chosen spot in the passband, not just band centre, so
        # the RX/TX columns match where the operator is actually listening.
        self._pbbar2 = ttk.Frame(parent, style="TFrame")
        self._pbbar2.pack(fill="x", padx=8, pady=(0, 2))
        ttk.Label(self._pbbar2, text="Passband position:",
                  style="TLabel").pack(side="left")
        self._pb_frac2 = tk.DoubleVar(value=50.0)
        self._pb_scale2 = ttk.Scale(self._pbbar2, from_=0, to=100, style="Accent.Horizontal.TScale",
                                    orient="horizontal", variable=self._pb_frac2,
                                    command=lambda _v: self._render_pb())
        self._pb_scale2.pack(side="left", fill="x", expand=True, padx=8)
        self._pb_lbl2 = tk.StringVar(value="")
        ttk.Label(self._pbbar2, textvariable=self._pb_lbl2,
                  style="Muted.TLabel").pack(side="left", padx=6)

        cols = ("min", "az", "el", "rr", "rx", "tx")
        heads = ("Min", "Az", "El", "Range-rate (km/s)", "RX (MHz)",
                 "TX (MHz)")
        treewrap, self.tree = make_scrolled_tree(
            parent, cols, show="headings", height=16)
        widths = {"min": 70, "az": 70, "el": 70, "rr": 140, "rx": 130,
                  "tx": 130}
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="center")
        treewrap.pack(fill="both", expand=True, padx=8, pady=6)
        self.pbinfo = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.pbinfo,
                  style="Muted.TLabel").pack(anchor="w", padx=8, pady=(0, 6))
        self._pb_rows = []

    def on_show(self):
        self._reload_passes()

    def _next_pass(self):
        pred = self.pred()
        t = now_unix()
        ps = pred.predict_passes(t, getattr(self.store, "min_el", 5.0), 1)
        return ps[0] if ps else None

    def _build_pb_rows(self):
        s = self.sat()
        if not s:
            return [], None, ""
        self.store.ensure_transponders(s)
        tp = self.store.selected_transponder(s)
        pred = self.pred()
        is_lin = bool(tp and tp.is_linear)
        invert = bool(tp and tp.invert)
        # For a linear transponder, build the table around the selected spot in
        # the passband (so RX/TX match where you're actually tuned). For an FM
        # bird the passband control is meaningless, so fall back to the centre.
        if tp and is_lin and tp.bandwidth() > 0:
            frac = max(0.0, min(1.0, self._pb_frac2.get() / 100.0))
            off = int(frac * tp.bandwidth())
            dl, ul = pred.passband_freqs(tp, off)
            self._pb_scale2.configure(state="normal")
            self._pb_lbl2.set("%.0f%% \u2014 DL %.4f MHz"
                              % (self._pb_frac2.get(), dl / 1e6))
        else:
            dl = tp.downlink_center() if tp and tp.downlink_center() \
                else 145_800_000
            ul = tp.uplink_center() if tp and tp.uplink_center() else 0
            self._pb_scale2.configure(state="disabled")
            self._pb_lbl2.set("(linear transponder only)")
        p = self._selected_pass() or self._next_pass()
        if not p:
            return [], tp, "No upcoming pass in range."
        times, rrs, azels = [], [], []
        t = p.aos
        while t <= p.los:
            look = pred.look(t)
            times.append(t)
            rrs.append(look.range_rate)
            azels.append((look.az, look.el))
            t += self._interval.get()
        rows = LB.doppler_playbook_rows(
            times, rrs, dl, ul, is_linear=is_lin, invert=invert,
            hold=self._hold.get())
        # attach pointing (az/el) to each row -- doppler_playbook_rows preserves
        # input order, so the az/el samples line up one-to-one with the rows.
        for r, (az, el) in zip(rows, azels):
            r["az"] = az
            r["el"] = el
        label = (tp.desc or tp.kind()) if tp else "default"
        return rows, tp, label

    def _render_pb(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows, tp, label = self._build_pb_rows()
        self._pb_rows = rows
        if not rows:
            self.pbinfo.set(label)
            return
        t0 = rows[0]["t"]
        for r in rows:
            self.tree.insert("", "end", values=(
                "%.1f" % ((r["t"] - t0) / 60.0),
                "%.0f\u00b0" % r.get("az", 0.0),
                "%.0f\u00b0" % r.get("el", 0.0),
                "%+.3f" % r["range_rate"],
                "%.4f" % (r["rx_hz"] / 1e6),
                ("%.4f" % (r["tx_hz"] / 1e6)) if r["tx_hz"] else "\u2014"))
        mode = rows[0]["mode"]
        p = self._selected_pass()
        pass_txt = (("Pass %s UTC.  " % fmt_utc(p.aos, "%a %m-%d %H:%M"))
                    if p else "")
        self.pbinfo.set(
            "%sTransponder: %s   mode: %s   %d rows. For a linear bird, the "
            "'hold' choice fixes one leg and round-trip-corrects the other so "
            "you keep hearing yourself." % (pass_txt, label, mode, len(rows)))

    def _export_csv(self):
        s = self.sat()
        if not s or not self._pb_rows:
            return
        csv = EX.playbook_to_csv(self._pb_rows, s.name)
        self.save_text_dialog(
            csv, "doppler_%s.csv" % s.name.replace("/", "-").replace(" ", "_"),
            title="Export Doppler playbook", ext=".csv",
            filetypes=[("CSV", "*.csv")])

    def _print_sheet(self):
        s = self.sat()
        if not s or not self._pb_rows:
            return
        from tkinter import filedialog, messagebox
        from ..doppler_sheet import generate_doppler_sheet
        path = filedialog.asksaveasfilename(
            title="Print Doppler playbook", defaultextension=".pdf",
            initialfile="doppler_%s.pdf" % s.name.replace("/", "-").replace(
                " ", "_"),
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_doppler_sheet(path, s, self._pb_rows, self._hold.get())
        except Exception as e:
            messagebox.showerror("Doppler sheet", "Could not generate:\n%s" % e)
            return
        self.app.set_status("Saved Doppler sheet: %s" % path)
