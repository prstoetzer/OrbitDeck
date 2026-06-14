"""
tenday.py - multi-day pass progression for the SELECTED satellite.

Shows, day by day, every pass of the current satellite over the next N days
(default 10), with a 24-hour timeline bar per day where each pass is drawn at
its time-of-day, its width = duration, shaded by max elevation. The whole thing
is vertically scrollable so you can keep adding days and scroll through them.
"""

import math
import datetime as dt
import tkinter as tk
from tkinter import ttk

from . import (Screen, COL_BG, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, FONT_MONO,
               fmt_hms, fmt_utc, now_unix, compass)


def _el_color(el):
    # low passes muted blue -> high passes bright green
    if el >= 45:
        return COL_ACCENT2
    if el >= 20:
        return COL_ACCENT
    return "#3b5ba5"


class TenDayScreen(Screen):
    def build(self):
        self.header("Multi-Day Pass Progression")
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(bar, text="Days:", style="TLabel").pack(side="left")
        self.days = tk.IntVar(value=10)
        for v in (5, 10, 14, 21):
            ttk.Radiobutton(bar, text=str(v), value=v, variable=self.days,
                            command=self._reload).pack(side="left", padx=2)
        ttk.Label(bar, text="   Min el:", style="TLabel").pack(side="left")
        self.minel = tk.IntVar(value=int(self.store.min_el))
        for v in (0, 5, 10, 20):
            ttk.Radiobutton(bar, text="%d\u00b0" % v, value=v, variable=self.minel,
                            command=self._reload).pack(side="left", padx=2)
        ttk.Button(bar, text="Refresh", command=self._reload).pack(side="left",
                                                                   padx=10)
        self.info = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info, style="Muted.TLabel").pack(
            anchor="w", padx=16)

        # scrollable canvas holding per-day rows
        outer = ttk.Frame(self.frame, style="Panel.TFrame")
        outer.pack(fill="both", expand=True, padx=12, pady=8)
        self.canvas = tk.Canvas(outer, bg=COL_PANEL, highlightthickness=0)
        self.vsb = ttk.Scrollbar(outer, orient="vertical",
                                 command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas, style="Panel.TFrame")
        self._win = self.canvas.create_window((0, 0), window=self.inner,
                                              anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))
        # mouse wheel scrolling (Windows/macOS and Linux)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind_all(seq, self._on_wheel)

    def on_hide(self):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(seq)

    def on_show(self):
        # (re)bind wheel when shown
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind_all(seq, self._on_wheel)
        self.minel.set(int(self.store.min_el))
        self._reload()

    def _on_wheel(self, e):
        if getattr(e, "num", None) == 4:
            self.canvas.yview_scroll(-1, "units")
        elif getattr(e, "num", None) == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def _reload(self):
        for w in self.inner.winfo_children():
            w.destroy()
        s = self.sat()
        if not s:
            self.info.set("No satellite selected.")
            return
        self.store.min_el = float(self.minel.get())
        self.store.save_config()
        t0 = now_unix()
        ndays = self.days.get()
        passes = self.pred().predict_passes(t0, self.store.min_el, 400,
                                            t0 + ndays * 86400)
        # group passes by UTC calendar day
        by_day = {}
        for p in passes:
            day = dt.datetime.fromtimestamp(
                p.aos, dt.timezone.utc).strftime("%Y-%m-%d")
            by_day.setdefault(day, []).append(p)

        start_day = dt.datetime.fromtimestamp(t0, dt.timezone.utc).date()
        for i in range(ndays):
            day_date = start_day + dt.timedelta(days=i)
            key = day_date.strftime("%Y-%m-%d")
            self._add_day_row(day_date, by_day.get(key, []))

        self.info.set("%s \u2014 %d passes over %d days (min %.0f\u00b0). "
                      "Scroll for more days." %
                      (s.name, len(passes), ndays, self.store.min_el))

    def _add_day_row(self, day_date, day_passes):
        row = ttk.Frame(self.inner, style="Panel.TFrame")
        row.pack(fill="x", padx=8, pady=3)

        # left label: weekday + date + count
        lbl = ttk.Frame(row, style="Panel.TFrame")
        lbl.pack(side="left", fill="y", padx=(4, 8))
        ttk.Label(lbl, text=day_date.strftime("%a"), style="Panel.TLabel",
                  font=("DejaVu Sans", 11, "bold")).pack(anchor="w")
        ttk.Label(lbl, text=day_date.strftime("%m-%d"),
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Label(lbl, text="%d pass%s" % (len(day_passes),
                                           "" if len(day_passes) == 1 else "es"),
                  style="Muted.TLabel").pack(anchor="w")

        # 24h timeline canvas
        c = tk.Canvas(row, bg=COL_BG, height=54, highlightthickness=0)
        c.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=4)
        c.bind("<Configure>",
               lambda e, cv=c, dp=day_passes, dd=day_date:
               self._draw_timeline(cv, dp, dd))
        # draw once now (Configure also redraws on resize)
        self.frame.after(10, lambda cv=c, dp=day_passes, dd=day_date:
                         self._draw_timeline(cv, dp, dd))

    def _draw_timeline(self, c, day_passes, day_date):
        c.delete("all")
        w = c.winfo_width() or 700
        h = 54
        pad = 6
        usable = w - 2 * pad
        # hour gridlines + labels
        for hr in range(0, 25, 3):
            x = pad + usable * hr / 24.0
            c.create_line(x, pad, x, h - pad, fill=COL_GRID)
            if hr < 24:
                c.create_text(x + 2, h - 4, text="%02d" % hr, anchor="sw",
                              fill=COL_MUTED, font=("DejaVu Sans", 7))
        day_start = dt.datetime(day_date.year, day_date.month, day_date.day,
                                tzinfo=dt.timezone.utc).timestamp()
        # each pass as a bar
        for p in day_passes:
            a = max(0.0, (p.aos - day_start) / 86400.0)
            b = min(1.0, (p.los - day_start) / 86400.0)
            x0 = pad + usable * a
            x1 = pad + usable * b
            if x1 - x0 < 3:
                x1 = x0 + 3
            col = _el_color(p.max_el)
            c.create_rectangle(x0, pad + 2, x1, h - 16, fill=col, outline="")
            # elevation label if wide enough
            if x1 - x0 > 26:
                c.create_text((x0 + x1) / 2, pad + 9,
                              text="%.0f\u00b0" % p.max_el, fill="#0d1117",
                              font=("DejaVu Sans", 7, "bold"))
            # tooltip on hover
            tag = "p%d" % int(p.aos)
            c.create_rectangle(x0, pad + 2, x1, h - 16, fill="", outline="",
                               tags=(tag,))
            tip = "%s  AOS %s  max %.0f\u00b0  %s  %s\u2192%s" % (
                day_date.strftime("%a"), fmt_utc(p.aos, "%H:%M:%S"),
                p.max_el, fmt_hms(p.los - p.aos),
                compass(p.az_aos), compass(p.az_los))
            c.tag_bind(tag, "<Enter>",
                       lambda e, txt=tip: self.app.set_status(txt))
