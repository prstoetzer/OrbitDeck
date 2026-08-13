"""Audit items C and D: MUF map, link-margin curve, DXCC lookup, GP-fit checks."""

import time

from orbitdeck.engine import linkbudget as LB
from orbitdeck.engine import muf as M
from orbitdeck.engine import refdata as RD
from orbitdeck.engine import statevector as SV


def test_link_margin_curve_shows_the_horizon_penalty():
    """The Tools calculator answers 'budget at 1000 km'; the decision turns on
    how much worse the horizon is than overhead."""
    rows = LB.link_margin_curve(500, 145.8e6, step=10.0)
    assert len(rows) == 10
    horizon, zenith = rows[0], rows[-1]
    assert horizon["elevation_deg"] == 0 and zenith["elevation_deg"] == 90
    # slant range shrinks and margin improves toward zenith
    assert horizon["slant_km"] > 4 * zenith["slant_km"]
    assert zenith["margin_db"] - horizon["margin_db"] > 10
    assert abs(zenith["slant_km"] - 500) < 1        # straight up
    # margin follows the sensitivity figure
    strict = LB.link_margin_curve(500, 145.8e6, sensitivity_dbm=-100.0)
    assert strict[0]["margin_db"] < rows[0]["margin_db"]


def test_muf_grid_covers_the_world_and_varies():
    lats, lons, vals = M.muf_grid(39.93, -74.89, time.time(), 100)
    assert len(lats) == len(vals)
    assert all(len(r) == len(lons) for r in vals)
    flat = [v for row in vals for v in row if v]
    assert flat
    # day and night sides differ markedly - that is what the map is for
    assert max(flat) - min(flat) > 5.0
    assert 2.0 < min(flat) and max(flat) < 60.0


def test_dxcc_lookup_finds_entities_and_reports_no_zone():
    """The bundled zone tables are ranges, not polygons. An early cut derived a
    zone from them and put Japan in 'Asiatic Russia' because that row's text
    contains 'Asia' - a wrong zone in a log is worse than none."""
    hits = RD.zone_lookup("JA")
    assert hits and hits[0][0] == "JA" and "Japan" in hits[0][1]
    assert "36" in hits[0][2]                       # coordinates, not a zone
    for row in hits:
        assert "zone" not in row[2].lower()
    assert RD.zone_lookup("Japan")[0][1] == "Japan"
    assert RD.zone_lookup("NOPE") == []
    assert RD.zone_lookup("") == []


def test_state_vector_diagnostics_catch_unit_mistakes():
    """A converged-looking element set from a bad vector is the dangerous case;
    meters-for-kilometers is the classic way to get plausible garbage."""
    good = SV.fit_diagnostics((6800, 0, 0), (0, 7.66, 0))
    assert good["plausible"]
    assert abs(good["speed_ratio"] - 1.0) < 0.01
    meters = SV.fit_diagnostics((6800000, 0, 0), (0, 7660, 0))
    assert not meters["plausible"]
    assert any("unit" in n or "meters" in n for n in meters["notes"])
    inside = SV.fit_diagnostics((3000, 0, 0), (0, 7.66, 0))
    assert not inside["plausible"]
    slow = SV.fit_diagnostics((6800, 0, 0), (0, 0.1, 0))
    assert not slow["plausible"]


def test_new_tools_registered_and_shaped():
    from orbitdeck.engine.tools_registry import TOOLS
    for key in ("dxcc_lookup", "link_margin", "gp_fit_check"):
        assert key in TOOLS
        spec = TOOLS[key]
        rows = spec["fn"](*[f.get("default") for f in spec["fields"]])
        assert rows and all(len(r) == 3 for r in rows)


def test_muf_screen_has_a_map():
    import inspect
    from orbitdeck.gui.screens import muf as gm
    src = inspect.getsource(gm.MufScreen)
    assert "_draw_map" in src and "muf_grid" in src
