"""
app.py - the OrbitDeck main window.

A Tkinter application with a navigation sidebar and a swappable content area.
Visual screens embed matplotlib. Designed to match the source device's analysis feature
set: Track, Passes, Pass Detail/Polar, World Map, Illumination, Orbital
Analysis (9 pages), Sun/Moon, Mutual Windows, Space Wx, Satellites, Location.
"""

import time
import datetime as dt
import threading

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .store import Store
from . import screens


# ---- dark "instrument" theme tuned to feel like the device ----
COL_BG = "#0d1117"
COL_PANEL = "#161b22"
COL_ACCENT = "#2f81f7"
COL_ACCENT2 = "#3fb950"
COL_WARN = "#d29922"
COL_TEXT = "#e6edf3"
COL_MUTED = "#8b949e"
COL_GRID = "#30363d"
FONT = ("DejaVu Sans", 10)
FONT_MONO = ("DejaVu Sans Mono", 10)
FONT_H = ("DejaVu Sans", 13, "bold")


NAV_ITEMS = [
    ("Track", "track"),
    ("Next Passes", "passes"),
    ("Pass Detail", "passdetail"),
    ("Polar", "polar"),
    ("World Map", "worldmap"),
    ("Ground Track", "groundtrack"),
    ("Orbital Analysis", "orbit"),
    ("Illumination", "illum"),
    ("Sun / Moon", "sunmoon"),
    ("Mutual Windows", "mutual"),
    ("Pass Progression", "tenday"),
    ("Satellites", "satellites"),
    ("Location", "location"),
]


class OrbitDeckApp:
    def __init__(self, root):
        self.root = root
        self.store = Store()
        self.current = None
        self.current_key = None
        self._screen_cache = {}

        root.title("OrbitDeck \u2014 Satellite Tracking & Orbital Analysis")
        root.geometry("1180x760")
        root.minsize(960, 640)
        root.configure(bg=COL_BG)

        self._init_style()
        self._build_layout()
        self.show("track")
        self._tick()

    def _init_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=COL_BG, foreground=COL_TEXT, font=FONT)
        st.configure("TFrame", background=COL_BG)
        st.configure("Panel.TFrame", background=COL_PANEL)
        st.configure("TLabel", background=COL_BG, foreground=COL_TEXT)
        st.configure("Panel.TLabel", background=COL_PANEL, foreground=COL_TEXT)
        st.configure("Muted.TLabel", background=COL_PANEL, foreground=COL_MUTED)
        st.configure("H.TLabel", background=COL_BG, foreground=COL_TEXT, font=FONT_H)
        st.configure("Mono.TLabel", background=COL_PANEL, foreground=COL_TEXT,
                     font=FONT_MONO)
        st.configure("TButton", background=COL_PANEL, foreground=COL_TEXT,
                     borderwidth=0, focusthickness=0, padding=6)
        st.map("TButton", background=[("active", COL_GRID)])
        st.configure("Nav.TButton", background=COL_BG, foreground=COL_TEXT,
                     anchor="w", padding=(14, 9), font=FONT)
        st.map("Nav.TButton", background=[("active", COL_PANEL)])
        st.configure("NavSel.TButton", background=COL_ACCENT, foreground="#ffffff",
                     anchor="w", padding=(14, 9), font=FONT)
        st.configure("Treeview", background=COL_PANEL, fieldbackground=COL_PANEL,
                     foreground=COL_TEXT, borderwidth=0, rowheight=24,
                     font=FONT_MONO)
        st.configure("Treeview.Heading", background=COL_GRID, foreground=COL_TEXT,
                     font=FONT)
        st.map("Treeview", background=[("selected", COL_ACCENT)])

    def _build_layout(self):
        # top bar
        top = ttk.Frame(self.root, style="Panel.TFrame")
        top.pack(side="top", fill="x")
        ttk.Label(top, text="  OrbitDeck", style="Panel.TLabel",
                  font=("DejaVu Sans", 15, "bold")).pack(side="left", pady=8)
        self.sat_var = tk.StringVar(value="\u2014")
        ttk.Label(top, textvariable=self.sat_var, style="Mono.TLabel").pack(
            side="left", padx=16)
        self.clock_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.clock_var, style="Mono.TLabel").pack(
            side="right", padx=16)
        ttk.Button(top, text="Update GP (online)",
                   command=self._update_online).pack(side="right", padx=6, pady=6)
        ttk.Button(top, text="Select Satellite\u2026",
                   command=self._quick_select).pack(side="right", padx=6, pady=6)

        # body: nav + content
        body = ttk.Frame(self.root)
        body.pack(side="top", fill="both", expand=True)

        nav = ttk.Frame(body, style="Panel.TFrame", width=180)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        self._nav_buttons = {}
        for label, key in NAV_ITEMS:
            b = ttk.Button(nav, text=label, style="Nav.TButton",
                           command=lambda k=key: self.show(k))
            b.pack(side="top", fill="x")
            self._nav_buttons[key] = b

        self.content = ttk.Frame(body, style="TFrame")
        self.content.pack(side="left", fill="both", expand=True)

        # status bar
        self.status_var = tk.StringVar(value="Ready.")
        status = ttk.Frame(self.root, style="Panel.TFrame")
        status.pack(side="bottom", fill="x")
        ttk.Label(status, textvariable=self.status_var, style="Muted.TLabel").pack(
            side="left", padx=10, pady=4)
        self.grid_var = tk.StringVar(value="")
        ttk.Label(status, textvariable=self.grid_var, style="Muted.TLabel").pack(
            side="right", padx=10, pady=4)

    # ---- navigation ----
    def show(self, key):
        if self.current is not None:
            self.current.on_hide()
            self.current.frame.pack_forget()
        for k, b in self._nav_buttons.items():
            b.configure(style="NavSel.TButton" if k == key else "Nav.TButton")
        scr = self._screen_cache.get(key)
        if scr is None:
            scr = screens.make_screen(key, self.content, self)
            self._screen_cache[key] = scr
        self.current = scr
        self.current_key = key
        scr.frame.pack(fill="both", expand=True)
        scr.on_show()

    # ---- live clock + active-screen refresh ----
    def _tick(self):
        now = dt.datetime.now(dt.timezone.utc)
        self.clock_var.set(now.strftime("%Y-%m-%d  %H:%M:%S UTC"))
        s = self.store.selected_sat()
        self.sat_var.set(s.name if s else "(no satellite)")
        self.grid_var.set("Grid %s  \u2022  %.3f, %.3f" %
                          (self.store.my_grid(), self.store.obs.lat,
                           self.store.obs.lon))
        if self.current is not None and getattr(self.current, "live", False):
            try:
                self.current.on_tick(now)
            except Exception as e:
                self.set_status("tick error: %s" % e)
        self.root.after(1000, self._tick)

    def set_status(self, text):
        self.status_var.set(text)

    # ---- toolbar actions ----
    def _quick_select(self):
        sats = self.store.db.sats
        if not sats:
            return
        win = tk.Toplevel(self.root)
        win.title("Select Satellite")
        win.configure(bg=COL_BG)
        win.geometry("360x460")
        lb = tk.Listbox(win, bg=COL_PANEL, fg=COL_TEXT, font=FONT_MONO,
                        selectbackground=COL_ACCENT, borderwidth=0,
                        highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=8, pady=8)
        order = sorted(range(len(sats)),
                       key=lambda i: (sats[i].norad not in self.store.favorites,
                                      sats[i].name))
        for i in order:
            s = sats[i]
            mark = "\u2605 " if s.norad in self.store.favorites else "  "
            lb.insert("end", "%s%-12s %5d" % (mark, s.name, s.norad))

        def choose(_=None):
            sel = lb.curselection()
            if sel:
                s = sats[order[sel[0]]]
                self.store.select(s.norad)
                self.store.save_config()
                if self.current:
                    self.current.on_show()
                win.destroy()
        lb.bind("<Double-Button-1>", choose)
        ttk.Button(win, text="Select", command=choose).pack(pady=6)

    def _update_online(self):
        def work():
            try:
                self.set_status("Updating GP catalog\u2026")
                n = self.store.update_gp_online(progress=self.set_status)
                self.set_status("Updated: %d satellites loaded." % n)
            except Exception as e:
                self.set_status("Update failed: %s" % e)
                self.root.after(0, lambda: messagebox.showerror(
                    "Update failed",
                    "Could not fetch GP data.\n\n%s\n\nThe app keeps working "
                    "with the cached/sample catalog." % e))
            self.root.after(0, lambda: self.current.on_show()
                            if self.current else None)
        threading.Thread(target=work, daemon=True).start()


def main():
    root = tk.Tk()
    OrbitDeckApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
