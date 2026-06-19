# OrbitDeck Engine API (`orbitdeck.engine`)

`orbitdeck.engine` is the **headless orbital core** behind OrbitDeck. It has
**no GUI dependency** (no Tkinter, no matplotlib) and only needs `numpy`, so you
can use it as a library for scripting, automation, a web backend, or your own
front end.

> **Performance note.** The engine runs on a bundled pure-Python SGP4/SDP4
> propagator out of the box, but installing the optional **`sgp4`** package
> (`pip install "orbitdeck[accurate]"`) is **strongly recommended** — it is the
> C-accelerated reference backend, is markedly faster for the repeated
> propagation that pass-finding and node-finding do, and is fully accurate for
> deep-space (GEO/HEO/Molniya) orbits where the bundled deep-space terms are
> only approximate. `orbitdeck.engine.propagator` detects and uses it
> automatically; call `have_full_sdp4()` to check which backend is active.

- [Quick start](#quick-start)
- [Public API surface](#public-api-surface)
- [Core data types](#core-data-types)
- [`SatDb` — the catalog](#satdb--the-catalog)
- [`Predictor` — propagation & geometry](#predictor--propagation--geometry)
- [Grid squares, time & backend helpers](#grid-squares-time--backend-helpers)
- [`engine.analysis` — orbital mechanics](#engineanalysis--orbital-mechanics)
- [`engine.linkbudget` — radio & visibility](#enginelinkbudget--radio--visibility)
- [`engine.planning` — targets & roves](#engineplanning--targets--roves)
- [`engine.celestial` — Sun, Moon, planets, EME](#enginecelestial--sun-moon-planets-eme)
- [Conventions & accuracy](#conventions--accuracy)

---

## Quick start

```python
import time
from orbitdeck.engine import SatDb, Predictor, Observer

# 1. Load a catalog from CelesTrak/AMSAT GP-in-JSON (an OMM array)
db = SatDb()
db.load_gp_json(open("gp.json").read())          # returns the number loaded

# 2. Point a Predictor at a site and a satellite
pred = Predictor()
pred.set_site(Observer(lat=39.93, lon=-74.89, alt_m=20, valid=True))
pred.set_sat(db.get(44909))                      # RS-44, by NORAD id

# 3. Ask it things
look = pred.look(time.time())
print(f"az {look.az:.1f}  el {look.el:.1f}  range {look.range_km:.0f} km")

for p in pred.predict_passes(time.time(), min_el=5.0, max_n=5):
    print(time.ctime(p.aos), f"max el {p.max_el:.0f}")
```

`SatEntry` objects also carry their own elements, so you can build a predictor
without a `SatDb` if you already have a `SatEntry` from elsewhere.

---

## Public API surface

Everything below is re-exported from `orbitdeck.engine`:

```python
from orbitdeck.engine import (
    SatDb, SatEntry, Transponder, satellite_category, CATEGORIES,
    Predictor, Observer, LiveLook, PassPredict, MutualWindow,
    latlon_to_grid, grid_to_latlon, jd_of, have_full_sdp4, analysis,
)
```

The submodules `linkbudget`, `planning`, and `celestial` are imported directly:

```python
from orbitdeck.engine import linkbudget, planning, celestial
```

---

## Core data types

All are plain dataclasses (cheap to construct, easy to inspect).

### `Observer`
A ground station.

| Field | Type | Meaning |
|---|---|---|
| `lat` | float | Latitude, °N (south negative) |
| `lon` | float | Longitude, °E (west negative) |
| `alt_m` | float | Site altitude, metres |
| `valid` | bool | Set `True` once you've filled it in |

### `SatEntry`
One satellite's mean elements (plus catalog metadata and any transponders).
Key fields: `name`, `norad`, `intl_des`, `epoch_unix`, `incl`, `ecc`, `raan`,
`argp`, `ma`, `mean_motion` (rev/day), `bstar`, `rev_at_epoch`, `amsat_status`,
`transponders` (a list of `Transponder`), `is_manual`.

### `Transponder`
A radio payload. Fields include `desc`, `downlink`/`uplink` (Hz, with
`_high` variants for a passband), `mode`, `invert`, `is_linear`, `tone_hz`,
`baud`, `service`. Helpers:

- `downlink_center()` / `uplink_center()` → centre frequency (Hz)
- `bandwidth()` → passband width (Hz)
- `kind()` → a short label ("Linear", "FM", "Beacon", …)

### `LiveLook`
Snapshot returned by `Predictor.look()`: `az`, `el`, `range_km`, `range_rate`
(km/s, + = receding), `sub_lat`, `sub_lon`, `alt_km`, `visible`, `sunlit`,
`sun_az`, `sun_el`.

### `PassPredict`
One pass: `aos`, `los`, `tca` (unix seconds), `max_el`, `az_aos`, `az_los`.

### `MutualWindow`
Two-station co-visibility: `start`, `end` (unix), `my_max_el`, `dx_max_el`.

---

## `SatDb` — the catalog

```python
db = SatDb()
n   = db.load_gp_json(text)        # replace catalog from a GP/OMM JSON array; -> count
n   = db.append_gp_json(text)      # merge more sats in (dedup by NORAD); -> count added
sat = db.get(25544)                # SatEntry or None, by NORAD id
i   = db.index_of_norad(25544)     # position in db.sats, or -1
c   = db.count()                   # number of satellites
```

GP-in-JSON is the OMM array CelesTrak serves (`?FORMAT=json`) and AMSAT mirrors;
each element becomes a `SatEntry`.

**Transponders** come from SatNOGS:

```python
xponders = SatDb.parse_transmitters_json(satnogs_text, max_n=64)
sat.transponders = xponders        # attach to a SatEntry
```

**Categories** for a by-type view:

```python
from orbitdeck.engine import satellite_category, CATEGORIES
satellite_category(sat)   # -> one of CATEGORIES
# CATEGORIES = ('Linear transponder', 'FM transponder', 'Digital transponder',
#               'Beacon / CW', 'Other', 'No transponder data')
```

---

## `Predictor` — propagation & geometry

Create one, then set a site and a satellite (either order). `set_sat()` returns
`False` if the elements can't be initialised.

```python
pred = Predictor()
pred.set_site(observer)
ok = pred.set_sat(sat)
```

### Instantaneous state

```python
look = pred.look(unix)                 # LiveLook (az/el/range/sub-point/sun/…)
az, el = pred.azel_at(unix)            # (deg, deg)
lat, lon, alt_km = pred.subpoint_at(unix)
lit = pred.sunlit_at(unix)             # bool, cylindrical shadow test
beta = pred.beta_angle_deg(unix)       # orbit-plane-to-Sun angle (deg)
depth = pred.eclipse_depth_deg(unix)   # how far into shadow (deg)
km = pred.footprint_radius_km(alt_km)  # ground-coverage radius
```

### Passes

```python
passes = pred.predict_passes(frm, min_el=5.0, max_n=10)
# optional: horizon_end (unix) to bound the search instead of max_n;
#           coarse_step (s) for the initial scan granularity.
for p in passes:
    print(p.aos, p.tca, p.los, p.max_el, p.az_aos, p.az_los)
```

### Equator crossings (nodes)

```python
asc  = pred.ascending_nodes(frm, to, max_n=200)   # [(unix, lon_deg), …]
desc = pred.descending_nodes(frm, to, max_n=200)
```

### Ephemeris listings (Nova-style)

```python
rows = pred.listing_rows(frm, step_s, count, visible_only=False)
# each row: {'t','az','el','range_km','range_rate','sub_lat','sub_lon',
#            'alt_km','sunlit'}
rows2 = pred.listing_rows_two(frm, step_s, count, dx=other_observer)
# adds the same geometry from a second station (for co-visibility tables)
```

### Mutual windows (two stations)

```python
wins = pred.mutual_windows(frm, dx=other_observer, min_el=5.0,
                           max_n=20, horizon_days=10)
for w in wins:
    print(w.start, w.end, w.my_max_el, w.dx_max_el)
```

### Eclipses

```python
ecl = pred.predict_eclipses(frm, max_n=64, horizon_days=1.0)
summary = pred.eclipse_daily_summary(frm, days=7)
```

### Doppler & transponder tuning (static helpers)

```python
# Corrected (heard / to-transmit) frequencies for a given range-rate:
rx_hz, tx_hz = Predictor.doppler_freqs(dl_nominal, ul_nominal, range_rate_kms,
                                       cal_dl_hz=0, cal_ul_hz=0)

# Passband edges for a linear transponder at a passband offset:
dl_hz, ul_hz = Predictor.passband_freqs(transponder, pb_offset_hz)
```

For the full Doppler **playbook** (per-time tables, full-duplex round-trip
correction, fixed-leg holding) use `engine.linkbudget` below.

### Which backend is active?

```python
pred.deepspace_approximate()   # True if the bundled approx deep-space model
                               # is being used for THIS (deep-space) satellite
```

---

## Grid squares, time & backend helpers

```python
from orbitdeck.engine import latlon_to_grid, grid_to_latlon, jd_of, have_full_sdp4

latlon_to_grid(39.93, -74.89)     # -> 'FM29' (4-char Maidenhead)
grid_to_latlon('FM29')            # -> (lat, lon) of the square centre
jd_of(unix)                       # -> Julian Date
have_full_sdp4()                  # -> True if the pip `sgp4` backend is in use
```

(For 6-character grids, see `analysis.latlon_to_grid6`.)

---

## `engine.analysis` — orbital mechanics

Pure functions over mean elements (no propagation). Useful for read-outs,
teaching, and quick estimates.

| Function | Returns |
|---|---|
| `period_min(mm)` | Orbital period (min) from mean motion |
| `semi_major_axis_km(mm)` | Semi-major axis (km) |
| `orbital_speed_kms(r_km, a_km)` | Vis-viva speed |
| `footprint_radius_deg(alt)` / `footprint_diameter_km(alt)` | Coverage cap |
| `horizon_distance_km(alt)` | Distance to the horizon from altitude |
| `slant_range_km(el_deg, alt)` | Slant range at an elevation |
| `elevation_for_central_angle_deg(γ, alt)` and its inverse `central_angle_for_elevation_deg(el, alt)` | Geometry conversions |
| `j2_rates(mm, incl, ecc)` | `(node_drift, perigee_drift)` deg/day (J2 secular) |
| `is_sun_synchronous(node_drift)` / `ltan_hours(raan, t)` | Sun-sync checks / LTAN |
| `groundtrack_shift_deg(mm)` | Westward shift per orbit |
| `repeat_ground_track(mm)` | `(revs, days)` repeat cycle or `None` |
| `true_anomaly_deg(M, ecc)` / `mean_anomaly_now_deg(...)` | Anomaly conversions |
| `time_to_perigee_apogee_s(...)` | Seconds to next perigee/apogee |
| `beta_star_deg(alt)` | Full-sun beta threshold |
| `estimate_decay_days(bstar, mm, ecc)` / `fmt_decay(days)` | Reentry estimate |
| `longest_possible_pass_min(mm, ecc)` | Best-case overhead pass length |
| `sats_for_continuous_coverage(alt, min_el)` | Constellation size estimate |
| `latlon_to_grid6(lat, lon)` | 6-char Maidenhead locator |
| `workable_grids(sub_lat, sub_lon, alt)` / `make_footprint_test(...)` | Grids inside the footprint / a predicate |

---

## `engine.linkbudget` — radio & visibility

```python
from orbitdeck.engine import linkbudget as lb

lb.doppler_shift_hz(freq_hz, range_rate_kms)
lb.observed_downlink_hz(dl_nominal_hz, range_rate_kms)
lb.uplink_for_observed_downlink_hz(ul_nominal_hz, range_rate_kms)
lb.free_space_path_loss_db(range_km, freq_hz)
lb.propagation_delay_ms(range_km)

lb.link_budget(range_km, freq_hz, tx_power_w=5.0, tx_gain_dbi=0.0,
               rx_gain_dbi=0.0, line_loss_db=1.0, other_loss_db=0.0)   # -> dict

# Tuning tables for a pass:
lb.doppler_playbook_rows(times, range_rates, dl_nominal_hz, ul_nominal_hz=0,
                         is_linear=False, invert=False, hold='downlink')
lb.linear_fixed_leg_playbook(dl_center_hz, ul_center_hz, range_rate_kms,
                             invert, hold='downlink')

# Optical visibility & pass scoring:
lb.is_optically_visible(sat_sunlit, observer_sun_el_deg, sat_el_deg)
lb.apparent_magnitude(std_mag, range_km, phase_angle_deg)
lb.pass_quality_score(max_el_deg, duration_s, sunlit_frac=None)   # 0–100

# Element trust & sat-to-sat:
lb.element_age_days(epoch_unix, now_unix)
lb.trust_level(age_days)                 # (label, confidence 0–1)
lb.along_track_error_km(age_days, mm=15.0)
lb.sat_to_sat_los(r1, r2)                # ECI line-of-sight test
```

---

## `engine.planning` — targets & roves

```python
from orbitdeck.engine import planning

# When can I work a distant grid/state/DXCC target via this satellite?
planning.best_passes_for_target(pred, obs, tgt_lat, tgt_lon, frm,
                                hours=72.0, min_el=0.0, max_results=20)

planning.both_in_footprint(pred, t, obs_lat, obs_lon, tgt_lat, tgt_lon)  # bool

# Rove planning: passes for one stop within a time-window hint
planning.rove_stop_passes(pred, stop_lat, stop_lon, frm, to, min_el=5.0)

# Aggregate passes into an az×el sky-occupancy grid (for heat maps)
planning.sky_coverage_grid(pred, obs, passes, az_bins=36, el_bins=9)

# Apply a per-azimuth horizon mask to a pass
planning.horizon_mask_apply(pred, p, mask_func, step_s=10.0)
```

---

## `engine.celestial` — Sun, Moon, planets, EME

```python
from orbitdeck.engine import celestial as cel

cel.source_azel('Sun', lat, lon, t)        # az/el of Sun/Moon/a planet/etc.
cel.moon_azel(lat, lon, t)
cel.planet_azel('Jupiter', lat, lon, t)
cel.planet_radec('Mars', t)                # geocentric RA/Dec
cel.radec_to_azel(ra, dec, lat, lon, t)
cel.moon_distance_km(t)

# Earth–Moon–Earth (moonbounce) planning:
cel.eme_path_loss_db(freq_hz, t)
cel.eme_doppler_hz(freq_hz, lat, lon, t)
cel.eme_window(lat1, lon1, lat2, lon2, t, hours=24.0, min_el=0.0)
cel.sky_temperature_k(galactic_lat_deg=None, freq_mhz=144.0)

# Satellite-to-satellite line-of-sight windows:
cel.sat_to_sat_windows(pred1, pred2, t, hours=24.0)
```

---

## Conventions & accuracy

- **Time** is **Unix seconds (UTC)** everywhere (`time.time()`); helpers convert
  to Julian Date where needed.
- **Angles** are **degrees**; latitude °N, longitude °E (west negative).
- **Range-rate** is from the **SGP4 velocity vector** (not slant-range
  differencing); positive = receding (so downlink Doppler is negative).
- **Gravity model** is **WGS72** to match GP/TLE mean elements.
- **Eclipse** uses a cylindrical Earth-shadow test; **beta** is the
  orbit-plane-to-Sun angle.
- **Propagator:** the bundled pure-Python SGP4/SDP4 matches the Vallado
  *AIAA-2006-6753* reference to ~1 cm at epoch and tracks the reference `sgp4`
  package to well under a kilometre across a typical LEO pass. For deep-space
  orbits (period ≥ 225 min) install the **`sgp4`** extra for full SDP4 accuracy
  and speed — `deepspace_approximate()` tells you when the approximate model is
  active for a given object.

See also: [`docs/MANUAL.md`](MANUAL.md) (the application), and
[`docs/INSTALL.md`](INSTALL.md) for installing the optional backends.
