"""tools_registry.py - declarative registry of the Tools-hub calculators.

Each entry binds a calculator name to its engine function
(orbitdeck.engine.toolcalc) and a list of input-field specs, so the Tools
screen can render a live-recalc form generically. A field is either numeric
(label, default, unit) or a picker (label, choices, default index). The order of
fields matches the positional arguments of the bound function.
"""

from . import toolcalc as tc
from . import calc as gc
from .thermal import thermal_rows, ATTITUDE
from .decay import decay_rows
from .refdata import char_lookup_rows, zone_lookup
from .linkbudget import link_margin_curve
from .statevector import fit_diagnostics
from .statevector import rv_to_rows
from .terrain import terrain_los_rows


def _num(label, default, unit=""):
    return {"label": label, "default": default, "unit": unit}


def _text(label, default=""):
    """A free-text field (the numeric-only form fields can't carry expressions)."""
    return {"label": label, "default": default, "text": True}


def _pick(label, choices, default=0):
    return {"label": label, "choices": choices, "default": default}


# key -> {name, desc, fn, fields}
def _dxcc_rows(query="JA"):
    hits = zone_lookup(query)
    return hits or [("no match", str(query), "")]


def _margin_rows(alt_km=500.0, freq_mhz=145.8, sens_dbm=-120.0):
    rows = link_margin_curve(alt_km, freq_mhz * 1e6,
                             sensitivity_dbm=sens_dbm, step=10.0)
    return [("%.0f\u00b0 elevation" % r["elevation_deg"],
             "%.1f dBm" % r["rx_dbm"],
             "%+.1f dB margin, %.0f km" % (r["margin_db"], r["slant_km"]))
            for r in rows]


def _fit_rows(rx=6800.0, ry=0.0, rz=0.0, vx=0.0, vy=7.66, vz=0.0):
    d = fit_diagnostics((rx, ry, rz), (vx, vy, vz))
    rows = [("Radius", "%.1f km" % d["r_km"], ""),
            ("Speed", "%.3f km/s" % d["v_kms"], ""),
            ("Circular speed", "%.3f km/s" % d["v_circular_kms"], "at this radius"),
            ("Speed ratio", "%.3f" % d["speed_ratio"], "1.0 = circular"),
            ("Plausible", "yes" if d["plausible"] else "NO", "")]
    for n in d["notes"]:
        rows.append(("", n, ""))
    return rows


TOOLS = {
    # ---- antennas & feedline ----
    "dipole": {
        "name": "Dipole length", "fn": tc.dipole,
        "desc": "Half-wave dipole leg and overall lengths (468/f, end effect).",
        "fields": [_num("Freq", 14.2, "MHz")],
    },
    "vertical": {
        "name": "Vertical / ground plane", "fn": tc.vertical,
        "desc": "Quarter-wave vertical and radial lengths.",
        "fields": [_num("Freq", 146.0, "MHz")],
    },
    "yagi": {
        "name": "Yagi elements", "fn": tc.yagi,
        "desc": "Starting element lengths and spacing for a Yagi.",
        "fields": [_num("Freq", 144.2, "MHz"), _num("Elements", 3)],
    },
    "quad": {
        "name": "Quad (full-wave loop)", "fn": tc.quad,
        "desc": "Full-wave loop dimensions for a quad beam.",
        "fields": [_num("Freq", 50.1, "MHz"), _num("Elements", 2)],
    },
    "helix": {
        "name": "Helix antenna", "fn": tc.helix,
        "desc": "Axial-mode helix gain, dimensions and beamwidth (Kraus).",
        "fields": [_num("Freq", 435.0, "MHz"), _num("Turns", 8),
                   _num("Circumf", 1.05, "wl"), _num("Pitch", 12.5, "deg")],
    },
    "wavelength": {
        "name": "Wavelength / frequency", "fn": tc.wavelength,
        "desc": "Free-space wavelength and common cut lengths.",
        "fields": [_num("Freq", 146.0, "MHz")],
    },
    "coax_loss": {
        "name": "Coax loss / power", "fn": tc.coax_loss,
        "desc": "Matched loss, total loss with SWR, and delivered power.",
        "fields": [_pick("Cable", tc.COAX_NAMES, 4), _num("Freq", 146.0, "MHz"),
                   _num("Length", 50.0, "ft"), _num("SWR at load", 1.5)],
    },
    "phasing_line": {
        "name": "Phasing line / stub", "fn": tc.phasing_line,
        "desc": "Physical length of a coax section for a wanted electrical "
                "length (uses the cable velocity factor).",
        "fields": [_pick("Cable", tc.COAX_NAMES, 4), _num("Freq", 146.0, "MHz"),
                   _pick("Length", tc.PHASE_FRAC_NAMES, 0)],
    },
    "match_network": {
        "name": "L/Pi/T match network", "fn": tc.match_network,
        "desc": "Component values for an impedance-matching network.",
        "fields": [_pick("Topology", tc.MATCH_TOPOLOGIES, 0),
                   _num("R source", 50.0, "ohm"), _num("R load", 200.0, "ohm"),
                   _num("Freq", 14.2, "MHz"), _num("Loaded Q", 5.0)],
    },
    "microstrip": {
        "name": "Microstrip/stripline Z0", "fn": tc.microstrip,
        "desc": "Characteristic impedance of a PCB trace.",
        "fields": [_pick("Line", tc.USTRIP_MODES, 0), _num("Er", 4.4),
                   _num("H sub/gap", 1.6, "mm"), _num("W trace", 3.0, "mm"),
                   _num("Freq", 435.0, "MHz")],
    },

    # ---- RF & measurement ----
    "rf_units": {
        "name": "RF units (dBm/W/V)", "fn": tc.rf_units,
        "desc": "Cross-convert power in W, dBm, dBW and voltage into 50 ohm.",
        "fields": [_num("Power", 100.0, "W")],
    },
    "swr": {
        "name": "SWR / return loss", "fn": tc.swr,
        "desc": "Return loss, reflection coefficient and mismatch loss.",
        "fields": [_num("SWR", 2.0)],
    },
    "fspl": {
        "name": "Free-space path loss", "fn": tc.fspl,
        "desc": "Free-space path loss in dB.",
        "fields": [_num("Distance", 1000.0, "km"), _num("Freq", 145.0, "MHz")],
    },
    "attenuator": {
        "name": "Attenuator pad", "fn": tc.attenuator,
        "desc": "Resistor values for pi- and T-topology resistive pads.",
        "fields": [_num("Atten", 6.0, "dB"), _num("Z0", 50.0, "ohm")],
    },
    "db_chain": {
        "name": "dB chain sum", "fn": tc.db_chain,
        "desc": "Sum a gain/loss chain (+gain, -loss).",
        "fields": [_num("Stage 1", 20.0, "dB"), _num("Stage 2", -3.0, "dB"),
                   _num("Stage 3", -6.0, "dB"), _num("Stage 4", 0.0, "dB")],
    },
    "cascade_nf": {
        "name": "Cascade NF & G/T", "fn": tc.cascade_nf,
        "desc": "Friis cascade for the antenna->LNA->coax->rig chain.",
        "fields": [_num("Ant gain", 16.0, "dBi"), _num("Sky temp", 150.0, "K"),
                   _num("LNA NF", 0.8, "dB"), _num("LNA gain", 20.0, "dB"),
                   _num("Coax loss", 3.0, "dB"), _num("Rig NF", 6.0, "dB")],
    },
    "sun_noise_gt": {
        "name": "Sun-noise G/T measure", "fn": tc.sun_noise_gt,
        "desc": "Turn a measured sun-noise Y-factor into a station G/T.",
        "fields": [_num("Y-factor", 1.0, "dB"), _num("Solar flux", 150.0, "sfu"),
                   _num("Freq", 435.0, "MHz"), _num("Ant gain", 0.0, "dBi")],
    },
    "imd_products": {
        "name": "IMD products", "fn": tc.imd_products,
        "desc": "Odd-order intermodulation products; flags in-band ones.",
        "fields": [_num("Freq 1", 145.900, "MHz"), _num("Freq 2", 145.950,
                   "MHz"), _num("Band low", 145.800, "MHz"),
                   _num("Band high", 146.000, "MHz")],
    },
    "rf_exposure": {
        "name": "RF exposure (MPE)", "fn": tc.rf_exposure,
        "desc": "FCC OET-65 far-field MPE limits and compliance distances.",
        "fields": [_num("Freq", 146.0, "MHz"), _num("Power", 100.0, "W"),
                   _pick("Mode duty", tc.RFDUTY_NAMES, 0),
                   _num("Ant gain", 2.15, "dBi")],
    },

    # ---- electronics & power ----
    "complex_polar": {
        "name": "Complex / polar", "fn": tc.complex_polar,
        "desc": "Rectangular <-> polar conversion for impedance work.",
        "fields": [_num("Real a", 50.0), _num("Imag b (j)", 25.0)],
    },
    "reactance": {
        "name": "Reactance & resonance", "fn": tc.reactance,
        "desc": "Xl, Xc and the L-C resonant frequency.",
        "fields": [_num("Freq", 7.0, "MHz"), _num("Induct L", 10.0, "uH"),
                   _num("Cap C", 100.0, "pF")],
    },
    "rc_time_constant": {
        "name": "RC/RL time constant", "fn": tc.rc_time_constant,
        "desc": "tau and charge/discharge percentages at 1-5 tau.",
        "fields": [_num("Resist R", 1000.0, "ohm"), _num("Cap C", 1.0, "uF")],
    },
    "battery_runtime": {
        "name": "Battery runtime", "fn": tc.battery_runtime,
        "desc": "Operating hours from a battery under a TX/RX duty cycle.",
        "fields": [_num("Capacity", 20.0, "Ah"), _num("RX draw", 0.5, "A"),
                   _num("TX draw", 8.0, "A"), _num("TX duty", 30.0, "%"),
                   _num("Usable", 80.0, "%")],
    },
    "cross_section": {
        "name": "Cross-section area", "fn": tc.cross_section,
        "desc": "Projected cross-sectional area for drag/thermal work.",
        "fields": [_pick("Form factor", tc.XSEC_NAMES, 2),
                   _num("Body X", 10.0, "cm"), _num("Body Y", 10.0, "cm"),
                   _num("Body Z", 30.0, "cm"), _num("Panel area", 0.0, "m2")],
    },
    "thermal_equilibrium": {
        "name": "Thermal equilibrium", "fn": tc.thermal_equilibrium,
        "desc": "Equilibrium temperature of a surface in sunlight.",
        "fields": [_pick("Surface", tc.THERM_NAMES, 1),
                   _num("Custom a", 0.25), _num("Custom e", 0.85)],
    },
    "ampacity": {
        "name": "Trace & wire ampacity", "fn": tc.ampacity,
        "desc": "Safe current / required trace width (IPC-2221).",
        "fields": [_pick("Mode", tc.AMPAC_MODES, 0), _num("Current", 1.0, "A"),
                   _num("Temp rise", 10.0, "C"), _num("Copper", 1.0, "oz"),
                   _num("Wire", 24, "AWG")],
    },
    "toroid_winding": {
        "name": "Toroid winding", "fn": tc.toroid_winding,
        "desc": "Turns needed on an Amidon core for a target inductance.",
        "fields": [_pick("Core", tc.TOROID_NAMES, 2),
                   _num("Target L", 10.0, "uH")],
    },
    "pll_plan": {
        "name": "PLL / frequency plan", "fn": tc.pll_plan,
        "desc": "Output frequency and step size of a PLL synthesizer plan.",
        "fields": [_num("Reference", 10.0, "MHz"), _num("R divider", 1.0),
                   _num("N divider", 40.0), _num("Multiplier", 1.0)],
    },

    # ---- terrestrial VHF/UHF/microwave ----
    "radio_horizon": {
        "name": "Radio horizon (VHF+)", "fn": tc.radio_horizon,
        "desc": "Line-of-sight horizon for each station and the max LOS path.",
        "fields": [_num("My ant HAAT", 10.0, "m"),
                   _num("Their ant HAAT", 10.0, "m"), _num("k factor", 1.33)],
    },
    "fresnel_zone": {
        "name": "Fresnel zone clearance", "fn": tc.fresnel_zone,
        "desc": "First Fresnel-zone radius and 60% clearance figure.",
        "fields": [_num("Path length", 30.0, "km"), _num("Freq", 144.0, "MHz")],
    },
    "tropo_ducting": {
        "name": "Tropo ducting index", "fn": tc.tropo_ducting,
        "desc": "A 0-6 ducting-likelihood index (a watch-this flag).",
        "fields": [_num("Surface temp", 20.0, "C"), _num("Dewpoint", 15.0, "C"),
                   _num("Inversion dT", 0.0, "C")],
    },
    "rain_fade": {
        "name": "Rain fade (microwave)", "fn": tc.rain_fade,
        "desc": "ITU-style specific attenuation and total path fade.",
        "fields": [_num("Freq", 10.0, "GHz"), _num("Rain rate", 25.0, "mm/h"),
                   _num("Path length", 10.0, "km")],
    },
    "terrestrial_path_budget": {
        "name": "Terrestrial path budget", "fn": tc.terrestrial_path_budget,
        "desc": "Two-way terrestrial link budget with a workable verdict.",
        "fields": [_num("TX power", 25.0, "W"), _num("TX gain", 6.0, "dBi"),
                   _num("RX gain", 6.0, "dBi"), _num("Line loss", 2.0, "dB"),
                   _num("Freq", 146.0, "MHz"), _num("Distance", 50.0, "km")],
    },
    "terrain_los": {
        "name": "Terrain path (LOS)", "fn": terrain_los_rows,
        "desc": "Does a straight radio path clear a known ridge? Enter the worst "
                "obstruction; checks 60% Fresnel clearance with Earth curvature.",
        "fields": [_num("Path length", 30.0, "km"),
                   _num("Obstruction ht", 200.0, "m"),
                   _num("Obstruction at", 15.0, "km"),
                   _num("TX ant HAAT", 10.0, "m"),
                   _num("RX ant HAAT", 10.0, "m"), _num("Freq", 146.0, "MHz"),
                   _num("TX ground el", 100.0, "m"),
                   _num("RX ground el", 100.0, "m")],
    },

    # ---- satellite & orbit ----
    "doppler_budget": {
        "name": "Doppler budget (orbit)", "fn": tc.doppler_budget,
        "desc": "Peak Doppler shift and rate to expect for an orbit.",
        "fields": [_num("Apogee alt", 550.0, "km"),
                   _num("Perigee alt", 550.0, "km"),
                   _num("Freq", 435.5, "MHz")],
    },
    "orbit_lifetime": {
        "name": "Orbit lifetime (decay)", "fn": decay_rows,
        "desc": "Days to re-entry from the element set, anchored on the "
                "observed decay rate where available (King-Hele, calibrated "
                "against 244 real re-entries).",
        "fields": [_num("Mean motion", 15.50, "rev/day"),
                   _num("Eccentricity", 0.0004),
                   _num("B*", 0.00025), _num("n-dot", 0.0001, "rev/day2"),
                   _pick("Solar activity", ["low", "mean", "high"], 1)],
    },
    "delta_v": {
        "name": "Delta-v (Hohmann/plane)", "fn": tc.delta_v,
        "desc": "Hohmann-transfer and plane-change delta-v between orbits.",
        "fields": [_num("Alt 1", 400.0, "km"), _num("Alt 2", 800.0, "km"),
                   _num("Plane chg", 0.0, "deg")],
    },
    "pointing_loss": {
        "name": "Pointing loss", "fn": tc.pointing_loss,
        "desc": "The dB loss from an antenna mispointed at that beamwidth.",
        "fields": [_num("HPBW", 30.0, "deg"), _num("Point err", 3.0, "deg")],
    },
    "link_margin_vs_elevation": {
        "name": "Link margin vs elevation", "fn": tc.link_margin_vs_elevation,
        "desc": "How received margin improves from the horizon to overhead as "
                "slant range shortens across a pass.",
        "fields": [_num("Altitude", 550.0, "km"), _num("Freq", 435.0, "MHz"),
                   _num("Margin @0deg", 6.0, "dB")],
    },
    "faraday_rotation": {
        "name": "Polarization / Faraday", "fn": tc.faraday_rotation,
        "desc": "Faraday-rotation of a linear signal through the ionosphere.",
        "fields": [_num("Freq", 145.9, "MHz"),
                   _pick("Ionosphere", tc.FARADAY_NAMES, 0)],
    },
    "dxcc_lookup": {
        "name": "DXCC entity lookup", "fn": _dxcc_rows,
        "desc": "Find a DXCC entity by prefix or name, with its coordinates.",
        "fields": [_text("Prefix or name", "JA")],
    },
    "link_margin": {
        "name": "Link margin vs elevation", "fn": _margin_rows,
        "desc": "Received power and margin across a pass, horizon to zenith - "
                "the horizon rows are what decide a marginal link.",
        "fields": [_num("Satellite alt", 500.0, "km"),
                   _num("Frequency", 145.8, "MHz"),
                   _num("RX sensitivity", -120.0, "dBm")],
    },
    "gp_fit_check": {
        "name": "State vector sanity", "fn": _fit_rows,
        "desc": "Whether a position/velocity pair is self-consistent, and the "
                "unit mix-ups that otherwise produce plausible garbage.",
        "fields": [_num("Rx", 6800.0, "km"), _num("Ry", 0.0, "km"),
                   _num("Rz", 0.0, "km"), _num("Vx", 0.0, "km/s"),
                   _num("Vy", 7.66, "km/s"), _num("Vz", 0.0, "km/s")],
    },
    "char_lookup": {
        "name": "Character / byte lookup", "fn": char_lookup_rows,
        "desc": "One byte in hex, decimal, octal and binary, with its ASCII "
                "meaning, Morse, ITA2 letters/figures shift and BCD reading.",
        "fields": [_num("Byte value", 65)],
    },
    "sci_calc": {
        "name": "Scientific calculator", "fn": gc.sci_rows,
        "desc": "Evaluate an expression: + - * / ^, sqrt, sin/cos/tan, log, "
                "exp, deg/rad, pi, e. Text field.",
        "fields": [_text("Expression", "300/145.9")],
    },
    "programmer_calc": {
        "name": "Programmer calc (hex/bin)", "fn": gc.programmer_rows,
        "desc": "Convert between decimal, hex, binary and octal with a bit "
                "breakdown and two's-complement view.",
        "fields": [_text("Value", "255"),
                   _pick("Input base", gc.PROG_BASES, 0),
                   _num("Width", 32, "bits")],
    },
    "unit_converter": {
        "name": "Unit converter", "fn": gc.convert_rows,
        "desc": "Convert length, mass, power, frequency, speed, angle and "
                "temperature; also lists every unit in the family.",
        "fields": [_num("Value", 1.0),
                   _pick("Family", gc.UNIT_FAMILY_NAMES, 0),
                   _pick("From", [u for u, _f in gc.UNIT_FAMILIES["Length"]], 0),
                   _pick("To", [u for u, _f in gc.UNIT_FAMILIES["Length"]], 1)],
    },
    "orbital_thermal": {
        "name": "Orbital thermal (cubesat)", "fn": thermal_rows,
        "desc": "First-order single-node thermal model: solar, albedo, Earth IR "
                "and internal power against radiation to space, over one orbit.",
        "fields": [_num("Altitude", 550.0, "km"), _num("Size", 3, "U"),
                   _num("Mass", 4.0, "kg"), _num("Absorptivity a", 0.35),
                   _num("Emissivity e", 0.85), _num("Internal power", 2.0, "W"),
                   _num("Beta angle", 0.0, "deg"),
                   _pick("Attitude", ATTITUDE, 0)],
    },
    "state_vector": {
        "name": "State vector \u2192 GP", "fn": rv_to_rows,
        "desc": "Recover classical orbital elements from a TEME position/"
                "velocity state vector (km, km/s).",
        "fields": [_num("Pos X", -4400.0, "km"), _num("Pos Y", -5100.0, "km"),
                   _num("Pos Z", 0.0, "km"), _num("Vel X", 3.6, "km/s"),
                   _num("Vel Y", -3.1, "km/s"), _num("Vel Z", 6.0, "km/s")],
    },
}


# Display grouping: (category label, [tool keys in order])
CATEGORIES = [
    ("General", ["sci_calc", "programmer_calc", "unit_converter",
                 "char_lookup", "dxcc_lookup"]),
    ("Antennas & feedline", ["dipole", "vertical", "yagi", "quad", "helix",
                             "wavelength", "coax_loss", "phasing_line",
                             "match_network", "microstrip"]),
    ("RF & measurement", ["rf_units", "swr", "fspl", "attenuator", "db_chain",
                          "cascade_nf", "sun_noise_gt", "imd_products",
                          "rf_exposure"]),
    ("Electronics & power", ["complex_polar", "reactance", "rc_time_constant",
                             "battery_runtime", "cross_section",
                             "thermal_equilibrium", "ampacity",
                             "toroid_winding", "pll_plan"]),
    ("Terrestrial VHF+", ["radio_horizon", "fresnel_zone", "tropo_ducting",
                          "rain_fade", "terrestrial_path_budget",
                          "terrain_los"]),
    ("Satellite & orbit", ["doppler_budget", "orbit_lifetime", "delta_v",
                           "pointing_loss", "link_margin_vs_elevation",
                           "faraday_rotation", "state_vector", "gp_fit_check",
                           "orbital_thermal", "link_margin"]),
]
