"""orbitterm/ui.py - small curses toolkit shared by all OrbitTerm screens.

Provides colour-pair setup, safe drawing helpers that never raise at the screen
edge, a Screen base class, and a reusable scrolling-list mixin. Pure stdlib.
"""

import curses

# colour pair ids
CLR_DEFAULT = 0
CLR_TITLE = 1
CLR_NAV = 2
CLR_NAV_SEL = 3
CLR_HEADER = 4
CLR_OK = 5
CLR_WARN = 6
CLR_BAD = 7
CLR_DIM = 8
CLR_ACCENT = 9
CLR_STATUS = 10
CLR_ROW_SEL = 11
CLR_VIS = 12


def init_colors():
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except Exception:
        bg = curses.COLOR_BLACK
    curses.init_pair(CLR_TITLE, curses.COLOR_CYAN, bg)
    curses.init_pair(CLR_NAV, curses.COLOR_WHITE, bg)
    curses.init_pair(CLR_NAV_SEL, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(CLR_HEADER, curses.COLOR_YELLOW, bg)
    curses.init_pair(CLR_OK, curses.COLOR_GREEN, bg)
    curses.init_pair(CLR_WARN, curses.COLOR_YELLOW, bg)
    curses.init_pair(CLR_BAD, curses.COLOR_RED, bg)
    curses.init_pair(CLR_DIM, curses.COLOR_BLUE, bg)
    curses.init_pair(CLR_ACCENT, curses.COLOR_MAGENTA, bg)
    curses.init_pair(CLR_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(CLR_ROW_SEL, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(CLR_VIS, curses.COLOR_BLACK, curses.COLOR_GREEN)


def cp(pair):
    if not curses.has_colors():
        return 0
    return curses.color_pair(pair)


def addstr(win, y, x, text, attr=0):
    """Draw text clipped to the window; never raise at the bottom-right cell."""
    if y < 0 or x < 0:
        return
    h, w = win.getmaxyx()
    if y >= h or x >= w:
        return
    text = str(text)
    avail = w - x
    if avail <= 0:
        return
    s = text[:avail]
    try:
        win.addstr(y, x, s, attr)
    except curses.error:
        # the very last cell of the window raises even on a valid write
        try:
            win.addstr(y, x, s[:-1], attr)
        except curses.error:
            pass


def hline(win, y, x, w, ch="\u2500", attr=0):
    addstr(win, y, x, ch * max(0, w), attr)


def clip(text, width):
    text = str(text)
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[:width - 1] + "\u2026"


def ljust(text, width):
    return clip(text, width).ljust(width)


def rjust(text, width):
    return clip(text, width).rjust(width)


def center(text, width):
    return clip(text, width).center(width)


class Screen:
    """Base class for a content screen. Subclasses implement draw() and may
    implement handle_key(); refreshes happen on a timer in the app loop."""

    title = "Screen"
    #: refresh cadence in seconds for live screens (0 = only on key/resize)
    refresh_secs = 0.0

    def __init__(self, app):
        self.app = app
        self.state = app.state

    def on_enter(self):
        """Called each time this screen becomes active."""

    def draw(self, win, y0, x0, h, w):
        raise NotImplementedError

    def handle_key(self, ch):
        """Return True if the key was consumed."""
        return False

    def help_keys(self):
        """Return a list of (key, label) shown in the footer hint."""
        return []


class ScrollList:
    """Reusable vertical-scroll selection state for list screens."""

    def __init__(self):
        self.sel = 0
        self.top = 0

    def clamp(self, n, page):
        if n <= 0:
            self.sel = 0
            self.top = 0
            return
        self.sel = max(0, min(self.sel, n - 1))
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + page:
            self.top = self.sel - page + 1
        self.top = max(0, min(self.top, max(0, n - page)))

    def move(self, delta, n, page):
        self.sel += delta
        self.clamp(n, page)

    def page_move(self, direction, n, page):
        self.sel += direction * page
        self.clamp(n, page)

    def home(self, n, page):
        self.sel = 0
        self.clamp(n, page)

    def end(self, n, page):
        self.sel = n - 1
        self.clamp(n, page)
