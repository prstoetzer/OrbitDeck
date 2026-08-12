"""references.py - static reference tables for OrbitTerm.

Browses the same tables the desktop References screen shows (CTCSS/PL tones,
Q-codes, CQ and ITU zones, ASCII), from ``orbitdeck.engine.refdata``.

Keys: left/right (or [ / ]) change table, up/down scroll.
"""

import curses

from ..ui import Screen, ScrollList, addstr, cp, clip
from ..ui import CLR_HEADER, CLR_DIM, CLR_ROW_SEL
from orbitdeck.engine import refdata as RD


class ReferencesScreen(Screen):
    title = "References"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.tbl = 0
        self.list = ScrollList()

    def _rows(self):
        return RD.TABLES[self.tbl][2]()

    def draw(self, win, y0, x0, h, w):
        name, desc, _fn = RD.TABLES[self.tbl]
        # Chooser: with 14 tables a horizontal strip does not fit 80 columns -
        # it ran off the edge and the truncated tail overlapped the next label,
        # which is what made this unreadable. Show the current table with its
        # position instead, and let left/right move through them.
        addstr(win, y0, x0, clip("%s  (%d/%d)  \u25c0 \u25b6 to change" % (
            name, self.tbl + 1, len(RD.TABLES)), w),
            cp(CLR_ROW_SEL))
        addstr(win, y0 + 1, x0, clip(desc, w), cp(CLR_DIM))

        rows = self._rows()
        page = max(1, h - 4)
        self.list.clamp(len(rows), page)
        headers = {
            "CTCSS tones": ("#", "Tone", "Group"),
            "Q-codes": ("Code", "", "Meaning"),
            "CQ zones": ("Zones", "Region", ""),
            "ITU zones": ("Zones", "Region", ""),
            "ASCII table": ("Dec", "Char", "Hex"),
        }.get(name, ("", "", ""))
        # Column widths scale with the pane: fixed 8/16 truncated the value
        # column on narrow terminals, which is what made entries unreadable.
        c1 = 10
        c2 = max(12, min(26, (w - c1) // 2))
        addstr(win, y0 + 3, x0, clip("%-*s %-*s %s" % (
            c1, headers[0], c2, headers[1], headers[2]), w), cp(CLR_HEADER))
        for i in range(page - 1):
            idx = self.list.top + i
            if idx >= len(rows):
                break
            a, b, c = rows[idx]
            y = y0 + 4 + i
            attr = cp(CLR_ROW_SEL) if idx == self.list.sel else 0
            addstr(win, y, x0, clip("%-*s %-*s %s" % (
                c1, clip(str(a), c1), c2, clip(str(b), c2), c), w), attr)
        if len(rows) > page:
            addstr(win, y0, x0 + w - 12,
                   "%d/%d" % (self.list.sel + 1, len(rows)), cp(CLR_DIM))

    def handle_key(self, ch):
        rows = self._rows()
        page = 10
        if ch in (curses.KEY_DOWN, ord("j")):
            self.list.move(1, len(rows), page)
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.list.move(-1, len(rows), page)
            return True
        if ch in (curses.KEY_NPAGE,):
            self.list.page_move(1, len(rows), page)
            return True
        if ch in (curses.KEY_PPAGE,):
            self.list.page_move(-1, len(rows), page)
            return True
        if ch in (ord("]"), curses.KEY_RIGHT):
            self.tbl = (self.tbl + 1) % len(RD.TABLES)
            self.list = ScrollList()
            return True
        if ch in (ord("["), curses.KEY_LEFT):
            self.tbl = (self.tbl - 1) % len(RD.TABLES)
            self.list = ScrollList()
            return True
        return False

    def help_keys(self):
        return [("up/dn", "scroll"), ("left/right", "table")]
