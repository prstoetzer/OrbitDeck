# Contributing to OrbitDeck

Thanks for your interest in improving OrbitDeck!

## Development setup

```bash
git clone https://github.com/USER/orbitdeck
cd orbitdeck
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,full]"
```

Run the app:

```bash
orbitdeck        # console entry point (installed by pip)
# or
python run.py
```

## Tests

```bash
pytest -q
```

The engine tests pin SGP4 accuracy against the canonical Vallado reference
vector. Please keep them green; if you change the propagator, run the suite
both with and without the optional `sgp4` package installed (CI does both).

## Code style

```bash
ruff check orbitdeck
```

## Architecture

- `orbitdeck/engine/` — the portable orbital core (no GUI imports). If you can
  do it without Tkinter, it probably belongs here.
- `orbitdeck/gui/` — the Tkinter app; one module per screen under
  `gui/screens/`. Screens subclass `Screen` and override `build/on_show/
  on_hide/on_tick`.
- `orbitdeck/data/` — bundled offline catalog and the simplified coastline.

## Scope

OrbitDeck deliberately covers **tracking and orbital analysis only**. Radio
(CAT) and rotator control are out of scope — there are excellent dedicated
tools for that, and the original device project already does it.

## Good first issues

- Higher-resolution bundled coastline (without pulling in cartopy).
- Antenna/observer obstruction mask for pass filtering.
- Export passes to iCal / CSV.
- Per-satellite Doppler tuning presets.
