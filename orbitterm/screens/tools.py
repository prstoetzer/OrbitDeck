"""tools.py - the Tools hub for OrbitTerm.

The same 41 bench calculators the desktop app offers, driven from the shared
registry in ``orbitdeck.engine.tools_registry``. Left pane picks a tool, right
pane shows its inputs and live results; edit a field in place and the result
recomputes.

Keys: up/down pick a tool, TAB/right moves to the fields, e or ENTER edits the
selected field, [ / ] step a picker, r resets to defaults.
"""

import curses

from ..ui import Screen, ScrollList, addstr, cp, clip, hline
from ..ui import (CLR_TITLE, CLR_HEADER, CLR_DIM, CLR_OK, CLR_WARN,
                  CLR_ACCENT, CLR_ROW_SEL)
from orbitdeck.engine.tools_registry import TOOLS, CATEGORIES


def _flat_tools():
    """Flatten CATEGORIES into a display list of (kind, label, key) rows where
    kind is 'cat' (heading) or 'tool'."""
    rows = []
    for cat, keys in CATEGORIES:
        rows.append(("cat", cat, None))
        for k in keys:
            rows.append(("tool", TOOLS[k]["name"], k))
    return rows


def _wrap(text, width):
    """Split ``text`` to fit ``width``, breaking mid-token if it has to.

    Word wrapping alone is not enough here: a full-precision float is one
    unbroken 17-character token, and it is long precisely because the digits
    are the point - clipping it would throw away the answer.
    """
    width = max(1, int(width))
    out, line = [], ""
    for word in str(text).split(" "):
        while len(word) > width:
            if line:
                out.append(line)
                line = ""
            out.append(word[:width])
            word = word[width:]
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(line)
    return out or [""]


class ToolsScreen(Screen):
    title = "Tools"
    refresh_secs = 0.0

    def __init__(self, app):
        super().__init__(app)
        self.rows = _flat_tools()
        self.list = ScrollList()
        # start on the first actual tool, not the category heading
        self.list.sel = 1
        self.focus_fields = False
        self.field_sel = 0
        self.values = {}          # tool key -> list of current values
        self.editing = False
        self.editbuf = ""

    # ---- helpers ----
    def _cur_key(self):
        kind, _label, key = self.rows[self.list.sel]
        return key if kind == "tool" else None

    def _vals_for(self, key):
        if key not in self.values:
            vals = []
            for f in TOOLS[key]["fields"]:
                vals.append(f.get("default", 0) if "choices" in f
                            else f["default"])
            self.values[key] = vals
        return self.values[key]

    def _compute(self, key):
        spec = TOOLS[key]
        args = []
        for f, v in zip(spec["fields"], self._vals_for(key)):
            if "choices" in f:
                args.append(int(v))
            elif f.get("text"):
                args.append(str(v))
            else:
                try:
                    args.append(float(v))
                except (TypeError, ValueError):
                    args.append(f["default"])
        try:
            return spec["fn"](*args)
        except Exception as exc:              # never let a tool crash the TUI
            return [("error", str(exc)[:40], "")]

    # ---- drawing ----
    def draw(self, win, y0, x0, h, w):
        list_w = min(30, max(22, w // 3))
        self._draw_list(win, y0, x0, h, list_w)
        cx = x0 + list_w + 2
        for y in range(y0, y0 + h):
            addstr(win, y, x0 + list_w, "\u2502", cp(CLR_DIM))
        self._draw_tool(win, y0, cx, h, w - list_w - 3)

    def _draw_list(self, win, y0, x0, h, w):
        page = h
        self.list.clamp(len(self.rows), page)
        for i in range(page):
            idx = self.list.top + i
            if idx >= len(self.rows):
                break
            kind, label, _key = self.rows[idx]
            y = y0 + i
            if kind == "cat":
                addstr(win, y, x0, clip(label.upper(), w), cp(CLR_HEADER))
                continue
            sel = (idx == self.list.sel)
            attr = cp(CLR_ROW_SEL) if (sel and not self.focus_fields) else (
                cp(CLR_ACCENT) if sel else 0)
            addstr(win, y, x0, clip("  " + label, w), attr)

    def _draw_tool(self, win, y0, x0, h, w):
        key = self._cur_key()
        if key is None:
            addstr(win, y0, x0, "Select a tool.", cp(CLR_DIM))
            return
        spec = TOOLS[key]
        addstr(win, y0, x0, clip(spec["name"], w), cp(CLR_TITLE))
        desc = spec.get("desc", "")
        y = y0 + 1
        # wrap the description over up to 2 lines
        if desc:
            words, line = desc.split(), ""
            lines = []
            for word in words:
                if len(line) + len(word) + 1 > w:
                    lines.append(line)
                    line = word
                else:
                    line = (line + " " + word).strip()
            if line:
                lines.append(line)
            for ln in lines[:2]:
                addstr(win, y, x0, clip(ln, w), cp(CLR_DIM))
                y += 1
        y += 1

        vals = self._vals_for(key)
        for i, (f, v) in enumerate(zip(spec["fields"], vals)):
            sel = self.focus_fields and i == self.field_sel
            label = f["label"]
            if "choices" in f:
                shown = f["choices"][int(v) % len(f["choices"])]
                unit = ""
            else:
                shown = (self.editbuf if (sel and self.editing) else str(v))
                unit = f.get("unit", "")
            attr = cp(CLR_ROW_SEL) if sel else 0
            addstr(win, y, x0, clip("%-18s" % label, 18), cp(CLR_DIM))
            addstr(win, y, x0 + 19, clip("%-14s" % shown, 14), attr)
            if unit:
                addstr(win, y, x0 + 34, clip(unit, 8), cp(CLR_DIM))
            y += 1
            if y >= y0 + h - 2:
                break

        y += 1
        if y < y0 + h:
            hline(win, y, x0, min(w, 46), attr=cp(CLR_DIM))
            y += 1
        addstr(win, y, x0, "RESULT", cp(CLR_HEADER))
        y += 1
        for label, value, note in self._compute(key):
            if y >= y0 + h:
                break
            low = (str(value) + " " + str(note)).lower()
            attr = 0
            if any(t in low for t in ("error", "need", "exceeds", "over",
                                      "blocked", "too low")):
                attr = cp(CLR_WARN)
            elif any(t in low for t in ("ok", "workable", "clear")):
                attr = cp(CLR_OK)
            addstr(win, y, x0, clip("%-16s" % label, 16), cp(CLR_DIM))
            txt = str(value) + (("   " + note) if note else "")
            avail = max(1, w - 17)
            if len(txt) <= avail:
                addstr(win, y, x0 + 17, txt, attr)
                y += 1
                continue
            # Wrap rather than clip: a value like "Full precision" is long
            # BECAUSE the digits are the point, so cutting it defeats the row.
            for chunk in _wrap(txt, avail):
                if y >= y0 + h:
                    break
                addstr(win, y, x0 + 17, chunk, attr)
                y += 1

    # ---- keys ----
    def handle_key(self, ch):
        key = self._cur_key()
        if self.editing:
            return self._handle_edit(ch, key)

        if ch in (curses.KEY_DOWN, ord("j")) and not self.focus_fields:
            self._move(1)
            return True
        if ch in (curses.KEY_UP, ord("k")) and not self.focus_fields:
            self._move(-1)
            return True
        if ch in (ord("\t"), curses.KEY_RIGHT) and key:
            self.focus_fields = True
            self.field_sel = 0
            return True
        if self.focus_fields:
            n = len(TOOLS[key]["fields"]) if key else 0
            if ch in (curses.KEY_DOWN, ord("j")):
                self.field_sel = (self.field_sel + 1) % max(1, n)
                return True
            if ch in (curses.KEY_UP, ord("k")):
                self.field_sel = (self.field_sel - 1) % max(1, n)
                return True
            if ch in (curses.KEY_LEFT, 27):
                self.focus_fields = False
                return True
            if ch in (ord("e"), ord("\n"), curses.KEY_ENTER):
                f = TOOLS[key]["fields"][self.field_sel]
                if "choices" not in f:
                    self.editing = True
                    self.editbuf = str(self._vals_for(key)[self.field_sel])
                return True
            if ch in (ord("["), ord("]")):
                f = TOOLS[key]["fields"][self.field_sel]
                if "choices" in f:
                    vals = self._vals_for(key)
                    step = 1 if ch == ord("]") else -1
                    vals[self.field_sel] = (int(vals[self.field_sel]) + step) \
                        % len(f["choices"])
                return True
            if ch == ord("r"):
                self.values.pop(key, None)
                return True
        return False

    def _handle_edit(self, ch, key):
        if ch in (ord("\n"), curses.KEY_ENTER):
            f = TOOLS[key]["fields"][self.field_sel]
            if f.get("text"):
                self._vals_for(key)[self.field_sel] = self.editbuf
            else:
                try:
                    self._vals_for(key)[self.field_sel] = float(self.editbuf)
                except ValueError:
                    pass
            self.editing = False
            return True
        if ch == 27:                       # ESC cancels
            self.editing = False
            return True
        if ch in (curses.KEY_BACKSPACE, 127, 8):
            self.editbuf = self.editbuf[:-1]
            return True
        if 32 <= ch < 127:
            self.editbuf += chr(ch)
            return True
        return True

    def _move(self, delta):
        """Move the tool selection, skipping category headings."""
        n = len(self.rows)
        i = self.list.sel
        for _ in range(n):
            i = (i + delta) % n
            if self.rows[i][0] == "tool":
                break
        self.list.sel = i
        self.list.clamp(n, 1)

    def help_keys(self):
        if self.editing:
            return [("ENTER", "apply"), ("ESC", "cancel")]
        if self.focus_fields:
            return [("up/dn", "field"), ("e", "edit"), ("[ ]", "pick"),
                    ("r", "reset"), ("left", "tools")]
        return [("up/dn", "tool"), ("TAB", "fields")]
