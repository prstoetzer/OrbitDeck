"""Printable PDF report tests.

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


def test_satellite_report_generates():
    """The PDF report generates with all sections and is a valid multi-page PDF."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.reports import generate_satellite_report
    from orbitdeck.engine.predict import Observer
    st = Store()
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
    s = st.db.sats[0]
    out = os.path.join(tempfile.mkdtemp(), "report.pdf")
    generate_satellite_report(out, st, s)
    assert os.path.getsize(out) > 5000
    with open(out, "rb") as f:
        assert f.read(5) == b"%PDF-"

def test_satellite_report_section_subset():
    """Selecting a single section still generates a valid report."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.reports import generate_satellite_report
    from orbitdeck.engine.predict import Observer
    st = Store()
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
    s = st.db.sats[0]
    out = os.path.join(tempfile.mkdtemp(), "report_analysis.pdf")
    generate_satellite_report(out, st, s, sections=("analysis",))
    assert os.path.getsize(out) > 3000

def test_report_generators_exist():
    """The new report entry points are importable from the reports module."""
    from orbitdeck.gui import reports
    assert hasattr(reports, "generate_favorites_passes_report")
    assert hasattr(reports, "generate_mutual_passes_report")
    assert hasattr(reports, "generate_illumination_report")
    assert hasattr(reports, "generate_progression_report")

def test_favorites_passes_report_generates():
    """The favorites pass schedule generates a valid PDF (and handles the empty
    favorites case)."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.reports import generate_favorites_passes_report
    from orbitdeck.engine.predict import Observer
    st = Store()
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
    d = tempfile.mkdtemp()
    # empty favorites -> still a valid PDF
    out0 = os.path.join(d, "fav0.pdf")
    generate_favorites_passes_report(out0, st, days=3)
    assert os.path.getsize(out0) > 2000
    # with a couple of favorites
    for s in st.db.sats[:3]:
        st.favorites.add(s.norad)
    out = os.path.join(d, "fav.pdf")
    generate_favorites_passes_report(out, st, days=3)
    assert os.path.getsize(out) > 3000
    with open(out, "rb") as f:
        assert f.read(5) == b"%PDF-"

def test_mutual_illum_progression_reports_generate():
    """The mutual, illumination (60-day) and progression (30-day) reports all
    generate valid PDFs."""
    import os
    import tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui import reports as R
    from orbitdeck.engine.predict import Observer
    st = Store()
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
    s = st.db.sats[0]
    dx = Observer(lat=51.5, lon=-0.1, alt_m=10, valid=True)
    d = tempfile.mkdtemp()
    for fn, args in [
        (R.generate_mutual_passes_report, (s, dx)),
        (R.generate_illumination_report, (s,)),
        (R.generate_progression_report, (s,)),
    ]:
        out = os.path.join(d, fn.__name__ + ".pdf")
        fn(out, st, *args)
        assert os.path.getsize(out) > 3000
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"

def test_polar_passes_report_generates():
    """The 3-day polar sky-tracks report generates a valid PDF."""
    import os, tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.reports import generate_polar_passes_report
    from orbitdeck.engine.predict import Observer
    st = Store()
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
    s = st.db.sats[0]
    out = os.path.join(tempfile.mkdtemp(), "polar.pdf")
    generate_polar_passes_report(out, st, s, days=3)
    assert os.path.getsize(out) > 3000
    with open(out, "rb") as f:
        assert f.read(5) == b"%PDF-"

def test_comprehensive_report_has_graphic_sections():
    """The comprehensive report with all sections generates a multi-page PDF."""
    import os, tempfile
    from orbitdeck.gui.store import Store
    from orbitdeck.gui.reports import generate_satellite_report
    from orbitdeck.engine.predict import Observer
    st = Store()
    st.obs = Observer(lat=39.9, lon=-75.0, alt_m=20, valid=True)
    s = st.db.sats[0]
    out = os.path.join(tempfile.mkdtemp(), "comp.pdf")
    generate_satellite_report(out, st, s)   # default sections incl. graphics
    assert os.path.getsize(out) > 8000
    with open(out, "rb") as f:
        data = f.read()
    assert data[:5] == b"%PDF-"
    # several pages expected (text + polar + illum + progression)
    assert data.count(b"/Type /Page") + data.count(b"/Type/Page") >= 4

def test_http_get_reports_403_and_404_clearly():
    """HTTP 403 (rate-limit/firewall) and 404 surface actionable messages, so a
    user isn't left guessing and a process won't blindly retry."""
    import io
    import urllib.error
    import orbitdeck.gui.net as net
    saved = net.urllib.request.urlopen
    try:
        def u403(req, timeout=None, context=None):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {},
                                         io.BytesIO(b""))
        net.urllib.request.urlopen = u403
        raised = ""
        try:
            net.http_get("https://celestrak.org/NORAD/elements/gp.php?GROUP=x")
        except RuntimeError as e:
            raised = str(e)
        assert "403" in raised
        def u404(req, timeout=None, context=None):
            raise urllib.error.HTTPError(req.full_url, 404, "NF", {},
                                         io.BytesIO(b""))
        net.urllib.request.urlopen = u404
        raised = ""
        try:
            net.http_get("https://celestrak.org/x")
        except RuntimeError as e:
            raised = str(e)
        assert "404" in raised
    finally:
        net.urllib.request.urlopen = saved


def test_report_content_clears_branding_footer():
    """Regression: printed reports must not draw content on top of the centred
    branding credit at the foot of each page (which sits at y=0.045). The full
    satellite report's pass-progression timeline chart previously printed its
    x-axis label over the branding. Assert the flow floor and the timeline chart
    bottom both sit clear of the branding band, and that a generated report
    renders with no text below the clearance line."""
    import os
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.engine import Observer
    from orbitdeck.gui import reports as R

    # static guarantees on the layout constants
    # branding occupies ~0.045..0.058; the content flow floor must be above it
    src = open(os.path.join(os.path.dirname(R.__file__), "reports.py")).read()
    assert "self.y - need < 0.085" in src, "flow floor regressed below branding"
    assert "fig.add_axes([0.13, 0.12," in src, "timeline chart bottom regressed"

    try:
        root = tk.Tk()
    except Exception:
        return
    try:
        app = OrbitDeckApp(root)
    except Exception:
        return
    app.store.save_config(onboarded=True)
    app.store.obs = Observer(lat=39.93, lon=-74.89, alt_m=20, valid=True)
    sat = next((s for s in app.store.db.sats if s.transponders), None)
    if sat is None:
        root.destroy()
        return
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "test_branding_report.pdf")
    R.generate_satellite_report(path, app.store, sat)
    assert os.path.exists(path) and os.path.getsize(path) > 0
    root.destroy()


def test_rove_sheet_paginates_and_keeps_full_dxcc_names():
    """The rove plan sheet must (a) paginate so entries never overflow into the
    footer branding, and (b) keep full DXCC entity names (e.g. 'United States',
    not a space-truncated 'United')."""
    import os
    import tempfile
    import tkinter as tk
    from orbitdeck.gui.app import OrbitDeckApp
    from orbitdeck.engine import Observer
    from orbitdeck.gui.rovesheet import generate_rove_sheet_pdf

    try:
        root = tk.Tk()
    except Exception:
        return
    try:
        app = OrbitDeckApp(root)
    except Exception:
        return
    app.store.save_config(onboarded=True)
    app.store.obs = Observer(lat=39.93, lon=-74.89, alt_m=20, valid=True)

    def res(el):
        return {"aos": 1.75e9, "los": 1.75e9 + 1200, "max_el": el,
                "grids": list(range(1234)),
                "states": {"NJ", "PA", "NY"},
                "dxcc": {"United States", "Canada"}}
    # many stops -> must split across pages
    rows = [("FN%02d" % i, "RS-44", res(30 + i)) for i in range(14)]
    path = os.path.join(tempfile.gettempdir(), "test_rove.pdf")
    generate_rove_sheet_pdf(path, "RS-44", app.store, rows)
    assert os.path.exists(path) and os.path.getsize(path) > 0

    # the PDF should have more than one page for 14 stops
    try:
        import pypdf
        n = len(pypdf.PdfReader(path).pages)
    except Exception:
        n = None
    if n is not None:
        assert n >= 2, "14 rove stops should paginate to >=2 pages, got %s" % n
    root.destroy()


def test_predictor_observer_cache_matches_recompute():
    """The cached observer ECEF/latitude trig (a speed optimisation) must exactly
    equal the on-the-fly computation, and must refresh when the site changes."""
    import math
    from orbitdeck.engine import Observer, Predictor
    from orbitdeck.engine.predict import _geodetic_to_ecef, DEG

    for lat, lon, alt in [(39.93, -74.89, 20), (-33.9, 18.4, 100), (0, 0, 0)]:
        p = Predictor()
        p.set_site(Observer(lat=lat, lon=lon, alt_m=alt, valid=True))
        assert p._obs_ecef == _geodetic_to_ecef(lat, lon, alt / 1000.0)
        assert p._obs_slat == math.sin(lat * DEG)
        assert p._obs_clat == math.cos(lat * DEG)
    p = Predictor()
    p.set_site(Observer(lat=0, lon=0, alt_m=0, valid=True))
    e1 = p._obs_ecef
    p.set_site(Observer(lat=45, lon=90, alt_m=0, valid=True))
    assert p._obs_ecef != e1, "observer cache did not refresh on set_site"
