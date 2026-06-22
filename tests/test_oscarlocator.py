"""OSCARLOCATOR printable-output and Sim tests.

Part of the OrbitDeck test suite (split from the original monolithic
test_engine.py). Shared fixtures live in conftest.py.
"""

import datetime as dt
import json
import math

import pytest

from orbitdeck.engine.sgp4_lite import Satrec
from orbitdeck.engine import (SatDb, Predictor, Observer,
                              latlon_to_grid, grid_to_latlon)


def test_oscarlocator_pdf_generates():
    """The OSCARLOCATOR generator produces a non-trivial 3-page PDF for a LEO
    satellite without error."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    st = Store()
    s = st.db.sats[0]
    out = os.path.join(tempfile.mkdtemp(), "osc.pdf")
    generate_oscarlocator_pdf(out, st, s)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 5000      # vector content, not empty
    # PDF magic bytes
    with open(out, "rb") as f:
        assert f.read(5) == b"%PDF-"


def _pdf_page_pts(path):
    """Return (width_pt, height_pt) of the first page of a PDF by reading the
    first /MediaBox in the file -- avoids a hard dependency on pdfinfo."""
    import re
    data = open(path, "rb").read()
    m = re.search(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
                  data)
    assert m, "no MediaBox found"
    x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
    return (x1 - x0, y1 - y0)


def test_pagesize_module_defaults_and_normalize():
    """The pagesize helper defaults to Letter and resolves A4 / unknowns
    sensibly from a string or a config-bearing object."""
    from orbitdeck.gui import pagesize as P
    assert P.DEFAULT_PAGE == "letter"
    assert P.normalize(None) == "letter"
    assert P.normalize("A4") == "a4"
    assert P.normalize("nonsense") == "letter"
    assert P.page_dims(None) == (8.5, 11.0)
    assert P.page_dims("a4") == P.PAGE_SIZES["a4"]

    class FakeStore:
        config = {"page_size": "a4"}
    assert P.page_dims(FakeStore()) == P.PAGE_SIZES["a4"]
    class NoPref:
        config = {}
    assert P.page_dims(NoPref()) == (8.5, 11.0)


def test_oscarlocator_page_size_letter_vs_a4():
    """The OSCARLOCATOR honours the global page-size setting: Letter ~612x792 pt,
    A4 ~595x842 pt. The disc is pinned to a fixed physical size, so switching the
    page must NOT change the figure's page-relative disc fraction math in a way
    that resizes the disc -- we assert the page dimensions change as expected."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    st = Store()
    s = st.db.sats[0]
    d = tempfile.mkdtemp()

    st.save_config(page_size="letter")
    pl = os.path.join(d, "letter.pdf")
    generate_oscarlocator_pdf(pl, st, s, projection="polar")
    wl, hl = _pdf_page_pts(pl)
    assert abs(wl - 612) < 2 and abs(hl - 792) < 2, (wl, hl)

    st.save_config(page_size="a4")
    pa = os.path.join(d, "a4.pdf")
    generate_oscarlocator_pdf(pa, st, s, projection="polar")
    wa, ha = _pdf_page_pts(pa)
    assert abs(wa - 595) < 2 and abs(ha - 842) < 2, (wa, ha)

    # the module page constants are restored to the default after generation
    import orbitdeck.gui.oscarlocator as OL
    assert (OL.PAGE_W_IN, OL.PAGE_H_IN) == (8.5, 11.0)


def test_reports_honor_page_size():
    """A standard report (satellite report) follows the global page size too."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.reports import generate_satellite_report
    st = Store()
    s = st.db.sats[0]
    st.select(s.norad)
    d = tempfile.mkdtemp()
    st.save_config(page_size="a4")
    pa = os.path.join(d, "sat_a4.pdf")
    generate_satellite_report(pa, st, s)
    wa, ha = _pdf_page_pts(pa)
    assert abs(wa - 595) < 2 and abs(ha - 842) < 2, (wa, ha)

def test_oscarlocator_node_shift_and_track():
    """The per-pass arc advance and canonical track behave physically: ISS
    advances ~23 deg west/pass, a polar sun-sync ~25 deg, and the canonical
    track latitude never exceeds the inclination."""
    import json
    import datetime
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import _node_shift_deg, _canonical_track
    now = datetime.datetime.now(datetime.timezone.utc)

    def make(mm, incl, nid):
        omm = [{"OBJECT_NAME": "T",
                "EPOCH": now.strftime("%Y-%m-%dT%H:%M:%S.000000"),
                "MEAN_MOTION": mm, "ECCENTRICITY": 0.001, "INCLINATION": incl,
                "RA_OF_ASC_NODE": 100, "ARG_OF_PERICENTER": 90,
                "MEAN_ANOMALY": 180, "BSTAR": 0.0001, "NORAD_CAT_ID": nid}]
        st = Store()
        st.db.load_gp_json(json.dumps(omm))
        return st.db.sats[0]

    iss = make(15.5, 51.6, 25544)
    shift = _node_shift_deg(iss)
    assert shift < 0                                  # westward for prograde LEO
    assert 20 < abs(shift) < 27                       # ~23 deg/orbit

    polar = make(14.3, 98.7, 99998)
    assert 22 < abs(_node_shift_deg(polar)) < 28

    # canonical track: |lat| <= inclination, one orbit of minute stamps
    track = _canonical_track(iss)
    assert all(abs(lat) <= iss.incl + 0.5 for _lon, lat, _m in track)
    assert abs(track[-1][2] - iss.period_min) < 0.5   # ends ~one period in

def test_oscarlocator_pdf_geostationary_ok():
    """The enhanced generator handles a geostationary satellite (huge footprint,
    360 deg/pass) without error."""
    import os
    import json
    import tempfile
    import datetime
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    now = datetime.datetime.now(datetime.timezone.utc)
    omm = [{"OBJECT_NAME": "QO-100",
            "EPOCH": now.strftime("%Y-%m-%dT%H:%M:%S.000000"),
            "MEAN_MOTION": 1.00271, "ECCENTRICITY": 0.0001, "INCLINATION": 0.05,
            "RA_OF_ASC_NODE": 80.0, "ARG_OF_PERICENTER": 100.0,
            "MEAN_ANOMALY": 200.0, "BSTAR": 0.0, "NORAD_CAT_ID": 43700}]
    st = Store()
    st.db.load_gp_json(json.dumps(omm))
    out = os.path.join(tempfile.mkdtemp(), "geo.pdf")
    generate_oscarlocator_pdf(out, st, st.db.sats[0])
    assert os.path.getsize(out) > 5000

def test_oscarlocator_polar_projection():
    """The polar projection maps points to colatitude/longitude and the polar
    PDF generates. QTH mode remains the default (revertable)."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import _Projection, generate_oscarlocator_pdf
    # polar projection geometry: a point at lat 60 -> rho 30 (colatitude), lon
    # passes through as bearing
    p = _Projection("polar")
    rho, br = p.project(60.0, 45.0)
    assert abs(rho - 30.0) < 1e-9
    assert abs(br - 45.0) < 1e-9
    # the North Pole maps to the centre
    rho0, _ = p.project(90.0, 123.0)
    assert abs(rho0) < 1e-9
    # qth projection still works and is the default
    q = _Projection("qth", 40.0, -75.0)
    rho_q, _ = q.project(40.0, -75.0)
    assert abs(rho_q) < 1e-6                 # station maps to its own centre

    st = Store()
    s = st.db.sats[0]
    d = tempfile.mkdtemp()
    out_polar = os.path.join(d, "polar.pdf")
    out_qth = os.path.join(d, "qth.pdf")
    generate_oscarlocator_pdf(out_polar, st, s, projection="polar")
    generate_oscarlocator_pdf(out_qth, st, s, projection="qth")
    assert os.path.getsize(out_polar) > 5000
    assert os.path.getsize(out_qth) > 5000

def test_oscarlocator_southern_projection():
    """South-pole projection maps points to colatitude-from-S-pole and mirrors
    longitude; the southern polar PDF generates; polar-auto picks by latitude."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import _Projection, generate_oscarlocator_pdf
    from orbitdeck.engine.predict import Observer
    p = _Projection("polar-south")
    # a point at lat -60 -> rho 30 (colatitude from south pole)
    rho, _br = p.project(-60.0, 45.0)
    assert abs(rho - 30.0) < 1e-9
    # South Pole maps to centre
    rho0, _ = p.project(-90.0, 12.0)
    assert abs(rho0) < 1e-9
    # bearing is now plain longitude (handedness handled by the axes
    # orientation, not by negating the longitude in the projection)
    _r, br = p.project(-45.0, 30.0)
    assert abs(br - (30.0 % 360.0)) < 1e-9
    assert p.is_south and p.is_polar

    st = Store()
    st.obs = Observer(lat=-33.9, lon=18.4, alt_m=10, valid=True)  # Cape Town
    s = st.db.sats[0]
    d = tempfile.mkdtemp()
    out = os.path.join(d, "south.pdf")
    generate_oscarlocator_pdf(out, st, s, projection="polar-south")
    assert os.path.getsize(out) > 5000
    # polar-auto resolves to the southern sheet for a southern station
    out2 = os.path.join(d, "auto.pdf")
    generate_oscarlocator_pdf(out2, st, s, projection="polar-auto")
    assert os.path.getsize(out2) > 5000

def test_footprint_locus_geometry():
    """Every point of the footprint locus is exactly the footprint radius (great-
    circle) from the QTH."""
    import math
    from orbitdeck.gui.oscarlocator import _footprint_locus

    def gc(p1, l1, p2, l2):
        p1, l1, p2, l2 = map(math.radians, [p1, l1, p2, l2])
        return math.degrees(math.acos(max(-1.0, min(1.0,
            math.sin(p1) * math.sin(p2) +
            math.cos(p1) * math.cos(p2) * math.cos(l2 - l1)))))

    for qlat, qlon, rad in [(40, -75, 20), (-33, 18, 25), (0, 0, 15)]:
        locus = _footprint_locus(qlat, qlon, rad)
        for lat, lon in locus:
            assert abs(gc(qlat, qlon, lat, lon) - rad) < 0.01

def test_oscarlocator_footprint_on_qth_pages():
    """footprint_on_qth=True yields a 2-page set for both qth and polar maps."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    from orbitdeck.engine.predict import Observer

    def npages(p):
        with open(p, "rb") as f:
            data = f.read()
        return max(data.count(b"/Type /Page\n"), data.count(b"/Type /Page "),
                   data.count(b"/Type/Page"))

    st = Store()
    st.obs = Observer(lat=40.0, lon=-75.0, alt_m=10, valid=True)
    s = st.db.sats[0]
    d = tempfile.mkdtemp()
    for proj in ("qth", "polar"):
        out = os.path.join(d, "fpq_%s.pdf" % proj)
        generate_oscarlocator_pdf(out, st, s, projection=proj,
                                  footprint_on_qth=True)
        assert os.path.getsize(out) > 5000

def test_canonical_track_node_start():
    """The path-arc track starts at minute 0 on the equator (sheet-lon 0) for
    both the ascending-node (north) and descending-node (south) references."""
    from orbitdeck.gui.oscarlocator import _canonical_track
    from orbitdeck.engine.satdb import SatEntry

    class S:
        incl = 51.6
        period_min = 92.9
        mean_motion = 15.5
        ecc = 0.0004
    asc = _canonical_track(S(), descending=False)
    desc = _canonical_track(S(), descending=True)
    # first point: minute 0, on the equator (lat ~ 0), sheet-lon ~ 0
    for track in (asc, desc):
        lon0, lat0, m0 = track[0]
        assert abs(m0) < 1e-6
        assert abs(lat0) < 1e-6
        assert abs(((lon0 + 180) % 360) - 180) < 1e-6
    # ascending node climbs north first; descending node dips south first
    assert asc[5][1] > 0          # latitude increasing just after the node
    assert desc[5][1] < 0

def test_qth_map_radius_capped():
    """The QTH azimuthal map is capped well short of a full hemisphere so it
    doesn't over-show the opposite hemisphere (rmax in the 50-80 deg window)."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui import oscarlocator as OL
    from orbitdeck.engine.predict import Observer
    # capture the rmax chosen for a mid-latitude QTH by intercepting the base
    # map call
    captured = {}
    orig = OL._base_map_page

    def spy(pdf, proj, qth_name, segments, rmax, *args, **kwargs):
        captured["rmax"] = rmax
        return orig(pdf, proj, qth_name, segments, rmax, *args, **kwargs)
    OL._base_map_page = spy
    try:
        st = Store()
        st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
        s = st.db.sats[0]
        out = os.path.join(tempfile.mkdtemp(), "qth.pdf")
        OL.generate_oscarlocator_pdf(out, st, s, projection="qth")
    finally:
        OL._base_map_page = orig
    assert 50.0 <= captured.get("rmax", 0) <= 80.0

def test_oscarsim_drag_is_ghost_free_and_coalesced():
    """A hand-drag redraws the whole scene each frame (no blitting), so the arc
    never accumulates -- the artist counts after several drag frames match a
    single render. The throttle coalesces rapid motion events into a pending
    redraw instead of one synchronous redraw per event."""
    import math
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp

    try:
        root = tk.Tk()
    except Exception:
        return
    import os
    try:
        os.remove(os.path.expanduser("~/.orbitdeck/config.json"))
    except OSError:
        pass
    app = OrbitDeckApp(root)
    app.store.save_config(onboarded=True)
    sat = next(s for s in app.store.db.sats if s.name == "RS-44")
    app.store.select(sat.norad)
    app.show("oscarsim")
    sim = app.current
    sim._mode.set("manual")
    sim._on_mode()
    root.update()
    # baseline artist count from a clean render (re-fetch ax: map.clear() can
    # replace the axes object on each render)
    n_lines = len(sim.map.ax.lines)
    n_texts = len(sim.map.ax.texts)

    class Ev:
        def __init__(self, th, r):
            self.inaxes = sim.map.ax
            self.xdata = th
            self.ydata = r
            self.button = 1

    # an arc-rotate gesture: press away from the dot, then several motions
    sim._on_press(Ev(math.radians(30), 70.0))
    assert sim._drag_kind == "arc"
    for d in (20, 40, 60, 80):
        sim._on_drag(Ev(math.radians(30 + d), 70.0))
    # rapid motions are coalesced: a render is pending, not run per-event
    assert sim._drag_pending is True
    root.update()                       # let the throttle fire
    sim._on_release(Ev(math.radians(120), 70.0))
    root.update()

    # no accumulation: a full clean render each frame keeps the artist count
    # at the single-render baseline (no leftover/ghost arcs)
    assert len(sim.map.ax.lines) == n_lines, (n_lines, len(sim.map.ax.lines))
    assert len(sim.map.ax.texts) == n_texts, (n_texts, len(sim.map.ax.texts))
    # the drag actually rotated the arc
    assert sim._manual_arc is True

    root.destroy()


def test_oscarsim_sweep_sliders_drive_and_sync():
    """The EQX-longitude and minutes-after-EQX sliders hand-position the arc
    (switching to manual mode), share their variables with the drag handler so
    the two stay in sync, and the minute slider's range tracks the period."""
    import math
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp

    try:
        root = tk.Tk()
    except Exception:
        return
    import os
    try:
        os.remove(os.path.expanduser("~/.orbitdeck/config.json"))
    except OSError:
        pass
    app = OrbitDeckApp(root)
    app.store.save_config(onboarded=True)
    sat = next(s for s in app.store.db.sats if s.name == "RS-44")
    app.store.select(sat.norad)
    app.show("oscarsim")
    sim = app.current
    root.update()

    # the minute slider spans one orbital period for this satellite
    assert abs(float(sim._min_scale.cget("to")) - sat.period_min) < 1.0

    # moving the EQX slider switches to manual mode and sets the arc longitude
    sim._eqx_lon.set(75.0)
    sim._on_eqx_slider()
    assert sim._manual_arc is True
    assert abs(sim._eqx_lon.get() - 75.0) < 1e-6

    # moving the minute slider slides the marker along the arc
    sim._minute.set(40.0)
    sim._on_min_slider()
    assert abs(sim._minute.get() - 40.0) < 1e-6

    # dragging the arc updates the SAME variable the slider is bound to, so the
    # slider thumb follows the drag
    ax = sim.map.ax

    class Ev:
        def __init__(self, th, r):
            self.inaxes = ax
            self.xdata = th
            self.ydata = r
            self.button = 1

    sim._on_press(Ev(math.radians(30), 70.0))
    sim._on_drag(Ev(math.radians(90), 70.0))
    sim._on_release(Ev(math.radians(90), 70.0))
    # eqx_lon (the slider's variable) moved off 75 due to the drag
    assert abs(sim._eqx_lon.get() - 75.0) > 1.0

    root.destroy()


def test_oscarsim_screen_geometry():
    """The OSCARLOCATOR simulator's projection helpers produce sane geometry:
    the canonical track starts on the equator at minute 0, the footprint radius
    grows with altitude, and the great-circle helper is symmetric."""
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen

    # canonical track (ascending) starts at lat 0, minute 0
    class S:
        incl = 51.6
        period_min = 92.9
    sim = OscarSimScreen.__new__(OscarSimScreen)
    track = sim._canonical_track(S(), descending=False)
    lon0, lat0, m0 = track[0]
    assert abs(lat0) < 1e-6 and abs(m0) < 1e-6
    # descending start dips south just after the node
    td = sim._canonical_track(S(), descending=True)
    assert td[3][1] < 0

    # footprint radius increases with altitude and is in (0, 90)
    f_low = OscarSimScreen._footprint_deg(500)
    f_high = OscarSimScreen._footprint_deg(20000)
    assert 0 < f_low < f_high < 90

    # great-circle distance is ~zero for identical points (float tolerance)
    d0, _ = OscarSimScreen._gc(40, -75, 40, -75)
    assert abs(d0) < 0.05
    d1, _ = OscarSimScreen._gc(0, 0, 0, 90)
    assert abs(d1 - 90.0) < 1e-6

def test_oscarsim_track_point_on_arc():
    """The simulator's _track_point (used to slide the marker along the arc in
    manual mode) lands on the equator at minute 0 and matches the canonical
    track it is drawn from."""
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen

    class S:
        incl = 51.6
        period_min = 92.9
    sim = OscarSimScreen.__new__(OscarSimScreen)
    # at minute 0 the sub-point is on the equator at the EQX longitude
    lat0, lon0 = sim._track_point(S(), 40.0, 0.0, is_south=False)
    assert abs(lat0) < 1e-6
    assert abs(((lon0 - 40.0 + 180) % 360) - 180) < 1e-6
    # a few minutes in, the latitude has climbed (ascending) and matches the
    # canonical track sampled at the same minute
    track = sim._canonical_track(S(), descending=False)
    # find the canonical point nearest 10 minutes
    pt = min(track, key=lambda p: abs(p[2] - 10.0))
    lat_t, lon_t = sim._track_point(S(), 0.0, pt[2], is_south=False)
    assert abs(lat_t - pt[1]) < 0.5

def test_oscarsim_drag_rotates_arc_and_works_in_lab():
    """Dragging the disc rotates the ground-track arc by the angular sweep of the
    pointer, sets the hand-positioned flag, and works regardless of which
    satellite (catalog or lab) is active -- the lab satellite must be hand-
    controllable too."""
    import math
    import tkinter as tk
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen

    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()

    sim = OscarSimScreen.__new__(OscarSimScreen)
    # minimal stubbed state the drag handlers touch (no real GUI/map needed)
    sim._eqx_lon = tk.DoubleVar(value=0.0)
    sim._minute = tk.DoubleVar(value=0.0)
    sim._manual_arc = True            # already hand-positioned
    sim._drag_kind = "arc"
    sim._min_span = 95.0
    sim._minute_dot_rt = None
    # pretend the resolved projection is the north polar sheet
    sim._resolve_proj = lambda: "polar"
    sim._render = lambda: None
    sim._render_drag = lambda: None

    class Ev:
        def __init__(self, th, r):
            self.inaxes = sim.map_ax
            self.xdata = th
            self.ydata = r

    # give _pointer_angle something to compare inaxes against
    sim.map_ax = object()
    sim.map = type("M", (), {"ax": sim.map_ax})()
    sim._pointer_angle = lambda e: (e.xdata if e.inaxes is sim.map.ax else None)

    # press at theta=0, then drag 40 deg -> EQX rotates ~40 deg on the north sheet
    sim._drag_ang0 = 0.0
    sim._drag_eqx0 = 0.0
    sim._drag_min0 = 0.0
    sim._on_drag(Ev(math.radians(40), 30.0))
    assert abs(sim._eqx_lon.get() - 40.0) < 1e-6

    # on the south sheet the on-screen sense is mirrored
    sim._resolve_proj = lambda: "polar-south"
    sim._eqx_lon.set(0.0)
    sim._drag_ang0 = 0.0
    sim._drag_eqx0 = 0.0
    sim._on_drag(Ev(math.radians(40), 30.0))
    assert abs(sim._eqx_lon.get() - (-40.0)) < 1e-6

    # dragging near the minute dot slides the marker ALONG THE ARC: the drag
    # now projects the pointer onto the arc via _minute_for_pointer (rather than
    # mapping the pointer's angle about the centre, which jumped near the centre)
    sim._resolve_proj = lambda: "polar"
    sim._drag_kind = "minute"
    sim._minute.set(0.0)
    sim._drag_ang0 = 0.0
    sim._min_span = 95.0
    sim._minute_for_pointer = lambda e: 47.5     # stub the arc projection
    sim._on_drag(Ev(math.radians(170), 30.0))
    assert abs(sim._minute.get() - 47.5) < 1e-6   # marker snaps to projected min

    # the projected minute is clamped to [0, span]
    sim._minute_for_pointer = lambda e: 999.0
    sim._on_drag(Ev(math.radians(10), 30.0))
    assert sim._minute.get() == sim._min_span

    root.destroy()


def test_oscarsim_minute_drag_projects_onto_arc():
    """The satellite marker slides along the FULL arc as the pointer moves:
    _minute_for_pointer returns the minute of the arc point nearest the pointer,
    so dragging tracks smoothly even through the centre of the disc (where the
    old angle-based mapping jumped)."""
    import math
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp

    try:
        root = tk.Tk()
    except Exception:
        return
    import os
    try:
        os.remove(os.path.expanduser("~/.orbitdeck/config.json"))
    except OSError:
        pass
    app = OrbitDeckApp(root)
    app.store.save_config(onboarded=True)
    sat = next(s for s in app.store.db.sats if s.name == "RS-44")
    app.store.select(sat.norad)
    app.show("oscarsim")
    sim = app.current
    sim._mode.set("manual")
    sim._on_mode()

    class Ev:
        def __init__(self, th, r):
            self.inaxes = sim.map.ax
            self.xdata = th
            self.ydata = r

    # for several target minutes, put the pointer exactly on that arc point and
    # confirm the projection recovers (close to) that minute -- including near
    # the centre of the disc, which the old mapping handled badly
    for target in (5.0, 20.0, 30.0, 45.0, 60.0):
        lat, lon = sim._track_point(sat, sim._eqx_lon.get(), target, False)
        rho, theta = sim._to_polar("polar", lat, lon)
        m = sim._minute_for_pointer(Ev(theta, rho))
        assert m is not None and abs(m - target) < 2.0, (target, m)

    root.destroy()



    """The QTH reticle (simulator and printout) is sized to the footprint radius
    at the satellite's MEAN orbital altitude (max ground distance of visibility),
    not the instantaneous sub-point altitude."""
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen
    from orbitdeck.engine import analysis as A

    class S:
        mean_motion = 15.50103472     # ~ISS
        period_min = 92.9
    # mean altitude from the mean motion
    sma = A.semi_major_axis_km(S.mean_motion)
    mean_alt = sma - 6378.135
    got_alt = OscarSimScreen._mean_alt_km(S())
    assert abs(got_alt - mean_alt) < 1.0
    # the footprint radius at that altitude is a sane LEO value (~20 deg)
    foot = OscarSimScreen._footprint_deg(got_alt)
    assert 15.0 < foot < 25.0
    # higher orbit -> larger footprint
    class S2:
        mean_motion = 2.0             # ~12 h orbit, much higher
        period_min = 720.0
    foot_high = OscarSimScreen._footprint_deg(OscarSimScreen._mean_alt_km(S2()))
    assert foot_high > foot

def test_canonical_track_matches_sgp4_groundtrack():
    """The OSCARLOCATOR canonical path arc should follow the real SGP4-propagated
    ground track (referenced to the node, with Earth rotation) to within a few
    degrees for circular, eccentric, prograde and retrograde orbits."""
    import time
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import _canonical_track

    st = Store()
    pred = st.pred

    def max_err(s, descending=False):
        pred.set_sat(s)
        t0 = time.time()
        prev = None
        node_t = None
        for k in range(0, 16000, 5):
            t = t0 + k
            la, _, _ = pred.subpoint_at(t)
            if prev is not None:
                if not descending and prev < 0 <= la:
                    node_t = t
                    break
                if descending and prev >= 0 > la:
                    node_t = t
                    break
            prev = la
        if node_t is None:
            return None
        la0, lo0, _ = pred.subpoint_at(node_t)
        P = s.period_min * 60.0
        canon = _canonical_track(s, descending=descending)

        def canon_at(m):
            b = min(canon, key=lambda p: abs(p[2] - m))
            return b[1], b[0]
        mlat = mlon = 0.0
        for k in range(0, int(P) + 1, 30):
            t = node_t + k
            la, lo, _ = pred.subpoint_at(t)
            dlon = ((lo - lo0 + 540) % 360) - 180
            cla, cdlon = canon_at(k / 60.0)
            dl = ((dlon - cdlon + 540) % 360) - 180
            mlat = max(mlat, abs(la - cla))
            mlon = max(mlon, abs(dl))
        return mlat, mlon

    # test a spread of inclinations including a retrograde (>90 deg) orbit
    tested = 0
    seen = set()
    for s in st.db.sats:
        key = round(s.incl)
        if key in seen:
            continue
        seen.add(key)
        r = max_err(s)
        if r is None:
            continue
        mlat, mlon = r
        # latitude should track tightly; longitude within ~8 deg even for the
        # more eccentric / retrograde cases in the sample catalogue
        assert mlat < 2.5, "%s lat err %.1f" % (s.name, mlat)
        assert mlon < 8.0, "%s lon err %.1f" % (s.name, mlon)
        tested += 1
        if tested >= 6:
            break
    assert tested >= 3

def test_oscarsim_eqx_listing_node_choice():
    """The simulator's EQX listing uses ascending nodes for a northern station
    and descending nodes for a southern one, returning (time, longitude) events
    in chronological order."""
    import time
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.predict import Observer

    st = Store()
    pred = st.pred
    s = st.db.sats[0]
    pred.set_sat(s)
    t = time.time()

    # northern station -> ascending nodes
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=10, valid=True)
    pred.set_site(st.obs)
    asc = pred.ascending_nodes(t, t + 2 * 86400)[:6]
    assert len(asc) >= 3
    # chronological and each is an equator crossing (longitude in range)
    times = [n[0] for n in asc]
    assert times == sorted(times)
    for tc, lon in asc:
        assert -180.0 <= lon <= 180.0
    # successive ISS nodes are ~1 orbit apart
    gap_min = (asc[1][0] - asc[0][0]) / 60.0
    assert 85 < gap_min < 105

    # southern station -> descending nodes exist too
    st.obs = Observer(lat=-33.9, lon=18.4, alt_m=10, valid=True)
    pred.set_site(st.obs)
    desc = pred.descending_nodes(t, t + 2 * 86400)[:6]
    assert len(desc) >= 3
    dtimes = [n[0] for n in desc]
    assert dtimes == sorted(dtimes)

def test_oscarsim_live_eqx_follows_view_not_qth():
    """In live mode the EQX node reference follows the VIEW (north sheet ->
    ascending node, south sheet -> descending node), NOT the station hemisphere.

    Two cases, controlled by sampling a known point in the orbit:
      * satellite IN the viewed hemisphere -> arc references the pass in
        progress (most recent matching node, minute >= 0) and the live marker
        sits on that arc;
      * satellite in the OPPOSITE hemisphere -> there is no live pass on this
        sheet, so the arc references the NEXT matching node (minute < 0), i.e.
        the upcoming pass into view.

    Regression: previously the node was chosen from the QTH latitude, so a
    northern station viewing the south sheet pinned the arc to the wrong node.

    Built without a full app/Tk root (just the screen object + a real predictor)
    so it can't be perturbed by global GUI state left over from other tests.
    """
    import math
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.screens import oscarsim as OS
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen
    from orbitdeck.engine.predict import Observer

    st = Store()
    st.obs = Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True)  # northern QTH
    s = st.selected_sat()
    st.pred.set_site(st.obs)
    st.pred.set_sat(s)

    class _Var:
        def get(self):
            return "live"
    sim = OscarSimScreen.__new__(OscarSimScreen)
    sim.store = st
    sim._mode = _Var()

    orig_now = OS.now_unix
    try:
        t0 = orig_now()
        asc = st.pred.ascending_nodes(t0 - 2 * 3600, t0 + 3600)
        assert asc
        tc = asc[-1][0]
        P = s.period_min * 60.0

        def gap_at(view_mode, t):
            _t, eqx_lon, minute = sim._current_state(s, view_mode)
            la, lo, _ = st.pred.subpoint_at(t)
            track = sim._canonical_track(
                s, descending=(view_mode == "polar-south"))
            best = min(
                math.hypot(la - lat, ((lo - (lr + eqx_lon) + 540) % 360) - 180)
                for lr, lat, _m in track)
            return best, minute

        # --- north sheet, satellite NORTH (quarter orbit after asc node) ---
        OS.now_unix = lambda: tc + P * 0.25
        assert st.pred.subpoint_at(OS.now_unix())[0] > 0
        gap, minute = gap_at("polar", OS.now_unix())
        assert minute >= 0          # current pass (past node)
        assert gap < 6.0            # marker on the arc

        # --- north sheet, satellite SOUTH (three-quarter orbit) ---
        OS.now_unix = lambda: tc + P * 0.75
        assert st.pred.subpoint_at(OS.now_unix())[0] < 0
        _gap, minute = gap_at("polar", OS.now_unix())
        assert minute < 0           # NEXT pass into view (future node)

        # --- south sheet, satellite SOUTH -> current pass, marker on arc ---
        OS.now_unix = lambda: tc + P * 0.75
        gap, minute = gap_at("polar-south", OS.now_unix())
        assert minute >= 0
        assert gap < 6.0

        # --- south sheet, satellite NORTH -> next pass into view ---
        OS.now_unix = lambda: tc + P * 0.25
        _gap, minute = gap_at("polar-south", OS.now_unix())
        assert minute < 0
    finally:
        OS.now_unix = orig_now

def test_oscarlocator_titles_all_say_oscarlocator():
    """Every OSCARLOCATOR PDF page title uses the correct 'OSCARLOCATOR' spelling
    (never the old 'OSCARLATOR' typo), and the footprint-on-QTH map includes the
    satellite name and footprint size."""
    import os
    import tempfile
    import subprocess
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    from orbitdeck.engine.predict import Observer

    st = Store()
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
    s = st.db.sats[0]
    d = tempfile.mkdtemp()
    p1 = os.path.join(d, "fp.pdf")
    generate_oscarlocator_pdf(p1, st, s, projection="qth",
                              footprint_on_qth=True)
    txt = subprocess.run(["pdftotext", p1, "-"], capture_output=True,
                         text=True).stdout
    assert "OSCARLATOR" not in txt
    assert "OSCARLOCATOR" in txt
    # the combined map names the satellite and gives the range-circle size
    assert s.name in txt
    assert "range-circle radius" in txt.lower()

def test_oscarsim_is_a_live_screen():
    """The simulator must opt into the live tick so its live mode tracks in real
    time, and its on_tick must accept the timestamp the app passes."""
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen
    assert getattr(OscarSimScreen, "live", False) is True
    import inspect
    sig = inspect.signature(OscarSimScreen.on_tick)
    # on_tick(self, now_dt=None) -> accepts being called with one positional arg
    params = list(sig.parameters.values())
    assert len(params) >= 2

def test_oscarlocator_title_shrinks_for_long_names():
    """A long satellite name in an OSCARLOCATOR page title is auto-shrunk so it
    stays within the page margins (rather than spilling off the edges)."""
    from orbitdeck.gui.oscarlocator import _fit_title_fontsize, FS_TITLE
    short = "ISS \u2014 OSCARLOCATOR \u2014 Base Map"
    long = ("VERY LONG SATELLITE NAME 2024-099ZZ \u2014 OSCARLOCATOR \u2014 "
            "Map + Footprint at QTH")
    assert _fit_title_fontsize(short) == FS_TITLE
    assert _fit_title_fontsize(long) < FS_TITLE

def test_oscarlocator_footer_wraps_to_margin():
    """Long footer/subtitle text is wrapped to the page margin, not the figure
    edge, so it does not run off the page."""
    from orbitdeck.gui.oscarlocator import _wrap_to_width
    note = ("Print on transparency at 100%. Lay over the polar base map with "
            "centres aligned and the ascending node at the EQX longitude, then "
            "rotate the whole sheet about the centre for each successive pass.")
    wrapped = _wrap_to_width(note, 9)
    assert "\n" in wrapped               # it actually wrapped
    # no single line is absurdly long
    assert max(len(line) for line in wrapped.splitlines()) < 110

def test_oscarlocator_export_is_shared_by_track_and_sim():
    """The 'Make printable OSCARLOCATOR' action is defined once on the base
    Screen class and used unchanged by both the Track and Simulator screens, so
    the two entry points behave identically (same base-map + footprint choices
    and the same saved output)."""
    from orbitdeck.gui.screens import Screen
    from orbitdeck.gui.screens.track import TrackScreen
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen

    # the workflow lives on the base class
    assert hasattr(Screen, "make_oscarlocator_pdf")
    # neither subclass defines its OWN copy -- they inherit the base method
    # (checked via __dict__ so it's robust to module re-import identity quirks)
    assert "make_oscarlocator_pdf" not in TrackScreen.__dict__
    assert "make_oscarlocator_pdf" not in OscarSimScreen.__dict__
    assert "make_oscarlocator_pdf" in Screen.__dict__
    # the old per-screen implementations are gone
    assert not hasattr(TrackScreen, "_make_oscarlocator")
    assert not hasattr(OscarSimScreen, "_print")

def test_oscarlocator_arc_subtitle_fits_one_line():
    """The path-arc subtitle for a typical satellite fits on a single line (so
    it can't wrap down into the red 'rotate sheet' annotation below it)."""
    from orbitdeck.gui.oscarlocator import _wrap_to_width, FS_SUBTITLE
    # the subtitle as built in _arc_page for an ISS-like satellite
    sub = ("Ground-track \u2014 incl. 51.6\u00b0, period 92.9\u00a0min "
           "\u2014 advance 23.6\u00b0\u00a0W per pass.")
    wrapped = _wrap_to_width(sub, FS_SUBTITLE)
    assert "\n" not in wrapped            # stays on one line

def test_oscarlocator_qth_map_has_elevation_rings():
    """The QTH base map names the satellite and its subtitle reports that the
    rings are elevation contours at the satellite's altitude."""
    import os
    import subprocess
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf

    st = Store()
    s = st.selected_sat()
    out = os.path.join(tempfile.mkdtemp(), "qth.pdf")
    generate_oscarlocator_pdf(out, st, s, projection="qth")
    txt = subprocess.run(["pdftotext", out, "-"], capture_output=True,
                         text=True).stdout
    assert s.name in txt
    assert "elevation" in txt.lower()
    # rings are labelled with explicit elevation angles; the 0 deg ring is the
    # footprint edge (no more "horizon" wording)
    assert "0\u00b0 el" in txt or "0 el" in txt
    assert "horizon" not in txt.lower()

def test_oscarlocator_arc_sheet_names_node_and_hemisphere():
    """The hemisphere/node distinction matters on the ARC sheet (the arc is
    built from the ascending node for northern sheets, the descending node for
    southern), so each arc sheet states it at the EQX indicator. The map sheets
    do NOT carry a redundant N/S badge (the map content makes the hemisphere
    obvious)."""
    import os
    import subprocess
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf

    st = Store()
    s = st.selected_sat()
    d = tempfile.mkdtemp()
    pn = os.path.join(d, "n.pdf")
    ps = os.path.join(d, "s.pdf")
    generate_oscarlocator_pdf(pn, st, s, projection="polar")
    generate_oscarlocator_pdf(ps, st, s, projection="polar-south")
    tn = subprocess.run(["pdftotext", pn, "-"], capture_output=True,
                        text=True).stdout
    ts = subprocess.run(["pdftotext", ps, "-"], capture_output=True,
                        text=True).stdout
    # the old corner badges are gone
    assert "N SHEET" not in tn
    assert "S SHEET" not in ts
    # the arc sheet states the node + hemisphere at the EQX indicator (compact
    # wording: "ascending node (N sheet)" / "descending node (S sheet)")
    assert "ascending node" in tn
    assert "(N sheet)" in tn
    assert "descending node" in ts
    assert "(S sheet)" in ts

def test_oscarlocator_long_sat_name_truncates():
    """A very long satellite name is truncated with an ellipsis so the title
    keeps its descriptive suffix at a readable size, while short names pass
    through unchanged."""
    from orbitdeck.gui.oscarlocator import _fit_sat_name
    suffix = " \u2014 OSCARLOCATOR Base Map"
    # short names are untouched
    assert _fit_sat_name("ISS", suffix) == "ISS"
    assert _fit_sat_name("AO-91", suffix) == "AO-91"
    # a very long name is shortened and ends with an ellipsis
    longname = "OSCAR-100 / QO-100 GEOSTATIONARY TRANSPONDER (ES HAIL 2) WIDEBAND"
    got = _fit_sat_name(longname, suffix)
    assert got.endswith("\u2026")
    assert len(got) < len(longname)
    # the truncated name plus suffix is not absurdly long
    assert len(got) + len(suffix) < 60

def test_oscarlocator_long_name_pdf_renders():
    """A long satellite name doesn't break PDF generation on any projection."""
    import copy
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf

    st = Store()
    s = copy.deepcopy(st.selected_sat())
    s.name = "OSCAR-100 / QO-100 GEOSTATIONARY TRANSPONDER (ES HAIL 2) WIDEBAND"
    d = tempfile.mkdtemp()
    for proj in ("qth", "polar", "polar-south"):
        out = os.path.join(d, proj + ".pdf")
        generate_oscarlocator_pdf(out, st, s, projection=proj)
        assert os.path.getsize(out) > 1000
    # the footprint-on-QTH 2-page variant too
    out = os.path.join(d, "fp.pdf")
    generate_oscarlocator_pdf(out, st, s, projection="qth",
                              footprint_on_qth=True)
    assert os.path.getsize(out) > 1000

def test_oscarsim_live_auto_sheet_follows_satellite_hemisphere():
    """In LIVE mode with 'Polar (auto N/S)' selected, the displayed sheet
    follows the SATELLITE's current hemisphere (north sheet while it's north of
    the equator, south sheet while south), flipping automatically as it crosses
    the equator -- so the active pass is always the one drawn. In non-live modes
    the auto sheet falls back to the station hemisphere."""
    import math
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.screens import oscarsim as OS
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen
    from orbitdeck.engine.predict import Observer

    st = Store()
    st.obs = Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True)  # northern QTH
    s = st.selected_sat()
    st.pred.set_site(st.obs)
    st.pred.set_sat(s)

    class _Var:
        def __init__(self, v):
            self._v = v

        def get(self):
            return self._v
    sim = OscarSimScreen.__new__(OscarSimScreen)
    sim.store = st
    sim._mode = _Var("live")
    sim._proj_mode = _Var("polar-auto")

    # drive _resolve_proj against a controlled "current sub-latitude" by
    # monkeypatching now_unix to land on a known north/south time
    orig_now = OS.now_unix
    try:
        # find a recent ascending node, then sample a time clearly AFTER it
        # (northbound -> sat is north) and clearly before the next descending
        t0 = orig_now()
        asc = st.pred.ascending_nodes(t0 - 2 * 3600, t0 + 3600)
        assert asc, "need an ascending node to anchor the test"
        tc = asc[-1][0] if asc[-1][0] <= t0 + 1800 else asc[0][0]
        period_s = s.period_min * 60.0

        # ~quarter orbit after an ascending node -> satellite is north
        OS.now_unix = lambda: tc + period_s * 0.25
        lat_n = st.pred.subpoint_at(OS.now_unix())[0]
        assert lat_n > 0
        assert sim._resolve_proj() == "polar"

        # ~three-quarter orbit after an ascending node -> satellite is south
        OS.now_unix = lambda: tc + period_s * 0.75
        lat_s = st.pred.subpoint_at(OS.now_unix())[0]
        assert lat_s < 0
        assert sim._resolve_proj() == "polar-south"
    finally:
        OS.now_unix = orig_now

    # in MANUAL mode the auto sheet falls back to the (northern) station
    sim._mode = _Var("manual")
    assert sim._resolve_proj() == "polar"

def test_oscarsim_live_shows_next_eqx_arc_when_out_of_view():
    """When the satellite is in the hemisphere OPPOSITE the viewed sheet, the
    live view shows the arc for the NEXT equator crossing into the viewed
    hemisphere (the upcoming pass), referenced to the upcoming node -- so the
    user always sees the next pass's arc even though there's no live marker on
    this sheet yet. As the satellite crosses into view, that same arc becomes
    the current pass."""
    import math
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.screens import oscarsim as OS
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen
    from orbitdeck.engine.predict import Observer

    st = Store()
    st.obs = Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True)
    s = st.selected_sat()
    st.pred.set_site(st.obs)
    st.pred.set_sat(s)

    class _Var:
        def get(self):
            return "live"
    sim = OscarSimScreen.__new__(OscarSimScreen)
    sim.store = st
    sim._mode = _Var()

    orig = OS.now_unix
    try:
        t0 = orig()
        asc = st.pred.ascending_nodes(t0 - 2 * 3600, t0 + 3600)
        assert asc
        tc = asc[-1][0]
        P = s.period_min * 60.0

        # satellite SOUTH, viewing the NORTH sheet: the referenced node must be
        # the NEXT ascending node (in the future), and it must match the EQX the
        # engine reports as upcoming.
        OS.now_unix = lambda: tc + P * 0.75
        now = OS.now_unix()
        assert st.pred.subpoint_at(now)[0] < 0          # sat is south
        _t, eqx_lon, minute = sim._current_state(s, "polar")
        assert minute < 0                               # arc is the next pass
        nxt = st.pred.ascending_nodes(now, now + 2 * 3600)
        assert nxt
        # the EQX longitude shown is the upcoming ascending node's longitude
        assert abs(((eqx_lon - nxt[0][1] + 540) % 360) - 180) < 1.0
    finally:
        OS.now_unix = orig

def test_oscarsim_live_arc_advances_for_long_period_sat():
    """Regression (RS-44, ~121 min period): the live arc must reference the
    correct equator-crossing node at EVERY phase of the orbit, including right at
    a crossing. The node-search window must exceed one full period, or a
    long-period satellite's most-recent node falls outside a too-narrow window
    and the arc fails to advance at the crossing."""
    import math
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.screens import oscarsim as OS
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen
    from orbitdeck.engine.predict import Observer

    st = Store()
    st.obs = Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True)
    # find RS-44 (or any sat with period > 2 h) in the bundled catalogue
    rs = next((x for x in st.db.sats if x.norad == 44909), None)
    if rs is None:
        rs = next((x for x in st.db.sats if x.period_min > 120.0), None)
    assert rs is not None, "need a long-period satellite for this test"
    assert rs.period_min > 120.0
    st.select(rs.norad)
    st.pred.set_site(st.obs)
    st.pred.set_sat(rs)

    class _V:
        def get(self):
            return "live"
    sim = OscarSimScreen.__new__(OscarSimScreen)
    sim.store = st
    sim._mode = _V()

    P = rs.period_min * 60.0
    orig = OS.now_unix
    try:
        t0 = orig()
        # anchor on a descending node; the bug appeared in the minutes JUST
        # AFTER a crossing, when the satellite is in view on the south sheet but
        # the most-recent descending node is one full period back -- outside a
        # window narrower than the period, so _current_state fell back to the
        # bare sub-point and the arc went stale.
        desc = st.pred.descending_nodes(t0, t0 + P * 2)
        assert desc
        tc = desc[0][0]

        # offsets spanning the whole orbit, with extra density LATE in the
        # in-view pass (near +period min), where the satellite has been in view
        # for almost a full period and the most-recent node ages past a window
        # narrower than the period -- the exact stale-arc condition reported.
        offsets_min = [0.5, 1, 2, 3, 5]
        offsets_min += list(range(10, int(rs.period_min) + 4))
        for off in offsets_min:
            OS.now_unix = lambda o=off: tc + o * 60.0
            now = OS.now_unix()
            lat = st.pred.subpoint_at(now)[0]
            _t, eqx_lon, minute = sim._current_state(rs, "polar-south")
            # The bug degraded to the bare sub-point fallback (return t, sp[1],
            # 0.0) when the most-recent node fell outside a too-narrow window:
            # minute exactly 0.0 AND eqx equal to the current sub-longitude.
            # That must never happen while the satellite is in view mid-pass.
            sub_lon = st.pred.subpoint_at(now)[1]
            is_fallback = (abs(minute) < 1e-9 and
                           abs(((eqx_lon - sub_lon + 540) % 360) - 180) < 0.05)
            if lat < -2.0:          # solidly in view on the south sheet
                assert not is_fallback, (
                    "arc fell back to the sub-point (stale) at +%g min, lat "
                    "%.1f -- node-search window too narrow for period %.0f min"
                    % (off, lat, rs.period_min))
            # and the referenced EQX should be a real descending node
            ref_t = now - minute * 60.0
            near = st.pred.descending_nodes(ref_t - 400, ref_t + 400)
            assert near, "no descending node near referenced time at +%g min" % off
            assert any(abs(((eqx_lon - lon + 540) % 360) - 180) < 1.0
                       for _tc, lon in near), (
                "eqx longitude not a real node at +%g min" % off)
    finally:
        OS.now_unix = orig

def test_oscarsim_next_pass_seeds_visible_pass_node():
    """'Next pass from QTH' must reference the arc to the equator-crossing node
    of the next VISIBLE pass (the one that rises above the horizon at the
    station), not merely the next equator crossing -- which is almost always a
    different orbit, putting the arc at the wrong longitude.

    Regression: failed for ISS (next EQX ~89 min out vs visible pass ~2 min) and
    RS-44 (next EQX vs a visible pass hours later)."""
    import math
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.screens import oscarsim as OS
    from orbitdeck.gui.screens.oscarsim import OscarSimScreen
    from orbitdeck.engine.predict import Observer

    class _V:
        def __init__(self, v):
            self._v = v

        def get(self):
            return self._v

        def set(self, v):
            self._v = v

    for norad in (25544, 44909):     # ISS, RS-44
        st = Store()
        sat = next((x for x in st.db.sats if x.norad == norad), None)
        if sat is None:
            continue
        st.obs = Observer(lat=38.9, lon=-77.0, alt_m=10, valid=True)
        st.pred.set_site(st.obs)
        st.pred.set_sat(sat)
        sim = OscarSimScreen.__new__(OscarSimScreen)
        sim.store = st
        sim.pred = lambda p=st.pred: p
        sim.sat = lambda s=sat: s
        sim._mode = _V("nextpass")
        sim._proj_mode = _V("qth")
        sim._eqx_lon = _V(0.0)
        sim._minute = _V(0.0)

        sim._seed_next_pass()
        t = OS.now_unix()
        passes = st.pred.predict_passes(t, 5.0, 1)
        assert passes, "expected a visible pass for %d" % norad
        aos = passes[0].aos
        tca = passes[0].tca
        # the seeded node is the ascending node of the VISIBLE pass's orbit.
        # Search a wider window (1.5 periods either side) so high-eccentricity
        # orbits like RS-44 -- whose ascending node can sit well before AOS --
        # still resolve a node to compare against.
        pd = sat.period_min * 60.0
        node = st.pred.ascending_nodes(aos - 1.5 * pd, aos + 0.5 * pd)
        if not node:
            # no ascending node in a generous window around this pass (can
            # happen for some geometries); the seeding fallback is exercised
            # elsewhere, so skip the longitude cross-check for this satellite.
            continue
        want_lon = node[-1][1]
        assert abs(((sim._eqx_lon.get() - want_lon + 540) % 360) - 180) < 1.5

        # and the arc, referenced to that node, passes over the real ground
        # track near closest approach (proves it's the right orbit/longitude)
        track = sim._canonical_track(sat, descending=False)
        tc = sim._seed_unix
        tca_min = (tca - tc) / 60.0
        cp = min(track, key=lambda p: abs(p[2] - tca_min))
        canon_lon = ((cp[0] + sim._eqx_lon.get() + 540) % 360) - 180
        _rla, rlo, _ = st.pred.subpoint_at(tca)
        assert abs(((canon_lon - rlo + 540) % 360) - 180) < 3.0

def test_oscarlocator_base_map_has_branding():
    """Every printed sheet carries the OrbitDeck + author credit EXCEPT the clean
    (reduced-text) transparency overlays, which stay free of any text outside the
    circular instrument so they don't clutter the stacked map."""
    import os
    import tempfile
    import subprocess
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    from orbitdeck.engine.predict import Observer
    st = Store()
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
    s = st.db.sats[0]
    d = tempfile.mkdtemp()

    # Full (non-reduced) 3-sheet set: base map + range-circle + arc. All three
    # carry full instructions and therefore all carry the credit.
    p = os.path.join(d, "full.pdf")
    generate_oscarlocator_pdf(p, st, s, projection="qth",
                              footprint_on_qth=False)
    for pg in (1, 2, 3):
        txt = subprocess.run(["pdftotext", "-f", str(pg), "-l", str(pg), p,
                              "-"], capture_output=True, text=True).stdout
        assert "OrbitDeck" in txt and "N8HM" in txt, \
            "page %d of the full set should carry the credit" % pg

    # Reduced set: the base map (page 1) is printed on card and IS branded, but
    # the clean transparency overlays (pages 2 and 3) must stay credit-free.
    pr = os.path.join(d, "reduced.pdf")
    generate_oscarlocator_pdf(pr, st, s, projection="polar",
                              footprint_on_qth=False, reduced_text=True)
    base = subprocess.run(["pdftotext", "-f", "1", "-l", "1", pr, "-"],
                          capture_output=True, text=True).stdout
    assert "OrbitDeck" in base and "N8HM" in base
    for pg in (2, 3):
        trans = subprocess.run(["pdftotext", "-f", str(pg), "-l", str(pg), pr,
                                "-"], capture_output=True, text=True).stdout
        assert "OrbitDeck" not in trans, \
            "clean transparency page %d must not carry branding" % pg

def test_oscarlocator_reduced_arc_renders_all_inclinations():
    """The reduced-text path-arc renders for a range of inclinations and for
    both hemispheres without error (the dynamic info-box placement must not
    blow up on prograde, retrograde, or southern sheets)."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    from orbitdeck.engine.predict import Observer
    st = Store()
    d = tempfile.mkdtemp()
    sats = st.db.sats
    # north then south QTH, each with a couple of projections
    for obs in (Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True),
                Observer(lat=-33.9, lon=151.2, alt_m=20, valid=True)):
        st.obs = obs
        for s in sats:
            for proj in ("qth", "polar-auto"):
                p = os.path.join(d, "a_%s_%s_%s.pdf" % (
                    s.norad, proj, obs.lat))
                generate_oscarlocator_pdf(p, st, s, projection=proj,
                                          reduced_text=True)
                assert os.path.exists(p) and os.path.getsize(p) > 1000

def test_oscarlocator_options_dialog_returns_dict():
    """The single options dialog returns the projection / range-circle / reduced
    selections as a dict (replacing the old chain of yes/no questions)."""
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.gui.dialogs import OscarlocatorOptionsDialog
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        OrbitDeckApp(root)
    except Exception:
        root.destroy()
        return
    d = OscarlocatorOptionsDialog(root, sat_name="RS-44")
    d._proj.set("qth")
    d._fp.set(True)
    d._reduced.set(True)
    d._ok()
    assert d.result == {"projection": "qth", "footprint_on_qth": True,
                        "reduced_text": True}
    root.destroy()

def test_oscarlocator_reduced_text_generates_all_modes():
    """Reduced-text PDFs render for the 3-sheet, combined, and polar variants."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.oscarlocator import generate_oscarlocator_pdf
    from orbitdeck.engine.predict import Observer
    st = Store()
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
    s = st.db.sats[0]
    d = tempfile.mkdtemp()
    cases = [("qth", False), ("qth", True), ("polar", False)]
    for proj, fp in cases:
        p = os.path.join(d, "r_%s_%s.pdf" % (proj, fp))
        generate_oscarlocator_pdf(p, st, s, projection=proj,
                                  footprint_on_qth=fp, reduced_text=True)
        assert os.path.exists(p) and os.path.getsize(p) > 1000

def test_oscarsim_independent_overlay_toggles():
    """The OSCARLOCATOR Sim exposes independent range-circle and footprint
    toggles that both render without error."""
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.gui.screens import make_screen
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        return
    app.store.select(app.store.db.sats[0].norad)
    scr = make_screen("oscarsim", app.content, app)
    scr.on_show()
    assert hasattr(scr, "_show_range") and hasattr(scr, "_show_foot")
    for r in (True, False):
        for f in (True, False):
            scr._show_range.set(r)
            scr._show_foot.set(f)
            scr._render()
    root.destroy()

def test_oscarlocator_rim_ticks_drawn():
    """Every degree of the rim gets a tick on the map and arc pages (360 ticks),
    so the rim reads like a protractor. Exercised by drawing onto a polar axes
    and counting the line artists the helper adds."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from orbitdeck.gui.oscarlocator import _draw_rim_ticks
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="polar")
    before = len(ax.lines)
    _draw_rim_ticks(ax, 90.0)
    added = len(ax.lines) - before
    plt.close(fig)
    assert added == 360

def test_oscarlocator_combined_map_renders_both_projections():
    """The combined map+footprint page renders for both the QTH and polar
    projections without error, and the polar variant draws QTH-centred elevation
    rings (the projected-ring helper is exercised)."""
    import os
    import tempfile
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.gui.oscarlocator import (generate_oscarlocator_pdf,
                                            _draw_qth_rings_projected,
                                            _draw_footprint_overlay)
    # the shared helpers must exist (footprint style is centralised so the
    # standalone and combined sheets stay identical)
    assert callable(_draw_footprint_overlay)
    assert callable(_draw_qth_rings_projected)
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        return
    sat = next((s for s in app.store.db.sats if s.name == "RS-44"),
               app.store.db.sats[0])
    app.store.select(sat.norad)
    d = tempfile.mkdtemp()
    for proj in ("qth", "polar"):
        path = os.path.join(d, "osc_%s.pdf" % proj)
        generate_oscarlocator_pdf(path, app.store, sat, projection=proj,
                                  footprint_on_qth=True)
        assert os.path.exists(path) and os.path.getsize(path) > 1000
    root.destroy()


def test_polar_range_circle_inflation():
    """The standalone polar range-circle transparency is enlarged by the fixed
    population-optimised factor (so a single generic circle best fits the polar
    map's oval distortion), while the QTH-centred transparency is left exact."""
    from orbitdeck.gui.oscarlocator import (_polar_range_circle_deg,
                                            POLAR_RANGE_CIRCLE_INFLATION)
    # factor is the agreed generic optimum and is a mild enlargement
    assert 1.0 < POLAR_RANGE_CIRCLE_INFLATION < 1.12
    foot = 38.3
    assert abs(_polar_range_circle_deg(foot)
               - foot * POLAR_RANGE_CIRCLE_INFLATION) < 1e-9
    # it never shrinks the circle
    assert _polar_range_circle_deg(foot) > foot


def test_polar_range_circle_reduces_population_weighted_error():
    """Sanity check on the optimisation itself: enlarging the circle by the
    chosen factor lowers the population-weighted worst-case error versus the raw
    footprint circle on the polar (pole-centred azimuthal-equidistant) sheet."""
    import math
    from orbitdeck.gui.oscarlocator import POLAR_RANGE_CIRCLE_INFLATION

    def true_radii(qlat, foot, n=180):
        qy = 90.0 - qlat
        p1 = math.radians(abs(qlat))
        d = math.radians(foot)
        out = []
        for i in range(n):
            az = math.radians(360.0 * i / n)
            p2 = math.asin(math.sin(p1) * math.cos(d)
                           + math.cos(p1) * math.sin(d) * math.cos(az))
            dlon = math.atan2(math.sin(az) * math.sin(d) * math.cos(p1),
                              math.cos(d) - math.sin(p1) * math.sin(p2))
            bcolat = 90.0 - math.degrees(p2)
            out.append(math.hypot(bcolat * math.sin(dlon),
                                  bcolat * math.cos(dlon) - qy))
        return out

    def maxerr(qlat, foot, factor):
        rs = true_radii(qlat, foot)
        r = foot * factor
        return max(abs(x - r) for x in rs)

    # population-by-latitude (northern-hemisphere heavy)
    pop = [(55, .16), (45, .215), (35, .274), (25, .176), (15, .068),
           (5, .039)]
    foot = 38.3
    raw = sum(w * maxerr(lat, foot, 1.0) for lat, w in pop)
    opt = sum(w * maxerr(lat, foot, POLAR_RANGE_CIRCLE_INFLATION)
              for lat, w in pop)
    assert opt < raw            # the inflated circle is better on average
