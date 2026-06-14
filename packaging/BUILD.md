# Building standalone OrbitDeck executables

OrbitDeck is packaged with [PyInstaller](https://pyinstaller.org/). The result
is a self-contained app that bundles the Python interpreter, OrbitDeck, and all
dependencies (numpy, matplotlib, tkinter) so users **don't need Python
installed**.

> **PyInstaller does not cross-compile.** A Windows `.exe` must be built on
> Windows, a macOS `.app` on macOS, and a Linux binary on Linux. To produce all
> three, use the GitHub Actions workflow in `.github/workflows/build.yml`, which
> builds on a runner matrix.

## Quick start (current platform)

```bash
# from the repo root, ideally in a clean virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e .                     # install OrbitDeck + its dependencies
pip install pyinstaller
pyinstaller orbitdeck.spec
```

The bundle appears in `dist/OrbitDeck/` (a one-folder app). Launch it with:

- **Windows:** `dist\OrbitDeck\OrbitDeck.exe`
- **macOS:** `dist/OrbitDeck.app` (double-click, or `open dist/OrbitDeck.app`)
- **Linux:** `dist/OrbitDeck/OrbitDeck`

A helper script is provided:

```bash
python packaging/build.py        # cleans, runs PyInstaller, prints the output path
```

## One-file vs one-folder

The spec produces a **one-folder** bundle (faster startup, easy to inspect). For
a single distributable file, the simplest approach is to zip `dist/OrbitDeck/`.
A true one-file `.exe` is possible but starts slower (it unpacks to a temp dir on
each launch) and trips some antivirus heuristics; one-folder is recommended for a
matplotlib/tkinter app.

## Icons

- **Windows** uses `orbitdeck/gui/assets/icon.ico` (already in the repo).
- **Linux** uses `orbitdeck/gui/assets/icon-256.png` at runtime for the window.
- **macOS** needs an `.icns`, which must be generated on a Mac:

  ```bash
  # from orbitdeck/gui/assets/, with icon-512.png present
  mkdir icon.iconset
  for s in 16 32 64 128 256 512; do
    sips -z $s $s icon-512.png --out icon.iconset/icon_${s}x${s}.png
    d=$((s*2)); sips -z $d $d icon-512.png --out icon.iconset/icon_${s}x${s}@2x.png
  done
  iconutil -c icns icon.iconset -o icon.icns
  ```

  Place `icon.icns` next to the other icons; the spec picks it up automatically.

## Common gotchas (already handled in the spec)

- **matplotlib data files** (fonts, `mpl-data`) are collected via
  `collect_data_files("matplotlib")`.
- **tkinter / Tcl-Tk** runtimes are bundled automatically; the hidden imports in
  the spec make the Tk backend resolve.
- **`~/.orbitdeck`** (config, GP cache, transponder cache, space-wx cache) is
  created in the user's home directory at runtime, so it works the same whether
  run from source or from a frozen bundle.
- The app **runs offline**: live data (GP, transponders, space weather) is
  fetched on demand and cached; without a network the app uses bundled sample
  elements and the last cached data.

## Reducing size

The spec already excludes Qt, wx, pytest, and IPython. UPX compression is on; if
UPX isn't installed it's skipped harmlessly. Typical bundle size is ~150–250 MB
(matplotlib + numpy dominate).

## Code signing / notarization (optional)

Unsigned apps trigger SmartScreen (Windows) and Gatekeeper (macOS) warnings.
For wide distribution:

- **Windows:** sign `OrbitDeck.exe` with `signtool` and a code-signing
  certificate.
- **macOS:** sign with a Developer ID and notarize with `notarytool`. Set
  `codesign_identity` and `entitlements_file` in the spec.

These require paid developer certificates and are out of scope for a local build.
