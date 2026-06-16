"""linkbudget.py - derived radio, optical, and planning analytics.

This module holds analysis that builds on the propagator/predictor but is not
about raw geometry: free-space path loss and a simple link budget, satellite
optical magnitude and visible-pass classification, a Doppler "tuning playbook"
(including the round-trip fixed-leg math for linear transponders), satellite-to-
satellite line-of-sight visibility, element-set age / drift estimation, and a
pass-quality score. Everything here is pure and unit-testable.

Conventions match the rest of the engine: distances in km, frequencies in Hz,
range-rate positive when receding, angles in degrees unless noted.
"""

import math

DEG = math.pi / 180.0
RE_KM = 6378.135
C_LIGHT = 299792458.0          # m/s


# ---------------------------------------------------------------------------
# Free-space path loss / link budget
# ---------------------------------------------------------------------------

def free_space_path_loss_db(range_km, freq_hz):
    """Free-space path loss in dB for a slant range and frequency.

    FSPL(dB) = 20 log10(d) + 20 log10(f) + 20 log10(4*pi/c)
    with d in metres and f in Hz.
    """
    if range_km <= 0 or freq_hz <= 0:
        return 0.0
    d = range_km * 1000.0
    return (20.0 * math.log10(d) + 20.0 * math.log10(freq_hz)
            + 20.0 * math.log10(4.0 * math.pi / C_LIGHT))


def propagation_delay_ms(range_km):
    """One-way propagation delay in milliseconds for a slant range."""
    if range_km <= 0:
        return 0.0
    return range_km * 1000.0 / C_LIGHT * 1000.0


def link_budget(range_km, freq_hz, tx_power_w=5.0, tx_gain_dbi=0.0,
                rx_gain_dbi=0.0, line_loss_db=1.0, other_loss_db=0.0):
    """A simple one-way link budget. Returns a dict of the terms (all dB except
    where noted) so a UI/report can show the chain.

    received power (dBm) = EIRP - FSPL - line loss - other losses + rx gain

    The defaults are deliberately conservative placeholders; a UI should let the
    operator override them. This is an estimate for "is this pass workable",
    not a calibrated measurement.
    """
    if tx_power_w <= 0:
        tx_power_dbm = -999.0
    else:
        tx_power_dbm = 10.0 * math.log10(tx_power_w * 1000.0)
    eirp_dbm = tx_power_dbm + tx_gain_dbi
    fspl = free_space_path_loss_db(range_km, freq_hz)
    rx_dbm = eirp_dbm - fspl - line_loss_db - other_loss_db + rx_gain_dbi
    return {
        "tx_power_dbm": tx_power_dbm,
        "tx_gain_dbi": tx_gain_dbi,
        "eirp_dbm": eirp_dbm,
        "fspl_db": fspl,
        "line_loss_db": line_loss_db,
        "other_loss_db": other_loss_db,
        "rx_gain_dbi": rx_gain_dbi,
        "rx_power_dbm": rx_dbm,
        "delay_ms": propagation_delay_ms(range_km),
    }


# ---------------------------------------------------------------------------
# Optical magnitude / visible-pass classification
# ---------------------------------------------------------------------------

def apparent_magnitude(std_mag, range_km, phase_angle_deg, range_ref_km=1000.0):
    """Estimate a satellite's visual magnitude from a standard (intrinsic)
    magnitude, the slant range, and the solar phase angle.

    Standard magnitude is defined as the brightness at a reference range
    (1000 km) at full illumination (phase angle 0). Apparent magnitude then
    grows (dimmer) with distance and with increasing phase angle:

        m = std_mag + 5*log10(d/d0) - 2.5*log10(F(phase))

    where F(phase) is a simple diffuse-sphere phase function (1 at full phase,
    0 at zero phase). The 5*log10 distance term is the standard inverse-square
    law in magnitudes. This is an estimate; real satellites flare and tumble.
    Typical std_mag: the ISS is around -1 to +0; a large rocket body +1 to +3;
    a small cubesat +6 to +8.
    """
    if range_km <= 0:
        return 99.0
    pa = max(0.0, min(180.0, phase_angle_deg)) * DEG
    # diffuse-sphere phase function, normalised to 1 at full phase (pa=0)
    fphase = (math.sin(pa) + (math.pi - pa) * math.cos(pa)) / math.pi
    fphase = max(fphase, 1e-3)
    return (std_mag + 5.0 * math.log10(range_km / range_ref_km)
            - 2.5 * math.log10(fphase))


def phase_angle_deg(sun_el_at_sat_deg=None, sat_r=None, sun_unit=None,
                    obs_r=None):
    """Solar phase angle (Sun-satellite-observer) in degrees, from ECI vectors.

    Pass the satellite ECI position ``sat_r`` (km), the unit Sun direction
    ``sun_unit``, and the observer ECI position ``obs_r`` (km). The phase angle
    is the angle at the satellite between the direction to the Sun and the
    direction to the observer. Small phase angle => nearly fully lit => bright.
    """
    if sat_r is None or sun_unit is None or obs_r is None:
        return 90.0
    # vector sat->observer
    so = (obs_r[0] - sat_r[0], obs_r[1] - sat_r[1], obs_r[2] - sat_r[2])
    so_n = math.sqrt(sum(c * c for c in so)) or 1.0
    so_u = (so[0] / so_n, so[1] / so_n, so[2] / so_n)
    # direction sat->Sun is +sun_unit (sun_unit points from Earth to Sun;
    # for phase we want sat->Sun which is approx the same unit at these scales)
    dot = (so_u[0] * sun_unit[0] + so_u[1] * sun_unit[1]
           + so_u[2] * sun_unit[2])
    dot = max(-1.0, min(1.0, dot))
    return math.acos(dot) / DEG


def is_optically_visible(sat_sunlit, observer_sun_el_deg, sat_el_deg,
                         twilight_max_sun_el_deg=-6.0, min_sat_el_deg=10.0):
    """A pass is optically visible (naked-eye) when the satellite is sunlit, the
    observer is in darkness/twilight (Sun sufficiently below the horizon), and
    the satellite is high enough above the horizon to be seen.

    ``twilight_max_sun_el_deg`` default -6 deg is civil-twilight darkness; use
    -12 (nautical) or -18 (astronomical) for stricter darkness.
    """
    return (bool(sat_sunlit)
            and observer_sun_el_deg <= twilight_max_sun_el_deg
            and sat_el_deg >= min_sat_el_deg)


# ---------------------------------------------------------------------------
# Doppler tuning playbook (incl. round-trip fixed-leg for linear transponders)
# ---------------------------------------------------------------------------

def doppler_shift_hz(freq_hz, range_rate_kms):
    """Classical Doppler shift (Hz) of a signal at ``freq_hz`` for a line-of-
    sight range-rate (km/s, positive = receding). Negative when approaching
    (frequency rises)."""
    beta = (range_rate_kms * 1000.0) / C_LIGHT
    return -freq_hz * beta


def observed_downlink_hz(dl_nominal_hz, range_rate_kms):
    """Frequency at which a downlink transmitted at ``dl_nominal_hz`` is heard
    on the ground (receding lowers it)."""
    beta = (range_rate_kms * 1000.0) / C_LIGHT
    return dl_nominal_hz * (1.0 - beta)


def uplink_for_observed_downlink_hz(ul_nominal_hz, range_rate_kms):
    """Frequency to transmit so the satellite *receives* ``ul_nominal_hz`` at
    its front end (the one-way uplink correction)."""
    beta = (range_rate_kms * 1000.0) / C_LIGHT
    if ul_nominal_hz <= 0:
        return 0.0
    return ul_nominal_hz / (1.0 - beta)


def linear_fixed_leg_playbook(dl_center_hz, ul_center_hz, range_rate_kms,
                              invert, hold="downlink"):
    """Round-trip Doppler for a LINEAR transponder worked full duplex, holding
    one leg fixed so the operator keeps hearing themselves on a stationary
    frequency.

    On a linear bird, where your own signal lands on the downlink depends on
    where the satellite *heard* your uplink, so holding one leg stationary
    requires the other leg to cancel BOTH Doppler shifts (the round trip), not
    just its own. (See CardSat v0.9.16.)

    hold="downlink": you park your receiver on a fixed downlink frequency and
    this returns the uplink frequency to transmit so your own signal stays on
    that fixed downlink as the satellite moves.

    hold="uplink": you park your transmitter on a fixed uplink frequency and
    this returns the downlink frequency on which you will then hear yourself.

    Returns a dict with the derived leg and the round-trip offset applied.
    Inverting transponders flip the sign of the uplink tuning relative to the
    downlink (tune up to move down in the passband).
    """
    beta = (range_rate_kms * 1000.0) / C_LIGHT
    sign = -1.0 if invert else 1.0
    if hold == "downlink":
        # We want our own signal to appear on the fixed downlink D_fix.
        # The satellite shifts our uplink by its uplink Doppler, then the
        # downlink we hear is shifted again. Net: tune the uplink to cancel the
        # round trip. For a non-inverting bird the passband offset tracks
        # directly; inverting flips it.
        d_fix = dl_center_hz
        # downlink heard from a transponder output at d_fix is d_fix*(1-beta);
        # to keep OUR signal on d_fix we must place the satellite-frame uplink
        # at the mirrored passband point, then pre-correct the uplink Doppler.
        # satellite-frame uplink point (passband-aligned to d_fix):
        ul_satframe = ul_center_hz + sign * (d_fix - dl_center_hz)
        ul_tx = ul_satframe / (1.0 - beta)
        return {
            "hold": "downlink",
            "fixed_hz": int(round(d_fix)),
            "tune_hz": int(round(ul_tx)),
            "tune_leg": "uplink",
            "round_trip_offset_hz": int(round(ul_tx - ul_satframe)),
            "invert": invert,
        }
    else:
        # hold == "uplink": park the transmitter on a fixed uplink U_fix.
        u_fix = ul_center_hz
        # the satellite hears U_fix shifted by the uplink Doppler:
        u_heard = u_fix * (1.0 - beta)
        # map that to the satellite-frame downlink passband point:
        dl_satframe = dl_center_hz + sign * (u_heard - ul_center_hz)
        # what we hear on the ground is that downlink shifted again:
        dl_rx = dl_satframe * (1.0 - beta)
        return {
            "hold": "uplink",
            "fixed_hz": int(round(u_fix)),
            "tune_hz": int(round(dl_rx)),
            "tune_leg": "downlink",
            "round_trip_offset_hz": int(round(dl_rx - dl_center_hz)),
            "invert": invert,
        }


def doppler_playbook_rows(times, range_rates, dl_nominal_hz, ul_nominal_hz=0,
                          is_linear=False, invert=False, hold="downlink"):
    """Build a per-time playbook table.

    For an FM bird (is_linear False), uplink and downlink are independent
    channels: each leg gets the plain one-way Doppler correction.

    For a linear bird worked full duplex, ``hold`` selects which leg is parked
    fixed; the other leg uses the round-trip correction so the operator stays on
    their own signal.

    Returns a list of dicts, one per time sample.
    """
    rows = []
    for t, rr in zip(times, range_rates):
        if not is_linear:
            rx = observed_downlink_hz(dl_nominal_hz, rr)
            tx = uplink_for_observed_downlink_hz(ul_nominal_hz, rr) \
                if ul_nominal_hz else 0
            rows.append({
                "t": t, "range_rate": rr,
                "rx_hz": int(round(rx)),
                "tx_hz": int(round(tx)) if ul_nominal_hz else 0,
                "mode": "FM/independent",
            })
        else:
            pb = linear_fixed_leg_playbook(dl_nominal_hz, ul_nominal_hz, rr,
                                           invert, hold=hold)
            if hold == "downlink":
                rows.append({
                    "t": t, "range_rate": rr,
                    "rx_hz": pb["fixed_hz"], "tx_hz": pb["tune_hz"],
                    "mode": "linear/hold-downlink",
                })
            else:
                rows.append({
                    "t": t, "range_rate": rr,
                    "rx_hz": pb["tune_hz"], "tx_hz": pb["fixed_hz"],
                    "mode": "linear/hold-uplink",
                })
    return rows


# ---------------------------------------------------------------------------
# Satellite-to-satellite line-of-sight visibility
# ---------------------------------------------------------------------------

def sat_to_sat_los(r1, r2, re_km=RE_KM):
    """True if two satellites at ECI positions r1, r2 (km) have a clear line of
    sight, i.e. the segment between them does not pass through the (spherical)
    Earth.

    Geometry: find the closest approach of the line segment r1->r2 to Earth
    centre. If that minimum distance exceeds Earth's radius, or the closest
    point lies outside the segment, the two can see each other.
    """
    d = (r2[0] - r1[0], r2[1] - r1[1], r2[2] - r1[2])
    dd = d[0] * d[0] + d[1] * d[1] + d[2] * d[2]
    if dd == 0:
        return True
    # parameter t of closest point on the segment to the origin
    t = -(r1[0] * d[0] + r1[1] * d[1] + r1[2] * d[2]) / dd
    if t <= 0.0 or t >= 1.0:
        # closest point is an endpoint; both endpoints are above the surface
        # (they're satellites), so the chord clears the Earth
        return True
    cx = r1[0] + t * d[0]
    cy = r1[1] + t * d[1]
    cz = r1[2] + t * d[2]
    min_dist = math.sqrt(cx * cx + cy * cy + cz * cz)
    return min_dist > re_km


# ---------------------------------------------------------------------------
# Element-set age / drift estimate
# ---------------------------------------------------------------------------

def element_age_days(epoch_unix, now_unix):
    """Age of an element set in days (now - epoch)."""
    return (now_unix - epoch_unix) / 86400.0


def along_track_error_km(age_days, mean_motion_revday=15.0):
    """A rough order-of-magnitude along-track position error for an SGP4
    propagation as a function of element-set age.

    SGP4 mean-element accuracy degrades roughly linearly for the first weeks;
    a common rule of thumb for LEO is on the order of ~1-3 km/day of along-track
    error growth, faster for low/high-drag or maneuvering objects. We scale a
    nominal 2 km/day by orbits/day relative to a 15 rev/day baseline so faster
    (lower) orbits accrue error a bit quicker. This is an ESTIMATE to inform a
    "refresh your elements" nudge, not a covariance.
    """
    base_km_per_day = 2.0
    scale = (mean_motion_revday / 15.0) if mean_motion_revday > 0 else 1.0
    return max(0.0, age_days) * base_km_per_day * scale


def trust_level(age_days):
    """Map element age to a coarse trust label and a 0-1 confidence for UI."""
    if age_days < 0:
        return ("future-epoch", 0.5)
    if age_days <= 3:
        return ("fresh", 1.0)
    if age_days <= 7:
        return ("good", 0.85)
    if age_days <= 14:
        return ("aging", 0.6)
    if age_days <= 30:
        return ("stale", 0.3)
    return ("expired", 0.1)


# ---------------------------------------------------------------------------
# Pass-quality score
# ---------------------------------------------------------------------------

def pass_quality_score(max_el_deg, duration_s, sunlit_frac=None,
                       weights=None):
    """A transparent 0-100 pass-quality score combining peak elevation,
    duration, and (optionally) the sunlit fraction.

    The default weighting favours high elevation (the dominant factor for both
    radio and visual quality), then duration. ``sunlit_frac`` is only folded in
    when provided (e.g. for visual-pass ranking). All sub-scores are 0-1.
    """
    if weights is None:
        weights = {"elevation": 0.6, "duration": 0.3, "sunlit": 0.1}
    el_score = max(0.0, min(1.0, max_el_deg / 90.0))
    # a 10-minute LEO pass is excellent; saturate there
    dur_score = max(0.0, min(1.0, duration_s / 600.0))
    parts = weights["elevation"] * el_score + weights["duration"] * dur_score
    total_w = weights["elevation"] + weights["duration"]
    if sunlit_frac is not None:
        parts += weights["sunlit"] * max(0.0, min(1.0, sunlit_frac))
        total_w += weights["sunlit"]
    return round(100.0 * parts / total_w, 1)
