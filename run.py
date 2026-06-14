#!/usr/bin/env python3
"""
run.py - launch OrbitDeck.

    python3 run.py

Requires Python 3.8+ with tkinter (bundled with standard CPython installers)
and matplotlib + numpy. See README for setup.
"""

import sys


def main():
    try:
        import tkinter  # noqa: F401
    except Exception:
        sys.stderr.write(
            "ERROR: tkinter is not available in this Python.\n"
            "  * Windows/macOS: use the python.org installer (tkinter is "
            "included).\n"
            "  * Debian/Ubuntu: sudo apt install python3-tk\n"
            "  * Fedora: sudo dnf install python3-tkinter\n")
        sys.exit(1)
    try:
        import matplotlib  # noqa: F401
        import numpy  # noqa: F401
    except Exception:
        sys.stderr.write("ERROR: matplotlib and numpy are required.\n"
                         "  pip install matplotlib numpy\n")
        sys.exit(1)
    from orbitdeck.gui.app import main as app_main
    app_main()


if __name__ == "__main__":
    main()
