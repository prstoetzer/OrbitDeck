"""Shared non-fixture helpers for the OrbitDeck test suite."""

import datetime as dt


def _jd_from_tle_epoch(year, day):
    if year < 57:
        year += 2000
    else:
        year += 1900
    d = dt.datetime(year, 1, 1)
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    jdn = (d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100
           + y // 400 - 32045)
    return (jdn - 0.5) + (day - 1.0)
