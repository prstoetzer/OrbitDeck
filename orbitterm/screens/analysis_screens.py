"""orbitterm/screens/analysis_screens.py - orbital analysis and ground track."""

import time
import math

from ..ui import Screen, addstr, cp, ljust, clip
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_OK, CLR_WARN, CLR_BAD, CLR_DIM,
                  CLR_ACCENT)
from .. import fmt
from orbitdeck.engine import analysis as an


def _sma_km(sat):
    """Semi-major axis from mean motion (km)."""
    mm = getattr(sat, "mean_motion", 0.0) or 0.0
    if mm <= 0:
        return 0.0
    n = mm * 2.0 * math.pi / 86400.0
    return (398600.4418 / (n * n)) ** (1.0 / 3.0)


def _eclipse_depth(pred, sat, now):
    """How deep into shadow the satellite is, as a fraction of the eclipse.

    0% means it is just entering or leaving; 100% is mid-eclipse. Shown as
    "in sunlight" when it is lit.
    """
    try:
        if pred.sunlit_at(now):
            return "in sunlight"
        period = 86400.0 / (getattr(sat, "mean_motion", 0) or 15.0)
        # walk out to each terminator, then report the position between them
        back = 0.0
        while back < period and not pred.sunlit_at(now - back):
            back += 30.0
        fwd = 0.0
        while fwd < period and not pred.sunlit_at(now + fwd):
            fwd += 30.0
        span = back + fwd
        if span <= 0:
            return "--"
        frac = min(back, fwd) / (span / 2.0)
        return "%.0f%% of the way in" % (frac * 100.0)
    except Exception:
        return "--"


def _rows(win, y0, x0, h, w, heading, rows):
    """Label/value rows, clipped to the pane so nothing is lost at 80 cols."""
    addstr(win, y0, x0, heading, cp(CLR_HEADER) | _bold())
    y = y0 + 1
    for lab, val in rows:
        if y >= y0 + h:
            break
        addstr(win, y, x0, ljust(lab, 18), cp(CLR_DIM))
        addstr(win, y, x0 + 19, clip(str(val), max(1, w - 19)))
        y += 1


class OrbitalAnalysisScreen(Screen):
    title = "Orbital Analysis"
    refresh_secs = 2.0

    # The desktop screen shows ~70 fields across sections; a single flat page
    # could only carry 18 of them. Paging brings the terminal to the same
    # information rather than making the operator open the desktop app.
    PAGES = ["elements", "live", "pass", "stats", "anomaly", "identity"]

    def __init__(self, app):
        super().__init__(app)
        self.page = 0

    def handle_key(self, ch):
        if ch in (ord("p"), ord("\t")):
            self.page = (self.page + 1) % len(self.PAGES)
            return True
        if ch == ord("P"):
            self.page = (self.page - 1) % len(self.PAGES)
            return True
        # keep the original satellite cycling - paging must not cost it
        if ch in (ord("["), ord("]")):
            self.app.cycle_sat(-1 if ch == ord("[") else 1)
            return True
        return False

    def help_keys(self):
        return [("p", "page (%s)" % self.PAGES[self.page]),
                ("[ ]", "prev/next sat")]

    def _draw_live(self, win, y0, x0, h, w, st, sat, pred, now):
        """Where it is right now - the desktop's live section."""
        L = pred.look(now)
        lat, lon, alt = pred.subpoint_at(now)
        rows = [
            ("Azimuth", fmt.fmt_az(L.az)),
            ("Elevation", fmt.fmt_el(L.el)),
            ("Range", "%.0f km" % L.range_km),
            ("Range rate", "%+.3f km/s" % L.range_rate),
            ("Altitude", "%.1f km" % alt),
            ("Sub-point", fmt.fmt_latlon(lat, lon)),
            ("Doppler 145.8", "%+.0f Hz" % (-145.8e6 * L.range_rate / 299792.458)),
            ("Doppler 435", "%+.0f Hz" % (-435.0e6 * L.range_rate / 299792.458)),
            ("Path delay", "%.1f ms" % (L.range_km / 299.792458)),
            ("Sunlit", "yes" if getattr(L, "sunlit", False) else "no"),
            ("Eclipse depth", _eclipse_depth(pred, sat, now)),
            ("Velocity", "%.3f km/s" % an.orbital_velocity_kms(
                an.semi_major_axis_km(sat.mean_motion),
                an.semi_major_axis_km(sat.mean_motion))),
        ]
        _rows(win, y0, x0, h, w, "Live geometry", rows)

    def _draw_pass(self, win, y0, x0, h, w, st, sat, pred, now):
        """The next pass - AOS/TCA/LOS, elevations and azimuths."""
        ps = pred.predict_passes(now, st.min_el, 1)
        if not ps:
            addstr(win, y0 + 2, x0, "no pass within the search window",
                   cp(CLR_DIM))
            return
        p0 = ps[0]
        rows = [
            ("AOS", fmt.fmt_clock(p0.aos, True)),
            ("AOS in", fmt.fmt_dur(p0.aos - now)),
            ("AOS azimuth", fmt.fmt_az(p0.az_aos)),
            ("TCA", fmt.fmt_clock(getattr(p0, "tca", p0.aos))),
            ("Max elevation", "%.0f\u00b0" % p0.max_el),
            ("LOS", fmt.fmt_clock(p0.los)),
            ("LOS azimuth", fmt.fmt_az(p0.az_los)),
            ("Duration", fmt.fmt_dur(p0.los - p0.aos)),
        ]
        _rows(win, y0, x0, h, w, "Next pass", rows)

    def _draw_stats(self, win, y0, x0, h, w, st, sat, pred, now):
        """Pass statistics over the coming days - the desktop's stats section."""
        ps = pred.predict_passes(now, st.min_el, 40, now + 7 * 86400)
        if not ps:
            addstr(win, y0 + 2, x0, "no passes in the next 7 days",
                   cp(CLR_DIM))
            return
        els = [p.max_el for p in ps]
        best = max(ps, key=lambda p: p.max_el)
        durs = [p.los - p.aos for p in ps]
        gaps = [ps[i + 1].aos - ps[i].los for i in range(len(ps) - 1)]
        rows = [
            ("Total passes", "%d in 7 days" % len(ps)),
            ("Above 30\u00b0", "%d" % sum(1 for e in els if e >= 30)),
            ("Peak elevation", "%.0f\u00b0" % best.max_el),
            ("Best pass", fmt.fmt_clock(best.aos, True)),
            ("Best duration", fmt.fmt_dur(best.los - best.aos)),
            ("Longest", fmt.fmt_dur(max(durs))),
            ("Mean gap", fmt.fmt_dur(sum(gaps) / len(gaps)) if gaps else "--"),
        ]
        _rows(win, y0, x0, h, w, "Pass statistics (7 days)", rows)

    def _draw_anomaly(self, win, y0, x0, h, w, st, sat, pred, now):
        """Anomalies, revolution counts and the decay estimate."""
        mm = sat.mean_motion
        period = 86400.0 / mm if mm else 0.0
        ma = getattr(sat, "ma", None)
        rows = []
        if ma is not None:
            frac = (ma % 360.0) / 360.0
            rows += [
                ("Mean anomaly", "%.2f\u00b0" % (ma % 360.0)),
                ("To perigee", fmt.fmt_dur((1.0 - frac) * period)),
                ("To apogee", fmt.fmt_dur(((0.5 - frac) % 1.0) * period)),
            ]
        rows += [
            ("Arg of perigee", "%.3f\u00b0" % sat.argp),
            ("Revs/day", "%.6f" % mm),
            ("Rev @ epoch", str(getattr(sat, "rev_at_epoch", "\u2014"))),
        ]
        try:
            # Recalibrated model (engine.decay, CardSat 0.9.68) - not
            # analysis.estimate_decay_days, which is the pre-refit formula and
            # predicts about a fifth of the true remaining life.
            from orbitdeck.engine import decay as DK
            nd = getattr(sat, "ndot", 0.0) or 0.0
            d_now, src = DK.estimate_decay_days(mm, sat.ecc, sat.bstar, nd)
            d_short, _ = DK.estimate_decay_days(mm, sat.ecc, sat.bstar, nd,
                                                solar="high")
            d_long, _ = DK.estimate_decay_days(mm, sat.ecc, sat.bstar, nd,
                                               solar="low")
            rows.append(("Decay est.", DK.fmt_decay(d_now)))
            rows.append(("Decay from", DK.SRC_NAMES.get(src, "")))
            # The solar range is only meaningful on the B* path: anchoring on
            # the observed n-dot cancels the density normalisation and the
            # solar scale by construction, so low/high would print the same
            # number twice and imply a confidence interval that is not there.
            if src == DK.SRC_BSTAR:
                rows.append(("Decay range", "%s \u2013 %s" % (
                    DK.fmt_decay(d_short), DK.fmt_decay(d_long))))
        except Exception:
            pass
        _rows(win, y0, x0, h, w, "Anomalies & decay", rows)

    def _draw_identity(self, win, y0, x0, h, w, st, sat, pred, now):
        """Catalog identity, epoch age and launch - the desktop's identity
        section, including the launch data added from the COSPAR designator."""
        yr = an.cospar_launch_year(sat.intl_des)
        yrs = an.years_in_orbit(sat.intl_des, now)
        sibs = an.launch_siblings(st.store.db, sat)
        va, vp = an.velocity_extremes_kms(
            an.semi_major_axis_km(sat.mean_motion), sat.ecc)
        rows = [
            ("Name", sat.name),
            ("NORAD", str(sat.norad)),
            ("Int'l desig", sat.intl_des or "\u2014"),
            ("Launched", ("%d (approx.)" % yr) if yr else "\u2014"),
            ("In orbit", ("~%d years" % yrs) if yrs is not None else "\u2014"),
            ("Launch siblings", ", ".join(x.name for x in sibs[:3])
             if sibs else "none in catalog"),
            ("Epoch", fmt.fmt_clock(sat.epoch_unix, True)),
            ("Epoch age", "%.1f days" % ((now - sat.epoch_unix) / 86400.0)),
            ("V apo / peri", "%.3f / %.3f km/s" % (va, vp)),
            ("B*", "%.6g" % sat.bstar),
        ]
        _rows(win, y0, x0, h, w, "Identity & launch", rows)

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        now = time.time()
        if sat is None:
            addstr(win, y0, x0, "No satellite selected (press 2).", cp(CLR_WARN))
            return
        addstr(win, y0, x0, sat.name, cp(CLR_TITLE) | _bold())
        addstr(win, y0, x0 + len(sat.name) + 2, "#%d  %s" % (
            sat.norad, sat.intl_des if hasattr(sat, "intl_des") else ""),
            cp(CLR_DIM))
        addstr(win, y0, x0 + w - 22,
               "page %d/%d %s  (p)" % (self.page + 1, len(self.PAGES),
                                       self.PAGES[self.page]), cp(CLR_ACCENT))
        if self.PAGES[self.page] != "elements":
            pred = st.pred_for(sat)
            fn = {"live": self._draw_live, "pass": self._draw_pass,
                  "stats": self._draw_stats, "anomaly": self._draw_anomaly,
                  "identity": self._draw_identity}[self.PAGES[self.page]]
            return fn(win, y0 + 2, x0, h - 2, w, st, sat, pred, now)

        mm = sat.mean_motion
        a = an.semi_major_axis_km(mm)
        node, perigee = an.j2_rates(mm, sat.incl, sat.ecc)
        alt_apo = sat.apogee_km
        alt_per = sat.perigee_km
        mean_alt = a - 6378.135
        foot_d = an.footprint_diameter_km(mean_alt)
        repeat = an.repeat_ground_track(mm)
        longest = an.longest_possible_pass_min(mm, sat.ecc)
        gt_shift = an.groundtrack_shift_deg(mm)
        beta_star = an.beta_star_deg(mean_alt)
        sunsync = an.is_sun_synchronous(node)
        try:
            ltan = an.ltan_hours(sat.raan, now)
        except Exception:
            ltan = None
        # Recalibrated model, as on the anomaly page and the desktop screen.
        from orbitdeck.engine import decay as DK
        decay, _decay_src = DK.estimate_decay_days(
            mm, sat.ecc, sat.bstar, getattr(sat, "ndot", 0.0) or 0.0)

        # Two columns only when both fit. At 80x24 the nav leaves ~61 columns
        # of content, and a hardcoded 40-column split pushed the right-hand
        # labels past the edge - values were truncated mid-number, losing their
        # units. Below the threshold, stack the sections instead.
        LAB, VAL = 18, 12
        two_col = w >= (LAB + VAL) * 2 + 2
        col2 = x0 + (w // 2 if two_col else 0)
        rows_left = [
            ("Mean motion", "%.6f rev/day" % mm),
            ("Period", "%.2f min" % sat.period_min),
            ("Semi-major axis", "%.1f km" % a),
            ("Apogee alt", "%.1f km" % alt_apo),
            ("Perigee alt", "%.1f km" % alt_per),
            ("Eccentricity", "%.5f" % sat.ecc),
            ("Inclination", "%.4f\u00b0" % sat.incl),
            ("RAAN", "%.3f\u00b0" % sat.raan),
            ("Arg perigee", "%.3f\u00b0" % sat.argp),
        ]
        rows_right = [
            ("Footprint dia", "%.0f km" % foot_d),
            ("Node drift", "%+.3f\u00b0/day" % node),
            ("Perigee drift", "%+.3f\u00b0/day" % perigee),
            ("Sun-synchronous", "yes" if sunsync else "no"),
            ("LTAN", ("%.2f h" % ltan) if ltan is not None else "--"),
            ("Beta* threshold", "%.1f\u00b0" % beta_star),
            ("Track shift/orbit", "%.2f\u00b0 W" % abs(gt_shift)),
            ("Repeat track", repeat or "no short cycle"),
            ("Longest pass", "%.1f min" % longest),
        ]
        def put(yy, xx, lab, val):
            addstr(win, yy, xx, ljust(lab, LAB), cp(CLR_DIM))
            addstr(win, yy, xx + LAB,
                   clip(val, max(1, x0 + w - xx - LAB)))

        addstr(win, y0 + 2, x0, "Elements & geometry", cp(CLR_HEADER) | _bold())
        if two_col:
            addstr(win, y0 + 2, col2, "Derived", cp(CLR_HEADER) | _bold())
            y = y0 + 3
            for lab, val in rows_left:
                put(y, x0, lab, val)
                y += 1
            y = y0 + 3
            for lab, val in rows_right:
                put(y, col2, lab, val)
                y += 1
            used = max(len(rows_left), len(rows_right))
        else:
            # Narrow terminal: stack the sections. Side by side, the right-hand
            # values were truncated mid-number and lost their units.
            y = y0 + 3
            for lab, val in rows_left:
                put(y, x0, lab, val)
                y += 1
            addstr(win, y, x0, "Derived", cp(CLR_HEADER) | _bold())
            y += 1
            for lab, val in rows_right:
                if y >= y0 + h - 2:
                    break
                put(y, x0, lab, val)
                y += 1
            used = (y - (y0 + 3))

        # decay line
        yb = y0 + 3 + used + 1
        addstr(win, yb, x0, "Decay estimate", cp(CLR_HEADER) | _bold())
        dtxt = DK.fmt_decay(decay)
        dattr = cp(CLR_BAD) if (decay and decay < 365) else cp(CLR_OK)
        addstr(win, yb, x0 + 18, dtxt, dattr)
        addstr(win, yb, x0 + 18 + len(dtxt) + 2,
               "(B* %.2e)" % sat.bstar, cp(CLR_DIM))

        # live mean/true anomaly
        yb += 1
        ma = an.mean_anomaly_now_deg(sat.ma, mm, now, sat.epoch_unix)
        ta = an.true_anomaly_deg(ma, sat.ecc)
        addstr(win, yb, x0, "Anomaly now", cp(CLR_HEADER) | _bold())
        addstr(win, yb, x0 + 18, "M %.1f\u00b0   \u03bd %.1f\u00b0   u %.1f\u00b0"
               % (ma, ta, an.arg_of_latitude_deg(sat.argp, ta)))

        if st.pred_for(sat).deepspace_approximate():
            addstr(win, y0 + h - 1, x0,
                   "deep-space orbit: positions approximate (no full SDP4)",
                   cp(CLR_WARN))


# A coarse equirectangular coastline mask for the ASCII world map. We render a
# land/sea grid by sampling a compact set of lon/lat land rectangles. This keeps
# the map dependency-free and tiny; it is a schematic, not a precise coastline.
class GroundTrackScreen(Screen):
    title = "Ground Track"
    refresh_secs = 2.0

    def draw(self, win, y0, x0, h, w):
        st = self.state
        sat = st.sat
        now = time.time()
        if sat is None:
            addstr(win, y0, x0, "No satellite selected (press 2).", cp(CLR_WARN))
            return
        pred = st.pred_for(sat)
        addstr(win, y0, x0, sat.name, cp(CLR_TITLE) | _bold())
        L = pred.look(now)
        addstr(win, y0, x0 + len(sat.name) + 2,
               "sub-point %s  alt %.0f km" % (
                   fmt.fmt_latlon(L.sub_lat, L.sub_lon), L.alt_km),
               cp(CLR_DIM))

        # map area
        my0 = y0 + 2
        mw = w - 2
        mh = h - 3
        if mw < 20 or mh < 8:
            addstr(win, my0, x0, "(terminal too small for map)", cp(CLR_DIM))
            return

        # Braille map: the land raster, ground track and footprint all draw on
        # the sub-cell canvas, so the coastline gets 2x4 dots per character cell
        # instead of one shaded block - roughly 8x the map detail in the same
        # space. Land is sampled per dot rather than per cell.
        from ..canvas import Canvas, blit
        # An equirectangular map needs a 2:1 area (360 deg of longitude against
        # 180 of latitude). Braille dots are square - 2 per cell across, 4 down,
        # against a roughly 1:2 cell - but the PANE is not 2:1, so filling it
        # stretched every continent about 30% vertically. Fit the widest 2:1
        # box that fits and centre it instead.
        _dw, _dh = mw * 2, mh * 4
        if _dw < 2 * _dh:
            _dh = _dw // 2
        else:
            _dw = _dh * 2
        cv = Canvas(max(1, _dw // 2), max(1, _dh // 4))
        _pad_y = max(0, (mh - cv.height // 4) // 2)

        def to_px(lat, lon):
            px = (lon + 180) / 360.0 * (cv.width - 1)
            py = (90 - lat) / 180.0 * (cv.height - 1)
            return px, py

        # Draw the bundled coastline POLYLINES, the same vector data the
        # desktop map uses. The previous version outlined a coarse land/sea
        # rectangle mask, which necessarily produced boxes rather than
        # coastlines - outlining a grid of rectangles can only ever give you
        # rectangles. Braille is line art, and a polyline is exactly that.
        from orbitdeck.data.worldmap_data import COASTLINES
        for poly in COASTLINES:
            prev = None
            for lon, lat in poly:
                pt = to_px(lat, lon)
                if prev is not None and abs(pt[0] - prev[0]) < cv.width * 0.5:
                    cv.line(prev[0], prev[1], pt[0], pt[1], cp(CLR_DIM))
                prev = pt

        # equator and prime meridian
        eq_y = int((90 - 0) / 180.0 * (cv.height - 1))
        for dx in range(0, cv.width, 2):
            cv.plot(dx, eq_y, cp(CLR_DIM))
        pm_x = int((0 + 180) / 360.0 * (cv.width - 1))
        for dy in range(0, cv.height, 2):
            cv.plot(pm_x, dy, cp(CLR_DIM))

        # ground track: +/- one period, past dim and future accented
        per = (sat.period_min or 95) * 60
        n = cv.width
        prev = None
        prev_past = True
        for i in range(n + 1):
            t = now - per + (2 * per) * i / n
            la, lo, _ = pred.subpoint_at(t)
            px, py = to_px(la, lo)
            past = t <= now
            colour = cp(CLR_DIM) if past else cp(CLR_ACCENT)
            if prev is not None and abs(px - prev[0]) < cv.width * 0.5:
                cv.line(prev[0], prev[1], px, py, colour)
            else:
                cv.plot(px, py, colour)
            prev = (px, py)
            prev_past = past
        _ = prev_past

        # footprint circle around the current sub-point
        foot_deg = an.footprint_radius_deg(L.alt_km)
        prev = None
        for k in range(73):
            la2, lo2 = _dest(L.sub_lat, L.sub_lon, foot_deg, k * 5.0)
            px, py = to_px(la2, lo2)
            if prev is not None and abs(px - prev[0]) < cv.width * 0.5:
                cv.line(prev[0], prev[1], px, py, cp(CLR_WARN))
            prev = (px, py)

        # the satellite itself
        sx, sy = to_px(L.sub_lat, L.sub_lon)
        for ddx in (-1, 0, 1):
            for ddy in (-1, 0, 1):
                cv.plot(sx + ddx, sy + ddy, cp(CLR_OK))

        blit(win, cv, my0 + _pad_y, x0)

        # Sat and observer stay as text glyphs on top of the braille map: they
        # are labels you need to pick out at a glance, not line art, and a
        # character cell can hold either braille or a marker, not both.
        def to_cell(lat, lon):
            # Same 2:1 box the map was drawn into, or the markers land off it.
            cols = cv.width // 2
            rows = cv.height // 4
            rx = int((lon + 180) / 360.0 * (cols - 1))
            ry = int((90 - lat) / 180.0 * (rows - 1)) + _pad_y
            return (max(0, min(cols - 1, rx)),
                    max(0, min(mh - 1, ry)))

        rx, ry = to_cell(L.sub_lat, L.sub_lon)
        addstr(win, my0 + ry, x0 + rx, "\u25c9",
               cp(CLR_OK) | _bold() if L.sunlit else cp(CLR_DIM) | _bold())
        orx, ory = to_cell(st.obs.lat, st.obs.lon)
        addstr(win, my0 + ory, x0 + orx, "\u25b2", cp(CLR_ACCENT) | _bold())

        addstr(win, y0 + h - 1, x0,
               "\u25c9 sat   \u25b2 you   track: dim past / bright future   "
               "footprint ring", cp(CLR_DIM))
    def help_keys(self):
        return [("[ ]", "prev/next sat")]

    def handle_key(self, ch):
        if ch in (ord("["), ord("]")):
            self.app.cycle_sat(-1 if ch == ord("[") else 1)
            return True
        return False


def grid_ok(rx, ry, mw, mh):
    return 0 <= rx < mw and 0 <= ry < mh


def _dest(lat, lon, dist_deg, bearing_deg):
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    d = math.radians(dist_deg)
    brg = math.radians(bearing_deg)
    lat2 = math.asin(math.sin(p1) * math.cos(d) +
                     math.cos(p1) * math.sin(d) * math.cos(brg))
    lon2 = l1 + math.atan2(math.sin(brg) * math.sin(d) * math.cos(p1),
                           math.cos(d) - math.sin(p1) * math.sin(lat2))
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


# Compact schematic land test: a set of lon/lat boxes approximating the
# continents at world-map scale. Good enough to orient the eye; not a coastline.
_LAND_BOXES = [
    # (lat_min, lat_max, lon_min, lon_max)
    (7, 72, -168, -52),     # North America
    (-56, 12, -82, -34),    # South America
    (35, 71, -10, 40),      # Europe
    (-35, 37, -18, 52),     # Africa
    (5, 78, 40, 180),       # Asia
    (-45, -10, 112, 154),   # Australia
    (-90, -63, -180, 180),  # Antarctica
    (60, 84, -55, -12),     # Greenland
]


def _is_land(lat, lon):
    for la0, la1, lo0, lo1 in _LAND_BOXES:
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return True
    return False


def _bold():
    import curses
    return curses.A_BOLD
