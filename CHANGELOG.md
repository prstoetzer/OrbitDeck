# Changelog

All notable changes to OrbitDeck are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning.

## [0.19.3]

### Added
- **Per-degree rim ticks on OSCARLOCATOR sheets.** The outer ring of every
  OSCARLOCATOR base map, combined "Map + Footprint at QTH" sheet, and path-arc
  overlay (both QTH-centred and polar) now carries fine tick marks every degree,
  with longer marks every 5° and 10°, so the rim reads like a protractor. This
  makes it easy to register stacked overlays and to measure the per-pass arc
  rotation to the degree. (The footprint transparency, whose red circle is its
  own boundary, has no outer rim and is unchanged.)

## [0.19.2]

### Changed
- **Cleaner OSCARLOCATOR combined maps.** On the "Map + Footprint at QTH" sheets
  (both the QTH-centred and polar versions) the footprint circle no longer
  repeats the azimuth degree numbers / N-E-S-W letters or the numeric elevation
  labels, since the base map underneath already shows the azimuth spokes/labels
  and elevation rings. The elevation rings themselves are still drawn inside the
  footprint — only the duplicative text is removed. The standalone footprint
  transparency in the 3-sheet set is unchanged (it keeps its full azimuth rose
  and km labels, since it prints on its own).

## [0.19.1]

### Added
- **Mutual windows across all favorites.** The Mutual Windows screen has a new
  **Satellite** selector: **Selected** (the active satellite, as before) or **All
  favorites**, which scans every favorited satellite against the DX station and
  lists all of their co-visibility windows in one chronological table with a
  **Satellite** column. Double-clicking any window opens the side-by-side
  per-station pass detail for that window's satellite (not just the selected
  one), and the whole table exports to **CSV**.
- **Az/El in the Doppler playbook.** The Radio Doppler-playbook table, its CSV
  export, and the printable PDF sheet now include the satellite's **azimuth and
  elevation** at each time step alongside the corrected RX/TX frequencies, so a
  single sheet drives both antenna pointing and tuning through the pass.
- **Edit and delete manual satellites.** The Satellites catalog now has **Edit
  manual…** and **Delete manual** buttons. You can change any field of a
  user-entered satellite (the form is pre-filled) or remove it; both update the
  live catalog and the persisted store, and deleting also clears it from
  favorites. Downloaded catalog satellites are protected — only manual entries
  can be edited or deleted.
- **Distance / azimuth / elevation on the combined OSCARLOCATOR QTH map.** The
  "Map + Footprint at QTH" sheet now carries the same readouts as the standalone
  footprint transparency: azimuth spokes and labels, **elevation rings**, and
  **dashed ground-distance rings labelled in km** out to the footprint edge, so
  you can read distance, bearing, and elevation to the sub-point directly off the
  one sheet. The elevation and distance rings now also appear on the **polar**
  version of this sheet (drawn as the correct off-centre rings around your
  station), not just the QTH-centred one.
- **Pass alarms for all favorites.** The top-bar alarm toggle (now **Favorite
  pass alarms**) watches the next pass of *every* favorited satellite, not just
  the selected one, firing AOS / TCA / LOS (and a one-minute warning) for each,
  with its own distinctive beep rhythm per event (a rising three-beep "rising
  soon", a firm double at AOS, a single chime at TCA, and a descending three-beep
  at LOS) so the events are clearly distinguishable from one another and from a
  stray system bell.

### Changed
- **"Who's up now" is now "What's up now."**
- **Consistent OSCARLOCATOR footprint style.** The footprint drawn on the
  combined QTH map now uses the same renderer as the standalone footprint
  transparency from the 3-sheet set, so the red range circle, azimuth rose and
  km distance rings look identical wherever the footprint appears.
- **Dark-theme consistency for sliders and scrollbars.** The time-in-pass and
  passband **scrub bars** were rendering with the light-grey default theme; they
  now use a dark trough with an accent handle. Scrollbar thumbs are more visible
  (with an accent hover), and the combobox drop-down popup is themed dark instead
  of flashing white.
- **Context-sensitive scrollbars.** Every table/list scrollbar now appears only
  when there is content beyond the visible area and hides itself when everything
  fits.
- **More room for long satellite names.** The catalog Name column is wider (and
  has a minimum width) so long designators like "RS-95S(QMR-KWT2)" are no longer
  squeezed against the next column.

### Fixed
- **Scrollbars on every table and list.** All scrollable surfaces now have a
  scrollbar: the pass, comparison, listing, eclipse, mutual-window, workable,
  planning, sites, celestial, and satellite tables, the Home favorites list, and
  the Select-satellite dialog (whose scrollbar was created but never shown).
- **3D Globe day/night terminator.** The night shading is now computed by testing
  each point of the visible disc against the subsolar direction directly, so it
  is correct from every viewpoint and at every time (an earlier version could
  shade the wrong region in some orientations).

## [0.19.0]

### Added
- **Listings.** A new **Listings** tab on the Exports screen provides Nova-style
  tabular ephemerides: a **One-observer** stepped position listing
  (az/el/range/range-rate/sub-point/altitude/sunlit), a compact **AOS/LOS** quick
  list (many passes at a glance), and a **Two-observer** stepped listing that
  shows both your station and a chosen secondary site from a single ephemeris.
  Step (30 s–5 min), span (2–24 h), and a visible-only filter; each sub-listing
  exports to CSV.
- **What's up now.** A new tab on the Satellites screen scans the whole catalog
  for satellites currently above your horizon, sorted by elevation, with a
  minimum-elevation floor, one-click "track this satellite", and CSV export.
- **Satellites by type.** A new **By type** tab on the Satellites screen groups
  the catalog by SatNOGS transponder kind — **Linear transponder**, **FM
  transponder**, **Digital transponder**, **Beacon / CW**, **Other**, and **No
  transponder data** — sortable by name / NORAD / period, filterable to one
  group, and CSV-exportable.
- **More data is now exportable.** Added CSV export to **Planning → Work a
  target** (shared-footprint windows), **Planning → Visible passes** (optically
  visible passes with estimated magnitude), **Workable** (grids / US states /
  DXCC under the footprint, live or next-pass), and **Orbital Analysis →
  Crossings List** (equator-crossing schedule).
- **Pass scrubber in the Radio link budget.** The Radio link-budget tab now has a
  **Time in pass** slider that evaluates the geometry anywhere from AOS to LOS
  (not just TCA), with a **TCA** snap button, plus range-rate and downlink-Doppler
  readouts. The **Doppler playbook** tab gains its own **passband-position**
  slider, so for a linear transponder the RX/TX table is built around where you
  are actually tuned rather than always the band centre.

### Fixed
- **Reversed elevation on several sky-polar plots.** Pass Detail, Track, Sun/Moon,
  Mutual Windows and the pass/mutual plots in PDF reports labelled the elevation
  rings backwards (the rim read "90", the centre "0"), so a high-elevation pass
  looked like it skimmed the horizon. The ring labels now match the radius —
  zenith reads 90 at the centre, the horizon reads 0 at the rim. (Celestial,
  Analytics and the pass card were already correct.)
- **Day/night terminator on the 3D Globe.** The night shading was built from only
  the visible points of the anti-solar circle, which shaded roughly the wrong
  hemisphere (a noon-centred globe came out half-dark). (Further corrected in
  0.19.1 to be robust from every viewpoint.)
- **OSCARLOCATOR footprint overlay instructions.** The printed footprint
  transparency told you to pin the circle at the satellite's sub-point. It now
  describes the traditional method: pin the range circle over your QTH at the map
  centre and read AOS/LOS where the path-arc overlay crosses the circle. (The
  on-screen OSCARLOCATOR Sim already worked this way.)

## [0.18.5]

### Added
- **Pass picker for the pass card.** The Exports → Pass card tab now has a **Pass**
  selector listing upcoming passes; pick any one and the card preview (and the
  saved PNG) is built for that pass, not just the next one. The card title now
  shows the pass date.
- **Satellite transmitter in the link budget.** The Radio link-budget tab now has
  separate **Your station** and **Satellite** parameter rows. The satellite's
  **TX power** and **antenna gain** (defaulting to ~1 W into a ~2 dBi simple
  monopole whip) drive the **downlink** received-power estimate — previously the
  downlink incorrectly used your ground-station transmit power. The downlink now
  also shows the satellite EIRP.

## [0.18.4]

### Added
- **Radio pass picker.** The Radio screen now has a **Plan for pass** selector
  listing the next several upcoming passes (date, max elevation, duration). Pick
  one and **both** tabs plan against it: the **link budget** is evaluated at that
  pass's **TCA** (closest approach / best-case geometry, with the pass's
  AOS/TCA/LOS shown), and the **Doppler playbook** is generated for that pass.
  Previously the link budget only used the current instant and the playbook only
  the very next pass.

## [0.18.3]

### Fixed
- The shared tab bar (Radio, Planning, Sites, Celestial, Exports) now matches the
  Orbital Analysis tabs exactly: the tab labels sit on the same subtle
  panel-coloured strip with the blue underline on the active tab. The previous
  version placed them on the plain dark background, which read as a different
  style.

## [0.18.2]

A polish release fixing reported issues on the screens added in 0.18.x and
tidying the navigation.

### Added
- **Pass card now renders on screen.** The Exports → Pass card tab shows the
  card live (sky track, Doppler curve, key facts) with **Refresh** and **Save
  pass card…** buttons, instead of being save-only.
- **Radio passband control.** On the Radio link-budget tab, a linear transponder
  now gets a **Passband position** slider to choose where in the passband to
  operate (0 % low edge / 50 % centre / 100 % high edge); the displayed
  downlink/uplink and the link budget update as you slide.
- **DXCC target** in Planning → Work a target — pick a DXCC entity from a list as
  the target, alongside grid / US state / lat,lon.
- **10 GHz (3 cm)** added to the EME band selector on the Celestial screen.

### Changed
- **Radio follows the Track screen's transponder.** The selected transponder is
  now shared, so the Radio screen's link budget and Doppler playbook reflect
  whatever you picked on Track (previously it always used the first transponder).
- **Tab styling.** The tabbed screens (Radio, Planning, Sites, Celestial,
  Exports) now use the same flat tab style as Orbital Analysis instead of the
  default light Notebook tabs that clashed with the dark theme.
- **Navigation reordered** into logical groups: live view, passes, analysis,
  operating tools, sky & space, and catalog & configuration.

### Fixed
- Removed a **stray panel-coloured mark** at the bottom of the Settings screen
  (empty status labels were using a panel background on the main background).
- Widened columns/labels to stop text truncation: the Celestial "Sagittarius A*
  (GC)" body name, and several link-budget / EME / element-trust labels.

## [0.18.1]

### Added
- **Mutual Windows pass detail.** Double-click any co-visibility window to open a
  detail view with the pass drawn on a polar sky plot **from each station's
  perspective side by side** — your station on the left, the DX station on the
  right. Each plot shows that station's full pass in grey with the
  **mutually-visible portion highlighted in orange**, plus AOS/LOS markers and
  each station's max elevation.
- The **mutual-windows PDF report** now includes the same per-window
  **dual-station comparison polar plots** (up to 12 windows), after the windows
  table, so the printed report shows the geometry, not just the times.

## [0.18.0]

A feature release adding multiple observer sites, celestial-body and EME
analysis, and a fuller two-satellite mutual-visibility tool, closing most of the
remaining gap to legacy trackers like Nova. Tracking-and-analysis only — radio
and rotator control remain out of scope.

### Added
- **Multiple observer sites.** The primary site (which still drives every other
  screen) can be **nicknamed**, and you can maintain a table of **secondary
  sites** (club station, portable spots, friends' QTHs), entered by grid or
  lat/lon and saved across sessions. A new **Sites** screen manages them and
  compares the selected satellite's upcoming passes across every site at once,
  exportable to **CSV** or a **PDF report**.
- **Celestial screen.** Live az/el of the **Sun, Moon, planets** (Mercury–
  Saturn) and bright **cosmic radio sources** (Cassiopeia A, Cygnus A, Crab,
  Virgo A, Sagittarius A\*, Orion A, Centaurus A, Fornax A) plus a **cold-sky**
  reference, on a sky polar plot and table (CSV-exportable) — for antenna
  calibration and radio astronomy.
- **EME (Earth-Moon-Earth) analysis panel.** Moon az/el and distance, total
  path loss by band (≈252 dB on 2 m, matching published figures across
  50 MHz–10 GHz), self-echo Doppler, echo delay, cold-sky temperature, and
  **common-Moon-visibility windows** with a second station (CSV-exportable).
- **Two-satellite mutual visibility** (Planning → Sat ↔ Sat) now resolves the
  other satellite by **NORAD id or name**, lists line-of-sight windows over a
  selectable 3–24 h window in a table with **start / end / duration / minimum
  range**, and exports to CSV.
- New engine module `celestial.py` (RA/Dec→az/el, planet ephemerides, radio
  sources, Moon geometry, EME path loss / Doppler / windows, sky temperature,
  satellite-to-satellite windows) with regression tests.

### Changed
- The navigation now has **22 screens** (added Celestial and Sites).
- The on-disk config persists the primary site nickname and the secondary-site
  table.

## [0.17.2]

### Changed
- **3D Globe** now shows **all favorite satellites live** — each as a coloured,
  labelled marker with its coverage footprint — instead of only the selected
  one. The selected satellite stays emphasized (ground track + brighter
  footprint), an **All favorites** checkbox toggles the rest, and at "now" the
  favorites advance in real time. (Favorites on the far side of the globe are
  hidden until they rotate into view.)
- **Sky Radar** now defaults to a new **Live (all favorites)** mode that plots
  the current sky position of every favorite above the horizon and updates in
  real time. The previous all-passes overlay and sky-coverage heatmap remain as
  the other two modes.

## [0.17.1]

### Fixed
- **Doppler playbook PDF sheet:** the intro note no longer runs off the right
  edge (it now wraps within the page margins), and the "Range-rate (km/s)"
  column header now fits on one line inside its (widened) cell instead of
  bleeding into neighbouring columns.
- **Per-pass card PNG:** the title now auto-scales its font size for long
  satellite names so it never runs past the card edges.

## [0.17.0]

A large feature release adding new visualization, analysis, and export
capabilities, plus real-time pass alarms. Tracking-and-analysis only — radio and
rotator control remain out of scope.

### Added
- **3D Globe** screen: a rotatable orthographic "view from space" with the
  satellite, ground track, footprint, day/night terminator and station, driven
  by a **simulated-time scrubber** (±180 min, play/pause, speed). Views follow
  the satellite, center on the station, or look down either pole.
- **Sky Radar** screen: the next N passes overlaid on one polar sky plot, and a
  **sky-coverage / elevation heatmap** aggregating where in your sky the
  satellite dwells (for antenna-pattern and obstruction planning).
- **Radio** screen: a **link budget** (free-space path loss, propagation delay,
  estimated received power from your station parameters) and a **Doppler tuning
  playbook** — a per-pass table of corrected RX/TX frequencies. For a linear
  transponder worked full duplex you can **hold the uplink OR the downlink
  fixed** and the other leg is round-trip corrected so you keep hearing yourself
  (the round-trip math follows CardSat v0.9.16). Export to CSV or a printable PDF
  sheet.
- **Planning** screen: **best time to work a target** (grid square, US state, or
  lat/lon) by finding windows where you and the target share the footprint;
  **visible-pass prediction** with an estimated optical magnitude and a
  twilight-darkness filter; **satellite-to-satellite** line-of-sight windows; and
  an **element-set trust** panel (epoch age, trust level, and an along-track
  drift estimate).
- **Exports** screen: pass-schedule export to **CSV, Excel (.xlsx), iCal (.ics
  with reminder alarms), and JSON**; a **multi-satellite comparison** of your
  favorites (with CSV export); and a shareable **per-pass card** PNG (sky track,
  Doppler curve, key facts, and a quality score).
- **Pass alarms**: a top-bar toggle that raises in-app **AOS / TCA / LOS**
  notifications (with an audible cue) for the selected satellite's next pass.
- New engine module `linkbudget.py` (path loss, optical magnitude, Doppler
  playbook incl. round-trip fixed-leg, sat-to-sat line of sight, element drift /
  trust, pass-quality score) and `planning.py` (best-passes-for-target,
  sky-coverage grid, horizon-mask trimming), with regression tests.

## [0.16.20]

### Fixed
- **OSCARLOCATOR Simulator: “Next pass from QTH” now shows the arc at the
  correct longitude.** It previously seeded the overlay to the next *equator
  crossing*, which is almost always a different orbit than the next *visible*
  pass over the station — so the arc was drawn at the wrong longitude and didn't
  cross over the QTH (failing for the ISS and RS-44, among others). It now finds
  the next pass that actually rises above the horizon at the station (via the
  pass predictor) and references the arc to the equator-crossing node of *that*
  pass's orbit, so the track runs across the QTH as expected.

## [0.16.19]

### Fixed
- **OSCARLOCATOR Simulator: the live arc now advances at the equator crossing
  for long-period satellites (e.g. RS-44, ~122 min period).** The live
  equator-crossing search used a fixed ±2-hour window; for a satellite whose
  period exceeds ~2 hours, the most-recent node could fall just outside that
  window, so at a crossing the code lost its node reference and the arc went
  stale (it stopped tracking the new crossing). The window now scales with the
  orbital period (~1.6 periods), and a small forward look-ahead lets a
  just-happened crossing be recognised immediately, so the arc updates to the
  current equator crossing the moment the satellite crosses, at any period.

## [0.16.18]

### Fixed
- **Footprint-overlay azimuth labels now clear the coverage circle on the polar
  sheets too.** The earlier fix used a clearance proportional to the footprint
  radius, which was too small when a low-altitude footprint is drawn on the
  large (pole-to-equator) polar sheet — the degree labels still touched the red
  circle. The clearance is now an absolute gap (scaled to the sheet), so the
  labels are comfortably outside the circle on every projection, while a large
  footprint still keeps its labels on the page.
- **Path-arc sheet: the “EQX — 0 min” box no longer overlaps the outer rim.** It
  has been made more compact (shorter wrapped wording, smaller font) and moved a
  little inboard so it sits clear of the boundary circle.

## [0.16.17]

### Changed
- **Footprint-overlay azimuth labels no longer crowd the footprint circle.** The
  degree labels (30°, 60°, …) and the N/E/S/W letters are pushed further outside
  the red coverage circle so they don't touch it, with the radius capped so that
  a large footprint (red circle near the sheet edge, e.g. a high-altitude
  satellite) keeps its labels on the page instead of running off the edge. Degree
  labels now also carry the degree symbol, matching the other sheets.

## [0.16.16]

### Changed
- **Polar OSCARLOCATOR base maps: outer labels no longer crowd the rim.** The
  longitude labels (e.g. 90°E, 120°W) are pushed further outside the boundary
  circle so they don't touch it, and the latitude-ring labels (75° … 15°) now
  sit on a quiet spoke with a small white backing so they read clearly over the
  rings instead of being cramped against the edge. The equator/rim ring is no
  longer given a redundant “0°” label (it is the map boundary, and its longitude
  labels already sit just outside it).

## [0.16.15]

### Changed
- **OSCARLOCATOR Simulator live mode: when the satellite is in the hemisphere
  opposite the viewed sheet, the view now shows the arc for the NEXT equator
  crossing into that hemisphere** (the upcoming pass), instead of the stale
  most-recent node. While the satellite is in the viewed hemisphere the arc is
  the pass in progress and the live marker rides it; while it's in the opposite
  hemisphere there is no live marker on the sheet (correct — the satellite isn't
  there yet) and the displayed arc is the next pass's track. As the satellite
  crosses the equator into view, that same arc seamlessly becomes the current
  pass. This pairs with the auto N/S hemisphere flip from 0.16.14.

## [0.16.14]

### Added
- **OSCARLOCATOR Simulator: live auto-flip across the equator.** In live mode
  with “Polar (auto N/S)” selected, the displayed sheet now follows the
  *satellite* — it shows the north sheet while the satellite is north of the
  equator and the south sheet while it's south, flipping automatically as the
  satellite crosses the equator. The path arc advances to the relevant
  equator-crossing node at the same time, so the active pass is always the one
  drawn and the live marker stays on the arc throughout the orbit (it previously
  drifted from the arc when the satellite was in the hemisphere opposite the
  shown sheet).

### Changed
- **OSCARLOCATOR printout labelling is less crowded.** The map disc is slightly
  smaller so the outer azimuth/longitude labels clear the page edge; the
  QTH-map cardinals no longer print a degree number on top of the N/E/S/W letter
  (e.g. “270°” over “W”); polar longitude labels sit clear of the rim; and the
  footprint-overlay distance rings use wider spacing (2–3 rings instead of a
  dense stack) with their km labels moved to a clear spoke away from the azimuth
  rose.
- The elevation-ring labels on the QTH map now read consistently as “0° el / 10°
  el / 30° el / 60° el”, aligned along a single radial, with “0° el” replacing
  the earlier “horizon” wording.

### Removed
- The “N SHEET / S SHEET” corner badges on the polar map sheets (the hemisphere
  is already obvious from the map content and title). The north/south
  distinction is now stated only where it has to be acted on: at the EQX
  indicator on the path-arc sheet, which names the node (“Ascending node
  (northern sheet)” / “Descending node (southern sheet)”).

## [0.16.13]

### Added
- **Elevation rings on the QTH-centred OSCARLOCATOR base map.** The range rings
  are now elevation contours for the selected satellite (horizon / 10° / 30° /
  60°), so an operator reads the satellite's elevation directly off the sheet
  (“the track crosses the 10° ring → 10° elevation”). The horizon ring is the
  satellite's footprint edge. Ring labels are staggered so they stay legible for
  both low (small-footprint) and higher orbits, and a faint dashed distance ring
  keeps a physical-scale (km) reference. The QTH base map is now titled with the
  satellite name and its subtitle states the altitude the rings assume. New
  geometry helpers `elevation_for_central_angle_deg` and
  `central_angle_for_elevation_deg` back this.
- **N/S sheet badge on the polar sheets.** Northern sheets carry a blue
  “N SHEET” badge and southern sheets a red “S SHEET” badge, so the two
  hemispheres' transparencies can't be mixed up.
- **Cardinal registration ticks** on every base-map and arc sheet (at N/E/S/W on
  the QTH map and at 0/90/180/270° on the polar maps), giving fixed rim marks to
  align stacked transparencies by eye.

## [0.16.12]

### Fixed
- **OSCARLOCATOR Simulator live mode now tracks correctly across both
  hemispheres.** In live mode the equator-crossing reference is now chosen to
  match the on-screen view (the north sheet references the ascending node, the
  south sheet the descending node) instead of being keyed to the station's own
  hemisphere. Previously a northern station viewing the south sheet (or vice
  versa) pinned the path arc to the wrong node, so the live satellite marker was
  offset from the drawn arc by ~15–20° until the QTH was moved to the matching
  hemisphere. A pass can now be followed accurately on either sheet from any
  station.
- **Path-arc overlay subtitle no longer collides with the rotate annotation.**
  The subtitle is more compact and keeps value+unit groups (“92.9 min”, “23.6° W”)
  together, so it stays on one line for typical satellites; the red “rotate
  sheet …” label was also given more vertical clearance.

### Changed
- **The “Make printable OSCARLOCATOR” action on the Simulator screen now behaves
  exactly like the one on the Track screen.** Both prompt for the base-map style
  (polar/generic vs. QTH-centred) and whether to draw the footprint directly on
  the QTH map, use a descriptive filename, and show tailored print instructions.
  The workflow is now defined once and shared by both screens.

## [0.16.11]

### Fixed
- OSCARLOCATOR footprint subtitle now breaks at a natural point: value+unit
  groups (e.g. “2240 km”, “416 km”, “(~2240 km)”) use non-breaking spaces so the
  line wrapper keeps them intact instead of splitting them across lines.

## [0.16.10]

### Fixed
- OSCARLOCATOR PDF text no longer spills off the page. Titles, subtitles and
  footer notes are kept inside proper page margins: long subtitles and footers
  wrap to the margin (previously they ran edge-to-edge, since matplotlib only
  wraps at the figure boundary), and a long satellite name in a page title is
  measured and auto-shrunk to fit instead of overrunning the edges.

## [0.16.9]

### Fixed
- **Simulator live mode now tracks in real time.** The OSCARLOCATOR Sim screen
  opts into the per-second tick, so in live mode the satellite position and
  footprint update continuously instead of only when you (re)select the mode.
- **All OSCARLOCATOR PDF titles are spelled “OSCARLOCATOR”** (some pages read
  “OSCARLATOR”). When the base map has the satellite footprint printed on it, the
  title now includes the **satellite name** and the subtitle gives the **footprint
  size** (radius in degrees and km at mean altitude).
- **Report table zebra striping is aligned with the rows.** The shaded band sat
  offset above the text; it now lines up squarely behind each row.

## [0.16.8]

### Fixed
- The minute dots on the OSCARLOCATOR simulator pass arc are drawn once each and
  now have a crisp edge so they stay defined against the track line. The
  simulator map also renders at a higher DPI (150), so dots, lines and labels
  stay sharp when the window is enlarged instead of softening from up-scaling a
  fixed-size bitmap.

## [0.16.7]

### Fixed
- The minute-number labels on the OSCARLOCATOR simulator pass arc no longer look
  blurry. They were being drawn several times on top of themselves (the densely
  sampled track put multiple points near each 10-minute mark); each label is now
  drawn exactly once, with a subtle background so it reads clearly over the track
  and coastlines.

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
