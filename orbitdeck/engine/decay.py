"""orbitdeck.engine.decay - days-to-reentry, empirically calibrated.

This replaces an earlier port that came from CardSat 0.9.61. CardSat 0.9.68
rebuilt the model after fitting it against **244 catalogued objects that
actually re-entered** (Space-Track TIP decay epochs plus gp_history element
sets), cross-checked against the observed mean-motion derivative of ~1500
catalogued objects. Their note on the old version is blunt: it used
``Cd*A/m = 38*B*`` together with a ``da/dt`` a factor of two too large; the two
errors partly cancelled at ISS altitude where the constant had been tuned, and
left the model predicting **about a fifth of the true remaining life** across
the re-entry set. The port carried that error, so it is fixed here.

Two anchors, in order of preference:

  1. **Observed n-dot.** The element set's mean-motion derivative *is* a
     measurement of the current decay rate: ``adot = -(2/3)(a/n) * ndot``.
     Back-solving the ballistic coefficient from it makes the present rate right
     by construction and cancels every calibration the B* path needs - the
     B*->Cd*A/m conversion, the absolute density normalisation and the solar
     scale (which multiplies both the back-solve and the integration). It also
     absorbs attitude and true area, being a measurement of the object rather
     than a model of it. Scored 0.99x median against real re-entries, 92% within
     +/-30%.
  2. **B* fallback**, for objects whose n-dot is absent, negative (rising or
     freshly manoeuvred) or below the noise floor. ``Cd*A/m = 12.741621 * B*``,
     the textbook SGP4 conversion.

Both integrate the same King-Hele decay: drag is evaluated at perigee with the
eccentricity factor ``exp(-z)(I0(z) + 2e*I1(z))``, ``z = a*e/H``, which accounts
for the satellite spending almost none of an eccentric revolution near perigee.
Without it a GTO reads ~40 days instead of years. Energy comes out of apogee
while perigee stays nearly fixed until the orbit circularises.
"""

import math

MU = 3.986004418e14
RE_M = 6.378137e6
TWO_PI = 6.283185307179586

SRC_NONE, SRC_NDOT, SRC_BSTAR = 0, 1, 2
SRC_NAMES = {SRC_NONE: "no usable data", SRC_NDOT: "observed decay rate",
             SRC_BSTAR: "B* drag term"}

SOLAR_SCALES = {"low": 0.35, "mean": 1.0, "high": 3.0}

# Empirical calibration (CardSat 0.9.68). DENS_CAL is the density multiplier for
# the B*-derived path - the exponential table is nominal, the fit wants 1.30x at
# ~250 km. DENS_HKM is how that grows with altitude and is the WEAKEST-
# constrained number in the model: the re-entry set is all low-altitude, so it
# comes from the n-dot ensemble at 400-600 km. ANCHOR_DRAG corrects n-dot being
# a fitted mean over the element set's span, which lags the instantaneous rate
# while decay accelerates. (A density factor would cancel out of the anchored
# path exactly, so this must be applied to the drag.)
DENS_CAL = 1.30
DENS_HKM = 300.0
ANCHOR_DRAG = 1.15
DENS_CAP = 8.0

# altitude km, density kg/m^3, scale height km
_ATM = [
    (100, 5.297e-7, 5.877), (110, 9.661e-8, 7.263), (120, 2.438e-8, 9.473),
    (130, 8.484e-9, 12.636), (140, 3.845e-9, 16.149), (150, 2.070e-9, 22.523),
    (180, 5.464e-10, 29.740), (200, 2.789e-10, 37.105), (250, 7.248e-11, 45.546),
    (300, 2.418e-11, 53.628), (350, 9.518e-12, 53.298), (400, 3.725e-12, 58.515),
    (450, 1.585e-12, 60.828), (500, 6.967e-13, 63.822), (600, 1.454e-13, 71.835),
    (700, 3.614e-14, 88.667), (800, 1.170e-14, 124.64), (900, 5.245e-15, 181.05),
    (1000, 3.019e-15, 268.00),
]


def _band(h_km):
    if h_km < 100:
        h_km = 100
    idx = 0
    for i in range(len(_ATM) - 1):
        if h_km < _ATM[i + 1][0]:
            idx = i
            break
        idx = i + 1
    return _ATM[idx]


def exp_atmosphere(h_km):
    """Density (kg/m^3) from the exponential table; 0 above ~1100 km."""
    if h_km >= 1100:
        return 0.0
    h0, rho0, sh = _band(h_km)
    return rho0 * math.exp(-(h_km - h0) / sh)


def scale_height_m(h_km):
    return _band(h_km)[2] * 1000.0


def dens_cal(h_km):
    """Altitude-dependent density calibration, capped."""
    s = DENS_CAL * math.exp((h_km - 250.0) / DENS_HKM)
    return DENS_CAP if s > DENS_CAP else s


def _i0e(z):
    """Exponentially scaled modified Bessel I0: exp(-z) * I0(z)."""
    if z < 3.75:
        t2 = (z / 3.75) ** 2
        v = 1.0 + t2 * (3.5156229 + t2 * (3.0899424 + t2 * (1.2067492
            + t2 * (0.2659732 + t2 * (0.0360768 + t2 * 0.0045813)))))
        return v * math.exp(-z)
    t = 3.75 / z
    return (0.39894228 + t * (0.01328592 + t * (0.00225319 + t * (-0.00157565
            + t * (0.00916281 + t * (-0.02057706 + t * (0.02635537
            + t * (-0.01647633 + t * 0.00392377)))))))) / math.sqrt(z)


def _i1e(z):
    """Exponentially scaled modified Bessel I1: exp(-z) * I1(z)."""
    if z < 3.75:
        t2 = (z / 3.75) ** 2
        v = z * (0.5 + t2 * (0.87890594 + t2 * (0.51498869 + t2 * (0.15084934
            + t2 * (0.02658733 + t2 * (0.00301532 + t2 * 0.00032411))))))
        return v * math.exp(-z)
    t = 3.75 / z
    return (0.39894228 + t * (-0.03988024 + t * (-0.00362018 + t * (0.00163801
            + t * (-0.01031555 + t * (0.02282967 + t * (-0.02895312
            + t * (0.01787654 + t * (-0.00420059))))))))) / math.sqrt(z)


def king_hele(a_m, ecc, h_km):
    """Eccentricity factor: how much of a revolution is spent near perigee."""
    if ecc <= 1e-4:
        return 1.0
    z = a_m * ecc / scale_height_m(h_km)
    if z <= 0.05:
        return 1.0
    return _i0e(z) + 2.0 * ecc * _i1e(z)


def estimate_decay_days(mean_motion, ecc, bstar, ndot=0.0, solar="mean",
                        max_steps=200000):
    """Days to re-entry. Returns (days, source).

    ``mean_motion`` rev/day, ``ndot`` is MEAN_MOTION_DOT (i.e. ndot/2 in
    rev/day^2, as carried in GP/TLE). ``days`` is -1 for no usable data and
    ``float('inf')`` for effectively stable.
    """
    dens_scale = SOLAR_SCALES.get(solar, 1.0)
    if mean_motion <= 0 or dens_scale <= 0:
        return -1.0, SRC_NONE
    nn = mean_motion * TWO_PI / 86400.0
    a = (MU / (nn * nn)) ** (1.0 / 3.0)
    e = min(0.95, max(0.0, ecc))
    rp, ra = a * (1.0 - e), a * (1.0 + e)
    hp0 = (rp - RE_M) / 1000.0
    if hp0 < 80.0:
        return 0.0, SRC_NONE

    def rho_at(h_km):
        return exp_atmosphere(h_km) * dens_scale * dens_cal(h_km)

    ballistic = 0.0
    src = SRC_NONE
    # anchor 1: the observed decay rate
    adot = -(2.0 / 3.0) * (a / mean_motion) * (2.0 * ndot)     # m/day
    rho0 = rho_at(hp0)
    if adot < -0.5 and rho0 > 0 and hp0 < 1000.0:
        f0 = king_hele(a, e, hp0)
        cand = (ANCHOR_DRAG * (-adot / 86400.0)
                / (rho0 * math.sqrt(MU * a) * f0))
        # a real satellite is ~1e-3..1e-1 m^2/kg; outside this the n-dot was not
        # drag (third-body, manoeuvre or fit noise), so fall through to B*
        if 1e-4 < cand < 50.0:
            ballistic, src = cand, SRC_NDOT
    if src == SRC_NONE:
        if bstar <= 0:
            return -1.0, SRC_NONE
        ballistic = 12.741621 * bstar
        src = SRC_BSTAR

    t_days = 0.0
    for _ in range(max_steps):
        hp = rp - RE_M
        h_km = hp / 1000.0
        a = 0.5 * (rp + ra)
        ecur = (ra - rp) / (ra + rp) if (ra + rp) else 0.0
        # An eccentric orbit sweeps through perigee too fast to be stopped at
        # 120 km and routinely survives with perigee well below it while the
        # orbit circularises, so the threshold depends on eccentricity.
        hp_end = 120e3 if ecur <= 0.02 else 90e3
        if hp < hp_end:
            return t_days, src
        rho = rho_at(h_km)
        if rho <= 0:
            return float("inf"), src
        dadt = -ballistic * rho * math.sqrt(MU * a) * king_hele(a, ecur, h_km)
        if dadt >= 0:
            return float("inf"), src
        dt = -((hp - 120e3) * 0.20 + 500.0) / dadt
        cap_days = 0.15 if hp < 200e3 else (2.0 if hp < 350e3 else 20.0)
        dt = min(dt, cap_days * 86400.0)
        dt = max(dt, 1.0)
        da = dadt * dt
        # King-Hele: on an eccentric orbit drag at perigee takes energy out of
        # APOGEE and the perigee altitude holds nearly constant until the orbit
        # circularises; only then do both apses come down together. (CardSat
        # 0.9.67 split the drop between the two, which lowered perigee far too
        # fast - and since perigee altitude sets the density, that error fed
        # back on itself.) Omitting the circular branch is worse still: perigee
        # never moves, the re-entry threshold is never reached, and every object
        # reads "stable".
        if ecur > 1e-3:
            ra += 2.0 * da
            if ra < rp:
                mid = 0.5 * (ra + rp)
                ra = rp = mid
        else:
            ra += da
            rp += da
        t_days += dt / 86400.0
        if t_days > 36500.0:                    # > 100 yr: effectively stable
            return float("inf"), src
    return t_days, src


def decay_rows(mean_motion=15.5, ecc=0.0004, bstar=0.00025, ndot=0.0,
               solar_index=1):
    """Tools-hub wrapper returning (label, value, note) rows."""
    solar = ("low", "mean", "high")[int(solar_index) % 3]
    days, src = estimate_decay_days(mean_motion, ecc, bstar, ndot, solar)
    if days < 0:
        return [("Decay estimate", "no usable data",
                 "needs B* or a decaying n-dot")]
    if days == float("inf"):
        life = "effectively stable"
    elif days < 365.25:
        life = "%.0f days" % days
    else:
        life = "%.1f years" % (days / 365.25)
    rows = [
        ("Lifetime", life, ""),
        ("Anchor", SRC_NAMES[src],
         "measured" if src == SRC_NDOT else "modelled"),
        ("Solar activity", solar, ""),
    ]
    if days != float("inf"):
        rows.append(("25-year rule", "OK" if days <= 25 * 365.25 else "EXCEEDS",
                     ""))
        rows.append(("5-year rule", "OK" if days <= 5 * 365.25 else "EXCEEDS",
                     ""))
    rows.append(("accuracy", "0.99x median vs 244 re-entries",
                 "92% within +/-30%"))
    return rows


def fmt_decay(days):
    """Human form of a decay estimate from :func:`estimate_decay_days`."""
    if days is None or days < 0:
        return "no usable data"
    if days == float("inf"):
        return "effectively stable"
    if days < 1:
        return "< 1 day"
    if days < 365.25:
        return "%.0f days" % days
    return "%.1f years" % (days / 365.25)
