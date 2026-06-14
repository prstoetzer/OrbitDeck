"""
net.py - a single HTTP GET helper with a robust TLS setup.

Frozen builds (PyInstaller, especially on macOS) frequently fail HTTPS requests
with CERTIFICATE_VERIFY_FAILED because Python's default certificate location
isn't present in the bundle. We build an explicit SSL context from certifi's CA
bundle when it's available (it bundles cleanly into PyInstaller), and fall back
to the platform default otherwise. All of OrbitDeck's network calls go through
http_get() so the fix lives in one place.
"""

import ssl
import urllib.request

USER_AGENT = "OrbitDeck/1.0"

_CTX = None


def _build_context():
    # 1) Prefer certifi's CA bundle -- reliable inside a frozen app.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    # 2) Fall back to the platform's default verification.
    try:
        return ssl.create_default_context()
    except Exception:
        return None


def _context():
    global _CTX
    if _CTX is None:
        _CTX = _build_context()
    return _CTX


def http_get(url, timeout=20):
    """Fetch a URL and return its decoded text body. Verifies TLS using the
    certifi CA bundle when available."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = _context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read().decode("utf-8", "replace")
