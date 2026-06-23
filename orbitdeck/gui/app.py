"""
app.py - the OrbitDeck main window.

A Tkinter application with a navigation sidebar and a swappable content area.
Visual screens embed matplotlib. Designed to match the source device's analysis feature
set: Track, Passes, Pass Detail/Polar, World Map, Illumination, Orbital
Analysis (9 pages), Sun/Moon, Mutual Windows, Space Wx, Satellites, Settings.
"""

import datetime as dt
import os
import sys
import threading

import tkinter as tk
from tkinter import ttk, messagebox

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
    # live view & overview
    ("Home", "home"),
    ("Track", "track"),
    ("3D Globe", "globe"),
    ("Sky Radar", "radar"),
    # passes
    ("Next Passes", "passes"),
    ("Pass Detail", "passdetail"),
    ("Ground Track", "groundtrack"),
    ("Pass Progression", "tenday"),
    # analysis
    ("Orbital Analysis", "orbit"),
    ("Illumination", "illum"),
    ("Mutual Windows", "mutual"),
    ("Workable", "grids"),
    # operating tools
    ("Radio", "radio"),
    ("Planning", "planning"),
    ("OSCARLOCATOR Sim", "oscarsim"),
    ("Learn", "learn"),
    ("Exports", "exports"),
    # sky & space environment
    ("Sun / Moon", "sunmoon"),
    ("Celestial", "celestial"),
    ("Space Wx", "spacewx"),
    # catalog & configuration
    ("Satellites", "satellites"),
    ("Sites", "sites"),
    ("Settings", "location"),
]


class OrbitDeckApp:
    def __init__(self, root):
        self.root = root
        self.store = Store()
        self.current = None
        self.current_key = None
        self._screen_cache = {}
        from .alarms import AlarmManager
        self.alarms = AlarmManager(self)

        root.title("OrbitDeck \u2014 Satellite Tracking & Orbital Analysis")
        root.geometry("1180x760")
        root.minsize(960, 640)
        root.configure(bg=COL_BG)
        self._set_window_icon(root)

        self._init_style()
        self._build_layout()
        self._bind_shortcuts()
        self.show("home")
        self._tick()
        self.root.after(400, self._first_run_check)

    def _set_window_icon(self, root):
        """Set the taskbar / title-bar icon from the bundled asset, if present.
        Resolves assets from the PyInstaller bundle dir when frozen, and applies
        BOTH the .ico (title bar) and the PNG (iconphoto, which Windows also uses
        for the taskbar) so the OrbitDeck icon shows reliably."""
        base = getattr(sys, "_MEIPASS", None)
        if base:
            assets = os.path.join(base, "orbitdeck", "gui", "assets")
        else:
            here = os.path.dirname(os.path.abspath(__file__))
            assets = os.path.join(here, "assets")
        try:
            ico = os.path.join(assets, "icon.ico")
            if os.name == "nt" and os.path.exists(ico):
                root.iconbitmap(default=ico)
        except Exception:
            pass
        try:
            png = os.path.join(assets, "icon-256.png")
            if os.path.exists(png):
                img = tk.PhotoImage(file=png)
                root.iconphoto(True, img)
                self._icon_img = img      # keep a reference so it isn't GC'd
        except Exception:
            pass

    def _init_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=COL_BG, foreground=COL_TEXT, font=FONT)
        st.configure("TFrame", background=COL_BG)
        # Panel.TFrame historically used a slightly lighter panel colour, which
        # left informational text sitting on a stray darker rectangle that
        # differed from the window. Flatten control containers to the window
        # background so text (other than buttons) never has its own background.
        # The deliberate readout CARDS are KVPanel, which paints its own
        # tk.Label(bg=COL_PANEL) widgets and is unaffected by these ttk styles.
        st.configure("Panel.TFrame", background=COL_BG)
        st.configure("TLabel", background=COL_BG, foreground=COL_TEXT)
        st.configure("Panel.TLabel", background=COL_BG, foreground=COL_TEXT)
        st.configure("Muted.TLabel", background=COL_BG, foreground=COL_MUTED)
        # kept as an explicit alias (same as Muted.TLabel now) for callers that
        # specifically want window-background muted text
        st.configure("MutedBg.TLabel", background=COL_BG, foreground=COL_MUTED)
        st.configure("H.TLabel", background=COL_BG, foreground=COL_TEXT, font=FONT_H)
        st.configure("PanelH.TLabel", background=COL_BG, foreground=COL_TEXT,
                     font=FONT_H)
        st.configure("Mono.TLabel", background=COL_BG, foreground=COL_TEXT,
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
                     bordercolor=COL_GRID, borderwidth=1,
                     selectbackground=COL_PANEL, selectforeground=COL_TEXT)
        st.map("TCombobox",
               fieldbackground=[("readonly", COL_PANEL)],
               foreground=[("readonly", COL_TEXT)],
               selectbackground=[("readonly", COL_PANEL)],
               selectforeground=[("readonly", COL_TEXT)])
        # the dropdown popup of a combobox is a Tk Listbox that ttk styling does
        # NOT reach; theme it through the option database so it doesn't flash a
        # white box on a dark UI.
        self.root.option_add("*TCombobox*Listbox.background", COL_PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", COL_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", COL_ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.borderWidth", 0)

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
        # "Panel" radio/check variants now sit on the window background too (the
        # containers they live on were flattened); the indicator reads against
        # the panel colour for contrast.
        st.configure("Panel.TRadiobutton", background=COL_BG,
                     foreground=COL_TEXT, indicatorcolor=COL_PANEL,
                     focuscolor=COL_ACCENT)
        st.map("Panel.TRadiobutton",
               background=[("active", COL_BG)],
               foreground=[("active", COL_TEXT), ("selected", COL_TEXT)],
               indicatorcolor=[("selected", COL_ACCENT),
                               ("pressed", COL_ACCENT)])
        st.configure("Panel.TCheckbutton", background=COL_BG,
                     foreground=COL_TEXT, indicatorcolor=COL_PANEL,
                     focuscolor=COL_ACCENT)
        st.map("Panel.TCheckbutton",
               background=[("active", COL_BG)],
               foreground=[("active", COL_TEXT), ("selected", COL_TEXT)],
               indicatorcolor=[("selected", COL_ACCENT),
                               ("pressed", COL_ACCENT)])

        # --- scrollbars: match the panels rather than OS default light gray ---
        # The thumb uses the grid colour so it reads as a raised handle against
        # the darker trough, with an accent hover; arrows are hidden for a clean
        # modern look (the trough + thumb carry the affordance).
        for _orient in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            st.configure(_orient, background=COL_GRID, troughcolor=COL_BG,
                         bordercolor=COL_BG, arrowcolor=COL_MUTED,
                         borderwidth=0, relief="flat")
            st.map(_orient,
                   background=[("active", COL_ACCENT),
                               ("pressed", COL_ACCENT)],
                   arrowcolor=[("active", COL_TEXT)])

        # --- scale / scrub bars: dark trough with an accent slider handle so the
        # time-in-pass and passband sliders match the theme instead of the clam
        # default light grey ---
        for _sc in ("Horizontal.TScale", "Vertical.TScale"):
            st.configure(_sc, background=COL_BG, troughcolor=COL_PANEL,
                         bordercolor=COL_GRID, lightcolor=COL_GRID,
                         darkcolor=COL_GRID, borderwidth=0)
            st.map(_sc,
                   background=[("active", COL_BG)],
                   troughcolor=[("active", COL_PANEL)])
        # the slider handle itself is drawn with the "slider" element colour,
        # which clam takes from `background`; give the Scale a dedicated style so
        # the handle is accent-coloured and clearly grabbable
        st.configure("Accent.Horizontal.TScale", background=COL_ACCENT,
                     troughcolor=COL_PANEL, bordercolor=COL_GRID,
                     lightcolor=COL_ACCENT, darkcolor=COL_ACCENT,
                     borderwidth=0)
        st.map("Accent.Horizontal.TScale",
               background=[("active", COL_ACCENT2)])
        st.configure("TSeparator", background=COL_GRID)

        # --- notebook (tabbed) panels: match the orbital-analysis tab look ---
        st.configure("TNotebook", background=COL_BG, borderwidth=0,
                     tabmargins=[2, 4, 2, 0])
        st.configure("TNotebook.Tab", background=COL_PANEL, foreground=COL_MUTED,
                     padding=[12, 6], borderwidth=0,
                     font=("DejaVu Sans", 10))
        st.map("TNotebook.Tab",
               background=[("selected", COL_BG), ("active", COL_PANEL)],
               foreground=[("selected", COL_ACCENT), ("active", COL_TEXT)],
               font=[("selected", ("DejaVu Sans", 10, "bold"))])

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
        ttk.Button(top, text="Update GP",
                   command=self._update_online).pack(side="right", padx=6, pady=6)
        ttk.Button(top, text="Update Transponders",
                   command=self._update_transponders).pack(
            side="right", padx=2, pady=6)
        ttk.Button(top, text="Select Satellite\u2026",
                   command=self._quick_select).pack(side="right", padx=6, pady=6)
        self._alarm_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Favorite pass alarms",
                        variable=self._alarm_var,
                        command=lambda: self.alarms.set_enabled(
                            self._alarm_var.get())).pack(
            side="right", padx=6, pady=6)

        # staleness / data-source banner (hidden unless there's something to say)
        self.banner = tk.Frame(self.root, bg=COL_WARN)
        self.banner_var = tk.StringVar(value="")
        self.banner_lbl = tk.Label(self.banner, textvariable=self.banner_var,
                                   bg=COL_WARN, fg="#1a1205",
                                   font=("DejaVu Sans", 10, "bold"),
                                   anchor="w", padx=12, pady=4)
        self.banner_lbl.pack(side="left", fill="x", expand=True)
        tk.Button(self.banner, text="Update GP",
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
        # keep the "selected satellite" badge current on screens that show one
        if hasattr(scr, "refresh_sat_header"):
            scr.refresh_sat_header()
        scr.on_show()

    # ---- keyboard shortcuts & command palette ----
    def _bind_shortcuts(self):
        """Global key bindings for fast navigation. Bindings are skipped while a
        text-entry widget has focus so typing isn't hijacked."""
        r = self.root
        r.bind_all("<Control-k>", lambda e: self._command_palette())
        r.bind_all("<Control-K>", lambda e: self._command_palette())
        r.bind_all("<Control-f>", lambda e: self._quick_select())
        r.bind_all("<slash>", self._maybe(lambda e: self._quick_select()))
        # next / previous satellite
        r.bind_all("<bracketright>", self._maybe(lambda e: self._cycle_sat(1)))
        r.bind_all("<bracketleft>", self._maybe(lambda e: self._cycle_sat(-1)))
        r.bind_all("<Control-period>", lambda e: self._cycle_sat(1))
        r.bind_all("<Control-comma>", lambda e: self._cycle_sat(-1))
        # font size
        r.bind_all("<Control-plus>", lambda e: self._bump_font(1))
        r.bind_all("<Control-equal>", lambda e: self._bump_font(1))
        r.bind_all("<Control-minus>", lambda e: self._bump_font(-1))
        r.bind_all("<Control-0>", lambda e: self._set_font_scale(1.0))
        # jump to screen by number (1-9) when not typing
        for i in range(1, 10):
            r.bind_all(str(i), self._maybe(
                lambda e, n=i: self._show_nth(n - 1)))
        r.bind_all("<F1>", lambda e: self._show_help())
        r.bind_all("<question>", self._maybe(lambda e: self._show_help()))

    @staticmethod
    def _is_text_focus(root):
        try:
            w = root.focus_get()
        except Exception:
            return False
        return isinstance(w, (tk.Entry, tk.Text)) or \
            (w is not None and w.winfo_class() in ("TEntry", "TCombobox",
                                                   "Entry", "Text"))

    def _maybe(self, fn):
        """Wrap a key handler so it's ignored while a text field has focus."""
        def handler(e):
            if self._is_text_focus(self.root):
                return
            return fn(e)
        return handler

    def _show_nth(self, idx):
        if 0 <= idx < len(NAV_ITEMS):
            self.show(NAV_ITEMS[idx][1])

    def _cycle_sat(self, step):
        """Select the next/previous satellite (favorites first, then by name)."""
        sats = self.store.db.sats
        if not sats:
            return
        order = sorted(sats, key=lambda s: (s.norad not in self.store.favorites,
                                            s.name.lower()))
        cur = self.store.selected_norad
        idx = next((i for i, s in enumerate(order) if s.norad == cur), -1)
        nxt = order[(idx + step) % len(order)]
        self.store.select(nxt.norad)
        self.sat_var.set(nxt.name)
        self._refresh_current()
        self.set_status("Satellite: %s" % nxt.name)

    def _command_palette(self):
        """Ctrl+K palette: type to jump to any screen or satellite."""
        win = tk.Toplevel(self.root)
        win.title("Go to\u2026")
        win.configure(bg=COL_BG)
        win.geometry("460x420")
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        ent = ttk.Entry(win)
        ent.pack(fill="x", padx=10, pady=10)
        ent.focus_set()
        lb = tk.Listbox(win, bg=COL_PANEL, fg=COL_TEXT, bd=0,
                        selectbackground=COL_ACCENT, selectforeground="#fff",
                        highlightthickness=0, activestyle="none",
                        font=("DejaVu Sans", 11))
        lb.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # build the command list: screens + satellites
        items = [("screen", label, key) for label, key in NAV_ITEMS]
        for s in self.store.db.sats:
            items.append(("sat", "\U0001f6f0 %s" % s.name, s.norad))
        shown = []

        def repop(*_):
            lb.delete(0, "end")
            shown.clear()
            q = ent.get().strip().lower()
            for kind, label, ref in items:
                if q and q not in label.lower():
                    continue
                lb.insert("end", label)
                shown.append((kind, ref))
                if len(shown) >= 200:
                    break
            if shown:
                lb.selection_set(0)

        def activate(_=None):
            sel = lb.curselection()
            if not sel:
                return
            kind, ref = shown[sel[0]]
            win.destroy()
            if kind == "screen":
                self.show(ref)
            else:
                self.store.select(ref)
                s = self.store.selected_sat()
                if s:
                    self.sat_var.set(s.name)
                self._refresh_current()

        def move(d):
            sel = lb.curselection()
            i = (sel[0] if sel else 0) + d
            i = max(0, min(lb.size() - 1, i))
            lb.selection_clear(0, "end")
            lb.selection_set(i)
            lb.see(i)

        ent.bind("<KeyRelease>", repop)
        ent.bind("<Down>", lambda e: (move(1), "break"))
        ent.bind("<Up>", lambda e: (move(-1), "break"))
        ent.bind("<Return>", activate)
        ent.bind("<Escape>", lambda e: win.destroy())
        lb.bind("<Double-Button-1>", activate)
        lb.bind("<Return>", activate)
        repop()

    # ---- UI font scaling ----
    def _bump_font(self, direction):
        cur = getattr(self, "_font_scale", 1.0)
        self._set_font_scale(cur + 0.1 * direction)

    def _set_font_scale(self, scale):
        scale = max(0.8, min(1.8, scale))
        self._font_scale = scale
        try:
            import tkinter.font as tkfont
            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                         "TkHeadingFont", "TkFixedFont"):
                try:
                    f = tkfont.nametofont(name)
                    base = getattr(self, "_font_base_%s" % name, None)
                    if base is None:
                        base = abs(f.cget("size")) or 10
                        setattr(self, "_font_base_%s" % name, base)
                    f.configure(size=max(7, int(round(base * scale))))
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.root.tk.call("tk", "scaling", 1.333 * scale)
        except Exception:
            pass
        self.store.save_config(ui_scale=scale)
        self.set_status("Text size: %d%%" % round(scale * 100))

    # ---- first-run onboarding & live-data prompt ----
    def _first_run_check(self):
        cfg = self.store.config
        # restore saved UI scale
        saved = cfg.get("ui_scale")
        if saved and abs(float(saved) - 1.0) > 0.01:
            self._set_font_scale(float(saved))
        if cfg.get("onboarded"):
            return
        try:
            self._show_welcome()
        except Exception:
            pass

    def _show_welcome(self):
        win = tk.Toplevel(self.root)
        win.title("Welcome to OrbitDeck")
        win.configure(bg=COL_BG)
        win.geometry("560x420")
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        from .. import __version__
        tk.Label(win, text="Welcome to OrbitDeck", bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", 16, "bold")).pack(anchor="w",
                                                        padx=20, pady=(18, 2))
        tk.Label(win, text="v%s \u2014 satellite tracking & orbital analysis"
                 % __version__, bg=COL_BG, fg=COL_MUTED,
                 font=("DejaVu Sans", 10)).pack(anchor="w", padx=20)
        steps = (
            "Three quick steps to get going:\n\n"
            "1.  Set your location \u2014 open Settings and enter your "
            "latitude/longitude or Maidenhead grid. Accurate pass times need "
            "your QTH.\n\n"
            "2.  Get live elements \u2014 click \u201cUpdate GP\u201d in the top "
            "bar to pull the current AMSAT catalog. Until you do, a sample "
            "catalog is loaded and pass times are illustrative only.\n\n"
            "3.  Explore \u2014 the Home screen counts down your favorite "
            "satellites' next passes. Press Ctrl+K any time to jump to a screen "
            "or satellite, or F1 for the full shortcut list.")
        msg = tk.Message(win, text=steps, bg=COL_BG, fg=COL_TEXT,
                         font=("DejaVu Sans", 11), width=510,
                         justify="left")
        msg.pack(anchor="w", padx=20, pady=14)

        btns = tk.Frame(win, bg=COL_BG)
        btns.pack(side="bottom", fill="x", padx=20, pady=16)

        def finish(fetch):
            self.store.save_config(onboarded=True)
            win.destroy()
            if fetch:
                self._update_online()

        ttk.Button(btns, text="Update GP now",
                   command=lambda: finish(True)).pack(side="right", padx=4)
        ttk.Button(btns, text="Later",
                   command=lambda: finish(False)).pack(side="right")
        tk.Button(btns, text="Open Settings", bg=COL_PANEL, fg=COL_TEXT,
                  relief="flat", bd=0, padx=10, pady=4,
                  command=lambda: (self.store.save_config(onboarded=True),
                                   win.destroy(),
                                   self.show("location"))).pack(side="left")

    def _show_help(self):
        from tkinter import messagebox
        messagebox.showinfo(
            "Keyboard shortcuts",
            "Ctrl+K\tCommand palette (jump to screen or satellite)\n"
            "Ctrl+F  or  /\tFind/select a satellite\n"
            "[  /  ]\tPrevious / next satellite\n"
            "1\u20139\tJump to the Nth screen in the sidebar\n"
            "Ctrl++  /  Ctrl+-\tText size larger / smaller\n"
            "Ctrl+0\tReset text size\n"
            "F1  or  ?\tThis help\n\n"
            "(Shortcuts are ignored while you're typing in a text field.)")

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
        try:
            self.alarms.tick()
        except Exception:
            pass
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
        win.geometry("560x560")

        top = ttk.Frame(win, style="TFrame")
        top.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(top, text="Filter:", style="TLabel").pack(side="left")
        filt = tk.StringVar()
        ent = ttk.Entry(top, textvariable=filt, width=28)
        ent.pack(side="left", padx=6)
        ent.focus_set()
        favonly = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Favorites", variable=favonly).pack(
            side="left", padx=8)

        cols = ("fav", "name", "norad", "period", "tx")
        heads = ("\u2605", "Name", "NORAD", "Period", "TX")
        widths = {"fav": 30, "name": 230, "norad": 80, "period": 90, "tx": 50}
        _twrap = ttk.Frame(win)
        _twrap.pack(fill="both", expand=True, padx=8, pady=4)
        tree = ttk.Treeview(_twrap, columns=cols, show="headings", height=20)
        for c, h in zip(cols, heads):
            tree.heading(c, text=h)
            tree.column(c, width=widths[c],
                        anchor="w" if c == "name" else "center")
        vsb = ttk.Scrollbar(_twrap, orient="vertical", command=tree.yview)
        tree.configure(
            yscrollcommand=screens.autohide_scrollbar(vsb, "right",
                                                      before=tree))
        vsb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        rows = []

        def repop(*_):
            for i in tree.get_children():
                tree.delete(i)
            rows.clear()
            f = filt.get().strip().lower()
            order = sorted(range(len(sats)),
                           key=lambda i: (sats[i].norad
                                          not in self.store.favorites,
                                          sats[i].name))
            for i in order:
                s = sats[i]
                if favonly.get() and s.norad not in self.store.favorites:
                    continue
                if f and f not in s.name.lower() and f not in str(s.norad):
                    continue
                star = "\u2605" if s.norad in self.store.favorites else ""
                tree.insert("", "end", values=(
                    star, s.name, s.norad, "%.1f min" % s.period_min,
                    "%d" % len(s.transponders) if s.transponders else ""))
                rows.append(s)

        def choose(_=None):
            sel = tree.selection()
            if sel:
                idx = tree.index(sel[0])
                if 0 <= idx < len(rows):
                    self.store.select(rows[idx].norad)
                    self.store.ensure_transponders(rows[idx], online=True)
                    self.store.save_config()
                    if self.current:
                        if hasattr(self.current, "refresh_sat_header"):
                            self.current.refresh_sat_header()
                        self.current.on_show()
                    win.destroy()

        filt.trace_add("write", repop)
        favonly.trace_add("write", repop)
        tree.bind("<Double-Button-1>", choose)
        ent.bind("<Return>", lambda _e: choose())
        ttk.Button(win, text="Select", command=choose).pack(pady=6)
        repop()

    def _refresh_current(self):
        if not self.current:
            return
        if hasattr(self.current, "refresh_sat_header"):
            self.current.refresh_sat_header()
        self.current.on_show()

    def _update_online(self):
        def work():
            try:
                self.set_status("Updating GP catalog\u2026")
                n = self.store.update_gp_online(progress=self.set_status)
                # also refresh the full transponder DB in the same pass
                try:
                    self.store.update_transponders_online(
                        progress=self.set_status)
                except Exception:
                    pass
                self.set_status("Updated: %d satellites loaded." % n)
            except Exception as e:
                self.set_status("Update failed: %s" % e)
                self.root.after(0, lambda e=e: messagebox.showerror(
                    "Update failed",
                    "Could not fetch GP data.\n\n%s\n\nThe app keeps working "
                    "with the cached/sample catalog." % e))
            self.root.after(0, self._refresh_current)
        threading.Thread(target=work, daemon=True).start()

    def _update_transponders(self):
        def work():
            try:
                n = self.store.update_transponders_online(
                    progress=self.set_status)
                self.set_status("Transponders cached for %d satellites." % n)
            except Exception as e:
                self.set_status("Transponder update failed: %s" % e)
                self.root.after(0, lambda e=e: messagebox.showerror(
                    "Update failed",
                    "Could not fetch the transponder database.\n\n%s" % e))
            self.root.after(0, self._refresh_current)
        threading.Thread(target=work, daemon=True).start()


def _ensure_ca_certs():
    """Make HTTPS work in frozen builds (see run.py for the rationale)."""
    import os
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
        ca = certifi.where()
        if os.path.exists(ca):
            os.environ["SSL_CERT_FILE"] = ca
            os.environ.setdefault("REQUESTS_CA_BUNDLE", ca)
    except Exception:
        pass


def _set_windows_app_id():
    """On Windows, give the process an explicit AppUserModelID so the taskbar
    shows OrbitDeck's own icon and groups its windows under OrbitDeck -- instead
    of inheriting the generic Python / pythonw host icon (a frozen Tkinter app
    has no app id of its own otherwise). Harmless / no-op off Windows."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "OrbitDeck.SatelliteTracker")
    except Exception:
        pass


def main():
    _set_windows_app_id()
    _ensure_ca_certs()
    root = tk.Tk()
    OrbitDeckApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
