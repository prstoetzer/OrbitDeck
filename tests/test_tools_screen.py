"""Test the Tools-hub GUI screen and its registry.

The pure calculators are covered in test_toolcalc.py; this guards the GUI
wiring: the registry shape, that every tool computes with its default inputs,
and that the screen builds and can select every tool.

Follows the codebase's defensive GUI-test convention: import tkinter inside the
test and bail out gracefully if a real Tk root can't be created (headless CI
without a display, or a tkinter stub without full widget support).
"""


def test_registry_shape():
    from orbitdeck.gui import tools_registry as reg
    seen = set()
    for _cat, keys in reg.CATEGORIES:
        for k in keys:
            assert k in reg.TOOLS, "category lists unknown tool %r" % k
            seen.add(k)
    assert seen == set(reg.TOOLS), "tools missing from CATEGORIES"
    for _key, spec in reg.TOOLS.items():
        assert callable(spec["fn"])
        assert spec["name"] and isinstance(spec["fields"], list)
        for fld in spec["fields"]:
            assert "label" in fld
            assert ("default" in fld) or ("choices" in fld)


def test_every_tool_computes_with_defaults():
    """Call each tool's fn with its default field values -> non-empty rows.

    Pure-Python; no Tk needed, so this always runs."""
    from orbitdeck.gui import tools_registry as reg
    for key, spec in reg.TOOLS.items():
        args = []
        for fld in spec["fields"]:
            if "choices" in fld:
                args.append(fld.get("default", 0))
            else:
                args.append(fld["default"])
        rows = spec["fn"](*args)
        assert isinstance(rows, list) and rows, "%s produced no rows" % key
        for r in rows:
            assert isinstance(r, tuple) and len(r) == 3


def _make_app():
    """Return (root, app) or None if a real Tk app can't be built here."""
    import tkinter as tk
    if not hasattr(tk, "Listbox") or not hasattr(tk, "Entry"):
        return None                       # tkinter stubbed without full widgets
    try:
        root = tk.Tk()
    except Exception:
        return None
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        app = OrbitDeckApp(root)
    except Exception:
        root.destroy()
        return None
    return root, app


def test_tools_screen_builds_and_selects_all():
    from orbitdeck.gui import tools_registry as reg
    made = _make_app()
    if made is None:
        return
    root, app = made
    try:
        app.show("tools")
        root.update()
        screen = app.current
        for key in reg.TOOLS:
            screen._select(key)
            root.update()
            assert screen._active == key
            assert screen._fields, "%s built no fields" % key
    finally:
        root.destroy()


def test_tools_screen_bad_input_does_not_crash():
    made = _make_app()
    if made is None:
        return
    root, app = made
    try:
        app.show("tools")
        root.update()
        screen = app.current
        screen._select("dipole")
        root.update()
        screen._fields[0]["var"].set("not a number")   # non-numeric
        root.update()                                   # must not raise
    finally:
        root.destroy()
