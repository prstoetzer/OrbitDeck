"""orbitdeck.engine.refdata - static reference tables for the References screen.

Pure data (no I/O) ported from CardSat's reference browsers: the EIA CTCSS tone
set, CQ/ITU zone summaries, a compact ASCII/Baudot character table, and the
common ham Q-codes. Each accessor returns rows of tuples so the browser screen
can render them uniformly.
"""

# Standard EIA CTCSS (PL) tones in Hz.
CTCSS_TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8, 97.4,
    100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8, 136.5,
    141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9, 171.3, 173.8,
    177.3, 179.9, 183.5, 186.2, 189.9, 192.8, 196.6, 199.5, 203.5, 206.5,
    210.7, 218.1, 225.7, 229.1, 233.6, 241.8, 250.3, 254.1,
]

# Common amateur Q-codes (question / meaning).
Q_CODES = [
    ("QRA", "What is your station name?"),
    ("QRG", "What is my exact frequency?"),
    ("QRL", "Are you busy? / I am busy."),
    ("QRM", "Man-made interference."),
    ("QRN", "Static / natural noise."),
    ("QRO", "Increase power."),
    ("QRP", "Decrease power / low power."),
    ("QRQ", "Send faster."),
    ("QRS", "Send slower."),
    ("QRT", "Stop sending / closing down."),
    ("QRU", "I have nothing for you."),
    ("QRV", "I am ready."),
    ("QRX", "Wait / stand by."),
    ("QRZ", "Who is calling me?"),
    ("QSB", "Your signal is fading."),
    ("QSL", "I acknowledge receipt."),
    ("QSO", "A contact / conversation."),
    ("QSY", "Change frequency."),
    ("QTH", "My location is..."),
    ("QTR", "The correct time is..."),
]

# CQ zones: a compact summary of the 40 CQ zones by region.
CQ_ZONES = [
    ("1-5", "North America (NE US/Canada to W US/Mexico)"),
    ("6-8", "Mexico, Central America, Caribbean, S America N"),
    ("9-11", "South America (Venezuela to Argentina/Chile)"),
    ("12-13", "South America W & S"),
    ("14-16", "Europe (W, Central, E)"),
    ("17-19", "Asiatic Russia / Siberia (W to E)"),
    ("20-21", "Balkans, Middle East"),
    ("22-23", "Southern Asia, Central Asia"),
    ("24-27", "East Asia (China, Japan, Korea, SE Asia)"),
    ("28-29", "Philippines, Indonesia"),
    ("30-32", "Australia, New Zealand, Oceania"),
    ("33-38", "Africa (NW, NE, Central, E, S, W)"),
    ("39-40", "Madagascar region, Arctic"),
]

# ITU zones: summary ranges (there are 90 ITU zones worldwide).
ITU_ZONES = [
    ("1-9", "North America & Greenland"),
    ("10-16", "South America"),
    ("17-27", "Western & Central Europe, N Africa"),
    ("28-38", "Eastern Europe, Middle East, Africa"),
    ("39-52", "Asia (S, Central, E), Indian Ocean"),
    ("53-64", "Africa (Central & Southern), Oceania W"),
    ("65-75", "Oceania, Australia, Pacific"),
    ("76-90", "Asiatic Russia, Arctic, far NE Asia"),
]


def ctcss_rows():
    """CTCSS tones as (index, 'NN.N Hz', group-note) rows."""
    out = []
    for i, hz in enumerate(CTCSS_TONES, 1):
        note = "Motorola PL" if i <= 38 else "extended EIA"
        out.append(("%02d" % i, "%.1f Hz" % hz, note))
    return out


def qcode_rows():
    return [(code, "", meaning) for code, meaning in Q_CODES]


def cq_zone_rows():
    return [(z, region, "") for z, region in CQ_ZONES]


def itu_zone_rows():
    return [(z, region, "") for z, region in ITU_ZONES]


def ascii_rows(start=32, end=126):
    """Printable ASCII as (decimal, char, hex) rows."""
    out = []
    for c in range(start, end + 1):
        ch = chr(c)
        label = "space" if c == 32 else ch
        out.append((str(c), label, "0x%02X" % c))
    return out


# Registry the References screen iterates over: (name, description, rows_fn)
TABLES = [
    ("CTCSS tones", "Standard EIA/Motorola PL sub-audible tones (Hz).",
     ctcss_rows),
    ("Q-codes", "Common amateur Q-signals.", qcode_rows),
    ("CQ zones", "The 40 CQ zones by region.", cq_zone_rows),
    ("ITU zones", "The 90 ITU zones by region.", itu_zone_rows),
    ("ASCII table", "Printable ASCII (decimal / char / hex).", ascii_rows),
]


# ITU/NATO phonetic alphabet.
PHONETIC = [
    ("A", "Alfa"), ("B", "Bravo"), ("C", "Charlie"), ("D", "Delta"),
    ("E", "Echo"), ("F", "Foxtrot"), ("G", "Golf"), ("H", "Hotel"),
    ("I", "India"), ("J", "Juliett"), ("K", "Kilo"), ("L", "Lima"),
    ("M", "Mike"), ("N", "November"), ("O", "Oscar"), ("P", "Papa"),
    ("Q", "Quebec"), ("R", "Romeo"), ("S", "Sierra"), ("T", "Tango"),
    ("U", "Uniform"), ("V", "Victor"), ("W", "Whiskey"), ("X", "X-ray"),
    ("Y", "Yankee"), ("Z", "Zulu"),
]

# RST reporting system.
RST_ROWS = [
    ("RST", "", "Readability / Strength / Tone"),
    ("READABILITY", "1-5", ""),
    ("1", "", "Unreadable"),
    ("2", "", "Barely readable, occasional words"),
    ("3", "", "Readable with difficulty"),
    ("4", "", "Readable, little difficulty"),
    ("5", "", "Perfectly readable"),
    ("STRENGTH", "1-9", ""),
    ("1", "", "Faint, barely perceptible"),
    ("5", "", "Fairly good"),
    ("9", "", "Extremely strong"),
    ("TONE", "1-9", "CW only"),
    ("1", "", "Extremely rough"),
    ("5", "", "Slightly modulated note"),
    ("9", "", "Perfect tone, no ripple"),
    ("note", "", "Satellite SSB reports are RS only (e.g. 5x9);"),
    ("", "", "Doppler smears tone, so judge S-units by ear."),
]

# Radio-math cheat sheet, distilled from the ARRL Handbook "Radio Mathematics"
# supplement. Rows are (section-or-blank, expression, note).
RADIO_MATH = [
    ("DECIBELS", "dB = 10 log(P/P0)", ""),
    ("", "x2 power = +3 dB", "x0.5 = -3 dB"),
    ("", "x4 = +6   x10 = +10   x100 = +20", ""),
    ("", "+1 dB ~ x1.26   +6 dB ~ x4", ""),
    ("", "dBm: 0=1mW 30=1W 50=100W 60=1kW", ""),
    ("", "voltage: dB = 20 log(V/V0)", ""),
    ("AC VOLTAGE", "Vrms = 0.707 x Vpeak", "sine"),
    ("", "Vpeak = 1.414 x Vrms", ""),
    ("", "Vpk-pk = 2 x Vpeak", ""),
    ("", "Vavg = 0.637 x Vpeak", ""),
    ("", "P(rms) into R = Vrms^2 / R", ""),
    ("PREFIXES", "p=-12 n=-9 u=-6 m=-3", "x10^n"),
    ("", "k=+3 M=+6 G=+9 T=+12", ""),
    ("CONSTANTS", "c = 2.998e8 m/s", "speed of light"),
    ("", "wavelength(m) = 300 / f(MHz)", ""),
    ("", "1/4 wave(ft) = 234 / f(MHz)", ""),
    ("", "k (Boltzmann) = 1.38e-23 J/K", ""),
    ("", "Earth R = 6378 km   GM = 398600", ""),
    ("REACTANCE", "Xc = 1/(2 pi f C)", ""),
    ("", "Xl = 2 pi f L", ""),
    ("", "f0 = 1/(2 pi sqrt(L C))", ""),
    ("", "Q = f0 / bandwidth", ""),
    ("IMPEDANCE", "Z = sqrt(R^2 + X^2)", ""),
    ("", "SWR = (1+|G|)/(1-|G|)", ""),
    ("", "|G| = (SWR-1)/(SWR+1)", ""),
    ("", "return loss(dB) = -20 log|G|", ""),
    ("TIME CONST", "tau = R C   (or L/R)", ""),
    ("", "1t=63% 2t=86% 3t=95%", ""),
    ("", "4t=98% 5t=99% (charged)", ""),
    ("OHM / POWER", "V = I R", ""),
    ("", "P = V I = I^2 R = V^2 / R", ""),
    ("source", "ARRL Radio Mathematics", ""),
]

# CubeSatSim command & control quick reference (AMSAT CubeSat Simulator).
# Offline reference only - OrbitDeck does not transmit these commands.
CUBESATSIM_C2C = [
    ("Radio C2C", "uplink FM on the C2C RX freq", "435.000 MHz default"),
    ("DTMF", "dial <mode #> then #", ""),
    ("APRS", "packet text  MODE=<letter>", ""),
    ("Carrier", "key up briefly -> mode steps +1", "sim reboots; LED blinks mode"),
    ("MODES", "#", "letter"),
    ("APRS / AFSK", "1", "a"),
    ("FSK / DUV", "2", "f"),
    ("BPSK", "3", "b"),
    ("SSTV camera", "4", "s"),
    ("CW beacon", "5", "m"),
    ("X-band rptr", "6", "e"),
    ("FUNcube", "7", "j"),
    ("CONSOLE", "ssh pi@cubesatsim", ""),
    ("", "CubeSatSim/config -h", "all options"),
    ("", "-q N", "squelch (8 = C2C RX off)"),
    ("", "-F", "set TX/RX freq (420-450)"),
    ("", "-A", "command ANOTHER sim (APRS)"),
    ("", "-o", "telemetry beacon on/off"),
    ("Sim TX", "~434.9 MHz FM", ""),
    ("Details", "github.com/alanbjohnston/CubeSatSim", "wiki: Command and Control"),
    ("note", "table per v2.x docs", "check the wiki for your firmware"),
]


def phonetic_rows():
    return [(ltr, word, "") for ltr, word in PHONETIC]


def rst_rows():
    return list(RST_ROWS)


def radio_math_rows():
    return list(RADIO_MATH)


def cubesatsim_rows():
    return list(CUBESATSIM_C2C)


TABLES.extend([
    ("Phonetic alphabet", "ITU/NATO phonetic alphabet.", phonetic_rows),
    ("RST system", "Readability / Strength / Tone reporting.", rst_rows),
    ("Radio math", "Decibels, AC voltage, constants and the common formulas.",
     radio_math_rows),
    ("CubeSatSim C2C", "Commanding AMSAT's CubeSat Simulator over the air.",
     cubesatsim_rows),
])


# IARU/ITU amateur band plan, satellite band designators and common satellite
# mode conventions. Section headings have empty second/third fields.
BAND_PLAN = [
    ('LF / MF', '', ''),
    ('2200 m', '135.7-137.8 kHz', 'LF; worldwide, tiny allocation'),
    ('630 m', '472-479 kHz', 'MF; secondary, low power'),
    ('HF (ITU REGIONS DIFFER)', '', ''),
    ('160 m', '1.8-2.0 MHz', 'R1 1.810-2.000, R2 1.800-2.000, R3 varies'),
    ('80 m', '3.5-4.0 MHz', 'R1 3.5-3.8, R2 3.5-4.0, R3 3.5-3.9'),
    ('60 m', '5.3-5.4 MHz', 'Channelised/limited; varies by country'),
    ('40 m', '7.0-7.3 MHz', 'R1/R3 7.0-7.2, R2 7.0-7.3'),
    ('30 m', '10.1-10.15 MHz', 'WARC; CW/data, no phone'),
    ('20 m', '14.0-14.35 MHz', 'Worldwide; primary DX band'),
    ('17 m', '18.068-18.168 MHz', 'WARC'),
    ('15 m', '21.0-21.45 MHz', 'Worldwide'),
    ('12 m', '24.89-24.99 MHz', 'WARC'),
    ('10 m', '28.0-29.7 MHz', 'Worldwide; FM >29.5, sats 29.3-29.51'),
    ('VHF', '', ''),
    ('6 m', '50-54 MHz', 'R1 50-52 (some 50-51), R2/R3 50-54'),
    ('6m calling', '50.313 FT8, 50.110 DX SSB, 50.090 CW', ''),
    ('4 m', '70.0-70.5 MHz', 'R1 only, some countries; none in R2/R3'),
    ('2 m', '144-148 MHz', 'R1 144-146, R2/R3 144-148'),
    ('2m calling', '144.200 SSB, 144.174 FT8', ''),
    ('2m EME', '144.100-144.160 CW, 144.115-144.140 JT65/Q65', ''),
    ('2m sat', '145.8-146.0 satellite subband', ''),
    ('UHF', '', ''),
    ('1.25 m', '222-225 MHz', 'R2 only (219-220 data)'),
    ('70 cm', '430-440 MHz', 'R1 430-440, R2 420-450, R3 430-440'),
    ('70cm calling', '432.100 SSB/CW, 432.174 FT8', ''),
    ('70cm EME', '432.000-432.070 CW, 432.065 JT65', ''),
    ('70cm sat', '435-438 satellite subband', ''),
    ('33 cm', '902-928 MHz', 'R2 only'),
    ('23 cm', '1240-1300 MHz', '1296 weak-signal; sat 1260-1270 uplink'),
    ('23cm EME', '1296.000 CW, 1296.065 JT65/Q65', ''),
    ('MICROWAVE (SHF/EHF)', '', ''),
    ('13 cm', '2300-2450 MHz', 'Segments vary; 2304/2320/2400 WS'),
    ('13cm sat', '2400-2450 (QO-100 NB 2400.25 up)', ''),
    ('9 cm', '3300-3500 MHz', 'Regional; 3400 common'),
    ('5 cm', '5650-5925 MHz', '5760 WS; sat 5830-5850 down'),
    ('3 cm', '10.0-10.5 GHz', '10368 WS/EME; 10.489 QO-100 down'),
    ('1.2 cm', '24.0-24.25 GHz', '24192 WS/EME'),
    ('6 mm', '47.0-47.2 GHz', ''),
    ('4 mm', '76-81 GHz', ''),
    ('2.5 mm', '122.25-123 GHz', ''),
    ('2 mm', '134-141 GHz', ''),
    ('1 mm', '241-250 GHz', ''),
    ('sub-mm/light', '>275 GHz, IR, optical', 'Experimental; laser/optical DX'),
    ('SATELLITE BAND DESIGNATORS (IARU)', '', ''),
    ('H / 15m', '21 MHz', ''),
    ('A / 10m', '29 MHz', ''),
    ('V / 2m', '145 MHz', ''),
    ('U / 70cm', '435 MHz', ''),
    ('L / 23cm', '1260 MHz (uplink)', ''),
    ('S / 13cm', '2400 MHz', ''),
    ('S2', '3.4 GHz', ''),
    ('C / 5cm', '5840 MHz', ''),
    ('X / 3cm', '10.45 GHz', ''),
    ('K / 1.2cm', '24 GHz', ''),
    ('COMMON SAT MODES (UP/DOWN)', '', ''),
    ('Mode V/U (J)', '145 up / 435 down', 'Most LEO linear/FM'),
    ('Mode U/V (B)', '435 up / 145 down', 'AO-7 Mode B etc.'),
    ('Mode L/U', '1260 up / 435 down', ''),
    ('Mode U/S', '435 up / 2400 down', ''),
    ('QO-100 NB', '2400.25 up / 10489.75 down', 'GEO, EU/Africa/Asia'),
]


def band_plan_rows():
    return list(BAND_PLAN)


TABLES.append(("Band plan",
               "Amateur bands, satellite subbands, IARU designators and modes.",
               band_plan_rows))


# ---------------------------------------------------------------------------
# Character / raw-value lookup (audit item D)
# ---------------------------------------------------------------------------
# The ASCII table alone answers "what is 0x41". An operator working RTTY or
# reading CI-V frequency bytes needs more: the Baudot/ITA2 letters- and
# figures-shift meaning of a 5-bit value, the Morse pattern, and the BCD
# reading. CardSat shows all of it for one value at once.

ASCII_CONTROL = [
    "NUL", "SOH", "STX", "ETX", "EOT", "ENQ", "ACK", "BEL", "BS", "TAB",
    "LF", "VT", "FF", "CR", "SO", "SI", "DLE", "DC1", "DC2", "DC3", "DC4",
    "NAK", "SYN", "ETB", "CAN", "EM", "SUB", "ESC", "FS", "GS", "RS", "US",
    "SP",
]

# ITA2 / US-TTY, 5-bit codes 0..31.
ITA2_LTRS = ["NUL", "E", "LF", "A", "SP", "S", "I", "U", "CR", "D", "R", "J",
             "N", "F", "C", "K", "T", "Z", "L", "W", "H", "Y", "P", "Q", "O",
             "B", "G", "FIGS", "M", "X", "V", "LTRS"]
ITA2_FIGS = ["NUL", "3", "LF", "-", "SP", "BEL", "8", "7", "CR", "$", "4",
             "'", ",", "!", ":", "(", "5", '"', ")", "2", "#", "6", "0", "1",
             "9", "?", "&", "FIGS", ".", "/", ";", "LTRS"]

MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "/": "-..-.", "-": "-....-",
    "=": "-...-", "+": ".-.-.",
}


def char_lookup(value):
    """Everything one byte represents, as (label, value) rows.

    ``value`` is 0-255. Shows the four bases, the ASCII meaning (control codes
    by name), Morse where one exists, the ITA2 shift meanings when the value
    fits in five bits, and the BCD reading - CI-V frequency bytes are BCD, so
    that row is not a curiosity.
    """
    try:
        v = int(value) & 0xFF
    except (TypeError, ValueError):
        return [("error", "not a byte value")]
    rows = [
        ("Hex", "0x%02X" % v),
        ("Decimal", "%d" % v),
        ("Octal", "0o%o" % v),
        ("Binary", format(v, "08b")),
    ]
    if v < 33:
        rows.append(("ASCII", ASCII_CONTROL[v] + " (control)"))
    elif v == 127:
        rows.append(("ASCII", "DEL (control)"))
    elif v < 127:
        rows.append(("ASCII", repr(chr(v)).strip("'")))
    else:
        rows.append(("ASCII", "(not 7-bit ASCII)"))
    ch = chr(v).upper() if 32 < v < 127 else ""
    if ch in MORSE:
        rows.append(("Morse", MORSE[ch]))
    if v < 32:
        rows.append(("ITA2 letters", ITA2_LTRS[v]))
        rows.append(("ITA2 figures", ITA2_FIGS[v]))
    hi, lo = (v >> 4), (v & 0x0F)
    if hi < 10 and lo < 10:
        rows.append(("BCD", "%d%d" % (hi, lo)))
    else:
        rows.append(("BCD", "invalid (nibble > 9)"))
    return rows


def char_lookup_rows(value=65):
    """Tools-hub wrapper: the hub's contract is (label, value, note) triples,
    while char_lookup() returns pairs for direct display."""
    return [(lab, val, "") for lab, val in char_lookup(value)]


def ita2_rows():
    """The whole ITA2 table, for the References browser."""
    return [("%2d  0b%s" % (i, format(i, "05b")), ITA2_LTRS[i], ITA2_FIGS[i])
            for i in range(32)]


def morse_rows():
    return [(k, MORSE[k], "") for k in sorted(MORSE)]


# ---------------------------------------------------------------------------
# Orbit types and amateur-satellite history (audit item C)
# ---------------------------------------------------------------------------
ORBIT_TYPES = [
    ("LEO", "160-2000 km, 90-128 min",
     "Most amateur satellites. Short passes, high Doppler."),
    ("Sun-synchronous", "~600-800 km, incl ~98 deg",
     "Crosses the equator at the same local time each pass."),
    ("MEO", "2000-35786 km",
     "Navigation constellations; long passes, low Doppler."),
    ("Molniya", "e~0.74, incl 63.4 deg, 12 h",
     "Long dwell over high latitudes near apogee. AO-10, AO-13 used this."),
    ("GEO", "35786 km, incl ~0 deg",
     "Fixed in the sky. QO-100 is the amateur example."),
    ("HEO", "highly elliptical",
     "Hours of access near apogee; AO-7's successors aimed here."),
    ("Polar", "incl ~90 deg",
     "Covers every latitude; passes at all longitudes over a day."),
    ("Retrograde", "incl > 90 deg",
     "Travels against Earth's rotation; ground track drifts east."),
]


def orbit_type_rows():
    return [(n, d, w) for n, d, w in ORBIT_TYPES]


SAT_HISTORY = [
    ("1961", "OSCAR 1", "First amateur satellite; battery HI beacon, 22 days."),
    ("1962", "OSCAR 2", "Similar to OSCAR 1 with improved thermal design."),
    ("1965", "OSCAR 3", "First amateur transponder - relayed live QSOs."),
    ("1970", "AO-5", "First amateur satellite commanded from the ground."),
    ("1974", "AO-7", "Mode A/B; still worked today after returning in 2002."),
    ("1978", "AO-8", "Mode A and J; long service life."),
    ("1983", "AO-10", "Molniya orbit, long-duration DX via Mode B."),
    ("1990", "AO-16 / LO-19", "Microsat class; digital store-and-forward."),
    ("1993", "AO-13", "High-orbit workhorse; re-entered 1996."),
    ("1998", "ISS", "Amateur radio aboard the station, from packet to SSTV."),
    ("2000", "AO-40", "Ambitious HEO; crippled by a propulsion failure."),
    ("2002", "AO-51", "Popular FM repeater; ceased 2011."),
    ("2011", "SO-50 era", "Small FM birds dominate everyday operating."),
    ("2013", "FUNcube-1 (AO-73)", "Education-focused with linear transponder."),
    ("2019", "QO-100", "First amateur geostationary transponder."),
    ("2022", "IO-117 (GreenCube)", "Digipeater in MEO; long-range digital."),
]


def sat_history_rows():
    return [(y, n, d) for y, n, d in SAT_HISTORY]


TABLES.extend([
    ("ITA2 / Baudot", "5-bit RTTY codes, letters and figures shift.",
     ita2_rows),
    ("Morse", "Morse patterns for letters, digits and punctuation.",
     morse_rows),
    ("Orbit types", "Orbit classes and what they mean for operating.",
     orbit_type_rows),
    ("Satellite history", "Milestones in amateur satellites.",
     sat_history_rows),
])


def zone_lookup(query):
    """DXCC entity lookup: prefix or name to entity, coordinates and bearing.

    Deliberately does NOT report a CQ or ITU zone number. The bundled tables
    are ranges with regional descriptions, not polygons, so any zone derived
    from them is a guess - an early cut here mapped Japan into "17-19 Asiatic
    Russia" because the word "Asia" appears in that row's description. A wrong
    zone in a contest log is worse than no zone, so this returns what the data
    actually supports and leaves the zone tables to be read directly.
    """
    from ..data.dxcc import DXCC
    q = (query or "").strip().upper()
    if not q:
        return []
    hits = []
    for pfx, (name, lat, lon) in DXCC.items():
        if pfx.upper() == q or q in name.upper():
            hits.append((pfx, name, lat, lon))
    hits.sort(key=lambda h: (h[0].upper() != q, h[0]))
    return [(pfx, name, "%.1f\u00b0, %.1f\u00b0" % (lat, lon))
            for pfx, name, lat, lon in hits[:8]]
