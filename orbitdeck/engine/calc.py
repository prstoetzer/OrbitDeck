"""orbitdeck.engine.calc - the general-purpose calculators from CardSat.

Three tools that aren't bench formulas but general utilities:

  * ``evaluate`` - a safe scientific-calculator expression evaluator (the maths
    functions a ham reaches for, no arbitrary code execution).
  * ``programmer_rows`` - hex / decimal / binary / octal conversion with the
    bitwise view, for register and protocol work.
  * ``convert_rows`` - a unit converter across the length / mass / power /
    frequency / temperature / angle families used around a station.

The expression evaluator walks Python's AST and permits only literals,
arithmetic, comparisons and a whitelist of maths functions - so a stray
``__import__`` or attribute access can't slip through.
"""

import ast
import math
import operator

# ---------------------------------------------------------------------------
# Scientific calculator
# ---------------------------------------------------------------------------
_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

# whitelisted names: maths functions and constants only
_NAMES = {
    "pi": math.pi, "e": math.e, "tau": math.tau,
    "sqrt": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "atan2": math.atan2, "hypot": math.hypot,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": math.log, "log10": math.log10, "log2": math.log2,
    "exp": math.exp, "pow": math.pow,
    "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil,
    "deg": math.degrees, "rad": math.radians,
    "degrees": math.degrees, "radians": math.radians,
    "min": min, "max": max, "fmod": math.fmod, "trunc": math.trunc,
    "factorial": math.factorial, "gcd": math.gcd,
}


class CalcError(ValueError):
    """Raised for a malformed or disallowed expression."""


def _eval_node(node, env=None):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise CalcError("only numbers are allowed")
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise CalcError("unsupported operator")
        return op(_eval_node(node.left, env), _eval_node(node.right, env))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise CalcError("unsupported unary operator")
        return op(_eval_node(node.operand, env))
    if isinstance(node, ast.Name):
        if env and node.id in env:
            return env[node.id]
        if node.id in _NAMES and not callable(_NAMES[node.id]):
            return _NAMES[node.id]
        raise CalcError("unknown name %r" % node.id)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise CalcError("unsupported call")
        fn = _NAMES.get(node.func.id)
        if fn is None or not callable(fn):
            raise CalcError("unknown function %r" % node.func.id)
        if node.keywords:
            raise CalcError("keyword arguments are not supported")
        return fn(*[_eval_node(a, env) for a in node.args])
    raise CalcError("unsupported expression")


def evaluate(expr):
    """Evaluate a scientific-calculator expression. Raises CalcError."""
    return evaluate_with(expr, None)


def evaluate_with(expr, variables=None):
    """Evaluate an expression with optional variable bindings (e.g. {'x': 1.0}).

    Bindings are looked up before the maths-name whitelist, so a graphing
    calculator can bind x without widening what the evaluator permits."""
    text = (expr or "").strip()
    if not text:
        raise CalcError("empty expression")
    # a couple of friendly aliases before parsing
    text = text.replace("^", "**").replace("\u00d7", "*").replace("\u00f7", "/")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise CalcError("syntax error") from exc
    try:
        val = _eval_node(tree, variables)
    except CalcError:
        raise
    except ZeroDivisionError as exc:
        raise CalcError("division by zero") from exc
    except (ValueError, OverflowError) as exc:
        raise CalcError(str(exc)) from exc
    return val


def sci_rows(expr):
    """Tools-hub wrapper: evaluate and show the result several ways."""
    try:
        v = evaluate(expr)
    except CalcError as exc:
        return [("error", str(exc), "")]
    out = [("Result", "%g" % v, "")]
    if isinstance(v, float) and v == v and abs(v) != float("inf"):
        out.append(("Full precision", repr(v), ""))
        if v != 0 and (abs(v) >= 1e5 or abs(v) < 1e-3):
            out.append(("Scientific", "%.6e" % v, ""))
        if abs(v) < 1e15:
            out.append(("Rounded", "%.4f" % v, ""))
    if isinstance(v, (int, float)) and float(v).is_integer() and abs(v) < 2**63:
        out.append(("As integer", "%d" % int(v), ""))
    return out


FUNCTION_HELP = sorted(k for k, v in _NAMES.items() if callable(v))


# ---------------------------------------------------------------------------
# Programmer calculator (hex / dec / bin / oct)
# ---------------------------------------------------------------------------
PROG_BASES = ["decimal", "hex", "binary", "octal"]


def parse_int(text, base_index=0):
    """Parse an integer written in the given base (index into PROG_BASES).
    Accepts 0x/0b/0o prefixes regardless of the selected base."""
    s = (text or "").strip().replace("_", "").replace(" ", "")
    if not s:
        raise CalcError("empty value")
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    low = s.lower()
    if low.startswith("0x"):
        val = int(low[2:], 16)
    elif low.startswith("0b"):
        val = int(low[2:], 2)
    elif low.startswith("0o"):
        val = int(low[2:], 8)
    else:
        base = {0: 10, 1: 16, 2: 2, 3: 8}[int(base_index) % 4]
        try:
            val = int(low, base)
        except ValueError as exc:
            raise CalcError("not a valid %s value" % PROG_BASES[base_index]) \
                from exc
    return -val if neg else val


def programmer_rows(value="255", base_index=0, width_bits=32):
    """Show a number in decimal / hex / binary / octal plus a bit breakdown."""
    try:
        v = parse_int(value, base_index)
    except CalcError as exc:
        return [("error", str(exc), "")]
    w = int(width_bits) if int(width_bits) in (8, 16, 32, 64) else 32
    mask = (1 << w) - 1
    uv = v & mask                       # two's-complement view at this width
    bits = format(uv, "0%db" % w)
    grouped = " ".join(bits[i:i + 4] for i in range(0, len(bits), 4))
    out = [
        ("Decimal", "%d" % v, ""),
        ("Hex", "0x%X" % uv, ""),
        ("Octal", "0o%o" % uv, ""),
        ("Binary", "0b%s" % bits.lstrip("0") or "0b0", ""),
        ("Grouped", grouped[:60], "%d-bit" % w),
        ("Bits set", "%d" % bin(uv).count("1"), "population count"),
    ]
    if v < 0:
        out.append(("Two's compl", "0x%X" % uv, "at %d bits" % w))
    signed_max = (1 << (w - 1)) - 1
    if uv > signed_max:
        out.append(("As signed", "%d" % (uv - (1 << w)), "%d-bit" % w))
    out.append(("Bytes (BE)", " ".join("%02X" % b for b in
                                       uv.to_bytes(w // 8, "big")), ""))
    return out


# ---------------------------------------------------------------------------
# Unit converter
# ---------------------------------------------------------------------------
# family -> (unit name, factor to the family's base unit)
UNIT_FAMILIES = {
    "Length": [("m", 1.0), ("km", 1000.0), ("cm", 0.01), ("mm", 0.001),
               ("in", 0.0254), ("ft", 0.3048), ("yd", 0.9144),
               ("mi", 1609.344), ("nmi", 1852.0)],
    "Mass": [("kg", 1.0), ("g", 0.001), ("lb", 0.45359237),
             ("oz", 0.028349523), ("t", 1000.0)],
    "Power": [("W", 1.0), ("mW", 0.001), ("kW", 1000.0), ("hp", 745.6999)],
    "Frequency": [("Hz", 1.0), ("kHz", 1e3), ("MHz", 1e6), ("GHz", 1e9)],
    "Speed": [("m/s", 1.0), ("km/h", 1 / 3.6), ("mph", 0.44704),
              ("kt", 0.514444)],
    "Angle": [("deg", 1.0), ("rad", 57.29577951308232),
              ("arcmin", 1 / 60.0), ("arcsec", 1 / 3600.0)],
    "Temperature": [("C", 1.0), ("F", 1.0), ("K", 1.0)],   # handled specially
}
UNIT_FAMILY_NAMES = list(UNIT_FAMILIES)


def _temp_to_c(v, unit):
    if unit == "C":
        return v
    if unit == "F":
        return (v - 32.0) * 5.0 / 9.0
    return v - 273.15                    # K


def _temp_from_c(c, unit):
    if unit == "C":
        return c
    if unit == "F":
        return c * 9.0 / 5.0 + 32.0
    return c + 273.15


def convert(value, family, from_unit, to_unit):
    """Convert a value between two units of the same family."""
    units = dict(UNIT_FAMILIES[family])
    if from_unit not in units or to_unit not in units:
        raise CalcError("unknown unit for %s" % family)
    if family == "Temperature":
        return _temp_from_c(_temp_to_c(value, from_unit), to_unit)
    return value * units[from_unit] / units[to_unit]


def convert_rows(value=1.0, family_index=0, from_index=0, to_index=1):
    """Tools-hub wrapper: convert, and also show the value in every unit of the
    family so it doubles as a quick table."""
    fams = UNIT_FAMILY_NAMES
    family = fams[int(family_index) % len(fams)]
    units = [u for u, _f in UNIT_FAMILIES[family]]
    fu = units[int(from_index) % len(units)]
    tu = units[int(to_index) % len(units)]
    try:
        v = float(value)
        main = convert(v, family, fu, tu)
    except (CalcError, ValueError) as exc:
        return [("error", str(exc), "")]
    out = [("%g %s" % (v, fu), "%g %s" % (main, tu), "")]
    out.append(("--- all units", family, "---"))
    for u in units:
        if u == fu:
            continue
        out.append((u, "%g" % convert(v, family, fu, u), ""))
    return out
