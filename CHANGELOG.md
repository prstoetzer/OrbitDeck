# Changelog

All notable changes to OrbitDeck are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning.

## [0.10.1]

### Changed
- **OSCARLOCATOR PDF export, much improved:**
  * `cartopy` is now a core dependency, so the base map uses full-resolution
    Natural Earth coastlines (bundled coastlines remain a fallback).
  * Base map gained a **lat/lon graticule** (parallels and meridians every 15°)
    and denser azimuth spokes.
  * Footprint overlay now has **distance rings every 1000 km** and **radial lines
    every 15°**.
  * Path-arc overlay is now the **classic rotatable any-orbit arc** (station-
    independent), with **1-minute tick marks** (larger every 10 minutes) and an
    **inset diagram of the per-pass advance angle** (degrees to rotate the arc
    for each successive pass).

## [0.10.0]

### Added
- **Printable OSCARLOCATOR PDF export** (Track screen → “Make OSCARLOCATOR
  PDF…”). Generates a 3-page vector PDF for the selected satellite, all drawn
  to the same angular scale so the overlays register:
  * an **azimuthal-equidistant base map** centred on your station, with range
    rings, azimuth spokes and coastlines (print on paper/card);
  * a **footprint coverage circle** sized for the satellite’s altitude (print on
    transparency); and
  * a **ground-track path arc** for the satellite’s inclination (print on
    transparency).
  Pin the transparencies through the centre cross over your QTH to build a
  homemade OSCARLOCATOR for any satellite.

### Fixed
- TEME→geodetic sub-point conversion no longer divides by zero for
  high-altitude near-equatorial (geostationary) satellites; pole-crossing
  positions are also handled. (Surfaced by the OSCARLOCATOR export for QO-100.)

## [0.9.6]

### Added
- **Crossings List** tab on the Orbital Analysis screen: a plain table of the
  ascending equator-crossing **date, time (UTC), and longitude** for the next 7
  days, alongside the existing OSCARLocator chart. Scrollable, with longitudes
  shown as °E/°W.

## [0.9.5]

### Added
- **Equatorial Crossings** tab on the Orbital Analysis screen: charts the
  ascending equator-crossing times and longitudes for the selected satellite
  over the next 7 days, for use with an OSCARLocator. The chart shows
  longitude vs. days-from-now with the soonest crossings labelled by UTC time.
- New `Predictor.ascending_nodes(from, to)` engine method that finds ascending
  node crossings (sub-latitude - to +) by coarse scan plus bisection refinement.

## [0.9.4]

### Documentation
- README now correctly states that the `sgp4` package is a **required
  dependency** (since 0.9.2), not an optional extra. Updated the intro, the
  optional-extras list, the accuracy/backend section, and the testing notes; the
  bundled pure-Python propagator is described as the fallback rather than the
  default.

## [0.9.3]

### Fixed
- **CelesTrak GP fetches failed unhelpfully.** CelesTrak frequently returns an
  HTTP 200 with a plain-text error body (rate-limit / bandwidth throttle, which
  they enforce since Feb 2026, or “Invalid query”) rather than JSON. OrbitDeck
  previously tried to parse that as JSON and failed with a cryptic error, and an
  empty result could wipe the catalog. Now the GP update:
  * detects non-JSON / error / empty responses and reports a clear, specific
    message (rate-limited vs. bad group vs. empty), and
  * loads into a temporary catalog first, so a failed or empty fetch never
    clobbers the working satellite list.
- Added a note in **Settings** that CelesTrak rate-limits requests and updates at
  most every 2 hours.

## [0.9.2]

### Fixed
- **Geostationary / deep-space satellites could show incorrect visibility** (e.g.
  QO-100 / Es'hail-2 appearing to rise and set from a location it is never
  visible from). The bundled pure-Python propagator's deep-space (SDP4) resonance
  terms are only approximate and mis-place synchronous orbits. The reference
  `sgp4` propagator (full SDP4) is now a **required dependency** and is bundled
  in the PyInstaller spec, so deep-space birds propagate correctly.
- As a safety net, when only the approximate backend is available, deep-space
  satellites are flagged in the screen header with a **reduced-accuracy warning**
  rather than silently showing a wrong position/visibility.

## [0.9.1]

### Changed
- Renamed the **Location** screen to **Settings** (it now holds both the observer
  site and the GP element-source picker).
- The Orbital Analysis **Doppler** page now has a **downlink selector**: choose
  any of the satellite's transponders from the database to model its Doppler
  curve (linear transponders use the passband center). Defaults to 145.800 MHz
  when a satellite has no transponder data.

## [0.9.0]

### Added
- **Manual orbital elements.** Satellites → “Add manual satellite…” lets you
  enter a satellite by its GP mean elements (name, NORAD, epoch, inclination,
  RAAN, eccentricity, arg of perigee, mean anomaly, mean motion, BSTAR). Manual
  satellites are stored separately and persist across GP refreshes.
- **Manual transponders.** Track → “+” next to the transponder selector adds a
  transponder by hand (downlink/uplink low, downlink/uplink high, inverting,
  mode). Linear vs single-channel is inferred the CardSat way. Manual
  transponders are kept separately from the SatNOGS cache so a refresh won’t
  erase them.
- **Selectable GP source.** Location → “GP element source” lets you pull elements
  from AMSAT (default), a CelesTrak category (Amateur, CubeSats, Stations,
  Active, Weather, NOAA, GOES, GPS, …), or a custom OMM-JSON URL. The choice is
  saved and used by the next Update GP.

## [0.8.3]

### Fixed
- **Orbital Analysis "Live" page still flashing on macOS.** Its section header
  embedded the current time ("Look angles @ HH:MM:SS"), which changed every
  second and made the key/value panel treat the layout as new each tick —
  forcing a full relayout. The time moved to an in-place row and the section
  title is now static, so the page updates smoothly. Added a regression test.

## [0.8.2]

### Fixed
- **Choppy text updates on macOS** on the live pages (Sun/Moon, Space Weather,
  and the Orbital Analysis live / next-pass / orbit-position pages). The
  key/value panel was re-running a full geometry relayout
  (pack_forget + pack on every row) on each one-second refresh, which is slow
  under macOS/Aqua. It now relayouts only when the set of rows actually changes
  and otherwise updates values in place, so the text refreshes smoothly.

### Changed
- The Track screen and the Orbital Analysis next-pass page now cache the forward
  pass search and throttle the sky-plot redraw, instead of recomputing the pass
  prediction and redrawing the full plot every second. The numeric read-outs and
  countdowns still update every second.

## [0.8.1]

### Fixed
- **macOS SSL "certificate verify failed" error** when fetching GP, transponder,
  or space-weather data from a PyInstaller build. OrbitDeck now depends on
  `certifi`, builds its TLS context from certifi'''s CA bundle, sets
  `SSL_CERT_FILE` at startup, and the spec bundles the certificate data — so
  HTTPS works in the frozen app with no user action.

### Changed
- All network requests now go through a single `orbitdeck.gui.net.http_get`
  helper with a robust, verifying SSL setup.

## [0.8.0]

### Changed
- **Linear transponders now display their center (passband midpoint) frequency**
  rather than the low edge, in both the Track dropdown and the tuned RX/TX
  read-outs, so the displayed and Doppler-corrected frequencies match where you
  actually operate.
- The **Track screen shows a transponder details panel**: type (FM / Linear /
  Linear-inverting / CW-Beacon / Data), mode, passband range and bandwidth, baud
  rate, service, and the descriptive notes for the selected transponder.

## [0.7.0]

### Changed
- Screens that act on the selected satellite (Track, Next Passes, Pass Detail,
  Ground Track, Orbital Analysis, Illumination, Pass Progression, Mutual Windows,
  Workable) now show a **▸ satellite-name badge** in their header, so it's
  clear which bird the page applies to. The badge updates when the selection
  changes.
- **Sun / Moon** moved below **Workable** in the navigation.

### Fixed
- Satellite name labels no longer spill off the edges of the Home map; they flip
  side / nudge inward near the map borders and are clipped to the map area.

## [0.6.0]

### Added
- Application **icon** (globe + orbiting satellite), bundled as SVG/PNG/ICO and
  shown in the title bar and taskbar.
- **PyInstaller packaging**: `orbitdeck.spec`, a `packaging/build.py` helper,
  `packaging/BUILD.md` instructions, and a `build.yml` GitHub Actions workflow
  that builds standalone Windows/macOS/Linux bundles on tagged releases.

### Changed
- Selecting a satellite on the Home **map** (side list) or **Next Passes**
  (double-click) now makes it the app-wide selected satellite for every screen.
- Removed the "(online)" suffix from the Update GP and Space-Wx refresh buttons.

## [0.5.0]

### Added
- **Home screen (new default view)** with two tabs:
  * **Map** — a world map of every favorited satellite with its current
    sub-point and footprint, the day/night terminator, and your station. Click a
    satellite in the side list to focus just that one (with its ground track);
    click "All" to show the whole fleet.
  * **Next Passes** — the soonest upcoming pass of every favorite with a
    live AOS/LOS countdown, in the style of CardSat's schedule page.

### Changed
- App now opens on **Home** instead of Track.
- **Illumination** and **Pass Progression** scroll through time indefinitely
  (back / forward / load-more) instead of fixed time chunks.
- The Illumination eclipse-fraction readout moved out of the plot into the
  toolbar.
- **Pass Progression** moved below Illumination in the navigation.

### Fixed
- Illumination showed all-dark for some satellites (e.g. FO-29) because the
  predictor was not re-pointed at the selected satellite before sampling.
- Track transponder dropdown no longer stays highlighted after a selection.
- Space Weather now reliably populates the **Kp and A** indices: Kp is read from
  NOAA's dict feed with a products-array fallback, and A from the daily
  geomagnetic report (falling back to a Kp-derived value).

### Removed
- **Polar** screen (it duplicated the polar plot already on the Track screen).
- **World Map** screen (superseded by the Home map of all favorites).

## [0.4.0]

### Added
- Transponder database can be cached for the **whole catalog** at once via a
  bulk SatNOGS fetch (new "Update Transponders" button; GP update also pulls
  them). Cached to disk and auto-attached on startup.
- **Track screen** now has a transponder selector and shows live downlink (DN),
  Doppler-corrected receive (RX), uplink (UP), Doppler-corrected transmit (TX),
  and both downlink and uplink Doppler shifts.
- **Sun / Moon** screen redrawn as a graphical polar sky dome (rayed Sun, phase-
  shaded Moon) with an aligned data panel.
- Info page now shows the **decay-estimate range** (solar-max to solar-min
  bracket), matching CardSat.

### Changed
- Live-updating data pages now **update in place instead of rebuilding**, which
  removes the flicker/blink on every tick.
- **Orbital Analysis** uses a **tab bar** instead of radio buttons.
- **Satellite selection** dialog is now a filterable, columned table.
- **Next Passes** list streamlined: day grouping, fewer columns, high passes
  colour-coded.
- **Pass Detail** left panel uses aligned key/value columns.
- **Illumination** raster transposed: days on X, orbital period on Y.
- **Workable** grids / states / DXCC shown in aligned rows and columns.

## [0.3.0]

### Added
- **Workable US States** and **Workable DXCC** overlays, alongside Workable
  Grids, in a combined Workable screen (live now / union across next pass).
  States use multi-point interior sampling; DXCC uses per-entity reference
  points for a practical set of commonly worked entities.
- **Space Weather screen** — solar 10.7 cm flux, planetary Kp, and A index
  from NOAA SWPC, with plain-language levels, an operating outlook, and offline
  caching. Completes parity with CardSat'''s tracking/analysis surface.
- Engine helpers make_footprint_test() and footprint_radius_deg() shared by all
  workable overlays.

### Notes
- With this release the only CardSat features not in OrbitDeck are radio (CAT)
  and rotator control, which are intentionally out of scope.

## [0.2.0]

### Added
- **Workable Grids screen** — the Maidenhead squares inside the footprint,
  live or unioned across the next pass (grid chasing), computed geometrically.
- **orbitdeck.engine.analysis** module with the full CardSat analysis math:
  J2 node/perigee drift, sun-synchronous detection, LTAN, repeat ground-track,
  longest-possible-pass, beta* threshold, true anomaly / argument of latitude,
  time to perigee/apogee, and a King-Hele decay estimate.

### Changed
- **Orbital Analysis completely reworked** to match the device''s nine pages and
  presented as clean grouped key/value cards instead of a raw text dump. New
  data: footprint diameter at apogee/perigee, B* decay estimate, eclipse depth,
  dual-band Doppler, slant ranges at AOS/TCA/LOS, one-way path delay, J2 nodal
  dynamics, beta* and eclipse fraction, 7-day pass outlook with best pass, and
  true-anomaly / argument-of-latitude / perigee-apogee timing.

### Notes
- Workable US-states and DXCC overlays and the NOAA Space-Wx feed are not yet
  ported (documented in the README coverage section).

## [0.1.1]

### Fixed
- **Pass times from the bundled catalog were computed from a fixed 2024 epoch**,
  which made them wildly inaccurate when run later. Demo elements are now stamped
  to the current date, and a stale on-disk cache (older than ~3 weeks) is
  discarded in favor of fresh sample data. A yellow banner now warns whenever
  demo or stale elements are loaded, so predictions are never silently wrong.
- **Text input fields were invisible** (dark text on a same-colored field) under
  the clam theme. Added explicit ttk styling for Entry, Combobox, Radiobutton,
  Checkbutton, Scrollbar, and Separator so all controls render consistently on
  the dark theme across platforms.

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
