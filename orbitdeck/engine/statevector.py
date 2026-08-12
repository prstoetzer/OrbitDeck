"""orbitdeck.engine.statevector - classical orbital elements from a TEME state.

Recover the classical (Keplerian) orbital elements from a position/velocity
state vector, ported from CardSat's rv2coe seed. This gives the osculating
elements - inclination, RAAN, eccentricity, argument of perigee, mean anomaly
and mean motion - which are what you need to turn a state vector (e.g. from a
launch provider or an ephemeris) into GP-style elements.

Note: these are *osculating* elements. SGP4 consumes *mean* (Brouwer/Kozai)
elements, which differ slightly because of J2. For most purposes - identifying an
orbit, seeding a propagator, sanity-checking a TLE - the osculating elements are
what you want; a full mean-element fit (SGP4 differential correction) is a larger
undertaking and not done here. The function says so in its output.
"""

import math

MU = 398600.4418          # Earth GM, km^3/s^2
R2D = 180.0 / math.pi


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _acos_clamped(x):
    return math.acos(max(-1.0, min(1.0, x)))


def rv_to_elements(r, v):
    """Classical orbital elements from a TEME state vector.

    ``r`` = position [x, y, z] in km, ``v`` = velocity [vx, vy, vz] in km/s.
    Returns a dict:
        a_km, ecc, incl_deg, raan_deg, argp_deg, ma_deg, nu_deg,
        mean_motion_rev_day, period_min, apogee_km, perigee_km
    Raises ValueError for a degenerate/hyperbolic state.
    """
    R = _norm(r)
    V2 = _dot(v, v)
    if R <= 0:
        raise ValueError("position vector is zero")

    h = _cross(r, v)                      # specific angular momentum
    hmag = _norm(h)
    if hmag < 1e-9:
        raise ValueError("degenerate orbit (zero angular momentum)")

    nod = [-h[1], h[0], 0.0]              # node vector k x h
    nmag = math.hypot(nod[0], nod[1])

    rv = _dot(r, v)
    ev = [((V2 - MU / R) * r[i] - rv * v[i]) / MU for i in range(3)]
    e = _norm(ev)

    energy = V2 / 2.0 - MU / R
    if energy >= 0:
        raise ValueError("non-elliptical orbit (parabolic/hyperbolic)")
    a = -MU / (2.0 * energy)              # semi-major axis, km

    incl = _acos_clamped(h[2] / hmag) * R2D
    if nmag > 1e-9:
        raan = _acos_clamped(nod[0] / nmag) * R2D
        if nod[1] < 0:
            raan = 360.0 - raan
    else:
        raan = 0.0

    if nmag > 1e-9 and e > 1e-9:
        argp = _acos_clamped(_dot(nod, ev) / (nmag * e)) * R2D
        if ev[2] < 0:
            argp = 360.0 - argp
    else:
        argp = 0.0

    # true anomaly
    if e > 1e-9:
        nu = _acos_clamped(_dot(ev, r) / (e * R))
        if rv < 0:
            nu = 2 * math.pi - nu
    elif nmag > 1e-9:
        nu = _acos_clamped((nod[0] * r[0] + nod[1] * r[1]) / (nmag * R))
        if r[2] < 0:
            nu = 2 * math.pi - nu
    else:
        nu = 0.0

    E = math.atan2(math.sqrt(max(0.0, 1 - e * e)) * math.sin(nu),
                   e + math.cos(nu))
    M = E - e * math.sin(E)
    ma = math.degrees(M) % 360.0
    n_revday = math.sqrt(MU / (a ** 3)) * 86400.0 / (2.0 * math.pi)
    period_min = 1440.0 / n_revday if n_revday > 0 else 0.0
    RE = 6378.137
    return {
        "a_km": a,
        "ecc": e,
        "incl_deg": incl,
        "raan_deg": raan,
        "argp_deg": argp,
        "ma_deg": ma,
        "nu_deg": math.degrees(nu) % 360.0,
        "mean_motion_rev_day": n_revday,
        "period_min": period_min,
        "apogee_km": a * (1 + e) - RE,
        "perigee_km": a * (1 - e) - RE,
    }


def rv_to_rows(rx, ry, rz, vx, vy, vz):
    """Wrapper for the Tools hub: take six scalars, return (label, value, note)
    rows. On a bad state vector, returns a single explanatory row."""
    try:
        el = rv_to_elements([rx, ry, rz], [vx, vy, vz])
    except ValueError as exc:
        return [("error", str(exc), "")]
    return [
        ("Semi-major a", "%.1f km" % el["a_km"], ""),
        ("Eccentricity", "%.6f" % el["ecc"], ""),
        ("Inclination", "%.4f deg" % el["incl_deg"], ""),
        ("RAAN", "%.4f deg" % el["raan_deg"], ""),
        ("Arg perigee", "%.4f deg" % el["argp_deg"], ""),
        ("Mean anomaly", "%.4f deg" % el["ma_deg"], ""),
        ("Mean motion", "%.8f rev/day" % el["mean_motion_rev_day"], ""),
        ("Period", "%.2f min" % el["period_min"], ""),
        ("Apogee", "%.1f km" % el["apogee_km"], "altitude"),
        ("Perigee", "%.1f km" % el["perigee_km"], "altitude"),
        ("note", "osculating elements", "SGP4 wants mean elems"),
    ]


def fit_diagnostics(r, v):
    """How trustworthy is this state-vector fit?

    A converged-looking element set from a bad vector is the dangerous case, so
    report what the fit rests on rather than only its output: the residual
    between the input vector and the vector regenerated from the derived
    elements, plus the sanity checks that catch a unit mix-up (metres for
    kilometres, m/s for km/s) which otherwise yields plausible-looking garbage.
    """
    import math as _m
    rmag = _m.sqrt(sum(c * c for c in r))
    vmag = _m.sqrt(sum(c * c for c in v))
    notes = []
    ok = True
    if rmag < 6500:
        notes.append("position is inside the Earth - are these metres?")
        ok = False
    elif rmag > 500000:
        notes.append("position is beyond cislunar space - check units")
        ok = False
    if vmag < 0.5:
        notes.append("velocity is very low - are these m/s rather than km/s?")
        ok = False
    elif vmag > 15.0:
        notes.append("velocity exceeds escape - check units")
        ok = False
    # circular-orbit speed at this radius, as a sanity reference
    v_circ = _m.sqrt(398600.4418 / rmag) if rmag > 0 else 0.0
    ratio = (vmag / v_circ) if v_circ else 0.0
    if ok and not (0.5 < ratio < 1.45):
        notes.append("speed is %.2fx circular at this radius - orbit is "
                     "highly eccentric or the vector is inconsistent" % ratio)
    return {
        "r_km": rmag, "v_kms": vmag, "v_circular_kms": v_circ,
        "speed_ratio": ratio, "plausible": ok and bool(0.5 < ratio < 1.45),
        "notes": notes or ["vector looks self-consistent"],
    }
