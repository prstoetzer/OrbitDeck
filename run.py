#!/usr/bin/env python3
"""
run.py - launch OrbitDeck.

    python3 run.py

Requires Python 3.8+ with tkinter (bundled with standard CPython installers)
and matplotlib + numpy. See README for setup.
"""

import sys


def _fatal(msg):
    """Report a fatal startup error and exit. In a windowed (no-console) frozen
    build sys.stderr is None, so writing to it would itself crash with
    "'NoneType' object has no attribute 'write'" -- masking the real error. Write
    to stderr when there is one, and also try a Tk message box so a packaged app
    shows something legible instead of silently dying."""
    if sys.stderr is not None:
        try:
            sys.stderr.write(msg)
        except Exception:
            pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("OrbitDeck \u2014 startup error", msg)
        root.destroy()
    except Exception:
        pass
    sys.exit(1)


def _ensure_ca_certs():
    """Point the process at certifi's CA bundle so HTTPS works in frozen builds.

    PyInstaller bundles on macOS commonly fail HTTPS with
    CERTIFICATE_VERIFY_FAILED because the default certificate path isn't present.
    Setting SSL_CERT_FILE / SSL_CERT_DIR before any network use fixes it for the
    whole process (urllib, ssl, etc.)."""
    import os
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
        ca = certifi.where()
        if os.path.exists(ca):
            os.environ["SSL_CERT_FILE"] = ca
            os.environ.setdefault("REQUESTS_CA_BUNDLE", ca)
    except Exception:
        pass


def main():
    _ensure_ca_certs()
    try:
        import tkinter  # noqa: F401
    except Exception:
        _fatal(
            "ERROR: tkinter is not available in this Python.\n"
            "  * Windows/macOS: use the python.org installer (tkinter is "
            "included).\n"
            "  * Debian/Ubuntu: sudo apt install python3-tk\n"
            "  * Fedora: sudo dnf install python3-tkinter\n")
    try:
        import matplotlib  # noqa: F401
        import numpy  # noqa: F401
    except Exception as exc:
        _fatal("ERROR: matplotlib and numpy are required, but matplotlib "
               "failed to import:\n  %s\n\nIf this is a packaged build, a "
               "native library may be missing from the bundle.\n" % exc)
    from orbitdeck.gui.app import main as app_main
    app_main()


if __name__ == "__main__":
    main()
