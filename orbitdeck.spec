# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for OrbitDeck.

Build (run on the OS you want to target -- PyInstaller does NOT cross-compile):

    pip install pyinstaller
    pyinstaller orbitdeck.spec

Output goes to dist/OrbitDeck/ (a one-folder bundle) or dist/OrbitDeck(.exe)
for the one-file variant. See packaging/BUILD.md for details and per-platform
notes (icons, code signing, installers).
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Bundle the app's image assets (icon, etc.) so they're found at runtime.
asset_datas = [
    ("orbitdeck/gui/assets/icon.png", "orbitdeck/gui/assets"),
    ("orbitdeck/gui/assets/icon-256.png", "orbitdeck/gui/assets"),
    ("orbitdeck/gui/assets/icon-128.png", "orbitdeck/gui/assets"),
    ("orbitdeck/gui/assets/icon.ico", "orbitdeck/gui/assets"),
    ("orbitdeck/gui/assets/icon.svg", "orbitdeck/gui/assets"),
]

# matplotlib ships data files (fonts, mpl-data) that must travel with the app.
mpl_datas = collect_data_files("matplotlib")

# certifi's CA bundle -- required so HTTPS (AMSAT / SatNOGS / NOAA) verifies in
# the frozen app. Without this, macOS bundles fail with CERTIFICATE_VERIFY_FAILED.
certifi_datas = collect_data_files("certifi")

# Per-platform icon for the executable itself.
if sys.platform == "win32":
    exe_icon = "orbitdeck/gui/assets/icon.ico"
elif sys.platform == "darwin":
    exe_icon = "orbitdeck/gui/assets/icon.icns"   # see BUILD.md to generate
else:
    exe_icon = None

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=asset_datas + mpl_datas + certifi_datas,
    hiddenimports=[
        # ssl / certificate handling for HTTPS data fetches:
        "certifi", "ssl",
        # tkinter + ttk are usually auto-detected, but be explicit:
        "tkinter", "tkinter.ttk", "tkinter.messagebox",
        "tkinter.simpledialog", "tkinter.filedialog",
        # matplotlib's Tk backend:
        "matplotlib.backends.backend_tkagg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # trim things OrbitDeck never uses to keep the bundle small:
        "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
        "pytest", "IPython", "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OrbitDeck",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,            # GUI app: no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OrbitDeck",
)

# On macOS, also wrap the collected folder into a proper .app bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="OrbitDeck.app",
        icon="orbitdeck/gui/assets/icon.icns",
        bundle_identifier="org.orbitdeck.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "0.8.2",
        },
    )
