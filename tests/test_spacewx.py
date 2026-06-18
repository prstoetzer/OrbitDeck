"""Space-weather tests.

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


def test_spacewx_labels_and_ap():
    from orbitdeck.gui import spacewx as W
    assert W.flux_label(140)[1] == "good"
    assert W.flux_label(80)[1] == "low"
    assert W.kp_label(1)[0] == "quiet"
    assert W.kp_label(6.5)[0] == "moderate storm"
    assert W.kp_label(8)[0] == "major storm"
    # Kp->ap monotonic and matches table anchors
    assert W._kp_to_ap(0) == 0
    assert W._kp_to_ap(4) == 27
    assert W._kp_to_ap(9) == 400
    out = W.outlook(140, 6)
    assert "storm" in out.lower()

def test_spacewx_ka_populate_from_feeds():
    import json
    from orbitdeck.gui import spacewx as W
    def fake(url, timeout=20):
        if "f107" in url:
            return json.dumps([{"flux": "138.2"}])
        if "planetary_k_index_1m" in url:
            return json.dumps([{"kp_index": 3.67}, {"kp_index": 4.33}])
        if "daily-geomagnetic" in url:
            return "# h\n2026 06 14   27   4 4 5 4 3 3 3 2\n"
        return "[]"
    orig = W._http_get
    W._http_get = fake
    try:
        d = W.fetch()
    finally:
        W._http_get = orig
    assert abs(d["kp"] - 4.33) < 0.01
    assert abs(d["a_index"] - 27) < 0.01      # A populates from DGD
    assert abs(d["flux"] - 138.2) < 0.1

def test_spacewx_ka_fallback_products_array():
    import json
    from orbitdeck.gui import spacewx as W
    def fake(url, timeout=20):
        if "planetary_k_index_1m" in url:
            return "[]"
        if "noaa-planetary-k-index" in url:
            return json.dumps([["time_tag", "Kp", "a_running", "n"],
                               ["2026-06-14 09:00:00", "5.33", "56", "8"]])
        if "f107" in url:
            return json.dumps([{"flux": "120"}])
        return "# none\n"
    orig = W._http_get
    W._http_get = fake
    try:
        d = W.fetch()
    finally:
        W._http_get = orig
    assert abs(d["kp"] - 5.33) < 0.01
    assert d["a_index"] is not None           # derived from Kp


def test_spacewx_color_map_has_no_duplicate_keys():
    """Regression: the space-weather level->colour map must not declare any key
    twice (a duplicate silently dropped the intended colour for that level)."""
    import ast
    import inspect
    from orbitdeck.gui.screens import spacewx as SW
    src = inspect.getsource(SW._color_for)
    tree = ast.parse(src.strip())
    # find the dict literal inside the function and check for duplicate keys
    dicts = [n for n in ast.walk(tree) if isinstance(n, ast.Dict)]
    assert dicts, "expected a colour dict in _color_for"
    keys = [k.value for d in dicts for k in d.keys
            if isinstance(k, ast.Constant)]
    assert len(keys) == len(set(keys)), "duplicate key in space-weather map"
    # and "moderate" resolves to a single, defined colour
    assert SW._color_for("moderate")
