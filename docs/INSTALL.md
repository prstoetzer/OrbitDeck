# OrbitDeck — Install, Run & Build Guide

This guide covers **installing Python**, **running OrbitDeck from source**, and
**building a standalone application**, on every supported platform:

- [Windows](#windows)
- [macOS](#macos)
- [Debian / Ubuntu](#debian--ubuntu)
- [Fedora](#fedora)
- [Arch Linux](#arch-linux)
- [Raspberry Pi OS](#raspberry-pi-os)

For **native distribution packages** (`.deb`, `.rpm`, Arch `PKGBUILD`,
AppImage, Flatpak), see the separate [packaging guide](../packaging/PACKAGING.md).
For the **PyInstaller** standalone-bundle details, see
[`packaging/BUILD.md`](../packaging/BUILD.md).

---

## What OrbitDeck needs

| Requirement | Notes |
|---|---|
| **Python ≥ 3.8** | 3.10+ recommended. CPython from python.org or your distro. |
| **Tkinter** | The GUI toolkit. Ships with the python.org installers (Windows/macOS); a **separate package** on most Linux distros (`python3-tk` / `python3-tkinter`). |
| `matplotlib`, `numpy`, `certifi` | The only **required** Python packages; installed automatically by `pip`. |

OrbitDeck ships its **own pure-Python SGP4 propagator** and a **bundled
coastline set**, so it runs with nothing but the three required packages.

### Optional extras

| Extra | Command | Adds |
|---|---|---|
| `accurate` | `pip install "orbitdeck[accurate]"` | `sgp4` — C-accelerated full SGP4/SDP4 (sharper for deep-space / GEO) |
| `maps` | `pip install "orbitdeck[maps]"` | `cartopy` — full-resolution Natural Earth coastlines (needs GEOS/PROJ system libraries) |
| `excel` | `pip install "orbitdeck[excel]"` | `openpyxl` — native `.xlsx` export (otherwise CSV) |
| `full` | `pip install "orbitdeck[full]"` | all of the above |

Without any extra, OrbitDeck still runs: bundled SGP4, bundled coastlines, and
CSV instead of `.xlsx`.

---

## Windows

### 1. Install Python

Download the latest **Python 3** installer from
<https://www.python.org/downloads/windows/> and run it. On the first screen:

- ✅ tick **"Add python.exe to PATH"**
- Keep **"tcl/tk and IDLE"** ticked (this is Tkinter — it is on by default)

Verify in a new PowerShell / Command Prompt:

```powershell
python --version
python -m tkinter      # a tiny test window should appear
```

> Prefer the **python.org** build over the Microsoft Store build — the Store
> build sandboxes the filesystem and occasionally ships without a working Tk.

### 2. Run from source

```powershell
git clone https://github.com/prstoetzer/OrbitDeck
cd OrbitDeck
python -m venv .venv
.venv\Scripts\activate
pip install -e .
orbitdeck
```

Or without installing the entry point: `python run.py`.

For all the optional features: `pip install -e ".[full]"` (cartopy on Windows
installs cleanly from wheels — no system libraries needed).

### 3. Build a standalone `.exe`

```powershell
pip install pyinstaller
pip install -e ".[full]"        # always build with ALL optional dependencies
pyinstaller orbitdeck.spec
```

The app appears at `dist\OrbitDeck\OrbitDeck.exe`. Zip the `dist\OrbitDeck\`
folder to distribute it. See [`packaging/BUILD.md`](../packaging/BUILD.md) for
icons and code-signing.

---

## macOS

### 1. Install Python

**Option A — python.org (recommended for building):** download the macOS
installer from <https://www.python.org/downloads/macos/>. It includes Tkinter
and the **Install Certificates.command** (run it once from
`/Applications/Python 3.x/` so HTTPS fetches work).

**Option B — Homebrew:**

```bash
brew install python-tk            # python3 + the matching Tk
```

Verify:

```bash
python3 --version
python3 -m tkinter                # test window
```

### 2. Run from source

```bash
git clone https://github.com/prstoetzer/OrbitDeck
cd OrbitDeck
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
orbitdeck
```

Optional extras: `pip install -e ".[full]"`. cartopy via pip may need
GEOS/PROJ — `brew install geos proj` first, or skip `maps` and use the bundled
coastlines.

### 3. Build a standalone `.app`

```bash
pip install pyinstaller
pip install -e ".[full]"
pyinstaller orbitdeck.spec
open dist/OrbitDeck.app
```

For a Retina-quality icon, generate `icon.icns` first (see
[`packaging/BUILD.md`](../packaging/BUILD.md)). Gatekeeper will warn about an
unsigned app; right-click → **Open** the first time, or sign + notarize for
distribution.

---

## Debian / Ubuntu

Covers Debian 11+/12+ and Ubuntu 20.04+/22.04+/24.04+.

### 1. Install Python + Tkinter

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-tk
```

### 2. Run from source

```bash
git clone https://github.com/prstoetzer/OrbitDeck
cd OrbitDeck
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
orbitdeck
```

For the optional **cartopy** extra you need the GEOS/PROJ headers:

```bash
sudo apt install libgeos-dev libproj-dev proj-data proj-bin
pip install -e ".[full]"
```

(If cartopy is fiddly, skip it — the bundled coastlines are used automatically.)

### 3. Build a standalone binary

```bash
pip install pyinstaller
pip install -e ".[full]"
pyinstaller orbitdeck.spec
./dist/OrbitDeck/OrbitDeck
```

To build a real `.deb`, see the [packaging guide](../packaging/PACKAGING.md).

---

## Fedora

Covers Fedora 38+ (and recent RHEL/Rocky/Alma with EPEL).

### 1. Install Python + Tkinter

```bash
sudo dnf install python3 python3-pip python3-tkinter
```

### 2. Run from source

```bash
git clone https://github.com/prstoetzer/OrbitDeck
cd OrbitDeck
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
orbitdeck
```

Optional cartopy extra:

```bash
sudo dnf install geos-devel proj-devel
pip install -e ".[full]"
```

### 3. Build a standalone binary

```bash
pip install pyinstaller
pip install -e ".[full]"
pyinstaller orbitdeck.spec
./dist/OrbitDeck/OrbitDeck
```

To build an `.rpm`, see the [packaging guide](../packaging/PACKAGING.md).

---

## Arch Linux

### 1. Install Python + Tkinter

```bash
sudo pacman -S python tk
```

(`tk` provides Tkinter on Arch; it is not bundled with the `python` package.)

### 2. Run from source

```bash
git clone https://github.com/prstoetzer/OrbitDeck
cd OrbitDeck
python -m venv .venv
source .venv/bin/activate
pip install -e .
orbitdeck
```

Optional cartopy extra:

```bash
sudo pacman -S geos proj
pip install -e ".[full]"
```

> On Arch, system Python is "externally managed" (PEP 668). Use a **virtual
> environment** as above; don't `pip install` into the system Python.

### 3. Build / package

For a standalone bundle: `pip install -e ".[full]" && pip install pyinstaller && pyinstaller orbitdeck.spec`
(always build with the full extras so the bundle ships sgp4 + cartopy +
openpyxl). For a real Arch package, a ready-to-use **`PKGBUILD`** is provided —
see the [packaging guide](../packaging/PACKAGING.md).

---

## Raspberry Pi OS

Raspberry Pi OS (Bullseye/Bookworm, 32- or 64-bit) is Debian-based, so the
Debian steps apply, with a couple of Pi-specific notes.

### 1. Install Python + Tkinter

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-tk
```

### 2. Run from source

```bash
git clone https://github.com/prstoetzer/OrbitDeck
cd OrbitDeck
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
orbitdeck
```

Pi notes:

- **Use piwheels.** Raspberry Pi OS is preconfigured to fetch ARM wheels from
  <https://www.piwheels.org>, so `numpy`/`matplotlib` install without a long
  compile. If you removed it, add piwheels back to `/etc/pip.conf`.
- **cartopy on ARM** is heavy to build; prefer the bundled coastlines (skip the
  `maps` extra). If you do want it: `sudo apt install libgeos-dev libproj-dev`.
- A **Pi 4 / Pi 5** runs the full UI comfortably; on a Pi 3 the 3-D globe and
  large rasters are slower but usable.
- Run under the **desktop** (X/Wayland) session — OrbitDeck is a GUI app and
  needs a display.

### 3. Build a standalone binary

PyInstaller works on the Pi and produces an **ARM** binary (runs on Pi only, not
x86):

```bash
pip install -e ".[full]"        # always build with all optional dependencies
pip install pyinstaller
pyinstaller orbitdeck.spec
./dist/OrbitDeck/OrbitDeck
```

> On ARM, the `cartopy` part of `[full]` needs the GEOS/PROJ dev packages
> (`sudo apt install libgeos-dev libproj-dev`) and can take a while to build. If
> you only need a quick bundle, `pip install -e ".[accurate,excel]"` ships the
> propagator and `.xlsx` extras and falls back to the bundled coastlines.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'tkinter'` | Install the Tk package: `python3-tk` (Debian/Ubuntu/Pi), `python3-tkinter` (Fedora), `tk` (Arch). On Windows/macOS re-run the python.org installer with Tcl/Tk ticked. |
| `_tkinter` import error on macOS Homebrew | Install `python-tk` (the Tk-matched formula), not just `python`. |
| `CERTIFICATE_VERIFY_FAILED` when fetching GP/space-wx | `pip install certifi`; on macOS python.org, run **Install Certificates.command**. Frozen builds bundle certifi automatically. |
| `error: externally-managed-environment` (Arch/Debian 12) | Use a virtual environment (`python -m venv .venv`), don't install into system Python. |
| cartopy fails to build | Install GEOS/PROJ dev packages (see your distro above), or simply skip the `maps` extra — bundled coastlines are used. |
| Blank/!no window on a headless box | OrbitDeck needs a display. Use a desktop session, or `xvfb-run` for screenshots/CI only. |
