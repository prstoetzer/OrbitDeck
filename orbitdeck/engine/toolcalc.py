"""orbitdeck.engine.toolcalc - bench calculators ported from CardSat.

Pure, GUI-free functions for the antenna / feedline / RF / electronics / and
terrestrial-propagation calculators that CardSat carries in its Tools hub. Each
function returns a list of (label, value_string, note) rows so a GUI or terminal
screen can render them uniformly, mirroring CardSat's live-recalc form tools.

The formulas are ported faithfully from the CardSat firmware (src/app.cpp); the
radio- and rotator-control tools are intentionally excluded (out of scope for
OrbitDeck), but the pure computational tools are all fair game.

Every function is deterministic and takes plain numbers, so they are trivially
unit-testable and reusable from both the desktop GUI and OrbitTerm.
"""

import math

C_M_S = 299792458.0            # speed of light, m/s
C_KM_S = 299792.458            # speed of light, km/s
C_FTMHZ = 983.571             # ft*MHz reference


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _ftin(feet):
    """Feet (decimal) -> a 'X ft Y.Y in' string."""
    if feet < 0:
        return "-" + _ftin(-feet)
    ft = int(feet)
    inches = (feet - ft) * 12.0
    return "%d ft %.1f in" % (ft, inches)


def _antlen(feet):
    """Antenna length in both ft-in and meters, as CardSat's antLen() does."""
    return "%s (%.3f m)" % (_ftin(feet), feet * 0.3048)


def row(label, value, note=""):
    return (label, value, note)


# --------------------------------------------------------------------------
# Antennas & feedline
# --------------------------------------------------------------------------
def dipole(freq_mhz):
    """Half-wave dipole (468/f with end effect)."""
    f = freq_mhz
    if f <= 0:
        return [row("error", "freq must be > 0")]
    L = 468.0 / f
    return [
        row("Total length", _antlen(L)),
        row("Each leg", _antlen(L / 2)),
    ]


def vertical(freq_mhz):
    """Quarter-wave vertical / ground plane (234/f), radials ~2% longer."""
    f = freq_mhz
    if f <= 0:
        return [row("error", "freq must be > 0")]
    L = 234.0 / f
    return [
        row("1/4-wave", _antlen(L)),
        row("Radials (4)", _antlen(L * 1.02)),
    ]


def yagi(freq_mhz, elements=3):
    """Starting Yagi element lengths (driven ~ dipole, reflector +5%,
    directors progressively shorter). Real lengths depend on boom/diameter."""
    f = freq_mhz
    if f <= 0:
        return [row("error", "freq must be > 0")]
    n = int(max(2, min(12, elements)))
    dr = 468.0 / f
    out = [
        row("Driven elem", _antlen(dr)),
        row("Reflector", _antlen(dr * 1.05)),
    ]
    for d in range(1, n - 1):
        out.append(row("Director %d" % d, _antlen(dr * (0.95 - 0.01 * (d - 1)))))
    out.append(row("Spacing 0.2wl", _antlen(0.2 * C_FTMHZ / f), "starting point"))
    return out


def quad(freq_mhz, elements=2):
    """Full-wave quad loop (1005/f ft), reflector ~2.5% larger."""
    f = freq_mhz
    if f <= 0:
        return [row("error", "freq must be > 0")]
    n = int(max(2, min(8, elements)))
    loop = 1005.0 / f
    out = [
        row("Driven loop", _antlen(loop)),
        row("  each side", _antlen(loop / 4)),
        row("Refl loop", _antlen(1030.0 / f)),
    ]
    for d in range(1, n - 1):
        out.append(row("Dir %d loop" % d, _antlen(975.0 / f)))
    return out


def helix(freq_mhz, turns=8, circumf_wl=1.05, pitch_deg=12.5):
    """Axial-mode helix: gain, dimensions and beamwidth.

    Standard Kraus axial-mode relations. C = circumference in wavelengths,
    S = turn spacing, gain ~ 12 * C^2 * n * S(wl)."""
    f = freq_mhz
    if f <= 0 or turns < 1:
        return [row("error", "need freq > 0 and turns >= 1")]
    lam = C_M_S / (f * 1e6)                     # wavelength, m
    C = circumf_wl * lam                        # circumference, m
    dia = C / math.pi                           # diameter, m
    spacing = C * math.tan(math.radians(pitch_deg))  # turn spacing, m
    s_wl = spacing / lam
    axial_len = turns * spacing
    gain_lin = 12.0 * circumf_wl * circumf_wl * turns * s_wl
    gain_db = 10.0 * math.log10(gain_lin) if gain_lin > 0 else 0.0
    hpbw = 52.0 / (circumf_wl * math.sqrt(turns * s_wl)) if s_wl > 0 else 0.0
    return [
        row("Wavelength", "%.3f m" % lam),
        row("Diameter", "%.1f mm" % (dia * 1000)),
        row("Turn spacing", "%.1f mm" % (spacing * 1000)),
        row("Axial length", "%.3f m" % axial_len),
        row("Gain", "%.1f dBi" % gain_db),
        row("Beamwidth", "%.0f deg" % hpbw),
        row("AR (end-fire)", "%.2f" % ((2.0 * turns + 1.0) / (2.0 * turns))),
    ]


def wavelength(freq_mhz):
    """Free-space wavelength and common cut lengths."""
    f = freq_mhz
    if f <= 0:
        return [row("error", "freq must be > 0")]
    lam = 299.792458 / f                         # m
    q, h, fe = lam / 4.0, lam / 2.0, lam * 0.625
    return [
        row("Wavelength", "%.3f m" % lam, _ftin(lam / 0.3048)),
        row("1/4 wave", "%.3f m" % q, _ftin(q / 0.3048)),
        row("1/2 wave", "%.3f m" % h, _ftin(h / 0.3048)),
        row("5/8 wave", "%.3f m" % fe, _ftin(fe / 0.3048)),
    ]


# coax presets: (name, velocity factor, loss constants). Loss model matched to
# CardSat: matched loss dB/100ft = k1*sqrt(f_MHz) + k2*f_MHz.
COAX_TYPES = [
    # name,           vf,    k1,       k2
    ("RG-58",        0.66, 0.1400,  0.00050),
    ("RG-8X",        0.82, 0.0900,  0.00035),
    ("RG-213",       0.66, 0.0600,  0.00022),
    ("LMR-240",      0.84, 0.0630,  0.00028),
    ("LMR-400",      0.85, 0.0390,  0.00015),
    ("LMR-600",      0.87, 0.0240,  0.00011),
    ("Hardline 1/2", 0.88, 0.0180,  0.00007),
]
COAX_NAMES = [c[0] for c in COAX_TYPES]


def coax_loss(coax_index, freq_mhz, length_ft, swr=1.5):
    """Matched loss, total loss including SWR, and delivered power.

    Loss model: dB/100ft = k1*sqrt(f) + k2*f, faithful to CardSat's table form.
    """
    ci = max(0, min(len(COAX_TYPES) - 1, int(coax_index)))
    name, vf, k1, k2 = COAX_TYPES[ci]
    f = freq_mhz
    if f <= 0 or length_ft <= 0:
        return [row("error", "need freq and length > 0")]
    ml_100 = k1 * math.sqrt(f) + k2 * f          # dB per 100 ft
    ml = ml_100 * (length_ft / 100.0)            # matched loss, dB
    s = max(1.0, swr)
    g = (s - 1.0) / (s + 1.0)
    a = 10.0 ** (ml / 10.0)
    num = a * a - g * g
    den = a * (1.0 - g * g)
    tot = 10.0 * math.log10(num / den) if (den > 0 and num > 0) else ml
    pout = 10.0 ** (-tot / 10.0)
    return [
        row("Cable", name, "VF %.2f" % vf),
        row("Matched loss", "%.2f dB" % ml),
        row("Loss at SWR", "%.2f dB" % tot),
        row("Power out", "%.1f %%" % (pout * 100.0)),
        row("100W in ->", "%.1f W" % (100.0 * pout)),
    ]


# phasing-line fractions
PHASE_FRACS = [("1/4 wave", 0.25), ("1/2 wave", 0.5), ("3/4 wave", 0.75),
               ("full wave", 1.0), ("1/8 wave", 0.125)]
PHASE_FRAC_NAMES = [p[0] for p in PHASE_FRACS]


def phasing_line(coax_index, freq_mhz, frac_index):
    """Physical length of a coax section for a wanted electrical length,
    using the cable velocity factor."""
    ci = max(0, min(len(COAX_TYPES) - 1, int(coax_index)))
    fi = max(0, min(len(PHASE_FRACS) - 1, int(frac_index)))
    name, vf = COAX_TYPES[ci][0], COAX_TYPES[ci][1]
    frac = PHASE_FRACS[fi][1]
    f = freq_mhz
    if f <= 0:
        return [row("error", "freq must be > 0")]
    lam = 299.792458 / f                          # m free-space
    phys_m = lam * frac * vf
    return [
        row("VF", "%.2f (%s)" % (vf, name)),
        row("Wavelength", "%.3f m free-sp" % lam),
        row("Length", _antlen(phys_m / 0.3048)),
        row("  metric", "%.3f m" % phys_m, "%.1f cm" % (phys_m * 100)),
    ]


# --------------------------------------------------------------------------
# RF & measurement
# --------------------------------------------------------------------------
def rf_units(power_w):
    """Cross-convert power in W, dBm, dBW and voltage into 50 ohm."""
    w = power_w if power_w > 0 else 1e-6
    dbm = 10.0 * math.log10(w) + 30.0
    vrms = math.sqrt(w * 50.0)
    return [
        row("dBm", "%.2f dBm" % dbm),
        row("dBW", "%.2f dBW" % (dbm - 30.0)),
        row("Vrms @50ohm", "%.2f V" % vrms),
        row("Vpp @50ohm", "%.2f V" % (vrms * 2.828)),
    ]


def swr(swr_value):
    """Return loss, reflection coefficient and mismatch loss from an SWR."""
    s = max(1.0, swr_value)
    g = (s - 1.0) / (s + 1.0)
    rl = -20.0 * math.log10(g) if g > 0 else 99.0
    refl = g * g * 100.0
    mismatch = -10.0 * math.log10(1 - g * g) if g < 1 else 99.0
    return [
        row("Return loss", "%.2f dB" % rl),
        row("Refl coeff", "%.4f" % g),
        row("Power refl", "%.1f %%" % refl),
        row("Mismatch", "%.3f dB" % mismatch),
    ]


def fspl(distance_km, freq_mhz):
    """Free-space path loss in dB."""
    d, f = distance_km, freq_mhz
    if d <= 0 or f <= 0:
        return [row("error", "need distance and freq > 0")]
    loss = 20.0 * math.log10(d) + 20.0 * math.log10(f) + 32.44
    return [
        row("Path loss", "%.1f dB" % loss),
        row("At 1W EIRP", "%.1f dBm" % (-loss + 30.0)),
    ]


def attenuator(atten_db, z0=50.0):
    """Resistive pi- and T-pad resistor values for a wanted attenuation."""
    K = 10.0 ** (atten_db / 20.0)
    if K <= 1.0 or z0 <= 0:
        return [row("error", "need atten > 0 dB")]
    pi_shunt = z0 * (K + 1.0) / (K - 1.0)
    pi_series = z0 * (K * K - 1.0) / (2.0 * K)
    t_series = z0 * (K - 1.0) / (K + 1.0)
    t_shunt = z0 * (2.0 * K) / (K * K - 1.0)
    return [
        row("Pi shunt", "%.1f ohm x2" % pi_shunt),
        row("Pi series", "%.1f ohm" % pi_series),
        row("T series", "%.1f ohm x2" % t_series),
        row("T shunt", "%.1f ohm" % t_shunt),
        row("power ratio", "%.1f:1" % (10.0 ** (atten_db / 10.0))),
    ]


def db_chain(*stages_db):
    """Sum a gain/loss chain (dB) and show the linear ratios."""
    total = sum(stages_db)
    return [
        row("Net gain", "%.2f dB" % total),
        row("Power ratio", "%.4f x" % (10.0 ** (total / 10.0))),
        row("Voltage x", "%.4f x" % (10.0 ** (total / 20.0))),
        row("100W in ->", "%.2f W" % (100.0 * 10.0 ** (total / 10.0))),
    ]


def cascade_nf(ant_gain_dbi=16.0, sky_temp_k=150.0, lna_nf_db=0.8,
               lna_gain_db=20.0, coax_loss_db=3.0, rig_nf_db=6.0):
    """Friis cascade for antenna -> LNA -> coax -> rig: system NF, Te, and G/T."""
    # stage noise factors (linear)
    f_lna = 10.0 ** (lna_nf_db / 10.0)
    g_lna = 10.0 ** (lna_gain_db / 10.0)
    l_coax = 10.0 ** (coax_loss_db / 10.0)       # loss as a factor >1
    f_coax = l_coax                              # passive: F = loss
    f_rig = 10.0 ** (rig_nf_db / 10.0)
    # Friis: F = F1 + (F2-1)/G1 + (F3-1)/(G1 G2) ...
    # order: LNA, then coax (gain 1/l_coax), then rig
    g_coax = 1.0 / l_coax
    f_total = f_lna + (f_coax - 1.0) / g_lna + (f_rig - 1.0) / (g_lna * g_coax)
    nf_total = 10.0 * math.log10(f_total)
    te = 290.0 * (f_total - 1.0)                 # equivalent noise temp, K
    tsys = sky_temp_k + te
    g_over_t = ant_gain_dbi - 10.0 * math.log10(tsys)
    return [
        row("System NF", "%.2f dB" % nf_total),
        row("Noise temp", "%.0f K" % te),
        row("System temp", "%.0f K" % tsys),
        row("G/T", "%.1f dB/K" % g_over_t),
    ]


# --------------------------------------------------------------------------
# Electronics & power
# --------------------------------------------------------------------------
def complex_polar(real_a, imag_b):
    """Rectangular <-> polar, plus the reciprocal 1/Z."""
    r = math.hypot(real_a, imag_b)
    th = math.degrees(math.atan2(imag_b, real_a))
    out = [
        row("Magnitude", "%.3f" % r),
        row("Angle", "%.2f deg" % th),
        row("Rect", "%.2f %s j%.2f" % (real_a, "+" if imag_b >= 0 else "-",
                                       abs(imag_b))),
    ]
    d = real_a * real_a + imag_b * imag_b
    if d > 0:
        ra, rb = real_a / d, -imag_b / d
        out.append(row("1/Z", "%.5f %s j%.5f" % (ra, "+" if rb >= 0 else "-",
                                                 abs(rb))))
    else:
        out.append(row("1/Z", "undef (0)"))
    return out


def reactance(freq_mhz, ind_uh, cap_pf):
    """Xl, Xc, net reactance and the L-C resonant frequency."""
    f = freq_mhz * 1e6
    L = ind_uh * 1e-6
    C = cap_pf * 1e-12
    w = 2.0 * math.pi * f
    Xl = w * L
    Xc = 1.0 / (w * C) if (w > 0 and C > 0) else 0.0
    out = [
        row("Xl", "%.1f ohm" % Xl),
        row("Xc", "%.1f ohm" % Xc),
        row("X net", "%.1f ohm" % (Xl - Xc)),
    ]
    if L > 0 and C > 0:
        f0 = 1.0 / (2.0 * math.pi * math.sqrt(L * C))
        out.append(row("Resonance",
                       "%.3f MHz" % (f0 / 1e6) if f0 >= 1e6
                       else "%.1f kHz" % (f0 / 1e3)))
    else:
        out.append(row("Resonance", "need L & C"))
    return out


def rc_time_constant(resist_ohm, cap_uf):
    """RC time constant, the 1..5 tau charge points and the cutoff frequency."""
    R = resist_ohm
    C = cap_uf * 1e-6
    tau = R * C
    if tau >= 1.0:
        ts = "%.3f s" % tau
    elif tau >= 1e-3:
        ts = "%.3f ms" % (tau * 1e3)
    else:
        ts = "%.1f us" % (tau * 1e6)
    fc = 1.0 / (2.0 * math.pi * tau) if tau > 0 else 0.0
    return [
        row("tau (RC)", ts),
        row("1 tau", "63% charged"),
        row("3 tau", "95% charged"),
        row("5 tau ~", "99% (settled)"),
        row("cutoff f", "%.1f Hz" % fc if tau > 0 else "--"),
    ]


def battery_runtime(capacity_ah=20.0, rx_draw_a=0.5, tx_draw_a=8.0,
                    tx_duty_pct=30.0, usable_pct=80.0):
    """Operating hours from a battery under a TX/RX duty cycle."""
    avg = rx_draw_a * (1.0 - tx_duty_pct / 100.0) + tx_draw_a * (tx_duty_pct / 100.0)
    rt = (capacity_ah * (usable_pct / 100.0) / avg) if avg > 0 else 0.0
    hh = int(rt)
    mm = int((rt - hh) * 60.0 + 0.5)
    if mm == 60:
        hh += 1
        mm = 0
    return [
        row("Avg current", "%.2f A" % avg),
        row("Usable cap", "%.1f Ah" % (capacity_ah * usable_pct / 100.0)),
        row("Runtime", "%.2f h" % rt),
        row("  =", "%dh %dm" % (hh, mm)),
        row("Energy", "%.1f Ah used" % (avg * rt)),
    ]


# --------------------------------------------------------------------------
# Terrestrial VHF/UHF/microwave
# --------------------------------------------------------------------------
def radio_horizon(my_haat_m=10.0, their_haat_m=10.0, k_factor=1.33):
    """Line-of-sight horizon for each station and the max LOS path.

    d_km = sqrt(2 * k * Re_km * h_km); with Re=6371 and k the refraction factor.
    """
    Re = 6371.0
    def horizon(h_m):
        return math.sqrt(2.0 * k_factor * Re * (h_m / 1000.0))
    d1 = horizon(my_haat_m)
    d2 = horizon(their_haat_m)
    return [
        row("My horizon", "%.1f km" % d1),
        row("Their horizon", "%.1f km" % d2),
        row("Max LOS path", "%.1f km" % (d1 + d2)),
        row("k factor", "%.2f" % k_factor,
            "raise >1.6 for ducting"),
    ]


def fresnel_zone(path_km=30.0, freq_mhz=144.0):
    """First Fresnel-zone radius at midpoint and the 60% clearance figure."""
    if path_km <= 0 or freq_mhz <= 0:
        return [row("error", "need path and freq > 0")]
    # General form r1 = 17.31 * sqrt(d1*d2 / (f_GHz * D)); at the midpoint
    # d1 = d2 = D/2, which collapses to r1 = 8.657 * sqrt(D_km / f_GHz).
    # (An earlier version applied the /2 twice - once by using the collapsed
    # constant and again explicitly - and reported half the true radius, which
    # would call a marginal path clear.)
    f_ghz = freq_mhz / 1000.0
    r1 = 8.657 * math.sqrt(path_km / f_ghz)
    return [
        row("F1 radius", "%.1f m" % r1, "at midpoint"),
        row("60% clearance", "%.1f m" % (0.6 * r1)),
        row("Path length", "%.1f km" % path_km),
    ]


def rain_fade(freq_ghz=10.0, rain_rate_mm_h=25.0, path_km=10.0):
    """ITU-style specific attenuation and total path fade for a microwave hop.

    gamma = k * R^alpha dB/km, using ITU-R P.838 horizontal-polarization
    coefficients interpolated for the frequency."""
    # A small subset of ITU-R P.838-3 horizontal-pol coefficients (k, alpha).
    # (freq GHz, k, alpha)
    table = [
        (1, 0.0000387, 0.912), (2, 0.000154, 0.963), (4, 0.000650, 1.121),
        (6, 0.00175, 1.308), (8, 0.00454, 1.327), (10, 0.0101, 1.276),
        (12, 0.0188, 1.217), (15, 0.0367, 1.154), (20, 0.0751, 1.099),
        (25, 0.124, 1.061), (30, 0.187, 1.021), (40, 0.350, 0.939),
    ]
    f = freq_ghz
    # linear interpolation in log-k / alpha
    if f <= table[0][0]:
        k, al = table[0][1], table[0][2]
    elif f >= table[-1][0]:
        k, al = table[-1][1], table[-1][2]
    else:
        for i in range(1, len(table)):
            if f <= table[i][0]:
                f0, k0, a0 = table[i - 1]
                f1, k1, a1 = table[i]
                t = (f - f0) / (f1 - f0)
                k = math.exp(math.log(k0) + t * (math.log(k1) - math.log(k0)))
                al = a0 + t * (a1 - a0)
                break
    gamma = k * (rain_rate_mm_h ** al)           # dB/km
    total = gamma * path_km
    return [
        row("Specific atten", "%.3f dB/km" % gamma),
        row("Total fade", "%.1f dB" % total),
        row("Rain rate", "%.0f mm/h" % rain_rate_mm_h),
        row("Path length", "%.1f km" % path_km),
    ]


def terrestrial_path_budget(tx_power_w=25.0, tx_gain_dbi=6.0, rx_gain_dbi=6.0,
                            line_loss_db=2.0, freq_mhz=146.0, distance_km=50.0):
    """Two-way terrestrial link budget: received level and margin.

    Uses FSPL plus a nominal thermal noise floor for a verdict."""
    if distance_km <= 0 or freq_mhz <= 0:
        return [row("error", "need distance and freq > 0")]
    loss = 20.0 * math.log10(distance_km) + 20.0 * math.log10(freq_mhz) + 32.44
    tx_dbm = 10.0 * math.log10(tx_power_w * 1000.0)
    eirp = tx_dbm + tx_gain_dbi - line_loss_db
    rx_level = eirp - loss + rx_gain_dbi - line_loss_db
    # nominal noise floor: kTB for ~12 kHz FM channel + 10 dB NF
    noise_floor = -174.0 + 10.0 * math.log10(12000.0) + 10.0
    margin = rx_level - noise_floor
    verdict = "workable" if margin > 10 else ("marginal" if margin > 0 else "no path")
    return [
        row("FSPL", "%.1f dB" % loss),
        row("EIRP", "%.1f dBm" % eirp),
        row("RX level", "%.1f dBm" % rx_level),
        row("Noise floor", "%.1f dBm" % noise_floor),
        row("Margin", "%.1f dB" % margin),
        row("Verdict", verdict),
    ]


# --------------------------------------------------------------------------
# lookup tables (ported from CardSat)
# --------------------------------------------------------------------------
# Toroid cores: (name, AL, is_ferrite, mm_per_turn). Iron AL = uH/100t;
# ferrite AL = mH/1000t (Amidon conventions).
TOROID_CORES = [
    ("T37-2", 40.0, False, 25), ("T37-6", 30.0, False, 25),
    ("T50-2", 49.0, False, 32), ("T50-6", 40.0, False, 32),
    ("T68-2", 57.0, False, 41), ("T68-6", 47.0, False, 41),
    ("T106-2", 135.0, False, 62), ("T130-2", 110.0, False, 73),
    ("T200-2", 120.0, False, 100),
    ("FT37-43", 350.0, True, 25), ("FT50-43", 523.0, True, 33),
    ("FT82-43", 557.0, True, 52), ("FT114-43", 603.0, True, 70),
    ("FT140-43", 952.0, True, 86),
    ("FT37-61", 55.3, True, 25), ("FT50-61", 68.0, True, 33),
]
TOROID_NAMES = [t[0] for t in TOROID_CORES]

# Thermal-surface materials: (name, absorptivity a, emissivity e)
THERM_MATERIALS = [
    ("Custom", 0.25, 0.85), ("White paint", 0.25, 0.88),
    ("Black anodize", 0.95, 0.90), ("Solar cell", 0.75, 0.83),
    ("Polished Al", 0.20, 0.08), ("Gold / MLI", 0.25, 0.03),
    ("Kapton (alum)", 0.40, 0.60),
]
THERM_NAMES = [m[0] for m in THERM_MATERIALS]

# Faraday ionosphere presets: (name, slant TEC in TECU)
FARADAY_CONDS = [("Quiet (10 TECU)", 10), ("Moderate (30)", 30),
                 ("Storm (80)", 80)]
FARADAY_NAMES = [f[0] for f in FARADAY_CONDS]

# Chassis-wiring ampacity: (AWG, amps)
WIRE_AMPACITY = [(10, 55), (12, 41), (14, 32), (16, 22), (18, 16),
                 (20, 11), (22, 7), (24, 3.5), (26, 2.2), (28, 1.4)]

# CubeSat form-factor presets for cross-section: (name, x_cm, y_cm, z_cm)
XSEC_PRESETS = [
    ("1U", 10, 10, 10), ("2U", 10, 10, 20), ("3U", 10, 10, 30),
    ("6U", 10, 20, 30), ("12U", 20, 20, 30), ("16U", 20, 20, 40),
    ("0.5U", 10, 10, 5), ("Custom", 10, 10, 10),
]
XSEC_NAMES = [x[0] for x in XSEC_PRESETS]

MATCH_TOPOLOGIES = ["L-network", "Pi", "T"]
USTRIP_MODES = ["Microstrip", "Stripline"]
AMPAC_MODES = ["PCB external", "PCB internal", "Wire (AWG)"]

# RF-exposure duty presets: (name, duty %)
RFDUTY_PRESETS = [("SSB 20%", 20), ("FM/data 100%", 100), ("CW 40%", 40),
                  ("FT8 50%", 50)]
RFDUTY_NAMES = [d[0] for d in RFDUTY_PRESETS]


# --------------------------------------------------------------------------
# RF & measurement (remaining)
# --------------------------------------------------------------------------
def _mpe_uncontrolled(f):
    if f < 1.34:
        return 100.0
    if f < 30:
        return 180.0 / (f * f)
    if f < 300:
        return 0.2
    if f < 1500:
        return f / 1500.0
    return 1.0


def _mpe_controlled(f):
    if f < 3.0:
        return 100.0
    if f < 30:
        return 900.0 / (f * f)
    if f < 300:
        return 1.0
    if f < 1500:
        return f / 300.0
    return 5.0


def _mpe_dist_cm(power_w, gain_dbi, duty_pct, s_limit):
    if s_limit <= 0:
        return 0.0
    p_mw = power_w * 1000.0 * (duty_pct / 100.0)
    g = 10.0 ** (gain_dbi / 10.0)
    return math.sqrt(p_mw * g / (4.0 * math.pi * s_limit))


def rf_exposure(freq_mhz=146.0, power_w=100.0, duty_index=0, gain_dbi=2.15):
    """FCC OET-65 far-field MPE limits and estimated compliance distances."""
    di = max(0, min(len(RFDUTY_PRESETS) - 1, int(duty_index)))
    duty = RFDUTY_PRESETS[di][1]
    mu = _mpe_uncontrolled(freq_mhz)
    mc = _mpe_controlled(freq_mhz)
    du = _mpe_dist_cm(power_w, gain_dbi, duty, mu) / 100.0
    dc = _mpe_dist_cm(power_w, gain_dbi, duty, mc) / 100.0
    return [
        row("Unctrl MPE", "%.3f mW/cm2" % mu),
        row("  distance", "%.2f m" % du),
        row("Ctrl MPE", "%.3f mW/cm2" % mc),
        row("  distance", "%.2f m" % dc),
        row("Avg power", "%.1f W" % (power_w * duty / 100.0)),
        row("+reflect x2", "%.2f m unc" % (du * 2.0), "not a station eval"),
    ]


def imd_products(f1_mhz=145.900, f2_mhz=145.950, band_low=145.800,
                 band_high=146.000):
    """Odd-order intermodulation products of two carriers; flags in-band ones."""
    def flag(f):
        return "IN" if band_low <= f <= band_high else "out"
    p3a, p3b = 2 * f1_mhz - f2_mhz, 2 * f2_mhz - f1_mhz
    p5a, p5b = 3 * f1_mhz - 2 * f2_mhz, 3 * f2_mhz - 2 * f1_mhz
    return [
        row("Spacing", "%.1f kHz" % (abs(f2_mhz - f1_mhz) * 1000)),
        row("3rd 2f1-f2", "%.4f" % p3a, flag(p3a)),
        row("3rd 2f2-f1", "%.4f" % p3b, flag(p3b)),
        row("5th 3f1-2f2", "%.4f" % p5a, flag(p5a)),
        row("5th 3f2-2f1", "%.4f" % p5b, flag(p5b)),
    ]


def sun_noise_gt(y_factor_db=1.0, solar_flux_sfu=150.0, freq_mhz=435.0,
                 ant_gain_dbi=0.0):
    """Turn a measured sun-noise Y-factor into a station G/T (point-source form)."""
    KB = 1.380649e-23
    y = 10.0 ** (y_factor_db / 10.0)
    S = solar_flux_sfu * 1e-22                    # sfu -> W/m^2/Hz
    lam = 299.792458 / freq_mhz if freq_mhz > 0 else 1.0
    if y > 1 and S > 0:
        gt = 10.0 * math.log10((y - 1.0) * 8.0 * math.pi * KB / (lam * lam * S))
    else:
        gt = -99.0
    out = [row("G/T", "%.2f dB/K" % gt)]
    if ant_gain_dbi > 0:
        out.append(row("T sys @gain",
                       "%.0f K" % (10.0 ** ((ant_gain_dbi - gt) / 10.0))))
    out.append(row("Sun size", "0.53 deg (point src)", "enter flux AT freq"))
    return out


# --------------------------------------------------------------------------
# Antennas & feedline (remaining)
# --------------------------------------------------------------------------
def match_network(topology_index=0, r_source=50.0, r_load=200.0,
                  freq_mhz=14.2, loaded_q=5.0):
    """L / Pi / T impedance-matching network component values (lowpass forms)."""
    topo = max(0, min(2, int(topology_index)))
    R1, R2, f = r_source, r_load, freq_mhz * 1e6
    if R1 <= 0 or R2 <= 0 or f <= 0:
        return [row("error", "need R, R, f > 0")]
    w = 2 * math.pi * f
    def Lu(X):
        return "%.3f uH" % (X / w * 1e6)
    def Cp(X):
        return "%.1f pF" % (1.0 / (w * X) * 1e12)
    Rb, Rs = (R1, R2) if R1 > R2 else (R2, R1)
    Qmin = math.sqrt(Rb / Rs - 1.0) if Rb > Rs else 0.0
    if topo == 0:
        if Rb == Rs:
            return [row("R1 == R2", "no L-net needed")]
        Xs, Xp = Qmin * Rs, Rb / Qmin
        return [
            row("Network Q", "%.2f" % Qmin),
            row("Series L", Lu(Xs) + " @lowR"),
            row("Shunt C", Cp(Xp) + " @highR"),
            row("or HP: ser C", Cp(Xs)),
            row("   shunt L", Lu(Xp)),
        ]
    if topo == 1:
        if loaded_q <= Qmin:
            return [row("Q too low", "need > %.2f" % Qmin)]
        Rv = Rb / (loaded_q * loaded_q + 1.0)
        Q2 = math.sqrt(Rs / Rv - 1.0)
        XpB, XsB = Rb / loaded_q, loaded_q * Rv
        XpS, XsS = Rs / Q2, Q2 * Rv
        Xl = XsB + XsS
        XcSrc = XpB if R1 >= R2 else XpS
        XcLoad = XpB if R2 > R1 else XpS
        return [
            row("C @source", Cp(XcSrc)),
            row("Series L", Lu(Xl)),
            row("C @load", Cp(XcLoad)),
            row("min Q", "%.2f" % Qmin),
        ]
    # T
    if loaded_q <= Qmin:
        return [row("Q too low", "need > %.2f" % Qmin)]
    Xl1, B = loaded_q * R1, R1 * (1.0 + loaded_q * loaded_q)
    if B / R2 <= 1.0:
        return [row("Q too low", "for this ratio")]
    Xl2 = R2 * math.sqrt(B / R2 - 1.0)
    Xc = B / (loaded_q + Xl2 / R2)
    return [
        row("L @source", Lu(Xl1)),
        row("Shunt C", Cp(Xc)),
        row("L @load", Lu(Xl2)),
        row("min Q", "%.2f" % Qmin),
    ]


def microstrip(mode_index=0, er=4.4, h_mm=1.6, w_mm=3.0, freq_mhz=435.0):
    """Characteristic impedance of a microstrip or stripline PCB trace."""
    mode = max(0, min(1, int(mode_index)))
    if er < 1 or h_mm <= 0 or w_mm <= 0:
        return [row("error", "need er>=1, H, W > 0")]
    if mode == 0:
        u = w_mm / h_mm
        eeff = ((er + 1) / 2.0 + (er - 1) / 2.0 * (1.0 + 12.0 / u) ** -0.5
                + (0.04 * (1 - u) ** 2 * (er - 1) / 2.0 if u < 1 else 0.0))
        if u <= 1:
            z0 = (60.0 / math.sqrt(eeff)) * math.log(8.0 / u + u / 4.0)
        else:
            z0 = 120.0 * math.pi / (math.sqrt(eeff)
                                    * (u + 1.393 + 0.667 * math.log(u + 1.444)))
    else:
        z0 = (60.0 / math.sqrt(er)) * math.log(1.9 * h_mm / (0.8 * w_mm))
        eeff = er
    out = [
        row("Z0", "%.1f ohm" % z0),
        row("e-eff", "%.2f" % eeff),
    ]
    if freq_mhz > 0:
        q = 74948.1 / (freq_mhz * math.sqrt(eeff))
        out.append(row("90deg line", "%.1f mm" % q))
        out.append(row("Guided wl", "%.1f mm" % (4 * q)))
    return out


def toroid_winding(core_index=2, target_uh=10.0):
    """Turns needed on an Amidon toroid core for a target inductance."""
    ci = max(0, min(len(TOROID_CORES) - 1, int(core_index)))
    name, al, ferrite, mm_turn = TOROID_CORES[ci]
    if ferrite:
        n = 1000.0 * math.sqrt((target_uh / 1000.0) / al)
    else:
        n = 100.0 * math.sqrt(target_uh / al)
    N = max(1, math.ceil(n - 1e-9))
    if ferrite:
        act = al * (N / 1000.0) ** 2 * 1000.0
    else:
        act = al * (N / 100.0) ** 2
    return [
        row("Core", name, "ferrite" if ferrite else "iron powder"),
        row("Turns", "%d" % N),
        row("Actual L", "%.2f uH" % act),
        row("AL", "%.1f %s" % (al, "mH/1k t" if ferrite else "uH/100t")),
        row("Wire approx", "%.0f cm +lead" % (N * mm_turn / 10.0)),
    ]


# --------------------------------------------------------------------------
# Electronics & power (remaining)
# --------------------------------------------------------------------------
def cross_section(preset_index=2, x_cm=10.0, y_cm=10.0, z_cm=30.0,
                  panel_m2=0.0):
    """Projected cross-sectional area of a rectangular body (+ optional panels)."""
    pi = max(0, min(len(XSEC_PRESETS) - 1, int(preset_index)))
    name = XSEC_PRESETS[pi][0]
    if name != "Custom":
        x_cm, y_cm, z_cm = XSEC_PRESETS[pi][1:]
    a, b, c = x_cm / 100.0, y_cm / 100.0, z_cm / 100.0
    ab, bc, ca = a * b, b * c, c * a
    minf = min(ab, bc, ca)
    maxf = max(ab, bc, ca)
    maxproj = math.sqrt(ab * ab + bc * bc + ca * ca)
    tumble = (ab + bc + ca) / 2.0
    return [
        row("Form", name),
        row("End-on min", "%.4f m2" % minf),
        row("Broadside", "%.4f m2" % (maxf + panel_m2)),
        row("Max any ang", "%.4f m2" % (maxproj + panel_m2)),
        row("Tumbling avg", "%.4f m2" % (tumble + panel_m2 / 2.0)),
        row("-> debris Area", "%.4f" % (tumble + panel_m2 / 2.0)),
    ]


def thermal_equilibrium(material_index=1, custom_a=0.25, custom_e=0.85):
    """Flat-plate solar-equilibrium temperature from absorptivity/emissivity."""
    mi = max(0, min(len(THERM_MATERIALS) - 1, int(material_index)))
    if mi == 0:
        a, e = custom_a, custom_e
    else:
        a, e = THERM_MATERIALS[mi][1], THERM_MATERIALS[mi][2]
    S, SIG = 1361.0, 5.670374419e-8
    if a <= 0 or e <= 0:
        return [row("error", "need a, e > 0")]
    t1 = (a * S / (e * SIG)) ** 0.25
    t2 = (a * S / (2.0 * e * SIG)) ** 0.25
    return [
        row("a / e", "%.2f / %.2f = %.2f" % (a, e, a / e)),
        row("1-side rad", "%.0f C (%.0fK)" % (t1 - 273.15, t1)),
        row("2-side rad", "%.0f C (%.0fK)" % (t2 - 273.15, t2)),
        row("Eclipse", "cools to ~ -60..-100C", "1st order, no albedo"),
    ]


def faraday_rotation(freq_mhz=145.9, cond_index=0):
    """Ionospheric Faraday-rotation of a linear signal (order-of-magnitude)."""
    ci = max(0, min(len(FARADAY_CONDS) - 1, int(cond_index)))
    tec = FARADAY_CONDS[ci][1] * 1e16
    B = 4e-5
    def rots(fh):
        return 2.36e4 * B * tec / (fh * fh) / (2 * math.pi)
    return [
        row("Condition", FARADAY_CONDS[ci][0]),
        row("Rotations", "%.1f @entered f" % rots(freq_mhz * 1e6)),
        row("  @146 MHz", "%.1f turns" % rots(146e6)),
        row("  @437 MHz", "%.2f turns" % rots(437e6)),
        row("CP wrong hand", "> 20 dB", "use CP on lin sats"),
    ]


def ampacity(mode_index=0, current_a=1.0, temp_rise_c=10.0, copper_oz=1.0,
             awg=24):
    """Safe current / required trace width (IPC-2221) or wire chassis ampacity."""
    mode = max(0, min(2, int(mode_index)))
    if mode < 2:
        k = 0.048 if mode == 0 else 0.024
        if current_a <= 0 or temp_rise_c <= 0 or copper_oz <= 0:
            return [row("error", "need I, dT, oz > 0")]
        area = (current_a / (k * temp_rise_c ** 0.44)) ** (1.0 / 0.725)  # mil^2
        w_mil = area / (1.378 * copper_oz)
        return [
            row("Trace width", "%.2f mm" % (w_mil * 0.0254)),
            row("  = mils", "%.0f mil" % w_mil),
            row("Cu / rise", "%.1f oz / %.0fC" % (copper_oz, temp_rise_c)),
            row("Std (IPC2221)", "external" if mode == 0 else "internal"),
        ]
    dmm = 0.127 * 92.0 ** ((36.0 - awg) / 39.0)
    A = math.pi * dmm * dmm / 4.0 * 1e-6
    Rm = 1.724e-8 / A * 1000.0
    amp = WIRE_AMPACITY[-1][1]
    for a_awg, a_amps in WIRE_AMPACITY:
        if a_awg >= awg:
            amp = a_amps
            break
    return [
        row("Diameter", "%.2f mm" % dmm),
        row("R", "%.1f mOhm/m" % Rm),
        row("Chassis max", "%.1f A" % amp),
        row("Your load", "%.1f A %s" % (current_a, "OK" if current_a <= amp
                                        else "OVER")),
    ]


def pll_plan(reference_mhz=10.0, r_divider=1.0, n_divider=40.0, multiplier=1.0):
    """Integer-N PLL synthesizer output frequency and step size."""
    if reference_mhz <= 0 or r_divider < 1 or n_divider < 1 or multiplier < 1:
        return [row("error", "need ref, R, N, M >= 1")]
    fpd = reference_mhz / r_divider
    fout = fpd * n_divider * multiplier
    return [
        row("F out", "%.4f MHz" % fout),
        row("F compare", "%.1f kHz" % (fpd * 1000)),
        row("Step", "%.1f kHz" % (fpd * multiplier * 1000)),
        row("Spurs at", "+/-%.0f kHz" % (fpd * multiplier * 1000)),
        row("Ref spur", "+/-%.3f MHz" % (reference_mhz * multiplier)),
    ]


# --------------------------------------------------------------------------
# Terrestrial (remaining)
# --------------------------------------------------------------------------
def tropo_ducting(surface_temp_c=20.0, dewpoint_c=15.0, inversion_dt=0.0):
    """Coarse 0-6 tropospheric-ducting likelihood index from humidity/inversion."""
    depr = surface_temp_c - dewpoint_c
    moist = 3.0 if depr < 2 else (2.0 if depr < 5 else (1.0 if depr < 10 else 0.0))
    inv = (3.0 if inversion_dt >= 4 else (2.0 if inversion_dt >= 2
           else (1.0 if inversion_dt >= 0.5 else 0.0)))
    idx = moist + inv
    word = ("strong duct likely" if idx >= 5 else
            "enhancement possible" if idx >= 3 else
            "weak / marginal" if idx >= 1 else "no ducting expected")
    return [
        row("Duct index", "%.0f / 6" % idx),
        row("Outlook", word),
        row("Dewpt depr", "%.1f C" % depr),
        row("Inversion", "%.1f C" % inversion_dt),
        row("Best on", "coast/eve/morning"),
    ]


# --------------------------------------------------------------------------
# Satellite & orbit tools
# --------------------------------------------------------------------------
def doppler_budget(apogee_alt_km=550.0, perigee_alt_km=550.0, freq_mhz=435.5):
    """Peak Doppler shift and rate to expect for an orbit at a frequency.

    Circularized at the mean altitude; Earth's rotation ignored (<~6% for LEO).
    """
    MU, RE, CKM = 398600.4418, 6378.137, 299792.458
    ap, pe = apogee_alt_km, perigee_alt_km
    if pe > ap:
        ap, pe = pe, ap
    f = freq_mhz * 1e6
    r = RE + 0.5 * (ap + pe)
    if r <= RE:
        return [row("error", "altitude too low")]
    w = math.sqrt(MU / (r * r * r))
    thH = math.acos(RE / r)
    rr_max = 0.0
    for i in range(1, 201):
        th = thH * i / 200.0
        rho = math.sqrt(r * r + RE * RE - 2 * r * RE * math.cos(th))
        rr = r * RE * math.sin(th) * w / rho if rho > 0 else 0.0
        rr_max = max(rr_max, rr)
    rate_tca = r * RE * w * w / (r - RE)
    rho_h = math.sqrt(r * r + RE * RE - 2 * r * RE * math.cos(thH))
    return [
        row("Max Doppler", "+/-%.2f kHz" % (f * rr_max / CKM / 1e3)),
        row("Rate at TCA", "%.1f Hz/s" % (f * rate_tca / CKM)),
        row("per MHz", "+/-%.1f Hz" % (1e6 * rr_max / CKM)),
        row("Max LOS vel", "%.3f km/s" % rr_max),
        row("Period", "%.1f min" % (2 * math.pi / w / 60.0)),
        row("Horizon range", "%.0f km" % rho_h),
    ]


def delta_v(alt1_km=400.0, alt2_km=800.0, plane_change_deg=0.0):
    """Hohmann-transfer and plane-change delta-v between two circular orbits."""
    MU, RE = 398600.4418, 6378.137
    r1, r2 = RE + alt1_km, RE + alt2_km
    di = math.radians(plane_change_deg)
    if r1 <= RE or r2 <= RE:
        return [row("error", "altitude > 0 km")]
    v1, v2 = math.sqrt(MU / r1), math.sqrt(MU / r2)
    at = 0.5 * (r1 + r2)
    dv1 = abs(math.sqrt(MU * (2.0 / r1 - 1.0 / at)) - v1)
    dv2 = abs(v2 - math.sqrt(MU * (2.0 / r2 - 1.0 / at)))
    tt = math.pi * math.sqrt(at ** 3 / MU) / 60.0
    dvp = 2.0 * v2 * math.sin(di / 2.0)
    ad = 0.5 * (r1 + RE + 60.0)
    dvd = v1 - math.sqrt(MU * (2.0 / r1 - 1.0 / ad))
    out = [
        row("Hohmann dv1", "%.1f m/s" % (dv1 * 1000)),
        row("Hohmann dv2", "%.1f m/s" % (dv2 * 1000)),
        row("Total", "%.1f m/s" % ((dv1 + dv2) * 1000)),
        row("Transfer t", "%.1f min" % tt),
    ]
    if di > 0:
        out.append(row("Plane chg", "%.0f m/s @alt2" % (dvp * 1000)))
    out.append(row("Deorbit", "%.1f m/s ->60km" % (dvd * 1000)))
    return out


def pointing_loss(hpbw_deg=30.0, point_err_deg=3.0):
    """Antenna pointing loss (parabolic main-lobe approx L = 12*(err/HPBW)^2 dB)."""
    b, e = hpbw_deg, point_err_deg
    loss = 12.0 * (e / b) ** 2 if b > 0 else 0.0
    out = [
        row("Loss", "%.2f dB" % loss),
        row("1 dB at", "+/-%.1f deg" % (b * 0.2887)),
        row("3 dB at", "+/-%.1f deg" % (b * 0.5)),
    ]
    if e > b * 0.5:
        out.append(row("Note", "approx past HPBW/2"))
    return out


def orbit_lifetime(perigee_alt_km=550.0, mass_kg=4.0, area_m2=0.03, cd=2.2):
    """DEPRECATED - superseded by engine.decay.estimate_decay_days().

    This is the CardSat 0.9.61-era model, kept only for the mass/area/Cd input
    form (the new model works from the element set instead). CardSat 0.9.68
    refit the physics against 244 real re-entries and found the old formula
    combined Cd*A/m = 38*B* with a da/dt a factor of two too large; the errors
    partly canceled at ISS altitude where the constant was tuned, and the model
    predicted roughly a fifth of the true remaining life elsewhere. It also
    lacks the King-Hele eccentricity factor, so it is badly wrong for eccentric
    orbits. Prefer engine.decay for anything quantitative.

    NOT a compliance tool - order-of-magnitude only; use NASA DAS for that."""
    MU, RE = 3.986004418e14, 6378137.0
    ATM = [
        (150, 2.070e-9, 22.523), (180, 5.464e-10, 29.740),
        (200, 2.789e-10, 37.105), (250, 7.248e-11, 45.546),
        (300, 2.418e-11, 53.628), (350, 9.518e-12, 53.298),
        (400, 3.725e-12, 58.515), (450, 1.585e-12, 60.828),
        (500, 6.967e-13, 63.822), (600, 1.454e-13, 71.835),
        (700, 3.614e-14, 88.667), (800, 1.170e-14, 124.64),
        (900, 5.245e-15, 181.05), (1000, 3.019e-15, 268.00),
    ]
    def band(h):
        idx = 0
        for i, b in enumerate(ATM):
            if h >= b[0]:
                idx = i
            else:
                break
        return ATM[idx]
    def density(h):
        h0, rho0, H = band(h)
        return rho0 * math.exp(-(h - h0) / H)
    B = cd * area_m2 / mass_kg
    bc = mass_kg / (cd * area_m2) if cd * area_m2 > 0 else 0.0
    if B <= 0 or perigee_alt_km <= 150.0:
        yr = 0.0
    else:
        t, h = 0.0, perigee_alt_km
        while h > 150.0:
            h_lo = max(150.0, h - 2.0)
            r_mid = RE + ((h + h_lo) / 2.0) * 1000.0
            H = band(h)[2] * 1000.0
            dt = ((1.0 / (B * math.sqrt(MU * r_mid))) * H
                  * (1.0 / density(h) - 1.0 / density(h_lo)))
            if dt > 0:
                t += dt
            h = h_lo
        yr = t / (365.25 * 86400.0)
    life = ("%.0f days" % (yr * 365.25)) if yr < 1.0 else ("%.1f years" % yr)
    return [
        row("Ballistic", "%.1f kg/m2" % bc),
        row("Lifetime", life),
        row("25-yr rule", "OK" if yr <= 25.0 else "EXCEEDS"),
        row("5-yr (new)", "OK" if yr <= 5.0 else "EXCEEDS"),
        row("est only", "use NASA DAS", "nominal Sun +-several x"),
    ]


def link_margin_vs_elevation(altitude_km=550.0, freq_mhz=435.0, margin_at_0_db=6.0):
    """Received-margin gain as a pass climbs in elevation (range-only model).

    Margin(el) = M0 + 20*log10(r0 / range(el)), where range(el) is the slant
    range to a circular orbit at ``altitude_km`` and r0 is the range at the
    horizon (worst case). Shows the free-space part of how much a pass improves
    from AOS to overhead - ported from CardSat's link-margin-vs-elevation curve.
    """
    RE = 6378.137
    h = altitude_km
    if h <= 0 or freq_mhz <= 0:
        return [row("error", "need altitude & freq > 0")]

    def rng(el_deg):
        e = math.radians(el_deg)
        se = math.sin(e)
        return math.sqrt(RE * RE * se * se + 2 * RE * h + h * h) - RE * se

    r0 = rng(0.0)
    out = []
    for el in (0, 10, 20, 30, 45, 60, 90):
        m = margin_at_0_db + 20.0 * math.log10(r0 / rng(el))
        tag = "horizon" if el == 0 else ("overhead (TCA)" if el == 90 else "")
        out.append(row("%2d deg el" % el, "%+.1f dB" % m, tag))
    out.append(row("AOS->TCA gain",
                   "%.1f dB" % (20.0 * math.log10(r0 / rng(90.0)))))
    return out
