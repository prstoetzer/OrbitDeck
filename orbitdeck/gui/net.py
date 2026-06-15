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
import urllib.error
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
    certifi CA bundle when available.

    Raises a clear, actionable error on the HTTP statuses CelesTrak documents
    (https://celestrak.org/NORAD/documentation/gp-data-formats.php):
      * 403 - rate-limited / firewalled. CelesTrak blocks IPs that fetch more
              often than the data updates (every ~2 hours). The caller should
              NOT retry automatically; wait and reuse cached data.
      * 404 - the query is wrong (e.g. an unknown GROUP); retrying won't help.
      * 301 - moved (e.g. using the .com domain). OrbitDeck uses the .org
              domain, so this shouldn't occur, but is reported if it does.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = _context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        code = e.code
        if code == 403:
            raise RuntimeError(
                "Server returned HTTP 403 (rate-limited or blocked). CelesTrak "
                "blocks repeated downloads; data updates only every ~2 hours, "
                "so wait a while and reuse cached data rather than retrying.")
        if code == 404:
            raise RuntimeError(
                "Server returned HTTP 404 (not found). Check the group name or "
                "URL \u2014 retrying the same request will not help.")
        if code in (301, 302, 307, 308):
            raise RuntimeError(
                "Server returned HTTP %d (redirect). Use the canonical URL "
                "(CelesTrak's .org domain)." % code)
        raise RuntimeError("Server returned HTTP %d." % code)
