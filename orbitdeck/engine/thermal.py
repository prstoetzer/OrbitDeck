"""orbitdeck.engine.thermal - first-order orbital thermal model for a cubesat.

A single isothermal node balances absorbed solar, Earth albedo, Earth IR and
internal dissipation against radiation to space, around one orbit. The orbital
environment is analytic - beta angle from inclination/RAAN/epoch, eclipse
fraction from cylindrical-shadow geometry - so no propagation is needed and a
paper orbit with no catalog entry works exactly like a real one.

Ported from CardSat 0.9.75's SCR_THERMAL. This is an **educational first-order
model**, not a flight thermal analysis: one node, no conduction, no internal
gradients, constant properties, grey surfaces.
"""

import math

RE_KM = 6378.137
SIGMA = 5.670374419e-8        # Stefan-Boltzmann, W/m^2/K^4
S0 = 1361.0                   # solar constant, W/m^2
ALBEDO = 0.30                 # Earth bond albedo
EARTH_IR = 237.0              # Earth IR emission, W/m^2
CP_ALUMINIUM = 900.0          # J/kg/K, aluminium-dominated bus

ATTITUDE = ["Tumbling", "Sun-pointing"]


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def eclipse_fraction(alt_km, beta_deg):
    """Fraction of a circular orbit spent in Earth's shadow (cylindrical model).

    Returns 0.0 when |beta| exceeds beta* (continuous sunlight).
    """
    re_r = RE_KM / (RE_KM + alt_km)
    beta_star = math.degrees(math.acos(_clamp(re_r, -1.0, 1.0)))
    if abs(beta_deg) >= beta_star:
        return 0.0
    cb = math.cos(math.radians(beta_deg))
    if cb <= 1e-6:
        return 0.0
    num = math.sqrt(max(0.0, 1.0 - re_r * re_r)) / cb
    return math.acos(_clamp(num, -1.0, 1.0)) / math.pi


def geometry(units=3, attitude_index=0):
    """External, sun-facing and Earth-facing areas (m^2) for a stack of N U's."""
    u = max(1, int(units))
    side = 0.1
    len_z = 0.1 * u
    a_end = side * side
    a_long = side * len_z
    a_tot = 2.0 * a_end + 4.0 * a_long
    # sun-pointing presents the largest single face; tumbling gets the convex
    # body-average projected area (A/4)
    a_sun = max(a_end, a_long) if int(attitude_index) == 1 else a_tot / 4.0
    return a_tot, a_sun, a_tot / 4.0


def orbital_thermal(alt_km=550.0, units=3, mass_kg=4.0, alpha=0.35, eps=0.85,
                    power_w=2.0, beta_deg=0.0, attitude_index=0):
    """Equilibrium and transient node temperatures over one orbit.

    Returns a dict with beta, eclipse fraction, period, the sunlit/eclipse
    equilibrium temperatures and the settled transient min/max/mean (all deg C).
    """
    h = max(100.0, float(alt_km))
    m = max(0.1, float(mass_kg))
    a = _clamp(float(alpha), 0.05, 1.0)
    e = _clamp(float(eps), 0.05, 1.0)
    p = max(0.0, float(power_w))
    a_tot, a_sun, a_earth = geometry(units, attitude_index)
    re_r = RE_KM / (RE_KM + h)
    f_earth = re_r * re_r                       # nadir view factor
    fe = eclipse_fraction(h, beta_deg)

    def q_in(sun):
        return (a * S0 * a_sun * sun
                + a * ALBEDO * S0 * a_earth * f_earth * sun
                + e * EARTH_IR * a_earth * f_earth
                + p)

    def t_eq(sun):
        denom = e * SIGMA * a_tot
        return (q_in(sun) / denom) ** 0.25 if denom > 0 else 0.0

    t_sun = t_eq(1.0)
    t_ecl = t_eq(0.0)

    # transient: integrate two orbits so the cycle settles, record the second
    mu = 398600.4418
    a_km = RE_KM + h
    period_s = 2.0 * math.pi * math.sqrt(a_km ** 3 / mu)
    heat_cap = m * CP_ALUMINIUM
    ecl_start = period_s * (1.0 - fe)
    t = t_sun
    tmin = tmax = t
    steps = 240
    dt = period_s / steps
    for orbit in range(2):
        tt = 0.0
        for _k in range(steps):
            sun = 1.0 if tt < ecl_start else 0.0
            q_out = e * SIGMA * a_tot * t ** 4
            t += (q_in(sun) - q_out) / heat_cap * dt
            t = max(3.0, t)                     # deep-space floor guard
            if orbit == 1:
                tmin = min(tmin, t)
                tmax = max(tmax, t)
            tt += dt
    return {
        "beta_deg": beta_deg,
        "eclipse_frac": fe,
        "period_min": period_s / 60.0,
        "area_total_m2": a_tot,
        "area_sun_m2": a_sun,
        "t_sun_c": t_sun - 273.15,
        "t_eclipse_c": t_ecl - 273.15,
        "t_min_c": tmin - 273.15,
        "t_max_c": tmax - 273.15,
        "t_mean_c": 0.5 * (tmin + tmax) - 273.15,
        "swing_c": tmax - tmin,
    }


def thermal_rows(alt_km=550.0, units=3, mass_kg=4.0, alpha=0.35, eps=0.85,
                 power_w=2.0, beta_deg=0.0, attitude_index=0):
    """Tools-hub wrapper returning (label, value, note) rows."""
    r = orbital_thermal(alt_km, units, mass_kg, alpha, eps, power_w, beta_deg,
                        attitude_index)
    return [
        ("Beta angle", "%+.1f deg" % r["beta_deg"], ""),
        ("Eclipse fraction", "%.1f %%" % (r["eclipse_frac"] * 100),
         "continuous sun" if r["eclipse_frac"] == 0 else ""),
        ("Orbit period", "%.1f min" % r["period_min"], ""),
        ("Radiating area", "%.4f m2" % r["area_total_m2"], ""),
        ("Sun-facing area", "%.4f m2" % r["area_sun_m2"],
         ATTITUDE[int(attitude_index) % 2]),
        ("Sunlit equilib", "%.0f C" % r["t_sun_c"], ""),
        ("Eclipse equilib", "%.0f C" % r["t_eclipse_c"], ""),
        ("Transient min", "%.0f C" % r["t_min_c"], ""),
        ("Transient max", "%.0f C" % r["t_max_c"], ""),
        ("Mean / swing", "%.0f C / %.0f C" % (r["t_mean_c"], r["swing_c"]), ""),
        ("model", "first-order, single node", "not flight analysis"),
    ]
