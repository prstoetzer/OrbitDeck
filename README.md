# OrbitDeck

**Cross-platform desktop satellite tracking & orbital analysis for amateur radio operators.**

OrbitDeck is a desktop application for **satellite tracking and orbital
analysis** — a roomy UI with embedded plots, built for amateur-radio operators
who work the birds. It is **tracking and analysis only**: radio (CAT) and
rotator control are intentionally out of scope, since excellent dedicated tools
already cover that.

It uses the reference [`sgp4`](https://pypi.org/project/sgp4/) propagator and
[`cartopy`](https://pypi.org/project/Cartopy/) (both **required dependencies**,
installed automatically) for accurate SGP4/SDP4 across low-Earth and deep-space
orbits and full-resolution coastlines. A pure-Python propagator and a bundled
coastline set ship as fallbacks.

<p align="center">
  <img src="docs/img/home.png" width="80%" alt="Home: all favorite satellites with footprints on the world map">
</p>

---

## Quick start

```bash
git clone https://github.com/prstoetzer/OrbitDeck
cd OrbitDeck
pip install -e .
orbitdeck
```

Or without installing:

```bash
pip install -r requirements.txt
python run.py
```

The base install pulls only `matplotlib`, `numpy`, and `certifi`, so it is quick
and reliable on every platform. On first launch OrbitDeck loads a small bundled
catalog (ISS, SO-50, AO-91, CAS-4B, RS-44) so every screen works immediately
offline. Click **Update GP (online)** to pull the live AMSAT catalog, and use the
**Satellites** screen to fetch SatNOGS transponder data for the selected bird.

> ⚠️ **Pass times from the bundled catalog are illustrative, not real.** The
> demo elements are stamped to the current date so the geometry is sensible, but
> their orbital *phase* is synthetic — they will not tell you when a satellite
> is actually overhead. A yellow banner reminds you while demo (or stale) data
> is loaded. **Click *Update GP (online)* for accurate, on-the-air pass times.**
> SGP4 is only trustworthy within ~1–2 weeks of an element set's epoch, so
> refresh periodically.

### Optional extras

OrbitDeck runs fully on its bundled, pure-Python building blocks, but two
optional packages improve it for users who want them:

| Extra | Adds | What you lose without it |
|---|---|---|
| `pip install "orbitdeck[accurate]"` | `sgp4` — the C-accelerated full SGP4/SDP4 backend | The bundled pure-Python propagator is used instead. It is accurate to well under a kilometre for typical LEO passes; the difference grows for deep-space / geostationary objects. |
| `pip install "orbitdeck[maps]"` | `cartopy` — high-resolution Natural Earth coastlines | The bundled lower-resolution coastlines are drawn instead (everything still works; the map outlines are just coarser). |
| `pip install "orbitdeck[excel]"` | `openpyxl` — native `.xlsx` export | Spreadsheet exports fall back to CSV. |
| `pip install "orbitdeck[full]"` | all of the above | — |

`cartopy` in particular depends on the GEOS/PROJ system libraries and can be
awkward to build, which is exactly why it is optional rather than required —
install it only if you want the high-resolution coastlines.

> **tkinter note:** the python.org installers for Windows and macOS include
> tkinter. On Linux: `sudo apt install python3-tk` (Debian/Ubuntu) or
> `sudo dnf install python3-tkinter` (Fedora).

---

## Features

The table below lists the screens **in the exact order they appear in the
left-hand navigation menu**.

| # | Screen | What it shows |
|---|---|---|
| 1 | **Home** *(default)* | Opens on a **Dashboard** tab: what's overhead right now, the **next passes across all favorites** (soonest first, with live countdowns), a one-click **"Print 7-day schedule (all favorites)"**, and a space-weather glance. A **Map** tab shows all favorited satellites with their footprints, the day/night terminator and your station (click one to focus it with its ground track). |
| 2 | **Track** | Live azimuth/elevation, slant range, range-rate, sub-point, altitude, transponder selector (FM/linear/beacon/data, passband, baud) and Doppler-corrected RX/TX using the passband **center** for linear transponders, sunlit/eclipse, next AOS/LOS, and a live sky polar plot. You can **add a manual transponder** and **export a printable OSCARLOCATOR PDF** for the selected satellite. |
| 3 | **3D Globe** | A rotatable orthographic "view from space" globe showing **all your favorite satellites live** (each with its coverage footprint and a label), with the selected one emphasized and carrying its ground track, plus the day/night terminator and your station. **Click and drag to spin the globe to any viewpoint** (a "Free (drag)" view), or snap to follow the satellite, center on your station, or look down a pole. A **time scrubber** (±180 min, with play and a speed control) flies the whole scene forward or back; at "now" the favorites advance in real time. |
| 4 | **Sky Radar** | Defaults to a **live radar of all favorites** — the current sky position (azimuth/elevation) of every favorite above your horizon, updating in real time (center = zenith, rim = horizon). Also offers an **all-passes overlay** (the next N passes of the selected satellite on one polar plot) and a **sky-coverage heatmap** showing where in your sky the satellite spends its time. |
| 5 | **Next Passes** | Pass table for the next 7 days with selectable minimum elevation and a **quality score** (0\u2013100 from peak elevation and duration, best pass flagged \u2605); double-click a pass for its detail. Prints a **3-day grid of polar sky tracks**. |
| 6 | **Pass Detail** | Polar sky-track plus an elevation-vs-time profile for a chosen pass. |
| 7 | **Ground Track** | Forward ground track over the next 1, 3, 5, or 8 upcoming orbits. |
| 8 | **Orbital Analysis** | Eleven pages (see the manual): Info, Live, Next Pass, Ground Track, Doppler, Nodal, Sun/Beta, Pass Outlook, Orbit Position, Equ. Crossings, and Crossings List. Clean grouped data cards and plots. The Crossings List exports the equator-crossing schedule to CSV. |
| 9 | **Radio** | Pick an **upcoming pass** to plan against, then get a **link budget** (free-space path loss, propagation delay, estimated received power, with separate **your-station** and **satellite** (TX power + antenna gain) parameters) with a **time-in-pass scrubber** that evaluates the geometry anywhere from AOS to LOS (snap to TCA), plus range-rate and downlink-Doppler readouts. A **Doppler tuning playbook** gives a per-pass table of corrected RX/TX frequencies (with antenna **az/el** at each step) at a chosen interval, with its own **passband-position** slider so a linear bird's table is built around where you're tuned. For a linear transponder worked full duplex you can **hold the uplink OR the downlink fixed** and the other leg is round-trip corrected so you keep hearing yourself. Export the playbook to CSV or a printable PDF sheet. |
| 10 | **Planning** | Goal-directed planning: **best time to work a target** (grid square, US state, DXCC entity, or lat/lon) by finding windows when you and the target share the footprint; **visible passes** with estimated optical magnitude and a twilight-darkness filter; **satellite-to-satellite** line-of-sight windows; a **rove route planner** (enter your planned grid stops with optional time-window hints and get, per stop, the covering passes and the US states / DXCC entities / grids workable through each, for the selected satellite **or all your favorites at once** \u2014 exportable to CSV and a printable rove sheet); and an **element-set trust** panel (epoch age, trust level, along-track drift estimate). Results export to CSV. |
| 11 | **Illumination** | A **raster** tab: scrollable 30-day sunlit-vs-eclipse map (prints a 60-day summary with mean eclipse fraction). An **Eclipse table** tab: orbit-by-orbit umbral eclipse list (enter/exit/duration/interval/sun-angle) and a daily summary (total, longest, percent of day, beta angle) over a selectable 1–14 day span, exportable to CSV and a printable PDF report. |
| 12 | **Pass Progression** | One satellite's passes across 10+ days as a scrollable stack of 24-hour timelines — each pass placed at its time of day, width = duration, shaded by max elevation. |
| 13 | **Mutual Windows** | Co-visibility windows between you and a DX station (entered as a grid or lat,lon), for the **selected satellite** or **all your favorites** at once (one chronological table tagged by satellite). **Double-click a window** to see the pass on a polar plot from **each station's perspective side by side**, with the mutually-visible portion highlighted on each. Exportable to CSV and a PDF report. |
| 14 | **Workable** | What's inside the footprint — **grids**, **US states**, or **DXCC entities** — live (now) or unioned across the next pass, for grid/state/DX chasing. Exports the current list to CSV. |
| 15 | **OSCARLOCATOR Sim** | An interactive on-screen OSCARLOCATOR: rotate the path-arc overlay over a polar or QTH base map and watch the satellite position and QTH footprint move, without printing transparencies. The map has a **protractor-style rim** with per-degree tick marks and longitude / azimuth labels. Drive it live, by hand (EQX-longitude and minutes-after-EQX sliders), or seed it to the next pass; a compact next-equator-crossings list is built in. A **lab-satellite mode** (educational) lets you invent a hypothetical satellite and edit its orbital elements with sliders + entries in a pop-up \u2014 with live explainers, preset orbits, an A/B comparison ghost, a guided tour, and a glossary \u2014 then name it and print it as an OSCARLOCATOR. Exports the matching printable PDF. |
| 16 | **Learn** | A home for OrbitDeck's teaching tools, organised into five groups (**Orbits**, **Geometry**, **Passes**, **Radio**, **Reference**) selected from a category row, with a **"use a lab orbit" toggle** so the orbit tools can run against a satellite you design. **Orbits:** a **Kepler** equal-areas demo, an **Anomalies** mean-vs-true visualiser, a **Speed** (vis-viva) plot, a **Transfers** Hohmann delta-v calculator, an **element-age** view, and a **Decay** lifetime-vs-altitude curve. **Geometry:** **Slant range** vs elevation, a **Horizon** reach view, a **Track drift** westward-shift view, a **Precession** sun-synchronous-orbit explainer, and a **Constellation** coverage estimator. **Passes:** a 24-hour **coverage heat map**, the **beta-angle sunlight** threshold, an **Eclipse** lit/shadow timeline, a **Pointing** sky-track, and a **Grid squares** Maidenhead locator tool. **Radio:** an interactive **Transponder** diagram, a two-leg **Doppler** plot, a **link-budget** sandbox, a **full-duplex tuning practice** widget, and an **Antenna** gain pattern. **Reference:** a broad satellite/RF/history reference and a printable four-page **Handouts** classroom set. |
| 17 | **Exports** | Export the pass schedule to **CSV, Excel, iCal, or JSON** (the iCal events carry a 10-minute reminder alarm); a **multi-satellite comparison** of your favorites; a shareable **per-pass card**; a **Reference orbits** PDF (the first equator crossing of each UTC day for the next 30/60 days — ascending for northern stations, descending for southern — to set up a physical OSCARLOCATOR); and a **Listings** tab with Nova-style tabular ephemerides (one-observer stepped, AOS/LOS quick list, and two-observer stepped), each CSV-exportable. |
| 18 | **Sun / Moon** | Solar and lunar az/el for your site, plus Moon phase and illumination. |
| 19 | **Celestial** | Live az/el of the **Sun, Moon, planets** (Mercury–Saturn) and **cosmic radio sources** (Cassiopeia A, Cygnus A, Crab, Sgr A\*, etc.) plus a **cold-sky** reference and the **selected satellite**, on a sky polar plot and table — for antenna calibration and radio astronomy. A second tab is an **EME (moon-bounce) panel**: Moon az/el and distance, total path loss by band (6 m–3 cm), self-echo Doppler, sky temperature, and **common-Moon-visibility windows** with a second station. CSV-exportable. |
| 20 | **Space Wx** | Solar 10.7 cm flux, planetary Kp, and A index from NOAA SWPC, with plain-language levels and an operating outlook. Cached for offline viewing. |
| 21 | **Satellites** | The catalog across three tabs: **Catalog** (filter, select, favorite ★, fetch transponders, and **add, edit, or delete manually-entered satellites** by GP mean elements that persist across refreshes); **By type** (the whole catalog grouped by SatNOGS transponder kind — linear / FM / digital / beacon-CW / other — sortable and CSV-exportable); and **What's up now** (a live scan of the whole catalog for satellites above your horizon, sorted by elevation, CSV-exportable). |
| 22 | **Sites** | Manage observer locations: nickname the **primary site** (which drives every other screen) and build a table of **secondary sites** (club, portable, friends' QTHs). A **Compare passes** tab shows the selected satellite's upcoming passes across all sites side by side, exportable to CSV or a PDF report. |
| 23 | **Settings** | Set your observer site by lat/lon/altitude or Maidenhead grid, choose the **GP element source** (AMSAT, a CelesTrak category, or a custom OMM-JSON URL), and set the **minimum elevation** used across pass tables and reports. |

A **Pass alarms** toggle in the top bar raises AOS / TCA / LOS notifications (a
gentle audible cue, the in-app status line, and a **native desktop toast** for
"starting soon" and AOS) for favorite satellites' next passes, so you don't miss
a rising bird while working in another screen or another app.

### Keyboard shortcuts

| Key | Action |
|---|---|
| `Ctrl`+`K` | Command palette — jump to any screen or satellite by typing |
| `Ctrl`+`F` or `/` | Find / select a satellite |
| `[` / `]` | Previous / next satellite |
| `1`–`9` | Jump to the Nth sidebar screen |
| `Ctrl`+`+` / `Ctrl`+`-` / `Ctrl`+`0` | Text size larger / smaller / reset |
| `F1` or `?` | Shortcut help |

(Shortcuts are ignored while you're typing in a text field.)

Every satellite-specific screen has a **Report…** button that saves a clean,
printable PDF for the selected satellite — a comprehensive document with orbital
analysis, next passes, the equator-crossing schedule, a 3-day sky-track grid, the
60-day illumination raster and the 30-day pass progression. Additional one-click
reports print a **7-day favorites schedule** (Home), **mutual windows** (Mutual
Windows), a **60-day illumination** summary (Illumination), a **30-day pass
progression** (Pass Progression), and a **3-day sky-track grid** (Next Passes).

For full, step-by-step documentation of every screen and workflow, see
**[the OrbitDeck manual](docs/MANUAL.md)**.

<p align="center">
  <img src="docs/img/sunmoon.png" width="42%" alt="Sun and Moon sky dome">
  &nbsp;&nbsp;
  <img src="docs/img/doppler.png" width="50%" alt="Doppler curve">
</p>

Settings, favorites, your site and the cached catalog persist under
`~/.orbitdeck/`.

---

## Accuracy & the SGP4 backend

The orbital core uses the **WGS72** gravity model to match the GP/TLE mean
elements. Key conventions:

* range-rate (for Doppler) is taken from the **SGP4 velocity vector**, not by
  differencing slant range;
* eclipse uses the **cylindrical Earth-shadow** test;
* beta angle is the orbit-plane-to-Sun angle;
* mutual windows are true two-station co-visibility.

**Propagation backend.** OrbitDeck ships its own dependency-free pure-Python
implementation, `orbitdeck/engine/sgp4_lite.py`, and runs entirely on it out of
the box. It is verified against the canonical Vallado *AIAA-2006-6753* reference
vector (catalog 88888) to about **one centimetre** at epoch and is accurate for
**near-Earth LEO** — essentially every FM and linear amateur satellite (SO-50,
the AO/FO/CAS birds, the ISS, RS-44, etc.), where it tracks the reference
[`sgp4`](https://pypi.org/project/sgp4/) package to well under a kilometre across
a typical pass.

Installing the optional `accurate` extra (`pip install "orbitdeck[accurate]"`)
adds the C-accelerated reference `sgp4` package. `orbitdeck/engine/propagator.py`
detects it at runtime and uses it automatically — no configuration needed.

**Deep-space orbits (GEO/HEO).** For deep-space orbits (orbital period ≥ 225 min
— e.g. the geostationary QO-100 / Es'hail-2, AO-7's ~12-hour orbit, or
Molniya-type orbits), full reference SDP4 gives the most correct positions. The
bundled propagator's deep-space terms are only approximate, so when it is in use
for such an object OrbitDeck **flags it in the header with a reduced-accuracy
warning** — an approximate model can mis-place a geostationary bird badly enough
to imply it rises and sets when it does not. Installing the reference backend
removes the warning and restores full accuracy:

```bash
pip install "orbitdeck[accurate]"   # or simply: pip install sgp4
```

In short: the base install is exact enough for everyday LEO satellite operating;
add `accurate` if you work deep-space birds or want the last bit of precision.

---

## Use the engine without the GUI

`orbitdeck.engine` has no GUI dependency, so you can script with it:

```python
import time
from orbitdeck.engine import SatDb, Predictor, Observer

db = SatDb()
db.load_gp_json(open("gp.json").read())

pred = Predictor()
pred.set_site(Observer(lat=39.93, lon=-74.89, alt_m=20, valid=True))
pred.set_sat(db.get(25544))               # ISS

for p in pred.predict_passes(time.time(), min_el=5.0, max_n=5):
    print(p.aos, round(p.max_el, 1))
```

---

## Project layout

```
orbitdeck/
├─ run.py                      dev entry point (python run.py)
├─ pyproject.toml              packaging + `orbitdeck` console script
├─ tests/                      pytest suite, split by area (propagation,
│                              oscarlocator, radio, reports, planning, …)
└─ orbitdeck/
   ├─ engine/                  portable orbital core (no GUI)
   │  ├─ sgp4_lite.py          vendored pure-Python SGP4/SDP4 (WGS72)
   │  ├─ propagator.py         backend selector (reference sgp4, lite fallback)
   │  ├─ satdb.py              GP/OMM + SatNOGS parsing, SatEntry/Transponder
   │  └─ predict.py            look angles, passes, Doppler, eclipse, beta,
   │                           footprint, mutual windows, Maidenhead grid
   ├─ data/                    bundled offline catalog + simplified coastline
   └─ gui/                     Tkinter app
      ├─ app.py                main window, nav, theme, clock loop
      ├─ store.py              state, persistence, online fetch (stdlib only)
      ├─ mapdraw.py            world basemap (cartopy if present, else bundled)
      └─ screens/              one module per screen
```

---

## Data sources

* **GP elements:** AMSAT daily bulletin (`newark192.amsat.org`).
* **Transponders:** SatNOGS DB transmitters API.

Both are fetched with the Python standard library only; no API key required.

---

## Testing

```bash
pip install -e ".[dev]"
pytest -q
ruff check orbitdeck      # lint
```

The 130+ tests are organised by area under `tests/` (`test_propagation.py`,
`test_oscarlocator.py`, `test_radio.py`, `test_reports.py`, `test_planning.py`,
and so on), with shared fixtures in `tests/conftest.py`. CI runs the suite on
Python 3.8/3.10/3.12. Because `sgp4` and `cartopy` are optional, one CI job runs
the full suite **without** them, guaranteeing the bundled fallback propagator and
coastlines stay correct on their own (with deep-space orbits flagged as
approximate, exactly as the app does at runtime).

---

## What was intentionally left out

By design, OrbitDeck does **not** include **radio/CAT control** (Icom CI-V,
Yaesu, Kenwood, IcomNet, `rigctld`) or **rotator control** (`rotctld`). The
engine still computes the Doppler-corrected frequencies and look angles those
subsystems would consume, so a rig/rotator bridge could be added later — but it
is not part of OrbitDeck.

## Coverage (tracking & analysis)

OrbitDeck provides a full tracking and orbital-analysis surface:

Satellites catalog; all of the Orbital-Analysis pages (Info, Live, Next Pass,
Ground Track, Doppler, Nodal/J2, Sun-Beta, Pass Outlook, Orbit Position, EQX
map and list); Next Passes; Pass detail & polar; Mutual windows; multi-day pass
progression; 60-day illumination; live Track; world map with footprint and
terminator; an interactive 3D globe; Sun/Moon and Celestial; **Workable grids,
US states, and DXCC**; rove planning; a broad **Learn** teaching suite;
**Space Weather** (F10.7 / Kp / A from NOAA SWPC); Settings; GP-age warnings;
online GP (AMSAT) and transponder (SatNOGS) fetch.

The only capabilities intentionally excluded are **radio (CAT) and rotator
control** — see above.

**Notes on the workable overlays.** Grids are computed geometrically (no bundled
data). US states use multi-point interior sampling per state, and DXCC uses
per-entity reference points for a practical set of the commonly worked / spread
entities. Both are footprint-scale accurate and intentionally lightweight; a
footprint grazing a border may briefly list a neighbour, which is correct at
footprint scale (both are workable).

---

## Author

OrbitDeck is written by **Paul Stoetzer, N8HM**. Source code, the issue
tracker, and releases are on GitHub:
[github.com/prstoetzer/OrbitDeck](https://github.com/prstoetzer/OrbitDeck).

## Supporting AMSAT

If you find OrbitDeck useful, please consider **joining and/or donating to
AMSAT** — the Radio Amateur Satellite Corporation — at
[www.amsat.org](https://www.amsat.org).

AMSAT is a volunteer, member-supported non-profit organization that designs,
builds, arranges launches for, and operates the amateur radio satellites that
OrbitDeck is built to track. Founded in 1969, AMSAT has kept amateur radio in
space for over half a century, building everything from the early OSCAR
satellites to today's linear-transponder and FM birds that this program helps
you work. The organization receives no government funding: membership dues and
donations are what fund the design and launch of the next generation of amateur
satellites. Supporting AMSAT directly helps keep these satellites — and the
hobby of satellite operating — alive.

## License

MIT — see [LICENSE](LICENSE).

OrbitDeck is an independent project; its satellite-tracking math follows the
public Vallado SGP4 reference.
