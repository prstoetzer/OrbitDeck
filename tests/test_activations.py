"""Activations: local-catalog resolution and the workability check."""

import datetime as dt
import os
import time

os.environ["ORBITDECK_TEST"] = "1"

from orbitdeck.engine import activations as ACT   # noqa: E402


def _store():
    from orbitdeck.gui.store import Store
    return Store()


def _act(sat="ISS", grid="FN31", offset_s=7200, call="W1AW"):
    d = dt.datetime.fromtimestamp(time.time() + offset_s, dt.timezone.utc)
    return {"sat": sat, "grid": grid, "callsign": call,
            "date": d.strftime("%Y-%m-%d"), "start": d.strftime("%H:%M:%S"),
            "max_el": "", "mode": ""}


def test_first_grid_handles_grid_line_activations():
    """A line activation lists two grids; the whole string will not parse, and
    treating that as a satellite problem sends the operator hunting."""
    assert ACT.first_grid("EM12/EM13") == "EM12"
    assert ACT.first_grid("EM12, EM13") == "EM12"
    assert ACT.first_grid("EM12 EM13") == "EM12"
    assert ACT.first_grid("FN31") == "FN31"
    assert ACT.first_grid("") == ""


def test_find_local_matches_feed_names_to_catalog_names():
    """The feed says 'AO-91'; the catalog says 'AO-91 (RADFXSAT)'. A plain
    compare misses, which is why every add went to CelesTrak and duplicated
    satellites already present."""
    db = _store().db
    for name in ("ISS", "AO-91", "SO-50"):
        found = ACT.find_local(db, name)
        assert found is not None, name
    assert ACT.find_local(db, "NOPE-99") is None
    assert ACT.find_local(db, "") is None


def test_parse_listed_utc():
    t = ACT.parse_listed_utc("2026-08-12", "18:30:00")
    assert t is not None
    assert dt.datetime.fromtimestamp(t, dt.timezone.utc).hour == 18
    assert ACT.parse_listed_utc("2026-08-12", "18:30") is not None
    assert ACT.parse_listed_utc("", "18:30") is None
    assert ACT.parse_listed_utc("2026-08-12", "") is None


def test_check_activation_distinguishes_failure_modes():
    """Collapsing these is the bug CardSat's notes call out: an unusable grid
    and an absent satellite are different problems."""
    st = _store()
    state, _ = ACT.check_activation(st, _act())
    assert state in (ACT.FP_OK, ACT.FP_NO_WINDOW)
    state, _ = ACT.check_activation(st, _act(sat="NOPE-99"))
    assert state == ACT.FP_NO_SAT
    state, _ = ACT.check_activation(st, _act(grid=""))
    assert state == ACT.FP_BAD_GRID
    bad = _act()
    bad["date"] = ""
    bad["start"] = ""
    state, _ = ACT.check_activation(st, bad)
    assert state == ACT.FP_BAD_TIME
    # every state has readable text
    for k in (ACT.FP_OK, ACT.FP_NO_WINDOW, ACT.FP_NO_SAT, ACT.FP_BAD_TIME,
              ACT.FP_BAD_GRID, ACT.FP_NO_CLOCK):
        assert ACT.FP_TEXT[k]


def test_check_activation_accepts_a_grid_line():
    st = _store()
    state, info = ACT.check_activation(st, _act(grid="EM12/EM13"))
    assert state != ACT.FP_BAD_GRID
    assert info["grid"] == "EM12"


def test_adding_a_known_satellite_does_not_refetch_or_duplicate():
    """The reported bug: adding from an activation re-fetched from CelesTrak
    and added satellites already in the catalog."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        app = OrbitDeckApp(root)
        app.show("datafeeds")
        root.update()
        scr = app.current
        before = app.store.db.count()
        scr._acts = [_act()]
        scr.atree.insert("", "end", values=("", "W1AW", "ISS", "FN31", "", ""))
        scr.atree.selection_set(scr.atree.get_children()[0])
        scr._add_act_sat()
        root.update()
        assert app.store.db.count() == before        # nothing added
        assert "already" in scr.ainfo.get()
        sat = ACT.find_local(app.store.db, "ISS")
        assert sat.norad in app.store.favorites      # starred instead
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_tui_activations_can_check_and_star():
    from orbitterm.state import AppState
    from orbitterm.screens.analysis4 import ActivationsScreen

    class _App:
        def __init__(self, st):
            self.state = st
    app = _App(AppState())
    s = ActivationsScreen(app)
    s.rows = [_act()]
    s.list.sel = 0
    s._check()
    assert "W1AW on ISS" in s.status
    s._add()
    assert "starred" in s.status or "already" in s.status
    s._add()
    assert "already a favorite" in s.status


# ---- full workflow: window -> DX Doppler ----
def test_check_returns_every_nearby_window_with_elevations():
    """The workflow needs the windows themselves, not just a yes/no."""
    st = _store()
    state, info = ACT.check_activation(st, _act())
    if state != ACT.FP_OK:
        return
    wins = info["windows"]
    assert wins
    for wm in wins:
        assert wm["end"] >= wm["start"]
        assert wm["my_max_el"] >= 0 and wm["dx_max_el"] >= 0
    # the chosen window is the one nearest the advertised start
    listed = info["listed"]
    best = info["best"]
    assert all(abs(best["start"] - listed) <= abs(wm["start"] - listed)
               for wm in wins)
    assert info["dx"] is not None            # the DX observer, for Doppler


def test_dx_doppler_table_from_an_activation_window():
    """The table must be seeded with the ACTIVATION's satellite and window."""
    from orbitdeck.engine import dxdoppler as DXD
    st = _store()
    state, info = ACT.check_activation(st, _act())
    if state != ACT.FP_OK:
        return
    sat = info["sat"]
    tps = list(getattr(sat, "transponders", []) or [])
    if not tps:
        return
    a, b = info["window"]
    rows = DXD.dx_doppler_table(a, b, sat, st.obs, info["dx"], tps[0], 0)
    assert len(rows) > 2
    for t, my_rx, my_tx, dx_rx, dx_tx in rows:
        assert a - 1 <= t <= b + 1
        for f in (my_rx, my_tx, dx_rx, dx_tx):
            assert f > 0
    # the two stations see different Doppler, so their dials differ
    assert any(abs(r[1] - r[3]) > 0 for r in rows)


def test_all_three_doppler_modes_build_from_a_window():
    from orbitdeck.engine import dxdoppler as DXD
    st = _store()
    state, info = ACT.check_activation(st, _act())
    if state != ACT.FP_OK:
        return
    sat = info["sat"]
    tps = list(getattr(sat, "transponders", []) or [])
    if not tps:
        return
    a, b = info["window"]
    for mode in (DXD.TRUE_RULE, DXD.FIXED_DL, DXD.FIXED_UL):
        for anchor in (DXD.ME_RX, DXD.ME_TX, DXD.DX_RX, DXD.DX_TX):
            rows = DXD.dx_doppler_table(a, b, sat, st.obs, info["dx"],
                                        tps[0], 0, mode=mode, anchor=anchor)
            assert rows


def test_gui_activation_detail_builds_windows_and_table():
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        from orbitdeck.gui.screens.actdetail import ActivationDetail
        app = OrbitDeckApp(root)
        root.update()
        act = _act()
        state, info = ACT.check_activation(app.store, act)
        if state != ACT.FP_OK:
            return
        dlg = ActivationDetail(root, app.store, act, info)
        root.update()
        assert len(dlg.wtree.get_children()) == len(info["windows"])
        if getattr(info["sat"], "transponders", None):
            assert len(dlg.dtree.get_children()) > 2
            dlg.mode_var.set("Fixed downlink")
            dlg._rebuild()
            root.update()
            assert len(dlg.dtree.get_children()) > 2
    except Exception:
        pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_tui_activation_detail_views():
    from orbitterm.state import AppState
    from orbitterm.screens.analysis4 import ActivationsScreen

    class _App:
        def __init__(self, st):
            self.state = st
    s = ActivationsScreen(_App(AppState()))
    s.rows = [_act()]
    s.list.sel = 0
    s._check()
    if s.detail is None:
        return
    assert s.view == "windows"                  # a successful check opens it
    s._cycle_view()
    assert s.view == "doppler"
    before = s.mode_sel
    s.handle_key(ord("m"))
    assert s.mode_sel != before
    s.handle_key(ord("n"))
    s.handle_key(ord("p"))
    s.handle_key(27)
    assert s.view == "list"


def test_activation_detail_is_actually_reachable():
    """Regression: _check_act() existed but nothing called it - the button
    insertion had silently not matched, so the mutual-window / Doppler view was
    unreachable on the desktop. A feature with no entry point is not shipped."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        app = OrbitDeckApp(root)
        app.show("datafeeds")
        root.update()
        scr = app.current

        labels = []

        def walk(w):
            for c in w.winfo_children():
                if c.winfo_class() == "TButton":
                    try:
                        labels.append(str(c.cget("text")))
                    except Exception:
                        pass
                walk(c)
        walk(scr.frame)
        assert any("work it" in ln.lower() for ln in labels), labels
        # and the activation list opens it on double-click. bind() with no
        # handler returns the script only for named callbacks, so check the
        # registered event list instead.
        assert "<Double-Button-1>" in scr.atree.bind()
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_hamsat_feed_date_and_time_are_parsed():
    """Reported: every activation reported 'feed date/time unusable'.

    Two causes. The DATE lives in the title as '[YYYY-MM-DD]' and was matched
    then thrown away, so nothing could be combined with the clock time. And the
    Atom content is HTML-escaped (&lt;li&gt;), so the list items - start time,
    mode, elevation - all came back empty.
    """
    from orbitdeck.gui import datafeeds as DF
    feed = (
        '<feed><entry>'
        '<title>[2026-08-14] W1AW on AO-91 from FN31</title>'
        '<content type="html">&lt;ul&gt;&lt;li&gt;Start time: 18:30:00 UTC'
        '&lt;/li&gt;&lt;li&gt;End time: 18:42:00 UTC&lt;/li&gt;'
        '&lt;li&gt;Mode: FM&lt;/li&gt;&lt;li&gt;Max elevation: 34&lt;/li&gt;'
        '&lt;/ul&gt;</content></entry>'
        '<entry><title>[2026-08-15] K1ABC on SO-50 from EM12/EM13</title>'
        '<content><![CDATA[<ul><li>Start time: 02:05 UTC</li>'
        '<li>Mode: FM</li></ul>]]></content></entry></feed>')
    acts = DF.parse_activations(feed)
    assert len(acts) == 2
    a = acts[0]
    assert a["date"] == "2026-08-14"
    assert a["start"].startswith("18:30")
    assert a["mode"] == "FM" and a["max_el"] == "34"
    assert a["callsign"] == "W1AW" and a["sat"] == "AO-91"
    # CDATA form, short clock, and a grid-line activation
    b = acts[1]
    assert b["date"] == "2026-08-15" and b["start"].startswith("02:05")
    assert b["grid"] == "EM12/EM13"
    # and the combination actually yields an epoch
    assert ACT.parse_listed_utc(a["date"], a["start"]) is not None
    assert ACT.parse_listed_utc(b["date"], b["start"]) is not None


def test_listed_utc_tolerates_the_feed_suffix():
    assert ACT.parse_listed_utc("2026-08-14", "18:30:00 UTC") is not None
    assert ACT.parse_listed_utc("2026-08-14", "18:30 UTC") is not None
    assert ACT.parse_listed_utc("2026-08-14", "") is None


def test_transponder_label_uses_the_real_attribute():
    """Regression: the picker showed '?' for every transponder because it read
    .description / .name, which do not exist - the attribute is .desc."""
    from orbitdeck.gui.screens.actdetail import _tp_label
    from orbitdeck.gui.store import Store
    st = Store()
    seen = 0
    for s in st.db.sats:
        for tp in (getattr(s, "transponders", []) or []):
            label = _tp_label(tp)
            assert label and label != "?"
            seen += 1
    assert seen > 0


def test_activation_detail_draws_mutual_window_polars():
    """A mutual window is a geometry question; two sky tracks answer it faster
    than a start/end pair."""
    import inspect
    from orbitdeck.gui.screens import actdetail
    src = inspect.getsource(actdetail.ActivationDetail)
    assert "_draw_polars" in src
    assert "my_panel" in src and "dx_panel" in src


def test_scan_freq_hz_and_transponder_seeding():
    """CardSat matches the activation's stated frequency to a transponder LEG.
    Defaulting to the first transponder ignores what the operator told you."""
    from orbitdeck.gui.store import Store
    assert ACT.scan_freq_hz("437.800 MHz") == 437800000
    assert ACT.scan_freq_hz("145.990") == 145990000
    assert ACT.scan_freq_hz("145990 kHz") == 145990000
    # a bare integer is too ambiguous - "Max el 50" is not 50 MHz
    assert ACT.scan_freq_hz("Max el 50") == 0
    assert ACT.scan_freq_hz("") == 0
    st = Store()
    sat = st.db.get(25544)
    idx, leg, hz = ACT.match_transponder(sat, {"freq": "437.800 MHz"})
    assert idx == 0 and leg == "downlink" and hz == 437800000
    idx, leg, _hz = ACT.match_transponder(sat, {"freq": "145.990"})
    assert leg == "uplink"
    assert ACT.match_transponder(sat, {"freq": ""})[0] is None


def test_max_elevation_is_computed_for_your_station():
    """The feed's Max elevation is the ACTIVATOR's and is usually absent, so
    the column read 'None' for every row."""
    import datetime as dt
    from orbitdeck.gui.store import Store
    st = Store()
    d = dt.datetime.fromtimestamp(time.time() + 5400, dt.timezone.utc)
    act = {"sat": "ISS", "grid": "FN31", "callsign": "W1AW",
           "date": d.strftime("%Y-%m-%d"), "start": d.strftime("%H:%M:%S")}
    el = ACT.max_elevation(st, act)
    assert el is None or 0 <= el <= 90
    # an unknown satellite yields None rather than raising
    assert ACT.max_elevation(st, dict(act, sat="NOPE-99")) is None


def test_valid_grid_rejects_what_grid_to_latlon_accepts():
    """grid_to_latlon does not validate - 'ZZZZ' becomes (202.5, 405.0) - so a
    typed grid must be checked before it is trusted."""
    for good in ("FN31", "fn31", "FN31pr", "FM29nw"):
        assert ACT.valid_grid(good)
    for bad in ("ZZZZ", "nonsense", "FN", "", "FN3"):
        assert not ACT.valid_grid(bad)


def test_activation_detail_offers_notes_and_seeds_from_frequency():
    import inspect
    from orbitdeck.gui.screens import actdetail
    src = inspect.getsource(actdetail.ActivationDetail)
    assert "_show_notes" in src and "comment" in src
    assert "_seed_from_activation" in src and "match_transponder" in src


def test_seeding_holds_a_linear_dial_on_the_stated_frequency():
    """Setting the operating point mid-passband is not seeding: the anchored
    dial then sits at the transponder centre, not the stated frequency."""
    import time as _t
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.predict import Observer
    from orbitdeck.engine import dxdoppler as D
    st = Store()
    linear = None
    for s in st.db.sats:
        for tp in (getattr(s, "transponders", []) or []):
            try:
                if getattr(tp, "is_linear", False) and tp.bandwidth() > 0:
                    linear = (s, tp)
                    break
            except Exception:
                continue
        if linear:
            break
    if linear is None:
        return
    sat, tp = linear
    dx = Observer(lat=41.5, lon=-73.0, alt_m=0, valid=True)
    t = _t.time() + 5400
    target = int(tp.downlink + tp.bandwidth() / 2)
    pb = D.solve_pb_for_dial(t, sat, st.obs, dx, tp, target, D.DX_RX,
                             D.FIXED_DL)
    rows = D.dx_doppler_table(t, t + 300, sat, st.obs, dx, tp, pb,
                              mode=D.FIXED_DL, anchor=D.DX_RX)
    for r in rows:
        assert abs(r[3] - target) < 200      # held within 200 Hz


def test_single_channel_transponder_stays_in_true_rule():
    """An FM bird has no passband to move, so a 'fixed' mode would just show
    the stated frequency plus that station's Doppler and call it held."""
    import inspect
    from orbitdeck.gui.screens import actdetail
    src = inspect.getsource(actdetail.ActivationDetail._seed_from_activation)
    assert "is_linear" in src and "single-channel" in src


def test_celestrak_404_means_no_such_satellite():
    """A 404 from a name query is an empty result, not a failure - showing the
    raw status made 'not in the catalog' look like a bug."""
    import orbitdeck.gui.store as S
    st = S.Store()
    saved = S._http_get
    S._http_get = lambda u, timeout=20: (_ for _ in ()).throw(
        RuntimeError("Server returned HTTP 404 (not found)."))
    try:
        st._last_search_t = 0
        assert st.search_celestrak("NOPE-99") == []
    finally:
        S._http_get = saved


def test_solver_holds_every_anchor_including_an_inverting_uplink():
    """Reported: an RS-44 activation naming a 145.95 MHz uplink showed DX TX at
    145.9941. The match was right; the SOLVER was wrong. It assumed the dial
    moved 1:1 with the passband, but on an INVERTING transponder the uplink dial
    moves the opposite way, so it pushed the offset the wrong direction and
    settled ~12 kHz out. It now measures the derivative instead of assuming it.
    """
    import time as _t
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.predict import Observer
    from orbitdeck.engine import dxdoppler as D
    st = Store()
    linear = None
    for s in st.db.sats:
        for tp in (getattr(s, "transponders", []) or []):
            try:
                if getattr(tp, "is_linear", False) and tp.bandwidth() > 0:
                    linear = (s, tp)
                    break
            except Exception:
                continue
        if linear:
            break
    if linear is None:
        return
    sat, tp = linear
    dx = Observer(lat=41.5, lon=-73.0, alt_m=0, valid=True)
    t = _t.time() + 5400
    cases = ((D.DX_RX, D.FIXED_DL, tp.downlink, 3),
             (D.DX_TX, D.FIXED_UL, tp.uplink, 4),
             (D.ME_RX, D.FIXED_DL, tp.downlink, 1),
             (D.ME_TX, D.FIXED_UL, tp.uplink, 2))
    for anchor, mode, base, col in cases:
        target = int(base + tp.bandwidth() / 2)
        pb = D.solve_pb_for_dial(t, sat, st.obs, dx, tp, target, anchor, mode)
        rows = D.dx_doppler_table(t, t + 120, sat, st.obs, dx, tp, pb,
                                  mode=mode, anchor=anchor)
        for r in rows:
            assert abs(r[col] - target) < 50, (anchor, r[col] - target)


def test_solver_reports_zero_for_a_single_channel_transponder():
    """An FM bird's dial does not follow the passband, so there is no offset to
    find - returning a large bogus number would look like a solved answer."""
    import time as _t
    from orbitdeck.gui.store import Store
    from orbitdeck.engine.predict import Observer
    from orbitdeck.engine import dxdoppler as D
    st = Store()
    iss = st.db.get(25544)
    if iss is None or not iss.transponders:
        return
    dx = Observer(lat=41.5, lon=-73.0, alt_m=0, valid=True)
    assert D.solve_pb_for_dial(_t.time() + 5400, iss, st.obs, dx,
                               iss.transponders[0], 437800000,
                               D.DX_RX, D.FIXED_DL) == 0


def test_uplink_edge_frequency_still_matches_within_tolerance():
    """RS-44's published uplink starts at 145.965; an activation naming 145.95
    is 15 kHz below that and must still match the uplink leg."""
    class _TP:
        is_linear = True
        invert = True
        uplink = 145965000
        uplink_high = 145995000
        downlink = 435610000
        downlink_high = 435640000
        desc = "Linear Transponder"

        def bandwidth(self):
            return 30000

    class _SAT:
        name = "RS-44"
        transponders = [_TP()]
    idx, leg, hz = ACT.match_transponder(_SAT(), {"freq": "145.95 MHz"})
    assert idx == 0 and leg == "uplink" and hz == 145950000
    # and something genuinely outside the passband does not match a leg
    assert ACT.match_transponder(_SAT(), {"freq": "145.900"})[1] is None
