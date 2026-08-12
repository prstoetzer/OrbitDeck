"""Audit items C and D: character lookup, orbit types, satellite history."""

from orbitdeck.engine import refdata as RD


def test_char_lookup_covers_every_representation():
    """The ASCII table alone answers 'what is 0x41'. RTTY and CI-V work needs
    the ITA2 shifts and the BCD reading too."""
    rows = dict(RD.char_lookup(0x41))
    assert rows["Hex"] == "0x41" and rows["Decimal"] == "65"
    assert rows["Binary"] == "01000001"
    assert rows["ASCII"] == "A"
    assert rows["Morse"] == ".-"
    assert rows["BCD"] == "41"
    # control codes are named, not printed
    ctl = dict(RD.char_lookup(0x03))
    assert "ETX" in ctl["ASCII"]
    # 5-bit values also carry their teleprinter meaning
    assert ctl["ITA2 letters"] == "A"
    assert ctl["ITA2 figures"] == "-"


def test_char_lookup_bcd_rejects_invalid_nibbles():
    """CI-V frequency bytes are BCD, so an invalid nibble must be called out
    rather than silently shown as a number."""
    assert "invalid" in dict(RD.char_lookup(0x1F))["BCD"]
    assert dict(RD.char_lookup(0x99))["BCD"] == "99"


def test_char_lookup_bad_input():
    assert RD.char_lookup("nope")[0][0] == "error"


def test_ita2_table_is_complete_and_shifted():
    rows = RD.ita2_rows()
    assert len(rows) == 32
    # the shift codes appear in both columns, as they must
    flat = [r[1] for r in rows] + [r[2] for r in rows]
    assert "FIGS" in flat and "LTRS" in flat
    # figures shift really differs from letters shift
    assert RD.ITA2_LTRS[1] == "E" and RD.ITA2_FIGS[1] == "3"


def test_morse_table():
    rows = dict((k, v) for k, v, _ in RD.morse_rows())
    assert rows["A"] == ".-" and rows["0"] == "-----"
    assert rows["?"] == "..--.."
    assert len(rows) >= 36


def test_orbit_types_and_history_tables():
    ot = RD.orbit_type_rows()
    assert len(ot) >= 8
    names = [r[0] for r in ot]
    for want in ("LEO", "GEO", "Molniya", "Sun-synchronous"):
        assert want in names
    hist = RD.sat_history_rows()
    assert len(hist) >= 12
    flat = " ".join(" ".join(r) for r in hist)
    for want in ("OSCAR 1", "AO-7", "QO-100", "IO-117"):
        assert want in flat
    # chronological
    years = [int(r[0]) for r in hist]
    assert years == sorted(years)


def test_new_tables_registered_and_render():
    names = [t[0] for t in RD.TABLES]
    for want in ("ITA2 / Baudot", "Morse", "Orbit types",
                 "Satellite history"):
        assert want in names
    for _n, _d, fn in RD.TABLES:
        rows = fn()
        assert rows and all(len(r) == 3 for r in rows)


def test_char_lookup_is_a_tool():
    from orbitdeck.engine.tools_registry import TOOLS
    assert "char_lookup" in TOOLS
    spec = TOOLS["char_lookup"]
    assert spec["fn"](*[f["default"] for f in spec["fields"]])


def test_radar_shows_the_sub_satellite_point():
    """CardSat's radar shows where the bird is, not only where to point."""
    import inspect
    from orbitterm.screens import catalog
    src = inspect.getsource(catalog.RadarScreen.draw)
    assert "subpoint_at" in src and "over" in src
