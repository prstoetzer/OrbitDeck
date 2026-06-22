"""Shared paper-size definitions for OrbitDeck's printable PDFs.

Every PDF generator lays its page out in physical inches so the printout has a
known scale (critical for the OSCARLOCATOR, whose base map and transparency
overlays must register at 100% print scale). Historically that page was always
US Letter (8.5 x 11 in). This module adds A4 as a global, user-selectable
option while keeping Letter the default.

Usage in a generator:

    from .pagesize import page_dims
    PAGE_W_IN, PAGE_H_IN = page_dims(store)        # reads store.config
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))

The returned dimensions drive the matplotlib ``figsize``. Because the existing
sheets position their content in *figure fractions* (0..1) rather than absolute
inches, switching the page size reshapes the figure and the fractional layout
follows automatically; only genuinely scale-locked artwork (the OSCARLOCATOR
disc) is pinned to an absolute size on top of this.
"""

# (width_in, height_in) for each supported paper size, portrait orientation.
PAGE_SIZES = {
    "letter": (8.5, 11.0),     # US Letter (default)
    "a4": (8.2677, 11.6929),   # ISO A4 (210 x 297 mm)
}

DEFAULT_PAGE = "letter"

# Human-readable labels for the settings UI.
PAGE_LABELS = {
    "letter": "US Letter (8.5 x 11 in)",
    "a4": "A4 (210 x 297 mm)",
}


def normalize(name):
    """Return a valid page-size key for ``name`` (case-insensitive), falling
    back to the default for anything unrecognised or missing."""
    if not name:
        return DEFAULT_PAGE
    key = str(name).strip().lower()
    return key if key in PAGE_SIZES else DEFAULT_PAGE


def page_dims(source=None):
    """Resolve (width_in, height_in) for the active page size.

    ``source`` may be:
      * a Store (or anything exposing a ``config`` dict) -- the page size is
        read from ``config['page_size']``;
      * a page-size string such as ``"a4"``;
      * ``None`` -- the default (Letter).
    """
    name = None
    if source is None:
        name = DEFAULT_PAGE
    elif isinstance(source, str):
        name = source
    else:
        cfg = getattr(source, "config", None)
        if isinstance(cfg, dict):
            name = cfg.get("page_size")
    return PAGE_SIZES[normalize(name)]
