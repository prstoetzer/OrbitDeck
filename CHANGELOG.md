# Changelog

All notable changes to OrbitDeck are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning.

## [0.16.6]

### Added
- A detailed user manual (docs/MANUAL.md) documenting every screen in menu order,
  the printable and interactive OSCARLOCATOR system, the report exports, data
  sources, and troubleshooting.

### Changed
- README features table reordered to match the navigation-menu order exactly and
  updated to include the OSCARLOCATOR Sim screen and corrected screen details;
  added a link to the new manual.

## [0.16.5]

### Added
- The OSCARLOCATOR Sim page now shows a compact “next equator crossings” listing
  (time and longitude) for the next few nodes — ascending nodes for northern
  stations, descending nodes for southern — so the simulator can be used without
  opening the separate EQX page. Clicking a row drives the overlay to that EQX.

## [0.16.4]

### Fixed
- **Pass-arc accuracy.** The OSCARLOCATOR path arc now follows the real SGP4
  ground track much more closely:
  * Fixed a retrograde-orbit bug (inclination > 90°, e.g. sun-synchronous
    satellites) where the longitude drift had the wrong sign — the arc could be
    off by up to ~180°. The inclination formula now handles retrograde natively.
  * Eccentricity is now modelled via Kepler’s equation (the satellite sweeps the
    orbit non-uniformly) instead of assuming a circular orbit, cutting along-track
    longitude error on eccentric orbits from tens of degrees to a few.
  Verified against SGP4: latitude within ~1° and longitude within ~5° over a full
  orbit for circular, eccentric, prograde and retrograde orbits in the sample
  catalogue. The simulator now reuses this same corrected track, so its arc and
  the printout match exactly.

## [0.16.3]

### Changed
- The QTH range reticle (both the simulator and the printable OSCARLOCATOR) is
  now sized to the satellite footprint radius at its MEAN orbital altitude — the
  maximum ground distance at which the satellite is ever visible — instead of the
  instantaneous sub-point altitude, so the reticle is a fixed, meaningful
  coverage circle.

## [0.16.2]

### Changed
- In the simulator’s live view the satellite’s actual coverage footprint is now
  drawn (green dashed) at its current sub-point, alongside the QTH-centred range
  reticle (orange), so you can see at a glance whether the satellite is within
  range of your station right now.

## [0.16.1]

### Changed
- **OSCARLOCATOR simulator fixes.**
  * The footprint circle is now always centred on the QTH (the OSCARLOCATOR range
    reticle is a fixed station-centred overlay), instead of following the
    satellite sub-point.
  * In manual / next-pass mode the “minutes after EQX” slider now moves the
    satellite marker along the drawn pass-arc line; in live mode the marker
    follows the true current sub-point.
  * Coastlines use cartopy / Natural Earth geometry when cartopy is installed
    (much higher resolution), falling back to the bundled outline otherwise.
- **Printable OSCARLOCATOR path-arc ticks** are now consistent straight marks
  drawn perpendicular across the track, with the minute numbers offset clear of
  the arc so they no longer change shape or collide with the labels.

## [0.16.0]

### Added
- **Interactive OSCARLOCATOR simulator** (new “OSCARLOCATOR Sim” screen). Play
  with a virtual OSCARLOCATOR on-screen without printing transparencies: a polar
  (auto N/S, or forced N/S) or QTH-centred azimuthal-equidistant base map with a
  rotatable orbit path-arc overlay, minute ticks, the satellite’s position
  marker and its footprint. Drive it live (current position), manually (EQX-
  longitude and minutes-after-EQX sliders), or seed it to the next pass from your
  station. A button exports the matching printable OSCARLOCATOR PDF. Projection
  conventions match the printed sheet exactly.

### Fixed
- The path-arc overlay’s “EQX (0 min) — line up on map” label no longer covers
  any part of the pass arc: it is placed on the side opposite the track (left for
  the northern sheet, right for the southern sheet).

## [0.15.0]

### Fixed
- **Polar base maps are no longer mirrored.** The north-polar map now uses the
  conventional ARRL OSCAR Locator orientation (0° longitude at the bottom, 90°E
  on the right, east increasing counter-clockwise); the south-polar map is the
  correct mirror (90°E on the left). Previously the continents were left-right
  reversed. The handedness is now set by the axes orientation, so the path-arc
  overlay registers correctly on both hemispheres.
- **QTH map no longer over-shows the opposite hemisphere.** Its azimuthal-
  equidistant radius is capped (~|lat|+25°, clamped 50–80°) instead of a full
  90° hemisphere, so the equator / EQX longitude line is placeable without the
  distorted far-side wrap around the rim.

### Changed
- **Path-arc overlay improvements.** Minute marks are now bold radial tick dashes
  (larger every 10 min) for easy reading. A prominent “EQX (0 min) — line up on
  map” arrow marks the equator-crossing radial so it’s clear where to align the
  overlay on the base map. The track is referenced to the ascending node for
  northern sheets and the descending node for southern sheets, with minute 0 on
  the equator in both cases.

## [0.14.3]

### Changed
- Verified compliance with the CelesTrak GP data-format documentation and
  hardened HTTP handling: `net.http_get` now reports HTTP 403 (rate-limit /
  firewall), 404 (bad query) and 3xx (redirect) with clear, actionable messages
  so failures are obvious and processes don’t blindly retry. OrbitDeck already
  queries the canonical `.org` domain with `FORMAT=json`, fetches only on
  explicit user action (never auto-polls), caches to disk, and parses the full
  set of CCSDS OMM keywords — including 6- and 9-digit catalog numbers and
  null OBJECT_NAME/OBJECT_ID for analyst objects — which the legacy TLE format
  cannot represent.

## [0.14.2]

### Fixed
- Sky-track polar plots: properly inset each plot within its grid cell so the
  cardinal theta-labels (N at top, S at bottom, and the diagonals) all have
  clear space and no longer collide with the per-pass caption. The circle is
  kept round and the caption sits in a reserved strip below the S label.

## [0.14.1]

### Fixed
- Sky-track polar plots: the “N” compass label no longer collides with the
  per-pass caption. Each caption now sits below its plot, with headroom above
  the circle for the cardinal label (both in the standalone sky-track report and
  the comprehensive report’s embedded grid).

## [0.14.0]

### Added
- **Pass sky-track report.** A “Print sky tracks (3 days)…” button on the Next
  Passes screen prints a grid of polar az/el sky-track plots — one per pass over
  the next three days — matching the on-screen Pass Detail view (N-up, zenith at
  centre, green AOS / orange LOS markers), labelled with time, max elevation,
  direction and duration.
- **Comprehensive report now includes graphics.** The per-satellite report
  (“Report…” button) now appends the 3-day sky-track grid, the 60-day
  illumination raster, and the 30-day pass-progression timeline after the
  orbital-analysis, passes and EQX text sections.

### Fixed
- The favorites pass-schedule report’s last column (Duration) no longer runs past
  the right margin; the columns are re-spaced and the numeric columns right-
  aligned.

## [0.13.1]

### Changed
- **Illumination and progression reports now mirror their on-screen displays.**
  * The illumination report uses the same 2D raster as the screen — day on the
    X axis, minutes into one orbit on the Y axis, bright = sunlit / dark =
    eclipse (cividis) — so the drifting eclipse band and full-sun seasons read
    the same on paper, with an added per-day eclipse-fraction strip.
  * The pass-progression report now draws one row per UTC day with passes as
    time-of-day bars coloured by max elevation (green ≥ 45°, blue 20–45°,
    dark-blue < 20°), matching the in-app stacked timeline; paginated, with the
    full pass table following.
- **Favorites pass report is now a single time-ordered list.** All favorites’
  passes are merged and sorted by AOS into one chronological table (with a
  Satellite column), instead of being grouped per satellite.

## [0.13.0]

### Added
- **Configurable minimum elevation.** Settings now has a free-entry minimum-
  elevation field (any value 0–89°), replacing the fixed presets as the source
  of truth. It persists in the config and applies everywhere — the Next Passes
  table, the Multi-Day Progression, and every report. The Next Passes screen shows
  the active value (including custom ones) alongside its quick-set buttons.
- **Favorites pass-schedule report.** A button on the Home “next passes” tab
  prints a 7-day pass schedule for every favorite satellite (per-satellite tables,
  using your station and minimum elevation).
- **Mutual-windows report.** A “Print mutual…” button on the Mutual Windows
  screen prints the co-visibility windows with the DX station.
- **Illumination report (60 days).** A “Print 60-day…” button on the
  Illumination screen prints a per-orbit sunlit-fraction chart with the mean
  eclipse fraction.
- **Pass-progression report (30 days).** A “Print 30-day…” button on the
  Multi-Day Pass Progression screen prints a time-of-day-vs-day scatter coloured
  by max elevation, plus a full table of every pass.

## [0.12.0]

### Added
- **Footprint-on-QTH option for the OSCARLOCATOR export.** A new choice draws the
  satellite footprint directly on the base map at your station, producing a
  2-page set (map+footprint, then the path-arc overlay) instead of three separate
  sheets. Works for both the QTH-centred and the polar maps; on the polar map the
  footprint is correctly drawn as the off-centre great-circle locus around the
  QTH. The standard 3-sheet output remains the default.
- **Printable satellite reports.** A new “Report…” button on every
  satellite-specific screen generates a clean, multi-section PDF covering the
  orbital analysis, the next passes from your station, and the equator-crossing
  schedule (ascending or descending node by hemisphere). New module
  `orbitdeck.gui.reports`.

### Changed
- **Bolder, larger OSCARLOCATOR sheets.** Thicker lines for the map graticule,
  rings, spokes, coastlines, ground track and footprint, plus larger, bolder
  labels and a bigger centre cross, so the printed sheets read clearly —
  especially through stacked transparencies. Tunable via style constants at the
  top of `oscarlocator.py`.

## [0.11.2]

### Changed
- **Footprint overlay now inks only the actual footprint.** Removed the distance
  rings that extended out to the sheet edge (~10,000 km) and the full-sheet
  boundary circle, so the area outside the coverage circle is clear and the base
  map shows through two stacked transparencies. The sheet keeps the same angular
  scale as the base map (so it still registers) and shows, within the footprint:
  the red coverage circle, an azimuth rose (N/E/S/W with 30° spokes/labels), and
  a few distance rings sized to the footprint (500/1000/2000 km steps).

## [0.11.1]

### Changed
- **Cleaner satellite path/overhead sheet.** Removed the “NEXT EQX” arrow and
  the small advance-diagram inset that overlapped the plot. The per-pass move is
  now shown by an uncluttered curved arrow in the top margin, outside the plot
  circle, with a label stating the angle, the on-sheet turn direction
  (clockwise / counter-clockwise), and that the node moves west — e.g.
  “rotate sheet 23.6° counter-clockwise (node moves west) each pass”. The
  on-screen sense is computed correctly for both the northern and the
  (longitude-mirrored) southern sheets.

## [0.11.0]

### Added
- **Southern-hemisphere OSCARLATOR support.** A new South-pole-centred polar base
  map (mirrored longitude so it reads correctly from the southern side) for
  stations below the equator, with Southern-hemisphere coastlines. The Track
  screen’s polar option now auto-selects north or south from your station
  latitude (“polar-auto”).
- **Descending-node equator crossings.** New `Predictor.descending_nodes()`;
  the Orbital Analysis “Equ. Crossings” chart and “Crossings List” table now
  show *descending*-node EQX events for southern stations and *ascending*-node
  for northern stations (auto-selected), since southern OSCARLATOR sheets key off
  the descending node.
- **Overheads closer to the classic PE1RAH design:** the orbit overhead now draws
  a “NEXT EQX” direction marker at the node, and the footprint overlay gains an
  azimuth compass rose (cardinals + 30° bearing labels) over the distance rings.

## [0.10.2]

### Added
- **Polar base-map option for the OSCARLOCATOR export.** In addition to the
  QTH-centred azimuthal map, you can now generate a generic **North-pole-centred
  polar great-circle map** in the classic PE1RAH OSCARLATOR style — latitude
  rings, longitude spokes, and the satellite drawn as an “overhead” orbit trace.
  Because it is pole-centred, the same sheet works for any station via the
  equator-crossing (EQX) list. The Track screen now asks which style to produce.
  The QTH-centred map remains the default, so existing behaviour is unchanged
  (the polar map is purely additive / revertable).

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
