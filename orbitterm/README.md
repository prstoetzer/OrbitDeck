# OrbitTerm

A terminal (curses) application for amateur-radio satellite
operating. OrbitTerm runs in any terminal — including over SSH on a headless
Raspberry Pi or a remote shack PC — and reuses the exact OrbitDeck engine
(vendored SGP4/SDP4 propagator, pass prediction, Doppler, orbital analysis) plus
the same `~/.orbitdeck` configuration and AMSAT catalog cache. Its numbers match
the desktop GUI because it calls the same code.

Pure Python standard library (`curses`) — no extra dependencies beyond
OrbitDeck's own.

## Running

**In the desktop download.** The OrbitDeck bundle for your platform contains an
`OrbitTerm` binary beside `OrbitDeck` — run it directly, no second download.

**Standalone download.** Every release also carries a single-file `OrbitTerm`
executable for Windows, macOS (Apple Silicon and Intel), Linux x86_64 and 64-bit
Raspberry Pi OS. It needs no Python install — about 9 MB, since the terminal UI
uses none of the desktop app's matplotlib/tkinter/cartopy stack. On Windows the
build bundles `windows-curses`, which the console needs.

```sh
orbitterm          # if installed via pip
# or, from a source checkout:
python -m orbitterm
python runterm.py
```

It shares state with the OrbitDeck GUI: your station, minimum-elevation
preference, selected satellite, favorites and the cached GP catalog all live in
`~/.orbitdeck/` and are read/written by both tools.

## Screens

| # | Screen | What it shows |
| - | --- | --- |
| 1 | Home | Station, catalog status, the selected satellite's live look, next pass, and everything currently above the horizon |
| 2 | Satellites | Searchable catalog (`/` filters, `f` favorites); live up/down status per satellite |
| 3 | Track | Full live look: az/el with bar, range, range-rate, sub-point, altitude, sunlit, sun geometry, visibility, AOS/LOS countdown |
| 4 | Next Passes | Scrollable pass table (date, AOS/TCA/LOS, color-coded max elevation, AOS/LOS azimuth); `e`/`E` adjusts minimum elevation |
| 5 | Pass Detail | One pass in full: braille sky curve, elevation profile and the numbers for AOS, TCA and LOS |
| 6 | Sky Radar | Everything above the horizon on a braille polar plot, with the active satellite's sub-point and altitude |
| 7 | Ground Track | World map with coastline outlines, the ground track past and future, footprint ring and your station |
| 8 | Pass Progression | One 24-hour timeline per day, passes shaded by maximum elevation |
| 9 | Illumination | Sunlit/eclipse raster at half-block resolution over a multi-day window, plus an eclipse table |
| 10 | Orbital Analysis | Six pages (`p`): elements, live geometry, next pass, 7-day pass statistics, anomalies and decay, and identity with launch data |
| 11 | Radio | Transponder Doppler dials with a live shift curve; `l` shows the link budget |
| 12 | Tools | The full 49-calculator hub with text and picker fields |
| 13 | 3D Globe | Orthographic wireframe globe on the braille canvas, with follow and track modes |
| 14 | Sky at a Glance | Pass timeline across every favorite, and the longest quiet gap |
| 15 | Planning | Workable horizon and target search for award chasing |
| 16 | Mutual Windows | Common-visibility windows against a DX grid |
| 17 | Sun/Moon Transits | Solar and lunar disk crossings and near approaches |
| 18 | Conjunctions | Close approaches against another catalog object |
| 19 | AO-7 Mode | AO-7 mode A/B phase estimate with fit confidence and report agreement |
| 20 | Workable | Grids, US states and DXCC entities under the footprint; `f` filters by prefix |
| 21 | Orbital Zones | SAA, radiation belt, polar cap and eclipse transits |
| 22 | Sun / Moon |  |
| 23 | EME | Moonbounce: path loss, Doppler, common-Moon windows (`e` sets the DX grid), per-band analysis and a 90-day plan |
| 24 | Sky Map | The satellite's track against the star background |
| 25 | Orbital History | Space-Track element archive (`f` fetches it) in value, rate, analysis and table views with zoom |
| 26 | Graphing Calc | Two-trace expression plotter on the braille canvas |
| 27 | MUF / HF Prop |  |
| 28 | Propagation | HF and 6 m outlook: MUF, per-band day/night states, aurora, absorption, meteor scatter and Es season |
| 29 | Space Wx | Solar and geomagnetic indices with band labels and a plain-language outlook |
| 30 | Celestial | Radio-source az/el for alignment and sun-noise work |
| 31 | Astronomy | Meteor showers, Jupiter decametric windows, aurora, twilight, EME conditions, and lunar/planetary events (`a` cycles the view) |
| 32 | Activations | Upcoming hams.at activations; `w` checks whether you can work it, then windows and DX Doppler |
| 32 | AMSAT Status | Community status board; `m` matches the active satellite to its API name |
| 33 | Sites | Saved observer locations |
| 34 | Exports | CSV and report output |
| 35 | OSCARLOCATOR | The paper instrument on screen: graticule disc, ground-track arc and footprint, live or manual |
| 36 | References | 14 lookup tables, one at a time with left/right to change |
| 37 | Settings | Station, grid, callsign and QRZ/Space-Track credentials — everything OrbitTerm needs, no desktop install required |

## Keys

- **Tab** — open the scrolling navigation menu; `↑`/`↓` to move, type a
  letter to jump, **Enter** to open. (Number shortcuts are gone: they
  reached only ten of 37 screens.)
- **`[` / `]`** — previous / next satellite (on detail screens).
- **`+` / `-`** — more / fewer days (Pass Progression, Illumination span).
- **`v`** — switch view (Illumination: raster ⇄ eclipse table).
- **`s`** — orbit / daily mode (Illumination eclipse table).
- **`↑`/`↓`, PgUp/PgDn, Home/End** — move within lists.
- **`Enter`** — select / open / edit, depending on the screen.
- **`/`** — search (Satellites). **`f`** — toggle favorite.
- **`R`** — fetch a fresh AMSAT catalog online (Home / Settings).
- **`q`** — quit.

The footer always shows the keys available on the current screen.

## Notes

- The ASCII world map and sky radar are schematic aids for orienting the eye;
  the underlying geometry (az/el, sub-point, Doppler) is the same precise engine
  output as the GUI.
- Deep-space orbits (period ≥ 225 min) are flagged as *approximate* when the
  full reference SDP4 backend isn't installed, exactly as in the GUI.
- OrbitTerm does not do radio/rotator CAT control — that's out of scope for the
  OrbitDeck project as a whole.

---

*OrbitTerm — part of OrbitDeck by Paul Stoetzer, N8HM. MIT-licensed.*
