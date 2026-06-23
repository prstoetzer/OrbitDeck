"""learnsheet.py - a one-page "Orbits 101" classroom handout, generated through
the same matplotlib/PdfPages pipeline as the rest of OrbitDeck's printables and
carrying the OrbitDeck + author credit.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages   # noqa: E402

PAGE_W_IN = 8.5
PAGE_H_IN = 11.0


def _brand(fig):
    # Centred branding credit at the foot of every handout page, at y=0.045.
    # The handout pages lay out fixed reference content with a manually
    # decremented ``y`` cursor (no auto-overflow guard), so KEEP CONTENT ABOVE
    # ~y=0.09: if you add items to the fixed lists below and the cursor runs
    # lower than that, the text will start printing on top of this credit. The
    # current content is well clear; verified by rendering every page.
    try:
        from .. import __version__ as _ver
    except Exception:
        _ver = ""
    fig.text(0.5, 0.045,
             "OrbitDeck%s \u2022 Paul Stoetzer, N8HM"
             % (" v%s" % _ver if _ver else ""),
             ha="center", va="bottom", fontsize=6.5, color="#9a9a9a")


_ELEMENTS = [
    ("Mean altitude / mean motion",
     "How high the orbit is. Sets the period via Kepler's third law: "
     "T = 2\u03c0\u221a(a\u00b3/\u03bc). Higher \u2192 slower, wider footprint, "
     "longer passes."),
    ("Eccentricity (e)",
     "Shape of the ellipse (0 = circle). Apogee = a(1+e), perigee = a(1\u2212e). "
     "Fast at perigee, slow at apogee (equal areas in equal times)."),
    ("Inclination (i)",
     "Tilt of the orbit plane to the equator. Ground track reaches \u00b1i in "
     "latitude. i > 90\u00b0 is retrograde."),
    ("RAAN (\u03a9)",
     "Rotation of the orbit plane about Earth's axis \u2014 sets which "
     "longitudes the passes fall over."),
    ("Argument of perigee (\u03c9)",
     "Orientation of the ellipse within its plane \u2014 the latitude where the "
     "satellite is lowest."),
    ("Mean anomaly (M)",
     "The satellite's position along the orbit at the epoch."),
]

_XPDR_TYPES = [
    ("FM repeater",
     "A single uplink and downlink channel, like a terrestrial repeater in the "
     "sky. One person talks at a time; bring a tone (CTCSS) if required. Easy "
     "to work with a handheld and a small antenna (e.g. SO-50)."),
    ("Linear transponder",
     "Relays a whole passband (typically 30-60 kHz) of SSB and CW signals at "
     "once \u2014 many stations share it simultaneously. INVERTING ones flip "
     "the passband: tuning your uplink up moves your downlink down (e.g. "
     "RS-44)."),
    ("Digital transponder / store-and-forward",
     "Carries data (BPSK, GMSK, AFSK, etc.) rather than voice; some store "
     "messages and dump them over a ground station later."),
]

_RADIO_NOTES = [
    ("Modes", "The mode names the uplink band then the downlink band: U/V is "
     "70 cm up / 2 m down; V/U is the reverse. It tells you which radios and "
     "antennas you need."),
    ("Doppler", "Approaching, the downlink is heard high and falls through the "
     "pass; you tune DOWN. On a linear bird both legs shift \u2014 keep the "
     "downlink centred by retuning the uplink (opposite direction if "
     "inverting)."),
    ("Polarization", "Satellites use circular polarization to beat the "
     "ionosphere's Faraday rotation; a linear ground antenna fades as the "
     "rotation drifts."),
    ("Full duplex", "Hearing your own downlink while you transmit lets you "
     "zero-beat onto a clear spot and follow Doppler \u2014 the single biggest "
     "help when working linear birds."),
]

_FAMILIES = [
    ("LEO", "~200-2000 km. Short fast passes; the home of amateur satellites "
     "and the ISS."),
    ("Sun-synchronous", "~98\u00b0 inclined LEO that precesses ~1\u00b0/day to "
     "follow the Sun \u2014 used by imaging satellites."),
    ("MEO", "~20,000 km. Navigation constellations (GPS, Galileo)."),
    ("Molniya / HEO", "Highly elliptical, 63.4\u00b0 inclined; lingers over the "
     "northern hemisphere."),
    ("GEO", "~35,786 km, equatorial, ~24 h period \u2014 appears to hover."),
]


def generate_orbits_101_pdf(path, page=None):
    global PAGE_W_IN, PAGE_H_IN
    from .pagesize import page_dims
    PAGE_W_IN, PAGE_H_IN = page_dims(page)
    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        fig.text(0.5, 0.955, "Orbits 101", ha="center", fontsize=20,
                 fontweight="bold", color="#0b3d91")
        fig.text(0.5, 0.93, "A one-page reference to orbital elements and "
                 "orbit families", ha="center", fontsize=10, color="#444444")

        y = 0.89
        fig.text(0.07, y, "The six orbital elements", fontsize=13,
                 fontweight="bold", color="#0b3d91")
        y -= 0.028
        for name, desc in _ELEMENTS:
            fig.text(0.08, y, name, fontsize=10.5, fontweight="bold",
                     color="#111111")
            y -= 0.020
            for line in _wrap(desc, 92):
                fig.text(0.10, y, line, fontsize=9.5, color="#222222")
                y -= 0.017
            y -= 0.006

        y -= 0.01
        fig.text(0.07, y, "Common orbit families", fontsize=13,
                 fontweight="bold", color="#0b3d91")
        y -= 0.028
        for name, desc in _FAMILIES:
            fig.text(0.08, y, name, fontsize=10.5, fontweight="bold",
                     color="#111111")
            for i, line in enumerate(_wrap(desc, 78)):
                fig.text(0.26, y, line, fontsize=9.5, color="#222222")
                y -= 0.017
            y -= 0.006

        y -= 0.01
        fig.text(0.07, y, "Key formulas", fontsize=13, fontweight="bold",
                 color="#0b3d91")
        y -= 0.028
        formulas = [
            "Period:  T = 2\u03c0 \u221a(a\u00b3 / \u03bc)   "
            "(\u03bc = 398,600 km\u00b3/s\u00b2)",
            "Footprint half-angle:  \u03b3 = arccos(R\u2091 / (R\u2091 + h))",
            "Apogee / perigee altitude:  a(1\u00b1e) \u2212 R\u2091",
            "Sun-sync nodal drift:  ~ +0.986\u00b0 / day",
        ]
        for f in formulas:
            fig.text(0.10, y, f, fontsize=10, color="#222222",
                     family="DejaVu Sans")
            y -= 0.022

        _brand(fig)
        pdf.savefig(fig)
        plt.close(fig)

        # --- page 2: radio & transponders ---
        fig2 = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        fig2.text(0.5, 0.955, "Working Satellites by Radio", ha="center",
                  fontsize=20, fontweight="bold", color="#0b3d91")
        fig2.text(0.5, 0.93, "Transponders, modes, Doppler, and the link",
                  ha="center", fontsize=10, color="#444444")
        y = 0.89
        fig2.text(0.07, y, "Transponder types", fontsize=13,
                  fontweight="bold", color="#0b3d91")
        y -= 0.028
        for name, desc in _XPDR_TYPES:
            fig2.text(0.08, y, name, fontsize=10.5, fontweight="bold",
                      color="#111111")
            y -= 0.020
            for line in _wrap(desc, 92):
                fig2.text(0.10, y, line, fontsize=9.5, color="#222222")
                y -= 0.017
            y -= 0.006
        y -= 0.01
        fig2.text(0.07, y, "Modes & Doppler", fontsize=13, fontweight="bold",
                  color="#0b3d91")
        y -= 0.028
        for name, desc in _RADIO_NOTES:
            fig2.text(0.08, y, name, fontsize=10.5, fontweight="bold",
                      color="#111111")
            for i, line in enumerate(_wrap(desc, 80)):
                fig2.text(0.22, y, line, fontsize=9.5, color="#222222")
                y -= 0.017
            y -= 0.006
        _brand(fig2)
        pdf.savefig(fig2)
        plt.close(fig2)

        # --- page 3: operating, bands, antennas ---
        fig3 = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        fig3.text(0.5, 0.955, "Operating & Antennas", ha="center",
                  fontsize=20, fontweight="bold", color="#0b3d91")
        fig3.text(0.5, 0.93, "Etiquette, bands, and pointing your station",
                  ha="center", fontsize=10, color="#444444")
        y = 0.89
        sections = [("Operating practice", _OPERATING),
                    ("Bands & licensing", _BANDS),
                    ("Antennas & pointing", _ANTENNAS)]
        for title, rows in sections:
            fig3.text(0.07, y, title, fontsize=13, fontweight="bold",
                      color="#0b3d91")
            y -= 0.028
            for name, desc in rows:
                fig3.text(0.08, y, name, fontsize=10.5, fontweight="bold",
                          color="#111111")
                y -= 0.020
                for line in _wrap(desc, 92):
                    fig3.text(0.10, y, line, fontsize=9.5, color="#222222")
                    y -= 0.017
                y -= 0.006
            y -= 0.012
        _brand(fig3)
        pdf.savefig(fig3)
        plt.close(fig3)

        # --- page 4: orbit geometry & the bigger picture ---
        fig4 = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
        fig4.text(0.5, 0.955, "Geometry & the Bigger Picture", ha="center",
                  fontsize=20, fontweight="bold", color="#0b3d91")
        fig4.text(0.5, 0.93, "Speed, range, ground-track drift, and "
                  "constellations", ha="center", fontsize=10, color="#444444")
        y = 0.89
        for name, desc in _GEOMETRY:
            fig4.text(0.08, y, name, fontsize=10.5, fontweight="bold",
                      color="#111111")
            y -= 0.020
            for line in _wrap(desc, 92):
                fig4.text(0.10, y, line, fontsize=9.5, color="#222222")
                y -= 0.017
            y -= 0.008
        _brand(fig4)
        pdf.savefig(fig4)
        plt.close(fig4)
    return path


def _wrap(text, width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


_OPERATING = [
    ("FM birds, one at a time",
     "A single-channel repeater in the sky: only one station transmits at a "
     "time. Listen first, give your call and grid, keep it brief, let others "
     "in. A dual-band handheld and a small beam will work them."),
    ("Linear birds, full duplex",
     "SSB/CW transponders carry many contacts across a passband. Work them full "
     "duplex so you hear your own downlink, find a clear spot, and follow "
     "Doppler. Use only the uplink power you need."),
    ("Exchange & logging",
     "Trade callsign and grid; log time in UTC, the satellite, and the grid. "
     "Many chase grids, states, or DXCC entities via satellite."),
]

_BANDS = [
    ("Get licensed to transmit",
     "Tracking and listening are open to all, but transmitting needs an amateur "
     "license; satellite privileges depend on your class and country."),
    ("The amateur-satellite service",
     "Birds use set segments within the amateur bands \u2014 commonly parts of "
     "2 m and 70 cm, with some on 10 m, 23 cm, 13 cm and up. Operate only where "
     "your license permits."),
]

_ANTENNAS = [
    ("Gain vs beamwidth",
     "More antenna gain means a narrower beam: a high-gain Yagi must be aimed "
     "and tracked, while a low-gain omni hears the whole sky weakly. For LEO "
     "passes a modest hand-aimed beam is a good balance."),
    ("Circular polarization",
     "Satellites transmit circular polarization to beat the ionosphere's "
     "Faraday rotation; a fixed linear ground antenna fades as the rotation "
     "drifts."),
    ("Point where it is, not where it was",
     "Use the Pointing tab (or a rotator) to follow the pass in azimuth and "
     "elevation; low passes need a clear horizon, high passes pass nearly "
     "overhead."),
]


_GEOMETRY = [
    ("Orbital speed (vis-viva)",
     "A satellite moves fastest at perigee and slowest at apogee, and lower "
     "orbits are faster overall: ~7.7 km/s in low Earth orbit, ~3 km/s at "
     "geostationary altitude. v = sqrt(mu*(2/r - 1/a))."),
    ("Slant range vs elevation",
     "Directly overhead, a satellite is only its altitude away; near the "
     "horizon you look across the Earth's curve, so it is several times "
     "farther \u2014 weaker signal, more atmosphere, and more Doppler. This is "
     "why high passes are easier than low ones."),
    ("Radio horizon",
     "From altitude h the horizon distance is arccos(Re/(Re+h)) \u2014 the same "
     "circle as the footprint. Higher orbits see farther, which is why two "
     "satellites can cross-link only while each is above the other's horizon."),
    ("Ground-track westward drift",
     "While the satellite orbits once, the Earth turns east under it, so each "
     "pass crosses the equator farther west (~23\u00b0 per orbit for a low "
     "satellite). When a whole number of orbits fits a sidereal day, the track "
     "repeats \u2014 the basis of repeat-ground-track orbits."),
    ("Why passes cluster",
     "Because the track drifts a fixed amount each orbit, you often get several "
     "workable passes in a row as the track walks across your area, then a gap "
     "of hours until it comes back around."),
    ("How many satellites for coverage",
     "A low satellite is only in view for minutes, so continuous coverage needs "
     "many spread around the orbit; the higher the orbit, the larger each "
     "footprint and the fewer required. Three geostationary satellites cover "
     "nearly the whole Earth, while low-orbit internet constellations need "
     "thousands."),
    ("Sunlight & eclipse",
     "Most satellites pass through the Earth's shadow part of each orbit, "
     "running on battery, then recharge in sunlight. How much shadow depends on "
     "the beta angle (orbit-plane tilt to the Sun); at high enough beta the "
     "satellite stays lit the whole way around."),
    ("Changing orbits (delta-v)",
     "Raising or lowering an orbit takes two engine burns (a Hohmann transfer): "
     "speed up to raise the far side, coast halfway, then speed up again to "
     "circularise. Changing the orbit's tilt is far more expensive because it "
     "redirects the whole orbital velocity \u2014 which is why satellites launch "
     "into their target inclination rather than change it later."),
]
