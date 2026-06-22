"""refsheet.py - printable "reference orbits" table for OSCARLOCATOR use.

For each UTC day over a span (default 60 days) this lists the *reference orbit*:
the FIRST equator crossing of that UTC day -- ascending for northern-hemisphere
stations, descending for southern-hemisphere stations -- giving the crossing time
(UTC) and the sub-satellite longitude at the crossing. Those two numbers are
exactly what you set on a physical OSCARLOCATOR to line up the path-arc overlay
for that day's first pass, then step forward orbit by orbit.

One satellite per page (or a combined multi-satellite export). Pure matplotlib
PdfPages output, matching the rest of OrbitDeck's printables (no extra deps).
"""

import datetime as dt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages   # noqa: E402

from ..engine.predict import Predictor   # noqa: E402


PAGE_W_IN = 8.5
PAGE_H_IN = 11.0
ROWS_PER_PAGE = 31           # ~a month per page; 60 days -> 2 pages/sat


def _lon_str(lon):
    return "%.1f\u00b0%s" % (abs(lon), "E" if lon >= 0 else "W")


def reference_orbits(pred, lat, start_unix, days):
    """Return a list of dicts, one per UTC day:
        {"date": date, "t": unix|None, "lon": deg|None}
    using the first ascending (lat>=0) or first descending (lat<0) crossing of
    each UTC day."""
    descending = lat < 0.0
    day = 86400.0
    # start at 00:00 UTC of the start day
    d0 = dt.datetime.fromtimestamp(start_unix, dt.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0)
    base = d0.timestamp()
    # one search over the whole span is far cheaper than per-day searches
    nodes = (pred.descending_nodes(base, base + (days + 1) * day, max_n=4000)
             if descending else
             pred.ascending_nodes(base, base + (days + 1) * day, max_n=4000))
    out = []
    for i in range(days):
        ds = base + i * day
        de = ds + day
        first = next((n for n in nodes if ds <= n[0] < de), None)
        date = dt.datetime.fromtimestamp(ds, dt.timezone.utc).date()
        if first:
            out.append({"date": date, "t": first[0], "lon": first[1]})
        else:
            out.append({"date": date, "t": None, "lon": None})
    return out, descending


def _sat_pages(pdf, store, sat, days, start_unix):
    pred = Predictor()
    try:
        pred.set_site(store.obs)
        pred.set_sat(sat)
    except Exception:
        pass
    lat = store.obs.lat
    # geosynchronous / very high orbits hold a sub-point and have no useful
    # equator-crossing reference orbits
    if (sat.period_min or 0) > 600:
        fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        fig.text(0.5, 0.9, "%s \u2014 OSCARLOCATOR Reference Orbits" % sat.name,
                 ha="center", fontsize=15, fontweight="bold")
        fig.text(0.5, 0.5,
                 "%s is a geosynchronous / high-altitude satellite:\nit holds a "
                 "fixed sub-point and has no equator-crossing\nreference orbits."
                 % sat.name, ha="center", va="center", fontsize=11,
                 color="#555555")
        pdf.savefig(fig)
        plt.close(fig)
        return

    rows, descending = reference_orbits(pred, lat, start_unix, days)
    node_name = "Descending" if descending else "Ascending"
    hemi = "southern" if descending else "northern"

    for pg in range(0, len(rows), ROWS_PER_PAGE):
        chunk = rows[pg:pg + ROWS_PER_PAGE]
        fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        fig.text(0.5, 0.955,
                 "%s \u2014 OSCARLOCATOR Reference Orbits" % sat.name,
                 ha="center", fontsize=15, fontweight="bold")
        fig.text(0.5, 0.927,
                 "First %s equator crossing of each UTC day "
                 "(%s-hemisphere station, lat %.2f\u00b0)"
                 % (node_name.lower(), hemi, lat),
                 ha="center", fontsize=10, color="#444444")
        fig.text(0.5, 0.906,
                 "Set the path-arc overlay to the longitude at the listed UTC "
                 "time, then step forward one orbit per pass.",
                 ha="center", fontsize=9, color="#666666")

        # table
        col_x = [0.10, 0.34, 0.55, 0.78]
        headers = ["UTC date", "%s UTC" % node_name, "Sub-longitude", "Notes"]
        y0 = 0.872
        dy = 0.0258
        for x, h in zip(col_x, headers):
            fig.text(x, y0, h, fontsize=10, fontweight="bold",
                     color="#222222")
        fig.add_artist(plt.Line2D([0.09, 0.93], [y0 - 0.006, y0 - 0.006],
                                  color="#999999", lw=1.0,
                                  transform=fig.transFigure))
        for i, r in enumerate(chunk):
            y = y0 - (i + 1) * dy
            iso = r["date"].isoformat()
            fig.text(col_x[0], y, iso, fontsize=9.5, color="#111111",
                     family="monospace")
            if r["t"] is not None:
                hhmm = dt.datetime.fromtimestamp(
                    r["t"], dt.timezone.utc).strftime("%H:%M:%S")
                fig.text(col_x[1], y, hhmm, fontsize=9.5, color="#111111",
                         family="monospace")
                fig.text(col_x[2], y, _lon_str(r["lon"]), fontsize=9.5,
                         color="#b35900", family="monospace")
            else:
                fig.text(col_x[1], y, "\u2014", fontsize=9.5, color="#999999")
                fig.text(col_x[2], y, "\u2014", fontsize=9.5, color="#999999")
            if i % 2 == 1:
                fig.add_artist(plt.Rectangle(
                    (0.09, y - 0.007), 0.84, dy, color="#f2f2f2", zorder=-5,
                    transform=fig.transFigure))

        from .. import __version__
        fig.text(0.5, 0.045,
                 "OrbitDeck v%s \u2022 Paul Stoetzer, N8HM" % __version__,
                 ha="center", va="bottom", fontsize=6.5, color="#9a9a9a")
        pdf.savefig(fig)
        plt.close(fig)


def generate_reference_orbits_pdf(path, store, sats, days=60,
                                  start_unix=None):
    """Write a reference-orbits PDF for one or more satellites.

    ``sats`` is a satellite or a list of satellites; each gets its own page(s).
    ``days`` defaults to 60. The reference orbit per UTC day is the first
    ascending crossing for northern stations, first descending for southern.
    """
    global PAGE_W_IN, PAGE_H_IN
    from .pagesize import page_dims
    PAGE_W_IN, PAGE_H_IN = page_dims(store)
    import time
    if start_unix is None:
        start_unix = time.time()
    if not isinstance(sats, (list, tuple)):
        sats = [sats]
    with PdfPages(path) as pdf:
        for sat in sats:
            _sat_pages(pdf, store, sat, days, start_unix)
    return path
