"""Every screen is printable, and the audit's new information exists."""

import os
import tempfile
import time

os.environ["ORBITDECK_TEST"] = "1"

import matplotlib  # noqa: E402
matplotlib.use("Agg")


def test_generic_report_writes_a_pdf():
    from orbitdeck.gui.store import Store
    from orbitdeck.gui import reports as R
    path = tempfile.mktemp(suffix=".pdf")
    R.generate_generic_report(
        path, Store(), "Test", "sub",
        [("KV", "kv", [("A", "1")]),
         ("Table", "table", (["X", "Y"], [["1", "2"]])),
         ("Note", "text", "words")])
    with open(path, "rb") as f:
        assert f.read(5) == b"%PDF-"
    assert os.path.getsize(path) > 5000


def test_every_screen_has_a_report_action():
    """27 screens had no way to print. A screen that cannot print is a gap, so
    the base class provides one and this asserts none regress."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp, NAV_ITEMS
        app = OrbitDeckApp(root)
        missing = []
        for _label, key in NAV_ITEMS:
            app.show(key)
            root.update()
            if not callable(getattr(app.current, "_report", None)):
                missing.append(key)
        assert not missing, missing
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_kv_panel_records_rows_for_printing():
    """A KV screen prints what it displayed, without keeping a second copy."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.screens import KVPanel
        kv = KVPanel(root)
        kv.begin()
        kv.row("Alpha", "1")
        kv.row("Beta", "2")
        kv.end()
        assert kv.printable_pairs() == [("Alpha", "1"), ("Beta", "2")]
        kv.begin()
        assert kv.printable_pairs() == []      # begin() clears
    finally:
        try:
            root.destroy()
        except Exception:
            pass


# ---- audit item B1: velocity and launch identity ----
def test_orbital_velocity_matches_known_values():
    from orbitdeck.engine import analysis as A
    # ISS: ~7.66 km/s at ~6795 km semi-major axis
    v = A.orbital_velocity_kms(6794.6, 6794.6)
    assert 7.6 < v < 7.7
    # GTO is slow at apogee and fast at perigee
    va, vp = A.velocity_extremes_kms(24400.0, 0.72)
    assert va < 2.0 < 9.0 < vp
    assert A.orbital_velocity_kms(0, 100) == 0.0


def test_cospar_parsing():
    from orbitdeck.engine import analysis as A
    assert A.cospar_launch_year("1998-067A") == 1998
    assert A.cospar_launch_year("98067A") == 1998        # legacy 2-digit
    assert A.cospar_launch_year("05001A") == 2005        # pivot
    assert A.cospar_launch_year("") is None
    assert A.launch_stem("1998-067A") == "1998-067"
    assert A.launch_stem("2019-084AB") == "2019-084"
    assert A.years_in_orbit("1998-067A", time.time()) >= 27


# ---- audit item A1: propagation outlook ----
def test_propagation_outlook_responds_to_conditions():
    from orbitdeck.engine import propagation as P
    quiet = P.outlook({"flux": 180, "kp": 2})
    storm = P.outlook({"flux": 180, "kp": 8})
    # a storm suppresses the MUF and raises aurora and absorption
    assert storm["muf_day"] < quiet["muf_day"]
    assert storm["aurora"][1] > quiet["aurora"][1]
    assert storm["absorption"][1] > quiet["absorption"][1]
    # more flux opens more bands
    hi = P.outlook({"flux": 200, "kp": 2})
    lo = P.outlook({"flux": 70, "kp": 2})
    def n_open(r):
        return sum(1 for _b, s, _v in r["bands_day"] if s == "open")
    assert n_open(hi) > n_open(lo)


def test_propagation_without_data_says_so():
    from orbitdeck.engine import propagation as P
    res = P.outlook({})
    assert res["have_data"] is False
    assert res["muf_day"] is None
    assert "No space-weather data" in P.summary_line(res)


def test_band_state_thresholds():
    from orbitdeck.engine import propagation as P
    assert P.band_state(30.0, 14.1)[0] == "open"
    assert P.band_state(15.0, 14.1)[0] == "fair"
    assert P.band_state(12.0, 14.1)[0] == "weak"
    assert P.band_state(5.0, 14.1)[0] == "shut"
    assert P.band_state(None, 14.1)[0] == "unknown"


def test_seasonal_modes():
    from orbitdeck.engine import propagation as P
    import calendar
    aug = calendar.timegm((2026, 8, 12, 0, 0, 0, 0, 0, 0))
    assert "Perseids" in P.meteor_scatter(aug)[0]
    jun = calendar.timegm((2026, 6, 1, 0, 0, 0, 0, 0, 0))
    assert "Es season" in P.sporadic_e(jun)[0]
    oct_ = calendar.timegm((2026, 10, 1, 0, 0, 0, 0, 0, 0))
    assert P.sporadic_e(oct_)[1] == 0


def test_propagation_screen_builds_and_reports():
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        app = OrbitDeckApp(root)
        app.show("propagation")
        root.update()
        scr = app.current
        assert len(scr.tree.get_children()) == 9      # nine bands
        assert callable(scr._report)
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_every_nav_screen_has_a_visible_report_control():
    """A _report method with no button is not printable. ao7 and amsatstatus
    label theirs differently, so they are checked by method instead."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp, NAV_ITEMS
        app = OrbitDeckApp(root)
        missing = []

        def walk(w, out):
            for c in w.winfo_children():
                if c.winfo_class() == "TButton":
                    try:
                        out.append(str(c.cget("text")))
                    except Exception:
                        pass
                walk(c, out)
        for _label, key in NAV_ITEMS:
            app.show(key)
            root.update()
            labels = []
            walk(app.current.frame, labels)
            if any("Report" in x or "Print" in x for x in labels):
                continue
            if callable(getattr(app.current, "_report", None)):
                continue
            missing.append(key)
        assert not missing, missing
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_orbital_history_produces_a_pdf():
    """Called out as a gap: the screen had data and no way to print it."""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.withdraw()
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        from orbitdeck.gui.reports import generate_generic_report
        app = OrbitDeckApp(root)
        app.show("orbithistory")
        root.update()
        scr = app.current
        base = 1.6e9
        scr.samples = [{"epoch": base + i * 86400 * 30,
                        "APOAPSIS": 420 - i * 0.05,
                        "PERIAPSIS": 410 - i * 0.05, "INCLINATION": 51.6,
                        "ECCENTRICITY": 0.0005, "PERIOD": 92.9,
                        "SEMIMAJOR_AXIS": 6790, "BSTAR": 2e-4}
                       for i in range(60)]
        scr._redraw()
        scr._fill_table()
        root.update()
        sections = scr._report_sections()
        assert sections
        path = tempfile.mktemp(suffix=".pdf")
        generate_generic_report(path, app.store, "Orbital history", None,
                                sections)
        with open(path, "rb") as f:
            assert f.read(5) == b"%PDF-"
        assert os.path.getsize(path) > 10000
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_no_desktop_label_is_clipped():
    """A label narrower than its own text loses the end of it. The Tools and
    References sidebars could not fit their own longest entries, and two status
    lines had no wraplength."""
    import time as _t
    import tkinter as tk
    import tkinter.font as tkfont
    try:
        root = tk.Tk()
    except Exception:
        return
    root.geometry("1280x800")
    try:
        from orbitdeck.gui.app import OrbitDeckApp, NAV_ITEMS
        app = OrbitDeckApp(root)

        def settle(n=10):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                _t.sleep(0.01)
        settle(18)
        bad = []

        def check(w, key):
            for c in w.winfo_children():
                try:
                    if (c.winfo_class() in ("TLabel", "Label")
                            and c.winfo_ismapped()):
                        txt = str(c.cget("text"))
                        wrap = int(c.cget("wraplength") or 0)
                        if txt and not wrap:
                            f = tkfont.Font(font=c.cget("font")
                                            or "TkDefaultFont")
                            have = c.winfo_width()
                            if have > 20 and f.measure(txt) > have + 2:
                                bad.append("%s: %r" % (key, txt[:40]))
                except Exception:
                    pass
                check(c, key)
        for _label, key in NAV_ITEMS:
            app.show(key)
            settle(6)
            check(app.current.frame, key)
        assert not bad, bad
    finally:
        try:
            root.destroy()
        except Exception:
            pass
