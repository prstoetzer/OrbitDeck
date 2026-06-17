# OrbitDeck — User Manual

OrbitDeck is a cross-platform desktop application for **satellite tracking and
orbital analysis**, aimed at amateur-radio operators working the FM, linear, and
digital birds. It is a desktop port of the analysis tools from the CardSat
hardware tracker, with a roomy windowed interface and embedded plots.

Radio (CAT) and rotator control are intentionally **out of scope** — OrbitDeck
tells you where a satellite is, when it will be in range, how to point, and what
Doppler to expect, but it does not key your radio or turn your rotator.

This manual documents every screen in the order it appears in the navigation
menu, plus the printable OSCARLOCATOR system, the report exports, and the data
sources.

---

## Contents

1. [Getting started](#1-getting-started)
2. [The application window](#2-the-application-window)
3. [The navigation menu (in order)](#3-the-navigation-menu-in-order)
   - [1. Home](#31-home)
   - [2. Track](#32-track)
   - [3. 3D Globe](#33-3d-globe)
   - [4. Sky Radar](#34-sky-radar)
   - [5. Next Passes](#35-next-passes)
   - [6. Pass Detail](#36-pass-detail)
   - [7. Ground Track](#37-ground-track)
   - [8. Orbital Analysis](#38-orbital-analysis)
   - [9. Radio](#39-radio)
   - [10. Planning](#310-planning)
   - [11. Illumination](#311-illumination)
   - [12. Pass Progression](#312-pass-progression)
   - [13. Mutual Windows](#313-mutual-windows)
   - [14. Workable](#314-workable)
   - [15. OSCARLOCATOR Sim](#315-oscarlocator-sim)
   - [16. Exports](#316-exports)
   - [17. Sun / Moon](#317-sun--moon)
   - [18. Celestial](#318-celestial)
   - [19. Space Wx](#319-space-wx)
   - [20. Satellites](#320-satellites)
   - [21. Sites](#321-sites)
   - [22. Settings](#322-settings)
4. [The OSCARLOCATOR system](#4-the-oscarlocator-system)
5. [Reports (printable PDFs)](#5-reports-printable-pdfs)
6. [Data sources & staying accurate](#6-data-sources--staying-accurate)
7. [Files & where settings live](#7-files--where-settings-live)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Getting started

Install and launch:

```bash
pip install -e .
orbitdeck
```

Or run without installing:

```bash
pip install -r requirements.txt
python run.py
```

On first launch OrbitDeck loads a small **bundled demo catalog** (ISS, SO-50,
AO-91, CAS-4B, RS-44) so every screen works immediately, even offline.

> **Important — demo pass times are not real.** The bundled elements are stamped
> to today's date so the geometry looks sensible, but their orbital *phase* is
> synthetic. They will **not** tell you when a satellite is actually overhead. A
> yellow banner appears whenever demo or stale data is loaded. Click **Update
> GP** in the top bar to download live elements, then your pass times are real.

Because SGP4 is only trustworthy within roughly **one to two weeks** of an
element set's epoch, refresh your elements periodically.

**First-run checklist**

1. Open **Settings** (last menu item) and set your **observer site** — latitude,
   longitude, and altitude, or a Maidenhead grid square.
2. Click **Update GP** in the top bar to pull a live catalog.
3. Open **Satellites**, select the birds you care about, and press **space** to
   favorite them (★). Favorites drive the Home map and the favorites schedule.
4. Optionally, on **Satellites**, fetch transponder data for a selected bird so
   the Track screen can show Doppler-corrected frequencies.

---

## 2. The application window

The window has three parts:

- **Top bar** — application-wide actions, including **Update GP** (download a
  fresh element set from your configured source) and **Update Transponders**
  (refresh the SatNOGS transponder database). A **Favorite pass alarms** toggle
  raises in-app **AOS / TCA / LOS** notifications — plus a one-minute "rising
  soon" warning — for the next pass of **every favorited satellite**, so you
  don't miss a rising bird while working in another screen or watching a
  different satellite. Each event has its own **distinctive beep rhythm** (a
  rising three-beep warning, a firm double at AOS, a single chime at TCA, and a
  descending three-beep at LOS) so you can tell them apart by ear. A **yellow
  banner** appears here when the loaded catalog is
  demo or stale data; it also carries an Update GP button.
- **Navigation menu** (left) — the 22 screens, described below in order.
- **Content area** (right) — the active screen.

Most screens act on the **currently selected satellite**, shown in a header
badge. Change the selection on the **Satellites** screen (or by clicking a
favorite on the Home map). Each satellite-specific screen also carries a
**Report…** button (see [Reports](#5-reports-printable-pdfs)).

Times are shown in **UTC** throughout, the convention for satellite operating.

---

## 3. The navigation menu (in order)

### 3.1 Home

The default screen. Two tabs:

- **Map** — a world map showing **every favorited satellite** with its current
  footprint, the day/night terminator, and your station. Click a satellite in
  the side list to focus it and draw its ground track.
- **Passes** — the **next pass of every favorite**, each with a live countdown,
  as a schedule. A button prints a **7-day schedule for all favorites** as a PDF.

Home is the at-a-glance "what can I work soon" view.

### 3.2 Track

The live operating screen for the selected satellite. It shows:

- **Look angles** — azimuth, elevation, slant range, and range-rate, updated
  live.
- **Sub-point and altitude** — where the satellite is over the Earth.
- **Transponder selector** — pick a transponder (FM, linear, beacon, or data);
  details include the passband and baud rate.
- **Doppler-corrected frequencies** — live downlink (DN) and your corrected
  receive (RX), plus uplink (UP) and corrected transmit (TX). For linear
  transponders the correction uses the passband **center**.
- **Sunlit / eclipse** status and the next **AOS / LOS** times.
- A **live sky polar plot** of the current pass.

You can **add a manual transponder** if the database lacks one, and **export a
printable OSCARLOCATOR PDF** for the selected satellite from here (see
[The OSCARLOCATOR system](#4-the-oscarlocator-system)).

### 3.3 3D Globe

A rotatable **orthographic "view from space"** of the Earth showing **all your
favorite satellites at once, live** — each as a coloured dot with its coverage
footprint and a name label — over the day/night terminator and your station. The
**selected** satellite is emphasized (it carries its ground track and a brighter
footprint), and the chosen **View** follows it.

- **View** (radio buttons): **follow the satellite** (it stays centred),
  **over your station**, or look straight down the **north** or **south** pole.
- **All favorites** (checkbox): show every favorite live, or untick to show only
  the selected satellite.
- **Time scrubber** — a slider spanning **±180 minutes** flies the whole scene
  forward or backward in time, so you can watch a pass develop or rewind one.
  **Play** animates it; the **speed** control sets how fast (10× to 1800×). Click
  **Now** to snap back to the present. At "now", the favorites advance in **real
  time**.

A favorite on the far side of the globe (over the horizon from the current
viewpoint) is hidden until it rotates into view. The orange star is your station.

### 3.4 Sky Radar

A polar sky plot (N-up, zenith at centre, rim = horizon) with three modes chosen
by the radio buttons:

- **Live (all favorites)** *(default)* — the **current sky position** of every
  favorite satellite that is **above your horizon right now**, each a coloured
  labelled dot, updating in **real time** as they move. This is the "what can I
  hear right now" view.
- **All-passes radar** — the upcoming passes of the **selected** satellite
  overlaid on one plot (each arc one pass, colour-coded by order, with a dot at
  AOS), over a selectable window (6–48 h). Good for "what is my sky doing in the
  next few hours."
- **Sky-coverage heatmap** — the selected satellite's upcoming passes aggregated
  into an azimuth × elevation density map: brighter cells are where it spends
  more time in your sky. Useful for planning antenna patterns or spotting where a
  treeline or building will block passes.

### 3.5 Next Passes

A table of upcoming passes for the selected satellite over the next 7 days. A
**minimum-elevation** control filters out passes too low to be useful (presets
plus whatever you set in Settings). **Double-click** a pass to open it in Pass
Detail. A button prints a **3-day grid of polar sky tracks** as a PDF.

### 3.6 Pass Detail

A detailed look at one chosen pass: a **polar sky-track** (the path across your
sky, N-up, zenith at center) alongside an **elevation-versus-time** profile.
Reached by double-clicking a pass on Next Passes.

### 3.7 Ground Track

The selected satellite's **forward ground track** over the next **1, 3, 5, or 8
orbits** (selectable with the radio buttons), drawn on the world map so you can
see where it will pass.

### 3.8 Orbital Analysis

Eleven pages of detailed analysis for the selected satellite, navigated with the
page control. Data pages are clean grouped key/value cards; graph pages embed a
plot.

1. **Info** — size/shape, footprint diameter now / at apogee / at perigee, the
   B\* drag-decay lifetime estimate, and element-set age.
2. **Live** — current look angles, dual-band Doppler, and eclipse depth.
3. **Next Pass** — slant ranges at AOS / TCA / LOS and one-way path delay.
4. **Ground Track** — the ground track plotted over upcoming orbits.
5. **Doppler** — the Doppler curve for a selectable downlink (from the
   transponder database); shows peak shift and maximum range-rate.
6. **Nodal** — J2 node and perigee drift rates, sun-synchronous flag, local time
   of ascending node (LTAN), repeat-ground-track period, and the longest
   geometrically possible pass.
7. **Sun/Beta** — beta angle now, the beta\* eclipse threshold, eclipse fraction,
   and a 60-day beta plot.
8. **Pass Outlook** — a 7-day planning summary with the best upcoming pass.
9. **Orbit Position** — mean and true anomaly, argument of latitude, and time to
   perigee / apogee.
10. **Equ. Crossings** — ascending-node times and longitudes for the next 7
    days, charted in the style used to set an OSCARLOCATOR.
11. **Crossings List** — the same equator crossings as a date/time/longitude
    table, with an **Export crossings CSV** button.

### 3.9 Radio

Radio-planning analysis for the selected satellite, in two tabs. (OrbitDeck does
**not** control a radio — these are calculators that *inform* operating.)

A **Plan for pass** selector at the top lists the next several upcoming passes
(with date, max elevation, and duration); pick one and **both** tabs plan against
it. **Refresh passes** re-scans. With a pass chosen, the link budget defaults to
that pass's **TCA** (closest approach — the best-case geometry), and the Doppler
playbook is generated for that pass's AOS→LOS span.

- **Link budget** — for the chosen geometry: the **slant range**, one-way
  **propagation delay**, **range rate**, **free-space path loss** on the downlink
  (and uplink), an **estimated received power**, and the **downlink Doppler** at
  that instant. You enter two sets of parameters: **Your station** (TX power,
  TX/RX antenna gains, line loss) drives the uplink and your receive side, and the
  **Satellite** (its TX power and antenna gain — defaulting to ~1 W into a ~2 dBi
  *simple monopole whip*) drives the downlink received power, since on the
  downlink the spacecraft is the transmitter. The figures use the **transponder
  you selected on the Track screen** (the two screens stay in sync). For a
  **linear transponder**, a **Passband position** slider lets you choose where in
  the passband you want to operate (0 % = low edge, 50 % = centre, 100 % = high
  edge). A **Time in pass** slider scrubs the geometry from **AOS to LOS** so you
  can watch range, path loss and Doppler change through the pass; the **TCA**
  button snaps back to closest approach. It's an estimate for "is this pass
  workable," not a calibrated measurement — override the inputs to match your
  station and the bird.
- **Doppler playbook** — a per-pass table of the **corrected RX and TX
  frequencies** at a chosen interval (30/60/120 s), with the satellite's
  **azimuth and elevation** at each step, for tuning (and pointing) by hand
  without a computer in the loop. For an **FM bird** each leg is corrected
  independently.
  For a **linear transponder worked full duplex**, choose which leg to **hold
  fixed** — **Fixed downlink** (you park your receiver and the table tells you
  where to set the uplink) or **Fixed uplink** (you park your transmitter and it
  tells you where you'll hear yourself). The non-fixed leg is **round-trip
  corrected** so you stay on your own signal as the satellite moves. A
  **Passband position** slider builds the table around where you are actually
  tuned in a linear bird's passband, rather than always the band centre. Export
  the table to **CSV** or a **printable PDF sheet**.

### 3.10 Planning

Goal-directed planning and element-status, in four tabs:

- **Work a target** — pick a target as a **grid square**, a **US state**, a
  **DXCC entity** (chosen from a list), or **lat,lon**, and OrbitDeck finds the
  upcoming windows (next 72 h) when **both you and the target are inside the
  satellite's footprint** at once — i.e. a contact through the bird is
  geometrically possible. Windows are ranked by start time, with a
  footprint-margin figure (bigger = both stations nearer the centre
  of coverage). Export the windows to **CSV**.
- **Visible passes** — the next 5 days of **optically observable** passes: the
  satellite sunlit while you are in darkness and it is high enough to see. Choose
  the darkness threshold (**civil / nautical / astronomical** twilight) and a
  **standard magnitude** for the satellite; each pass shows an **estimated
  brightness**. Magnitudes are estimates — real satellites flare and tumble.
  Export the list to **CSV**.
- **Sat ↔ Sat** — enter a second satellite by **NORAD id or name** and choose a
  window (3–24 h); OrbitDeck lists the **line-of-sight windows** between the two
  satellites in a table with each window's **start, end, duration, and minimum
  range** (the closest the two spacecraft come during that window). A clear line
  of sight means the chord between them does not pass through the Earth. Export
  the windows to **CSV**. This is two-satellite **mutual visibility** — useful
  for inter-satellite link and crosslink planning.
- **Element trust** — the selected satellite's element-set **epoch age**, a
  coarse **trust level**, and an **along-track drift estimate**, with guidance on
  when to refresh. Quantifies the stale-data warning.

### 3.11 Illumination

Two tabs for the selected satellite's illumination.

- **Illumination raster** — a **sunlit-versus-eclipse raster** showing a 30-day
  window you can **scroll** forward and back through time (buttons or mouse
  wheel). Day runs along one axis and minutes-into-orbit along the other; bright
  is sunlit, dark is eclipse. A **Print 60-day** button exports the full summary,
  which reports the mean eclipse fraction — useful for power-budget reasoning.
- **Eclipse table** — a tabular **umbral-eclipse ephemeris** over a selectable
  span (1–14 days), in two sub-tabs. **Every orbit** lists each eclipse's
  **enter / exit / duration**, the **interval** of sunlight between successive
  eclipses, and the **sun angle** (the orbit-plane beta angle). **Daily summary**
  rolls each UTC day up into the **number of eclipses**, **total** eclipse time,
  the **longest** single eclipse, the **percent of the day** spent in shadow, and
  the day's sun angle. High beta angles mean shallow, short eclipses — or none at
  all in continuous sunlight. Both views export to **CSV**, and **Print report**
  produces a formatted PDF. This is the data you need for spacecraft
  power-budget planning.

### 3.12 Pass Progression

The selected satellite's passes across **10 or more days**, drawn as a scrollable
stack of **24-hour timelines** — one row per day. Each pass sits at its time of
day, its width is its duration, and its shade encodes max elevation. This is the
"how does my pass time drift day to day" view.

### 3.13 Mutual Windows

**Co-visibility** windows — the times when both you and a **DX station** can see
the same satellite simultaneously (the requirement for a direct satellite QSO).
Enter the DX station as a Maidenhead grid or as `lat,lon`. The **Satellite**
selector chooses the scope: **Selected** computes windows for the active
satellite, or **All favorites** scans every favorited satellite against the DX
station and lists all their windows together in one chronological table, each
tagged with its satellite. **Export CSV** saves the table, and a button prints
the mutual-windows report.

**Double-click any window** to open a detail view showing the pass on a polar
sky plot **from each station's perspective side by side** — your station on the
left, the DX station on the right. (In All-favorites mode the detail is built for
that window's own satellite.) Each plot draws that station's full pass in grey
with the **mutually-visible portion highlighted in bold orange**, and marks AOS
(circle) and LOS (square). This makes it easy to see when in the pass the
satellite is workable from both ends and how high it sits in each sky.

### 3.14 Workable

What is **inside the satellite's footprint** — useful for grid-square, US-state,
and DXCC chasing. Choose the category with the radio buttons:

- **Grids** — Maidenhead grid squares.
- **US States** — states currently reachable.
- **DXCC** — DXCC entities currently reachable.

And choose the time mode:

- **Live** — what is under the footprint right now (refreshes every few seconds).
- **Pass** — the union of everything reachable across the next pass.

**Export CSV** saves the current list (grids, states, or DXCC entities) for the
chosen category and time mode.

### 3.15 OSCARLOCATOR Sim

An **interactive on-screen OSCARLOCATOR** — play with the classic transparency
tool without printing anything. The display is a polar (or QTH-centered)
azimuthal-equidistant base map with a **rotatable orbit path-arc overlay**, the
satellite's position marker, and the footprint.

**Drive modes** (radio buttons):

- **Live** — the overlay follows the satellite's real current position; the
  satellite's actual coverage footprint (green dashed) is drawn at its sub-point
  alongside the fixed QTH range reticle (orange).
- **Manual** — set the **EQX longitude** and **minutes-after-EQX** with the
  sliders; the marker slides along the drawn arc. This is exactly how you use a
  physical OSCARLOCATOR: line the node up on the equator-crossing longitude, then
  read along the track.
- **Next pass** — seeds the overlay to the node of the next pass from your
  station.

**Base map** (radio buttons): polar auto (picks N or S from your latitude), polar
north, polar south, or QTH-centered.

A compact **"next equator crossings"** list is built into the page — the next few
node times and longitudes (ascending nodes for northern stations, descending for
southern). Click a row to drive the overlay straight to that crossing. There is
also a **"Make printable OSCARLOCATOR…"** button to export the matching PDF.

The QTH range reticle is sized to the satellite's footprint radius at its **mean
orbital altitude** — i.e. the **maximum ground distance** at which the satellite
is ever visible. When the path arc touches or crosses that circle, the satellite
is above your horizon (within the natural tolerances of an overlay system).

### 3.16 Exports

Data export and sharing, in four tabs:

- **Pass schedule** — the next 1/3/7 days of passes for the selected satellite,
  exportable to **CSV**, **Excel (.xlsx)**, **iCal (.ics)**, or **JSON**. The
  iCal events carry a **10-minute reminder alarm**, so passes show up in your
  calendar app with a heads-up. (Excel export needs the optional `openpyxl`
  package; CSV needs nothing extra.)
- **Compare favorites** — a side-by-side table of your favorited satellites over
  a 1/3/7-day window: how many passes each has and its single best pass (time,
  max elevation, duration). Exportable to CSV. If you have no favorites, the
  first few catalog satellites are used.
- **Pass card** — a shareable single-image summary of a pass: the sky-track
  polar plot, the Doppler curve, and the key facts (AOS/TCA/LOS, duration,
  azimuth sweep, and a 0–100 quality score). Pick **which upcoming pass** from
  the selector; the card is **rendered right on the screen** so you can preview
  it. **Save pass card…** exports it as a PNG and **Refresh passes** re-scans.
  Good for dropping into a club chat or attaching to a log entry.
- **Listings** — Nova-style **tabular ephemerides** for the selected satellite,
  with a step interval (30 s–5 min), a span (2–24 h), and a **visible-only**
  filter, in three sub-tabs. **One observer** is a stepped position listing
  (time, az, el, range, range-rate, sub-point, altitude, sunlit) from your
  primary site. **AOS / LOS** is a compact pass list (AOS, LOS, duration, max
  elevation, AOS/LOS azimuths) for seeing many passes at once. **Two observers**
  is a stepped listing that shows your station *and* a chosen **secondary site**
  (picked from the sites you set up on the Sites screen) side by side from a
  single ephemeris. Each sub-listing exports to **CSV**.

### 3.17 Sun / Moon

Solar and lunar **azimuth/elevation** for your site, plus the **Moon phase and
illumination** percentage. Handy for visual passes and for knowing sky
conditions.

### 3.18 Celestial

Tracking and analysis for objects beyond satellites, in two tabs:

- **Bodies** — the live **azimuth/elevation** of the **Sun**, **Moon**, the
  **planets** (Mercury, Venus, Mars, Jupiter, Saturn) and a set of bright
  **cosmic radio sources** (Cassiopeia A, Cygnus A, Taurus A / Crab, Virgo A,
  Sagittarius A\* at the galactic centre, Orion A, Centaurus A, Fornax A), plus a
  **cold-sky** reference direction. Everything that is above the horizon is
  plotted on a polar sky map (zenith centre, horizon rim) and listed in a table.
  Useful for antenna calibration, sun/moon-noise measurements, and radio
  astronomy. The table exports to **CSV**.
- **EME** — an **Earth-Moon-Earth (moon-bounce)** analysis panel. Pick a band
  (6 m / 2 m / 70 cm / 23 cm / 3 cm) and it shows the **Moon's az/el and
  distance**, the **total path loss** for that band (around 252 dB on 2 m, rising
  to ~288 dB at 10 GHz), the **self-echo Doppler** on your own returning signal,
  the round-trip echo delay (~2.5 s), and a **cold-sky temperature** estimate.
  Enter a second station (grid or lat,lon) to list the **common-Moon-visibility
  windows** — the times both stations can see the Moon at once, which is the
  requirement for an EME QSO. Windows export to **CSV**.

Positions are low-precision (good to a fraction of a degree) — enough for
pointing and planning, not ephemeris-grade work.

### 3.19 Space Wx

Space-weather indices for HF/propagation context: the **solar 10.7 cm flux**,
planetary **Kp**, and the **A index**, sourced from NOAA SWPC, each with a
plain-language level and an operating outlook. Cached to disk so it still
displays offline.

### 3.20 Satellites

The **catalog** screen and the place you choose what everything else acts on, in
three tabs.

**Catalog** is the main list:

- **Filter** the list by typing.
- **Select** a satellite (it becomes the active satellite everywhere).
- **Favorite** with the **space bar** (or the "Toggle favorite" button); the ★
  marks favorites, which populate the Home map and the favorites schedule.
- **Fetch transponders** for the selected bird (from SatNOGS).
- **Add a manually-entered satellite** by its GP mean elements; manual sats
  persist across catalog refreshes. You can also **Edit** a manual satellite
  (the form opens pre-filled with its current elements) or **Delete** it. Only
  manually-entered satellites can be edited or deleted — satellites from the
  downloaded catalog are protected — and deleting one also removes it from your
  favorites.

**By type** groups the whole catalog by **SatNOGS transponder kind** — **Linear
transponder**, **FM transponder**, **Digital transponder**, **Beacon / CW**,
**Other**, and **No transponder data** — with a count per group and the downlink
and transponder kinds shown for each satellite. Filter to a single group, sort by
**name / NORAD / period**, double-click to start tracking a bird, and **Export
CSV**. (Grouping is only as complete as the transponder data you have loaded —
use **Update Transponders** for the full SatNOGS database.)

**What's up now** scans the **whole catalog** for satellites currently above your
horizon, sorted by elevation, with a minimum-elevation floor (0/5/10/20°). It
shows each satellite's az/el, range, sub-point, altitude and sunlit flag;
double-click to start tracking one, or **Export CSV**.

### 3.21 Sites

Manage the observer **locations** OrbitDeck works from, in two tabs:

- **Manage sites** — give the **primary site** a nickname (it is the location
  that drives every other screen — Track, passes, Doppler, footprints, and so
  on), and build a table of **secondary sites**: a club station, portable spots,
  or friends' QTHs. Add each by nickname and a Maidenhead grid or `lat,lon`
  (plus optional altitude); names are kept unique. Secondary sites are saved and
  persist across sessions, and are used only for comparison — they do not change
  what the rest of the app tracks.
- **Compare passes** — the selected satellite's upcoming passes (1–3 days)
  across **every site at once**: how many passes each gets, the next AOS and its
  max elevation, and each site's best pass. The primary site is listed first.
  Export to **CSV** or a printable **PDF report**.

### 3.22 Settings

Configure:

- **Observer site** — latitude, longitude, and altitude, or a Maidenhead grid
  square. (You can nickname this primary site on the **Sites** screen.)
- **GP element source** — where Update GP fetches elements from: **AMSAT**, a
  **CelesTrak category** (amateur, cubesat, stations, weather, GPS, etc.), or a
  **custom OMM-JSON URL**.
- **Minimum elevation** — the default floor (in degrees) applied to pass tables
  and reports across the app.

---

## 4. The OSCARLOCATOR system

The OSCARLOCATOR is a classic predict-by-hand tool: a polar map of the Earth with
a transparent, rotatable overlay of the satellite's ground track. You line the
track's equator crossing up with the longitude where the satellite crosses the
equator, and read off where it will be minute by minute.

OrbitDeck supports it two ways:

- **Interactive** — the [OSCARLOCATOR Sim](#311-oscarlocator-sim) screen.
- **Printable** — a multi-page PDF you print (at **100% / actual size**) onto
  paper and transparency film to build a physical OSCARLOCATOR. Export it from
  the **Track** screen or the **Sim** screen.

### Printable pages

- **Base map** — an azimuthal-equidistant map with a lat/lon graticule and
  full-resolution coastlines. The outer ring carries **per-degree tick marks**
  (with longer marks every 5° and 10°), so the rim reads like a protractor — handy
  for registering stacked overlays and measuring the per-pass arc rotation to the
  degree. Choose:
  - **Polar** (auto N/S from your latitude) — the generic ARRL/PE1RAH-style map
    anyone can use together with the equator-crossing list. 0° longitude is at
    the bottom; east increases counter-clockwise on the northern sheet (the
    conventional, un-mirrored orientation), mirrored on the southern sheet.
  - **QTH-centered** — a personalized map centered on your station, capped so it
    does not over-show the opposite hemisphere.
- **Map + Footprint at QTH** — a single QTH-centered sheet that draws the
  footprint **range circle** right on the map (centered on your station), so no
  separate transparency is needed. It carries the full set of readouts inside the
  circle: **azimuth** spokes and degree labels with N/E/S/W cardinals, **elevation
  rings** (0/10/30/60°, the 0° ring being the footprint edge), and **dashed
  ground-distance rings labelled in km** out to the footprint edge — so you can
  read the bearing, elevation, and ground distance to the sub-point directly off
  the one sheet. The footprint circle itself is kept clean — the azimuth labels
  and the elevation rings come from the base map underneath, so they aren't
  repeated on the footprint. Use the path-arc overlay on top to see when the
  satellite enters the circle. The **polar** version of this sheet carries the
  same elevation and distance rings, drawn as the correct off-centre rings around
  your station, and the footprint uses the identical red-circle style. (The
  standalone footprint transparency in the 3-sheet set keeps its own full azimuth
  rose and km labels, since it prints on its own.)
- **Footprint transparency** — the **range circle**, the same radius as the
  satellite's coverage footprint at its **mean orbital altitude**, with distance
  rings and azimuth radials. Pin it through the centre cross **over your QTH**:
  the satellite is in range whenever its ground track (the path-arc overlay) is
  **inside** this circle, so you read AOS and LOS where the arc crosses it. (When
  the QTH-centred base map is used, the 0° elevation ring is the same circle, so
  this transparency is mainly for the polar map.)
- **Path-arc overlay** — the rotatable ground-track transparency, with **minute
  tick marks** (straight marks across the track; longer, labelled marks every 10
  minutes), a bold **"EQX (0 min)"** marker showing which radial to line up with
  the equator-crossing longitude on the map, and a per-pass node-advance
  indicator. The track is referenced to the **ascending node** for northern
  sheets and the **descending node** for southern sheets, with minute 0 on the
  equator.

### How to use the printed set

1. Print all pages at **100% (actual size)** so they register on top of each
   other.
2. Print the base map on paper or card; print the path-arc (and footprint) pages
   on transparency film.
3. Pin the transparencies through the center so they rotate.
4. From the **Equ. Crossings** page (Orbital Analysis) or the **Sim** page's
   crossing list, read the **longitude** of the next equator crossing.
5. Rotate the path-arc overlay so its **EQX mark** points at that longitude on
   the base map.
6. Read along the track: each tick is one minute after the equator crossing. The
   satellite is workable while the track is inside your QTH footprint circle.

The interactive Sim does all of this on screen, which is the easiest way to learn
the workflow before committing to print.

---

## 5. Reports (printable PDFs)

Every satellite-specific screen has a **Report…** button that saves a clean,
printable **comprehensive PDF** for the selected satellite. It contains:

- orbital analysis,
- the next passes from your station,
- the equator-crossing schedule,
- a 3-day grid of **polar sky tracks**,
- the 60-day **illumination** raster, and
- the 30-day **pass progression** timeline.

Additional one-click reports live on specific screens:

| Report | Where |
|---|---|
| 7-day schedule for **all favorites** | Home → Passes tab |
| 3-day **polar sky-track grid** | Next Passes |
| **Mutual windows** with a DX station | Mutual Windows |
| 60-day **illumination** summary | Illumination → Illumination raster |
| **Eclipse ephemeris** (every-orbit + daily) | Illumination → Eclipse table |
| 30-day **pass progression** | Pass Progression |
| Printable **OSCARLOCATOR** | Track and OSCARLOCATOR Sim |
| **Doppler playbook** sheet (PDF) | Radio → Doppler playbook |
| Pass schedule as **CSV / Excel / iCal / JSON** | Exports → Pass schedule |
| **Favorites comparison** (CSV) | Exports → Compare favorites |
| Per-pass **card** (PNG) | Exports → Pass card |
| **Listings** (one-/two-observer, AOS/LOS) CSV | Exports → Listings |
| **Eclipse tables** (CSV) | Illumination → Eclipse table |
| **Work-a-target** / **visible passes** CSV | Planning |
| **Workable** grids/states/DXCC CSV | Workable |
| **Equator crossings** CSV | Orbital Analysis → Crossings List |
| **Satellites by type** / **what's up** CSV | Satellites |

Beyond PDF reports, OrbitDeck can export **data** for use in other tools — pass
schedules as CSV, Excel, iCal (with reminder alarms), or JSON; the Doppler
playbook, favorites comparison, eclipse ephemerides, stepped listings, workable
lists, planning windows, equator crossings, and the satellite catalog (by type or
what's-up) as CSV; and a shareable per-pass card image. See
[Exports](#316-exports), [Radio](#39-radio), [Illumination](#311-illumination),
[Planning](#310-planning), and [Satellites](#320-satellites).

The **minimum elevation** set in Settings is applied throughout.

---

## 6. Data sources & staying accurate

OrbitDeck reads **GP (general perturbations) elements** in the modern CCSDS OMM
JSON format and propagates them with SGP4/SDP4.

- **Update GP** (top bar) fetches a fresh catalog from your configured source
  (Settings → GP element source): AMSAT, a CelesTrak category, or a custom URL.
  OrbitDeck queries CelesTrak's `.org` domain in JSON, only when you click the
  button (it does not poll), caches the result to disk, and handles the modern
  6- and 9-digit catalog numbers that the old TLE format cannot represent.
- **Update Transponders** refreshes the SatNOGS transponder database, which feeds
  the Track screen's frequency/Doppler display.

> **Refresh regularly.** SGP4 accuracy degrades as an element set ages; aim to
> update within one to two weeks of the element epoch. A yellow banner warns you
> when the loaded catalog is demo or stale.

Be a good citizen of CelesTrak's free service: only fetch when you actually need
fresh data. OrbitDeck already reuses the cached catalog and never auto-polls.

---

## 7. Files & where settings live

Everything persistent is stored under **`~/.orbitdeck/`**:

- your observer site and preferences (including minimum elevation and GP source),
- your favorites,
- the cached GP catalog,
- the cached transponder database, and
- the cached space-weather data.

Deleting that directory resets OrbitDeck to a first-run state.

---

## 8. Troubleshooting

**Pass times look wrong / a yellow banner is showing.** You are on demo or stale
elements. Click **Update GP**. If you just did, check that your **GP source** in
Settings is reachable.

**Update GP fails.** OrbitDeck surfaces the HTTP problem. A **403** usually means
the source is rate-limiting you (CelesTrak updates only every couple of hours —
wait and reuse cached data); a **404** means the group name or URL is wrong.
OrbitDeck keeps your existing catalog rather than wiping it on a failed fetch.

**No Doppler frequencies on Track.** Fetch transponders for the satellite on the
**Satellites** screen (or **Update Transponders** in the top bar). Some
satellites have no transponder entries; you can add one manually on Track.

**The app won't start — tkinter missing.** Install Tk: `sudo apt install
python3-tk` (Debian/Ubuntu) or `sudo dnf install python3-tkinter` (Fedora). The
python.org installers for Windows and macOS already include it.

**Coastlines look coarse.** Full-resolution coastlines come from cartopy; if
cartopy isn't installed (or its map data hasn't been downloaded yet), OrbitDeck
falls back to a lower-resolution bundled outline.

**Printed OSCARLOCATOR overlays don't register.** Make sure every page is printed
at **100% / actual size** (no "fit to page" scaling), and that the transparencies
are pinned through the exact center.

---

*OrbitDeck is tracking-and-analysis software. Always confirm critical operating
information against live, current element sets.*
