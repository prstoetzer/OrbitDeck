"""OrbitTerm - a curses terminal UI for OrbitDeck.

A headless, SSH-friendly terminal application for amateur-radio satellite
work. It ships standalone and reuses the
exact OrbitDeck engine (SGP4/SDP4 propagator, pass prediction, Doppler, orbital
analysis) and the same ~/.orbitdeck config and AMSAT catalog cache, so its
numbers match the GUI. Pure standard library (curses) - no extra dependencies.
"""

__version__ = "0.39.2"
