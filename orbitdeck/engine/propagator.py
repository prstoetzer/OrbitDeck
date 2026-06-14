"""
propagator.py - chooses the best available SGP4 backend.

If the user has the `sgp4` PyPI package installed (the C-accelerated Vallado
reference, full SDP4 deep-space), we use it. Otherwise we fall back to the
vendored pure-Python `sgp4_lite`, which is verified accurate for near-Earth
LEO (the FM/linear amateur birds) and approximate for deep-space orbits.

Both backends are exposed through a single `make_satrec(elements)` returning an
object with `.sgp4(tsince_minutes) -> (r_km, v_kms)` and `.error`.
"""

import math

_HAVE_PYPI = False
try:
    from sgp4.api import Satrec as _PypiSatrec, WGS72 as _WGS72  # type: ignore
    _HAVE_PYPI = True
except Exception:
    _HAVE_PYPI = False

from .sgp4_lite import Satrec as _LiteSatrec


def have_full_sdp4():
    """True if the high-accuracy pip backend (full SDP4) is in use."""
    return _HAVE_PYPI


class _LiteAdapter:
    """Wrap the vendored propagator behind the common interface."""

    def __init__(self, sat):
        self._s = sat

    @property
    def error(self):
        return self._s.error

    @property
    def is_deep(self):
        return self._s.isdeep

    def sgp4(self, tsince_min):
        return self._s.sgp4(tsince_min)


class _PypiAdapter:
    def __init__(self, sat, jd_epoch):
        self._s = sat
        self._jd = jd_epoch

    @property
    def error(self):
        return self._s.error

    @property
    def is_deep(self):
        return self._s.method == 'd'

    def sgp4(self, tsince_min):
        # Propagate using the epoch JD recorded at build time, split into
        # integer day + fractional remainder for the library's precise path.
        total = self._jd + tsince_min / 1440.0
        jd = float(int(total))
        fr = total - jd
        e, r, v = self._s.sgp4(jd, fr)
        return list(r), list(v)


def make_satrec(el):
    """Build a propagator from an Elements namedtuple-like object.

    `el` must expose: jdsatepoch, bstar, ndot, nddot, ecco, argpo_deg,
    inclo_deg, mo_deg, no_kozai_revperday, nodeo_deg, satnum.
    """
    if _HAVE_PYPI:
        s = _PypiSatrec()
        # mean motion to rad/min for sgp4init
        no_kozai = el.no_kozai_revperday / 1440.0 * 2.0 * math.pi
        # epoch days since 1949-12-31 00:00 UT
        epoch_days = el.jdsatepoch - 2433281.5
        d2r = math.pi / 180.0
        s.sgp4init(_WGS72, 'i', el.satnum, epoch_days, el.bstar,
                   el.ndot, el.nddot, el.ecco, el.argpo_deg * d2r,
                   el.inclo_deg * d2r, el.mo_deg * d2r, no_kozai,
                   el.nodeo_deg * d2r)
        return _PypiAdapter(s, el.jdsatepoch)
    s = _LiteSatrec()
    s.init_from_elements(el.jdsatepoch, el.bstar, el.ndot, el.nddot,
                         el.ecco, el.argpo_deg, el.inclo_deg, el.mo_deg,
                         el.no_kozai_revperday, el.nodeo_deg, el.satnum)
    return _LiteAdapter(s)
