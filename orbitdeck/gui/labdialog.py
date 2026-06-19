"""labdialog.py - the pop-up element editor for the OSCARLOCATOR lab satellite.

A Toplevel with one slider + linked numeric entry per orbital element, a name
field, an orbit-preset gallery, a live derived-quantity read-out, a one-line
plain-language explainer for the element last touched, an optional A/B compare
satellite, and Save / glossary actions. Every change calls an ``on_change``
callback so the simulator re-renders the path, footprint, and range circle live.
"""

import tkinter as tk
from tkinter import ttk

from . import lab
from .screens import (COL_BG, COL_PANEL, COL_TEXT, COL_MUTED, COL_ACCENT,
                      COL_GRID, COL_ACCENT2, COL_WARN)


# (label, field, min, max, unit, resolution)
_SLIDERS = [
    ("Mean altitude", "alt_km", lab.ALT_MIN_KM, lab.ALT_MAX_KM, "km", 1.0),
    ("Eccentricity", "ecc", 0.0, lab.ECC_MAX, "", 0.001),
    ("Inclination", "incl", 0.0, 180.0, "\u00b0", 0.1),
    ("RAAN", "raan", 0.0, 360.0, "\u00b0", 0.1),
    ("Arg. of perigee", "argp", 0.0, 360.0, "\u00b0", 0.1),
    ("Mean anomaly", "ma", 0.0, 360.0, "\u00b0", 0.1),
]

# field -> snap resolution, so a dragged slider lands on clean values
_RES = {field: res for (_lbl, field, _lo, _hi, _u, res) in _SLIDERS}

# named preset orbits for the gallery: field dict (no name)
PRESETS = {
    "ISS-like LEO": {"alt_km": 420.0, "ecc": 0.0, "incl": 51.6,
                     "raan": 0.0, "argp": 0.0, "ma": 0.0},
    "Sun-synchronous": {"alt_km": 700.0, "ecc": 0.001, "incl": 98.2,
                        "raan": 0.0, "argp": 0.0, "ma": 0.0},
    "Polar": {"alt_km": 800.0, "ecc": 0.0, "incl": 90.0,
              "raan": 0.0, "argp": 0.0, "ma": 0.0},
    "Molniya": {"alt_km": 26600.0, "ecc": 0.70, "incl": 63.4,
                "raan": 0.0, "argp": 270.0, "ma": 0.0},
    "GPS-like MEO": {"alt_km": 20200.0, "ecc": 0.0, "incl": 55.0,
                     "raan": 0.0, "argp": 0.0, "ma": 0.0},
    "Geostationary": {"alt_km": 35786.0, "ecc": 0.0, "incl": 0.0,
                      "raan": 0.0, "argp": 0.0, "ma": 0.0},
}

# glossary entries for the formula / definition cards
GLOSSARY = [
    ("Mean altitude",
     "Height of the orbit above Earth's surface (semi-major-axis altitude, "
     "a \u2212 R\u2091). Sets the orbital period via Kepler's third law: "
     "T = 2\u03c0\u221a(a\u00b3/\u03bc)."),
    ("Eccentricity",
     "How elongated the ellipse is (0 = circle). Apogee = a(1+e), "
     "perigee = a(1\u2212e). The satellite moves fastest at perigee, slowest "
     "at apogee (Kepler's second law)."),
    ("Inclination",
     "Tilt of the orbit plane to the equator. The ground track reaches up to "
     "\u00b1(inclination) in latitude; >90\u00b0 is retrograde (east-to-west)."),
    ("RAAN",
     "Right Ascension of the Ascending Node \u2014 the orbit plane's rotation "
     "about Earth's axis. Sets which longitudes the passes fall over."),
    ("Argument of perigee",
     "Orientation of the ellipse within the orbit plane \u2014 the latitude at "
     "which the satellite is lowest (perigee). 270\u00b0 puts apogee over the "
     "far northern hemisphere (Molniya)."),
    ("Mean anomaly",
     "The satellite's position along the orbit at the epoch, as an angle that "
     "advances uniformly in time. Just slides the bird along the same path."),
    ("Footprint radius",
     "Earth-central half-angle to the horizon: arccos(R\u2091 / (R\u2091+h)). "
     "Larger altitude \u2192 wider footprint \u2192 longer, farther-reaching "
     "passes."),
    ("Period",
     "Time for one orbit: T = 1440 / mean-motion (minutes). Geostationary "
     "altitude (~35,786 km) gives a 24-hour period, so the satellite appears "
     "to hover."),
]


class LabDialog:
    def __init__(self, parent, elements, on_change, on_save=None,
                 compare=None, on_compare=None):
        self.on_change = on_change
        self.on_save = on_save
        self.on_compare = on_compare
        self.el = lab.clamp_elements(elements)
        self._compare = compare        # dict or None
        self._building = True
        self._vars = {}                # field -> DoubleVar
        self._entries = {}             # field -> StringVar
        self._getters = {}             # field -> callable returning current val
        self._fmts = {}                # field -> formatter callable
        self._emit_after = None        # pending debounced render handle

        self.win = tk.Toplevel(parent)
        self.win.title("Lab satellite \u2014 orbital elements")
        self.win.configure(bg=COL_BG)
        self.win.geometry("440x800")
        self.win.transient(parent)

        self._build()
        self._building = False
        self._sync_all_from_el()
        self._update_derived()

    # ---- layout ----
    def _build(self):
        pad = {"padx": 12}
        # name
        top = tk.Frame(self.win, bg=COL_BG)
        top.pack(fill="x", pady=(12, 4), **pad)
        tk.Label(top, text="Satellite name", bg=COL_BG, fg=COL_MUTED,
                 font=("DejaVu Sans", 9)).pack(anchor="w")
        self._name = tk.StringVar(value=self.el["name"])
        ent = tk.Entry(top, textvariable=self._name, bg=COL_PANEL, fg=COL_TEXT,
                       insertbackground=COL_TEXT, relief="flat",
                       highlightthickness=1, highlightbackground=COL_GRID)
        ent.pack(fill="x", pady=2)
        self._name.trace_add("write", lambda *_: self._on_name())

        # preset gallery
        pf = tk.Frame(self.win, bg=COL_BG)
        pf.pack(fill="x", pady=(4, 6), **pad)
        tk.Label(pf, text="Preset orbits", bg=COL_BG, fg=COL_MUTED,
                 font=("DejaVu Sans", 9)).pack(anchor="w")
        grid = tk.Frame(pf, bg=COL_BG)
        grid.pack(fill="x", pady=2)
        names = list(PRESETS.keys())
        for i, nm in enumerate(names):
            b = ttk.Button(grid, text=nm, width=16,
                           command=lambda n=nm: self._apply_preset(n))
            b.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # sliders + linked entries
        sf = tk.Frame(self.win, bg=COL_BG)
        sf.pack(fill="x", pady=4, **pad)
        for (label, field, lo, hi, unit, res) in _SLIDERS:
            self._build_slider_row(
                sf, label, lo, hi, unit, self.el[field],
                getter=lambda f=field: self.el[f],
                fmt=lambda v, f=field: self._fmt(f, v),
                on_slide=lambda v, f=field: self._on_slider_value(f, v),
                on_type=lambda v, f=field: self._on_entry_value(f, v),
                key=field)

        # Apogee / perigee as sliders too (like the other parameters), each with
        # a linked entry. They are not independent elements -- they map to mean
        # altitude + eccentricity -- so moving either solves back for alt/ecc and
        # the pair re-syncs. Ranges span the altitude limits.
        for key, label in (("apogee", "Apogee altitude"),
                           ("perigee", "Perigee altitude")):
            apo0, peri0 = lab.apsides_from_alt_ecc(self.el["alt_km"],
                                                   self.el["ecc"])
            cur = apo0 if key == "apogee" else peri0
            self._build_slider_row(
                sf, label, lab.ALT_MIN_KM, lab.ALT_MAX_KM, "km", cur,
                getter=lambda k=key: self._apsis_value(k),
                fmt=lambda v: "%.0f" % v,
                on_slide=lambda v, k=key: self._on_apsis_value(k, v),
                on_type=lambda v, k=key: self._on_apsis_value(k, v),
                key=key)

        # explainer line
        self._explain = tk.StringVar(value="")
        ex = tk.Label(self.win, textvariable=self._explain, bg=COL_BG,
                      fg=COL_ACCENT2, font=("DejaVu Sans", 9),
                      wraplength=410, justify="left")
        ex.pack(fill="x", padx=12, pady=(2, 4))

        # derived read-out
        self._derived = tk.StringVar(value="")
        dv = tk.Label(self.win, textvariable=self._derived, bg=COL_PANEL,
                      fg=COL_TEXT, font=("DejaVu Sans Mono", 9),
                      justify="left", anchor="w")
        dv.pack(fill="x", padx=12, pady=4, ipady=6, ipadx=8)

        # compare toggle
        cf = tk.Frame(self.win, bg=COL_BG)
        cf.pack(fill="x", padx=12, pady=2)
        self._cmp_on = tk.BooleanVar(value=self._compare is not None)
        ttk.Checkbutton(cf, text="Compare: freeze current orbit as a ghost (B) "
                        "to contrast with edits", variable=self._cmp_on,
                        command=self._on_compare_toggle).pack(anchor="w")

        # actions
        af = tk.Frame(self.win, bg=COL_BG)
        af.pack(fill="x", padx=12, pady=(8, 12))
        ttk.Button(af, text="Glossary\u2026",
                   command=self._show_glossary).pack(side="left")
        ttk.Button(af, text="Guided tour\u2026",
                   command=self._start_tour).pack(side="left", padx=6)
        ttk.Button(af, text="Save as manual satellite",
                   command=self._on_save_click).pack(side="right")

    # ---- slider row builder ----
    def _build_slider_row(self, parent, label, lo, hi, unit, value,
                          getter, fmt, on_slide, on_type, key):
        """Build one labelled slider + linked entry box. ``key`` indexes the
        widget dicts; ``getter`` returns the current value for syncing; ``fmt``
        formats it; ``on_slide``/``on_type`` receive a float value."""
        row = tk.Frame(parent, bg=COL_BG)
        row.pack(fill="x", pady=3)
        head = tk.Frame(row, bg=COL_BG)
        head.pack(fill="x")
        tk.Label(head, text=label, bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", 9)).pack(side="left")
        tk.Label(head, text=unit, bg=COL_BG, fg=COL_MUTED,
                 font=("DejaVu Sans", 8)).pack(side="left", padx=4)
        evar = tk.StringVar(value=fmt(value))
        e = tk.Entry(head, textvariable=evar, width=9, bg=COL_PANEL,
                     fg=COL_ACCENT, insertbackground=COL_TEXT, relief="flat",
                     justify="right", highlightthickness=1,
                     highlightbackground=COL_GRID)
        e.pack(side="right")

        def _typed(_e=None):
            if self._building:
                return
            try:
                v = float(evar.get())
            except ValueError:
                evar.set(fmt(getter()))
                return
            on_type(v)
        e.bind("<Return>", _typed)
        e.bind("<FocusOut>", _typed)
        self._entries[key] = evar
        dvar = tk.DoubleVar(value=value)
        sc = ttk.Scale(row, from_=lo, to=hi, variable=dvar,
                       style="Accent.Horizontal.TScale",
                       command=lambda _v, k=key: (
                           None if self._building else on_slide(
                               self._vars[k].get())))
        sc.pack(fill="x")
        self._vars[key] = dvar
        self._getters[key] = getter
        self._fmts[key] = fmt

    # ---- value plumbing ----
    def _sync_all_from_el(self):
        """Push the current elements out to every slider + entry (including the
        derived apogee/perigee rows)."""
        for key, dvar in self._vars.items():
            val = self._getters[key]()
            dvar.set(val)
            self._entries[key].set(self._fmts[key](val))
        self._name.set(self.el["name"])

    @staticmethod
    def _fmt(field, val):
        if field == "ecc":
            return "%.3f" % val
        if field == "alt_km":
            return "%.0f" % val
        return "%.1f" % val

    @staticmethod
    def _snap(field, val):
        """Round a raw slider value to that field's resolution so it's easy to
        land on the value you want."""
        res = _RES.get(field)
        if not res:
            return val
        return round(val / res) * res

    def _on_slider_value(self, field, val):
        val = self._snap(field, val)
        self.el[field] = val
        self.el = lab.clamp_elements(self.el)
        self._entries[field].set(self._fmt(field, self.el[field]))
        self._explain.set(lab.explain(field, self.el))
        self._sync_apsides()
        self._update_derived()
        # heavy sim re-render is coalesced so dragging stays smooth
        self._emit(debounce=True)

    def _on_entry_value(self, field, val):
        self.el = lab.clamp_elements({**self.el, field: val})
        self._sync_all_from_el()
        self._explain.set(lab.explain(field, self.el))
        self._update_derived()
        self._emit()

    # ---- apogee / perigee sliders (map to alt_km + ecc) ----
    def _apsis_value(self, which):
        apo, peri = lab.apsides_from_alt_ecc(self.el["alt_km"], self.el["ecc"])
        return apo if which == "apogee" else peri

    def _on_apsis_value(self, which, val):
        """An apogee or perigee slider/entry moved: combine with the OTHER apsis
        (held fixed) to solve back for mean altitude + eccentricity."""
        val = round(val)
        apo, peri = lab.apsides_from_alt_ecc(self.el["alt_km"], self.el["ecc"])
        if which == "apogee":
            apo = val
        else:
            peri = val
        alt, ecc = lab.alt_ecc_from_apsides(apo, peri)
        self.el = lab.clamp_elements({**self.el, "alt_km": alt, "ecc": ecc})
        # re-sync BOTH apsis rows and the alt/ecc rows from the clamped result
        self._sync_all_from_el()
        got_apo, got_peri = lab.apsides_from_alt_ecc(self.el["alt_km"],
                                                     self.el["ecc"])
        if abs(got_apo - apo) > 1.0 or abs(got_peri - peri) > 1.0:
            self._explain.set(
                "Apogee/perigee clamped to the safe range: apogee %.0f km / "
                "perigee %.0f km (alt %.0f km, ecc %.3f)."
                % (got_apo, got_peri, self.el["alt_km"], self.el["ecc"]))
        else:
            self._explain.set(
                "Apogee %.0f km, perigee %.0f km \u2014 mean altitude %.0f km, "
                "eccentricity %.3f." % (got_apo, got_peri, self.el["alt_km"],
                                        self.el["ecc"]))
        self._update_derived()
        self._emit(debounce=True)

    def _sync_apsides(self):
        """Refresh the apogee/perigee slider rows from the current alt_km + ecc."""
        for key in ("apogee", "perigee"):
            if key in self._vars:
                v = self._apsis_value(key)
                self._vars[key].set(v)
                self._entries[key].set("%.0f" % v)

    def _on_name(self):
        if self._building:
            return
        self.el["name"] = self._name.get()
        self._emit()

    def _apply_preset(self, name):
        preset = dict(PRESETS[name])
        preset["name"] = name.replace(" ", "-").upper()
        self.el = lab.clamp_elements(preset)
        self._building = True
        self._sync_all_from_el()
        self._building = False
        self._explain.set("Loaded the %s preset \u2014 now drag any element to "
                          "see its effect." % name)
        self._update_derived()
        self._emit()

    def _update_derived(self):
        d = lab.derived_readout(self.el)
        # ground-track repeat cycle and node-drift / sun-sync verdict
        if d["repeat"]:
            revs, days = d["repeat"]
            repeat_txt = "%d revs / %d day%s" % (revs, days,
                                                 "" if days == 1 else "s")
        else:
            repeat_txt = "no short cycle"
        ss = "  \u2190 sun-synchronous!" if d["sun_synchronous"] else ""
        self._derived.set(
            "Type:     %s\n"
            "Period:   %.1f min   (mean motion %.4f rev/day)\n"
            "Apogee:   %.0f km    Perigee: %.0f km\n"
            "Footprint:%.1f\u00b0   (~%.0f km radius)\n"
            "Node drift: %+.3f\u00b0/day%s\n"
            "Perigee drift: %+.3f\u00b0/day\n"
            "Repeat track: %s\n"
            "Est. lifetime: %s  (at a typical drag)"
            % (d["type"], d["period_min"], d["mean_motion"],
               d["apogee_km"], d["perigee_km"], d["footprint_deg"],
               d["footprint_km"], d["node_drift_degday"], ss,
               d["perigee_drift_degday"], repeat_txt, d["decay_text"]))

    def _emit(self, debounce=False):
        if not self.on_change:
            return
        if not debounce:
            # immediate (entry box, preset, name): cancel any pending render
            if getattr(self, "_emit_after", None) is not None:
                try:
                    self.win.after_cancel(self._emit_after)
                except Exception:
                    pass
                self._emit_after = None
            self.on_change(dict(self.el))
            return
        # coalesce rapid slider moves: (re)schedule a single render after a short
        # idle so dragging stays smooth and we don't rebuild/redraw per pixel
        if getattr(self, "_emit_after", None) is not None:
            try:
                self.win.after_cancel(self._emit_after)
            except Exception:
                pass
        self._emit_after = self.win.after(60, self._emit_now)

    def _emit_now(self):
        self._emit_after = None
        if self.on_change:
            self.on_change(dict(self.el))

    # ---- compare ----
    def _on_compare_toggle(self):
        if self._cmp_on.get():
            self._compare = dict(self.el)        # freeze current as ghost B
        else:
            self._compare = None
        if self.on_compare:
            self.on_compare(self._compare)

    # ---- save ----
    def _on_save_click(self):
        if self.on_save:
            self.on_save(dict(self.el))

    # ---- glossary ----
    def _show_glossary(self):
        g = tk.Toplevel(self.win)
        g.title("Orbital elements \u2014 glossary")
        g.configure(bg=COL_BG)
        g.geometry("460x560")
        g.transient(self.win)
        canvas = tk.Canvas(g, bg=COL_BG, highlightthickness=0)
        sb = ttk.Scrollbar(g, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_BG)
        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for term, desc in GLOSSARY:
            tk.Label(inner, text=term, bg=COL_BG, fg=COL_ACCENT,
                     font=("DejaVu Sans", 10, "bold"),
                     wraplength=420, justify="left").pack(anchor="w",
                                                          padx=14, pady=(12, 2))
            tk.Label(inner, text=desc, bg=COL_BG, fg=COL_TEXT,
                     font=("DejaVu Sans", 9), wraplength=420,
                     justify="left").pack(anchor="w", padx=14)

    def _start_tour(self):
        def on_step(elements):
            self.el = lab.clamp_elements(elements)
            self._building = True
            self._sync_all_from_el()
            self._building = False
            self._update_derived()
            self._emit()
        WalkthroughDialog(self.win, on_step)

    def focus(self):
        try:
            self.win.lift()
            self.win.focus_force()
        except Exception:
            pass


# --- design-to-a-requirement challenges ---------------------------------------
# each challenge: id -> (title, description, check(derived, el) -> (ok, detail))

def _chk_cover_continent(d, el):
    # footprint radius >= ~25 deg covers a continent-sized area
    ok = d["footprint_deg"] >= 25.0
    return ok, ("footprint %.1f\u00b0 (need \u2265 25\u00b0 \u2014 raise altitude)"
                % d["footprint_deg"])


def _chk_daily_repeat(d, el):
    rep = d["repeat"]
    ok = bool(rep and rep[1] == 1)
    txt = ("repeats every %d revs / %d days" % rep) if rep else "no repeat cycle"
    return ok, txt + " (need a 1-day repeat)"


def _chk_sun_sync(d, el):
    ok = d["sun_synchronous"]
    return ok, ("node drift %+.3f\u00b0/day (need ~+0.986 \u2014 try ~98\u00b0 "
                "incl near 700-800 km)" % d["node_drift_degday"])


def _chk_geo(d, el):
    ok = abs(d["period_min"] - 1436.0) < 12.0 and el["incl"] < 2.0 \
        and el["ecc"] < 0.02
    return ok, ("period %.0f min, incl %.1f\u00b0 (need ~1436 min, ~0\u00b0 "
                "incl, near-circular)" % (d["period_min"], el["incl"]))


def _chk_molniya(d, el):
    ok = (el["ecc"] >= 0.6 and abs(el["incl"] - 63.4) < 2.0
          and d["apogee_km"] > 30000.0)
    return ok, ("ecc %.2f, incl %.1f\u00b0, apogee %.0f km (need ecc \u2265 0.6, "
                "incl ~63.4\u00b0, high apogee)"
                % (el["ecc"], el["incl"], d["apogee_km"]))


CHALLENGES = [
    ("Cover a continent",
     "Design an orbit whose footprint is wide enough to see a whole continent "
     "at once (footprint radius \u2265 25\u00b0).", _chk_cover_continent),
    ("Repeat the same track daily",
     "Make the ground track repeat every single day, so the satellite passes "
     "over the same places at the same times.", _chk_daily_repeat),
    ("Build a sun-synchronous orbit",
     "Tune the inclination and altitude so the orbit plane precesses ~0.986"
     "\u00b0/day to follow the Sun.", _chk_sun_sync),
    ("Park it over one spot (geostationary)",
     "Find the altitude, inclination and eccentricity that make the satellite "
     "appear to hover over the equator.", _chk_geo),
    ("Recreate a Molniya orbit",
     "Use eccentricity and the 63.4\u00b0 magic inclination to linger over the "
     "northern hemisphere.", _chk_molniya),
]


class ChallengeDialog:
    """A 'design to a requirement' panel: pick a goal, edit the lab orbit, and
    the panel checks live whether you've met it."""

    def __init__(self, parent, sim, elements):
        self.sim = sim
        self.win = tk.Toplevel(parent)
        self.win.title("Lab challenges \u2014 design to a requirement")
        self.win.configure(bg=COL_BG)
        self.win.geometry("440x420")
        self.win.transient(parent)

        tk.Label(self.win, text="Pick a challenge, then edit the lab "
                 "satellite to meet it:", bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", 10), wraplength=410,
                 justify="left").pack(anchor="w", padx=14, pady=(14, 6))

        self._sel = tk.IntVar(value=0)
        cf = tk.Frame(self.win, bg=COL_BG)
        cf.pack(fill="x", padx=14)
        for i, (title, desc, _chk) in enumerate(CHALLENGES):
            tk.Radiobutton(cf, text=title, value=i, variable=self._sel,
                           bg=COL_BG, fg=COL_TEXT, selectcolor=COL_PANEL,
                           activebackground=COL_BG, activeforeground=COL_ACCENT,
                           highlightthickness=0, command=self._refresh,
                           font=("DejaVu Sans", 10)).pack(anchor="w")

        self._desc = tk.Label(self.win, text="", bg=COL_BG, fg=COL_MUTED,
                              font=("DejaVu Sans", 9), wraplength=410,
                              justify="left")
        self._desc.pack(anchor="w", padx=14, pady=(8, 4))

        self._verdict = tk.Label(self.win, text="", bg=COL_PANEL, fg=COL_TEXT,
                                 font=("DejaVu Sans", 11, "bold"),
                                 wraplength=410, justify="left", anchor="w")
        self._verdict.pack(fill="x", padx=14, pady=6, ipady=8, ipadx=8)

        bf = tk.Frame(self.win, bg=COL_BG)
        bf.pack(side="bottom", fill="x", padx=14, pady=12)
        ttk.Button(bf, text="Check current orbit",
                   command=self._refresh).pack(side="left")
        ttk.Button(bf, text="Open editor\u2026",
                   command=self._open_editor).pack(side="right")
        self._refresh()

    def _open_editor(self):
        try:
            self.sim._open_lab_editor()
        except Exception:
            pass

    def _refresh(self):
        title, desc, chk = CHALLENGES[self._sel.get()]
        self._desc.configure(text=desc)
        el = lab.clamp_elements(self.sim._lab_elements)
        d = lab.derived_readout(el)
        ok, detail = chk(d, el)
        if ok:
            self._verdict.configure(
                text="\u2713 Challenge met!  %s" % detail, fg=COL_ACCENT)
        else:
            self._verdict.configure(
                text="Not yet:  %s" % detail, fg=COL_WARN)


# walkthrough steps: (title, body, element-override-or-None)
WALKTHROUGH = [
    ("1. Altitude sets the period and footprint",
     "Start with a low orbit. Notice the small footprint and short, fast pass. "
     "Now imagine raising it: higher orbits have longer periods and wider "
     "footprints, so they're in view longer and reach farther. We've set a "
     "low ~400 km LEO \u2014 watch the footprint circle on the map.",
     {"name": "TOUR", "alt_km": 420.0, "ecc": 0.0, "incl": 51.6,
      "raan": 0.0, "argp": 0.0, "ma": 0.0}),
    ("2. Raise the altitude",
     "We've raised the orbit to ~1500 km. The footprint grew and the ground "
     "track moved more slowly. A higher satellite sees more of the Earth at "
     "once \u2014 that's why MEO navigation sats sit ~20,000 km up.",
     {"name": "TOUR", "alt_km": 1500.0, "ecc": 0.0, "incl": 51.6,
      "raan": 0.0, "argp": 0.0, "ma": 0.0}),
    ("3. Inclination sets the latitudes reached",
     "Inclination is the tilt of the orbit plane. We've set 90\u00b0 (polar): "
     "the ground track now crosses every latitude, including the poles. Lower "
     "the inclination and the satellite would stay nearer the equator.",
     {"name": "TOUR", "alt_km": 1500.0, "ecc": 0.0, "incl": 90.0,
      "raan": 0.0, "argp": 0.0, "ma": 0.0}),
    ("4. A sun-synchronous orbit",
     "Set ~98\u00b0 inclination at ~700 km and the orbit plane precesses about "
     "1\u00b0/day to follow the Sun \u2014 a sun-synchronous orbit, used by "
     "imaging satellites so lighting is consistent. This is a slightly "
     "retrograde orbit.",
     {"name": "TOUR", "alt_km": 700.0, "ecc": 0.001, "incl": 98.2,
      "raan": 0.0, "argp": 0.0, "ma": 0.0}),
    ("5. Eccentricity and the Molniya trick",
     "Make the orbit eccentric (0.7) at 63.4\u00b0 inclination with perigee in "
     "the south: the satellite spends most of its time slow and high over the "
     "northern hemisphere. The 63.4\u00b0 'magic' inclination keeps the apogee "
     "from drifting. This is a Molniya orbit.",
     {"name": "TOUR", "alt_km": 26600.0, "ecc": 0.70, "incl": 63.4,
      "raan": 0.0, "argp": 270.0, "ma": 0.0}),
    ("6. Read a pass on the OSCARLOCATOR",
     "The path-arc on the map is what an OSCARLOCATOR transparency traces. "
     "Where the arc enters and leaves your QTH range circle is AOS and LOS. "
     "You can now print this exact satellite as an OSCARLOCATOR, or keep "
     "experimenting with the sliders. Tour complete!",
     None),
]


class WalkthroughDialog:
    """A small stepped tutorial that drives the lab satellite through a sequence
    of teaching orbits, calling on_step(elements) to update the live map."""

    def __init__(self, parent, on_step):
        self.on_step = on_step
        self.i = 0
        self.win = tk.Toplevel(parent)
        self.win.title("Guided tour \u2014 build a satellite pass")
        self.win.configure(bg=COL_BG)
        self.win.geometry("440x300")
        self.win.transient(parent)

        self._title = tk.Label(self.win, text="", bg=COL_BG, fg=COL_ACCENT,
                               font=("DejaVu Sans", 12, "bold"),
                               wraplength=410, justify="left")
        self._title.pack(anchor="w", padx=14, pady=(14, 4))
        self._body = tk.Label(self.win, text="", bg=COL_BG, fg=COL_TEXT,
                              font=("DejaVu Sans", 10), wraplength=410,
                              justify="left")
        self._body.pack(anchor="w", padx=14, pady=4)

        nav = tk.Frame(self.win, bg=COL_BG)
        nav.pack(side="bottom", fill="x", padx=14, pady=12)
        self._step_lbl = tk.Label(nav, text="", bg=COL_BG, fg=COL_MUTED,
                                  font=("DejaVu Sans", 9))
        self._step_lbl.pack(side="left")
        self._next = ttk.Button(nav, text="Next \u2192", command=self._go_next)
        self._next.pack(side="right")
        self._prev = ttk.Button(nav, text="\u2190 Back", command=self._go_prev)
        self._prev.pack(side="right", padx=6)
        self._show()

    def _show(self):
        title, body, el = WALKTHROUGH[self.i]
        self._title.configure(text=title)
        self._body.configure(text=body)
        self._step_lbl.configure(text="Step %d of %d"
                                 % (self.i + 1, len(WALKTHROUGH)))
        self._prev.configure(state=("disabled" if self.i == 0 else "normal"))
        self._next.configure(text=("Finish" if self.i == len(WALKTHROUGH) - 1
                                   else "Next \u2192"))
        if el is not None and self.on_step:
            self.on_step(dict(el))

    def _go_next(self):
        if self.i >= len(WALKTHROUGH) - 1:
            self.win.destroy()
            return
        self.i += 1
        self._show()

    def _go_prev(self):
        if self.i > 0:
            self.i -= 1
            self._show()
