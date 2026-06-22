"""oscarsim.py - an interactive on-screen OSCARLOCATOR.

Lets the user play with a virtual OSCARLOCATOR without printing transparencies:
a polar (or QTH-centred) azimuthal-equidistant base map with a rotatable orbit
path-arc overlay and the satellite footprint. The overlay can be driven these
ways:

  * LIVE      - follow the satellite's real current position and EQX.
  * DRAG      - drag the map disc to rotate the ground-track arc by hand (pin
                the node to any longitude); drag near the moving dot to step the
                minutes after the equator crossing. Works for the catalog
                satellite and the lab satellite alike.
  * NEXT PASS - jump the EQX to the node of the next pass from the station.

The projection conventions match the printable OSCARLOCATOR (north pole: 0 deg
longitude at the bottom, east counter-clockwise; south pole mirrored), so what
you see here is exactly what the printed sheet does.
"""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, MplPanel, COL_PANEL, COL_MUTED, COL_ACCENT,
               COL_ACCENT2, COL_WARN, COL_GRID, COL_TEXT, FONT_MONO, fmt_utc,
               now_unix)
from ...data.worldmap_data import COASTLINES

SIDEREAL_DAY_S = 86164.0905
RE_KM = 6378.135
KM_PER_DEG = math.pi / 180.0 * RE_KM


class OscarSimScreen(Screen):
    live = True            # receive on_tick so the live drive mode tracks in real time

    def build(self):
        self.sat_header("OSCARLOCATOR Simulator")
        self._mode = tk.StringVar(value="live")
        self._proj_mode = tk.StringVar(value="polar-auto")
        self._eqx_lon = tk.DoubleVar(value=0.0)
        self._minute = tk.DoubleVar(value=0.0)
        # interactive "drag the disc to rotate the arc" state (replaces the EQX /
        # minutes sliders): a press remembers where the drag began and the EQX
        # longitude at that moment, so motion rotates the whole ground track
        # east-west by the angular sweep of the pointer about the map centre.
        self._drag_eqx0 = None         # EQX longitude at button-press
        self._drag_ang0 = None         # pointer angle (rad) at button-press
        self._drag_kind = None         # "arc" (rotate) or "minute" (slide marker)
        self._drag_after = None        # pending throttled-render handle
        self._drag_pending = False     # a drag frame is waiting to be drawn
        # when True the arc is positioned by hand (via dragging) rather than
        # following the live sub-point. This lets BOTH catalog and lab satellites
        # be swept by hand; "Go live" clears it.
        self._manual_arc = False
        # two independent overlays: the QTH range circle (fixed, centred on the
        # station) and the satellite's own footprint (its instantaneous coverage
        # circle at its current sub-point)
        self._show_range = tk.BooleanVar(value=True)
        self._show_foot = tk.BooleanVar(value=True)

        # --- educational "lab satellite" state ---
        # a synthetic, user-edited satellite the sim can render and print instead
        # of the catalog selection. Ephemeral until the user clicks Save.
        from .. import lab as _lab
        self._lab_elements = _lab.default_elements()
        self._lab_sat = None           # built lazily when lab mode is entered
        self._lab_pred = None          # dedicated predictor for the lab sat
        self._lab_compare = None       # frozen "ghost B" elements, or None
        self._lab_dialog = None        # the open editor Toplevel, or None

        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        # --- left: controls
        ctrl = ttk.Frame(body, style="Panel.TFrame")
        ctrl.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(ctrl, text="Drive the overlay", style="Panel.TLabel",
                  font=("DejaVu Sans", 11, "bold")).pack(anchor="w", padx=10,
                                                         pady=(10, 4))
        for txt, val in (("Live (current position)", "live"),
                         ("Manual (drag the map)", "manual"),
                         ("Next pass from QTH", "nextpass"),
                         ("Lab satellite", "lab")):
            ttk.Radiobutton(ctrl, text=txt, value=val, variable=self._mode,
                            style="Panel.TRadiobutton",
                            command=self._on_mode).pack(anchor="w", padx=14)

        ttk.Separator(ctrl, orient="horizontal").pack(fill="x", pady=8, padx=8)
        ttk.Label(ctrl, text="Base map", style="Muted.TLabel").pack(
            anchor="w", padx=10)
        for txt, val in (("Polar (auto N/S)", "polar-auto"),
                         ("Polar North", "polar"),
                         ("Polar South", "polar-south"),
                         ("QTH-centred", "qth")):
            ttk.Radiobutton(ctrl, text=txt, value=val,
                            variable=self._proj_mode,
                            style="Panel.TRadiobutton",
                            command=self._render).pack(anchor="w", padx=14)

        ttk.Separator(ctrl, orient="horizontal").pack(fill="x", pady=8, padx=8)
        # --- "Sweep the arc": the equator-crossing longitude and the minutes
        # after the crossing can be set EITHER by dragging the map disc directly
        # (like the web simulator) OR with these two sliders. Dragging and the
        # sliders share the same _eqx_lon / _minute variables, so moving one
        # updates the other automatically.
        self._eqx_row = ttk.Frame(ctrl, style="Panel.TFrame")
        self._eqx_row.pack(fill="x", padx=10, pady=2)
        ttk.Label(self._eqx_row, text="Sweep the arc", style="PanelH.TLabel",
                  font=("DejaVu Sans", 11, "bold")).pack(anchor="w")
        self._sweep_hint = tk.StringVar(value="")
        ttk.Label(self._eqx_row, textvariable=self._sweep_hint,
                  style="Muted.TLabel", wraplength=210,
                  justify="left").pack(anchor="w", pady=(0, 4))

        # Equator-crossing longitude slider (-180..180 deg E)
        self._eqx_lbl = tk.StringVar(value="")
        ttk.Label(self._eqx_row, textvariable=self._eqx_lbl,
                  style="Mono.TLabel").pack(anchor="w")
        self._eqx_scale = ttk.Scale(
            self._eqx_row, from_=-180.0, to=180.0, variable=self._eqx_lon,
            command=self._on_eqx_slider)
        self._eqx_scale.pack(fill="x", pady=(0, 4))

        # Minutes-after-EQX slider (0..one orbital period); the upper bound is
        # set per-satellite in _sync_sweep_sliders.
        self._min_lbl = tk.StringVar(value="")
        ttk.Label(self._eqx_row, textvariable=self._min_lbl,
                  style="Mono.TLabel").pack(anchor="w")
        self._min_scale = ttk.Scale(
            self._eqx_row, from_=0.0, to=95.0, variable=self._minute,
            command=self._on_min_slider)
        self._min_scale.pack(fill="x", pady=(0, 2))

        btnrow = ttk.Frame(self._eqx_row, style="Panel.TFrame")
        btnrow.pack(fill="x", pady=(6, 2))
        ttk.Button(btnrow, text="Next pass",
                   command=self._seed_next_pass_manual).pack(side="left")
        ttk.Button(btnrow, text="Go live",
                   command=self._go_live).pack(side="left", padx=6)
        # the minutes-after-EQX span is one orbit; the drag handler and the
        # minute slider both clamp to it
        self._min_span = 95.0
        # keep a reference so older code paths that call _min_row don't break
        self._min_row = self._eqx_row

        ttk.Separator(ctrl, orient="horizontal").pack(fill="x", pady=8, padx=8)
        ttk.Checkbutton(ctrl, text="Show QTH range circle",
                        variable=self._show_range, style="Panel.TCheckbutton",
                        command=self._render).pack(anchor="w", padx=14)
        ttk.Checkbutton(ctrl, text="Show satellite footprint",
                        variable=self._show_foot, style="Panel.TCheckbutton",
                        command=self._render).pack(anchor="w", padx=14)
        ttk.Button(ctrl, text="Make printable OSCARLOCATOR\u2026",
                   command=self.make_oscarlocator_pdf).pack(anchor="w",
                                                            padx=12, pady=10)
        # lab-mode editor launcher (only meaningful in lab mode; always visible
        # so users can discover it)
        self._lab_btn = ttk.Button(ctrl, text="Edit lab satellite\u2026",
                                   command=self._open_lab_editor)
        self._lab_btn.pack(anchor="w", padx=12, pady=(0, 4))
        # lab-mode extras: a multi-orbit ground-track trace and a challenge
        # launcher. Packed into their own frame so they can be shown only in lab
        # mode and never clutter the normal control column.
        self._lab_extras = ttk.Frame(ctrl, style="Panel.TFrame")
        self._trace_orbits = tk.IntVar(value=0)
        trow = ttk.Frame(self._lab_extras, style="Panel.TFrame")
        trow.pack(fill="x", padx=2, pady=2)
        ttk.Label(trow, text="Trace orbits", style="Muted.TLabel").pack(
            side="left")
        ttk.Spinbox(trow, from_=0, to=6, width=3,
                    textvariable=self._trace_orbits,
                    command=self._render).pack(side="left", padx=6)
        ttk.Button(self._lab_extras, text="Challenges\u2026",
                   command=self._open_challenge).pack(anchor="w", padx=2,
                                                      pady=(2, 2))

        self._readout = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self._readout, style="Muted.TLabel",
                  justify="left").pack(anchor="w", padx=10, pady=(4, 6))

        # --- compact "next EQX" listing so users don't need the EQX page.
        # Ascending nodes for northern stations, descending for southern.
        ttk.Separator(ctrl, orient="horizontal").pack(fill="x", pady=6, padx=8)
        self._eqx_head = tk.StringVar(value="Next equator crossings")
        ttk.Label(ctrl, textvariable=self._eqx_head, style="Panel.TLabel",
                  font=("DejaVu Sans", 10, "bold")).pack(anchor="w", padx=10)
        self._eqx_list = ttk.Frame(ctrl, style="Panel.TFrame")
        self._eqx_list.pack(fill="x", padx=10, pady=(2, 10))

        # --- right: the map
        right = ttk.Frame(body, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.map = MplPanel(right, figsize=(6.4, 6.4), polar=True, dpi=150)
        self.map.pack(fill="both", expand=True, padx=6, pady=6)
        # interactive disc: drag to rotate the arc (and slide the minute marker)
        self.map.canvas.mpl_connect("button_press_event", self._on_press)
        self.map.canvas.mpl_connect("motion_notify_event", self._on_drag)
        self.map.canvas.mpl_connect("button_release_event", self._on_release)

    # ---- mode handling -----------------------------------------------------
    def on_show(self):
        self._on_mode()
        self._refresh_eqx_list()

    def _on_mode(self):
        mode = self._mode.get()
        # The "Sweep the arc" panel (drag readouts + Next pass / Go live) is now
        # useful in every mode EXCEPT live: dragging the disc hand-positions the
        # arc for the catalog or lab satellite alike. Switching drive mode clears
        # any hand positioning so the chosen mode takes over.
        self._manual_arc = (mode == "manual")
        self._eqx_row.pack(fill="x", padx=10, pady=2)
        # the hint reflects whether dragging is available in this mode
        if mode == "live":
            self._sweep_hint.set(
                "Live mode follows the satellite in real time. To set the arc by "
                "hand, switch to \u201cManual (drag the map)\u201d or "
                "\u201cNext pass\u201d, then drag the disc or use the sliders.")
        else:
            self._sweep_hint.set(
                "Drag the map to rotate the arc, and drag near the moving dot to "
                "step the minutes \u2014 or use the two sliders below to set the "
                "equator-crossing longitude and minutes after the crossing.")
        # entering lab mode: ensure the lab satellite exists and open the editor
        if mode == "lab":
            self._ensure_lab_sat()
            self._lab_extras.pack(fill="x", padx=12, pady=(0, 6))
            self._open_lab_editor()
        else:
            self._lab_extras.pack_forget()
        # the 'minutes after EQX' range spans exactly one orbit
        s = self.sat()
        if s is not None:
            per = s.period_min if s.period_min else 95.0
            self._min_span = round(per)
        if mode == "nextpass":
            self._seed_next_pass()
        self._render()

    # ---- educational lab satellite -----------------------------------------
    def _lab_active(self):
        return getattr(self, "_mode", None) is not None \
            and self._mode.get() == "lab"

    def sat(self):
        """Override: in lab mode the simulator renders and prints the synthetic
        lab satellite instead of the catalog selection, so every existing method
        (render, EQX list, readouts, PDF export) uses it automatically."""
        if self._lab_active() and getattr(self, "_lab_sat", None) is not None:
            return self._lab_sat
        return self.store.selected_sat()

    def pred(self):
        """Override: in lab mode use the dedicated lab predictor."""
        if self._lab_active() and getattr(self, "_lab_pred", None) is not None:
            return self._lab_pred
        return self.store.pred

    def _ensure_lab_sat(self):
        from .. import lab as _lab
        from ...engine import Predictor
        self._lab_sat = _lab.make_lab_sat(self._lab_elements)
        if self._lab_pred is None:
            self._lab_pred = Predictor()
        self._lab_pred.set_site(self.store.obs)
        self._lab_pred.set_sat(self._lab_sat)

    def _open_lab_editor(self):
        # switch into lab mode if not already (so the button works as an entry
        # point), then show the editor pop-up
        if self._mode.get() != "lab":
            self._mode.set("lab")
            self._ensure_lab_sat()
        if self._lab_dialog is not None:
            try:
                self._lab_dialog.focus()
                return
            except Exception:
                self._lab_dialog = None
        from ..labdialog import LabDialog
        self._lab_dialog = LabDialog(
            self.frame, self._lab_elements,
            on_change=self._on_lab_change,
            on_save=self._on_lab_save,
            compare=self._lab_compare,
            on_compare=self._on_lab_compare)
        # when the editor window closes, drop the reference
        try:
            self._lab_dialog.win.protocol(
                "WM_DELETE_WINDOW", self._on_lab_dialog_close)
        except Exception:
            pass
        self._render()

    def _on_lab_dialog_close(self):
        try:
            self._lab_dialog.win.destroy()
        except Exception:
            pass
        self._lab_dialog = None

    def _on_lab_change(self, elements):
        self._lab_elements = elements
        self._ensure_lab_sat()
        # keep the minutes span matching one orbit of the new lab orbit
        per = self._lab_sat.period_min if self._lab_sat.period_min else 95.0
        self._min_span = round(per)
        self._render()
        self._refresh_eqx_list()

    def _on_lab_compare(self, compare_elements):
        self._lab_compare = compare_elements
        self._render()

    def _on_lab_save(self, elements):
        """Persist the lab satellite into the catalog as a manual satellite."""
        from tkinter import messagebox
        from .. import lab as _lab
        # give it a unique synthetic NORAD so repeated saves don't collide
        existing = {s.norad for s in self.store.db.sats}
        norad = _lab.LAB_NORAD_BASE
        while norad in existing:
            norad += 1
        sat = _lab.make_lab_sat(elements, norad=norad)
        try:
            if hasattr(self.store, "add_manual_sat"):
                self.store.add_manual_sat(sat)
            else:
                self.store.db.sats.append(sat)
                if hasattr(self.store, "_save_manual_sats"):
                    self.store._save_manual_sats()
            self.app.set_status("Saved lab satellite '%s' to the catalog."
                                % sat.name)
            messagebox.showinfo(
                "Lab satellite saved",
                "'%s' was saved as a manual satellite (NORAD %d). You'll find "
                "it in the Satellites catalog and it persists across element "
                "refreshes." % (sat.name, norad))
        except Exception as e:
            messagebox.showerror("Save failed", str(e))


    # ---- interactive disc: drag to rotate the arc -------------------------
    def _seed_next_pass_manual(self):
        """Jump the hand-positioned arc to the next visible pass, then keep it
        hand-positioned so the user can fine-tune by dragging. Works for the
        catalog satellite and the lab satellite alike."""
        self._manual_arc = True
        self._seed_next_pass()
        self._render()

    def _go_live(self):
        """Return to the live, real-time overlay (clears any hand positioning).
        In lab mode this resumes following the lab satellite; otherwise it
        switches to the live catalog drive."""
        self._manual_arc = False
        if self._mode.get() not in ("live", "lab"):
            self._mode.set("live")
        self._on_mode()

    def _pointer_angle(self, event):
        """Pointer angle (radians) about the map centre, or None if off-axes.
        The polar axes already report event.xdata as theta, which is exactly the
        on-screen angle we want for rotating the arc."""
        if event.inaxes is not self.map.ax or event.xdata is None:
            return None
        return float(event.xdata)          # theta in radians

    def _on_press(self, event):
        ang = self._pointer_angle(event)
        if ang is None:
            return
        # Live mode follows the real satellite, so dragging must NOT take it
        # over -- the user picks "Manual (drag the map)", "Next pass", or "Lab
        # satellite" first. (In those modes the arc is hand-positionable, and for
        # lab the lab satellite stays active.)
        if self._mode.get() == "live":
            return
        # dragging positions the arc by hand. This works in manual, next-pass,
        # and lab modes without leaving them (lab keeps rendering the lab sat).
        if not self._manual_arc:
            # seed the hand arc from wherever the seeded arc currently is, so the
            # first drag starts smoothly from the on-screen position
            _t, lon, minute = self._current_state(self.sat(), self._resolve_proj())
            self._eqx_lon.set(lon)
            self._minute.set(minute)
            self._manual_arc = True
        # decide what the drag adjusts: if the press lands near the minute dot,
        # slide the minute marker; otherwise rotate the whole arc.
        self._drag_kind = "minute" if self._near_minute_dot(event) else "arc"
        self._drag_ang0 = ang
        self._drag_eqx0 = self._eqx_lon.get()
        self._drag_min0 = self._minute.get()

    def _on_drag(self, event):
        if self._drag_ang0 is None:
            return
        ang = self._pointer_angle(event)
        if ang is None:
            return
        if self._drag_kind == "minute":
            # Slide the satellite ALONG the arc by snapping to the arc sample
            # nearest the pointer. (Mapping the pointer's angle about the centre
            # to minutes fails badly: near the centre a tiny move spins the angle
            # wildly, and near the rim a big move barely changes it -- so the dot
            # would jump or refuse to move. Projecting onto the arc tracks the
            # pointer smoothly the whole way across the pass.)
            m = self._minute_for_pointer(event)
            if m is not None:
                span = getattr(self, "_min_span", 95.0) or 95.0
                self._minute.set(min(max(m, 0.0), span))
                self._render_drag()
            return
        # rotate the ground-track east-west; on the south sheet the on-screen
        # sense is mirrored, so flip the sign to keep "drag east -> arc east"
        dtheta = math.degrees(ang - self._drag_ang0)
        dtheta = (dtheta + 180.0) % 360.0 - 180.0
        sign = -1.0 if self._resolve_proj() == "polar-south" else 1.0
        lon = self._drag_eqx0 + sign * dtheta
        lon = ((lon + 180.0) % 360.0) - 180.0
        self._eqx_lon.set(lon)
        self._render_drag()

    def _minute_for_pointer(self, event):
        """Minute-after-EQX of the arc point closest to the pointer, found by
        projecting the pointer's screen position onto the drawn arc. Returns
        None if the pointer is off-axes or no arc is available."""
        if event.xdata is None or event.ydata is None:
            return None
        s = self.sat()
        if s is None:
            return None
        mode = self._resolve_proj()
        is_south = (mode == "polar-south")
        eqx_lon = self._eqx_lon.get()
        period = s.period_min if s.period_min else 95.0
        # pointer in Cartesian screen space (theta, rho) -> (x, y)
        px = event.ydata * math.cos(event.xdata)
        py = event.ydata * math.sin(event.xdata)
        best_m, best_d2 = None, None
        # walk the orbit in ~1-minute steps and keep the closest projected point
        steps = max(60, int(period))
        for k in range(steps + 1):
            m = period * k / steps
            lat, lon = self._track_point(s, eqx_lon, m, is_south)
            rho, theta = self._to_polar(mode, lat, lon)
            x = rho * math.cos(theta)
            y = rho * math.sin(theta)
            d2 = (x - px) ** 2 + (y - py) ** 2
            if best_d2 is None or d2 < best_d2:
                best_d2, best_m = d2, m
        return best_m

    def _on_release(self, _event):
        # ensure the final position is drawn even if the last motion event was
        # coalesced away by the throttle
        if getattr(self, "_drag_pending", False):
            self._drag_pending = False
            if getattr(self, "_drag_after", None) is not None:
                try:
                    self.frame.after_cancel(self._drag_after)
                except Exception:
                    pass
                self._drag_after = None
            self._render()
        self._drag_ang0 = None
        self._drag_eqx0 = None
        self._drag_kind = None

    def _render_drag(self):
        """Throttled render for hand-drags: coalesce rapid motion events into at
        most one redraw per frame interval so the disc keeps up with the pointer
        without queueing more full renders than it can draw. A full clean redraw
        (no blitting) guarantees the old arc is erased -- no ghosting."""
        self._drag_pending = True
        if getattr(self, "_drag_after", None) is not None:
            return                          # a render is already scheduled
        self._drag_after = self.frame.after(16, self._drag_tick)

    def _on_eqx_slider(self, _val=None):
        """The EQX-longitude slider hand-positions the arc (manual mode), like a
        drag. Shares _eqx_lon with the drag handler, so the two stay in sync."""
        if getattr(self, "_syncing_sliders", False):
            return
        if self._mode.get() == "live":
            self._mode.set("manual")
            self._on_mode()
            return
        if not self._manual_arc:
            _t, _lon, minute = self._current_state(self.sat(),
                                                   self._resolve_proj())
            self._minute.set(minute)
            self._manual_arc = True
        self._render_drag()

    def _on_min_slider(self, _val=None):
        """The minutes-after-EQX slider slides the satellite along the arc."""
        if getattr(self, "_syncing_sliders", False):
            return
        if self._mode.get() == "live":
            self._mode.set("manual")
            self._on_mode()
            return
        if not self._manual_arc:
            _t, lon, _minute = self._current_state(self.sat(),
                                                   self._resolve_proj())
            self._eqx_lon.set(lon)
            self._manual_arc = True
        self._render_drag()

    def _sync_sweep_sliders(self):
        """Keep the minute slider's upper bound at one orbital period for the
        current satellite, so the slider spans exactly one pass."""
        s = self.sat()
        period = (s.period_min if s and s.period_min else 95.0)
        self._min_span = period
        try:
            self._min_scale.configure(to=round(period, 1))
        except Exception:
            pass

    def _drag_tick(self):
        self._drag_after = None
        if not getattr(self, "_drag_pending", False):
            return
        self._drag_pending = False
        self._render()
        # if more motion arrived while rendering, schedule the next frame
        if getattr(self, "_drag_pending", False):
            self._drag_after = self.frame.after(16, self._drag_tick)

    def _near_minute_dot(self, event):
        """True if the press is near the satellite's current minute marker, so
        the drag slides the marker along the arc instead of rotating the whole
        arc. Compared in Cartesian screen space so the target is an even disc at
        any radius (an angular tolerance would shrink to nothing near the
        centre, making the dot impossible to grab there)."""
        dot = getattr(self, "_minute_dot_rt", None)
        if dot is None or event.xdata is None or event.ydata is None:
            return False
        th0, r0 = dot
        dx = event.ydata * math.cos(event.xdata) - r0 * math.cos(th0)
        dy = event.ydata * math.sin(event.xdata) - r0 * math.sin(th0)
        # ~10 rho-units of pickup radius, uniform around the dot
        return (dx * dx + dy * dy) <= 10.0 ** 2

    def _seed_next_pass(self):
        """Seed the overlay to the next pass that is actually VISIBLE from the
        station (rises above the horizon), referencing the arc to the equator-
        crossing node of THAT pass's orbit.

        Previously this just grabbed the next equator crossing, which is almost
        always a different orbit than the next visible pass -- so the arc was
        drawn at the wrong longitude (it didn't correspond to the pass the user
        is waiting for). We now find the next visible pass via the pass
        predictor, then take the node (ascending for a northern station,
        descending for a southern one) of that pass's orbit.
        """
        s = self.sat()
        if not s:
            return
        pred = self.pred()
        t = now_unix()
        south = self.store.obs.lat < 0
        period_s = (s.period_min or 95.0) * 60.0
        min_el = getattr(self.store, "min_el", 5.0)

        # the next pass that actually clears the horizon at the QTH
        passes = pred.predict_passes(t, min_el, 1)
        if passes:
            aos = passes[0].aos
            # the matching node of that pass's orbit: the most recent node of the
            # right type at or before AOS (search back a little over one period)
            win = max(2.5 * 3600.0, period_s * 1.6)
            cand = (pred.descending_nodes(aos - win, aos + 600) if south
                    else pred.ascending_nodes(aos - win, aos + 600))
            cand = [n for n in cand if n[0] <= aos + 60.0]
            if cand:
                tc, lon = cand[-1]
                self._eqx_lon.set(lon)
                self._minute.set(0.0)
                self._seed_unix = tc
                return

        # fallback: no visible pass found in range -> next equator crossing
        win = max(2.5 * 3600.0, period_s * 1.6)
        nodes = (pred.descending_nodes(t, t + 3 * 86400) if south
                 else pred.ascending_nodes(t, t + 3 * 86400))
        if nodes:
            tc, lon = nodes[0]
            self._eqx_lon.set(lon)
            self._minute.set(0.0)
            self._seed_unix = tc

    def _refresh_eqx_list(self, n=6):
        """Populate the compact 'next equator crossings' listing: ascending nodes
        for northern stations, descending nodes for southern. Each row is
        clickable to drive the overlay to that EQX."""
        # clear old rows
        for w in self._eqx_list.winfo_children():
            w.destroy()
        s = self.sat()
        if not s:
            ttk.Label(self._eqx_list, text="Select a satellite.",
                      style="Muted.TLabel").pack(anchor="w")
            return
        south = self.store.obs.lat < 0
        self._eqx_head.set("Next equator crossings (%s)"
                           % ("descending" if south else "ascending"))
        pred = self.pred()
        t = now_unix()
        nodes = (pred.descending_nodes(t, t + 2 * 86400) if south
                 else pred.ascending_nodes(t, t + 2 * 86400))[:n]
        if not nodes:
            ttk.Label(self._eqx_list, text="No crossings in the next 2 days.",
                      style="Muted.TLabel").pack(anchor="w")
            return
        for tc, lon in nodes:
            hemi = "E" if lon >= 0 else "W"
            txt = "%s   %6.1f\u00b0%s" % (fmt_utc(tc, "%a %H:%M"), abs(lon), hemi)
            row = ttk.Label(self._eqx_list, text=txt, style="Muted.TLabel",
                            cursor="hand2", font=FONT_MONO)
            row.pack(anchor="w")
            # clicking a row drives the manual overlay to that EQX
            row.bind("<Button-1>",
                     lambda _e, lo=lon, tcc=tc: self._use_eqx(lo, tcc))

    def _use_eqx(self, lon, tc):
        """Drive the simulator to the chosen EQX (manual mode, minute 0)."""
        self._mode.set("manual")
        self._on_mode()
        self._eqx_lon.set(lon)
        self._minute.set(0.0)
        self._seed_unix = tc
        self._render()

    # ---- projection (matches the printable OSCARLOCATOR) -------------------
    def _resolve_proj(self):
        mode = self._proj_mode.get()
        if mode == "polar-auto":
            # In LIVE mode the auto sheet follows the SATELLITE: show the north
            # sheet while the satellite is in the northern hemisphere and the
            # south sheet while it's in the southern, flipping automatically as
            # it crosses the equator so the active pass is always the one drawn.
            # Otherwise (manual / next-pass) fall back to the station hemisphere.
            if self._mode.get() == "live":
                s = self.sat()
                if s is not None:
                    try:
                        lat = self.pred().subpoint_at(now_unix())[0]
                        return "polar-south" if lat < 0 else "polar"
                    except Exception:
                        pass
            mode = "polar-south" if self.store.obs.lat < 0 else "polar"
        return mode

    def _project(self, mode, lat, lon):
        """Return (rho_deg, theta_rad) for the chosen projection, in the same
        convention as oscarlocator.py."""
        if mode == "polar":
            rho = 90.0 - lat
            theta = math.radians(lon)            # axes: S-zero, CCW
        elif mode == "polar-south":
            rho = 90.0 + lat
            theta = math.radians(lon)            # axes: S-zero, CW
        else:  # qth
            rho, brg = self._gc(self.store.obs.lat, self.store.obs.lon,
                                lat, lon)
            theta = math.radians(brg)            # axes: N-zero, CW
        return rho, theta

    @staticmethod
    def _gc(lat1, lon1, lat2, lon2):
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dl = math.radians(lon2 - lon1)
        ca = math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * \
            math.cos(dl)
        ca = max(-1.0, min(1.0, ca))
        d = math.degrees(math.acos(ca))
        y = math.sin(dl) * math.cos(p2)
        x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * \
            math.cos(dl)
        brg = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
        return d, brg

    def _setup_axes(self, ax, mode, rmax):
        if mode == "polar":
            ax.set_theta_zero_location("S")
            ax.set_theta_direction(1)
        elif mode == "polar-south":
            ax.set_theta_zero_location("S")
            ax.set_theta_direction(-1)
        else:
            ax.set_theta_zero_location("N")
            ax.set_theta_direction(-1)
        ax.set_rlim(0, rmax * 1.25)
        ax.set_rticks([])
        ax.set_xticks([])
        # The custom _draw_rim draws the instrument's rim circle at exactly rmax.
        # Hide matplotlib's own polar frame spine (which sits at the rlim edge)
        # so we don't get a second, larger rim circle around the labels.
        try:
            ax.spines["polar"].set_visible(False)
        except Exception:
            pass
        ax.set_facecolor(COL_PANEL)

    # ---- rendering ---------------------------------------------------------
    def _render(self):
        s = self.sat()
        self.map.clear(polar=True)
        ax = self.map.ax
        ax.set_facecolor(COL_PANEL)
        if not s:
            ax.set_title("Select a satellite first.", color=COL_MUTED,
                         fontsize=10)
            self.map.draw()
            return
        mode = self._resolve_proj()
        if mode in ("polar", "polar-south"):
            rmax = 90.0
        else:
            rmax = max(50.0, min(80.0, abs(self.store.obs.lat) + 25.0))
        self._setup_axes(ax, mode, rmax)

        self._draw_graticule(ax, mode, rmax)
        self._draw_rim(ax, mode, rmax)
        self._draw_coastlines(ax, mode, rmax)
        self._draw_qth(ax, mode, rmax)

        t, eqx_lon, minute = self._current_state(s, mode)
        live = (self._mode.get() in ("live", "lab")) and not self._manual_arc

        if self._lab_active() and self._lab_compare is not None:
            self._draw_compare_ghost(ax, mode, rmax)
        if self._lab_active() and self._trace_orbits.get() > 0:
            self._draw_orbit_trace(ax, mode, rmax, s)

        self._draw_track(ax, mode, rmax, s, eqx_lon)
        self._draw_satellite(ax, mode, rmax, s, t, eqx_lon, minute, live)

        # keep the minute slider's range matched to this satellite's period
        self._sync_sweep_sliders()

        # A single canvas draw per frame. (An earlier blitting fast-path that
        # cached the static layer and repainted only the arc was removed: on the
        # real TkAgg backend restore_region/blit left the previous arc visible
        # -- the "moved arc stays on the map" ghosting -- and stuttered. Clearing
        # and redrawing the whole scene each frame is always correct, and the
        # drag is kept smooth by coalescing motion events in _on_drag instead.)
        self.map.draw()
        self._update_readout(s, t, eqx_lon, minute)

    def _draw_compare_ghost(self, ax, mode, rmax):
        """Draw the frozen comparison orbit (ghost B) as a faint dashed track +
        footprint so the user can contrast it with the orbit they're editing."""
        from .. import lab as _lab
        from ...engine import Predictor
        try:
            gsat = _lab.make_lab_sat(self._lab_compare)
            gpred = Predictor()
            gpred.set_site(self.store.obs)
            gpred.set_sat(gsat)
        except Exception:
            return
        t = now_unix()
        # ghost track: sample one full orbit from the subpoint forward
        period = gsat.period_min * 60.0 if gsat.period_min else 5400.0
        pts = []
        for k in range(0, 101):
            tt = t + (k / 100.0) * period
            lat, lon, _ = gpred.subpoint_at(tt)
            pts.append((lon, lat))
        self._poly(ax, mode, pts, COL_MUTED, 1.2, rmax, dashed=True)
        # ghost footprint at its current sub-point
        glat, glon, galt = gpred.subpoint_at(t)
        self._draw_footprint(ax, mode, rmax, glat, glon,
                             _lab.footprint_radius_deg(galt),
                             color=COL_MUTED, dashed=True)

    def _draw_orbit_trace(self, ax, mode, rmax, s):
        """Draw the previous N successive orbits as progressively fainter ground
        tracks, so the per-orbit westward drift (Earth rotation) is visible."""
        n = self._trace_orbits.get()
        pred = self.pred()
        period = s.period_min * 60.0 if s.period_min else 5400.0
        t0 = now_unix()
        for k in range(1, n + 1):
            # orbit k back in time
            t_start = t0 - k * period
            pts = []
            for j in range(0, 101):
                tt = t_start + (j / 100.0) * period
                lat, lon, _ = pred.subpoint_at(tt)
                pts.append((lon, lat))
            # fade with age
            alpha = max(0.12, 0.6 - 0.12 * k)
            self._poly_alpha(ax, mode, pts, COL_ACCENT2, 1.0, rmax, alpha)

    def _poly_alpha(self, ax, mode, lonlat_pts, color, lw, rmax, alpha):
        th, rr, prev = [], [], None
        for lon, lat in lonlat_pts:
            rho, theta = self._project(mode, lat, lon)
            if rho > rmax:
                if len(th) > 1:
                    ax.plot(th, rr, color=color, linewidth=lw, alpha=alpha)
                th, rr, prev = [], [], None
                continue
            if prev is not None and abs(theta - prev) > math.pi:
                if len(th) > 1:
                    ax.plot(th, rr, color=color, linewidth=lw, alpha=alpha)
                th, rr = [], []
            th.append(theta)
            rr.append(rho)
            prev = theta
        if len(th) > 1:
            ax.plot(th, rr, color=color, linewidth=lw, alpha=alpha)

    def _open_challenge(self):
        from ..labdialog import ChallengeDialog
        ChallengeDialog(self.frame, self, self._lab_elements)

    def _current_state(self, s, view_mode):
        """Return (display_time, eqx_lon, minute) for the active mode.

        ``view_mode`` is the resolved projection ("polar", "polar-south", or a
        QTH-centred mode). The EQX node is chosen to MATCH the view so the arc
        and the live satellite share one reference: the south sheet uses
        descending nodes, every other view ascending nodes.

        In live mode, if the satellite is currently IN the viewed hemisphere we
        reference the most recent matching node (the pass in progress). If it is
        in the OPPOSITE hemisphere -- so there's no live pass to follow on this
        sheet -- we instead reference the NEXT matching node, i.e. the arc for
        the upcoming pass into the viewed hemisphere. (With "Polar (auto N/S)"
        the sheet follows the satellite, so the in-progress pass is the common
        case; this rule matters for a fixed sheet, or for the QTH view.)
        """
        pred = self.pred()
        mode = self._mode.get()
        # a hand-positioned (dragged) arc uses the manual EQX/minute regardless
        # of the drive mode, so lab and live sats can both be swept by hand
        if getattr(self, "_manual_arc", False):
            minute = self._minute.get()
            tc = getattr(self, "_seed_unix", now_unix())
            return tc + minute * 60.0, self._eqx_lon.get(), minute
        if mode in ("live", "lab"):
            t = now_unix()
            south = (view_mode == "polar-south")
            # The search window must comfortably exceed ONE orbital period, or a
            # long-period satellite's most-recent (or next) matching node can
            # fall outside a fixed window -- which happened for RS-44 (period
            # ~121 min > a fixed 120 min window): right at an equator crossing
            # the window found no node and the arc failed to advance. Use ~1.6
            # periods, with a floor for short-period birds.
            period_s = (s.period_min or 95.0) * 60.0
            win = max(2.5 * 3600.0, period_s * 1.6)
            # is the satellite currently in the hemisphere this sheet shows?
            cur_lat = pred.subpoint_at(t)[0]
            in_view = (cur_lat < 0) if south else (cur_lat >= 0)
            if in_view:
                # The pass in progress: the most recent matching node at or
                # before now. We search a little PAST `t` as well, because the
                # node-finder brackets crossings with a coarse (~period/12) scan
                # and a crossing that happened only a minute ago may not be
                # bracketed by a window that stops exactly at `t` -- which left
                # the arc referencing the PREVIOUS node for a few minutes right
                # after a crossing. Take the last node at or before now.
                look = (pred.descending_nodes(t - win, t + 600) if south
                        else pred.ascending_nodes(t - win, t + 600))
                nodes = [n for n in look if n[0] <= t + 30.0]
                if nodes:
                    tc, lon = nodes[-1]
                    return t, lon, (t - tc) / 60.0
            else:
                # no live pass on this sheet -> show the NEXT pass into view:
                # the upcoming matching node, with the clock counting up to it
                # (negative "minutes since node" means the pass hasn't started).
                fwd = (pred.descending_nodes(t, t + win) if south
                       else pred.ascending_nodes(t, t + win))
                if fwd:
                    tc, lon = fwd[0]
                    return t, lon, (t - tc) / 60.0
            sp = pred.subpoint_at(t)
            return t, sp[1], 0.0
        if mode == "nextpass":
            tc = getattr(self, "_seed_unix", now_unix())
            minute = self._minute.get()
            return tc + minute * 60.0, self._eqx_lon.get(), minute
        # manual
        minute = self._minute.get()
        return now_unix(), self._eqx_lon.get(), minute

    def _draw_rim(self, ax, mode, rmax):
        """Outer rim circle with degree tick marks (every 5 deg, longer every
        30 deg) and a ring of longitude labels (polar) or azimuth labels (QTH)
        around the edge -- matching the OSCARLOCATOR web simulator so the rim
        reads like a protractor and the longitude scale is visible at a glance.

        The rim circle and all 72 tick marks are drawn as two LineCollections
        (one per line weight) rather than ~73 separate ax.plot() calls, which is
        much cheaper to build and redraw -- this is the single biggest cost in a
        drag re-render.
        """
        from matplotlib.collections import LineCollection
        # rim circle as one polyline
        th_full = [math.radians(a) for a in range(0, 361, 2)]
        ax.plot(th_full, [rmax] * len(th_full), color=COL_MUTED,
                linewidth=1.4, zorder=3)
        # tick marks every 5 deg, longer + heavier every 30 deg, batched by weight
        major_segs, minor_segs = [], []
        for a in range(0, 360, 5):
            major = (a % 30 == 0)
            ln = (rmax * 0.034) if major else (rmax * 0.017)
            ar = math.radians(a)
            seg = [(ar, rmax - ln), (ar, rmax)]
            (major_segs if major else minor_segs).append(seg)
        ax.add_collection(LineCollection(
            minor_segs, colors=COL_MUTED, linewidths=0.6, zorder=3,
            capstyle="butt"))
        ax.add_collection(LineCollection(
            major_segs, colors=COL_MUTED, linewidths=1.0, zorder=3,
            capstyle="butt"))
        # labels around the rim, pushed well OUTSIDE the rim circle so there is
        # a clear gap between the longitude values and the rim (rim is at rmax;
        # rlim extends to ~1.25*rmax). The font is kept small (matching the web
        # simulator) so the wider longitude labels like "150 W" don't crowd one
        # another at the diagonals.
        lab_r = rmax * 1.17
        if mode in ("polar", "polar-south"):
            south = (mode == "polar-south")
            for lon in range(0, 360, 30):
                disp = lon if lon <= 180 else lon - 360
                hemi = "E" if 0 < disp < 180 else ("W" if disp < 0 else "")
                txt = "%d\u00b0%s" % (abs(disp), hemi)
                ax.text(math.radians(lon), lab_r, txt, color=COL_MUTED,
                        fontsize=5.5, ha="center", va="center", zorder=3)
            # latitude ring labels along the ~60 deg meridian, kept small and
            # inside the rings so they don't clutter the disc
            for lat_abs in range(15, 90, 15):
                ring = 90 - lat_abs
                disp_lat = -lat_abs if south else lat_abs
                ax.text(math.radians(60), ring, "%d\u00b0" % disp_lat,
                        color=COL_MUTED, fontsize=5.5, ha="center",
                        va="center", alpha=0.85, zorder=3)
        else:
            # QTH: cardinal letters + intercardinal azimuth numbers
            for az, name in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
                ax.text(math.radians(az), lab_r, name, color=COL_TEXT,
                        fontsize=9, fontweight="bold", ha="center",
                        va="center", zorder=3)
            for az in range(30, 360, 30):
                if az % 90 == 0:
                    continue
                ax.text(math.radians(az), lab_r, "%d\u00b0" % az,
                        color=COL_MUTED, fontsize=5.5, ha="center",
                        va="center", zorder=3)
            # range-ring km labels along the 45 deg radial
            for rho in range(30, int(rmax) + 1, 30):
                km = round(rho * 111.195 / 100.0) * 100
                ax.text(math.radians(45), rho, "%d km" % km, color=COL_MUTED,
                        fontsize=5.5, ha="left", va="bottom", alpha=0.85,
                        zorder=3)

    def _draw_graticule(self, ax, mode, rmax):
        if mode in ("polar", "polar-south"):
            lat_lo = -90 if mode == "polar-south" else 0
            lat_hi = 1 if mode == "polar-south" else 91
            for lon in range(-180, 180, 30):
                pts = [(lon, j) for j in range(lat_lo, lat_hi, 3)]
                self._poly(ax, mode, pts, COL_GRID, 0.5, rmax)
            par_lo = -75 if mode == "polar-south" else 0
            par_hi = 1 if mode == "polar-south" else 76
            for lat in range(par_lo, par_hi, 15):
                pts = [(k, lat) for k in range(-180, 181, 4)]
                self._poly(ax, mode, pts, COL_GRID, 0.5, rmax)
        else:
            for rho in range(30, int(rmax) + 1, 30):
                th = [math.radians(a) for a in range(0, 361, 3)]
                ax.plot(th, [rho] * len(th), color=COL_GRID, linewidth=0.5)
            for az in range(0, 360, 30):
                ax.plot([math.radians(az)] * 2, [0, rmax], color=COL_GRID,
                        linewidth=0.5)

    def _draw_coastlines(self, ax, mode, rmax):
        for poly in self._coastline_polys():
            self._poly(ax, mode, poly, "#5a86a8", 0.7, rmax)

    def _coastline_polys(self):
        """High-resolution coastline polylines as lists of (lon, lat).

        Prefers cartopy's Natural Earth coastline geometry (much denser and more
        accurate than the small bundled outline); falls back to the bundled
        COASTLINES when cartopy isn't installed. The result is cached per session
        so we only build it once."""
        cached = getattr(self, "_coast_cache", None)
        if cached is not None:
            return cached
        polys = self._cartopy_coastlines()
        if not polys:
            polys = [[(lon, lat) for lon, lat in poly] for poly in COASTLINES]
        self._coast_cache = polys
        return polys

    @staticmethod
    def _cartopy_coastlines(resolution="110m"):
        """Return coastline polylines from cartopy/Natural Earth, or [] if
        cartopy isn't available."""
        try:
            import cartopy.feature as cfeature
            from shapely.geometry import LineString, MultiLineString
        except Exception:
            return []
        try:
            feat = cfeature.NaturalEarthFeature("physical", "coastline",
                                                resolution)
            polys = []
            for geom in feat.geometries():
                geoms = (geom.geoms if isinstance(geom, MultiLineString)
                         else [geom])
                for g in geoms:
                    if isinstance(g, LineString):
                        polys.append([(x, y) for x, y in g.coords])
            return polys
        except Exception:
            return []

    def _poly(self, ax, mode, lonlat_pts, color, lw, rmax, dashed=False):
        ls = (0, (4, 3)) if dashed else "-"
        th, rr = [], []
        prev = None
        for lon, lat in lonlat_pts:
            rho, theta = self._project(mode, lat, lon)
            if rho > rmax:
                if len(th) > 1:
                    ax.plot(th, rr, color=color, linewidth=lw, linestyle=ls)
                th, rr, prev = [], [], None
                continue
            if prev is not None and abs(theta - prev) > math.pi:
                if len(th) > 1:
                    ax.plot(th, rr, color=color, linewidth=lw, linestyle=ls)
                th, rr = [], []
            th.append(theta)
            rr.append(rho)
            prev = theta
        if len(th) > 1:
            ax.plot(th, rr, color=color, linewidth=lw, linestyle=ls)

    def _draw_qth(self, ax, mode, rmax):
        rho, theta = self._project(mode, self.store.obs.lat,
                                   self.store.obs.lon)
        if rho <= rmax:
            ax.plot([theta], [rho], marker="*", color=COL_WARN, markersize=13,
                    zorder=6)

    def _canonical_track(self, s, descending):
        # Reuse the printable OSCARLOCATOR's corrected ground-track model
        # (eccentricity via Kepler, native retrograde handling) so the simulator
        # and the printout draw exactly the same arc.
        from ..oscarlocator import _canonical_track as _ct
        return _ct(s, descending=descending)

    def _draw_track(self, ax, mode, rmax, s, eqx_lon):
        is_south = (mode == "polar-south")
        track = self._canonical_track(s, descending=is_south)
        th, rr = [], []
        prev = None
        ticks = []
        for lon_rel, lat, minute in track:
            lon = lon_rel + eqx_lon
            if mode == "polar":
                rho = 90.0 - lat
                theta = math.radians(lon)
            elif mode == "polar-south":
                rho = 90.0 + lat
                theta = math.radians(lon)
            else:
                rho, brg = self._gc(self.store.obs.lat, self.store.obs.lon,
                                    lat, lon)
                theta = math.radians(brg)
            if rho > rmax:
                if len(th) > 1:
                    ax.plot(th, rr, color=COL_ACCENT, linewidth=2.0, zorder=4)
                th, rr, prev = [], [], None
                continue
            if prev is not None and abs(theta - prev) > math.pi:
                if len(th) > 1:
                    ax.plot(th, rr, color=COL_ACCENT, linewidth=2.0, zorder=4)
                th, rr = [], []
            th.append(theta)
            rr.append(rho)
            ticks.append((theta, rho, minute))
            prev = theta
        if len(th) > 1:
            ax.plot(th, rr, color=COL_ACCENT, linewidth=2.0, zorder=4)
        # 10-minute labels: draw each one exactly ONCE. The track is sampled
        # densely, so several consecutive samples fall near the same integer
        # minute; without de-duping, the same number is drawn on top of itself
        # slightly offset, which looks blurry. Pick the single sample closest to
        # each 10-minute mark.
        if ticks:
            period = ticks[-1][2]
            # Choose a label interval and font size that scale with the orbital
            # period, so a long high-orbit pass doesn't crowd dozens of numbers
            # on top of each other. Aim for roughly 8-12 labels along the arc.
            step = 10
            for cand in (5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240):
                if period / cand <= 12:
                    step = cand
                    break
            else:
                step = max(10, int(round(period / 12.0 / 10.0)) * 10)
            n_labels = max(1, int(period) // step + 1)
            tick_font = 7 if n_labels <= 10 else 6 if n_labels <= 16 else 5
            for target in range(0, int(period) + 1, step):
                best = min(ticks, key=lambda tk: abs(tk[2] - target))
                if abs(best[2] - target) > step * 0.25:
                    continue
                theta, rho, _m = best
                ax.plot([theta], [rho], marker="o", markersize=5,
                        markerfacecolor="#9ecbff", markeredgecolor=COL_PANEL,
                        markeredgewidth=0.8, zorder=5)
                # the 0-minute mark sits on the equator-crossing node, where the
                # EQX indicator already is -- its label is superfluous and
                # collides, so draw the dot but skip the number.
                if target == 0:
                    continue
                ax.annotate(
                    "%d" % target, xy=(theta, rho),
                    xytext=(6, 0), textcoords="offset points",
                    fontsize=tick_font, color="#cfe6ff", ha="left",
                    va="center", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.12", fc=COL_PANEL,
                              ec="none", alpha=0.7))

    def _track_point(self, s, eqx_lon, minute, is_south):
        """Sub-point (lat, lon) ON the drawn pass arc at the given minute after
        the EQX. Interpolates the same canonical track the arc is plotted from,
        so the marker always sits exactly on the line."""
        track = self._canonical_track(s, descending=is_south)
        period_min = s.period_min if s.period_min else 95.0
        m = minute % period_min
        # find the bracketing samples and linearly interpolate
        best = min(range(len(track)), key=lambda i: abs(track[i][2] - m))
        j = best + 1 if best + 1 < len(track) else best
        lon0, lat0, m0 = track[best]
        lon1, lat1, m1 = track[j]
        if m1 != m0:
            f = (m - m0) / (m1 - m0)
        else:
            f = 0.0
        lat = lat0 + (lat1 - lat0) * f
        # interpolate longitude with wraparound safety
        dlon = ((lon1 - lon0 + 540) % 360) - 180
        lon_rel = lon0 + dlon * f
        return lat, lon_rel + eqx_lon

    def _to_polar(self, mode, lat, lon):
        if mode == "polar":
            return 90.0 - lat, math.radians(lon)
        if mode == "polar-south":
            return 90.0 + lat, math.radians(lon)
        rho, brg = self._gc(self.store.obs.lat, self.store.obs.lon, lat, lon)
        return rho, math.radians(brg)

    def _draw_satellite(self, ax, mode, rmax, s, t, eqx_lon, minute, live):
        """Draw the satellite marker. In live mode it follows the true current
        sub-point; in manual / next-pass mode it slides along the drawn arc as
        the 'minutes after EQX' changes. The footprint is ALWAYS centred on the
        QTH (the OSCARLOCATOR range reticle is a fixed QTH-centred overlay)."""
        pred = self.pred()
        is_south = (mode == "polar-south")
        if live:
            lat, lon, alt = pred.subpoint_at(t)
        else:
            lat, lon = self._track_point(s, eqx_lon, minute, is_south)
            # altitude from the ephemeris (near-constant for these orbits)
            _a, _o, alt = pred.subpoint_at(now_unix())
        rho, theta = self._to_polar(mode, lat, lon)
        # remember the dot's polar position so a drag starting near it slides the
        # minute marker instead of rotating the whole arc
        self._minute_dot_rt = (theta, rho) if rho <= rmax else None
        if rho <= rmax:
            ax.plot([theta], [rho], marker="o", markersize=9,
                    color=COL_ACCENT2, markeredgecolor="white",
                    markeredgewidth=1.0, zorder=8)
        if self._show_range.get():
            # The QTH range circle covers the MAX ground distance at which this
            # satellite is ever visible -- i.e. the footprint radius at the
            # satellite's MEAN orbital altitude. This is a fixed circle (it
            # doesn't jitter with the live sub-point altitude).
            reticle = self._footprint_deg(self._mean_alt_km(s))
            self._draw_footprint(ax, mode, rmax, self.store.obs.lat,
                                 self.store.obs.lon, reticle, color="#d29922")
        if self._show_foot.get() and rho <= rmax:
            # the satellite's ACTUAL coverage circle at its current sub-point
            # (its instantaneous footprint), so you can see whether your QTH is
            # inside it. Shown in live mode (true sub-point) and along the arc.
            foot = self._footprint_deg(alt)
            self._draw_footprint(ax, mode, rmax, lat, lon, foot,
                                 color=COL_ACCENT2, lw=1.2, dashed=True)

    @staticmethod
    def _mean_alt_km(s):
        """Mean orbital altitude (km) from the mean motion: semi-major axis minus
        Earth radius."""
        try:
            from ...engine import analysis as A
            a = A.semi_major_axis_km(s.mean_motion)
            if a > 0:
                return max(a - RE_KM, 1.0)
        except Exception:
            pass
        # fallback: derive from period via Kepler's third law
        per_s = (s.period_min if s.period_min else 95.0) * 60.0
        mu = 398600.4418
        a = (mu * (per_s / (2 * math.pi)) ** 2) ** (1.0 / 3.0)
        return max(a - RE_KM, 1.0)

    @staticmethod
    def _footprint_deg(alt_km):
        re = RE_KM
        x = re / (re + max(alt_km, 1.0))
        return math.degrees(math.acos(max(-1.0, min(1.0, x))))

    def _draw_footprint(self, ax, mode, rmax, qlat, qlon, foot_deg,
                        color="#d29922", lw=1.4, dashed=False):
        p1 = math.radians(qlat)
        l1 = math.radians(qlon)
        d = math.radians(foot_deg)
        ls = (0, (4, 3)) if dashed else "solid"
        th, rr = [], []
        prev = None
        for i in range(0, 361, 4):
            brg = math.radians(i)
            lat2 = math.asin(math.sin(p1) * math.cos(d) +
                             math.cos(p1) * math.sin(d) * math.cos(brg))
            lon2 = l1 + math.atan2(math.sin(brg) * math.sin(d) * math.cos(p1),
                                   math.cos(d) - math.sin(p1) * math.sin(lat2))
            la = math.degrees(lat2)
            lo = (math.degrees(lon2) + 540) % 360 - 180
            if mode == "polar":
                rho = 90.0 - la
                theta = math.radians(lo)
            elif mode == "polar-south":
                rho = 90.0 + la
                theta = math.radians(lo)
            else:
                rho, brg2 = self._gc(self.store.obs.lat, self.store.obs.lon,
                                     la, lo)
                theta = math.radians(brg2)
            if rho > rmax:
                if len(th) > 1:
                    ax.plot(th, rr, color=color, linewidth=lw, linestyle=ls,
                            zorder=5)
                th, rr, prev = [], [], None
                continue
            if prev is not None and abs(theta - prev) > math.pi:
                if len(th) > 1:
                    ax.plot(th, rr, color=color, linewidth=lw, linestyle=ls,
                            zorder=5)
                th, rr = [], []
            th.append(theta)
            rr.append(rho)
            prev = theta
        if len(th) > 1:
            ax.plot(th, rr, color=color, linewidth=lw, linestyle=ls, zorder=5)

    def _update_readout(self, s, t, eqx_lon, minute):
        pred = self.pred()
        lat, lon, alt = pred.subpoint_at(t)
        az, el = pred.azel_at(t)
        vis = "VISIBLE" if el > 0 else "below horizon"
        hemi_e = "E" if eqx_lon >= 0 else "W"
        self._eqx_lbl.set("%.1f\u00b0 %s" % (abs(eqx_lon), hemi_e))
        self._min_lbl.set("%.0f min after EQX" % (minute + 0.0 if minute > 0.05
                                                  else 0))
        self._readout.set(
            "Sub-point: %.1f\u00b0%s, %.1f\u00b0%s\n"
            "Altitude: %.0f km\n"
            "From your QTH: az %.0f\u00b0, el %.0f\u00b0 (%s)\n"
            "Time: %s UTC" % (
                abs(lat), "N" if lat >= 0 else "S",
                abs(lon), "E" if lon >= 0 else "W",
                alt, az % 360, el, vis,
                fmt_utc(t, "%Y-%m-%d %H:%M:%S")))

    def on_tick(self, now_dt=None):
        # keep the live view moving in real time; manual / next-pass modes and a
        # hand-positioned (dragged) arc hold their position, so don't redraw
        if self._mode.get() in ("live", "lab") and not self._manual_arc:
            self._render()
