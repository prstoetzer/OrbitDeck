"""OrbitTerm - a curses terminal UI for OrbitDeck.

A headless, SSH-friendly companion to the OrbitDeck desktop GUI. It reuses the
exact OrbitDeck engine (SGP4/SDP4 propagator, pass prediction, Doppler, orbital
analysis) and the same ~/.orbitdeck config and AMSAT catalog cache, so its
numbers match the GUI. Pure standard library (curses) - no extra dependencies.
"""

__version__ = "0.37.0"
