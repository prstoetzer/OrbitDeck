"""
mapdraw.py - draw a world basemap into a matplotlib Axes.

Prefers Cartopy + Natural Earth coastlines when installed (high fidelity);
otherwise falls back to the bundled simplified coastlines so the World Map and
Ground Track screens always render a real map with no required dependency.
"""

_HAVE_CARTOPY = False
try:  # optional, high-fidelity path
    import cartopy.crs as ccrs        # noqa: F401
    import cartopy.feature as cfeature  # noqa: F401
    _HAVE_CARTOPY = True
except Exception:
    _HAVE_CARTOPY = False

from ..data.worldmap_data import COASTLINES

OCEAN = "#0b1e3a"
LAND_EDGE = "#2c4a63"
LAND_FILL = "#13314d"
GRATICULE = "#1d2f44"


def have_cartopy():
    return _HAVE_CARTOPY


def draw_basemap(ax, graticule=True):
    """Draw coastlines/landmasses and a lon/lat grid into a normal (non-GeoAxes)
    matplotlib Axes spanning lon -180..180, lat -90..90.

    We deliberately use a plain Axes (not a Cartopy GeoAxes) so the rest of the
    app can plot in raw lon/lat without projection bookkeeping. When Cartopy is
    present we still use its coastline geometry for fidelity.
    """
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.set_facecolor(OCEAN)

    drew = False
    if _HAVE_CARTOPY:
        try:
            _draw_cartopy_geometry(ax)
            drew = True
        except Exception:
            drew = False
    if not drew:
        for poly in COASTLINES:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            ax.plot(xs, ys, color=LAND_EDGE, linewidth=0.9, zorder=1)

    if graticule:
        for lon in range(-180, 181, 30):
            ax.axvline(lon, color=GRATICULE, linewidth=0.4, zorder=0)
        for lat in range(-90, 91, 30):
            ax.axhline(lat, color=GRATICULE, linewidth=0.4, zorder=0)
    ax.set_xticks(range(-180, 181, 60))
    ax.set_yticks(range(-90, 91, 30))


def _draw_cartopy_geometry(ax):
    """Extract Natural Earth coastline geometry from Cartopy and plot it as
    raw lon/lat lines onto the plain Axes."""
    import cartopy.feature as cfeature
    coast = cfeature.NaturalEarthFeature("physical", "coastline", "110m")
    for geom in coast.geometries():
        for line in _iter_lines(geom):
            xs, ys = zip(*line)
            ax.plot(xs, ys, color=LAND_EDGE, linewidth=0.8, zorder=1)


def _iter_lines(geom):
    """Yield coordinate lists from shapely geometries (Line/Multi/Polygon)."""
    gt = geom.geom_type
    if gt == "LineString":
        yield list(geom.coords)
    elif gt in ("MultiLineString", "GeometryCollection"):
        for g in geom.geoms:
            yield from _iter_lines(g)
    elif gt == "Polygon":
        yield list(geom.exterior.coords)
    elif gt == "MultiPolygon":
        for g in geom.geoms:
            yield list(g.exterior.coords)
