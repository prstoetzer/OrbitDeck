"""passes.py - upcoming passes for the selected satellite."""

import tkinter as tk
from tkinter import ttk

from . import (Screen, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT, COL_ACCENT2,
               FONT_MONO, fmt_hms, fmt_utc, now_unix, compass,
               make_scrolled_tree)


class PassesScreen(Screen):
    def build(self):
        self.sat_header("Next Passes")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16)
        ttk.Label(bar, text="Min elevation:", style="TLabel").pack(side="left")
        self.minel = tk.IntVar(value=int(self.store.min_el))
        for v in (0, 5, 10, 20, 30):
            ttk.Radiobutton(bar, text="%d\u00b0" % v, value=v, variable=self.minel,
                            command=self._reload).pack(side="left", padx=2)
        # the active minimum (which may be a custom value set in Settings) is
        # shown here so a non-preset value is visible
        self.minel_lbl = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.minel_lbl,
                  style="Muted.TLabel").pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="Print sky tracks (3 days)\u2026",
                   command=self._print_polar).pack(side="right")

        cols = ("day", "aos", "maxel", "dur", "los", "dir")
        heads = ("Day", "AOS (UTC)", "Max El", "Duration", "LOS", "Track")
        widths = {"day": 90, "aos": 90, "maxel": 90, "dur": 90, "los": 80,
                  "dir": 130}
        treewrap, self.tree = make_scrolled_tree(
            self.frame, cols, show="headings", height=18)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], minwidth=widths[c],
                             anchor="w" if c in ("day", "dir") else "center")
        # color tags for pass quality + zebra striping
        self.tree.tag_configure("hi", foreground=COL_ACCENT2)
        self.tree.tag_configure("vhi", foreground=COL_ACCENT)
        self.tree.tag_configure("odd", background=COL_PANEL)
        treewrap.pack(fill="both", expand=True, padx=16, pady=10)
        self.tree.bind("<Double-Button-1>", self._open_detail)
        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info, style="Muted.TLabel").pack(
            anchor="w", padx=16, pady=(0, 8))

    def on_show(self):
        # reflect the active minimum; presets snap the radio, custom values show
        # in the label only
        mv = self.store.min_el
        self.minel.set(int(mv) if mv in (0, 5, 10, 20, 30) else -1)
        self._sync_minel_label()
        self._reload()

    def _sync_minel_label(self):
        mv = self.store.min_el
        if mv in (0, 5, 10, 20, 30):
            self.minel_lbl.set("")
        else:
            self.minel_lbl.set("(custom: %g\u00b0 \u2014 set in Settings)" % mv)

    def _reload(self):
        # a preset radio overrides; -1 means "keep the custom value from Settings"
        sel = self.minel.get()
        if sel >= 0:
            self.store.min_el = float(sel)
            self.store.save_config()
        self._sync_minel_label()
        for i in self.tree.get_children():
            self.tree.delete(i)
        s = self.sat()
        if not s:
            self.info.set("No satellite selected.")
            return
        t = now_unix()
        passes = self.pred().predict_passes(t, self.store.min_el, 30,
                                            t + 7 * 86400)
        prev_day = None
        for i, p in enumerate(passes):
            day = fmt_utc(p.aos, "%a %m-%d")
            day_cell = "" if day == prev_day else day   # group by day
            prev_day = day
            tags = []
            if p.max_el >= 40:
                tags.append("vhi")
            elif p.max_el >= 20:
                tags.append("hi")
            if i % 2:
                tags.append("odd")
            self.tree.insert("", "end", values=(
                day_cell,
                fmt_utc(p.aos, "%H:%M:%S"),
                "%.0f\u00b0" % p.max_el,
                fmt_hms(p.los - p.aos),
                fmt_utc(p.los, "%H:%M:%S"),
                "%s \u2192 %s" % (compass(p.az_aos), compass(p.az_los)),
            ), tags=tuple(tags))
        self.info.set("%s \u2014 %d passes / 7 days (min %.0f\u00b0).  "
                      "Green \u2265 20\u00b0, blue \u2265 40\u00b0.  "
                      "Double-click for detail." %
                      (s.name, len(passes), self.store.min_el))
        self._passes = passes

    def _open_detail(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self._passes):
            self.app._screen_cache.pop("passdetail", None)
            self.app.show("passdetail")
            scr = self.app.current
            scr.set_pass(self._passes[idx])

    def _print_polar(self):
        s = self.sat()
        if not s:
            return
        from tkinter import filedialog, messagebox
        from ..reports import generate_polar_passes_report
        default = "skytracks_%s.pdf" % s.name.replace("/", "-").replace(
            " ", "_")
        path = filedialog.asksaveasfilename(
            title="Save sky-track report", defaultextension=".pdf",
            initialfile=default, filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_polar_passes_report(path, self.store, s, days=3)
        except Exception as e:
            messagebox.showerror("Report", "Could not generate report:\n%s" % e)
            return
        self.app.set_status("Saved sky-track report: %s" % path)
        messagebox.showinfo("Report", "Saved sky-track polar plots for every "
                            "pass of %s over the next 3 days." % s.name)
