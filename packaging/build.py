#!/usr/bin/env python3
"""
build.py - convenience wrapper around PyInstaller for OrbitDeck.

Cleans previous build artifacts, runs PyInstaller against orbitdeck.spec, and
prints where the result landed. Run from the repo root:

    python packaging/build.py
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    os.chdir(ROOT)

    # ensure PyInstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Install it with:\n"
              "    pip install pyinstaller", file=sys.stderr)
        return 1

    # clean previous artifacts
    for d in ("build", "dist"):
        if os.path.isdir(d):
            print("removing %s/ ..." % d)
            shutil.rmtree(d, ignore_errors=True)

    print("running PyInstaller ...")
    rc = subprocess.call([sys.executable, "-m", "PyInstaller",
                          "--noconfirm", "orbitdeck.spec"])
    if rc != 0:
        print("PyInstaller failed (exit %d)." % rc, file=sys.stderr)
        return rc

    out = os.path.join(ROOT, "dist")
    print("\nBuild complete. Bundle is in: %s" % out)
    if sys.platform == "win32":
        print("Run: dist\\OrbitDeck\\OrbitDeck.exe")
    elif sys.platform == "darwin":
        print("Run: open dist/OrbitDeck.app")
    else:
        print("Run: ./dist/OrbitDeck/OrbitDeck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
