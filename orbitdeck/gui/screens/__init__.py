"""
screens package entry - screen factory + base classes + shared helpers.

Each screen owns a ttk Frame. The factory make_screen(key, parent, app) returns
the right screen instance. Visual screens embed matplotlib via MplPanel.
"""

import math
import datetime as dt

import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

COL_BG = "#0d1117"
COL_PANEL = "#161b22"
COL_ACCENT = "#2f81f7"
COL_ACCENT2 = "#3fb950"
COL_WARN = "#d29922"
COL_TEXT = "#e6edf3"
COL_MUTED = "#8b949e"
COL_GRID = "#30363d"
FONT_MONO = ("DejaVu Sans Mono", 10)
FONT_BIG = ("DejaVu Sans Mono", 22, "bold")
FONT_H = ("DejaVu Sans", 13, "bold")


def fmt_hms(seconds):
    seconds = int(max(0, seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return "%dh%02dm%02ds" % (h, m, s)
    return "%dm%02ds" % (m, s)


def fmt_utc(unix, fmt="%Y-%m-%d %H:%M:%S"):
    return dt.datetime.fromtimestamp(unix, dt.timezone.utc).strftime(fmt)


def now_unix():
    return dt.datetime.now(dt.timezone.utc).timestamp()


def compass(az):
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[int((az % 360) / 22.5 + 0.5) % 16]


class Screen:
    """Base screen. Subclasses build into self.frame and override hooks."""
    live = False

    def __init__(self, parent, app):
        self.app = app
        self.store = app.store
        self.frame = ttk.Frame(parent, style="TFrame")
        self.build()

    def build(self):
        pass

    def on_show(self):
        pass

    def on_hide(self):
        pass

    def on_tick(self, now_dt):
        pass

    # helpers
    def header(self, text):
        h = ttk.Label(self.frame, text=text, style="H.TLabel")
        h.pack(side="top", anchor="w", padx=16, pady=(14, 6))
        return h

    def sat_header(self, text):
        """Header for screens that act on the currently selected satellite.

        Shows the screen title with a live badge naming the selected satellite,
        so it's obvious which bird the page applies to. Call self.refresh_sat_
        header() from on_show() to keep the name current."""
        bar = ttk.Frame(self.frame, style="TFrame")
        bar.pack(side="top", anchor="w", fill="x", padx=16, pady=(14, 6))
        ttk.Label(bar, text=text, style="H.TLabel").pack(side="left")
        self._sat_badge = tk.Label(
            bar, text="", bg=COL_BG, fg=COL_ACCENT,
            font=("DejaVu Sans", 12, "bold"))
        self._sat_badge.pack(side="left", padx=(12, 0), pady=(2, 0))
        self._ds_badge = tk.Label(
            bar, text="", bg=COL_BG, fg=COL_WARN,
            font=("DejaVu Sans", 9))
        self._ds_badge.pack(side="left", padx=(10, 0), pady=(3, 0))
        # a "Report..." action is offered on every satellite-specific screen so
        # a printable PDF (analysis + passes + EQX) is always one click away
        ttk.Button(bar, text="Report\u2026",
                   command=self.make_report).pack(side="right", padx=(0, 4))
        self.refresh_sat_header()
        return bar

    def make_report(self):
        """Generate a printable PDF report for the selected satellite. Shared by
        all satellite screens via the sat_header bar."""
        s = self.sat()
        if not s:
            return
        from tkinter import filedialog, messagebox
        from ..reports import generate_satellite_report
        default = "report_%s.pdf" % s.name.replace("/", "-").replace(" ", "_")
        path = filedialog.asksaveasfilename(
            title="Save satellite report",
            defaultextension=".pdf",
            initialfile=default,
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_satellite_report(path, self.store, s)
        except Exception as e:
            messagebox.showerror("Report", "Could not generate report:\n%s" % e)
            return
        self.app.set_status("Saved report: %s" % path)
        messagebox.showinfo(
            "Report",
            "Saved a printable report for %s, covering orbital analysis, the "
            "next passes from your station, and the equator-crossing "
            "schedule." % s.name)

    def refresh_sat_header(self):
        badge = getattr(self, "_sat_badge", None)
        if badge is None:
            return
        s = self.sat()
        if s:
            badge.configure(text="\u25b8 %s" % s.name, fg=COL_ACCENT)
        else:
            badge.configure(text="\u25b8 no satellite selected", fg=COL_WARN)
        ds = getattr(self, "_ds_badge", None)
        if ds is not None:
            if s and self.store.pred.deepspace_approximate():
                ds.configure(text="\u26a0 deep-space orbit \u2014 reduced "
                                  "accuracy (install 'sgp4' for full SDP4)")
            else:
                ds.configure(text="")

    def pred(self):
        return self.store.pred

    def sat(self):
        return self.store.selected_sat()

    def make_oscarlocator_pdf(self):
        """Interactive 'Make printable OSCARLOCATOR' workflow shared by every
        screen that offers the export (Track and the OSCARLOCATOR Simulator),
        so both behave identically: pick the base-map style, choose whether the
        footprint is drawn on the QTH map, save, then show tailored print
        instructions."""
        s = self.sat()
        if not s:
            return
        from tkinter import filedialog, messagebox
        from ..oscarlocator import generate_oscarlocator_pdf
        # choose the base-map style: polar (generic, PE1RAH OSCARLATOR) or a
        # personalised map centred on the station
        polar = messagebox.askyesno(
            "OSCARLOCATOR base map",
            "Choose the base map style:\n\n"
            "\u2022 YES \u2014 Polar map (North/South-pole-centred, generic). The "
            "classic OSCARLATOR sheet that works for any QTH using the "
            "equator-crossing list.\n\n"
            "\u2022 NO \u2014 QTH-centred map, personalised to your station "
            "(azimuth/range from your location).")
        # optional: draw the footprint right on the base map at the QTH, giving a
        # 2-page set (map+footprint, then path arc) instead of separate sheets
        fp_on_qth = messagebox.askyesno(
            "Footprint placement",
            "Draw the satellite footprint directly on the base map at your "
            "station?\n\n"
            "\u2022 YES \u2014 2-page set: the map already shows the footprint at "
            "your QTH (one less transparency to align).\n\n"
            "\u2022 NO \u2014 3-page set: the footprint prints on a separate "
            "transparency you place over the map.")
        projection = "polar-auto" if polar else "qth"
        suffix = "polar" if polar else "qth"
        if fp_on_qth:
            suffix += "_fpqth"
        default = "oscarlocator_%s_%s.pdf" % (
            s.name.replace("/", "-").replace(" ", "_"), suffix)
        path = filedialog.asksaveasfilename(
            title="Save OSCARLOCATOR PDF",
            defaultextension=".pdf",
            initialfile=default,
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_oscarlocator_pdf(path, self.store, s,
                                      projection=projection,
                                      footprint_on_qth=fp_on_qth)
        except Exception as e:
            messagebox.showerror("OSCARLOCATOR", "Could not generate PDF:\n%s"
                                 % e)
            return
        self.app.set_status("Saved OSCARLOCATOR PDF: %s" % path)
        if fp_on_qth:
            detail = ("Page 1 (base map with footprint at your QTH): print on "
                      "paper or card.\nPage 2 (orbit path arc): print on "
                      "transparency film.\n\nThe footprint is already on the "
                      "map; use the path overlay to see when the satellite "
                      "enters it.")
        elif polar:
            detail = ("Page 1 (polar base map): print on paper or card.\n"
                      "Pages 2 & 3 (footprint + orbit overhead): print on "
                      "transparency film.\n\nLay the overlays on the base map "
                      "with centres aligned and rotate to the equator-crossing "
                      "longitude (see the Orbital Analysis \u2192 Crossings List).")
        else:
            detail = ("Page 1 (base map): print on paper or card.\n"
                      "Pages 2 & 3 (footprint + path arc): print on "
                      "transparency film.\n\nPin the overlays through the centre "
                      "cross over your station on the base map.")
        messagebox.showinfo(
            "OSCARLOCATOR",
            "Saved an OSCARLOCATOR PDF for %s.\n\n%s" % (s.name, detail))


class MplPanel:
    """A matplotlib Figure embedded in a Tk frame with the dark theme."""

    def __init__(self, parent, figsize=(6, 5), polar=False, dpi=100):
        self.fig = Figure(figsize=figsize, dpi=dpi, facecolor=COL_PANEL)
        if polar:
            self.ax = self.fig.add_subplot(111, projection="polar")
        else:
            self.ax = self.fig.add_subplot(111)
        self._style_axes()
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.widget = self.canvas.get_tk_widget()
        self.widget.configure(bg=COL_PANEL, highlightthickness=0)

    def _style_axes(self):
        ax = self.ax
        ax.set_facecolor(COL_PANEL)
        for spine in ax.spines.values():
            spine.set_color(COL_GRID)
        ax.tick_params(colors=COL_MUTED, labelsize=8)
        ax.title.set_color(COL_TEXT)
        try:
            ax.xaxis.label.set_color(COL_MUTED)
            ax.yaxis.label.set_color(COL_MUTED)
        except Exception:
            pass

    def clear(self, polar=False):
        self.fig.clf()
        if polar:
            self.ax = self.fig.add_subplot(111, projection="polar")
        else:
            self.ax = self.fig.add_subplot(111)
        self._style_axes()

    def draw(self):
        self.canvas.draw_idle()

    def pack(self, **kw):
        self.widget.pack(**kw)


class KVPanel:
    """A grouped key/value readout with aligned columns.

    Build content by calling section()/row()/note() between begin() and end().
    Rows are matched by (label) within their section across refreshes, so live
    pages update text/color IN PLACE instead of destroying and recreating
    widgets every tick -- that's what eliminates the flicker/blink. When the set
    of rows changes (e.g. switching pages), stale widgets are pruned at end().
    """

    def __init__(self, parent, label_width=15):
        self.outer = tk.Frame(parent, bg=COL_PANEL, highlightthickness=0)
        self.label_width = label_width
        self._body = tk.Frame(self.outer, bg=COL_PANEL)
        self._body.pack(fill="both", expand=True, padx=4, pady=4)
        # cache of built widgets keyed by a stable id; reused across rebuilds
        self._cache = {}         # key -> dict(kind, frame, widgets...)
        self._order = []         # keys touched this pass, in order
        self._packed = []        # keys currently packed, in order
        self._seq = 0            # disambiguates duplicate labels/sections

    def pack(self, **kw):
        self.outer.pack(**kw)

    def begin(self):
        self._order = []
        self._seq = 0

    def _key(self, kind, ident):
        self._seq += 1
        # include a running index so identical labels in different positions
        # stay distinct and stable as long as call order is stable
        return "%s::%s::%d" % (kind, ident, self._seq)

    def section(self, title):
        key = self._key("section", title)
        self._order.append(key)
        ent = self._cache.get(key)
        if ent is None:
            f = tk.Frame(self._body, bg=COL_PANEL)
            lbl = tk.Label(f, text=title.upper(), bg=COL_PANEL, fg=COL_ACCENT,
                           font=("DejaVu Sans", 9, "bold"), anchor="w")
            lbl.pack(side="left", padx=(8, 0))
            line = tk.Frame(self._body, bg=COL_GRID, height=1)
            ent = {"kind": "section", "frame": f, "line": line, "label": lbl}
            self._cache[key] = ent
        else:
            ent["label"].configure(text=title.upper())
        return key

    def row(self, label, value, color=None, big=False):
        key = self._key("row", label)
        self._order.append(key)
        ent = self._cache.get(key)
        font = ("DejaVu Sans Mono", 15, "bold") if big else FONT_MONO
        if ent is None:
            f = tk.Frame(self._body, bg=COL_PANEL)
            lab = tk.Label(f, text=label, bg=COL_PANEL, fg=COL_MUTED,
                           font=FONT_MONO, width=self.label_width, anchor="w")
            lab.pack(side="left")
            val = tk.Label(f, text=value, bg=COL_PANEL, fg=color or COL_TEXT,
                           font=font, anchor="w")
            val.pack(side="left")
            ent = {"kind": "row", "frame": f, "lab": lab, "val": val,
                   "big": big}
            self._cache[key] = ent
        else:
            # update in place; only touch attributes that changed
            if ent["lab"].cget("text") != label:
                ent["lab"].configure(text=label)
            if ent["val"].cget("text") != str(value):
                ent["val"].configure(text=value)
            newfg = color or COL_TEXT
            if ent["val"].cget("fg") != newfg:
                ent["val"].configure(fg=newfg)
            if ent.get("big") != big:
                ent["val"].configure(font=font)
                ent["big"] = big
        return key

    def note(self, text, color=None):
        key = self._key("note", text[:40])
        self._order.append(key)
        ent = self._cache.get(key)
        if ent is None:
            lbl = tk.Label(self._body, text=text, bg=COL_PANEL,
                           fg=color or COL_MUTED, font=("DejaVu Sans", 9),
                           anchor="w", justify="left", wraplength=560)
            ent = {"kind": "note", "frame": lbl}
            self._cache[key] = ent
        else:
            ent["frame"].configure(text=text, fg=color or COL_MUTED)
        return key

    def end(self):
        # prune widgets that weren't touched this pass
        touched = set(self._order)
        pruned = False
        for key in list(self._cache.keys()):
            if key not in touched:
                ent = self._cache.pop(key)
                ent["frame"].destroy()
                if ent.get("line") is not None:
                    ent["line"].destroy()
                pruned = True

        # Only re-pack when the set/order of rows actually changed. On a live
        # page the layout is identical every tick, and pack_forget()+pack() each
        # time forces a full geometry relayout -- which is slow on macOS (Aqua)
        # and makes the text updates look choppy. Skipping it leaves the in-place
        # configure() calls to refresh the values smoothly.
        if not pruned and self._order == self._packed:
            return

        for ent in self._cache.values():
            ent["frame"].pack_forget()
            if ent.get("line") is not None:
                ent["line"].pack_forget()
        for key in self._order:
            ent = self._cache.get(key)
            if not ent:
                continue
            if ent["kind"] == "section":
                ent["frame"].pack(fill="x", pady=(10, 2))
                ent["line"].pack(fill="x", padx=8, pady=(0, 4))
            elif ent["kind"] == "row":
                ent["frame"].pack(fill="x", padx=8, pady=1)
            else:
                ent["frame"].pack(fill="x", padx=8, pady=(6, 2))
        self._packed = list(self._order)


def make_screen(key, parent, app):
    from . import (home, track, passes, passdetail, groundtrack,
                   orbit, illum, sunmoon, mutual, tenday, satellites, location,
                   grids, spacewx, oscarsim)
    mapping = {
        "home": home.HomeScreen,
        "track": track.TrackScreen,
        "passes": passes.PassesScreen,
        "passdetail": passdetail.PassDetailScreen,
        "groundtrack": groundtrack.GroundTrackScreen,
        "orbit": orbit.OrbitScreen,
        "illum": illum.IllumScreen,
        "sunmoon": sunmoon.SunMoonScreen,
        "mutual": mutual.MutualScreen,
        "tenday": tenday.TenDayScreen,
        "satellites": satellites.SatellitesScreen,
        "location": location.LocationScreen,
        "grids": grids.GridsScreen,
        "spacewx": spacewx.SpaceWxScreen,
        "oscarsim": oscarsim.OscarSimScreen,
    }
    cls = mapping[key]
    return cls(parent, app)
