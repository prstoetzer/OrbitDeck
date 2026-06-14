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
    ("Workable", "grids"),
    ("Space Wx", "spacewx"),
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

        # --- text entry: explicit field colors so typed text is visible ---
        st.configure("TEntry", fieldbackground=COL_PANEL, foreground=COL_TEXT,
                     insertcolor=COL_TEXT, bordercolor=COL_GRID,
                     lightcolor=COL_GRID, darkcolor=COL_GRID,
                     selectbackground=COL_ACCENT, selectforeground="#ffffff",
                     borderwidth=1, padding=4)
        st.map("TEntry",
               fieldbackground=[("focus", COL_PANEL), ("!focus", COL_PANEL)],
               foreground=[("focus", COL_TEXT), ("!focus", COL_TEXT)],
               bordercolor=[("focus", COL_ACCENT)])

        st.configure("TCombobox", fieldbackground=COL_PANEL, background=COL_PANEL,
                     foreground=COL_TEXT, arrowcolor=COL_TEXT,
                     bordercolor=COL_GRID, borderwidth=1)
        st.map("TCombobox",
               fieldbackground=[("readonly", COL_PANEL)],
               foreground=[("readonly", COL_TEXT)])

        # --- radio / check: visible indicators on the dark background ---
        st.configure("TRadiobutton", background=COL_BG, foreground=COL_TEXT,
                     indicatorcolor=COL_PANEL, focuscolor=COL_ACCENT)
        st.map("TRadiobutton",
               background=[("active", COL_BG)],
               foreground=[("active", COL_TEXT), ("selected", COL_TEXT)],
               indicatorcolor=[("selected", COL_ACCENT),
                               ("pressed", COL_ACCENT)])
        st.configure("TCheckbutton", background=COL_BG, foreground=COL_TEXT,
                     indicatorcolor=COL_PANEL, focuscolor=COL_ACCENT)
        st.map("TCheckbutton",
               background=[("active", COL_BG)],
               foreground=[("active", COL_TEXT), ("selected", COL_TEXT)],
               indicatorcolor=[("selected", COL_ACCENT),
                               ("pressed", COL_ACCENT)])

        # --- scrollbars: match the panels rather than OS default light gray ---
        st.configure("Vertical.TScrollbar", background=COL_PANEL,
                     troughcolor=COL_BG, bordercolor=COL_BG,
                     arrowcolor=COL_TEXT)
        st.configure("Horizontal.TScrollbar", background=COL_PANEL,
                     troughcolor=COL_BG, bordercolor=COL_BG,
                     arrowcolor=COL_TEXT)
        st.configure("TSeparator", background=COL_GRID)

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

        # staleness / data-source banner (hidden unless there's something to say)
        self.banner = tk.Frame(self.root, bg=COL_WARN)
        self.banner_var = tk.StringVar(value="")
        self.banner_lbl = tk.Label(self.banner, textvariable=self.banner_var,
                                   bg=COL_WARN, fg="#1a1205",
                                   font=("DejaVu Sans", 10, "bold"),
                                   anchor="w", padx=12, pady=4)
        self.banner_lbl.pack(side="left", fill="x", expand=True)
        tk.Button(self.banner, text="Update GP (online)",
                  command=self._update_online, bg="#1a1205", fg=COL_WARN,
                  relief="flat", font=("DejaVu Sans", 9, "bold"),
                  padx=10, pady=2, bd=0, highlightthickness=0).pack(
            side="right", padx=8, pady=3)
        self._banner_visible = False

        # body: nav + content
        body = ttk.Frame(self.root)
        self._body_ref = body
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
        self._update_banner()
        if self.current is not None and getattr(self.current, "live", False):
            try:
                self.current.on_tick(now)
            except Exception as e:
                self.set_status("tick error: %s" % e)
        self.root.after(1000, self._tick)

    def _update_banner(self):
        """Show a warning banner when predictions can't be trusted: either the
        bundled demo catalog is in use, or the loaded elements are stale."""
        age = self.store.catalog_age_days()
        msg = None
        if self.store.using_sample():
            msg = ("Demo elements in use \u2014 pass times are illustrative, "
                   "not real. Click Update GP for live data.")
        elif age > 14:
            msg = ("Orbital elements are %.0f days old \u2014 pass times will be "
                   "inaccurate. Update GP for fresh data." % age)
        elif age > 7:
            msg = ("Elements are %.0f days old; consider updating GP for best "
                   "accuracy." % age)
        if msg:
            self.banner_var.set(msg)
            if not self._banner_visible:
                self.banner.pack(side="top", fill="x", before=self._body_ref)
                self._banner_visible = True
        else:
            if self._banner_visible:
                self.banner.pack_forget()
                self._banner_visible = False

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
