"""
screens package entry - screen factory + base classes + shared helpers.

Each screen owns a ttk Frame. The factory make_screen(key, parent, app) returns
the right screen instance. Visual screens embed matplotlib via MplPanel.
"""

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


def autohide_scrollbar(bar, side, before=None):
    """Return a yscrollcommand/xscrollcommand callback that shows ``bar`` only
    when its axis has content beyond the visible area and hides it otherwise.

    ``side`` is "right" (vertical) or "bottom" (horizontal); ``before`` is the
    widget the bar should pack before when it reappears (so it keeps its place).
    The packed-state is tracked explicitly rather than via winfo_ismapped(), so
    it behaves correctly even before the window is mapped.
    """
    fill = "y" if side == "right" else "x"
    state = {"packed": True}        # bars are packed by the creator initially

    def _cb(first, last):
        try:
            lo, hi = float(first), float(last)
        except (TypeError, ValueError):
            return
        if lo <= 0.0 and hi >= 1.0:
            if state["packed"]:
                bar.pack_forget()
                state["packed"] = False
        elif not state["packed"]:
            opts = {"side": side, "fill": fill}
            if before is not None:
                opts["before"] = before
            try:
                bar.pack(**opts)
            except Exception:
                bar.pack(side=side, fill=fill)
            state["packed"] = True
        bar.set(first, last)

    return _cb


def make_scrolled_tree(parent, columns, show="headings", height=16,
                       horizontal=False, **tree_kwargs):
    """Create a ttk.Treeview wrapped in a frame with a vertical (and optionally
    horizontal) scrollbar. Returns (container, tree); pack/grid the container
    where the tree would have gone, and configure columns/headings on the
    returned tree as usual.

    The scrollbars are *context sensitive*: each one is shown only when its axis
    actually has content beyond the visible area, and hidden when everything
    fits. They use the app's themed Vertical/Horizontal.TScrollbar styles.
    """
    container = ttk.Frame(parent, style="TFrame")
    tree = ttk.Treeview(container, columns=columns, show=show, height=height,
                        **tree_kwargs)

    vsb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    hsb = (ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
           if horizontal else None)

    tree.configure(yscrollcommand=autohide_scrollbar(vsb, "right",
                                                     before=tree))
    vsb.pack(side="right", fill="y")
    if hsb is not None:
        tree.configure(xscrollcommand=autohide_scrollbar(hsb, "bottom",
                                                         before=tree))
        hsb.pack(side="bottom", fill="x")
    tree.pack(side="left", fill="both", expand=True)
    return container, tree


def make_vscroll_frame(parent):
    """Return (container, interior) where ``interior`` is a frame you build into
    and ``container`` is packed/gridded by the caller. The interior scrolls
    vertically when its content is taller than the visible area, with an
    auto-hiding themed scrollbar and mouse-wheel support. Use this for tall
    forms (e.g. Settings) so low-resolution displays never clip the bottom.

    The interior tracks the container's width, so content reflows/wraps to the
    available width instead of triggering a horizontal scrollbar.
    """
    container = ttk.Frame(parent, style="TFrame")
    canvas = tk.Canvas(container, bg=COL_BG, highlightthickness=0, bd=0)
    vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=autohide_scrollbar(vsb, "right"))
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    interior = ttk.Frame(canvas, style="TFrame")
    win_id = canvas.create_window((0, 0), window=interior, anchor="nw")

    def _on_interior(_e=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas(e):
        # keep the interior as wide as the canvas so content wraps to width
        canvas.itemconfigure(win_id, width=e.width)

    interior.bind("<Configure>", _on_interior)
    canvas.bind("<Configure>", _on_canvas)

    # mouse wheel: bind only while the pointer is over this canvas, so nested
    # scroll regions and other screens aren't affected.
    def _wheel(e):
        if e.num == 4:
            canvas.yview_scroll(-1, "units")
        elif e.num == 5:
            canvas.yview_scroll(1, "units")
        else:
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _bind_wheel(_e=None):
        canvas.bind_all("<MouseWheel>", _wheel)
        canvas.bind_all("<Button-4>", _wheel)
        canvas.bind_all("<Button-5>", _wheel)

    def _unbind_wheel(_e=None):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", _bind_wheel)
    canvas.bind("<Leave>", _unbind_wheel)

    return container, interior


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

    def save_text_dialog(self, content, default_name, title="Save file",
                         ext=".csv", filetypes=None):
        """Prompt for a path and write a text payload (CSV/ICS/JSON). Returns
        the path written, or None if cancelled/failed."""
        from tkinter import filedialog, messagebox
        if filetypes is None:
            filetypes = [("All files", "*.*")]
        path = filedialog.asksaveasfilename(
            title=title, defaultextension=ext, initialfile=default_name,
            filetypes=filetypes)
        if not path:
            return None
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
        except Exception as e:
            messagebox.showerror("Export", "Could not write file:\n%s" % e)
            return None
        self.app.set_status("Saved: %s" % path)
        return path

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
        screen that offers the export (Track and the OSCARLOCATOR Simulator).
        A single options dialog gathers the base-map style, range-circle
        placement, and reduced-text choice; then save and show print
        instructions."""
        s = self.sat()
        if not s:
            return
        from tkinter import filedialog, messagebox
        from ..oscarlocator import generate_oscarlocator_pdf
        from ..dialogs import OscarlocatorOptionsDialog
        opts = OscarlocatorOptionsDialog(self.frame, sat_name=s.name).show()
        if not opts:
            return
        projection = opts["projection"]
        fp_on_qth = opts["footprint_on_qth"]
        reduced = opts["reduced_text"]
        polar = projection.startswith("polar")
        suffix = "polar" if polar else "qth"
        if fp_on_qth:
            suffix += "_rangeqth"
        if reduced:
            suffix += "_clean"
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
                                      footprint_on_qth=fp_on_qth,
                                      reduced_text=reduced)
        except Exception as e:
            messagebox.showerror("OSCARLOCATOR", "Could not generate PDF:\n%s"
                                 % e)
            return
        self.app.set_status("Saved OSCARLOCATOR PDF: %s" % path)
        if fp_on_qth:
            detail = ("Page 1 (base map with the range circle at your QTH): "
                      "print on paper or card.\nPage 2 (orbit path arc): print "
                      "on transparency film.\n\nThe range circle is already on "
                      "the map; use the path overlay to see when the satellite "
                      "enters it.")
        elif polar:
            detail = ("Page 1 (polar base map): print on paper or card.\n"
                      "Pages 2 & 3 (range circle + orbit overhead): print on "
                      "transparency film.\n\nLay the overlays on the base map "
                      "with centres aligned and rotate to the equator-crossing "
                      "longitude (see the Orbital Analysis \u2192 Crossings List).")
        else:
            detail = ("Page 1 (base map): print on paper or card.\n"
                      "Pages 2 & 3 (range circle + path arc): print on "
                      "transparency film.\n\nPin the overlays through the centre "
                      "cross over your station on the base map.")
        if reduced:
            detail += ("\n\nReduced-text set: the base map carries all the "
                       "instructions, and the transparencies are kept clean so "
                       "this set can be reused.")
        messagebox.showinfo(
            "OSCARLOCATOR",
            "Saved an OSCARLOCATOR PDF for %s.\n\n%s" % (s.name, detail))


class TabBar:
    """A flat tabbed container matching the Orbital Analysis screen's look:
    text labels on a subtle panel-coloured strip, a blue underline on the active
    tab, no boxes and no client border (unlike ttk.Notebook).

    Usage:
        tabs = TabBar(parent)
        page1 = tabs.add("Link budget")
        page2 = tabs.add("Doppler playbook")
        tabs.pack(fill="both", expand=True)
        # build widgets into page1 / page2 (plain tk/ttk frames)
        tabs.on_change = lambda i: ...   # optional callback
    """

    def __init__(self, parent, on_change=None, wrap=False, groups=False):
        import tkinter as tk
        from tkinter import ttk
        self._tk = tk
        self.on_change = on_change
        self._wrap = wrap
        self._use_groups = groups
        self.outer = ttk.Frame(parent, style="TFrame")
        # optional group selector row (category buttons) above the tab strip
        if groups:
            self._groupbar = tk.Frame(self.outer, bg=COL_BG)
            self._groupbar.pack(fill="x", pady=(0, 2))
            self._groups = []          # list of (name, btn, [tab_indices])
            self._active_group = 0
        # the tab strip itself is panel-coloured, exactly like Orbital Analysis
        self._bar = tk.Frame(self.outer, bg=COL_PANEL)
        self._bar.pack(fill="x", pady=(0, 6))
        self._body = ttk.Frame(self.outer, style="TFrame")
        self._body.pack(fill="both", expand=True)
        self._tabs = []          # list of (label_widget, underline, page_frame)
        self._active = 0
        self._tab_group = {}     # tab index -> group index (when grouped)
        if wrap:
            # a flow layout: tabs are gridded and reflow to new rows when the bar
            # is resized, so a long tab set never runs off the edge.
            self._holders = []
            self._bar.bind("<Configure>", self._reflow)

    def add_group(self, name):
        """Register a category; subsequent add() calls belong to it until the
        next add_group(). Returns the group's index."""
        tk = self._tk
        gi = len(self._groups)
        btn = tk.Label(self._groupbar, text=name, bg=COL_BG, fg=COL_MUTED,
                       font=("DejaVu Sans", 11, "bold"), padx=14, pady=6,
                       cursor="hand2")
        btn.pack(side="left", padx=(0, 4))
        btn.bind("<Button-1>", lambda _e, i=gi: self.select_group(i))
        self._groups.append([name, btn, []])
        self._cur_group = gi
        return gi

    def add(self, name):
        tk = self._tk
        from tkinter import ttk
        holder = tk.Frame(self._bar, bg=COL_PANEL)
        lbl = tk.Label(holder, text=name, bg=COL_PANEL, fg=COL_MUTED,
                       font=("DejaVu Sans", 10), padx=10, pady=5,
                       cursor="hand2")
        lbl.pack(side="top")
        ind = tk.Frame(holder, bg=COL_PANEL, height=2)
        ind.pack(side="top", fill="x")
        page = ttk.Frame(self._body, style="TFrame")
        idx = len(self._tabs)
        lbl.bind("<Button-1>", lambda _e, i=idx: self.select(i))
        self._tabs.append((lbl, ind, page))
        if self._use_groups:
            gi = getattr(self, "_cur_group", 0)
            self._tab_group[idx] = gi
            self._groups[gi][2].append(idx)
            self._holders = getattr(self, "_holders", [])
            self._holders.append(holder)
        elif self._wrap:
            self._holders.append(holder)
            self._place_wrapped()
        else:
            holder.pack(side="left", padx=1, pady=2)
        if idx == 0:
            page.pack(fill="both", expand=True)
            self._highlight(0)
        return page

    def layout(self):
        """Call once after all groups/tabs are added to show the first group."""
        if self._use_groups:
            self.select_group(0, force=True)

    def select_group(self, gi, force=False):
        if not self._use_groups:
            return
        if gi == self._active_group and not force:
            return
        self._active_group = gi
        # restyle group buttons
        for i, (_n, btn, _idxs) in enumerate(self._groups):
            on = (i == gi)
            btn.configure(fg=COL_ACCENT if on else COL_MUTED, bg=COL_BG)
        # show only this group's tab holders
        for h in self._holders:
            h.grid_forget()
            h.pack_forget()
        idxs = self._groups[gi][2]
        bar_w = self._bar.winfo_width() or 1100
        x = row = col = 0
        for ti in idxs:
            h = self._holders[ti]
            h.update_idletasks()
            w = h.winfo_reqwidth() + 2
            if x + w > bar_w and col > 0:
                row += 1
                x = 0
                col = 0
            h.grid(row=row, column=col, padx=1, pady=2, sticky="w")
            x += w
            col += 1
        # select the first tab in the group
        if idxs:
            self.select(idxs[0])

    def _place_wrapped(self):
        # estimate each holder's width and break into rows that fit the bar
        bar_w = self._bar.winfo_width() or 1100
        x = 0
        row = 0
        col = 0
        for h in self._holders:
            h.update_idletasks()
            w = h.winfo_reqwidth() + 2
            if x + w > bar_w and col > 0:
                row += 1
                x = 0
                col = 0
            h.grid(row=row, column=col, padx=1, pady=2, sticky="w")
            x += w
            col += 1

    def _reflow(self, _evt=None):
        if self._use_groups:
            self.select_group(self._active_group, force=True)
        elif self._wrap:
            self._place_wrapped()


    def _highlight(self, active):
        for i, (lbl, ind, _page) in enumerate(self._tabs):
            on = (i == active)
            lbl.configure(fg=COL_ACCENT if on else COL_MUTED,
                          bg=COL_PANEL,
                          font=("DejaVu Sans", 10, "bold") if on
                          else ("DejaVu Sans", 10))
            ind.configure(bg=COL_ACCENT if on else COL_PANEL)

    def select(self, idx):
        if idx == self._active:
            return
        for i, (_lbl, _ind, page) in enumerate(self._tabs):
            if i == idx:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        self._active = idx
        self._highlight(idx)
        if self.on_change:
            try:
                self.on_change(idx)
            except Exception:
                pass

    def pack(self, **kw):
        self.outer.pack(**kw)
        return self


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
        ax.tick_params(which="both", colors=COL_MUTED, labelsize=8)
        # log-scale minor tick labels default to black; force them muted too
        for lbl in (ax.get_xticklabels(which="minor")
                    + ax.get_yticklabels(which="minor")):
            lbl.set_color(COL_MUTED)
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

    def recolor_ticks(self):
        """Re-apply muted colour to all (major and minor) tick labels. Call this
        after changing to a log scale, whose minor labels otherwise render in
        the default black and disappear on the dark panel."""
        ax = self.ax
        ax.tick_params(which="both", colors=COL_MUTED, labelsize=8)
        for lbl in (ax.get_xticklabels(which="both")
                    + ax.get_yticklabels(which="both")):
            lbl.set_color(COL_MUTED)

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
                   grids, spacewx, oscarsim, analytics, radio, planning,
                   exportscreen, sites, celestial, learn)
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
        "globe": analytics.GlobeScreen,
        "radar": analytics.RadarScreen,
        "radio": radio.RadioScreen,
        "planning": planning.PlanningScreen,
        "exports": exportscreen.ExportScreen,
        "sites": sites.SitesScreen,
        "celestial": celestial.CelestialScreen,
        "learn": learn.LearnScreen,
    }
    cls = mapping[key]
    return cls(parent, app)
