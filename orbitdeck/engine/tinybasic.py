"""orbitdeck.engine.tinybasic - the CardSat Tiny BASIC dialect.

A port of CardSat 0.9.75's interpreter, kept **source-compatible** so a program
written on the card runs here unchanged and vice versa. That constraint drives
most of the odd-looking decisions below:

  * variables are the 26 single letters A-Z, plus one anonymous array ``@(n)``
    and named arrays ``A(n)``-``Z(n)``;
  * the graphics coordinate space is **240x135**, the card's screen, whatever
    size the window is. Scaling happens at draw time in the UI, never here - if
    the interpreter used a bigger space, a program that drew a border at x=239
    would be wrong on one of the two machines;
  * colors are the card's ten palette indices, not RGB;
  * ``INPUT`` is collected before the run rather than during it. The card does
    this so the interpreter never re-enters the event loop with a live VM on the
    stack, and keeping that shape means a program cannot behave differently on
    the desktop.

The interpreter runs to completion and returns; it does not call back into a UI
event loop. Statement and time budgets bound a runaway program.
"""

import math
import random
import re
import time

MAX_STEPS = 2_000_000
MAX_SECONDS = 10.0
GOSUB_MAX = 32
FOR_MAX = 16
ARRAY_MAX = 4096

# The card's screen, and therefore the coordinate space every program is
# written against.
GFX_W = 240
GFX_H = 135

# 0 blk 1 wht 2 red 3 grn 4 blu 5 yel 6 cyn 7 org 8 gry 9 dark-green
PALETTE = ["#000000", "#ffffff", "#ff4136", "#2ecc40", "#4a90d9",
           "#ffdc00", "#39cccc", "#ff851b", "#aaaaaa", "#0b6623"]

# Statements that only mean something inside a numbered program.
IMMEDIATE_BANNED = ("GOTO", "GOSUB", "RETURN", "DATA", "READ", "RESTORE")


# The read-only system names a program can use. Every one is a *number*, and
# an unavailable one reads 0 with its matching ...OK flag at 0 - the card's
# design, so a program branches instead of halting. Names are matched longest
# first, and a name followed by another alphanumeric is an error rather than a
# silent partial match ("KP1" is not KP then 1).
SYS_NAMES = (
    "SATAZ SATEL SATRNG SATRR SATLAT SATLON SATALT SATSUN SATINC SATECC "
    "SATRAAN SATMM SATNOR AOSIN LOSIN PASSEL PASSVIS SUNAZ SUNEL MOONAZ "
    "MOONEL MYLAT MYLON MYALT UTCH UTCM UTCS UTCDAY UTCMON UTCYR SFI KP "
    "AINDEX NFAV SATOK TIMEOK POSOK SPWXOK PASSOK NSAT NTX PASSN "
    "TXDL TXUL TXBW TXINV TXLIN TXOK SSN MUF DOPPRX DOPPTX DECAYD "
    "UPTIME"
).split()


class BasicError(Exception):
    """A program error, reported with the line number where it happened."""

    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self):
        if self.line is not None:
            return "%s (line %d)" % (self.message, self.line)
        return self.message


class GfxOp:
    """One graphics call, recorded rather than drawn.

    The interpreter has no display: it emits ops in the card's 240x135 space
    and the UI scales them. That separation is what lets the same program
    produce the same picture at any window size.
    """

    __slots__ = ("op", "args", "text")

    def __init__(self, op, args=(), text=None):
        self.op = op                # cls pset line circle text show
        self.args = tuple(args)
        self.text = text

    def __repr__(self):
        return "GfxOp(%s, %r%s)" % (
            self.op, self.args, ", %r" % self.text if self.text else "")


def _num_str(v):
    """Format a number the way the card prints it."""
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return "%g" % v


class Program:
    """A parsed program: numbered lines in order, plus immediate-mode text."""

    def __init__(self, text):
        self.lines = []          # (line_number, source)
        self.immediate = []      # unnumbered lines, run in order
        for raw in (text or "").splitlines():
            s = raw.strip()
            if not s:
                continue
            m = re.match(r"^(\d+)\s*(.*)$", s)
            if m:
                self.lines.append((int(m.group(1)), m.group(2)))
            else:
                self.immediate.append(s)
        self.lines.sort(key=lambda t: t[0])

    def index_of(self, number):
        for i, (n, _s) in enumerate(self.lines):
            if n == number:
                return i
        return -1

    def input_prompts(self):
        """Every INPUT variable, in the order the program will reach them.

        Collected before the run - see the module docstring. Returns a list of
        variable names; the caller asks for values and passes them to run().
        """
        want = []
        for _n, src in self.lines:
            for stmt in _split_statements(src):
                m = re.match(r"^\s*INPUT\b(.*)$", stmt, re.I)
                if not m:
                    continue
                for part in m.group(1).split(","):
                    part = part.strip()
                    vm = re.match(r"^([A-Za-z])\b", part)
                    if vm:
                        want.append(vm.group(1).upper())
        return want


def _split_statements(src):
    """Split a line on ':' without breaking a quoted string or a comment.

    REM comments to the END OF THE LINE, colons included - a comment is prose,
    and prose contains colons. Splitting through one left the remainder to be
    parsed as code, so "REM Sky plot: every satellite" reported a syntax error
    on a line that is a comment.
    """
    out, cur, in_str = [], [], False
    i = 0
    while i < len(src):
        ch = src[i]
        if ch == '"':
            in_str = not in_str
            cur.append(ch)
        elif not in_str and _starts_rem(src, i):
            cur.append(src[i:])          # the rest of the line is comment
            break
        elif ch == ":" and not in_str:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return out


def _starts_rem(src, i):
    """True if a REM keyword begins at ``i`` (word-bounded)."""
    if src[i:i + 3].upper() != "REM":
        return False
    if i > 0 and (src[i - 1].isalnum() or src[i - 1] == "_"):
        return False
    nxt = src[i + 3:i + 4]
    return nxt == "" or not (nxt.isalnum() or nxt == "_")


class _ForRec:
    __slots__ = ("var", "limit", "step", "line_idx", "stmt_idx")

    def __init__(self, var, limit, step, line_idx, stmt_idx):
        self.var = var
        self.limit = limit
        self.step = step
        self.line_idx = line_idx
        self.stmt_idx = stmt_idx


class Interpreter:
    """Runs a Program to completion, collecting output and graphics ops."""

    def __init__(self, program, inputs=None, sat_context=None, host=None,
                 max_steps=MAX_STEPS, max_seconds=MAX_SECONDS, seed=None,
                 file_dir=None):
        self.prog = program
        self.out = []
        self.gfx = []
        self.vars = {chr(ord("A") + i): 0.0 for i in range(26)}
        self.arr = None            # the anonymous @() array
        self.named = {}            # named arrays A()..Z()
        self.gosub = []
        self.fors = []
        self.data_vals = []
        self.data_pos = 0
        self.inputs = list(inputs or [])
        self.input_pos = 0
        self.max_steps = max_steps
        self.max_seconds = max_seconds
        self.steps = 0
        self.rng = random.Random(seed)
        self.sat = sat_context or {}
        # ``host`` supplies the live system values (see BasicHost). Without one
        # every system name reads 0 and its OK flag is 0, which is what lets a
        # program written against a card run here and simply branch.
        self.host = host
        self.sys = dict(host.snapshot()) if host is not None else {}
        self.file_dir = file_dir
        self._fh = None
        self._files_written = []
        self._collect_data()

    # ---- helpers ---------------------------------------------------------
    def _collect_data(self):
        for _n, src in self.prog.lines:
            for stmt in _split_statements(src):
                m = re.match(r"^\s*DATA\b(.*)$", stmt, re.I)
                if m:
                    for item in m.group(1).split(","):
                        item = item.strip()
                        if item:
                            try:
                                self.data_vals.append(float(item))
                            except ValueError:
                                pass

    def _emit(self, text):
        self.out.append(text)

    def _tick(self, line):
        self.steps += 1
        if self.steps > self.max_steps:
            raise BasicError("too many statements (runaway program?)", line)
        if (self.steps & 0x3FF) == 0:
            if time.time() - self._t0 > self.max_seconds:
                raise BasicError("program ran too long", line)

    # ---- run -------------------------------------------------------------
    def run(self):
        self._t0 = time.time()
        for src in self.prog.immediate:
            banned = _banned_in(src)
            if banned:
                raise BasicError("%s needs a numbered program" % banned)
        if self.prog.immediate and not self.prog.lines:
            for src in self.prog.immediate:
                self._run_line(-1, src, 0)
            return self
        idx = 0
        try:
            while 0 <= idx < len(self.prog.lines):
                number, src = self.prog.lines[idx]
                nxt = self._run_line(number, src, idx)
                if nxt == -999:
                    break
                idx = idx + 1 if nxt is None else nxt
        finally:
            # An error must not leave a half-written file open.
            self.close()
        return self

    def _run_line(self, number, src, line_idx):
        stmts = _split_statements(src)
        si = 0
        while si < len(stmts):
            self._tick(number)
            res = self._exec(stmts[si], number, line_idx, si)
            if res is None:
                si += 1
                continue
            if res == -999:
                return -999
            if isinstance(res, tuple) and res[0] == "same_line":
                si = res[1]
                continue
            return res
        return None

    def _exec(self, stmt, number, line_idx, stmt_idx):
        s = stmt.strip()
        if not s:
            return None
        up = s.upper()

        def kw(word):
            return up.startswith(word) and (
                len(up) == len(word) or not up[len(word)].isalnum())

        if kw("REM"):
            return None
        if kw("END"):
            return -999
        if kw("DATA"):
            return None
        if kw("PRINT") or s.startswith("?"):
            rest = s[1:] if s.startswith("?") else s[5:]
            self._print(rest, number)
            return None
        if kw("LPRINT"):
            # The card sends this to its thermal printer; here it goes to the
            # output pane, prefixed, so a program written for the card still
            # runs and you can see what it would have printed.
            self._emit("[LPRINT] " + self._render(s[6:], number))
            return None
        if kw("CLS"):
            self.gfx.append(GfxOp("cls"))
            return None
        if kw("SHOW"):
            self.gfx.append(GfxOp("show"))
            return None
        if kw("PSET"):
            a = self._args(s[4:], number, 2, 3)
            self.gfx.append(GfxOp("pset", (a[0], a[1],
                                           a[2] if len(a) > 2 else 1)))
            return None
        if kw("LINE"):
            a = self._args(s[4:], number, 4, 5)
            self.gfx.append(GfxOp("line", (a[0], a[1], a[2], a[3],
                                           a[4] if len(a) > 4 else 1)))
            return None
        if kw("CIRCLE"):
            a = self._args(s[6:], number, 3, 4)
            self.gfx.append(GfxOp("circle", (a[0], a[1], a[2],
                                             a[3] if len(a) > 3 else 1)))
            return None
        if kw("TEXT"):
            return self._text(s[4:], number)
        if kw("INPUT"):
            return self._input(s[5:], number)
        if kw("LET"):
            return self._assign(s[3:], number)
        if kw("IF"):
            return self._if(s[2:], number, line_idx, stmt_idx)
        if kw("GOTO"):
            return self._jump(s[4:], number)
        if kw("GOSUB"):
            target = self._jump(s[5:], number)
            if len(self.gosub) >= GOSUB_MAX:
                raise BasicError("GOSUB too deep", number)
            self.gosub.append(line_idx + 1)
            return target
        if kw("RETURN"):
            if not self.gosub:
                raise BasicError("RETURN without GOSUB", number)
            return self.gosub.pop()
        if kw("FOR"):
            return self._for(s[3:], number, line_idx, stmt_idx)
        if kw("NEXT"):
            return self._next(number)
        if kw("DIM"):
            return self._dim(s[3:], number)
        if kw("ERASE"):
            name = s[5:].strip().upper()[:1]
            self.named.pop(name, None)
            return None
        if kw("RESTORE"):
            self.data_pos = 0
            return None
        if kw("READ"):
            return self._read(s[4:], number)
        if kw("ON"):
            return self._on(s[2:], number)
        if kw("FOPEN"):
            return self._fopen(s[5:], number)
        if kw("FPRINT"):
            if self._fh is None:
                raise BasicError("no file open (FOPEN)", number)
            self._fh.write(self._render(s[6:], number) + "\n")
            return None
        if kw("FCLOSE"):
            if self._fh is not None:
                self._fh.close()
                self._fh = None
            return None
        if kw("FILES"):
            self._emit(self._file_list())
            return None
        if kw("SATSEL"):
            return self._satsel(s[6:], number)
        if kw("TXSEL"):
            return self._txsel(s[5:], number)
        return self._assign(s, number)

    # ---- statements ------------------------------------------------------
    def _args(self, text, number, lo, hi):
        vals = []
        for part in _split_args(text):
            vals.append(self._eval(part, number))
        if len(vals) < lo or len(vals) > hi:
            raise BasicError("wrong number of arguments", number)
        return vals

    def _text(self, text, number):
        parts = _split_args(text)
        if len(parts) < 3:
            raise BasicError("TEXT x,y,value", number)
        x = self._eval(parts[0], number)
        y = self._eval(parts[1], number)
        rest = ",".join(parts[2:]).strip()
        if rest.startswith('"'):
            body = rest[1:rest.index('"', 1)] if '"' in rest[1:] else rest[1:]
        else:
            body = _num_str(self._eval(rest, number))
        self.gfx.append(GfxOp("text", (x, y), body))
        return None

    def _input(self, text, number):
        for part in _split_args(text):
            part = part.strip()
            m = re.match(r"^([A-Za-z])\b", part)
            if not m:
                continue
            name = m.group(1).upper()
            if self.input_pos < len(self.inputs):
                self.vars[name] = float(self.inputs[self.input_pos])
                self.input_pos += 1
            else:
                self.vars[name] = 0.0
        return None

    def _assign(self, text, number):
        if "=" not in text:
            raise BasicError("syntax", number)
        lhs, rhs = text.split("=", 1)
        lhs = lhs.strip()
        val = self._eval(rhs, number)
        m = re.match(r"^@\s*\((.*)\)$", lhs)
        if m:
            i = int(self._eval(m.group(1), number))
            if self.arr is None or not 0 <= i < len(self.arr):
                raise BasicError("@ index", number)
            self.arr[i] = val
            return None
        m = re.match(r"^([A-Za-z])\s*\((.*)\)$", lhs)
        if m:
            name = m.group(1).upper()
            i = int(self._eval(m.group(2), number))
            a = self.named.get(name)
            if a is None or not 0 <= i < len(a):
                raise BasicError("%s index" % name, number)
            a[i] = val
            return None
        if re.fullmatch(r"[A-Za-z]", lhs):
            self.vars[lhs.upper()] = val
            return None
        raise BasicError("unknown name %r" % lhs, number)

    def _if(self, text, number, line_idx, stmt_idx):
        m = re.split(r"\bTHEN\b", text, 1, flags=re.I)
        if len(m) < 2:
            raise BasicError("IF without THEN", number)
        cond = self._eval(m[0], number)
        if cond == 0:
            return None
        rest = m[1].strip()
        if re.fullmatch(r"\d+", rest):
            return self._jump(rest, number)
        # Any other consequent is a full statement. CardSat's notes record that
        # keeping a hand-picked subset here made "IF C=3 THEN TEXT ..." fall
        # through to assignment and report "unknown name".
        return self._exec(rest, number, line_idx, stmt_idx)

    def _jump(self, text, number):
        try:
            target = int(float(text.strip().split()[0]))
        except (ValueError, IndexError):
            raise BasicError("line number expected", number)
        idx = self.prog.index_of(target)
        if idx < 0:
            raise BasicError("no line %d" % target, number)
        return idx

    def _for(self, text, number, line_idx, stmt_idx):
        m = re.match(r"^\s*([A-Za-z])\s*=\s*(.*)$", text)
        if not m:
            raise BasicError("FOR var A-Z", number)
        var = m.group(1).upper()
        body = m.group(2)
        parts = re.split(r"\bTO\b", body, 1, flags=re.I)
        if len(parts) < 2:
            raise BasicError("FOR without TO", number)
        start = self._eval(parts[0], number)
        rest = parts[1]
        step = 1.0
        sp = re.split(r"\bSTEP\b", rest, 1, flags=re.I)
        limit = self._eval(sp[0], number)
        if len(sp) > 1:
            step = self._eval(sp[1], number)
        self.vars[var] = start
        if len(self.fors) >= FOR_MAX:
            raise BasicError("FOR too deep", number)
        self.fors.append(_ForRec(var, limit, step, line_idx, stmt_idx))
        return None

    def _next(self, number):
        if not self.fors:
            raise BasicError("NEXT without FOR", number)
        f = self.fors[-1]
        self.vars[f.var] += f.step
        v = self.vars[f.var]
        going = (v <= f.limit) if f.step >= 0 else (v >= f.limit)
        if not going:
            self.fors.pop()
            return None
        # Resume the body. If it began on the FOR's own line, hand the cursor
        # back to that line rather than jumping to the following one and
        # skipping it.
        src = self.prog.lines[f.line_idx][1]
        if f.stmt_idx + 1 < len(_split_statements(src)):
            if f.line_idx == self._current_line_idx:
                return ("same_line", f.stmt_idx + 1)
        return f.line_idx if f.stmt_idx + 1 < len(
            _split_statements(src)) else f.line_idx + 1

    def _dim(self, text, number):
        for part in _split_args(text):
            part = part.strip()
            m = re.match(r"^@\s*\((.*)\)$", part)
            if m:
                n = int(self._eval(m.group(1), number))
                if not 1 <= n <= ARRAY_MAX:
                    raise BasicError("@ size 1..%d" % ARRAY_MAX, number)
                self.arr = [0.0] * n
                continue
            m = re.match(r"^([A-Za-z])\s*\((.*)\)$", part)
            if m:
                n = int(self._eval(m.group(2), number))
                if not 1 <= n <= ARRAY_MAX:
                    raise BasicError("array size 1..%d" % ARRAY_MAX, number)
                self.named[m.group(1).upper()] = [0.0] * n
                continue
            raise BasicError("DIM name", number)
        return None

    def _read(self, text, number):
        for part in _split_args(text):
            if self.data_pos >= len(self.data_vals):
                raise BasicError("out of DATA", number)
            v = self.data_vals[self.data_pos]
            self.data_pos += 1
            self._assign("%s=%s" % (part.strip(), _num_str(v)), number)
        return None

    def _on(self, text, number):
        parts = re.split(r"\bGOTO\b", text, 1, flags=re.I)
        if len(parts) < 2:
            raise BasicError("ON..GOTO", number)
        sel = int(self._eval(parts[0], number))
        targets = [t.strip() for t in parts[1].split(",") if t.strip()]
        if not 1 <= sel <= len(targets):
            return None            # out of range falls through, as on the card
        return self._jump(targets[sel - 1], number)

    def _satsel(self, text, number):
        """Point the SAT* names at catalog entry #expr.

        Follows the card: a bad *index* is an error, but a satellite that
        cannot be propagated is not - SATOK goes to 0 so a catalog scan
        (FOR I=0 TO NSAT-1 : SATSEL I : IF SATOK=0 ...) keeps going.
        """
        if self.host is None:
            raise BasicError("SATSEL needs satellite data", number)
        idx = int(self._eval(text, number))
        values = self.host.select_sat(idx)
        if values is None:
            raise BasicError("bad sat index", number)
        self.sys.update(values)
        # A previous TXSEL is stale once the satellite changes. The card notes
        # that silently keeping it was the old trap.
        for name in ("TXDL", "TXUL", "TXBW", "TXINV", "TXLIN"):
            self.sys[name] = 0.0
        self.sys["TXOK"] = 0.0
        return None

    def _txsel(self, text, number):
        """Snapshot transponder #expr of the SATSELed satellite."""
        if self.host is None:
            raise BasicError("TXSEL needs satellite data", number)
        idx = int(self._eval(text, number))
        values = self.host.select_tx(idx)
        if values is None:
            raise BasicError("bad tx index", number)
        self.sys.update(values)
        self.sys["TXOK"] = 1.0
        return None

    def _safe_name(self, raw):
        """A plain file name inside the program directory, never a path.

        The card sandboxes writes to one directory; the same rule here stops a
        program reaching the rest of the disk.
        """
        name = (raw or "").strip()
        if not name or "/" in name or "\\" in name or name.startswith("."):
            return None
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", name):
            return None
        return name

    def _fopen(self, text, number):
        t = text.strip()
        if not (t.startswith('"') and '"' in t[1:]):
            raise BasicError('FOPEN "name"', number)
        name = self._safe_name(t[1:t.index('"', 1)])
        if name is None:
            raise BasicError("bad file name", number)
        if not self.file_dir:
            raise BasicError("file writing is off (Settings)", number)
        import os
        os.makedirs(self.file_dir, exist_ok=True)
        if self._fh is not None:
            self._fh.close()
        path = os.path.join(self.file_dir, name)
        try:
            self._fh = open(path, "a", encoding="utf-8")
        except OSError as exc:
            raise BasicError("open failed: %s" % str(exc)[:40], number)
        if path not in self._files_written:
            self._files_written.append(path)
        return None

    def _file_list(self):
        import os
        if not self.file_dir or not os.path.isdir(self.file_dir):
            return "(no files)"
        names = sorted(os.listdir(self.file_dir))
        return "\n".join(names) if names else "(no files)"

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    # ---- printing --------------------------------------------------------
    def _render(self, text, number):
        pieces = []
        for part in _split_args(text, seps=(",", ";")):
            part = part.strip()
            if not part:
                continue
            if part.startswith('"'):
                end = part.index('"', 1) if '"' in part[1:] else len(part)
                pieces.append(part[1:end])
            else:
                pieces.append(_num_str(self._eval(part, number)))
        return "".join(pieces)

    def _print(self, text, number):
        self._emit(self._render(text, number))

    # ---- expressions -----------------------------------------------------
    def _eval(self, text, number):
        try:
            return _Expr(text, self, number).parse()
        except BasicError:
            raise
        except Exception as exc:
            raise BasicError("bad expression: %s" % str(exc)[:40], number)

    _current_line_idx = 0


def _banned_in(src):
    """First banned immediate-mode keyword, ignoring quoted text."""
    depth = False
    token = ""
    for ch in src + " ":
        if ch == '"':
            depth = not depth
            continue
        if depth:
            continue
        if ch.isalpha():
            token += ch.upper()
        else:
            if token in IMMEDIATE_BANNED:
                return token
            token = ""
    return None


def _split_args(text, seps=(",",)):
    """Split on separators outside quotes and parentheses."""
    out, cur, depth, in_str = [], [], 0, False
    for ch in text:
        if ch == '"':
            in_str = not in_str
            cur.append(ch)
        elif in_str:
            cur.append(ch)
        elif ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch in seps and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


class _Expr:
    """Recursive-descent expression parser for the CardSat dialect."""

    FUNCS = {
        "ABS": abs, "INT": lambda v: float(math.floor(v)),
        "SGN": lambda v: float((v > 0) - (v < 0)),
        "SQR": lambda v: math.sqrt(max(0.0, v)),
        "SIN": lambda v: math.sin(math.radians(v)),
        "COS": lambda v: math.cos(math.radians(v)),
        "TAN": lambda v: math.tan(math.radians(v)),
        "ASN": lambda v: math.degrees(math.asin(max(-1.0, min(1.0, v)))),
        "ACS": lambda v: math.degrees(math.acos(max(-1.0, min(1.0, v)))),
        "ATN": lambda v: math.degrees(math.atan(v)),
        "LOG": lambda v: math.log(v) if v > 0 else 0.0,
        "EXP": math.exp,
        "FRAC": lambda v: v - math.floor(v),
        "ROUND": lambda v: float(round(v)),
    }
    FUNCS2 = {
        "MIN": min, "MAX": max,
        "HYP": lambda a, b: math.hypot(a, b),
    }

    def __init__(self, text, interp, number):
        self.s = text
        self.i = 0
        self.vm = interp
        self.line = number

    def parse(self):
        v = self.lor()
        return v

    # token helpers
    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def peek(self, n=1):
        self.ws()
        return self.s[self.i:self.i + n]

    def eat(self, tok):
        self.ws()
        if self.s[self.i:self.i + len(tok)].upper() == tok.upper():
            self.i += len(tok)
            return True
        return False

    # grammar
    def lor(self):
        v = self.land()
        while True:
            self.ws()
            if self.eat("OR"):
                v = 1.0 if (v != 0 or self.land() != 0) else 0.0
            else:
                return v

    def land(self):
        v = self.cmp()
        while True:
            self.ws()
            if self.eat("AND"):
                v = 1.0 if (v != 0 and self.cmp() != 0) else 0.0
            else:
                return v

    def cmp(self):
        v = self.add()
        while True:
            self.ws()
            for op in ("<=", ">=", "<>", "=", "<", ">"):
                if self.s[self.i:self.i + len(op)] == op:
                    self.i += len(op)
                    r = self.add()
                    v = float({
                        "<=": v <= r, ">=": v >= r, "<>": v != r,
                        "=": v == r, "<": v < r, ">": v > r}[op])
                    break
            else:
                return v

    def add(self):
        v = self.mul()
        while True:
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == "+":
                self.i += 1
                v += self.mul()
            elif self.i < len(self.s) and self.s[self.i] == "-":
                self.i += 1
                v -= self.mul()
            else:
                return v

    def mul(self):
        v = self.power()
        while True:
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == "*":
                self.i += 1
                v *= self.power()
            elif self.i < len(self.s) and self.s[self.i] == "/":
                self.i += 1
                d = self.power()
                if d == 0:
                    raise BasicError("divide by zero", self.line)
                v /= d
            elif self.i < len(self.s) and self.s[self.i] == "%":
                self.i += 1
                d = self.power()
                if d == 0:
                    raise BasicError("divide by zero", self.line)
                v = math.fmod(v, d)
            else:
                return v

    def power(self):
        v = self.unary()
        self.ws()
        if self.i < len(self.s) and self.s[self.i] == "^":
            self.i += 1
            return v ** self.power()
        return v

    def unary(self):
        self.ws()
        if self.i < len(self.s) and self.s[self.i] == "-":
            self.i += 1
            return -self.unary()
        if self.i < len(self.s) and self.s[self.i] == "+":
            self.i += 1
            return self.unary()
        if self.eat("NOT"):
            return 0.0 if self.unary() != 0 else 1.0
        return self.atom()

    def atom(self):
        self.ws()
        if self.i >= len(self.s):
            raise BasicError("unexpected end of expression", self.line)
        ch = self.s[self.i]
        if ch == "(":
            self.i += 1
            v = self.lor()
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == ")":
                self.i += 1
            return v
        if ch == "@":
            self.i += 1
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == "(":
                self.i += 1
                idx = int(self.lor())
                self.ws()
                if self.i < len(self.s) and self.s[self.i] == ")":
                    self.i += 1
                a = self.vm.arr
                if a is None or not 0 <= idx < len(a):
                    raise BasicError("@ index", self.line)
                return a[idx]
            raise BasicError("@ needs ()", self.line)
        if ch.isdigit() or ch == ".":
            m = re.match(r"\d*\.?\d+([eE][-+]?\d+)?", self.s[self.i:])
            self.i += m.end()
            return float(m.group(0))
        if ch.isalpha():
            m = re.match(r"[A-Za-z]+", self.s[self.i:])
            name = m.group(0).upper()
            # RND first: it takes no argument on the card.
            if name == "RND":
                self.i += m.end()
                return self.vm.rng.random()
            if name == "PI":
                self.i += m.end()
                return math.pi
            if name in self.FUNCS or name in self.FUNCS2:
                self.i += m.end()
                self.ws()
                if self.i < len(self.s) and self.s[self.i] == "(":
                    self.i += 1
                    a = self.lor()
                    self.ws()
                    if name in self.FUNCS2:
                        if self.i < len(self.s) and self.s[self.i] == ",":
                            self.i += 1
                            b = self.lor()
                            self.ws()
                            if self.i < len(self.s) and self.s[self.i] == ")":
                                self.i += 1
                            return float(self.FUNCS2[name](a, b))
                        raise BasicError("%s needs two arguments" % name,
                                         self.line)
                    if self.i < len(self.s) and self.s[self.i] == ")":
                        self.i += 1
                    return float(self.FUNCS[name](a))
                raise BasicError("%s needs ()" % name, self.line)
            # System names, longest first. A name followed by another
            # alphanumeric is an error rather than a silent partial match, so
            # "KP1" does not quietly parse as KP then 1.
            best = ""
            for cand in SYS_NAMES:
                if (name.startswith(cand) and len(cand) > len(best)
                        and len(name) == len(cand)):
                    best = cand
            if best:
                self.i += len(best)
                if (self.i < len(self.s)
                        and (self.s[self.i].isalnum() or self.s[self.i] == "_")):
                    raise BasicError("unknown name %s" % name, self.line)
                return float(self.vm.sys.get(best, 0.0))
            if len(name) == 1:
                self.i += 1
                self.ws()
                if self.i < len(self.s) and self.s[self.i] == "(":
                    self.i += 1
                    idx = int(self.lor())
                    self.ws()
                    if self.i < len(self.s) and self.s[self.i] == ")":
                        self.i += 1
                    a = self.vm.named.get(name)
                    if a is None or not 0 <= idx < len(a):
                        raise BasicError("%s index" % name, self.line)
                    return a[idx]
                return self.vm.vars[name]
            raise BasicError("unknown name %s" % name, self.line)
        raise BasicError("unexpected %r" % ch, self.line)


def run_source(text, inputs=None, seed=None, max_seconds=MAX_SECONDS):
    """Convenience: parse and run, returning the Interpreter."""
    return Interpreter(Program(text), inputs=inputs, seed=seed,
                       max_seconds=max_seconds).run()
