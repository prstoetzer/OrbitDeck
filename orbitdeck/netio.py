"""orbitdeck.netio - HTTP helpers shared by every front-end.

These used to live in ``orbitdeck.gui.net`` / ``orbitdeck.gui.store``, which meant
OrbitTerm - a curses application that never touches Tk - had to import from a
package named ``gui`` to make a web request. That is the wrong dependency
direction and it made the failure modes confusing: a problem in the desktop
package could surface as a fetch error in the terminal app.

``orbitdeck.gui.net`` now re-exports from here, so existing callers keep working.
"""

import ssl
import urllib.error
import urllib.request

USER_AGENT = "OrbitDeck"
DEFAULT_TIMEOUT = 20


def _build_context():
    """A verifying TLS context that also works inside a frozen app.

    PyInstaller builds do not carry the platform CA store, so prefer certifi's
    bundle when it is available and fall back to the platform default. (Carried
    over from the original gui/net.py - dropping it would have broken TLS in the
    packaged builds.)
    """
    # 1) Prefer certifi's CA bundle - reliable inside a frozen app.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    # 2) Fall back to the platform's default verification.
    return ssl.create_default_context()


_CTX = None


def _context():
    global _CTX
    if _CTX is None:
        _CTX = _build_context()
    return _CTX


def _raise_for_status(code):
    """Turn an HTTP status into an actionable message.

    These are the statuses CelesTrak documents, and the wording matters: a 403
    means back off and reuse the cache rather than retry, and a 404 means the
    query itself is wrong so retrying cannot help.
    """
    if code == 403:
        raise RuntimeError(
            "Server returned HTTP 403 (rate-limited or blocked). CelesTrak "
            "blocks repeated downloads; data updates only every ~2 hours, so "
            "wait a while and reuse cached data rather than retrying.")
    if code == 404:
        raise RuntimeError(
            "Server returned HTTP 404 (not found). Check the group name or "
            "URL \u2014 retrying the same request will not help.")
    if code in (301, 302, 307, 308):
        raise RuntimeError(
            "Server returned HTTP %d (redirect). Use the canonical URL "
            "(CelesTrak's .org domain)." % code)
    raise RuntimeError("Server returned HTTP %d." % code)


def http_get(url, timeout=DEFAULT_TIMEOUT):
    """GET a URL and return the decoded body.

    Verifies TLS using certifi's bundle when available, and raises a clear,
    actionable error for the documented HTTP failure statuses.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=_context()) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        _raise_for_status(e.code)


def http_post_json(url, body, timeout=25):
    """POST a JSON body and return the decoded response."""
    data = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=_context()) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        _raise_for_status(e.code)


def http_post_form(url, fields, timeout=25):
    """POST an urlencoded form (Space-Track's login wants this)."""
    import urllib.parse
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=_context()) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        _raise_for_status(e.code)
