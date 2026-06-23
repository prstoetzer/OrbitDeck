# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for OrbitDeck.

Build (run on the OS you want to target -- PyInstaller does NOT cross-compile):

    pip install -e ".[full]"     # OrbitDeck + ALL optional deps (sgp4, cartopy, openpyxl)
    pip install pyinstaller
    pyinstaller orbitdeck.spec

A standalone bundle should always be built with the [full] extras so the shipped
app includes the C-accelerated propagator, high-resolution coastlines, and native
xlsx export.
Output goes to dist/OrbitDeck/ (a one-folder bundle) or dist/OrbitDeck(.exe)
for the one-file variant. See packaging/BUILD.md for details and per-platform
notes (icons, code signing, installers).
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_all

block_cipher = None

# Bundle the app's image assets (icon, etc.) so they're found at runtime.
asset_datas = [
    ("orbitdeck/gui/assets/icon.png", "orbitdeck/gui/assets"),
    ("orbitdeck/gui/assets/icon-256.png", "orbitdeck/gui/assets"),
    ("orbitdeck/gui/assets/icon-128.png", "orbitdeck/gui/assets"),
    ("orbitdeck/gui/assets/icon.ico", "orbitdeck/gui/assets"),
    ("orbitdeck/gui/assets/icon.svg", "orbitdeck/gui/assets"),
]

# matplotlib ships data files (fonts, mpl-data) AND compiled C extensions
# (ft2font, _path, ...) whose bundled DLLs -- FreeType on Windows -- must travel
# with the app. collect_data_files() gathers only the data, which on Windows
# leaves ft2font unable to find its DLL at runtime ("DLL load failed while
# importing ft2font"). collect_all() also pulls the binaries and hidden imports,
# which is what makes the frozen app import matplotlib cleanly on Windows.
mpl_datas, mpl_binaries, mpl_hiddenimports = collect_all("matplotlib")


def _vendored_dll_dir(pkg):
    """On Windows, wheels built with delvewheel vendor their native DLLs (e.g.
    FreeType for matplotlib, OpenBLAS for numpy) into a sibling '<pkg>.libs'
    directory next to the package. PyInstaller's import graph picks up the .pyd
    extension modules but can miss this sibling DLL dir, which is what causes the
    'DLL load failed while importing ft2font' crash. Collect those DLLs
    explicitly as binaries placed in '<pkg>.libs' so the extensions find them.
    Returns a (src, dest) list (empty off Windows / when the dir is absent)."""
    out = []
    try:
        import importlib
        mod = importlib.import_module(pkg)
        base = os.path.dirname(os.path.dirname(os.path.abspath(mod.__file__)))
        libs = os.path.join(base, pkg + ".libs")
        if os.path.isdir(libs):
            for name in os.listdir(libs):
                if name.lower().endswith(".dll"):
                    out.append((os.path.join(libs, name), pkg + ".libs"))
    except Exception:
        pass
    return out


# Windows vendored-DLL directories for the native-extension packages.
vendored_binaries = (_vendored_dll_dir("matplotlib")
                     + _vendored_dll_dir("numpy")
                     + _vendored_dll_dir("PIL"))

# certifi's CA bundle -- required so HTTPS (AMSAT / SatNOGS / NOAA) verifies in
# the frozen app. Without this, macOS bundles fail with CERTIFICATE_VERIFY_FAILED.
certifi_datas = collect_data_files("certifi")

# cartopy ships Natural Earth shapefiles / data used for the OSCARLOCATOR base
# map coastlines, plus compiled extensions that link GEOS/PROJ; collect_all gets
# the data, the binaries, and the hidden imports together. Falls back to
# OrbitDeck's own bundled coastlines if cartopy isn't installed.
try:
    cartopy_datas, cartopy_binaries, cartopy_hiddenimports = collect_all("cartopy")
except Exception:
    cartopy_datas, cartopy_binaries, cartopy_hiddenimports = [], [], []


def _trim_datas(datas):
    """Drop large data files that collect_all() grabs but OrbitDeck never uses.

    This matters most on Windows, where the dependencies come from conda-forge
    and bundle a much fuller native/data payload than the pip wheels used on
    Linux/macOS. The biggest avoidable chunk is the PROJ datum-shift grid set
    (share/proj/*): OrbitDeck only ever needs ``proj.db`` for basic projections,
    not the optional high-accuracy transformation grids, which can be 100+ MB.
    Also drop matplotlib/cartopy sample and test data. Pure filtering -- it never
    removes a code module, only inert data files, so it can't break imports.
    """
    import os

    def drop(dest):
        d = dest.replace("\\", "/").lower()
        base = os.path.basename(d)
        # PROJ grids: keep proj.db (+ its ini), drop everything else under proj/
        if "/proj/" in d or d.startswith("proj/") or "share/proj" in d:
            return base not in ("proj.db", "proj.ini")
        # matplotlib bundled sample images and the test suite's baseline images
        if "mpl-data/sample_data/" in d:
            return True
        if "/tests/" in d and ("matplotlib" in d or "cartopy" in d):
            return True
        # cartopy ships no offline feature data by default (it downloads Natural
        # Earth on demand); any *_test / gallery data is unused here
        if "cartopy" in d and ("/data/tests" in d or "/tests/" in d):
            return True
        return False

    kept = [(src, dest, typ) for (src, dest, typ) in datas if not drop(dest)]
    return kept

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
    binaries=mpl_binaries + cartopy_binaries + vendored_binaries,
    datas=_trim_datas(asset_datas + mpl_datas + certifi_datas + cartopy_datas),
    hiddenimports=[
        # ssl / certificate handling for HTTPS data fetches:
        "certifi", "ssl",
        # full SDP4 deep-space propagation (GEO/HEO birds like QO-100):
        "sgp4", "sgp4.api", "sgp4.propagation",
        # tkinter + ttk are usually auto-detected, but be explicit:
        "tkinter", "tkinter.ttk", "tkinter.messagebox",
        "tkinter.simpledialog", "tkinter.filedialog",
        # matplotlib's Tk backend:
        "matplotlib.backends.backend_tkagg",
        # matplotlib's PDF backend (OSCARLOCATOR sheet export):
        "matplotlib.backends.backend_pdf",
    ] + mpl_hiddenimports + cartopy_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # trim things OrbitDeck never uses to keep the bundle small. This helps
        # the Windows build most: its deps come from conda-forge, which pulls a
        # heavier scientific stack than the pip wheels used on Linux/macOS.
        "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
        "pytest", "IPython", "notebook",
        # scipy + pandas are not imported by OrbitDeck and are only *optional* for
        # cartopy (image warping / faster kd-tree); excluding them removes a large
        # payload (scipy alone bundles its own BLAS, ~100 MB on Windows). If a
        # future cartopy feature needs them, drop the relevant name from here.
        "scipy", "pandas",
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
    upx=False,                # UPX can corrupt compressed DLLs (numpy,
    console=False,            # matplotlib/FreeType, PROJ) -> runtime crashes
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
    upx=False,
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
            "CFBundleShortVersionString": "0.36.5",
        },
    )
