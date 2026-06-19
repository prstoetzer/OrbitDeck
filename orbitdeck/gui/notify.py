"""notify.py - best-effort native desktop notifications (toasts).

A single ``send(title, message)`` entry point that works without any third-party
dependency by shelling out to the platform's native mechanism:

* macOS   -> ``osascript`` (Notification Center)
* Linux   -> ``notify-send`` (libnotify), if present
* Windows -> PowerShell toast via the Windows.UI.Notifications API

Every path is wrapped so a missing tool simply results in no toast (the caller
still shows its in-app status line and audible cue). Notifications are fired on a
short-lived daemon thread so the UI never blocks.
"""

import os
import shutil
import subprocess
import sys
import threading


def _run(cmd, **kw):
    try:
        subprocess.run(cmd, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       **kw)
    except Exception:
        pass


def _mac(title, message):
    # escape double quotes for AppleScript
    t = title.replace('"', '\\"')
    m = message.replace('"', '\\"')
    script = 'display notification "%s" with title "%s"' % (m, t)
    _run(["osascript", "-e", script])


def _linux(title, message):
    if shutil.which("notify-send"):
        _run(["notify-send", "-a", "OrbitDeck", title, message])


def _windows(title, message):
    # Build a Windows toast via PowerShell + WinRT. Falls back silently if the
    # API isn't available (older Windows / locked-down hosts).
    t = title.replace("'", "''")
    m = message.replace("'", "''")
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, "
        "Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        "$x = [Windows.UI.Notifications.ToastNotificationManager]::"
        "GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        "$texts = $x.GetElementsByTagName('text');"
        "$texts.Item(0).AppendChild($x.CreateTextNode('%s')) > $null;"
        "$texts.Item(1).AppendChild($x.CreateTextNode('%s')) > $null;"
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($x);"
        "[Windows.UI.Notifications.ToastNotificationManager]::"
        "CreateToastNotifier('OrbitDeck').Show($toast);"
    ) % (t, m)
    _run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps])


def _dispatch(title, message):
    try:
        if sys.platform == "darwin":
            _mac(title, message)
        elif os.name == "nt":
            _windows(title, message)
        else:
            _linux(title, message)
    except Exception:
        pass


def send(title, message):
    """Fire a desktop notification without blocking the caller."""
    threading.Thread(target=_dispatch, args=(title, message),
                     daemon=True).start()


def available():
    """True if a native notifier appears to be usable on this platform."""
    if sys.platform == "darwin":
        return shutil.which("osascript") is not None
    if os.name == "nt":
        return shutil.which("powershell") is not None
    return shutil.which("notify-send") is not None
