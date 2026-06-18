"""Eclipse-period tests.

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


def test_eclipse_periods_well_formed(iss_predictor):
    """Umbral eclipse periods for a LEO bird: several per day, each enter<exit,
    positive duration, sorted, non-overlapping, with a plausible duration."""
    pred, sat = iss_predictor
    t0 = sat.epoch_unix
    ecl = pred.predict_eclipses(t0, max_n=64, horizon_days=1.0)
    assert len(ecl) >= 8                     # a LEO is eclipsed most orbits
    prev_exit = None
    for e in ecl:
        assert e.enter < e.exit
        assert e.duration_s > 0
        # an ISS-altitude eclipse runs well under an orbital period
        assert 60.0 < e.duration_s < 2400.0
        if prev_exit is not None:
            assert e.enter >= prev_exit       # sorted, non-overlapping
        prev_exit = e.exit

def test_eclipse_starts_after_query_even_mid_shadow(iss_predictor):
    """Starting the scan inside an eclipse must not emit a truncated period:
    the first returned 'enter' is at or after the query time."""
    pred, sat = iss_predictor
    t0 = sat.epoch_unix
    ecl = pred.predict_eclipses(t0, max_n=8, horizon_days=1.0)
    assert ecl
    mid = 0.5 * (ecl[0].enter + ecl[0].exit)
    ecl2 = pred.predict_eclipses(mid, max_n=4, horizon_days=0.3)
    assert ecl2
    assert ecl2[0].enter >= mid

def test_eclipse_daily_summary_consistency(iss_predictor):
    """Daily summary buckets must agree with the raw period list: per-day total
    equals the sum of that day's durations and longest is the max."""
    import math as _m
    pred, sat = iss_predictor
    t0 = sat.epoch_unix
    days = 3
    ecl = pred.predict_eclipses(t0, max_n=10000, horizon_days=float(days))
    summary = pred.eclipse_daily_summary(t0, days=days)
    assert len(summary) == days
    by_day = {}
    for e in ecl:
        d = _m.floor(e.enter / 86400.0) * 86400.0
        by_day.setdefault(d, []).append(e)
    for row in summary:
        es = by_day.get(row["date"], [])
        assert row["count"] == len(es)
        assert row["total_s"] == pytest.approx(
            sum(e.duration_s for e in es), abs=1.0)
        assert row["longest_s"] == pytest.approx(
            max((e.duration_s for e in es), default=0.0), abs=1.0)
        assert 0.0 <= row["percent"] <= 100.0

def test_eclipse_export_rows_shapes(iss_predictor):
    """The eclipse exporters produce header+row tables with matching widths and
    a populated interval column from the second row on."""
    from orbitdeck.gui import exports as EX
    pred, sat = iss_predictor
    t0 = sat.epoch_unix
    ecl = pred.predict_eclipses(t0, max_n=64, horizon_days=1.0)
    summ = pred.eclipse_daily_summary(t0, days=2)
    h1, r1 = EX.eclipse_periods_rows(ecl, sat.name)
    assert r1 and all(len(row) == len(h1) for row in r1)
    assert r1[0][4] == ""                     # first interval blank
    assert r1[1][4] != ""                     # later intervals populated
    h2, r2 = EX.eclipse_daily_rows(summ, sat.name)
    assert len(r2) == 2 and all(len(row) == len(h2) for row in r2)
