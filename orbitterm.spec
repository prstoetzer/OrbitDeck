# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a standalone **OrbitTerm** executable.

OrbitTerm is the curses front-end. It is built separately from the desktop app
because it needs almost none of what that bundle carries: verified at build time
that importing every one of its screens pulls in **no** matplotlib, tkinter,
numpy, cartopy or openpyxl. Bundling it with the GUI would ship a ~200 MB
download to run a terminal program.

That is also why this is a **one-file, console** build. A terminal application
that arrives as a folder of shared objects is awkward to drop onto a headless
box, which is the whole point of OrbitTerm: `scp` one file to a Raspberry Pi or
a VPS and run it.

Windows note: the Windows console does not support curses out of the box, so the
Windows build depends on `windows-curses`. The workflow installs it for that
platform only.
"""

import os
import sys

block_cipher = None

# The vendored SGP4 fallback, if present, so the executable still propagates
# when the compiled sgp4 wheel is unavailable on the target platform.
vendored_binaries = []
_vendor = os.path.join("orbitdeck", "engine", "_vendor")
if os.path.isdir(_vendor):
    for name in os.listdir(_vendor):
        if name.endswith((".so", ".pyd", ".dll", ".dylib")):
            vendored_binaries.append((os.path.join(_vendor, name),
                                      os.path.join("orbitdeck", "engine",
                                                   "_vendor")))

# Bundled data the engine reads at runtime (DXCC roster, sample catalog, ...).
datas = []
for pkg_dir in (os.path.join("orbitdeck", "data"),):
    if os.path.isdir(pkg_dir):
        for name in os.listdir(pkg_dir):
            if name.endswith((".json", ".csv", ".txt")):
                datas.append((os.path.join(pkg_dir, name), pkg_dir))

hidden = [
    # HTTPS fetches (CelesTrak, AMSAT, Space-Track, hams.at, NOAA):
    "certifi", "ssl",
    # full SDP4 deep-space propagation (GEO/HEO birds like QO-100):
    "sgp4", "sgp4.api", "sgp4.propagation",
    # curses is stdlib on POSIX; on Windows it comes from windows-curses:
    "curses", "curses.ascii",
]
if sys.platform == "win32":
    hidden.append("_curses")

a = Analysis(
    ["runterm.py"],
    pathex=[],
    binaries=vendored_binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # OrbitTerm imports none of these - verified by importing every screen
        # and checking sys.modules. Excluding them is what keeps this build a
        # few MB rather than a few hundred.
        "matplotlib", "numpy", "cartopy", "shapely", "pyproj",
        "tkinter", "tkinter.ttk", "PIL", "openpyxl",
        "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
        "pytest", "IPython", "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# One-file, console: a terminal app should be a single file you can scp to a
# headless box and run.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="OrbitTerm",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX can corrupt compressed extension modules
    runtime_tmpdir=None,
    console=True,            # it IS a console program
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
