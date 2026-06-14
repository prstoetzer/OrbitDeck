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

    def pred(self):
        return self.store.pred

    def sat(self):
        return self.store.selected_sat()


class MplPanel:
    """A matplotlib Figure embedded in a Tk frame with the dark theme."""

    def __init__(self, parent, figsize=(6, 5), polar=False):
        self.fig = Figure(figsize=figsize, dpi=100, facecolor=COL_PANEL)
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
    """A scrollable, grouped key/value readout with aligned columns.

    Build content by calling section()/row()/note() between begin() and end().
    Values can be colored (e.g. accent for headline figures, warn for cautions).
    Renders as a clean card instead of a raw text dump.
    """

    def __init__(self, parent, label_width=15):
        self.outer = tk.Frame(parent, bg=COL_PANEL, highlightthickness=0)
        self.label_width = label_width
        self._rows = []          # live tk widgets to clear on rebuild
        self._body = tk.Frame(self.outer, bg=COL_PANEL)
        self._body.pack(fill="both", expand=True, padx=4, pady=4)

    def pack(self, **kw):
        self.outer.pack(**kw)

    def begin(self):
        for w in self._rows:
            w.destroy()
        self._rows = []

    def section(self, title):
        f = tk.Frame(self._body, bg=COL_PANEL)
        f.pack(fill="x", pady=(10, 2))
        tk.Label(f, text=title.upper(), bg=COL_PANEL, fg=COL_ACCENT,
                 font=("DejaVu Sans", 9, "bold"), anchor="w").pack(
            side="left", padx=(8, 0))
        line = tk.Frame(self._body, bg=COL_GRID, height=1)
        line.pack(fill="x", padx=8, pady=(0, 4))
        self._rows.append(f)
        self._rows.append(line)

    def row(self, label, value, color=None, big=False):
        f = tk.Frame(self._body, bg=COL_PANEL)
        f.pack(fill="x", padx=8, pady=1)
        tk.Label(f, text=label, bg=COL_PANEL, fg=COL_MUTED,
                 font=FONT_MONO, width=self.label_width, anchor="w").pack(
            side="left")
        tk.Label(f, text=value, bg=COL_PANEL, fg=color or COL_TEXT,
                 font=("DejaVu Sans Mono", 15, "bold") if big else FONT_MONO,
                 anchor="w").pack(side="left")
        self._rows.append(f)

    def note(self, text, color=None):
        lbl = tk.Label(self._body, text=text, bg=COL_PANEL,
                       fg=color or COL_MUTED, font=("DejaVu Sans", 9),
                       anchor="w", justify="left", wraplength=560)
        lbl.pack(fill="x", padx=8, pady=(6, 2))
        self._rows.append(lbl)

    def end(self):
        pass


def make_screen(key, parent, app):
    from . import (track, passes, passdetail, polar, worldmap, groundtrack,
                   orbit, illum, sunmoon, mutual, tenday, satellites, location,
                   grids, spacewx)
    mapping = {
        "track": track.TrackScreen,
        "passes": passes.PassesScreen,
        "passdetail": passdetail.PassDetailScreen,
        "polar": polar.PolarScreen,
        "worldmap": worldmap.WorldMapScreen,
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
    }
    cls = mapping[key]
    return cls(parent, app)
