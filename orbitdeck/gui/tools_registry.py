"""Backwards-compatible shim.

The tools registry moved to ``orbitdeck.engine.tools_registry`` so both the
desktop GUI and OrbitTerm can share it. This module re-exports it.
"""

from ..engine.tools_registry import TOOLS, CATEGORIES  # noqa: F401
