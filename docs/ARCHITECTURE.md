# OrbitDeck architecture

A short orientation for contributors. The aim is to explain how the pieces fit
together so you can find the right file quickly and add features in keeping with
the existing patterns. For end-user documentation see [MANUAL.md](MANUAL.md); for
a feature overview see the [README](../README.md).

## Layered design

OrbitDeck separates the **orbital engine** (no GUI, no I/O beyond fetching
elements) from the **GUI**. The engine is independently usable and independently
tested.

```
orbitdeck/
├─ engine/      pure computation: propagation, geometry, analysis
├─ gui/         Tkinter + matplotlib UI, one module per screen
└─ data/        bundled static data (coastlines, DXCC, US states, sample GP)
```

### engine/

- **`propagator.py`** — the single place that chooses a propagation backend. It
  probes for the optional C-accelerated `sgp4` package at import time; if present
  it uses that (full SGP4/SDP4), otherwise it wraps the bundled
  **`sgp4_lite.py`** (a faithful pure-Python port of the Vallado reference).
  `have_full_sdp4()` reports which is active. Everything downstream consumes the
  common `make_satrec(...)` interface and never imports `sgp4` directly.
- **`sgp4_lite.py`** — the vendored reference propagator. It intentionally mirrors
  the published Vallado implementation, including intermediate variables, so it
  stays reviewable against the source; treat changes here with care and keep the
  Vallado test vector green.
- **`predict.py`** — `Observer`, `Predictor`, pass prediction, look angles,
  Doppler, eclipses, equator crossings, mutual visibility, Maidenhead grid
  conversion. This is the engine's main entry point for the GUI.
- **`analysis.py`** — orbit-derived quantities: J2 nodal/apsidal rates, beta
  angle, footprint radius, central-angle/elevation geometry, decay estimates,
  sun-synchronous detection.
- **`linkbudget.py`**, **`planning.py`**, **`celestial.py`**, **`satdb.py`** —
  link budgets, pass scoring / optical visibility, Sun/Moon/planet positions, and
  the satellite database + transponder model and category classification.

### gui/

- **`app.py`** — the application shell: builds the window, the navigation list
  (`NAV_ITEMS`), the top bar, the status line, and owns the background threads for
  *Update GP* and *Update Transponders*. It holds the single `Store`.
- **`store.py`** — **the central state object.** One `Store` instance holds the
  loaded catalog (`db`), the primary observer (`obs`) and secondary sites, the
  selected satellite (`selected_norad` / `select()`), favorites, the shared
  `Predictor`, the minimum-elevation preference, and config load/save. Screens
  read and mutate state through the `Store`; they do not keep their own copies.
- **`screens/`** — one module per screen, each a subclass of `Screen` (in
  `screens/__init__.py`). `make_screen(key, parent, app)` maps a nav key to its
  class. A screen builds its widgets into `self.frame`, reads state via
  `self.store` / `self.sat()` / `self.pred()`, and uses shared helpers from
  `screens/__init__.py` (`KVPanel`, `TabBar`, `MplPanel`, `make_scrolled_tree`,
  `autohide_scrollbar`, the theme colour constants, …). To add a screen: create
  the module, register it in `make_screen`, and add it to `NAV_ITEMS`.
- **`oscarlocator.py`**, **`reports.py`**, **`doppler_sheet.py`**,
  **`passcard.py`**, **`exports.py`** — printable/exportable output (PDF, CSV,
  XLSX). `mapdraw.py` draws the world map and, like the propagator, probes for the
  optional `cartopy` package and falls back to the bundled coastlines.

## Conventions worth knowing

- **Optional dependencies are detected, never required.** `sgp4` and `cartopy` are
  probed at import time with a `try/except` and a `have_*()` helper; the app must
  work without them. A CI job runs the suite with them absent to keep the
  fallbacks honest.
- **Theme colours** are module constants in `app.py` (`COL_BG`, `COL_PANEL`,
  `COL_ACCENT`, …) re-exported through `screens/__init__.py`; use them rather than
  hard-coded hex so the dark theme stays consistent.
- **Deep-space accuracy** is surfaced, not hidden: when the bundled propagator is
  used for a deep-space object, the header shows a reduced-accuracy warning
  (`Predictor.deepspace_approximate()`).
- **No network keys.** GP elements (AMSAT) and transponders (SatNOGS) are fetched
  with the standard library only.

## Tests

Tests live in `tests/`, split by area (`test_propagation.py`,
`test_oscarlocator.py`, `test_radio.py`, `test_reports.py`, `test_planning.py`,
`test_analysis.py`, `test_celestial.py`, `test_gui.py`, …). Shared fixtures are in
`tests/conftest.py` and non-fixture helpers in `tests/_helpers.py`. The headline
test checks the vendored propagator against the canonical Vallado reference
vector; please keep it green when touching `sgp4_lite.py`.

Run `pytest -q` and `ruff check orbitdeck` before opening a PR.
