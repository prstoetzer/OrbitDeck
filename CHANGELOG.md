# Changelog

All notable changes to OrbitDeck are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning.

## [0.1.0] - 2025

Initial public release. A cross-platform desktop port of the tracking and
orbital-analysis features of the CardSat device project (radio/CAT and rotator
control intentionally excluded).

### Added
- Pure-Python SGP4/SDP4 propagator (WGS72), verified against the canonical
  Vallado AIAA-2006-6753 reference vector; zero required orbital dependencies.
- Automatic use of the C-accelerated `sgp4` package when installed (full SDP4
  accuracy for deep-space orbits).
- Thirteen analysis screens: Track, Next Passes, Pass Detail, Polar, World Map,
  Ground Track, Orbital Analysis (9 sub-pages), Illumination, Sun/Moon, Mutual
  Windows, Multi-Day Pass Progression, Satellites, Location.
- World map with bundled offline coastline; full-resolution Natural Earth
  coastlines when `cartopy` is installed.
- Online GP catalog (AMSAT) and transponder (SatNOGS) fetch via the standard
  library; bundled sample catalog for instant offline use.
- Maidenhead grid in/out, footprints, eclipse, solar beta, Doppler, and
  two-station mutual-visibility windows.
- Engine test suite and CI (tests run with and without the optional `sgp4`
  backend).
