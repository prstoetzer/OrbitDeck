"""Tiny BASIC: the CardSat dialect, ported source-compatible."""

import pytest

from orbitdeck.engine import tinybasic as TB


def run(src, **kw):
    return TB.run_source(src, **kw)


def test_print_loops_and_arithmetic():
    r = run("10 PRINT \"HELLO\"\n20 FOR I=1 TO 3\n30 PRINT I*I\n40 NEXT\n50 END")
    assert r.out == ["HELLO", "1", "4", "9"]


def test_multiple_statements_on_one_line():
    assert run('10 A=5:B=7:PRINT A+B').out == ["12"]


def test_gosub_and_return():
    r = run("10 GOSUB 100\n20 PRINT \"back\"\n30 END\n"
            "100 PRINT \"sub\"\n110 RETURN")
    assert r.out == ["sub", "back"]
    with pytest.raises(TB.BasicError):
        run("10 RETURN")


def test_if_then_takes_any_statement():
    """CardSat's notes record that a hand-picked subset after THEN made
    'IF C=3 THEN TEXT ...' fall through to assignment and report
    'unknown name'."""
    r = run('10 C=3\n20 IF C=3 THEN TEXT 5,5,"yes"\n30 END')
    assert [g.op for g in r.gfx] == ["text"]
    # a bare line number after THEN is an implicit GOTO
    r = run('10 X=1\n20 IF X=1 THEN 50\n30 PRINT "no"\n50 PRINT "yes"')
    assert r.out == ["yes"]


def test_data_read_restore_and_arrays():
    r = run("10 DIM @(3)\n20 FOR I=0 TO 2\n30 READ @(I)\n40 NEXT\n"
            "50 PRINT @(0)+@(1)+@(2)\n60 DATA 10,20,30")
    assert r.out == ["60"]
    assert run("10 DIM A(4)\n20 A(2)=9\n30 PRINT A(2)").out == ["9"]
    with pytest.raises(TB.BasicError):
        run("10 READ X")                     # no DATA at all


def test_on_goto_out_of_range_falls_through():
    """Classic behavior, and what CardSat does."""
    assert run("10 N=2\n20 ON N GOTO 100,200\n"
               "100 PRINT \"one\"\n110 END\n200 PRINT \"two\"").out == ["two"]
    assert run("10 N=9\n20 ON N GOTO 100\n30 PRINT \"fell\"\n40 END\n"
               "100 PRINT \"one\"").out == ["fell"]


def test_functions_use_degrees_like_the_card():
    r = run("10 PRINT SIN(90)\n20 PRINT COS(0)\n30 PRINT SQR(16)\n"
            "40 PRINT MAX(3,7)\n50 PRINT INT(3.9)")
    assert r.out == ["1", "1", "4", "7", "3"]


def test_errors_carry_the_line_number():
    with pytest.raises(TB.BasicError) as e:
        run("10 PRINT 1/0")
    assert e.value.line == 10 and "divide" in str(e.value)
    with pytest.raises(TB.BasicError):
        run("10 GOTO 999")


def test_immediate_mode_bans_program_only_statements():
    """With no line table a GOTO silently falls through, so refuse it."""
    for kw in ("GOTO 10", "GOSUB 10", "RETURN", "READ X", "RESTORE"):
        with pytest.raises(TB.BasicError):
            run(kw)
    # ...but the same word inside a string is fine
    assert run('PRINT "GOTO"').out == ["GOTO"]


def test_graphics_use_the_cards_coordinate_space():
    """240x135 and ten palette indices, so a program is portable both ways."""
    assert (TB.GFX_W, TB.GFX_H) == (240, 135)
    assert len(TB.PALETTE) == 10
    r = run("10 CLS\n20 PSET 10,20,2\n30 LINE 0,0,239,134,3\n"
            "40 CIRCLE 120,67,50\n50 TEXT 4,4,\"HI\"\n60 SHOW")
    ops = [g.op for g in r.gfx]
    assert ops == ["cls", "pset", "line", "circle", "text", "show"]
    assert r.gfx[1].args == (10.0, 20.0, 2.0)
    assert r.gfx[3].args[3] == 1          # color defaults to white
    assert r.gfx[4].text == "HI"


def test_input_is_collected_before_the_run():
    """As on the card: the interpreter never re-enters an event loop with a
    live program on the stack, so behavior cannot diverge."""
    prog = TB.Program("10 INPUT A\n20 INPUT B\n30 PRINT A+B")
    assert prog.input_prompts() == ["A", "B"]
    vm = TB.Interpreter(prog, inputs=[2, 40]).run()
    assert vm.out == ["42"]


def test_runaway_programs_are_bounded():
    with pytest.raises(TB.BasicError):
        TB.Interpreter(TB.Program("10 GOTO 10"), max_steps=5000).run()


def test_card_only_statements_are_refused_not_ignored():
    """Silently doing nothing would make a program look like it worked."""
    for src in ('10 FOPEN "x"', "10 FPRINT 1", "10 SATSEL 1", "10 TXSEL 1"):
        with pytest.raises(TB.BasicError):
            run(src)


def test_screen_scales_by_a_whole_number_and_is_registered():
    from orbitdeck.gui.app import NAV_ITEMS
    assert "tinybasic" in [k for _l, k in NAV_ITEMS]
    import inspect
    from orbitdeck.gui.screens import tinybasic as scr
    src = inspect.getsource(scr.TinyBasicScreen)
    assert "_geometry" in src and "// TB.GFX_W" in src
    # the display clips to the card's screen, or the same program would draw a
    # different picture on each machine
    assert "_mask" in src and "clip" in src


# ---- system names, SATSEL/TXSEL and file statements ----
def _host():
    import os
    os.environ["ORBITDECK_TEST"] = "1"
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.basichost import BasicHost
    return BasicHost(Store())


def test_system_names_read_zero_without_a_host():
    """Unavailable data reads 0 with its OK flag at 0, so a program branches
    instead of halting - the whole point of the ...OK convention."""
    r = run('10 PRINT SATAZ, " ", SATOK, " ", MYLAT')
    assert r.out == ["0 0 0"]


def test_system_names_reject_a_partial_match():
    """'KP1' must be an error, not KP followed by 1."""
    with pytest.raises(TB.BasicError):
        run("10 PRINT KP1")


def test_satsel_reads_live_satellite_data():
    host = _host()
    vm = TB.Interpreter(TB.Program(
        '10 SATSEL 0\n20 PRINT SATOK, " ", SATNOR, " ", NTX'), host=host).run()
    parts = vm.out[0].split()
    assert parts[0] == "1"                    # SATOK
    assert int(parts[1]) > 0                  # a real NORAD number


def test_satsel_bad_index_is_an_error():
    host = _host()
    with pytest.raises(TB.BasicError):
        TB.Interpreter(TB.Program("10 SATSEL 9999"), host=host).run()


def test_satsel_clears_a_stale_transponder():
    """A previous TXSEL is stale once the satellite changes; the card's notes
    record that silently keeping it was the old trap."""
    host = _host()
    vm = TB.Interpreter(TB.Program(
        "10 SATSEL 0\n20 TXSEL 0\n30 PRINT TXOK\n"
        "40 SATSEL 1\n50 PRINT TXOK"), host=host).run()
    assert vm.out == ["1", "0"]


def test_catalog_scan_survives_an_unpropagatable_satellite():
    host = _host()
    vm = TB.Interpreter(TB.Program(
        "10 FOR I=0 TO NSAT-1\n20 SATSEL I\n30 IF SATOK=0 THEN 50\n"
        "40 PRINT SATNOR\n50 NEXT"), host=host).run()
    assert len(vm.out) >= 1


def test_file_statements_write_to_a_sandboxed_directory(tmp_path):
    host = _host()
    vm = TB.Interpreter(TB.Program(
        '10 FOPEN "log.txt"\n20 FPRINT "hello ", 42\n30 FCLOSE\n40 FILES'),
        host=host, file_dir=str(tmp_path)).run()
    assert (tmp_path / "log.txt").read_text().strip() == "hello 42"
    assert "log.txt" in vm.out[0]


def test_file_names_cannot_escape_the_directory(tmp_path):
    host = _host()
    for bad in ("../escape.txt", "/etc/passwd", ".hidden", "a/b.txt"):
        with pytest.raises(TB.BasicError):
            TB.Interpreter(TB.Program('10 FOPEN "%s"' % bad),
                           host=host, file_dir=str(tmp_path)).run()


def test_fprint_without_fopen_is_an_error(tmp_path):
    with pytest.raises(TB.BasicError):
        TB.Interpreter(TB.Program('10 FPRINT "x"'),
                       file_dir=str(tmp_path)).run()


def test_file_writing_off_when_no_directory_is_configured():
    with pytest.raises(TB.BasicError):
        run('10 FOPEN "x.txt"')


def test_screen_text_does_not_mention_the_card():
    """The screen describes the canvas, not where the dialect came from."""
    import pathlib
    text = pathlib.Path("orbitdeck/gui/screens/tinybasic.py").read_text()
    assert "CardSat" not in text
    assert "240" in text and "135" in text


def test_rem_comments_to_end_of_line_including_colons():
    """A comment is prose, and prose contains colons. Splitting through one
    left the remainder to be parsed as code, so a line that is entirely a
    comment reported a syntax error."""
    from orbitdeck.engine.tinybasic import _split_statements
    assert _split_statements("REM Sky plot: every satellite") == \
        ["REM Sky plot: every satellite"]
    # a trailing REM swallows the rest, but the statement before it still runs
    assert run("10 X=5 : REM why: because\n20 PRINT X").out == ["5"]
    # quoted colons are unaffected
    assert _split_statements('PRINT "a:b" : X=2') == ['PRINT "a:b" ', ' X=2']
    # REMARK is not REM
    assert len(_split_statements("REMARK=1 : PRINT REMARK")) == 2
    assert run("10 REM note: with a colon\n20 PRINT \"ok\"").out == ["ok"]
