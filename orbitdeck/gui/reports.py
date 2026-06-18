"""reports.py - generate clean, printable PDF reports for a satellite.

Produces a multi-section report covering orbital analysis, the next passes from
the user's station, and the equator-crossing (EQX) schedule. Output is a vector
PDF laid out with matplotlib's PdfPages so it prints cleanly on Letter paper.

The report intentionally reuses the same engine functions the on-screen pages
use, so the printed figures match what the app shows.
"""

import math
import time
import datetime as _dt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from ..engine.predict import Predictor
from ..engine import analysis as A

PAGE_W_IN = 8.5
PAGE_H_IN = 11.0

C_TITLE = "#0b3d91"
C_HEAD = "#0b3d91"
C_TEXT = "#111111"
C_MUTED = "#555555"
C_RULE = "#0b3d91"
C_ROWALT = "#eef2fa"


def _utc(unix, fmt="%Y-%m-%d %H:%M:%S"):
    return _dt.datetime.fromtimestamp(unix, _dt.timezone.utc).strftime(fmt)


def _draw_sky_polar(ax, pred, p, n=80):
    """Draw a single pass as a sky-track polar plot on the given polar axes,
    matching the on-screen Pass Detail view: N-up, clockwise, radius 90deg
    (zenith) at centre to 0deg (horizon) at the rim, AOS = green circle,
    LOS = orange square."""
    azs, els = [], []
    for i in range(n + 1):
        tt = p.aos + (p.los - p.aos) * i / n
        a, e = pred.azel_at(tt)
        azs.append(math.radians(a))
        els.append(max(e, 0.0))
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(90, 0)
    ax.set_rgrids([0, 30, 60, 90], labels=["0", "30", "60", "90"],
                  color="#888888", fontsize=6)
    ax.set_thetagrids(range(0, 360, 45),
                      labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                      color="#444444", fontsize=7)
    ax.grid(True, color="#cccccc", linewidth=0.6)
    ax.plot(azs, els, color="#2f81f7", linewidth=2.0)
    ax.plot([azs[0]], [0], "o", color="#3fb950", markersize=6)
    ax.plot([azs[-1]], [0], "s", color="#d29922", markersize=6)


class _Page:
    """A simple top-down text/table layout helper over a matplotlib figure.

    Coordinates are in figure fraction; y starts near the top and descends as
    content is added. When the cursor runs off the bottom, ``ensure`` starts a
    fresh page."""

    def __init__(self, pdf, header):
        self.pdf = pdf
        self.header = header
        self.fig = None
        self.y = 0.0
        self._new_page()

    def _new_page(self):
        if self.fig is not None:
            self.pdf.savefig(self.fig)
            plt.close(self.fig)
        self.fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        self.y = 0.93
        # running header
        self.fig.text(0.07, 0.965, self.header, fontsize=9, color=C_MUTED,
                      va="center")
        self.fig.text(0.93, 0.965, "OrbitDeck", fontsize=9, color=C_MUTED,
                      ha="right", va="center")
        self.fig.add_artist(plt.Line2D([0.07, 0.93], [0.955, 0.955],
                                       color=C_RULE, linewidth=1.0))

    def ensure(self, need=0.06):
        if self.y - need < 0.06:
            self._new_page()

    def title(self, text):
        self.ensure(0.08)
        self.fig.text(0.07, self.y, text, fontsize=20, color=C_TITLE,
                      fontweight="bold", va="top")
        self.y -= 0.045

    def subtitle(self, text):
        self.fig.text(0.07, self.y, text, fontsize=10, color=C_MUTED, va="top")
        self.y -= 0.035

    def section(self, text):
        self.ensure(0.08)
        self.y -= 0.02
        self.fig.text(0.07, self.y, text, fontsize=13, color=C_HEAD,
                      fontweight="bold", va="top")
        self.y -= 0.024
        self.fig.add_artist(plt.Line2D([0.07, 0.93], [self.y, self.y],
                                       color="#cccccc", linewidth=0.8))
        self.y -= 0.014

    def kv_two_col(self, pairs):
        """Render key/value pairs in two columns to save vertical space."""
        col_x = (0.07, 0.52)
        val_x = (0.30, 0.75)
        i = 0
        while i < len(pairs):
            self.ensure(0.03)
            for c in (0, 1):
                if i + c < len(pairs):
                    k, v = pairs[i + c]
                    self.fig.text(col_x[c], self.y, k, fontsize=9.5,
                                  color=C_MUTED, va="top")
                    self.fig.text(val_x[c], self.y, str(v), fontsize=9.5,
                                  color=C_TEXT, va="top", fontweight="bold")
            self.y -= 0.026
            i += 2

    def table(self, headers, rows, col_x, aligns=None):
        """A simple table with a header row and zebra striping."""
        aligns = aligns or (["left"] * len(headers))
        self.ensure(0.06)
        self.y -= 0.008                      # gap below the section heading

        def _draw_header():
            self.fig.add_artist(plt.Rectangle(
                (0.07, self.y - 0.020), 0.86, 0.024, color=C_HEAD,
                zorder=-1, transform=self.fig.transFigure))
            for h, x, al in zip(headers, col_x, aligns):
                self.fig.text(x, self.y - 0.015, h, fontsize=9.5,
                              color="white", fontweight="bold", va="baseline",
                              ha=al)
            self.y -= 0.030

        _draw_header()
        # rows
        row_h = 0.022
        for r, row in enumerate(rows):
            self.ensure(0.026)
            if self.y <= 0.07:
                _draw_header()
            if r % 2 == 1:
                # the cell text is drawn with va="top" at self.y, so it occupies
                # the band from roughly (self.y - row_h + a little) up to self.y.
                # Shade exactly that band so the stripe lines up with the text.
                self.fig.add_artist(plt.Rectangle(
                    (0.07, self.y - row_h + 0.006), 0.86, row_h, color=C_ROWALT,
                    zorder=-2, transform=self.fig.transFigure))
            for cell, x, al in zip(row, col_x, aligns):
                self.fig.text(x, self.y, str(cell), fontsize=9, color=C_TEXT,
                              va="top", ha=al)
            self.y -= row_h

    def paragraph(self, text, color=C_TEXT, size=9.5):
        self.ensure(0.03)
        self.fig.text(0.07, self.y, text, fontsize=size, color=color, va="top",
                      wrap=True)
        self.y -= 0.026

    def finish(self):
        if self.fig is not None:
            self.pdf.savefig(self.fig)
            plt.close(self.fig)
            self.fig = None


def _orbital_analysis_pairs(sat, obs, now):
    """Build the orbital-analysis key/value list, mirroring the on-screen pages."""
    mm = sat.mean_motion
    a_km = A.semi_major_axis_km(mm)
    per = A.period_min(mm)
    alt = a_km - 6378.137
    node_dpd, argp_dpd = A.j2_rates(mm, sat.incl, sat.ecc)
    foot_km = A.footprint_diameter_km(max(alt, 1.0))
    pairs = [
        ("Catalog #", sat.norad),
        ("Int'l designator", sat.intl_des or "\u2014"),
        ("Inclination", "%.4f\u00b0" % sat.incl),
        ("Eccentricity", "%.7f" % sat.ecc),
        ("Mean motion", "%.8f rev/day" % mm),
        ("Period", "%.2f min" % per),
        ("Semi-major axis", "%.1f km" % a_km),
        ("Mean altitude", "%.1f km" % alt),
        ("RAAN", "%.4f\u00b0" % sat.raan),
        ("Arg. of perigee", "%.4f\u00b0" % sat.argp),
        ("Footprint diameter", "%.0f km" % foot_km),
        ("Node regression", "%.4f\u00b0/day" % node_dpd),
        ("Perigee precession", "%.4f\u00b0/day" % argp_dpd),
        ("Sun-synchronous", "yes" if A.is_sun_synchronous(node_dpd) else "no"),
        ("Element epoch", _utc(sat.epoch_unix)),
        ("Element age", "%.2f days" % ((now - sat.epoch_unix) / 86400.0)),
    ]
    try:
        rev_days, rev_orbits = A.repeat_ground_track(mm)
        if rev_days:
            pairs.append(("Repeat ground track",
                          "%d orbits / %d days" % (rev_orbits, rev_days)))
    except Exception:
        pass
    try:
        longest = A.longest_possible_pass_min(mm, sat.ecc)
        pairs.append(("Longest possible pass", "%.1f min" % longest))
    except Exception:
        pass
    try:
        decay = A.estimate_decay_days(sat.bstar, mm, sat.ecc)
        pairs.append(("Est. orbital lifetime", A.fmt_decay(decay)))
    except Exception:
        pass
    return pairs


def generate_satellite_report(path, store, sat, when_unix=None,
                              sections=("analysis", "passes", "eqx",
                                        "polar", "illum", "progression"),
                              days=7, max_passes=20):
    """Write a printable PDF report for ``sat`` from the station in ``store``.

    ``sections`` selects which parts to include:
      'analysis'    - orbital analysis key/values
      'passes'      - next passes table from the QTH
      'eqx'         - equator-crossing schedule
      'polar'       - sky-track polar plots for the next 3 days
      'illum'       - 60-day illumination raster
      'progression' - 30-day pass-progression timeline
    """
    if when_unix is None:
        when_unix = time.time()
    obs = store.obs
    pred = Predictor()
    pred.set_site(obs)
    pred.set_sat(sat)

    header = "%s  \u2014  satellite report  \u2014  generated %s UTC" % (
        sat.name, _utc(when_unix, "%Y-%m-%d %H:%M"))
    with PdfPages(path) as pdf:
        pg = _Page(pdf, header)
        pg.title(sat.name)
        pg.subtitle(
            "OrbitDeck report \u2014 station %s (%.3f, %.3f) \u2014 %s UTC"
            % (store.my_grid(), obs.lat, obs.lon, _utc(when_unix)))

        if "analysis" in sections:
            pg.section("Orbital analysis")
            pg.kv_two_col(_orbital_analysis_pairs(sat, obs, when_unix))

        if "passes" in sections:
            pg.section("Next passes (min elevation %d\u00b0, next %d days)"
                       % (int(store.min_el), days))
            passes = pred.predict_passes(when_unix, store.min_el, max_passes,
                                         when_unix + days * 86400)
            if passes:
                rows = []
                for p in passes:
                    dur = (p.los - p.aos) / 60.0
                    rows.append((
                        _utc(p.aos, "%m-%d"),
                        _utc(p.aos, "%H:%M:%S"),
                        "%.0f\u00b0" % p.az_aos,
                        _utc(p.tca, "%H:%M:%S"),
                        "%.0f\u00b0" % p.max_el,
                        _utc(p.los, "%H:%M:%S"),
                        "%.0f\u00b0" % p.az_los,
                        "%.1f min" % dur,
                    ))
                pg.table(
                    ["Date", "AOS", "Az", "TCA", "Max el", "LOS", "Az",
                     "Dur"],
                    rows,
                    col_x=(0.07, 0.17, 0.29, 0.37, 0.49, 0.59, 0.71, 0.83))
            else:
                pg.paragraph("No passes above the minimum elevation in this "
                             "window.", color=C_MUTED)

        if "eqx" in sections:
            south = obs.lat < 0
            kind = "descending" if south else "ascending"
            pg.section("Equator crossings \u2014 %s node (next %d days)"
                       % (kind, days))
            nodes = (pred.descending_nodes(when_unix, when_unix + days * 86400)
                     if south else
                     pred.ascending_nodes(when_unix, when_unix + days * 86400))
            if nodes:
                rows = []
                for n, (tc, lon) in enumerate(nodes, start=1):
                    hemi = "E" if lon >= 0 else "W"
                    rows.append((n, _utc(tc, "%Y-%m-%d"), _utc(tc, "%H:%M:%S"),
                                 "%.1f\u00b0 %s" % (abs(lon), hemi)))
                pg.table(["#", "Date (UTC)", "Time (UTC)", "Longitude"], rows,
                         col_x=(0.07, 0.22, 0.45, 0.68))
            else:
                pg.paragraph("No equator crossings found.", color=C_MUTED)

        pg.finish()        # flush the text-flow pages before any graphic pages

        # graphic sections, each on their own page(s)
        if "polar" in sections:
            polar_passes = pred.predict_passes(when_unix, store.min_el, 400,
                                               when_unix + 3 * 86400)
            if polar_passes:
                _pass_polar_grid(
                    pdf, pred, sat, polar_passes,
                    "%s \u2014 pass sky tracks" % sat.name,
                    "Next 3 days \u2014 min elevation %g\u00b0 \u2014 %d passes. "
                    "Green \u25cf AOS, orange \u25a0 LOS; centre = zenith."
                    % (store.min_el, len(polar_passes)))

        if "illum" in sections:
            _illumination_pages(pdf, pred, sat, when_unix, days=60)

        if "progression" in sections:
            prog_days = 30
            prog_passes = pred.predict_passes(when_unix, store.min_el, 4000,
                                              when_unix + prog_days * 86400)
            start_day = _dt.datetime.fromtimestamp(
                when_unix, _dt.timezone.utc).date()
            by_day = {}
            for p in prog_passes:
                di = (_dt.datetime.fromtimestamp(
                    p.aos, _dt.timezone.utc).date() - start_day).days
                by_day.setdefault(di, []).append(p)
            _progression_chart_pages(pdf, store, sat, when_unix, prog_days,
                                     prog_passes, by_day, start_day,
                                     include_table=False)

        d = pdf.infodict()
        d["Title"] = "OrbitDeck report \u2014 %s" % sat.name
        d["Subject"] = "Orbital analysis, passes, EQX, sky tracks, illumination"
        d["Creator"] = "OrbitDeck"
    return path


def _favorite_sats(store):
    """Resolve the favorite NORAD ids to SatEntry objects present in the
    catalog, sorted by name."""
    sats = [store.db.get(n) for n in store.favorites]
    sats = [s for s in sats if s is not None]
    sats.sort(key=lambda s: s.name)
    return sats


def generate_favorites_passes_report(path, store, when_unix=None, days=7,
                                     max_per_sat=200):
    """A single time-ordered schedule of upcoming passes across all favorite
    satellites over the next ``days`` days, using the station and minimum
    elevation from ``store``. Every favorite's passes are merged and sorted by
    AOS so the report reads as a chronological timeline."""
    if when_unix is None:
        when_unix = time.time()
    obs = store.obs
    sats = _favorite_sats(store)
    header = "Favorites pass schedule \u2014 generated %s UTC" % _utc(
        when_unix, "%Y-%m-%d %H:%M")
    with PdfPages(path) as pdf:
        pg = _Page(pdf, header)
        pg.title("Favorite satellites \u2014 pass schedule")
        pg.subtitle("Station %s (%.3f, %.3f) \u2014 next %d days \u2014 min "
                    "elevation %g\u00b0 \u2014 all favorites, in time order"
                    % (store.my_grid(), obs.lat, obs.lon, days, store.min_el))
        if not sats:
            pg.paragraph("No favorite satellites. Mark some with the star on "
                         "the Satellites screen.", color=C_MUTED)
            pg.finish()
            return path

        # gather every favorite's passes, tagged with the satellite name, then
        # sort the whole set by AOS
        events = []
        for s in sats:
            pred = Predictor()
            pred.set_site(obs)
            pred.set_sat(s)
            for p in pred.predict_passes(when_unix, store.min_el, max_per_sat,
                                         when_unix + days * 86400):
                events.append((p.aos, s.name, p))
        events.sort(key=lambda e: e[0])

        pg.section("Upcoming passes (%d) \u2014 chronological" % len(events))
        if not events:
            pg.paragraph("No passes above %g\u00b0 for any favorite in this "
                         "window." % store.min_el, color=C_MUTED)
        else:
            rows = []
            for _aos, name, p in events:
                rows.append((
                    _utc(p.aos, "%a %m-%d"),
                    _utc(p.aos, "%H:%M:%S"),
                    name,
                    "%.0f\u00b0" % p.az_aos,
                    "%.0f\u00b0" % p.max_el,
                    _utc(p.los, "%H:%M:%S"),
                    "%.1f min" % ((p.los - p.aos) / 60.0),
                ))
            pg.table(["Day", "AOS", "Satellite", "Az", "Max el", "LOS", "Dur"],
                     rows,
                     col_x=(0.07, 0.17, 0.29, 0.50, 0.60, 0.72, 0.93),
                     aligns=["left", "left", "left", "right", "right", "left",
                             "right"])
        pg.finish()
        d = pdf.infodict()
        d["Title"] = "OrbitDeck \u2014 favorites pass schedule"
        d["Creator"] = "OrbitDeck"
    return path


def generate_site_comparison_report(path, store, sat, entries, days):
    """A per-site comparison of one satellite's upcoming passes across the
    primary site and all secondary sites."""
    when_unix = time.time()
    obs = store.obs
    header = "Site comparison \u2014 generated %s UTC" % _utc(
        when_unix, "%Y-%m-%d %H:%M")
    with PdfPages(path) as pdf:
        pg = _Page(pdf, header)
        pg.title("%s \u2014 passes by site" % sat.name)
        pg.subtitle("Primary %s (%.3f, %.3f) + %d secondary site(s) \u2014 next "
                    "%d day(s) \u2014 min elevation %g\u00b0"
                    % (store.obs_name, obs.lat, obs.lon, len(store.sites),
                       days, store.min_el))
        pg.section("Per-site summary")
        rows = []
        for e in entries:
            nxt = e.get("next_pass")
            best = e.get("best_pass")
            rows.append((
                e["name"],
                str(e.get("n_passes", 0)),
                _utc(nxt.aos, "%m-%d %H:%M") if nxt and nxt.aos else "\u2014",
                "%.0f\u00b0" % nxt.max_el if nxt and nxt.aos else "\u2014",
                "%.0f\u00b0" % best.max_el if best and best.aos else "\u2014",
            ))
        pg.table(["Site", "Passes", "Next AOS", "Next max el", "Best max el"],
                 rows, col_x=(0.07, 0.34, 0.50, 0.72, 0.93),
                 aligns=["left", "right", "left", "right", "right"])
        pg.paragraph("The primary site drives every other screen; secondary "
                     "sites are compared here only.", color=C_MUTED)
        pg.finish()
        d = pdf.infodict()
        d["Title"] = "OrbitDeck \u2014 site comparison"
        d["Creator"] = "OrbitDeck"
    return path


def generate_mutual_passes_report(path, store, sat, dx, when_unix=None,
                                  days=10, min_el=0.0, max_n=60):
    """Mutual (co-visibility) windows between the user's station and a DX station
    ``dx`` (an Observer) for ``sat``."""
    if when_unix is None:
        when_unix = time.time()
    obs = store.obs
    pred = Predictor()
    pred.set_site(obs)
    pred.set_sat(sat)
    wins = pred.mutual_windows(when_unix, dx, min_el, max_n, days)
    header = "%s \u2014 mutual windows \u2014 generated %s UTC" % (
        sat.name, _utc(when_unix, "%Y-%m-%d %H:%M"))
    with PdfPages(path) as pdf:
        pg = _Page(pdf, header)
        pg.title("%s \u2014 mutual windows" % sat.name)
        pg.subtitle("Between %s (%.3f, %.3f) and DX (%.3f, %.3f) \u2014 next %d "
                    "days \u2014 min elevation %g\u00b0"
                    % (store.my_grid(), obs.lat, obs.lon, dx.lat, dx.lon,
                       days, min_el))
        pg.section("Co-visibility windows")
        if not wins:
            pg.paragraph("No mutual windows in this period.", color=C_MUTED)
        else:
            rows = []
            for w in wins:
                rows.append((
                    _utc(w.start, "%a %m-%d"),
                    _utc(w.start, "%H:%M:%S"),
                    _utc(w.end, "%H:%M:%S"),
                    "%.1f min" % ((w.end - w.start) / 60.0),
                    "%.0f\u00b0" % w.my_max_el,
                    "%.0f\u00b0" % w.dx_max_el,
                ))
            pg.table(["Day", "Start", "End", "Dur", "My max el", "DX max el"],
                     rows, col_x=(0.07, 0.22, 0.36, 0.50, 0.64, 0.80))
        pg.finish()
        # per-window comparison polar plots (both stations side by side)
        if wins:
            _mutual_polar_pages(pdf, store, sat, dx, wins, max_windows=12)
        d = pdf.infodict()
        d["Title"] = "OrbitDeck \u2014 mutual windows \u2014 %s" % sat.name
        d["Creator"] = "OrbitDeck"
    return path


def _illumination_pages(pdf, pred, sat, when_unix, days=60):
    """Draw the illumination raster page(s) into an open PdfPages."""
    import numpy as np
    period_min = A.period_min(sat.mean_motion) or 95.0
    per_s = period_min * 60.0
    rows = 96                                  # matches the on-screen PHASE_ROWS
    grid = np.zeros((rows, days))
    for d in range(days):
        t0 = when_unix + d * 86400
        for r in range(rows):
            tt = t0 + (r / rows) * per_s
            grid[r, d] = 1.0 if pred.sunlit_at(tt) else 0.0
    day_frac_lit = grid.mean(axis=0)
    mean_lit = float(grid.mean())

    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    fig.text(0.07, 0.95, "%s \u2014 illumination" % sat.name,
             fontsize=20, color=C_TITLE, fontweight="bold", va="top")
    fig.text(0.07, 0.915,
             "Bright = sunlit, dark = eclipse. Day vs minutes into one "
             "orbit, over %d days from %s UTC."
             % (days, _utc(when_unix, "%Y-%m-%d")),
             fontsize=10, color=C_MUTED, va="top")
    ax = fig.add_axes([0.10, 0.40, 0.83, 0.45])
    ax.imshow(grid, aspect="auto", origin="lower",
              extent=[0, days, 0, period_min], cmap="cividis",
              interpolation="nearest", vmin=0, vmax=1)
    ax.set_xlabel("Days from start")
    ax.set_ylabel("Minutes into orbit (one period)")
    ax2 = fig.add_axes([0.10, 0.24, 0.83, 0.10])
    ax2.bar(range(days), [(1 - f) * 100 for f in day_frac_lit],
            color="#26416b", width=0.9)
    ax2.set_ylim(0, 100)
    ax2.set_xlim(-0.5, days - 0.5)
    ax2.set_ylabel("Eclipse\n% / orbit", fontsize=8)
    ax2.set_xlabel("Days from start")
    ax2.grid(True, axis="y", color="#dddddd", linewidth=0.5)
    fig.text(0.07, 0.17,
             "Mean sunlit fraction: %.1f%%   \u2014   mean eclipse fraction: "
             "%.1f%% per orbit" % (mean_lit * 100, (1 - mean_lit) * 100),
             fontsize=11, color=C_TEXT, va="top", fontweight="bold")
    fig.text(0.07, 0.13,
             "Solid bright bands are full-sun seasons (no eclipse); a dark "
             "band each orbit is the eclipse \u2014 its height shows how long "
             "the satellite is in shadow. Useful for power budgeting.",
             fontsize=9.5, color=C_MUTED, va="top", wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def generate_illumination_report(path, store, sat, when_unix=None, days=60):
    """A 60-day (default) illumination chart matching the on-screen Illumination
    display: a 2D raster with day on the X axis and minutes-into-orbit (one
    period) on the Y axis, bright = sunlit, dark = eclipse."""
    if when_unix is None:
        when_unix = time.time()
    pred = Predictor()
    pred.set_site(store.obs)
    pred.set_sat(sat)
    with PdfPages(path) as pdf:
        _illumination_pages(pdf, pred, sat, when_unix, days)
        d = pdf.infodict()
        d["Title"] = "OrbitDeck \u2014 illumination \u2014 %s" % sat.name
        d["Creator"] = "OrbitDeck"
    return path


def generate_eclipse_report(path, store, sat, periods=None, summary=None,
                            when_unix=None, days=7):
    """Printable eclipse ephemeris for ``sat``: an orbit-by-orbit umbral-eclipse
    table (enter / exit / duration / interval / sun angle) followed by a daily
    summary (total, longest, percent of day, sun angle). Mirrors the on-screen
    Eclipse table. If ``periods`` / ``summary`` are not supplied they are
    computed here so the report can be generated independently."""
    if when_unix is None:
        when_unix = time.time()
    obs = store.obs
    pred = Predictor()
    pred.set_site(obs)
    pred.set_sat(sat)
    if periods is None:
        periods = pred.predict_eclipses(when_unix, max_n=10000,
                                        horizon_days=float(days))
    if summary is None:
        summary = pred.eclipse_daily_summary(when_unix, days=days)

    header = "%s  \u2014  eclipse ephemeris  \u2014  generated %s UTC" % (
        sat.name, _utc(when_unix, "%Y-%m-%d %H:%M"))
    with PdfPages(path) as pdf:
        pg = _Page(pdf, header)
        pg.title("%s \u2014 eclipses" % sat.name)
        pg.subtitle(
            "OrbitDeck report \u2014 umbral eclipse (Earth's shadow) \u2014 %s UTC"
            % _utc(when_unix))

        if not periods:
            pg.section("Every orbit")
            pg.paragraph("No eclipses in the next %d days \u2014 the satellite "
                         "is in continuous sunlight over this window." % days)
            pg.finish()
            d = pdf.infodict()
            d["Title"] = "OrbitDeck \u2014 eclipses \u2014 %s" % sat.name
            d["Creator"] = "OrbitDeck"
            return path

        # Every-orbit table
        pg.section("Every orbit")
        col_x = (0.07, 0.27, 0.47, 0.62, 0.82)
        aligns = ("left", "left", "right", "right", "right")
        heads = ["Enter (UTC)", "Exit (UTC)", "Duration",
                 "Interval", "Sun angle"]
        rows = []
        prev_exit = None
        total = 0.0
        for e in periods:
            intvl = _hms(e.enter - prev_exit) if prev_exit is not None else "\u2014"
            rows.append([
                _utc(e.enter, "%m-%d %H:%M:%S"),
                _utc(e.exit, "%m-%d %H:%M:%S"),
                _hms(e.duration_s), intvl, "%+.1f\u00b0" % e.sun_angle])
            prev_exit = e.exit
            total += e.duration_s
        pg.table(heads, rows, col_x, aligns)
        pg.paragraph("%d eclipses, total %s, mean %.1f min."
                     % (len(periods), _hms(total),
                        total / len(periods) / 60.0))

        # Daily summary table
        pg.section("Daily summary")
        col_x2 = (0.07, 0.30, 0.47, 0.64, 0.79, 0.90)
        aligns2 = ("left", "right", "right", "right", "right", "right")
        heads2 = ["Date", "Eclipses", "Total", "Longest", "% day", "Sun ang"]
        rows2 = []
        for r in summary:
            rows2.append([
                _utc(r["date"], "%Y-%m-%d"), str(r["count"]),
                _hms(r["total_s"]), _hms(r["longest_s"]),
                "%.1f%%" % r["percent"], "%+.1f\u00b0" % r["sun_angle"]])
        pg.table(heads2, rows2, col_x2, aligns2)
        pg.paragraph("Sun angle is the orbit-plane beta angle; high beta means "
                     "shallow, short eclipses (or none in continuous sunlight). "
                     "Useful for spacecraft power-budget planning.",
                     color=C_MUTED)
        pg.finish()
        d = pdf.infodict()
        d["Title"] = "OrbitDeck \u2014 eclipses \u2014 %s" % sat.name
        d["Creator"] = "OrbitDeck"
    return path


def _hms(seconds):
    """Format a duration in seconds as H:MM:SS for report tables."""
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s)


def _el_color(el):
    """Match the on-screen progression colours: low passes muted blue, mid
    blue, high passes bright green."""
    if el >= 45:
        return "#3fb950"        # COL_ACCENT2
    if el >= 20:
        return "#2f81f7"        # COL_ACCENT
    return "#3b5ba5"


def generate_progression_report(path, store, sat, when_unix=None, days=30):
    """Multi-day pass progression matching the on-screen display: one row per
    day, each a 24-hour UTC timeline with passes drawn as bars positioned by
    AOS->LOS and coloured by max elevation (green high, blue mid, dark-blue
    low). Paginated across days; a full pass table follows."""
    if when_unix is None:
        when_unix = time.time()
    obs = store.obs
    pred = Predictor()
    pred.set_site(obs)
    pred.set_sat(sat)
    passes = pred.predict_passes(when_unix, store.min_el, 4000,
                                 when_unix + days * 86400)

    # group passes by UTC calendar day index from the start day
    start_day = _dt.datetime.fromtimestamp(
        when_unix, _dt.timezone.utc).date()
    by_day = {}
    for p in passes:
        di = (_dt.datetime.fromtimestamp(p.aos, _dt.timezone.utc).date()
              - start_day).days
        by_day.setdefault(di, []).append(p)

    with PdfPages(path) as pdf:
        _progression_chart_pages(pdf, store, sat, when_unix, days, passes,
                                 by_day, start_day, include_table=True)
        d = pdf.infodict()
        d["Title"] = "OrbitDeck \u2014 pass progression \u2014 %s" % sat.name
        d["Creator"] = "OrbitDeck"
    return path


def _progression_chart_pages(pdf, store, sat, when_unix, days, passes, by_day,
                             start_day, include_table=True):
    """Draw the progression day-lane chart page(s) (and optionally the pass
    table) into an open PdfPages."""
    header = "%s \u2014 %d-day pass progression \u2014 generated %s UTC" % (
        sat.name, days, _utc(when_unix, "%Y-%m-%d %H:%M"))
    rows_per_page = 16
    page_starts = list(range(0, days, rows_per_page))
    for pi, d0 in enumerate(page_starts):
        d1 = min(d0 + rows_per_page, days)
        fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        if pi == 0:
            fig.text(0.07, 0.955, "%s \u2014 pass progression" % sat.name,
                     fontsize=20, color=C_TITLE, fontweight="bold",
                     va="top")
            fig.text(0.07, 0.918, "%d-day progression from %s UTC \u2014 min "
                     "elevation %g\u00b0 \u2014 %d passes. Each row is a UTC day; "
                     "bars are passes by time of day, coloured by max "
                     "elevation." % (days, _utc(when_unix, "%Y-%m-%d"),
                                     store.min_el, len(passes)),
                     fontsize=9.5, color=C_MUTED, va="top", wrap=True)
            top = 0.86
        else:
            fig.text(0.07, 0.955, "%s \u2014 pass progression (cont.)"
                     % sat.name, fontsize=14, color=C_TITLE,
                     fontweight="bold", va="top")
            top = 0.90
        ax = fig.add_axes([0.13, 0.07, 0.82, top - 0.07])
        n = d1 - d0
        for li, di in enumerate(range(d0, d1)):
            y = n - 1 - li                 # top day first
            day_date = start_day + _dt.timedelta(days=di)
            ax.axhspan(y - 0.42, y + 0.42, color="#f4f6fb", zorder=0)
            for hr in range(0, 25, 6):
                ax.plot([hr, hr], [y - 0.42, y + 0.42], color="#dddddd",
                        linewidth=0.5, zorder=1)
            for p in by_day.get(di, []):
                a = _dt.datetime.fromtimestamp(p.aos, _dt.timezone.utc)
                b = _dt.datetime.fromtimestamp(p.los, _dt.timezone.utc)
                h0 = a.hour + a.minute / 60.0 + a.second / 3600.0
                h1 = b.hour + b.minute / 60.0 + b.second / 3600.0
                if h1 < h0:
                    h1 = 24.0
                w = max(h1 - h0, 0.15)
                ax.barh(y, w, left=h0, height=0.6,
                        color=_el_color(p.max_el), zorder=2)
                if w > 1.4:
                    ax.text(h0 + w / 2, y, "%.0f\u00b0" % p.max_el,
                            ha="center", va="center", fontsize=6.5,
                            color="#0d1117", fontweight="bold", zorder=3)
            ax.text(-0.4, y, "%s %s" % (day_date.strftime("%a"),
                    day_date.strftime("%m-%d")), ha="right", va="center",
                    fontsize=8, color=C_TEXT)
        ax.set_xlim(0, 24)
        ax.set_ylim(-0.6, n - 0.4)
        ax.set_xticks(range(0, 25, 3))
        ax.set_xlabel("Time of day (UTC hour)")
        ax.set_yticks([])
        for sp in ("left", "right", "top"):
            ax.spines[sp].set_visible(False)
        if pi == 0:
            import matplotlib.patches as mpatches
            handles = [mpatches.Patch(color="#3fb950", label="\u2265 45\u00b0"),
                       mpatches.Patch(color="#2f81f7", label="20\u201345\u00b0"),
                       mpatches.Patch(color="#3b5ba5", label="< 20\u00b0")]
            ax.legend(handles=handles, loc="upper right", fontsize=7,
                      title="max el", title_fontsize=7, ncol=3,
                      framealpha=0.9)
        pdf.savefig(fig)
        plt.close(fig)

    if include_table:
        pg = _Page(pdf, header)
        pg.section("All passes (%d) over %d days" % (len(passes), days))
        if not passes:
            pg.paragraph("No passes above %g\u00b0 in this window."
                         % store.min_el, color=C_MUTED)
        else:
            rows = []
            for p in passes:
                rows.append((
                    _utc(p.aos, "%a %m-%d"),
                    _utc(p.aos, "%H:%M:%S"),
                    "%.0f\u00b0" % p.az_aos,
                    "%.0f\u00b0" % p.max_el,
                    _utc(p.los, "%H:%M:%S"),
                    "%.1f min" % ((p.los - p.aos) / 60.0),
                ))
            pg.table(["Day", "AOS", "Az", "Max el", "LOS", "Dur"], rows,
                     col_x=(0.07, 0.22, 0.36, 0.48, 0.62, 0.78))
        pg.finish()


def _pass_polar_grid(pdf, pred, sat, passes, title, subtitle, cols=3, rows=4):
    """Lay out the given passes as a grid of sky-track polar plots across one or
    more pages."""
    per_page = cols * rows
    n_pages = max(1, (len(passes) + per_page - 1) // per_page)
    idx = 0
    for pageno in range(n_pages):
        fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        if pageno == 0:
            fig.text(0.07, 0.955, title, fontsize=20, color=C_TITLE,
                     fontweight="bold", va="top")
            fig.text(0.07, 0.918, subtitle, fontsize=9.5, color=C_MUTED,
                     va="top", wrap=True)
            top = 0.88
        else:
            fig.text(0.07, 0.955, title + " (cont.)", fontsize=14,
                     color=C_TITLE, fontweight="bold", va="top")
            top = 0.92
        # grid of polar axes
        gap_x, gap_y = 0.04, 0.03
        cell_w = (0.86 - (cols - 1) * gap_x) / cols
        cell_h = (top - 0.06 - (rows - 1) * gap_y) / rows
        for r in range(rows):
            for c in range(cols):
                if idx >= len(passes):
                    break
                p = passes[idx]
                left = 0.07 + c * (cell_w + gap_x)
                bottom = top - cell_h - r * (cell_h + gap_y)
                # The polar theta-labels (N/S/E/W ...) sit just OUTSIDE the
                # circle on every side, so the plot must be inset within the
                # cell on all sides to leave room. We size the axes to the
                # central ~62% of the cell height and centre it horizontally,
                # then drop the caption into the clear strip at the very bottom.
                lbl = "%s  %s\nmax %.0f\u00b0  %s\u2192%s  %.1f min" % (
                    _utc(p.aos, "%a %m-%d"), _utc(p.aos, "%H:%M"),
                    p.max_el,
                    _compass(p.az_aos), _compass(p.az_los),
                    (p.los - p.aos) / 60.0)
                fig.text(left + cell_w / 2, bottom + cell_h * 0.005, lbl,
                         ha="center", va="bottom", fontsize=7.5,
                         color=C_TEXT)
                # square-ish axes, inset: bottom 22% reserved for caption + the
                # S label, top 10% for the N label
                ax_h = cell_h * 0.62
                ax_w = min(cell_w * 0.78, ax_h)        # keep the circle round
                ax_left = left + (cell_w - ax_w) / 2.0
                ax = fig.add_axes([ax_left, bottom + cell_h * 0.22,
                                   ax_w, ax_h],
                                  projection="polar")
                _draw_sky_polar(ax, pred, p)
                idx += 1
        pdf.savefig(fig)
        plt.close(fig)


def _draw_mutual_station_polar(ax, pred, w, n=120):
    """Draw a station's full pass containing mutual window ``w`` on polar axes,
    with the mutually-visible portion highlighted in orange. ``pred`` must be a
    Predictor for that station with the satellite already set."""
    # find the full-pass bounds (walk outward from the window while up)
    step = 10.0
    aos = w.start
    t = w.start
    while pred.azel_at(t)[1] >= 0 and t > w.start - 3600:
        aos = t
        t -= step
    los = w.end
    t = w.end
    while pred.azel_at(t)[1] >= 0 and t < w.end + 3600:
        los = t
        t += step
    azs, els, times = [], [], []
    for i in range(n + 1):
        tt = aos + (los - aos) * i / n
        a, e = pred.azel_at(tt)
        if e >= 0:
            azs.append(math.radians(a))
            els.append(e)
            times.append(tt)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rgrids([0, 30, 60, 90], labels=["0", "30", "60", "90"],
                  color="#888888", fontsize=6)
    ax.set_thetagrids(range(0, 360, 45),
                      labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                      color="#444444", fontsize=7)
    ax.set_rlim(90, 0)
    ax.grid(True, color="#cccccc", linewidth=0.6)
    if not azs:
        return
    # full pass muted grey
    ax.plot(azs, els, color="#999999", linewidth=1.6)
    # mutual portion bold orange
    maz = [a for a, tt in zip(azs, times) if w.start <= tt <= w.end]
    mel = [e for e, tt in zip(els, times) if w.start <= tt <= w.end]
    if maz:
        ax.plot(maz, mel, color="#d29922", linewidth=3.0, zorder=5)
    ax.plot([azs[0]], [els[0]], "o", color="#2f81f7", markersize=6, zorder=6)
    ax.plot([azs[-1]], [els[-1]], "s", color="#2f81f7", markersize=6, zorder=6)


def _mutual_polar_pages(pdf, store, sat, dx, wins, max_windows=12):
    """One row per mutual window: the pass from the user's station (left) and
    the DX station (right), with the mutual portion highlighted on each."""
    my = Predictor()
    my.set_site(store.obs)
    my.set_sat(sat)
    dx_pred = Predictor()
    dx_pred.set_site(dx)
    dx_pred.set_sat(sat)
    my_name = getattr(store, "obs_name", "My station")
    sel = wins[:max_windows]
    rows_per_page = 3
    n_pages = max(1, (len(sel) + rows_per_page - 1) // rows_per_page)
    idx = 0
    for pageno in range(n_pages):
        fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        title = ("%s \u2014 mutual passes by station" % sat.name
                 if pageno == 0 else
                 "%s \u2014 mutual passes (cont.)" % sat.name)
        fig.text(0.07, 0.955, title, fontsize=16, color=C_TITLE,
                 fontweight="bold", va="top")
        if pageno == 0:
            fig.text(0.07, 0.925,
                     "Left: %s.  Right: DX (%.3f, %.3f).  Grey = full pass; "
                     "orange = mutually-visible portion.  \u25cb AOS  \u25a1 LOS"
                     % (my_name, dx.lat, dx.lon),
                     fontsize=9, color=C_MUTED, va="top", wrap=True)
        top = 0.89 if pageno == 0 else 0.93
        row_h = (top - 0.06) / rows_per_page
        for r in range(rows_per_page):
            if idx >= len(sel):
                break
            w = sel[idx]
            bottom = top - row_h - r * row_h
            # caption strip for this window
            cap = ("%s  %s\u2013%s UTC   mutual %.1f min   "
                   "my el %.0f\u00b0 / DX el %.0f\u00b0"
                   % (_utc(w.start, "%a %m-%d"), _utc(w.start, "%H:%M:%S"),
                      _utc(w.end, "%H:%M:%S"), (w.end - w.start) / 60.0,
                      w.my_max_el, w.dx_max_el))
            fig.text(0.5, bottom + row_h - 0.012, cap, ha="center", va="top",
                     fontsize=8.5, color=C_TEXT, fontweight="bold")
            ax_h = row_h * 0.74
            ax_w = ax_h * (PAGE_H_IN / PAGE_W_IN)   # keep circles round
            ax_bottom = bottom + row_h * 0.10
            # left = my station, right = DX
            axL = fig.add_axes([0.32 - ax_w, ax_bottom, ax_w, ax_h],
                               projection="polar")
            _draw_mutual_station_polar(axL, my, w)
            fig.text(0.32 - ax_w / 2, ax_bottom - 0.005, my_name,
                     ha="center", va="top", fontsize=7.5, color=C_MUTED)
            axR = fig.add_axes([0.68, ax_bottom, ax_w, ax_h],
                               projection="polar")
            _draw_mutual_station_polar(axR, dx_pred, w)
            fig.text(0.68 + ax_w / 2, ax_bottom - 0.005,
                     "DX %.2f,%.2f" % (dx.lat, dx.lon),
                     ha="center", va="top", fontsize=7.5, color=C_MUTED)
            idx += 1
        pdf.savefig(fig)
        plt.close(fig)


def _compass(az):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[int((az % 360) / 45.0 + 0.5) % 8]


def generate_polar_passes_report(path, store, sat, when_unix=None, days=3):
    """A grid of sky-track polar plots for every pass of ``sat`` over the next
    ``days`` days (default 3), matching the on-screen Pass Detail sky track:
    N-up, zenith at centre, AOS green circle, LOS orange square."""
    if when_unix is None:
        when_unix = time.time()
    obs = store.obs
    pred = Predictor()
    pred.set_site(obs)
    pred.set_sat(sat)
    passes = pred.predict_passes(when_unix, store.min_el, 400,
                                 when_unix + days * 86400)
    title = "%s \u2014 pass sky tracks" % sat.name
    subtitle = ("Station %s (%.3f, %.3f) \u2014 next %d days \u2014 min elevation "
                "%g\u00b0 \u2014 %d passes. Green \u25cf AOS, orange \u25a0 LOS; centre = "
                "zenith." % (store.my_grid(), obs.lat, obs.lon, days,
                             store.min_el, len(passes)))
    with PdfPages(path) as pdf:
        if not passes:
            fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
            fig.text(0.07, 0.95, title, fontsize=20, color=C_TITLE,
                     fontweight="bold", va="top")
            fig.text(0.07, 0.90, "No passes above %g\u00b0 in the next %d days."
                     % (store.min_el, days), fontsize=11, color=C_MUTED,
                     va="top")
            pdf.savefig(fig)
            plt.close(fig)
        else:
            _pass_polar_grid(pdf, pred, sat, passes, title, subtitle)
        d = pdf.infodict()
        d["Title"] = "OrbitDeck \u2014 pass sky tracks \u2014 %s" % sat.name
        d["Creator"] = "OrbitDeck"
    return path
