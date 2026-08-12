"""Backwards-compatible shim.

The HTTP helpers moved to :mod:`orbitdeck.netio` so OrbitTerm does not have to
import from a package named ``gui`` to make a web request.
"""

from ..netio import (http_get, http_post_json, http_post_form,  # noqa: F401
                     USER_AGENT, _context, _build_context, urllib)
