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
