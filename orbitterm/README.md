# OrbitTerm

A terminal (curses) companion to **OrbitDeck** for amateur-radio satellite
operating. OrbitTerm runs in any terminal — including over SSH on a headless
Raspberry Pi or a remote shack PC — and reuses the exact OrbitDeck engine
(vendored SGP4/SDP4 propagator, pass prediction, Doppler, orbital analysis) plus
the same `~/.orbitdeck` configuration and AMSAT catalog cache. Its numbers match
the desktop GUI because it calls the same code.

Pure Python standard library (`curses`) — no extra dependencies beyond
OrbitDeck's own.

## Running

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
| 1 | Home | Station, catalog status, selected-sat live look, next pass, and everything currently above the horizon |
| 2 | Satellites | Searchable catalog (`/` to filter, `f` to favorite); live up/down status per sat |
| 3 | Track | Full live look: az/el with bar, range, range-rate, sub-point, altitude, sunlit, sun geometry, visibility check, LOS/AOS countdown |
| 4 | Next Passes | Scrollable pass table (date, AOS/TCA/LOS, max-el colour-coded, AOS/LOS azimuth); `e`/`E` adjusts min elevation |
| 5 | Sky Radar | ASCII polar sky plot of everything up now (N-up, elevation rings) |
| 6 | Ground Track | ASCII world map with ground track (past/future), coverage footprint, sub-point and your station |
| 7 | Pass Progression | One 24-hour timeline per day over N days; passes placed by time of day, shaded by max elevation (`+`/`-` for more/fewer days) |
| 8 | Illumination | Sunlit/eclipse raster over a 30-day window (scroll in time) plus an umbral-eclipse ephemeris — per-orbit and per-day, with the mean eclipse fraction and beta angle (`v` switches view, `s` orbit/daily, `+`/`-` span) |
| 9 | Orbital Analysis | Elements, J2 node/perigee drift, sun-synchronicity, LTAN, beta\*, repeat-track, decay estimate, live anomalies |
| 10 | Radio | Transponder Doppler dials (nominal vs tune-now), shift, and a live downlink-Doppler curve across the next pass |
| 11 | Settings | Edit station lat/lon/alt/name and min-elevation; refresh the catalog |

## Keys

- **Number keys 1–9, 0** — jump straight to a screen.
- **Tab** — move focus to/from the left nav column (then `↑`/`↓` to pick).
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
