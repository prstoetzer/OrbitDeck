"""radioedu.py - helpers and reference content for the radio / transponder
education tabs on the Learn screen.

Keeps the teaching text and small data tables out of the screen module, and
provides a couple of derived helpers (band labels, mode decoding) that build on
the transponder model and the link-budget engine.
"""

import math

C_LIGHT = 299792458.0

# amateur-satellite bands: (label, nominal freq Hz, the ham band name)
SAT_BANDS = [
    ("2 m (VHF)", 145900000.0),
    ("70 cm (UHF)", 435000000.0),
    ("23 cm (L)", 1265000000.0),
    ("13 cm (S)", 2400000000.0),
    ("3 cm (X)", 10450000000.0),
]

# mode shorthand: first letter = uplink band, second = downlink band
MODE_BANDS = {
    "H": "15 m (HF)", "A": "10 m", "V": "2 m (VHF)", "U": "70 cm (UHF)",
    "L": "23 cm (L)", "S": "13 cm (S)", "S2": "9 cm", "C": "5 cm (C)",
    "X": "3 cm (X)", "K": "1.2 cm (K)",
}

MODE_EXPLAINERS = [
    ("U/V (\u201cMode B\u201d)",
     "Uplink on 70 cm, downlink on 2 m. The most common amateur-satellite "
     "arrangement (e.g. RS-44, many linear birds). The wider 70 cm uplink "
     "leaves the quieter 2 m band for the downlink you listen to."),
    ("V/U (\u201cMode J\u201d)",
     "Uplink on 2 m, downlink on 70 cm (e.g. SO-50, AO-91 FM repeaters and "
     "many CubeSats). Most of the Doppler ends up on the 70 cm downlink, which "
     "you retune as the pass progresses."),
    ("L/S, U/S, etc.",
     "Higher-band modes (23 cm up / 13 cm down and similar) used by some "
     "satellites. They need dish or high-gain antennas but suffer less "
     "terrestrial interference."),
]

POLARIZATION_TEXT = (
    "Satellites usually transmit circular polarization. As a signal passes "
    "through the ionosphere its plane of polarization rotates by an "
    "unpredictable amount (Faraday rotation), so a fixed linear antenna on the "
    "ground would fade deeply as the rotation drifts. Circular polarization "
    "(or a switchable crossed-Yagi system) keeps the coupling roughly "
    "constant, reducing those fades. A handheld whip is linear and cheap but "
    "pays a polarization penalty; a beam with more gain narrows the beamwidth "
    "but must be aimed."
)

SUBSYSTEMS = [
    ("Transponder / payload",
     "The radio that relays your signal: a single-channel FM repeater, a "
     "linear (SSB/CW) transponder that relays a whole passband, or a digital "
     "transceiver. This is what you actually work."),
    ("Communications bus",
     "Command receivers and telemetry transmitters the control team uses to "
     "operate the satellite and read its health, separate from the user "
     "payload."),
    ("Power",
     "Solar panels charge a battery; the satellite runs on the battery through "
     "eclipse. How much of each orbit is sunlit depends on the beta angle (see "
     "the Sunlight tab) \u2014 some transponders are switched off over eclipse "
     "or over certain regions to save power."),
    ("Attitude control",
     "Keeps the antennas pointed (or the satellite spinning predictably) using "
     "magnetorquers, reaction wheels, or gravity-gradient booms. Affects how "
     "the signal strength varies through a pass."),
    ("Structure & thermal",
     "The frame (a 1U CubeSat is 10 cm cubed) and the coatings/heaters that "
     "keep electronics in their temperature range as the satellite moves in "
     "and out of sunlight."),
]

BEACON_TEXT = (
    "Many satellites transmit a beacon: a steady CW (Morse) or digital signal, "
    "separate from the transponder, that always identifies the satellite and "
    "carries telemetry (battery voltage, temperatures, mode). Finding the "
    "beacon first is the easiest way to confirm you have the right bird and to "
    "calibrate your Doppler tuning before you try to work the transponder. "
    "Digital beacons (BPSK, AFSK, FSK, often 1k2\u20139k6 baud) are decoded "
    "with free soundcard software and uploaded to telemetry databases."
)


def band_label(freq_hz):
    """Nearest amateur-satellite band label for a frequency."""
    if freq_hz <= 0:
        return ""
    best, bd = "", 1e30
    for label, f in SAT_BANDS:
        d = abs(math.log10(freq_hz) - math.log10(f))
        if d < bd:
            bd, best = d, label
    return best


def fspl_db(range_km, freq_hz):
    if range_km <= 0 or freq_hz <= 0:
        return 0.0
    d = range_km * 1000.0
    return (20.0 * math.log10(d) + 20.0 * math.log10(freq_hz)
            + 20.0 * math.log10(4.0 * math.pi / C_LIGHT))


def workable_verdict(rx_dbm, mode):
    """A crude 'will I hear it?' verdict given received power and mode.

    Required carrier-to-noise differs by mode: FM needs a stronger signal to
    quiet than a narrow CW/SSB signal. These thresholds are deliberately rough,
    for teaching the *relationship*, not for station design.
    """
    m = (mode or "").upper()
    if "FM" in m:
        thresh = -116.0
        need = "FM (needs full quieting)"
    elif "USB" in m or "LSB" in m or "CW" in m or "SSB" in m:
        thresh = -127.0
        need = "SSB/CW (narrow, more sensitive)"
    else:
        thresh = -120.0
        need = "digital/other"
    margin = rx_dbm - thresh
    return margin, need, (margin >= 0)


# --- antenna pattern model ----------------------------------------------------

def antenna_gain_pattern(gain_dbi, n=360):
    """A simple normalized power pattern (theta_deg, relative_dB) for an antenna
    of a given boresight gain. Higher gain -> narrower main lobe. This is a
    teaching approximation (a raised-cosine main lobe with a floor), not a real
    measured pattern.

    Returns (thetas_deg, gains_dbi) where gains_dbi is the absolute gain in that
    direction (boresight = gain_dbi).
    """
    import math as _m
    # approximate -3 dB beamwidth from gain: BW ~ sqrt(~30000 / linear_gain)
    g_lin = 10.0 ** (gain_dbi / 10.0)
    if g_lin < 1.2:
        g_lin = 1.2
    bw_deg = max(8.0, min(360.0, _m.sqrt(30000.0 / g_lin)))
    thetas = [(-180.0 + 360.0 * i / n) for i in range(n + 1)]
    out = []
    floor_db = -22.0          # back/side-lobe floor relative to boresight
    for th in thetas:
        # main lobe as a cos^2 within +/- ~beamwidth, then floor
        if abs(th) <= bw_deg:
            rel = 10.0 * _m.log10(max(_m.cos(_m.radians(90.0 * th / bw_deg))
                                      ** 2, 1e-3))
        else:
            rel = floor_db + 4.0 * _m.cos(_m.radians(th))
            rel = max(min(rel, -6.0), floor_db)
        out.append(gain_dbi + rel)
    return thetas, out


def beamwidth_deg(gain_dbi):
    import math as _m
    g_lin = max(1.2, 10.0 ** (gain_dbi / 10.0))
    return max(8.0, min(360.0, _m.sqrt(30000.0 / g_lin)))


# --- operating practice / bands / modes / etc. (reference content) ------------

OPERATING_PRACTICE = [
    ("FM birds (one at a time)",
     "An FM satellite is a single-channel repeater: only one station transmits "
     "at a time. Listen first, give your call and grid, keep it short, and let "
     "others in. A handheld with a small beam and a dual-band radio is enough."),
    ("Linear birds (full duplex)",
     "SSB/CW transponders carry many QSOs across a passband at once. Work them "
     "full duplex \u2014 hear your own downlink while you transmit \u2014 so you "
     "can find a clear spot and follow Doppler. Keep power modest to avoid "
     "desensing the transponder ('alligator' stations ruin the pass for all)."),
    ("Logging & exchanges",
     "Exchange is usually callsign and 4- or 6-character grid. Log the time "
     "(UTC), satellite, and grid; many chase grid squares, US states, or DXCC "
     "entities worked via satellite."),
    ("Be a good neighbour",
     "Don't transmit through a transponder you can't hear yourself on, don't "
     "run more uplink power than you need, and yield to stations completing a "
     "contact. The whole pass is only a few minutes \u2014 share it."),
]

BANDS_LICENSING = [
    ("You must be licensed to transmit",
     "Receiving and tracking is open to everyone, but transmitting to a "
     "satellite requires an amateur radio license. Satellite operating "
     "privileges depend on your license class and country."),
    ("The amateur-satellite service",
     "Satellites use specific segments within the amateur bands set aside for "
     "the satellite service \u2014 commonly portions of 2 m (VHF) and 70 cm "
     "(UHF), with some birds on 10 m, 23 cm, 13 cm and higher. Operate only "
     "within the segments your license permits."),
    ("Coordination",
     "Amateur satellites coordinate their frequencies (e.g. via IARU) to avoid "
     "interference; the published uplink/downlink for each bird is what you "
     "program into your radio."),
]

MODULATION_MODES = [
    ("SSB (single sideband)",
     "Efficient voice mode used on linear transponders; narrow bandwidth lets "
     "many stations share the passband. Tuning matters \u2014 a few hundred Hz "
     "off and the audio sounds wrong."),
    ("CW (Morse)",
     "The narrowest and most robust mode; gets through when SSB can't, and is "
     "popular on linear birds for weak-signal work."),
    ("FM",
     "Wideband voice used by the single-channel repeater satellites; easiest to "
     "operate (no fine tuning) but only one station at a time."),
    ("Digital",
     "Packet/BPSK/GMSK and similar carry data, telemetry, and store-and-forward "
     "messaging; decoded with soundcard software."),
]

NOISE_SENSITIVITY = [
    ("It's about signal-to-noise, not just power",
     "Whether you hear a satellite depends on how far its signal sits above the "
     "noise floor, not the raw received power. On the downlink, a low-noise "
     "receive system often helps more than more transmit power."),
    ("Sky & system noise",
     "Noise comes from the sky (galactic background, stronger at VHF), the "
     "ground (warm, picked up by side lobes), and your own receiver. A "
     "low-noise preamp at the antenna and keeping the antenna's main lobe on "
     "the satellite both improve the ratio."),
    ("Why the downlink is the hard part",
     "The satellite has limited transmit power and a small antenna, so the "
     "weak link is usually what you receive. That's why operators invest in "
     "receive gain, preamps, and low-loss feedline."),
]

TIME_FRAMES = [
    ("Everything is UTC",
     "Satellite predictions, passes, and logs use Coordinated Universal Time so "
     "operators worldwide agree on timing regardless of time zone."),
    ("The element-set epoch",
     "An orbit is described by a set of elements valid at a specific instant "
     "(the epoch). Propagation carries it forward from there; the further from "
     "the epoch, the more the prediction drifts (see the Element age tab)."),
    ("Why elements go stale",
     "Atmospheric drag and other perturbations slowly change a real orbit, so "
     "fresh element sets are published regularly. Refresh yours (Update GP) for "
     "accurate pass timing, especially for low, high-drag satellites."),
]

CONSTELLATIONS = [
    ("Where amateur satellites fit",
     "Amateur (OSCAR) satellites are a small, open corner of a crowded sky: "
     "they share orbits with weather, navigation, imaging, and communications "
     "spacecraft, but are built and operated by volunteers for two-way "
     "amateur radio."),
    ("Navigation (MEO)",
     "GPS, Galileo, GLONASS and BeiDou sit ~20,000 km up so a few satellites "
     "cover huge areas continuously \u2014 a different design point from a "
     "low, fast amateur LEO."),
    ("Big LEO constellations",
     "Systems like Starlink put thousands of satellites in low orbit for "
     "low-latency internet; they're why the sky is busier (and why accurate "
     "tracking and coordination matter more than ever)."),
    ("Geostationary",
     "Weather and broadcast satellites at ~35,786 km appear to hover over one "
     "spot; a few amateur payloads (e.g. on GEO birds) give continuous "
     "coverage of a whole hemisphere."),
]


# --- history & coordinate frames (reference content) -------------------------

SAT_HISTORY = [
    ("OSCAR-1 (1961)",
     "The first amateur satellite, launched just four years after Sputnik. It "
     "transmitted a simple 'HI' in Morse and proved amateurs could build and "
     "operate spacecraft. OSCAR stands for Orbiting Satellite Carrying Amateur "
     "Radio."),
    ("The early OSCARs",
     "Through the 1960s-70s a series of OSCARs added voice transponders and "
     "telemetry; AMSAT formed in 1969 to coordinate the work, and the linear "
     "transponder (relaying a whole passband) became the standard for shared "
     "SSB/CW operating."),
    ("Phase 3 high orbits",
     "Satellites like AO-10, AO-13 and AO-40 flew elliptical Molniya-type "
     "orbits, hanging high over a hemisphere for hours at a time and enabling "
     "intercontinental contacts \u2014 a big step beyond short low-orbit "
     "passes."),
    ("CubeSats & today",
     "The CubeSat standard (10 cm cubes) made satellites cheap to build and "
     "launch, so universities and clubs now fly dozens of amateur payloads: FM "
     "repeaters, linear transponders, and digital/store-and-forward birds. The "
     "ISS itself carries amateur gear and an FM repeater."),
]

COORDINATE_FRAMES = [
    ("ECI \u2014 Earth-centred inertial",
     "A frame fixed to the stars, not rotating with the Earth. Orbits are "
     "naturally described here because gravity points at the Earth's centre and "
     "the orbit plane stays (almost) fixed. The propagator works in an "
     "ECI-like frame."),
    ("ECEF \u2014 Earth-centred, Earth-fixed",
     "Rotates with the Earth, so a point on the ground keeps constant "
     "coordinates. Converting the satellite's ECI position into ECEF (using the "
     "Earth's rotation angle for the time) gives the sub-satellite latitude and "
     "longitude you see on the maps."),
    ("Topocentric \u2014 your local sky",
     "Centred on your station: azimuth (compass bearing) and elevation (angle "
     "above the horizon), plus range. This is what you point an antenna with, "
     "and it comes from subtracting your ECEF position from the satellite's and "
     "rotating into your local up/north/east frame."),
    ("Why the conversions matter",
     "Every pass prediction walks the same chain: propagate the orbit in ECI, "
     "rotate to ECEF for the ground track, then to topocentric for az/el and "
     "Doppler. Each frame answers a different question \u2014 where it is in "
     "space, where it is over the Earth, and where it is in your sky."),
]
