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
   - [3. Next Passes](#33-next-passes)
   - [4. Pass Detail](#34-pass-detail)
   - [5. Ground Track](#35-ground-track)
   - [6. Orbital Analysis](#36-orbital-analysis)
   - [7. Illumination](#37-illumination)
   - [8. Pass Progression](#38-pass-progression)
   - [9. Mutual Windows](#39-mutual-windows)
   - [10. Workable](#310-workable)
   - [11. OSCARLOCATOR Sim](#311-oscarlocator-sim)
   - [12. Sun / Moon](#312-sun--moon)
   - [13. Space Wx](#313-space-wx)
   - [14. Satellites](#314-satellites)
   - [15. Settings](#315-settings)
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
  (refresh the SatNOGS transponder database). A **yellow banner** appears here
  when the loaded catalog is demo or stale data; it also carries an Update GP
  button.
- **Navigation menu** (left) — the 15 screens, described below in order.
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

### 3.3 Next Passes

A table of upcoming passes for the selected satellite over the next 7 days. A
**minimum-elevation** control filters out passes too low to be useful (presets
plus whatever you set in Settings). **Double-click** a pass to open it in Pass
Detail. A button prints a **3-day grid of polar sky tracks** as a PDF.

### 3.4 Pass Detail

A detailed look at one chosen pass: a **polar sky-track** (the path across your
sky, N-up, zenith at center) alongside an **elevation-versus-time** profile.
Reached by double-clicking a pass on Next Passes.

### 3.5 Ground Track

The selected satellite's **forward ground track** over the next **1, 3, 5, or 8
orbits** (selectable with the radio buttons), drawn on the world map so you can
see where it will pass.

### 3.6 Orbital Analysis

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
    table.

### 3.7 Illumination

A **sunlit-versus-eclipse raster** for the selected satellite, showing a 30-day
window you can **scroll** forward and back through time (buttons or mouse wheel).
Day runs along one axis and minutes-into-orbit along the other; bright is sunlit,
dark is eclipse. A **Print 60-day** button exports the full summary, which reports
the mean eclipse fraction — useful for power-budget reasoning.

### 3.8 Pass Progression

The selected satellite's passes across **10 or more days**, drawn as a scrollable
stack of **24-hour timelines** — one row per day. Each pass sits at its time of
day, its width is its duration, and its shade encodes max elevation. This is the
"how does my pass time drift day to day" view.

### 3.9 Mutual Windows

**Co-visibility** windows — the times when both you and a **DX station** can see
the same satellite simultaneously (the requirement for a direct satellite QSO).
Enter the DX station as a Maidenhead grid or as `lat,lon`. A button prints the
mutual-windows report.

### 3.10 Workable

What is **inside the satellite's footprint** — useful for grid-square, US-state,
and DXCC chasing. Choose the category with the radio buttons:

- **Grids** — Maidenhead grid squares.
- **US States** — states currently reachable.
- **DXCC** — DXCC entities currently reachable.

And choose the time mode:

- **Live** — what is under the footprint right now (refreshes every few seconds).
- **Pass** — the union of everything reachable across the next pass.

### 3.11 OSCARLOCATOR Sim

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

### 3.12 Sun / Moon

Solar and lunar **azimuth/elevation** for your site, plus the **Moon phase and
illumination** percentage. Handy for visual passes and for knowing sky
conditions.

### 3.13 Space Wx

Space-weather indices for HF/propagation context: the **solar 10.7 cm flux**,
planetary **Kp**, and the **A index**, sourced from NOAA SWPC, each with a
plain-language level and an operating outlook. Cached to disk so it still
displays offline.

### 3.14 Satellites

The **catalog** screen and the place you choose what everything else acts on:

- **Filter** the list by typing.
- **Select** a satellite (it becomes the active satellite everywhere).
- **Favorite** with the **space bar** (or the "Toggle favorite" button); the ★
  marks favorites, which populate the Home map and the favorites schedule.
- **Fetch transponders** for the selected bird (from SatNOGS).
- **Add a manually-entered satellite** by its GP mean elements; manual sats
  persist across catalog refreshes.

### 3.15 Settings

Configure:

- **Observer site** — latitude, longitude, and altitude, or a Maidenhead grid
  square.
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
  full-resolution coastlines. Choose:
  - **Polar** (auto N/S from your latitude) — the generic ARRL/PE1RAH-style map
    anyone can use together with the equator-crossing list. 0° longitude is at
    the bottom; east increases counter-clockwise on the northern sheet (the
    conventional, un-mirrored orientation), mirrored on the southern sheet.
  - **QTH-centered** — a personalized map centered on your station, capped so it
    does not over-show the opposite hemisphere.
- **Footprint transparency** — the coverage circle with distance rings and
  azimuth radials, sized at the satellite's **mean orbital altitude**.
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
| 60-day **illumination** summary | Illumination |
| 30-day **pass progression** | Pass Progression |
| Printable **OSCARLOCATOR** | Track and OSCARLOCATOR Sim |

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
