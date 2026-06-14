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


def make_screen(key, parent, app):
    from . import (track, passes, passdetail, polar, worldmap, groundtrack,
                   orbit, illum, sunmoon, mutual, tenday, satellites, location)
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
    }
    cls = mapping[key]
    return cls(parent, app)
