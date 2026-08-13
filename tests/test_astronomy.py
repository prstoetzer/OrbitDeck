"""The observing-astronomy set from CardSat 0.9.76."""

import time

import pytest

from orbitdeck.engine import astronomy as AS

LAT, LON = 39.93, -74.89


def test_meteor_showers_are_sorted_and_answer_the_radio_question():
    rows = AS.meteor_showers(LAT, LON, time.time())
    assert len(rows) == 11
    assert [r["days"] for r in rows] == sorted(r["days"] for r in rows)
    for r in rows:
        assert -90 <= r["radiant_el"] <= 90
        assert 0.0 <= r["moon_illum"] <= 1.0
        assert r["verdict"]
        # a radiant below the horizon must never be called workable
        if r["radiant_el"] < 0:
            assert "below horizon" in r["verdict"]
    names = [r["name"] for r in rows]
    assert "Perseids" in names and "Geminids" in names


def test_jupiter_cml_and_io_phase_advance_at_the_right_rate():
    """CML III turns once per 9h55m; Io orbits in 42.5 h. Wrong rates would
    put every storm window in the wrong place."""
    t = time.time()
    c0, i0 = AS.jupiter_cml_io(t)
    c1, i1 = AS.jupiter_cml_io(t + 86400)
    assert 0 <= c0 < 360 and 0 <= i0 < 360
    # one day of System III rotation
    assert abs(((c1 - c0) % 360) - (870.536 % 360)) < 0.01
    assert abs(((i1 - i0) % 360) - (203.4889538 % 360)) < 0.01


def test_jupiter_windows_require_jupiter_to_be_up():
    """A storm you cannot hear is not a window."""
    t = time.time()
    for w in AS.jupiter_windows(LAT, LON, t, hours=48):
        assert w["max_el"] > 0
        assert w["end"] >= w["start"]
        assert w["source"] in ("Io-A", "Io-B", "Io-C")


def test_aurora_uses_magnetic_not_geographic_latitude():
    """The oval follows the dipole: at the same geographic latitude the UK and
    Labrador are in very different places for aurora."""
    uk = AS.magnetic_latitude(55.0, -4.0)
    labrador = AS.magnetic_latitude(55.0, -60.0)
    assert abs(uk - labrador) > 5
    a = AS.aurora_outlook(65.0, -147.0, kp=5)      # Fairbanks
    assert a["boundary"] == pytest.approx(56.5)
    assert "likely" in a["visual"]
    low = AS.aurora_outlook(25.0, -80.0, kp=2)     # Florida
    assert "unlikely" in low["visual"]
    # no Kp is reported, not guessed
    assert AS.aurora_outlook(LAT, LON, None)["kp"] is None


def test_twilight_crossings_are_ordered_and_allow_polar_days():
    rows = AS.twilight_times(LAT, LON)
    assert [r["altitude"] for r in rows] == [-0.833, -6.0, -12.0, -18.0]
    # NOT morning < evening: the table covers a UTC day, so at western
    # longitudes the evening crossing falls earlier in that day than the
    # morning one (civil dusk 00:29 UTC, civil dawn 09:40 UTC at -75 deg).
    # Both must simply land inside the day.
    day0 = AS._utc_midnight(time.time())
    for r in rows:
        for v in (r["morning"], r["evening"]):
            if v is not None:
                assert day0 <= v <= day0 + 86400
    # Svalbard at midsummer: the Sun never drops below +11 deg, so NO phase
    # has a crossing. Reported as dashes rather than invented times.
    polar = AS.twilight_times(78.0, 15.0,
                              day_start=AS.calendar_timegm(2026, 6, 21, 0))
    assert all(r["morning"] is None and r["evening"] is None for r in polar)


def test_eme_conditions_bracket_the_current_distance():
    c = AS.eme_conditions(time.time())
    assert c["perigee_km"] <= c["distance_km"] <= c["apogee_km"] + 1
    assert 350000 < c["perigee_km"] < 375000
    assert 380000 < c["apogee_km"] < 410000
    # the monthly swing is about 2 dB two-way
    assert 1.0 < c["swing_db"] < 3.0
    assert c["degradation_db"] >= -0.01


def test_occultations_distinguish_a_hit_from_a_near_miss():
    """A coarse scan reported 1.05 deg against a 0.27 deg limb and called it an
    occultation. The minimum is refined, then classified honestly."""
    rows = AS.occultations(LAT, LON, time.time(), days=365)
    for r in rows:
        assert r["moon_el"] > 0            # someone else's event otherwise
        assert r["separation_deg"] < 1.0
        assert r["occultation"] == (r["separation_deg"]
                                    < r["semidiameter_deg"])
        assert 0.2 < r["semidiameter_deg"] < 0.3


def test_appulses_are_close_pairings_only():
    rows = AS.appulses(time.time(), days=365, max_sep=2.0)
    for r in rows:
        assert r["separation_deg"] < 2.0
        assert r["a"] != r["b"]
    assert [r["time"] for r in rows] == sorted(r["time"] for r in rows)


def test_comet_solver_holds_its_invariants():
    """Halley: q=0.586, e=0.967. At perihelion r must equal q; half a period
    later it must reach aphelion; and the orbit must be time-symmetric."""
    q, e = 0.586, 0.967
    args = (q, e, 162.26, 58.42, 111.33)
    peri = AS.comet_position(*args, tp_days=0.0)
    assert peri["r_au"] == pytest.approx(q, abs=1e-6)
    a = q / (1 - e)
    period_days = a ** 1.5 * 365.25
    assert period_days / 365.25 == pytest.approx(74.8, abs=0.5)
    apo = AS.comet_position(*args, tp_days=period_days / 2)
    assert apo["r_au"] == pytest.approx(a * (1 + e), rel=1e-3)
    fwd = AS.comet_position(*args, tp_days=200.0)
    back = AS.comet_position(*args, tp_days=-200.0)
    assert fwd["r_au"] == pytest.approx(back["r_au"], rel=1e-9)
    # the parabolic branch: Kepler's equation degenerates at e = 1
    par = AS.comet_position(1.0, 1.0, 90.0, 0.0, 0.0, 0.0)
    assert par["r_au"] == pytest.approx(1.0, abs=1e-6)
    # and it produces a real sky position
    sky = AS.comet_position(*args, tp_days=0.0, lat=LAT, lon=LON)
    assert 0 <= sky["ra_deg"] < 360 and -90 <= sky["dec_deg"] <= 90
    assert 0 <= sky["elongation_deg"] <= 180
    assert "az" in sky and "el" in sky


def test_astronomy_is_on_both_front_ends():
    from orbitdeck.gui.app import NAV_ITEMS
    import orbitterm.app as A
    assert "astronomy" in [k for _l, k in NAV_ITEMS]
    assert "astronomy" in [n[0] for n in A.NAV]
    from orbitterm.screens.analysis4 import AstronomyScreen
    assert len(AstronomyScreen.VIEWS) == 8


# ---- eclipses ----
def test_eclipse_matches_the_published_canon():
    """The 28 August 2026 partial lunar eclipse: umbral magnitude 0.93 at
    04:13 UT. Anything that cannot reproduce a known eclipse should not be
    shown to an operator as one."""
    t0 = AS.calendar_timegm(2026, 8, 12, 0)
    rows = AS.eclipses(39.93, -74.89, t0, days=730)
    aug = [r for r in rows
           if r["kind"] == "lunar"
           and time.gmtime(r["max_time"])[:3] == (2026, 8, 28)]
    assert aug, [time.strftime("%Y-%m-%d", time.gmtime(r["max_time"]))
                 for r in rows]
    e = aug[0]
    assert e["class_name"] == "partial"
    assert e["magnitude"] == pytest.approx(0.93, abs=0.05)
    tm = time.gmtime(e["max_time"])
    assert (tm.tm_hour, tm.tm_min) == pytest.approx((4, 13), abs=5)


def test_eclipse_classes_keep_the_deepest_not_the_shallowest():
    """CardSat's harness caught the old form keeping the SHALLOWEST class,
    which called a total eclipse penumbral."""
    import inspect
    src = inspect.getsource(AS._lunar_eclipse)
    assert "DEEPEST" in src or "deepest" in src
    assert "c > cls" in src


def test_solar_eclipses_are_topocentric_and_local():
    """The Moon's ~1 degree parallax IS the locality of a solar eclipse:
    geocentric geometry would report the same event for the whole planet."""
    import inspect
    src = inspect.getsource(AS._solar_eclipse)
    assert "_observer_eq_km" in src
    t0 = AS.calendar_timegm(2026, 8, 12, 0)
    for r in AS.eclipses(39.93, -74.89, t0, days=730):
        if r["kind"] == "solar":
            assert r["visible"]                  # only listed when Sun is up
            assert r["elevation"] > -0.5
        assert r["start"] <= r["max_time"] <= r["end"]
        assert 0 <= r["class"] <= 2


def test_moon_model_carries_the_main_perturbations():
    """The earlier model had only the equation of the center and ran 1-2
    degrees out - invisible on a pointing readout, fatal for eclipses. And
    Schlyter's epoch is 1999-12-31.0, not J2000: using J2000 shifted the mean
    longitude by 19.8 degrees."""
    import inspect
    from orbitdeck.engine import celestial
    src = inspect.getsource(celestial.moon_ecliptic)
    assert "2451543.5" in src                    # the right epoch
    assert "1.274" in src and "0.658" in src     # evection and variation
    # distance comes from the same solution, not a separate series
    dsrc = inspect.getsource(celestial.moon_distance_km)
    assert "moon_ecliptic" in dsrc
    lon, lat, dist = celestial.moon_ecliptic(2451545.0)
    assert 0 <= lon < 360 and -6 < lat < 6
    assert 356000 < dist < 407000


def test_eclipses_appear_on_both_front_ends():
    from orbitdeck.gui.screens.astronomy import TABS
    assert "Eclipses" in TABS
    from orbitterm.screens.analysis4 import AstronomyScreen
    assert "eclipses" in AstronomyScreen.VIEWS


def test_eclipse_ground_track_lands_where_the_almanac_says():
    """The 12 August 2026 total solar eclipse: greatest eclipse at 65.2N
    25.2W, 17:46 UT."""
    g = AS.eclipse_axis_ground(AS.calendar_timegm(2026, 8, 12, 17) + 46 * 60)
    assert g is not None
    lat, lon = g
    assert lat == pytest.approx(65.2, abs=1.5)
    assert lon == pytest.approx(-25.2, abs=2.0)


def test_ground_track_splits_at_the_date_line():
    """Joining points across the date line would draw a stripe straight across
    the map, which is why the track is segments rather than one polyline."""
    t0 = AS.calendar_timegm(2026, 8, 12, 0)
    rows = AS.eclipses(39.93, -74.89, t0, days=730)
    solar = [r for r in rows if r["kind"] == "solar"]
    assert solar
    for ev in solar:
        for seg in AS.eclipse_ground_track(ev):
            assert len(seg) > 1
            for i in range(len(seg) - 1):
                assert abs(seg[i + 1][1] - seg[i][1]) < 180.0
                assert -90 <= seg[i][0] <= 90


def test_a_partial_only_eclipse_says_so_rather_than_drawing_nothing():
    """No intersection means the axis misses the Earth entirely. An empty map
    with no explanation reads as a bug."""
    lunar = {"kind": "lunar", "max_time": time.time()}
    assert AS.eclipse_ground_track(lunar) == []
    assert "no ground track" in AS.eclipse_track_summary(lunar)
    assert AS.eclipse_ground_track(None) == []
    # a real solar event produces a described line
    t0 = AS.calendar_timegm(2026, 8, 12, 0)
    solar = [r for r in AS.eclipses(39.93, -74.89, t0, days=730)
             if r["kind"] == "solar"]
    text = AS.eclipse_track_summary(solar[0])
    assert "Central line" in text or "Partial-only" in text


def test_the_track_is_on_both_front_ends():
    import inspect
    from orbitdeck.gui.screens import astronomy as gscr
    assert "eclipse_ground_track" in inspect.getsource(gscr.AstronomyScreen)
    from orbitterm.screens.analysis4 import AstronomyScreen
    assert "ecltrack" in AstronomyScreen.VIEWS
    assert "eclipse_ground_track" in inspect.getsource(
        AstronomyScreen._v_ecltrack)


def test_every_astronomy_tab_actually_displays_content():
    """Three tabs rendered blank: KVPanel builds rows between begin() and
    end(), and end() is what packs them. Without those calls the widgets were
    constructed and never shown - so a test that only counted widgets, as mine
    did, passed while the screen was empty."""
    import time as _t
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception:
        return
    root.geometry("1280x820")
    try:
        from orbitdeck.gui.app import OrbitDeckApp
        from orbitdeck.gui.screens.astronomy import TABS
        app = OrbitDeckApp(root)

        def settle(n=8):
            for _ in range(n):
                root.update_idletasks()
                root.update()
                _t.sleep(0.01)
        settle(14)
        app.show("astronomy")
        settle(8)
        scr = app.current
        blank = []
        for i, name in enumerate(TABS):
            scr.tabs.select(i)
            settle(6)
            shown = []

            def walk(w):
                for c in w.winfo_children():
                    if c.winfo_class() == "Treeview":
                        shown.extend(c.get_children())
                    else:
                        try:
                            txt = str(c.cget("text"))
                            # mapped AND laid out: an unpacked label reports
                            # height 1, which is how the blank tabs slipped by
                            if txt and c.winfo_ismapped() \
                                    and c.winfo_height() > 1:
                                shown.append(txt)
                        except Exception:
                            pass
                    walk(c)
            walk(scr.pages[i])
            if not shown:
                blank.append(name)
        assert not blank, blank
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_jupiter_windows_span_long_enough_to_find_one():
    """A source has to be active AND Jupiter above the horizon; 48 hours often
    contains no overlap at all, so an empty table read as a broken screen."""
    import inspect
    from orbitdeck.gui.screens import astronomy as gscr
    from orbitterm.screens import analysis4
    for src in (inspect.getsource(gscr.AstronomyScreen._tab_1),
                inspect.getsource(analysis4.AstronomyScreen._v_jupiter)):
        assert "24 * 14" in src
    # and over a fortnight there is normally something to show
    wins = AS.jupiter_windows(39.93, -74.89, time.time(), hours=24 * 14)
    assert wins
    for w in wins:
        assert w["max_el"] > 0 and w["end"] > w["start"]
