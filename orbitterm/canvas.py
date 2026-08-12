"""orbitterm/canvas.py - a braille sub-cell drawing canvas for the TUI.

OrbitTerm already runs on ncurses (Python's ``curses`` is an ncurses binding, and
we link the wide-character ``libncursesw`` build). The lever that actually raises
graphical quality in a terminal is not a different library but **sub-cell
rendering**: the Unicode braille block at U+2800 encodes 2x4 independently
settable dots per character cell, so a 80x24 terminal becomes a 160x96 pixel
surface - 8x the addressable points - while staying pure text.

    dot bit layout in a cell        bit values
        (0,0) (1,0)                  0x01 0x08
        (0,1) (1,1)                  0x02 0x10
        (0,2) (1,2)                  0x04 0x20
        (0,3) (1,3)                  0x40 0x80

Set dots with ``plot``/``line``, then ``blit`` the result into a curses window.
Colour is per character cell (a terminal limitation, not a braille one), so a
cell takes the colour of the last coloured dot written into it.

Terminals without a braille-capable font degrade to mojibake rather than
crashing, so ``Canvas.ascii_fallback`` renders the same buffer with '#'/'.' if
the caller prefers safety over resolution.
"""

BRAILLE_BASE = 0x2800
_DOT_BITS = ((0x01, 0x02, 0x04, 0x40),      # column 0, rows 0..3
             (0x08, 0x10, 0x20, 0x80))      # column 1, rows 0..3


class Canvas:
    """A braille pixel surface ``cols`` x ``rows`` character cells in size."""

    def __init__(self, cols, rows):
        self.cols = max(1, int(cols))
        self.rows = max(1, int(rows))
        self.width = self.cols * 2          # addressable dots
        self.height = self.rows * 4
        self._cells = {}                    # (cx, cy) -> bitmask
        self._colour = {}                   # (cx, cy) -> colour pair

    # ---- drawing ----
    def plot(self, x, y, colour=None):
        """Set the dot at pixel (x, y). Origin is top-left."""
        x, y = int(x), int(y)
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        cx, cy = x // 2, y // 4
        bit = _DOT_BITS[x % 2][y % 4]
        key = (cx, cy)
        self._cells[key] = self._cells.get(key, 0) | bit
        if colour is not None:
            self._colour[key] = colour
        return True

    def line(self, x0, y0, x1, y1, colour=None):
        """Bresenham line between two pixel coordinates."""
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.plot(x0, y0, colour)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def rect(self, x0, y0, x1, y1, colour=None):
        self.line(x0, y0, x1, y0, colour)
        self.line(x1, y0, x1, y1, colour)
        self.line(x1, y1, x0, y1, colour)
        self.line(x0, y1, x0, y0, colour)

    def circle(self, cx, cy, r, colour=None):
        """Midpoint circle - used for the sky disk and the globe limb."""
        x, y, err = int(r), 0, 1 - int(r)
        while x >= y:
            for px, py in ((x, y), (y, x), (-x, y), (-y, x),
                           (-x, -y), (-y, -x), (x, -y), (y, -x)):
                self.plot(cx + px, cy + py, colour)
            y += 1
            if err < 0:
                err += 2 * y + 1
            else:
                x -= 1
                err += 2 * (y - x) + 1

    def fill_column(self, x, y0, y1, colour=None):
        """A vertical run - the building block for bar charts."""
        if y1 < y0:
            y0, y1 = y1, y0
        for y in range(int(y0), int(y1) + 1):
            self.plot(x, y, colour)

    def clear(self):
        self._cells.clear()
        self._colour.clear()

    # ---- output ----
    def cell_char(self, cx, cy):
        bits = self._cells.get((cx, cy), 0)
        return chr(BRAILLE_BASE + bits) if bits else " "

    def rows_out(self):
        """Yield (row_index, text, [(col, colour), ...]) for each canvas row."""
        for cy in range(self.rows):
            text = "".join(self.cell_char(cx, cy) for cx in range(self.cols))
            colours = [(cx, self._colour[(cx, cy)])
                       for cx in range(self.cols) if (cx, cy) in self._colour]
            yield cy, text, colours

    def ascii_fallback(self):
        """The same buffer as plain ASCII, for fonts without braille."""
        out = []
        for cy in range(self.rows):
            out.append("".join("#" if self._cells.get((cx, cy)) else " "
                               for cx in range(self.cols)))
        return out


def blit(win, canvas, y0, x0, default_attr=0, use_braille=True):
    """Draw a canvas into a curses window at (y0, x0).

    Each cell is written with its own colour where one was recorded. Writing is
    guarded: a terminal that refuses a glyph (no braille in the font, or the
    bottom-right corner) is skipped rather than raising.
    """
    if not use_braille:
        for i, line in enumerate(canvas.ascii_fallback()):
            try:
                win.addstr(y0 + i, x0, line, default_attr)
            except Exception:
                pass
        return
    for cy, text, colours in canvas.rows_out():
        cmap = dict(colours)
        for cx, ch in enumerate(text):
            if ch == " ":
                continue
            try:
                win.addstr(y0 + cy, x0 + cx, ch, cmap.get(cx, default_attr))
            except Exception:
                pass


def scale(value, vmin, vmax, out_min, out_max, invert=False):
    """Map ``value`` from a data range onto a pixel range."""
    if vmax == vmin:
        frac = 0.5
    else:
        frac = (value - vmin) / float(vmax - vmin)
    frac = max(0.0, min(1.0, frac))
    if invert:
        frac = 1.0 - frac
    return out_min + frac * (out_max - out_min)


# ---------------------------------------------------------------------------
# Half-block rendering, for filled areas
# ---------------------------------------------------------------------------
# Braille is line art. For a FILLED area - a heatmap, an eclipse raster, a bar -
# its 2x4 dots render as sparse specks and read washed out next to a solid
# block. The right tool there is the half-block set: U+2580 UPPER HALF BLOCK
# over a coloured background gives two independently coloured, fully filled
# half-cells, so a raster gets 2x the vertical resolution of full blocks while
# staying solid.
#
#   both halves lit, same colour  -> full block, that colour
#   top only                      -> upper half block, fg = top colour
#   bottom only                   -> upper half block, fg = bg colour, bg = ...
#                                    (we use LOWER HALF via reversed fg/bg)
#   neither                       -> space
UPPER_HALF = "\u2580"
LOWER_HALF = "\u2584"
FULL_BLOCK = "\u2588"


class HalfBlockCanvas:
    """A filled raster at 2x vertical resolution using half-block glyphs.

    ``set(x, y, colour)`` addresses rows at half-cell granularity. Rendering
    picks the glyph and attribute that fills the cell solidly.
    """

    def __init__(self, cols, rows):
        self.cols = max(1, int(cols))
        self.rows = max(1, int(rows))
        self.width = self.cols
        self.height = self.rows * 2
        self._px = {}                    # (x, y) -> colour attr

    def set(self, x, y, colour=0):
        x, y = int(x), int(y)
        if 0 <= x < self.width and 0 <= y < self.height:
            self._px[(x, y)] = colour
            return True
        return False

    def fill_column(self, x, y0, y1, colour=0):
        if y1 < y0:
            y0, y1 = y1, y0
        for y in range(int(y0), int(y1) + 1):
            self.set(x, y, colour)

    def clear(self):
        self._px.clear()

    def cell(self, cx, cy):
        """Return (char, attr) for one character cell, or (None, 0) if empty."""
        top = self._px.get((cx, cy * 2))
        bot = self._px.get((cx, cy * 2 + 1))
        if top is None and bot is None:
            return None, 0
        if top is not None and bot is not None:
            if top == bot:
                return FULL_BLOCK, top
            # two different colours: draw the top half in its colour over the
            # bottom's - curses can't set a per-cell background here, so prefer
            # the upper glyph and the top colour, which keeps boundaries crisp
            return UPPER_HALF, top
        if top is not None:
            return UPPER_HALF, top
        return LOWER_HALF, bot


def blit_half(win, canvas, y0, x0):
    """Draw a HalfBlockCanvas into a curses window."""
    for cy in range(canvas.rows):
        for cx in range(canvas.cols):
            ch, attr = canvas.cell(cx, cy)
            if ch is None:
                continue
            try:
                win.addstr(y0 + cy, x0 + cx, ch, attr)
            except Exception:
                pass
