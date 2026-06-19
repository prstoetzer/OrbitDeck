"""lab.py - build a synthetic "lab" satellite from chosen orbital elements.

The OSCARLOCATOR Simulator's educational mode lets a user dial in a hypothetical
satellite's Keplerian elements and watch the path, footprint, and range circle
respond. This module turns a set of slider/entry values into a real ``SatEntry``
that flows through the exact same predictor and PDF pipeline as a catalog
satellite -- so no engine changes are needed.

Altitude is exposed as the primary size control (more intuitive than mean
motion); we convert a chosen *mean altitude* to the mean motion the propagator
needs. Eccentricity and altitude are clamped to ranges the bundled pure-Python
propagator handles well, and helpers expose the derived quantities (period,
apogee/perigee, footprint radius) plus a plain-language orbit-type label for the
educational read-outs.
"""

import math
import time

from ..engine.satdb import SatEntry

MU = 398600.4418          # km^3/s^2, Earth GM
RE_KM = 6378.135
LAB_NORAD_BASE = 99000    # synthetic NORAD ids for lab satellites

# clamp ranges chosen so the bundled SGP4 stays well-behaved and the result is
# physically meaningful for teaching
ALT_MIN_KM = 200.0
ALT_MAX_KM = 40000.0
ECC_MAX = 0.70


def apsides_from_alt_ecc(mean_alt_km, ecc):
    """Apogee and perigee ALTITUDES (km above the surface) for a mean-altitude /
    eccentricity pair. a = Re + mean_alt; apogee = a(1+e) - Re, etc."""
    a = RE_KM + mean_alt_km
    apo = a * (1.0 + ecc) - RE_KM
    peri = a * (1.0 - ecc) - RE_KM
    return apo, peri


def alt_ecc_from_apsides(apogee_km, perigee_km):
    """Inverse: mean-altitude and eccentricity for given apogee/perigee
    ALTITUDES (km). The semi-major axis is the mean of the two radii, and
    e = (ra - rp)/(ra + rp). Perigee is forced not to exceed apogee."""
    ra = RE_KM + max(apogee_km, perigee_km)
    rp = RE_KM + min(apogee_km, perigee_km)
    a = 0.5 * (ra + rp)
    ecc = 0.0 if (ra + rp) <= 0 else (ra - rp) / (ra + rp)
    return a - RE_KM, ecc


def mean_motion_from_alt(mean_alt_km, ecc=0.0):
    """Rev/day for a circular-equivalent orbit of the given *mean altitude*.

    We treat the mean altitude as the semi-major-axis altitude (a = Re + alt),
    which makes the slider read as "how high" independent of eccentricity; the
    apogee/perigee then spread around it as ecc grows.
    """
    a = RE_KM + max(ALT_MIN_KM, min(ALT_MAX_KM, mean_alt_km))
    n_rad_s = math.sqrt(MU / (a ** 3))          # rad/s
    return n_rad_s * 86400.0 / (2.0 * math.pi)  # rev/day


def alt_from_mean_motion(mean_motion_revday):
    """Inverse of mean_motion_from_alt: mean altitude (km) for a mean motion."""
    if mean_motion_revday <= 0:
        return 0.0
    n_rad_s = mean_motion_revday * 2.0 * math.pi / 86400.0
    a = (MU / (n_rad_s * n_rad_s)) ** (1.0 / 3.0)
    return a - RE_KM


def period_min_from_alt(mean_alt_km):
    mm = mean_motion_from_alt(mean_alt_km)
    return 1440.0 / mm if mm else 0.0


def footprint_radius_deg(alt_km):
    """Earth-central half-angle of the 0-deg-elevation footprint at altitude."""
    if alt_km <= 0:
        return 0.0
    return math.degrees(math.acos(RE_KM / (RE_KM + alt_km)))


def orbit_type_label(mean_alt_km, ecc, incl_deg):
    """A short plain-language classification for the read-out."""
    apo = mean_alt_km * (1.0 + ecc)
    if mean_alt_km >= 34000.0 and ecc < 0.05:
        if incl_deg < 1.0:
            return "Geostationary"
        return "Geosynchronous"
    if ecc >= 0.5 and 60.0 <= incl_deg <= 65.0 and apo > 30000.0:
        return "Molniya-like (high ellipse)"
    if ecc >= 0.4:
        return "Highly elliptical (HEO)"
    if 8000.0 <= mean_alt_km < 34000.0:
        return "Medium Earth orbit (MEO)"
    if mean_alt_km < 2000.0:
        if 96.0 <= incl_deg <= 102.0:
            return "Sun-synchronous LEO"
        if incl_deg > 102.0:
            return "Retrograde LEO"
        if incl_deg < 20.0:
            return "Low-inclination LEO"
        return "Low Earth orbit (LEO)"
    return "Elliptical orbit"


def default_elements():
    """A sensible starting point: a roughly ISS-like circular LEO."""
    return {
        "name": "LAB-SAT",
        "alt_km": 420.0,
        "ecc": 0.0,
        "incl": 51.6,
        "raan": 0.0,
        "argp": 0.0,
        "ma": 0.0,
    }


def clamp_elements(el):
    """Return a copy with all values clamped to safe/teaching ranges."""
    out = dict(el)
    out["alt_km"] = max(ALT_MIN_KM, min(ALT_MAX_KM, float(el.get("alt_km",
                                                                 420.0))))
    out["ecc"] = max(0.0, min(ECC_MAX, float(el.get("ecc", 0.0))))
    out["incl"] = max(0.0, min(180.0, float(el.get("incl", 51.6))))
    out["raan"] = float(el.get("raan", 0.0)) % 360.0
    out["argp"] = float(el.get("argp", 0.0)) % 360.0
    out["ma"] = float(el.get("ma", 0.0)) % 360.0
    out["name"] = (el.get("name") or "LAB-SAT").strip() or "LAB-SAT"
    return out


def make_lab_sat(el, epoch_unix=None, norad=None):
    """Build a ``SatEntry`` from the (clamped) element dict so it can be fed to a
    Predictor and the OSCARLOCATOR PDF generator exactly like a catalog sat."""
    el = clamp_elements(el)
    if epoch_unix is None:
        epoch_unix = time.time()
    mm = mean_motion_from_alt(el["alt_km"], el["ecc"])
    return SatEntry(
        name=el["name"],
        norad=norad if norad is not None else LAB_NORAD_BASE,
        intl_des="LAB",
        epoch_unix=epoch_unix,
        incl=el["incl"],
        ecc=el["ecc"],
        raan=el["raan"],
        argp=el["argp"],
        ma=el["ma"],
        mean_motion=mm,
        bstar=0.0,
        is_manual=True,
    )


def derived_readout(el):
    """A dict of derived quantities for the educational read-out panel."""
    el = clamp_elements(el)
    alt = el["alt_km"]
    ecc = el["ecc"]
    incl = el["incl"]
    apo = alt * (1.0 + ecc)
    per = alt * (1.0 - ecc)
    mm = mean_motion_from_alt(alt, ecc)

    # secular J2 effects, sun-synchronicity, LTAN, and a ground-track repeat
    # cycle -- reuse the engine's models so the lab teaches the same numbers the
    # rest of OrbitDeck reports.
    from ..engine import analysis as _A
    node_drift, perigee_drift = _A.j2_rates(mm, incl, ecc)
    sunsync = _A.is_sun_synchronous(node_drift)
    repeat = _A.repeat_ground_track(mm)        # (revs, days) or None
    # decay needs a drag (B*) assumption; use a small representative value so a
    # very low perigee visibly shortens lifetime, but report "n/a" up high.
    bstar_assumed = 1e-4
    decay_days = _A.estimate_decay_days(bstar_assumed, mm, ecc)

    return {
        "period_min": period_min_from_alt(alt),
        "mean_motion": mm,
        "apogee_km": apo,
        "perigee_km": per,
        "footprint_deg": footprint_radius_deg(alt),
        "footprint_km": footprint_radius_deg(alt) * math.pi / 180.0 * RE_KM,
        "type": orbit_type_label(alt, ecc, incl),
        "node_drift_degday": node_drift,
        "perigee_drift_degday": perigee_drift,
        "sun_synchronous": sunsync,
        "repeat": repeat,
        "decay_days": decay_days,
        "decay_text": _A.fmt_decay(decay_days),
    }


# --- element-effect explainers (plain language) -------------------------------

def explain(field, el):
    """One-line plain-language consequence of the current value of ``field``,
    used by the lab's live explainer line."""
    el = clamp_elements(el)
    alt = el["alt_km"]
    ecc = el["ecc"]
    incl = el["incl"]
    if field == "alt_km":
        foot = footprint_radius_deg(alt)
        return ("Higher orbit \u2192 longer period and a wider footprint "
                "(now ~%.0f\u00b0 / ~%.0f km radius), so passes are longer but "
                "the satellite moves more slowly across the sky."
                % (foot, foot * math.pi / 180.0 * RE_KM))
    if field == "ecc":
        if ecc < 0.02:
            return ("Near-circular orbit: altitude and speed stay roughly "
                    "constant all the way around.")
        return ("Eccentric orbit: the satellite is fast and low at perigee "
                "(~%.0f km) and slow and high at apogee (~%.0f km), so it "
                "lingers over the apogee hemisphere."
                % (alt * (1.0 - ecc), alt * (1.0 + ecc)))
    if field == "incl":
        if incl < 1.0:
            return ("Equatorial orbit: the ground track stays over the "
                    "equator \u2014 only low latitudes are ever covered.")
        if 96.0 <= incl <= 102.0:
            return ("Near sun-synchronous: this inclination makes the orbit "
                    "plane precess ~1\u00b0/day to follow the Sun, so passes "
                    "recur at similar local times.")
        if abs(incl - 63.4) < 1.0:
            return ("63.4\u00b0 is the \u2018magic\u2019 critical inclination: "
                    "the argument of perigee stops drifting \u2014 the basis of "
                    "Molniya orbits.")
        if incl > 90.0:
            return ("Retrograde orbit (inclination > 90\u00b0): the satellite "
                    "travels east-to-west; reachable latitudes go up to "
                    "%.0f\u00b0." % (180.0 - incl))
        return ("Inclination sets the maximum latitude reached: about "
                "\u00b1%.0f\u00b0. Your QTH must be near the ground track to "
                "get a pass." % incl)
    if field == "raan":
        return ("Right ascension of the ascending node rotates the whole orbit "
                "plane around Earth's axis \u2014 it shifts WHERE (which "
                "longitudes) the passes happen, not their shape.")
    if field == "argp":
        return ("Argument of perigee rotates the ellipse within its plane \u2014 "
                "it sets WHERE in the orbit (which latitude) the satellite is "
                "lowest/highest.")
    if field == "ma":
        return ("Mean anomaly is just the satellite's starting position along "
                "the orbit at the epoch \u2014 it slides the bird forward or "
                "back along the same path.")
    return ""


def pass_explain(pred, p):
    """Plain-language explanation of WHY a real pass has the geometry it does,
    for the Pass Detail screen. Returns a list of short strings.

    Connects the abstract numbers to the cause: the peak elevation is set by how
    close the ground track comes to the station; the Doppler swing is set by the
    range-rate, which is largest for low, fast, overhead passes.
    """
    lines = []
    try:
        look_tca = pred.look(p.tca)
        rng_tca = look_tca.range_km
        alt_tca = look_tca.alt_km
    except Exception:
        return lines

    # 1) peak elevation <-> ground-track proximity
    if p.max_el >= 70.0:
        lines.append(
            "Very high pass (%.0f\u00b0): the ground track passes almost "
            "overhead, so the satellite is nearly straight up at its closest "
            "point (~%.0f km)." % (p.max_el, rng_tca))
    elif p.max_el >= 30.0:
        lines.append(
            "Good pass (%.0f\u00b0): the ground track comes fairly close to "
            "your QTH, clearing buildings and trees for most of the pass."
            % p.max_el)
    else:
        lines.append(
            "Low pass (%.0f\u00b0): the ground track stays off to one side, so "
            "the satellite skims the horizon \u2014 expect terrain blockage and "
            "weaker signals." % p.max_el)

    # 2) duration <-> altitude / geometry
    dur_min = (p.los - p.aos) / 60.0
    lines.append(
        "Lasts about %.0f minutes: higher orbits (this one ~%.0f km) give "
        "longer horizon-to-horizon passes." % (dur_min, alt_tca))

    # 3) Doppler <-> range-rate at AOS/LOS
    try:
        rr_aos = pred.look(p.aos).range_rate
        rr_los = pred.look(p.los).range_rate
        lines.append(
            "Doppler: the satellite approaches at AOS (signal shifts high) and "
            "recedes at LOS (shifts low); the swing is largest on high, fast "
            "passes. Range-rate runs ~%+.1f to %+.1f km/s here, so tune the "
            "radio down through the pass." % (rr_aos, rr_los))
    except Exception:
        pass

    return lines
