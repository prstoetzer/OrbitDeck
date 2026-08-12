# Porting CardSat tools to OrbitDeck

CardSat (the ESP32 hardware tracker OrbitDeck was originally ported from) has
grown a large set of tools since OrbitDeck last tracked it — by CardSat 0.9.61
the Tools hub alone holds **54 tools**, plus a number of new orbital/analysis
view screens, games and a Tiny BASIC. This document inventories every CardSat
tool, marks what is **portable** vs **out of scope**, records what OrbitDeck
**already has**, and tracks porting progress.

**Scope rule (from the OrbitDeck project spec):** radio (CAT) control and
antenna-rotator control are intentionally *not* ported. Everything else — the
analysis views and the pure computational tools — is fair game. A handful of
tools are *seeded* from radio/rotator state on CardSat (e.g. pointing-loss error
seeded from the rotator deadband); those port fine as plain calculators, just
without the hardware seeding.

---

## Status legend

- ✅ **Done** — ported and tested in OrbitDeck this effort.
- 🟩 **Have** — OrbitDeck already had equivalent functionality.
- ⬜ **To do** — portable, not yet done.
- 🚫 **Out of scope** — radio/rotator hardware control, or hardware-only.

---

## Bench calculators (Tools hub)

Ported into `orbitdeck/engine/toolcalc.py` as pure functions returning
`(label, value, note)` rows. Formulas are faithful to CardSat `src/app.cpp`.

### Antennas & feedline
| CardSat tool | Status | Notes |
| --- | --- | --- |
| Dipole length | ✅ | `toolcalc.dipole` |
| Vertical / ground plane | ✅ | `toolcalc.vertical` |
| Yagi elements | ✅ | `toolcalc.yagi` |
| Quad (full-wave loop) | ✅ | `toolcalc.quad` |
| Helix antenna | ✅ | `toolcalc.helix` |
| Wavelength / frequency | ✅ | `toolcalc.wavelength` |
| Coax loss / power | ✅ | `toolcalc.coax_loss` |
| Phasing line / stub | ✅ | `toolcalc.phasing_line` |
| L/Pi/T match network | ✅ | `toolcalc.match_network` |
| Microstrip/stripline Z0 | ✅ | `toolcalc.microstrip` |

### RF & measurement
| CardSat tool | Status | Notes |
| --- | --- | --- |
| RF units (dBm/W/V) | ✅ | `toolcalc.rf_units` |
| SWR / return loss | ✅ | `toolcalc.swr` |
| Free-space path loss | ✅ | `toolcalc.fspl` (also in engine.linkbudget) |
| Attenuator pad | ✅ | `toolcalc.attenuator` |
| dB chain sum | ✅ | `toolcalc.db_chain` |
| Cascade NF & G/T | ✅ | `toolcalc.cascade_nf` |
| Link budget | 🟩 | `engine.linkbudget.link_budget` |
| Sun-noise G/T measure | ✅ | `toolcalc.sun_noise_gt` |
| IMD products | ✅ | `toolcalc.imd_products` |
| RF exposure (MPE) | ✅ | `toolcalc.rf_exposure` |

### Electronics & power
| CardSat tool | Status | Notes |
| --- | --- | --- |
| Complex / polar | ✅ | `toolcalc.complex_polar` |
| Reactance & resonance | ✅ | `toolcalc.reactance` |
| RC/RL time constant | ✅ | `toolcalc.rc_time_constant` |
| Battery runtime | ✅ | `toolcalc.battery_runtime` |
| Cross-section area | ✅ | `toolcalc.cross_section` |
| Thermal equilibrium | ✅ | `toolcalc.thermal_equilibrium` |
| Trace & wire ampacity | ✅ | `toolcalc.ampacity` |
| Toroid winding | ✅ | `toolcalc.toroid_winding` |
| PLL / frequency plan | ✅ | `toolcalc.pll_plan` |

### Terrestrial VHF/UHF/microwave
| CardSat tool | Status | Notes |
| --- | --- | --- |
| Radio horizon (VHF+) | ✅ | `toolcalc.radio_horizon` |
| Fresnel zone clearance | ✅ | `toolcalc.fresnel_zone` |
| Rain fade (microwave) | ✅ | `toolcalc.rain_fade` (ITU-R P.838) |
| Terrestrial path budget | ✅ | `toolcalc.terrestrial_path_budget` |
| Tropo ducting index | ✅ | `toolcalc.tropo_ducting` (manual inputs) |
| Terrain path profile | ✅ | `engine/terrain.py`: LOS calc in Tools + Open-Meteo fetch helper |

### Satellite & orbit tools
| CardSat tool | Status | Notes |
| --- | --- | --- |
| Location converter | 🟩 | OrbitDeck grid tools / `engine.analysis` |
| Orbit lifetime (debris) | 🟩 | `engine.analysis.estimate_decay_days` |
| Doppler budget (orbit) | ✅ | `toolcalc.doppler_budget` |
| Delta-v (Hohmann/plane) | ✅ | `toolcalc.delta_v` |
| Pointing loss | ✅ | `toolcalc.pointing_loss` |
| Polarization / Faraday | ✅ | `toolcalc.faraday_rotation` |
| State vector → GP | ✅ | Tools → `statevector.rv_to_elements` (osculating) |
| Conjunction screener | ✅ | `engine/conjunction.py` + screen |
| Orbital neighborhood | ✅ | `engine/conjunction.py` neighborhood tab |
| Transponder planner | ✅ | Radio → Passband plan tab (`passband_plan`) |
| Link margin vs elevation | ✅ | Tools → `link_margin_vs_elevation` |
| Debris group screen | ✅ | debris groups added to CelesTrak source list |

### Reference / lookup browsers
| CardSat tool | Status | Notes |
| --- | --- | --- |
| DXCC entity lookup | 🟩 | Workable → DXCC + planning DXCC picker |
| CQ / ITU zones | ✅ | References screen (`refdata`) |
| CTCSS tone reference | ✅ | References screen (`refdata`) |
| Operating / Radio-math references | ✅ | References (Q-codes) + Tools |
| Char lookup (ASCII/RTTY) | ✅ | References → ASCII table |
| Unit converter | ✅ | folded into `rf_units`/`wavelength` output |

---

## Analysis & orbital view screens

| CardSat screen | Status | Notes |
| --- | --- | --- |
| Pass detail / polar / sky-track | 🟩 | `gui/screens/passdetail.py` |
| Visible-pass list | 🟩 | `gui/screens/passes.py` |
| Multi-sat schedule (Next Passes) | 🟩 | `gui/screens/passes.py` |
| Sun/Moon tracking | 🟩 | `gui/screens/sunmoon.py` |
| Sun/Moon transits | ✅ | done in Phase 3a |
| Sky sources / star map | ✅ | `engine/skymap.py` + Sky Map screen (1018-star catalog) |
| Simulation (time-step) | 🟩 | `gui/screens/oscarsim.py` / analytics |
| Sat-to-sat visibility | 🟩 | `gui/screens/mutual.py` |
| Footprint grids / states / DXCC | 🟩 | `gui/screens/grids.py` |
| Space weather / weather | 🟩 | `gui/screens/spacewx.py` |
| AMSAT status | 🟩 | in satellites/track |
| OSCARLOCATOR + EQX | 🟩 | `gui/screens/oscarsim.py`, oscarlocator |
| Illumination | 🟩 | `gui/screens/illum.py` |
| 10-day pass progression | 🟩 | `gui/screens/tenday.py` |
| Mutual window finder | 🟩 | `gui/screens/mutual.py` |
| DX Doppler | 🟩 | `gui/screens/radio.py`, `engine.dxdoppler` |
| 3D globe (orthographic) | 🟩 | `gui/screens/analytics.py` GlobeScreen |
| Sun/Moon transits | ✅ | `engine/transits.py` + `gui/screens/transits.py` |
| Overhead now | 🟩 | Satellites → "What's up now" tab (`whos_up`) |
| QRZ callsign lookup | ✅ | `gui/datafeeds.py` + Activations/QRZ screen |
| Upcoming activations feed | ✅ | `gui/datafeeds.py` hams.at feed |

### Adding satellites from CelesTrak

| Capability | Status | Notes |
| --- | --- | --- |
| Search entire CelesTrak catalog | ✅ | `gui/satsearch.py`, `store.search_celestrak` |
| Add hit as auto-updating favorite | ✅ | `store.add_extra_sat` → `~/.orbitdeck/extras.json` |
| Extras re-fetched on GP update | ✅ | `store.refresh_extras` (courtesy limits enforced) |
| Search UI in Satellites screen | ✅ | "Search CelesTrak…" dialog |

---

## Explicitly out of scope (per project spec)

🚫 Radio CAT control (CI-V, Kenwood, Yaesu, Icom LAN, rigctl, USB-serial CAT),
antenna-rotator control (GS-232, Easycomm, SPID, rotctl, PstRotator, Yaesu),
LoRa messaging/KESSLER-over-LoRa, IR pass beacon, physical receipt printing
(PWG/URF/IPP), direct LoTW/Cloudlog upload transport, voice memos, and the
CardSat-as-network-server modes. These are hardware/radio integrations, not
desktop analysis features.

*Games (7) and Tiny BASIC are not analysis tools; they are candidates only if
specifically requested, and are unranked here.*

---

## Progress

- **Phase 1 (done):** the bench-calculator engine — 22 pure calculators across
  antennas, feedline, RF/measurement, electronics and terrestrial propagation,
  in `engine/toolcalc.py`, with `tests/test_toolcalc.py`. Faithful to CardSat
  formulas; no GUI yet.
- **Phase 2 (done):** *every remaining portable calculator* ported into
  `engine/toolcalc.py` (now **38 tools**: added match network, microstrip,
  sun-noise G/T, IMD, RF exposure, cross-section, thermal, ampacity, toroid,
  PLL, tropo ducting, Doppler budget, delta-v, pointing loss, Faraday) — 40
  calculator tests. **Plus the desktop Tools hub screen**
  (`gui/screens/tools.py` + `gui/tools_registry.py`): a categorised tool list
  with live-recalc forms (numeric fields and pickers) that recompute as you
  type, wired into the nav as **Tools**. Tested in `tests/test_tools_screen.py`.
  Full suite 208 → 252.
- **Still to do (future phases):** the *new orbital/analysis view screens* that
  aren't calculators — 3D globe, sky sources / star map, Sun/Moon transits,
  conjunction screener, orbital neighborhood, debris-group fetch, overhead-now,
  QRZ lookup and the activations feed — and the reference-table browsers (DXCC /
  CQ-ITU zones / CTCSS / char lookup). These need new UI and, in some cases,
  online fetches or data tables, so they're separate work from the calculators.


## Rove & workable parity (added after review)

A later audit against CardSat found real gaps beyond the initial "already have"
scoping. Closed:

| Capability | Status | Notes |
| --- | --- | --- |
| DXCC roster | ✅ | expanded 122 → **340** current ARRL entities (`data/dxcc.py`), matching CardSat's workable-DXCC coverage |
| Workable horizon | ✅ | `planning.workable_horizon()` — 10-day union of every workable state/DXCC (grids optional) across ALL favorites; Planning → "Workable horizon" tab |
| Target search | ✅ | `planning.target_search()` — every pass over N days where one state/DXCC/grid is workable, time-ordered across ALL favorites; Planning → "Target search" tab |
| State name↔abbrev | ✅ | `data/us_states.state_abbrev()` so targets accept "California" or "CA" |

Already present (confirmed, not rebuilt): live workable grids/states/DXCC under
the footprint (Workable screen, NOW + next-pass union); Rove tab showing workable
states/DXCC/grid-count per pass; Work-a-target two-way contact windows.

## OrbitTerm (TUI) parity

The desktop app reached CardSat parity first; OrbitTerm lagged at 12 screens
against the desktop's 29. Tracking the TUI catch-up here.

| TUI screen | Status | Notes |
| --- | --- | --- |
| Home, Satellites, Track, Passes, Pass Detail, Sky Radar, Ground Track, Progression, Illumination, Orbital Analysis, Radio, Settings | 🟩 | already present |
| Tools (41 calculators) | ✅ | `orbitterm/screens/tools.py`, shared registry |
| References | ✅ | `orbitterm/screens/references.py` |
| Workable (grids/states/DXCC) | ✅ | `screens/analysis2.py` |
| Planning (target search, workable horizon, rove) | ⬜ | |
| Mutual Windows | ⬜ | |
| Sun/Moon Transits | ⬜ | |
| Conjunctions | ⬜ | |
| Sun / Moon | ✅ | `screens/analysis2.py` |
| Celestial | ⬜ | |
| Space Wx | ⬜ | |
| Activations / QRZ | ⬜ | |
| Sites | ⬜ | |
| Exports | ⬜ | |
| Learn | ⬜ | |
| Sky Map | ⬜ | ASCII star field |
| 3D Globe | ⬜ | ASCII globe |
| OSCARLOCATOR Sim | ⬜ | |

**Shared-code note:** the tools registry moved from `orbitdeck/gui/` to
`orbitdeck/engine/tools_registry.py` so both front-ends import it from a neutral
place; `orbitdeck/gui/tools_registry.py` remains as a re-export shim.

## Tool-parity re-audit (corrective)

An earlier claim that "every portable tool is ported" was **wrong**. A
programmatic diff of CardSat's 60-entry Tools menu against OrbitDeck's registry
found nine genuine gaps. Closed here:

| CardSat tool | Status | Notes |
| --- | --- | --- |
| Scientific calculator | ✅ | `engine/calc.evaluate` - safe AST evaluator (no code execution) |
| Programmer calc (hex/bin) | ✅ | `engine/calc.programmer_rows` - dec/hex/bin/oct, bits, two's complement |
| Unit converter | ✅ | `engine/calc.convert_rows` - 7 unit families incl. temperature |
| Operating references | ✅ | phonetic alphabet + RST added to References |
| Radio math reference | ✅ | ARRL radio-mathematics cheat sheet in References |
| CubeSatSim C2C ref | ✅ | References table |
| Terrain path profile | ✅ | was present as "Terrain path (LOS)"; name differed |
| Graphing calculator | ⬜ | needs a plot surface (matplotlib GUI / ASCII TUI) |
| Tiny BASIC | ⬜ | interpreter + editor; large, and only questionably in scope |

**Not a tool:** "Space-Track" appears in CardSat only as a data-source
attribution line (CelesTrak is the actual catalog-search source, which OrbitDeck
implements). There is no Space-Track tool or credentialed feed in CardSat.

Tools hub is now **44 calculators across 6 categories**; References is **9 tables**.

## Re-audit against CardSat 0.9.75 (supersedes the 0.9.61 audit)

Everything above was audited against the **0.9.61-wip** drop. CardSat 0.9.75 is
substantially larger (`app.cpp` 33k -> 44.6k lines, 60 -> **64** tools, **164**
`SCR_*` screen states). Re-running the programmatic tool diff against 0.9.75:

### Tools still missing from OrbitDeck (6)

| CardSat 0.9.75 tool | Status | Note |
| --- | --- | --- |
| Space-Track history | ✅ **built** | `engine/spacetrack.py` + Orbital History screen |
| Graphing calculator | ⬜ | needs a plot surface |
| Tiny BASIC | ⬜ | interpreter + editor |
| Orbital thermal (cubesat) | ⬜ | new in 0.9.6x |
| AO-7 mode switch | ⬜ | new in 0.9.6x |
| Telnet client | ⬜ | DX-cluster telnet |

### Screens: not yet diffed in detail

0.9.75 carries 164 screen states, including whole subsystems added after 0.9.61
that OrbitDeck has no equivalent for — award tracking (`SCR_AWARDS/AWARDLIST/
AWARDSAT`), QSO logging (`SCR_LOG/LOGENTRY/LOGLIST`), LoTW (`SCR_LOTW*`),
DX cluster (`SCR_DXC`), APRS (`SCR_APRS*`), propagation/MUF (`SCR_MUF/MUFMAP/
PROP`), EME planning (`SCR_EME/EMEPLAN`), band plan (`SCR_BANDPLAN`), glossary,
notes, SAA, sky-at-a-glance, orbit zoo, thermal, ADS-B and more. **This screen
diff is outstanding work** — the tool-menu diff alone understates the gap.

### Space-Track orbital history (built)

`engine/spacetrack.py` queries the `gp_history` class for one object
(EPOCH, SEMIMAJOR_AXIS, ECCENTRICITY, INCLINATION, PERIOD, APOAPSIS, PERIAPSIS,
BSTAR, oldest first) using the operator's own credentials.

**Full resolution on desktop.** CardSat decimates into 120-240 time bins because
the ESP32 has ~31 KB of contiguous heap (114 B/bin). Desktop has no such limit,
so every row is kept; `decimate()` exists but is off by default.

Two fidelity details carried over from CardSat's bench findings:
- decades-old rows carry **empty** derived-value cells; parsing them as 0.0
  zero-poisons the series (drags minima to zero and flattens real structure), so
  an absent cell is `None` and is skipped **per column**, not per row;
- a 0 in a strictly-positive column is treated as absent for the same reason;
- gp_history may quote its CSV fields, so the parser is quote-aware.

Archival data is cached to `~/.orbitdeck/sthist/<norad>.json` and not re-queried;
queries are throttled (>=3 s apart, 200/hour) per Space-Track's API ToS.

## Screen-level diff vs 0.9.75 (the audit that was outstanding)

Ran programmatically over all **164** `SCR_*` states in 0.9.75, mapped against
OrbitDeck's screens and subsystems:

- **121 covered** by an OrbitDeck screen or subsystem
- **13 excluded** by the project spec (radio CAT, rotator, LoRa, USB helper)
- **30 gaps** across ~18 distinct subsystems

### Gaps, by subsystem

| Subsystem | CardSat screens | Status |
| --- | --- | --- |
| Band plan | `SCR_BANDPLAN` | ✅ **added** (References → Band plan) |
| EME / moonbounce | `SCR_EME`, `SCR_EMEPLAN` | ✅ **added** (EME screen; engine already existed, unexposed) |
| QSO logging | `SCR_LOG`, `LOGENTRY`, `LOGLIST` | ⬜ |
| Award tracking | `SCR_AWARDS`, `AWARDLIST`, `AWARDSAT` | ⬜ |
| LoTW / Cloudlog upload | `SCR_LOTW`, `LOTWSUB`, `CLOUDLOG` | ⬜ (upload transport was previously ruled out of scope; the *log* side is not) |
| DX cluster / telnet | `SCR_DXC`, `TELNET`, `TELNETTERM` | ⬜ |
| APRS | `SCR_APRS`, `APRSDET` | ⬜ |
| ADS-B | `SCR_ADSB` | ⬜ |
| MUF / propagation | `SCR_MUF`, `MUFMAP`, `PROP` | ⬜ |
| AMSAT status reporting | `SCR_AMSRPICK`, `AMSRPT` | ⬜ |
| Fox telemetry | `SCR_FOXANAT`, `FOXTEXT` | ⬜ |
| Orbital zones / SAA | `SCR_SAA` | ⬜ |
| Notes | `SCR_NOTES`, `NOTEEDIT` | ⬜ |
| Graphing calculator | `SCR_GRAPH` | ⬜ |
| Tiny BASIC | `SCR_BASIC` + 5 sub-screens | ⬜ |
| AO-7 mode switch | `SCR_AO7` | ⬜ (needs beta/eclipse math + an AMSAT-report fetch) |
| Orbital thermal | `SCR_THERMAL` | ⬜ |
| Sky at a glance | `SCR_SKYGLANCE` | ⬜ |

The single largest coherent chunk is the **logging/award/upload** family
(9 screens) — it needs a QSO log store first, which OrbitDeck has no equivalent
of; everything else in that family builds on it.

## Scope update + progress (post screen-diff)

**Dropped at the user's request:** QSO logging (`SCR_LOG/LOGENTRY/LOGLIST`) and
the telnet client (`SCR_TELNET/TELNETTERM`). Award tracking, LoTW and Cloudlog
upload all build on the QSO log, and the DX cluster is telnet-based, so those go
with them — **9 screens removed from scope**.

### Closed this round

| Gap | Status | Notes |
| --- | --- | --- |
| Graphing calculator | ✅ | `gui/screens/graphcalc.py`; uses the safe evaluator with an `x` binding (`calc.evaluate_with`), two traces, auto/manual y-range, undefined points break the trace |
| Orbital thermal (cubesat) | ✅ | `engine/thermal.py` + Tools entry; single-node model with beta, eclipse fraction, equilibrium and settled transient min/max |

### Remaining gaps (revised)

| Subsystem | Status |
| --- | --- |
| Tiny BASIC (`SCR_BASIC` + 5) | ⬜ largest single item |
| APRS (`SCR_APRS`, `APRSDET`) | ⬜ |
| ADS-B (`SCR_ADSB`) | ⬜ |
| MUF / propagation (`SCR_MUF/MUFMAP/PROP`) | ⬜ |
| AMSAT status reporting (`SCR_AMSRPICK/AMSRPT`) | ⬜ |
| Fox telemetry (`SCR_FOXANAT/FOXTEXT`) | ⬜ |
| Orbital zones / SAA (`SCR_SAA`) | ⬜ |
| Notes (`SCR_NOTES/NOTEEDIT`) | ⬜ |
| AO-7 mode switch (`SCR_AO7`) | ⬜ needs beta/eclipse (now available in `engine/thermal`) + an AMSAT-report fetch |
| Sky at a glance (`SCR_SKYGLANCE`) | ⬜ display reuse of existing predictions |

Tools: **45 of 64** CardSat entries (telnet now out of scope; Tiny BASIC
outstanding). OrbitTerm remains at 14 of 32 desktop screens.

### Orbital zones (added)

`engine/zones.py` + the **Orbital Zones** screen: South Atlantic Anomaly,
inner/outer radiation belts, polar caps and eclipse. Reports the current
verdict, upcoming entry/exit windows (boundary-bisected to ~2 s) and dwell
minutes per day.

**Deliberate difference from CardSat, stated rather than glossed:** CardSat
classifies the belts from a real **IGRF-14** field with field-line tracing.
OrbitDeck uses a **tilted centred-dipole** model for the McIlwain L shell and
B/B0. That is the standard analytic approximation and fine for "is this orbit
belt-exposed" questions, but it will disagree with IGRF near the belt horns and
inside the SAA, where the real field is markedly non-dipolar. Belt verdicts are
indicative, not dosimetry; the SAA, polar and eclipse zones are geometric and
carry no such caveat. Porting IGRF-14 properly is its own piece of work.

Sanity-checked against the ISS: ~11 SAA crossings/day (~150 min dwell) and
eclipse at ~36% of each orbit, both of which match the real spacecraft.

### Scope update 2 + sky-at-a-glance / AO-7

**Also dropped at the user's request:** APRS (`SCR_APRS/APRSDET`), ADS-B
(`SCR_ADSB`) and the DX cluster.

| Gap | Status | Notes |
| --- | --- | --- |
| Sky at a glance | ✅ | `engine/skyglance.py` + screen: Gantt-style timeline of every upcoming pass across favorites, bars coloured by peak elevation, plus the longest quiet gap |
| AO-7 mode calculator | ✅ **complete** | `skyglance.ao7_illumination()`: beta angle, eclipse fraction over one orbit, and the continuous-sunlight verdict that decides whether AO-7's 24 h mode timer is running. CardSat *also* estimates the current mode phase from a month of fetched AMSAT status reports — that crowd-sourced estimate is **not** ported |

### Remaining (revised)

Tiny BASIC (largest), MUF/propagation, AMSAT status reporting, Fox telemetry,
Notes, and the AO-7 report-based phase estimate. OrbitTerm remains at 14 of 34
desktop screens.

### AO-7 mode calculator (now complete)

`engine/ao7.py` + the **AO-7 Mode** screen. The full calculator, not just the
illumination verdict:

1. fetches AMSAT status reports for Mode A and Mode B **separately** (the API's
   record cap is per request, so per-mode queries spend the whole budget on AO-7
   instead of diluting it);
2. discards reports from before continuous illumination began - AO-7 has no
   batteries, so while it eclipses each orbit the timer isn't running and the
   phase carries no information;
3. fits a square wave by weighted agreement: a "heard" of mode m says the mode
   *was* m (weight 1.0); a "not heard" says it was *not* m, weighted 0.35,
   because a station can miss an active transponder for local reasons while the
   converse doesn't hold;
4. coarse-searches period **12-30 h** and phase over one period, both parities,
   then refines to 30 s / 1 min to remove grid quantization;
5. measures phase uncertainty by sweeping until the score drops by one positive
   report's worth, and grades confidence (near-a-switch, few reports, reports
   disagree, loosely constrained).

The 12-30 h search range is load-bearing: CardSat found a fixed ~24 h assumption
aliased badly against real data, which sits nearer **19.5 h**. A regression test
asserts the fit tracks 14 h, 19.5 h and 26 h rather than snapping to 24 h.

Validated by recovering a synthetic 19.5 h square wave to within 5 minutes at
100% agreement, with the transport injected so no network is touched in tests.

### MUF / HF propagation (added)

`engine/muf.py` + the **MUF / HF Prop** screen: MINIMUF-3.5 from the station to
24 world regions, showing the maximum usable frequency, the ~85%-of-MUF
"workable" figure, the band that implies, and path distance/bearing. Sortable by
region, MUF or distance; rows colour-graded by band quality.

The MINIMUF transcription deliberately keeps the published BASIC's variable
names (K1, G0, Y1, M9...) so it stays checkable line-by-line against the
reference rather than being tidied into something unverifiable.

Caveats carried into the UI: MINIMUF is a monthly-median model driven by sunspot
number, not a live ionosonde; it is weakest on very short (<~800 km) and
antipodal paths and models nothing about absorption.

Validated: MUF rises with sunspot number, all paths clamp to the model's 2-32
MHz range, band labels are monotonic in MUF, great-circle distance/bearing check
out against known paths, and a path and its reverse agree.

### Remaining (revised)

Tiny BASIC (largest), AMSAT status reporting, Fox telemetry, Notes.
OrbitTerm remains at 14 of 36 desktop screens.

### AMSAT status reporting (added)

`engine/amsatstatus.py` + the **AMSAT Status** screen: reads the community status
board (who has heard what in the last N hours, per satellite and per report) and
posts your own observation - Heard / Telemetry Only / Not Heard / Crew Active.

Submitting is **public and attributed**: the report carries your callsign and
grid and appears on amsat.org. So the screen confirms before sending, and
`build_report` refuses outright without a callsign, with an unknown status, or
without an AMSAT catalog name - a malformed or anonymous report should never
leave the machine. A test asserts nothing is posted when the callsign is missing.

This also added a real `http_post_json` to `gui/net.py` (and `store._http_post`);
OrbitDeck had only ever needed GET before.

**Scope note:** Notes and Fox telemetry dropped at the user's request.

### Remaining

Desktop: **Tiny BASIC** only. OrbitTerm: 14 of 37 desktop screens.

## OrbitTerm parity (2)

Desktop is complete against 0.9.75 (Tiny BASIC omitted at the user's request), so
the remaining work is the TUI. Five more text-native screens added, all reusing
engines the desktop already drives:

| TUI screen | Notes |
| --- | --- |
| Workable | grids / US states / DXCC under the footprint now, multi-column, `w` cycles type |
| Orbital Zones | SAA / belts / polar / eclipse transits, `z` cycles zone |
| Sun / Moon | solar and lunar az/el, distance, echo delay, sky temperature |
| EME | path loss, self-echo Doppler, common-Moon windows (`b` band, `g` scan) |
| MUF | MINIMUF to 24 regions, `+/-` adjusts sunspot number |

OrbitTerm: **19 of 37** screens (was 14). Verified rendering in a real curses
session: 887 workable grids under the ISS footprint, 2 m EME path loss 251.3 dB,
and SAA dwell ~149 min/day - matching the desktop screens.

Remaining TUI gap (18), mostly the graphical ones: 3D globe, sky map, sky at a
glance, orbital history, graphing calculator, OSCARLOCATOR sim, plus planning,
mutual, transits, conjunctions, AO-7, activations/QRZ, AMSAT status, celestial,
space wx, sites, exports and learn.

## OrbitTerm parity (3)

Six more text-native TUI screens (`screens/analysis3.py`), again reusing desktop
engines:

| TUI screen | Notes |
| --- | --- |
| Mutual Windows | co-visibility with a remote grid (`g` scans) |
| Sun/Moon Transits | disk crossings and near approaches (`b` body, `s` separation) |
| Conjunctions | orbital neighborhood (`n`) or a pair scan (`p`, `]` next object) |
| AO-7 Mode | illumination verdict (`i`) and the fitted mode phase (`f`) |
| Space Wx | cached solar/geomagnetic indices (`u` updates) |
| Sites | saved stations, ENTER makes one active |

OrbitTerm: **25 of 37** screens (was 19). Verified in a real curses session:
20 mutual windows with FN31 at matching elevations, neighborhood ranking
correctly ordered by range, and AO-7 reporting cleanly that the sample catalog
has no NORAD 7530 rather than crashing.

### Remaining TUI gap (12)

All the graphical ones plus a few forms: 3D globe, sky map, sky at a glance,
orbital history, graphing calculator, OSCARLOCATOR sim, planning,
activations/QRZ, AMSAT status, celestial, exports, learn. The first six need
real ASCII rendering work (star fields, plots, timelines in characters).

## OrbitTerm parity (4) - non-graphical gap closed

Five more TUI screens (`screens/analysis4.py`):

| TUI screen | Notes |
| --- | --- |
| Planning | workable horizon (`h`) and target search (`t`, `k` cycles state/DXCC/grid) |
| Activations | hams.at upcoming-activations feed (`r`) |
| AMSAT Status | community status board (`r`, `w` window) |
| Celestial | radio-source az/el for alignment and sun-noise work |
| Exports | 7-day pass CSV (`p`) and catalog element CSV (`e`) |

OrbitTerm: **30 of 37** screens (was 25). Verified in curses with favorites set:
50 states / 76 DXCC over the 10-day horizon and 60 passes working California -
matching the desktop.

**Learn moved to the graphical group.** It is not a form or table but a set of
interactive plot demos (Kepler equal-areas, vis-viva, footprint accumulation,
eclipse timelines), so it belongs with the ASCII-rendering work rather than this
batch.

### Remaining TUI gap (7) - all graphical

3D globe, sky map, sky at a glance, orbital history, graphing calculator,
OSCARLOCATOR sim, Learn. Each needs character-cell rendering (star fields,
plots, timelines) rather than a table.

## OrbitTerm parity (5) - braille graphics

**On "should we move to ncurses":** OrbitTerm already *is* ncurses. Python's
`curses` module is a binding to it, and the interpreter here links
`libncursesw.so.6` (the wide-character build). There is no migration to make.

The lever that actually raises graphical quality in a terminal is **sub-cell
rendering**. `orbitterm/canvas.py` adds a braille surface: the Unicode block at
U+2800 encodes 2x4 independently settable dots per character cell, so a plot gets
**8x the addressable points** of a block-character chart in the same space, while
staying pure text. Colour remains per cell (a terminal limit, not a braille one),
and `ascii_fallback()` renders the same buffer with `#` for fonts without
braille coverage.

Four graphical screens built on it (`screens/graphics.py`):

| TUI screen | Notes |
| --- | --- |
| Graphing Calc | expression plot, `e` edits, `[ ]` zoom, poles break the trace |
| Sky Map | star field + constellation lines on a zenith disk, satellites overlaid |
| Sky at a Glance | pass timeline across favorites, bars coloured by peak elevation |
| Orbital History | Space-Track element series from the desktop's cache, `c` cycles column |

OrbitTerm: **34 of 37** screens. Verified by rendering in a real curses session -
the sine curve is smooth across cell boundaries and the sky map shows a genuine
star field with cardinal markers.

### Remaining TUI gap (3)

3D globe, OSCARLOCATOR sim, Learn - the projection- and demo-heavy ones.

## OrbitTerm parity (6) - globe, and retrofits

**New:** `screens/globe.py` - an orthographic wireframe globe on the braille
canvas: graticule, limb, ground track, footprint circle, observer and
sub-satellite point. Steerable with the arrows, `f` locks to the satellite,
`t` toggles the track.

**Retrofitted to the braille canvas** (existing screens that gained from it):

| Screen | Before | After |
| --- | --- | --- |
| Pass Detail | one block glyph per column - a ~60x10 staircase | smooth elevation curve; the now-marker lands on the right dot rather than the nearest whole cell |
| Sky Radar | character-cell rings, visibly polygonal | round 0/30/60-degree elevation rings and cardinal spokes |

OrbitTerm: **35 of 37** screens. Verified by rendering each in a real curses
session and reading the output back.

### Remaining TUI gap (1, plus one omitted)

OSCARLOCATOR sim is the last screen. **Learn is omitted at the user's request.**

Ground Track and Illumination are the next retrofit candidates if wanted - both
still build character grids and would gain the same 8x resolution.

## OrbitTerm parity (7) - map retrofits

| Screen | Change |
| --- | --- |
| Ground Track | land raster, ground track, footprint and graticule all move to the braille canvas |
| Illumination | eclipse raster sampled at sub-cell resolution (2 dots per day, 4 per orbit row) so season boundaries are smooth rather than whole-cell steps |

**A finding worth recording: braille is line art, not area fill.** The first
ground-track cut plotted a dot for every land sample. At dot resolution that
sets every dot in a cell, so continents rendered as solid blocks that *buried*
the ground track and footprint underneath - visibly worse than the old shaded
blocks. The fix is to plot only the land/sea boundary, giving a coastline
outline that the track reads clearly over. The same caution applies to any
future fill: use braille for curves, rings and tracks; use character shading
where a filled area is genuinely wanted.

Sat and observer markers stay as text glyphs over the map for the same reason
they do on the radar: they are labels to pick out at a glance, and a cell can
hold braille or a marker, not both.

OrbitTerm: **35 of 37**. Remaining: OSCARLOCATOR sim (Learn omitted).

## OrbitTerm parity (8) - complete

`screens/oscarsim.py` adds the last screen: an on-screen **OSCARLOCATOR** on the
braille canvas - graticule disc, ground-track arc, footprint circle and a live
readout of EQX longitude and minutes after the crossing. Projection conventions
match the printable sheet and the desktop screen (north polar: 0 deg longitude
at the bottom, east counter-clockwise; QTH-centred: north up, clockwise
bearings). LIVE pins the overlay to the satellite's real last ascending node;
MANUAL rotates the disc and steps the minutes by hand, as you would slide the
paper transparency.

The arc is closed-form rather than propagated - inclination plus Earth rotation
under the orbit - because that is exactly what the paper overlay encodes, and it
keeps the arc independent of real time so the manual mode behaves like the
physical instrument.

### Final state

| | Screens |
| --- | --- |
| OrbitDeck desktop | 37 (complete vs CardSat 0.9.75; Tiny BASIC omitted) |
| OrbitTerm TUI | **36 of 37** - Learn omitted at the user's request |

Every CardSat 0.9.75 tool and view that is in scope is now present in the
desktop app, and every one of those except Learn is present in the TUI.

## Network audit (bug fix round)

Activations and AMSAT Status were reported broken. They were - and the causes
were things canned-data tests could never catch, because the canned data was
written from the same wrong assumptions as the code. Verified this round against
the **live** endpoints.

| Bug | Detail |
| --- | --- |
| AMSAT summary shape wrong | `/summary.php` returns `{"data": [...]}` with `report_count`, `report`, `latest_reported_time`, `satellite_display_name` - and **one record per (satellite, report value)**. The parser expected a flat per-satellite list with `reports`/`heard`/`last_report`, so every count read 0. Now folds the per-status records into one row per satellite. |
| AO-7 API names invented | The calculator queried `AO-7[A]` / `AO-7[B]`. The real names carry the transponder mode: **`AO-7_[V/a]`** (2 m up / 10 m down) and **`AO-7_[U/v]`** (70 cm up / 2 m down). The old names 404, so the mode fit silently had nothing to fit. |
| URL encoding | `quote()` defaults to `safe="/"`, leaving the slash in `AO-7_[V/a]` unencoded. The API encodes it `%2F`. |
| `pretty_name` | Did not handle the underscore form (`AO-91_[FM]`, `ISS_[UHF_Digi]`). Now uses the API's own `display_name` where present. |
| Errors swallowed | `fetch_activations` returned `[]` on any exception, and the API error envelope `{"error": {...}}` parsed as "no data". **A broken endpoint was indistinguishable from a quiet weekend.** Both now raise/surface, and the hams.at fetch detects an HTML login page specifically. |

Added `parse_catalog()` and `resolve_names()`: a bare `AO-91` is not a valid API
name (the endpoint 404s), so callers resolve common names through `/catalog.php`.

**Process lesson recorded:** canned-response tests validate the parser against
the author's assumption, not against the service. Where an endpoint is public,
fetch it once and pin a real captured response as the fixture.

### Still unverified

hams.at's `/feeds/upcoming_alerts` could not be fetched during the audit (the
site front page is public; the feed path was not reachable from here). The feed
URL came from CardSat's config and may require an account. The screen now says
which failure it hit, so the next live run will report the truth rather than an
empty list.

## Updated-upstream audit: decay model

The inventory was re-audited against 0.9.75, but many *implementations* were
ported from the 0.9.61 drop and never re-checked. Decay is the clearest case.

**CardSat 0.9.68 rebuilt the decay model** after fitting it against **244
catalogued objects that actually re-entered** (Space-Track TIP decay epochs plus
gp_history element sets), cross-checked against ~1500 objects' observed n-dot.
Their finding about the version OrbitDeck had ported: it combined
`Cd*A/m = 38*B*` with a `da/dt` a factor of two too large; the errors partly
cancelled at ISS altitude where the constant was tuned, and elsewhere the model
predicted **about a fifth of the true remaining life**.

`engine/decay.py` now implements the calibrated model:

- **n-dot anchor.** The element set's mean-motion derivative *is* a measurement
  of the current decay rate, so back-solving the ballistic coefficient from it
  makes the present rate right by construction and cancels the B*→Cd*A/m
  conversion, the density normalisation and the solar scale. Scored 0.99x median
  against real re-entries, 92% within ±30%.
- **B* fallback** (`Cd*A/m = 12.741621 * B*`) when n-dot is absent, negative or
  noise.
- **King-Hele eccentricity factor** `exp(-z)(I0(z)+2e·I1(z))`. It *suppresses*
  drag on an eccentric orbit because the satellite spends almost none of a
  revolution near perigee — without it a GTO reads ~40 days instead of years.
- Eccentricity-dependent re-entry threshold (120 km circular, 90 km eccentric),
  and energy leaving apogee while perigee holds until the orbit circularises.

Sanity after the port: ISS-like **2.7 yr** unreboosted, 300 km **70 d**, GTO
stable, and solar activity spanning **9–80 yr** at 550 km.

`toolcalc.orbit_lifetime` is kept but marked deprecated, with the reason.

**Two bugs I introduced and caught while porting**, both worth recording:
1. I truncated the integrator and omitted the near-circular branch, so perigee
   never descended and *every* object read "stable".
2. I asserted the King-Hele factor was >1. It is <1 — a suppression — which is
   the whole reason eccentric orbits survive. The test now states the physics.

### Still to re-check against 0.9.75

Other 0.9.61-era ports not yet diffed: MPE/RF-exposure, coax-loss constants,
Doppler budget, state-vector→GP, and the transponder passband planner. The
zones/MINIMUF/thermal ports were taken from 0.9.75 directly and are current.


## 0.38.0: rendering correction and nav rework

**Half-blocks, not braille, for filled areas.** The braille lesson from the
ground-track retrofit applied to the illumination raster too and I missed it:
a lit/dark heatmap is an *area*, and braille's 2x4 dots render an area as sparse
specks. `canvas.HalfBlockCanvas` uses U+2580/U+2584/U+2588, which fill the cell
solidly while still giving 2x the vertical resolution of whole blocks. The rule
is now three-way, not two:

| content | glyph set |
| --- | --- |
| curves, rings, tracks, plots | braille (`Canvas`) |
| filled rasters, heatmaps, bars | half-blocks (`HalfBlockCanvas`) |
| labels and markers | plain text over either |

**Pass Progression was never changed by me** - it is the original v0.37.0 screen
using the `.` shading ramp, and it is unaffected by the braille work. If it still
reads poorly the cause is its own design, not a regression.

**Navigation.** The number shortcuts are gone. With 36 screens, 1-9 + 0 addressed
ten and silently orphaned the rest.

## Implementation diff audit: complete

Every tool computation was diffed case-by-case between the 0.9.61 drop the ports
came from and 0.9.75.

**Result: 39 of 40 tool cases are byte-identical.** The one that "differs" is
`TOOL_FRESNEL`, and the only change is a spelling correction in a comment
(`metres` → `meters`). The MPE/RF-exposure limits, the state-vector→GP seed, the
Doppler budget and the coax/antenna/electronics constants are all unchanged, so
those ports are current.

That leaves **decay as the only algorithm CardSat actually revised** (0.9.68,
ported in the previous round), which is a reassuring result: the drift was
confined to the one model they explicitly refit against observational data.

### A bug of my own, found by the diff

Reading CardSat's Fresnel case next to my port exposed an error I had
introduced. The general form is

    r1 = 17.31 * sqrt(d1*d2 / (f_GHz * D))

which at the midpoint (d1 = d2 = D/2) collapses to `r1 = 8.657 * sqrt(D/f_GHz)`.
I wrote that collapsed constant in the comment **and then divided by two again**,
so `toolcalc.fresnel_zone` reported **half the true first-zone radius**. That
error is in the unsafe direction: it makes an obstructed path look clear, and
the 60% clearance figure inherited the same halving.

`engine/terrain.py` used the general form and was always correct - the two now
agree to <0.2 m across 10-50 km paths from 146 MHz to 10 GHz, and a regression
test cross-checks them against each other rather than against a constant I might
copy wrong twice.

**Audit status: closed.** All ported implementations are current against 0.9.75.

## Two field-reported bugs (0.38.0 follow-up)

**`'Store' object has no attribute '_http_get'`.** `_http_get` and `_http_post`
are **module-level functions** in `gui/store.py`, not `Store` methods. Five
screens called `self.store._http_get(...)`, which raises `AttributeError` the
moment a fetch is attempted - so every new network screen failed on first use.
Fixed at all five call sites by importing the module function. A test now scans
both packages for `store._http_get`/`store._http_post` and asserts `Store` has no
such attribute, so the whole class of mistake is caught rather than this one
instance.

Worth noting *why* the unit tests missed it: they inject a fake transport
callable, so they exercised the parsers without ever going through the real
accessor. Injection is right for testing parse logic and wrong as the only
coverage of the wiring.

**AO-7 illumination started "now".** `illumination_since()` walked backwards in
30-minute steps and treated a single shadowed sample as an eclipse. Near a season
boundary one of 24 samples grazes shadow on some orbits and not others, so the
walk stopped immediately and reported the continuous-sunlight run as beginning at
the present time. It also treated a propagator exception as "eclipsing", which
silently truncated the search.

Rewritten as a coarse backward scan (12 h steps) to find the first eclipsing
orbit, then a bisection to 30-minute resolution, requiring at least two shadowed
samples so a graze cannot flip the verdict. `orbit_eclipse_samples()` now returns
`None` for an unevaluatable state instead of claiming eclipse, and the function
returns `(start, exact)` so a run older than the search window is labelled as
"at least this long" rather than presented as a found boundary.

## OrbitTerm was showing local time under UTC labels

Reported from the field and confirmed: `fmt.fmt_clock/fmt_hm/fmt_date` all used
`time.localtime()`, so every pass time, AOS/LOS and countdown was the **local**
clock while the column headers said UTC. For anyone not sitting on UTC+0 the
tables were silently wrong by their offset.

Six call sites fixed (three in `fmt.py`, three in `progression.py`), and the
visual audit caught two more the grep had not:

- the **title-bar clock** rendered `13:05:00 EDT` from `strftime("%Z")`;
- the **progression axis** was labelled `local h` and bucketed passes by local
  day.

All now UTC. A regression test re-imports the formatters under
`TZ=America/New_York`, asserts each matches `gmtime`, and scans the package for
any remaining `time.localtime(` or `strftime("%Z")`.

## Visual audit

**OrbitTerm:** all 36 screens rendered in a real curses session and checked
programmatically for exceptions, empty content and line overflow. No overflows,
no exceptions. Seven screens report only 2-4 content rows, all of them by design
- they are action-first (`press g to scan`, `r fetches the feed`) or need data
the sample catalog lacks (Orbital History has no cached archive).

**Desktop:** all 37 screens render with content. Conclusions about *layout* are
limited: without a window manager the capture leaves an unpainted region over
part of the frame, so fine alignment could not be judged from these images. The
threaded screens (MUF, Zones) were captured mid-scan showing their progress
message and an empty table, which is correct behaviour rather than a defect.

## OrbitTerm independence, Space-Track fetch, and the time question

**Times (reported still local).** I could not reproduce this against the
delivered tree. At `TZ=Pacific/Auckland` (UTC+12) `fmt_clock` returns the true
UTC value, and the header reads `UTC`. Every formatter, the header clock and the
progression axis were converted in commit `834ddef`. Two things worth checking on
your side: that the running copy is at `834ddef` or later, and that it is not an
older `pip install`ed OrbitDeck shadowing the working tree - `python -c "import
orbitterm; print(orbitterm.__file__)"` will say which. If it still shows local
time after that, the screen and field would pin it down.

Also worth recording: my first attempt to prove this used a harness that froze
`time.time()` but not `time.gmtime()`, so every screen "differed" between
timezones and appeared broken. That was a defective test, not 36 bugs.

**Space-Track from OrbitTerm.** The Orbital History screen now fetches the
archive itself (`f`), using credentials from Settings, and writes to the same
`~/.orbitdeck/sthist/` cache the desktop screen reads - so either front-end can
populate it for the other.

**Everything settable from OrbitTerm.** Settings grew from 5 fields to 11:
station lat/lon/alt, **Maidenhead grid** (resolved through the normal site
setter so predictors invalidate), station name, min elevation, callsign, QRZ
user/password and Space-Track user/password. Passwords display as asterisks and
an edit starts blank, so the mask can never be saved back as the literal
password.

**Dependency direction fixed.** OrbitTerm was importing `orbitdeck.gui.store` and
`orbitdeck.gui.net` to make web requests - a curses app reaching into a package
named `gui`. The HTTP layer moved to `orbitdeck/netio.py`; `gui/net.py` is now a
re-export shim. A test asserts OrbitTerm never imports the GUI networking again.

**A regression this caught in passing:** the first cut of the shim dropped
`http_get`'s HTTP status handling - the 403 "back off and use the cache rather
than retry" and 404 "the query is wrong, retrying will not help" messages. An
existing test flagged it. Restored in `netio`, and now applied to the POST
helpers too, which never had it.

## AMSAT API name matching (ported from CardSat)

The AMSAT status API does not use catalog names. It publishes its own
mode-tagged designators - `AO-7_[V/a]`, `ISS_[FM]`, `CAS-3H` - while the GP
catalog carries `AO-7 (OSCAR 7)`, `ISS (ZARYA)`, `LILACSAT-2`. Guessing a name
is exactly how the AO-7 fit ended up querying `AO-7[A]` and getting a 404.

`engine/amsatnames.py` ports CardSat's matching ladder, applied to names pulled
from the API's own `catalog.php`:

1. parenthesised designator (`AO-7` -> `AO-7 (OSCAR 7)`) - the CelesTrak bridge
2. whole-name equality on the normalised form
3. delimited-token containment
4. legacy prefix stem (`AO-07` and `AO-7` collapse together)
5. collapsed form (`AO-7` / `AO 7` / `AO7`)
6. alias table for designators with **no lexical bridge at all**: `CAS-3H` is
   `LILACSAT-2` and `IO-117` is `GREENCUBE` - nothing in the strings connects
   them, so no amount of string cleverness finds these.

A satellite can hold several API names (AO-7 has one per transponder mode), so
`names_for()` returns all of them - which is what the mode calculator and the
reporting picker need.

**AO-7** now calls `resolve_api_names()` to ask the catalog which names it
publishes today, mapping each to a mode by its tag (`V/a` = 2 m up / 10 m down =
Mode A; `U/v` = 70 cm up / 2 m down = Mode B). Hardcoded names remain only as a
fallback, so a catalog fetch failure degrades to the previous behaviour instead
of breaking the fit.

**Both AMSAT Status screens** resolve the selected satellite through the ladder
rather than assuming its catalog name is an API name (desktop on entry, TUI on
`m`).

Two details carried over because they are easy to get wrong: the API
pretty-prints its JSON, so a naive `"name":"` byte match finds nothing (CardSat
hit this and ended up with an empty map, leaving multi-mode birds offering one
mode); and report precedence is Heard > Telemetry Only > Not Heard, ties broken
by recency, so status, age and count all come from one row.

## Per-screen feature parity: Orbital History

The earlier audit checked that each tool *existed*, not that each screen offered
what CardSat's does. Orbital History was the clearest gap: CardSat's `SCR_STHIST`
has **four views** and a time-axis zoom; OrbitDeck had a plot and a summary.

Now at parity on both front-ends:

| Feature | Notes |
| --- | --- |
| **Value** view | the element plotted over time (was already there) |
| **Rate** view | d(element)/dt - drag and manoeuvres read directly off this |
| **Analysis** view | has the *rate itself* changed? |
| **Table** view | per-element first/last/change/per-year over the window |
| Time zoom & pan | `+`/`-` zoom, `[`/`]` pan, `0` reset; value, rate and table honour it - **analysis deliberately ignores it**, because its question is about the whole record |

The analysis view ports CardSat's logic, including three details that are easy
to get wrong and that their source documents as audit findings:

- **Era split is on the time axis, not the sample count.** A sparse 1970s
  archive next to a dense modern one would otherwise put modern samples in both
  halves and report the same rate twice.
- **Jump baseline falls back to the mean.** An object that sat perfectly still
  for years has a median |rate| of zero, which disabled the detector at exactly
  the moment its one big manoeuvre arrived.
- **A near-zero era outranks the ratio.** "early 0, late large" used to print
  "rate roughly steady (0.00x)"; it now reads "NEW trend developed lately".

Rate pairs closer than an hour are skipped: the archive holds several element
sets per day, and dividing by a near-zero interval manufactures enormous
spurious rates.

Validated against a synthetic record with a planted manoeuvre: the jump is
detected at ~150 km/yr against a 0.6 km/yr median, and the verdict reports the
acceleration.

## Per-screen parity sweep (beyond Orbital History)

Method: extract every CardSat key handler and footer help string, decode what
each key does, and compare against the OrbitDeck screen. Findings:

| CardSat feature | Screen | Status |
| --- | --- | --- |
| `g`/`w`/`e` workable grids / states / DXCC **on the selected pass** | Passes | ✅ added (`planning.workable_on_pass`, both front-ends) |
| `f`/`c` prefix filter on the workable list | Grid | ✅ added (both front-ends) |
| `i` one-key "I heard it" AMSAT report | Track | ✅ added (desktop) |
| `V` visible-pass list, `v` visibility, `i` illumination from Passes | Passes | 🟩 present as their own screens |
| `x` mutual window vs a DX grid from Passes | Passes | 🟩 present as Mutual Windows |
| `z` orbital zones from Orbit | Orbit | 🟩 present as Orbital Zones |
| `q`/`s`/`v` QTH presets, GPS source, live DMS | Illum | 🟩 Sites screen / no GPS on desktop |
| `a` point-here arrow, `d` Doppler mode, `m` TUNE/CAL, `v` voice memo | Track | ⬜ out of scope (radio/rotator/memo) |
| `p` print report | many | 🟩 present as Report/Export |

**Per-pass workable** is the substantive one. The Workable screen answers "what
is under the footprint *now*"; CardSat's Passes screen answers "what can I work
on **this** pass", which is the question you ask *before* a pass rather than
during it. `workable_on_pass()` samples the footprint across AOS-LOS and unions
the result - on a test ISS pass, 1695 grids / 33 states / 50 DXCC versus a much
smaller instantaneous set.

**The prefix filter** matters more than it looks: a footprint holds roughly 1700
grid squares, so the unfiltered list is not usable. CardSat has `f`/`c` for
exactly this reason.

**The one-key report** belongs on the tracking screen because that is the moment
you know the answer - mid-pass, with the bird in front of you. It resolves the
API name through the catalog matcher rather than assuming the catalog name works,
and refuses without a callsign.

## Stale per-satellite state on screen switch

Reported: selecting a new satellite and returning to Orbital History still shows
the **previous** satellite's archive. That is not a cosmetic problem - the screen
presents AO-73's history under AO-7's name, so the UI asserts something false.

Cause: screens are constructed once and reused, so any per-satellite result a
screen caches survives a satellite change.

Fixed generically rather than one screen at a time. Both base `Screen` classes
gained a `sat_scoped` declaration and a clear step that runs before the screen
draws:

- desktop: `Screen.sat_scoped` + `_clear_if_sat_changed()`, called from
  `App.show()`;
- terminal: `Screen.sat_scoped` + `clear_if_sat_changed()`, called from
  `App.goto()` **and** from a listener on `AppState.select()`, so a satellite
  change clears every screen, not just the one being opened.

Orbital History also resets its **zoom window and view state**: a zoom chosen for
one record is meaningless against another.

Two bugs of my own, caught by the tests:

1. I guessed `_neigh` was cached data on the Conjunctions screen. It is a
   **method** - nulling it broke the screen's button. Both base classes now
   raise if `sat_scoped` names a callable, so the mistake cannot repeat
   silently.
2. I registered the TUI satellite listener inside `goto()`, which runs on every
   screen change and would have piled up duplicate listeners. Moved to
   construction with a guard.

The desktop cache directory is now an overridable attribute so tests can isolate
it; previously a real archive on disk made the test result depend on what other
tests had written.

## Space weather: a real data bug, and parity

**SFI was wrong, and badly.** NOAA's `f107_cm_flux.json` is ordered
**newest-first**; the code took `vals[-1]`, i.e. the *oldest* record in the
feed. Checked live: the feed's newest entry was **95 sfu** for today while the
tail was **201 sfu** from 40 days earlier - so the screen was showing a
six-week-old flux.

Worse, the feeds do not agree with each other: `planetary_k_index_1m.json` is
oldest-first, so *either* fixed index would be wrong for one of them. Both now
select by **sorting on the timestamp**, which makes the ordering irrelevant.

### Display parity with CardSat's Space Wx

| Feature | Status |
| --- | --- |
| Solar flux with band label (low / moderate / good / very high) | ✅ added |
| Kp with label (quiet / unsettled / minor / mod. / major storm) | ✅ added |
| A index with label (quiet / unsettled / active / storm) | ✅ added |
| **Aurora likelihood** from Kp | ✅ added |
| **Plain-language operating outlook** | ✅ added |
| Data-age line ("<1h old", "3d old") | ✅ added |
| Sunspot number and 90-day flux mean | ✅ added (beyond CardSat) |

The thresholds live in `engine/spacewx_interp.py` so the desktop screen, the TUI
and the report writer share one definition rather than three. The outlook
deliberately lets a geomagnetic storm outrank a high flux, because that is what
actually changes the evening.

### MUF now seeds its sunspot number

It did not - it defaulted to 100 and made the operator type a value they would
have to look up elsewhere, which defeats having fetched the space-weather data
at all. The MUF screen now takes SSN from the Space Wx cache, falls back to
deriving it from the flux via `ssn_from_flux()` (the Covington-style relation,
`1.61*(F10.7-67)`), and **says which** - an observed SSN and a derived one are
not the same claim, so the screen labels the provenance rather than presenting
both as measured.

A bug of my own found while testing: `age_text()` tested the timestamp for
falsiness, so an epoch of 0 rendered as "no data" instead of "very old".

### OrbitTerm MUF now seeds its SSN too

The previous round seeded the **desktop** MUF screen and left the TUI pinned at
a hardcoded `100`, so the two front-ends disagreed about the current sunspot
number - a fix applied to one surface and not the other.

The seeding logic now lives once, in `spacewx_interp.seed_ssn()`, and both
screens call it: observed SSN from the cache, else derived from F10.7, else a
labelled default. Both show the provenance.

The TUI additionally tracks it through edits: `+`/`-` relabels the source as
`manual`, and `s` reseeds from the cache. A number nudged by hand must stop
claiming it came from the feed.

## Activations: duplicate adds, and parity

**The duplicate-add bug.** Adding a satellite from an activation went straight
to CelesTrak and called `add_extra_sat()` unconditionally. It never looked in the
local catalog - and it could not have matched anyway, because the feed uses
operating names (`AO-91`, `RS-44`) while the catalog carries `AO-91 (RADFXSAT)`.
So a satellite you already had was re-fetched and added a second time.

Now: `activations.find_local()` resolves the feed name against the catalog
through the AMSAT name matcher first. If it is already there, the screen just
**stars** it and says so. If a CelesTrak search does happen, the result is
checked again by NORAD before adding, since a search can return an object
already present under a different name.

**Parity with CardSat's Activations screen.** The feature that screen exists for
was missing: CardSat answers *"can I actually work this?"* on ENTER, by checking
whether you and the activator can both see the satellite around the listed time.
Added to both front-ends, with the failure modes kept distinct:

| State | Meaning |
| --- | --- |
| `FP_OK` | mutual window found (start/end shown) |
| `FP_NO_WINDOW` | both known, but no common visibility near the listed time |
| `FP_NO_SAT` | the satellite genuinely is not in your catalog |
| `FP_BAD_TIME` | the feed's date/time could not be parsed |
| `FP_BAD_GRID` | the activator grid could not be parsed |

That separation is deliberate and comes from CardSat's own notes: collapsing
them meant a feed date problem was reported as "satellite not in your list",
sending the operator hunting for a satellite that was there all along.

**Grid-line activations** are handled too: a line activation lists two grids
(`EM12/EM13`), the whole string fails to parse, and that failure used to be
reported as a satellite problem. `first_grid()` takes the first token - the two
are adjacent by definition, so either places the activator in the same footprint.

## Activations: the whole CardSat workflow

Previously the screen answered a yes/no. CardSat's workflow does not stop there:
an activation leads to the **mutual window itself**, and from that window to a
**DX Doppler table** seeded with it. Both front-ends now do the same.

    activation -> check -> mutual windows -> DX Doppler for the chosen window

**Windows.** `check_activation()` returns every window near the listed start,
each with both stations' maximum elevation, plus the DX observer. The window
nearest the advertised start is preselected - that is the one being advertised.

**DX Doppler.** Seeded with the activation's **own** satellite and transponder
rather than whatever happened to be selected, which is the point CardSat makes
explicitly in `openActMutual()`. All three operating modes and all four anchors
are available, from the existing `engine/dxdoppler` - the new work here is the
seeding, not the maths:

| Mode | Behaviour |
| --- | --- |
| True rule | the passband point is fixed; every dial Doppler-tracks its own station |
| Fixed downlink | the anchor's RX dial is held in real RF; the passband drifts to absorb its Doppler and the other three follow |
| Fixed uplink | the anchor's TX dial is held instead |

Linear transponders open on the middle of the passband, as the tracker would.

**Desktop:** "Can I work it?" opens a detail window - window list on top,
transponder / mode / anchor pickers, dial table below. **TUI:** ENTER cycles
list → windows → Doppler, with `m` mode, `n` anchor, `p` transponder, ESC back.

Verified end to end: an ISS activation from FN31 yields an 8m50s mutual window
at 17 degrees both ends, and 18 dial rows at 30 s spacing showing my RX/TX and
the DX station's - which differ, as they must, since the two stations see
different range rates.

## EME: parity with CardSat's analysis and planner

The EME screen showed path loss, Doppler and common-Moon windows. CardSat has
two more views, and they carry most of the operational value - path loss alone
does not tell you whether tonight is worth setting up for.

**Per-band analysis** (`a` on CardSat, a tab / `a` here), across 50 / 144 / 432 /
1296 / 10368 MHz:

| Figure | Why it decides the night |
| --- | --- |
| Self-echo Doppler | how far to offset to hear your own echo |
| Faraday rotation | polarity offset; ~90° at 144 for mid flux, falling as 1/f², so it matters on 6 m and 2 m and not above 1296. Seeded from the Space Wx flux |
| Sky temperature | the galactic plane behind the Moon is the difference between an easy 2 m night and an impossible one |
| Libration spread | echo smearing: negligible for CW on 2 m, dominant at 10 GHz |
| Two-way path loss | including the 6 dB reflection loss |

Plus **path degradation** vs perigee, **ground gain** (below 8° the reflected ray
adds - why operators favour moonrise and moonset), and **Sun separation** (inside
10° solar noise swamps a weak echo).

**90-day plan.** Declination and path degradation sampled at 12:00 UTC each day
so rows compare like with like, flagging days when the Moon is both well north
(a long window from the northern hemisphere) and near perigee.

New engine functions in `engine/celestial.py`: `moon_dec_deg`,
`moon_galactic_lat_deg`, `eme_faraday_deg`, `eme_sky_temp_k`,
`eme_libration_spread_hz`, `eme_path_degradation_db`, `eme_band_analysis`,
`eme_ground_gain`, `eme_sun_separation_deg`, `eme_plan`.

Sanity-checked: 2 m two-way path loss 251.4 dB, Faraday 71° at 144 falling to 0°
at 10 GHz, sky temperature 203 K at 144 down to 3 K at 10 GHz, and the planner
showing the full 0.37-2.25 dB perigee/apogee cycle over 90 days.

**Caveat carried from CardSat:** Faraday and libration spread are coarse models -
real rotation depends on the whole ionospheric path and true spread varies
through the month. They are good enough to answer "will this hurt tonight",
not to predict a number.

### The activation detail view had no way in

Asked how to reach it, I checked instead of answering from memory - and the
honest answer was **you could not**, on the desktop. Two mistakes:

1. The "Can I work it?" button was never added. My edit targeted
   `text="Refresh"` while the actual string is `"Refresh feed"`, so the
   replacement silently did not match and `_check_act()` sat there uncalled.
2. The double-click binding was registered inside the *refresh handler*, so it
   did nothing until a feed had loaded - and it was wired to "add satellite"
   rather than the detail view anyway.

Fixed: **Can I work it?…** and **Add satellite** are now both buttons on the
Activations tab, and double-click opens the detail (the primary action; adding a
satellite changes your catalog, so it stays an explicit button). The binding is
made at build time.

A regression test now walks the built widget tree and asserts an entry point
exists. A feature with no way to reach it is not shipped, and a string-replace
edit that does not match fails silently - both worth a test rather than a
promise.

## OrbitTerm normalised to 80x24

Audited every screen at exactly 80x24 (and at 100x30 / 120x40 to check nothing
regressed wider). No screen overflowed or came up blank, but the **Orbital
Analysis** screen was quietly broken: the nav takes 19 columns, leaving ~61 for
content, and the layout split at a hardcoded 40 columns - so the right-hand
values ran off the edge and were truncated *mid-number*, losing their units
("4489 km" read as "44", "-4.956°/day" as "-4").

That is the worst kind of narrow-terminal bug: it looks like a value rather than
an error. The layout is width-aware now - two columns when both fit, stacked
sections when they do not - and every value is clipped rather than allowed to
overrun. Two regression tests: one asserts the layout adapts, the other walks
all 36 screens at 80x24 and fails on any overflow or blank body.

## Audit response, round 1

**A1 Propagation outlook** — built. `engine/propagation.py` + a screen: headline
day/night MUF, per-band open/fair/weak/shut for 80 m through 6 m, geomagnetic
state, aurora-VHF likelihood, D-layer absorption, meteor scatter (named showers
with their dates, else the sporadic background) and sporadic-E season. Verified
that a storm suppresses the MUF while raising aurora and absorption, which is
the behaviour that makes the screen worth having.

**B1 Orbital Analysis fields** — Velocity and V apo/peri added (vis-viva from
elements already held: ISS 7.659 km/s, GTO 1.63 / 10.02). Launched, In orbit and
Launch siblings added from the COSPAR designator. The designator carries the
launch **year** only, so those read "1998 (approx.)" and "~28 years" rather than
implying a precision the data does not contain.

**Everything printable** — 27 screens had no way to print and there was no
generic path. Now:
- `reports.generate_generic_report()` renders kv / table / text sections;
- `reports.save_report_dialog()` is one call for a screen to become printable;
- the **base `Screen` class carries a default `_report`** that walks whatever the
  screen has actually displayed, so a new screen cannot silently ship unable to
  print;
- `KVPanel` records its rows as they are drawn, so key/value screens print what
  they showed without keeping a second copy in sync.

A test asserts every screen in the nav has a working report action.

### Still outstanding from the audit

- **B2** Sky Radar sub-satellite point.
- **C** MUF map, Orbit types, Ham satellite history, link-margin curve, field
  weather, Doppler lock. (QTH presets are covered by Sites.)
- **D** RTTY/CCITT columns in the character table; CQ/ITU/DXCC drill-downs;
  GP-fit convergence diagnostics; AMSAT status inline in the satellite list.
- Graphical screens (globe, sky map, radar, ground track, OSCARLOCATOR,
  graphing calculator) have a report action, but it prints their **tables**, not
  the figure. Printing the plot itself is a separate piece of work.

## Reported issues, round 2

**1. hams.at date/time "unusable".** Two bugs, both in the parser:

- The **date lives in the title** as `[YYYY-MM-DD]`, and the content's list
  items carry only a clock time. My regex matched the bracket and threw the
  date away, so there was never a date to combine with "Start time". CardSat
  reads it from the title for exactly this reason.
- The Atom **content is HTML-escaped** (`&lt;li&gt;`) and CDATA-wrapped in some
  entries, so every list item - start, end, mode, elevation - came back empty.

Both fixed and covered by a test built from the real feed shapes, including the
CDATA variant, a short `HH:MM` clock, the trailing " UTC", and a grid-line
activation.

**3. 80-column truncation.** The earlier pass fixed the layout that *overflowed*;
these were losing data inside the line:

- Home showed `grid FM2` instead of `grid FM29nw`, and dropped the pass
  duration entirely - the thing you plan around. Now the grid moves to its own
  line and the pass detail wraps rather than clipping.
- The satellite list's selected row used `ljust(..., w - x0)` where `w` was
  already the content width, so the highlight ran under the active-satellite
  marker and overwrote the period and altitude. The marker's columns are now
  reserved.

A test asserts both survive at 80x24 and that no line exceeds the width.

**Graphical screens print their tables** - confirmed as the intended behaviour
rather than a limitation to fix.

## Activations display, and OrbitTerm data parity

**Date column and the redundant UTC.** The activation list showed a start time
with no date, so an entry three days out looked like one tonight. Date is now
its own column, and the trailing "UTC" is stripped from feed values - every time
OrbitDeck shows is UTC and the header says so, which makes a per-row suffix
noise. The same "(UTC)" suffix was removed from column headers across 19 screen
files in both front-ends; the header clock still carries it once.

**Desktop vs TUI parity.** Compared the displayed fields screen by screen. Most
matched; the outlier was **Orbital Analysis** - the desktop shows ~70 fields
across sections, the terminal had a single flat page of 18. Added paging
(`p` / `Tab`, `P` backwards) with four pages:

| Page | Contents |
| --- | --- |
| elements | the original page - mean motion, period, SMA, apsides, angles, drift, repeat track |
| live | az/el, range, range rate, altitude, sub-point, Doppler at 145.8 and 435, path delay, sunlit, velocity |
| pass | AOS/TCA/LOS with azimuths, max elevation, duration, countdown |
| identity | NORAD, COSPAR, launch year, years in orbit, launch siblings, epoch and age, V apo/peri, B* |

Smaller gaps closed at the same time: EME and AO-7 fields the terminal lacked.

Two mistakes worth recording from this change. Removing "duplicate" methods by
pattern matched the **Ground Track** screen's `handle_key`/`help_keys` and cut
them mid-line; and the orbit screen's own `[`/`]` satellite cycling would have
been lost had it not been folded into the new paged handler rather than
replaced. A test now asserts `cycle_sat` survives in that handler.

## Audit response, round 2

**D — character lookup.** The References ASCII table answered "what is 0x41" and
nothing more. A new **Character / byte lookup** tool shows one byte in all four
bases with its ASCII meaning (control codes by name), Morse pattern, **ITA2
letters- and figures-shift** meaning for 5-bit values, and the **BCD** reading.
The last two are not curiosities: ITA2 is what RTTY actually sends, and CI-V
frequency bytes are BCD. An invalid BCD nibble is reported as invalid rather
than shown as a number.

Also added as browsable References tables: the full **ITA2/Baudot** table and a
**Morse** table.

**C — orbit types and satellite history.** Two content tables: orbit classes
(LEO, sun-synchronous, MEO, Molniya, GEO, HEO, polar, retrograde) with what each
means for operating, and a chronological list of amateur-satellite milestones
from OSCAR 1 to IO-117.

**B2 — radar sub-satellite point.** The Sky Radar now shows where the active
satellite actually is (sub-point and altitude), not only where to point the
antenna.

References is now **14 tables**; Tools is **46 calculators**.

### Still outstanding

- **C**: MUF map (a shaded world map rather than the region table), field
  weather, Doppler-lock practice display, link-margin *curve* (the numbers are
  already a Tools calculator).
- **D**: CQ/ITU/DXCC drill-down detail views; GP-fit convergence diagnostics.

## Reported issues, round 3

**1. Transponders showed "?" and there were no mutual-window polars.**
The picker read `.description` / `.name`; the Transponder attribute is `.desc`,
so every entry fell through to "?". Now reads the real field (ISS shows "Voice
Repeater", CAS-4B "Linear Transponder") with a frequency-pair fallback.

Added **two sky-track polars** to the activation detail - this station and the
activator - with the mutually-visible arc highlighted, reusing the same helper
the mutual-pass report uses. A mutual window is a geometry question and two
plots answer it faster than a start/end pair.

**2. `'PassPredict' object has no attribute 'aos_az'`.** The new orbit pass page
read `aos_az` / `los_az`; the real attributes are **`az_aos` / `az_los`**. My
fault when writing the page, and a plain crash on that view. Fixed, with a test
that asserts both the attribute names and that the screen source uses them.

**3. 24-row overflow.** Re-checked every screen *and every page/view* at 80x24:
no line exceeds the width and nothing draws past the last row. Clean.

**4. Parity reassessed.** A field-by-field comparison found real gaps, several
of them mine from recent work:

- **EME** - the terminal was missing Moon distance, declination, path
  degradation, libration spread, sky temperature, echo delay, Sun separation
  and ground gain. All added; the live page now matches the desktop.
- **Propagation** - the desktop screen had **no terminal twin at all**. Added,
  with MUF day/night, the per-band day/night table and all five modes.

OrbitTerm is now **37 screens**.

Still uneven, listed honestly: Orbital Analysis (~20 desktop fields the terminal
still lacks, mostly on pages I have not split yet), Radio link-budget figures,
AO-7 fit diagnostics, Sites next-pass columns, and the Learn screen's teaching
readouts.

## Parity round: OrbitTerm catches up

Measured field by field against the desktop, then closed the gaps:

| Screen | Before | After |
| --- | --- | --- |
| Orbital Analysis | 20 fields missing | 8 |
| Radio | 6 missing | 1 |
| AO-7 | 5 missing | 0 |
| Sites | 0 | 0 |

**Orbital Analysis** gained two more pages - **stats** (total passes over 7 days,
count above 30 degrees, peak elevation, best pass and duration, longest, mean
gap) and **anomaly** (mean anomaly, time to perigee and apogee, arg of perigee,
revs/day, rev at epoch, decay estimate and its solar-activity range). Six pages
now: elements, live, pass, stats, anomaly, identity.

**Radio** gained a link-budget view (`l`): slant range, free-space path loss,
EIRP, propagation delay and estimated received power, labelled as an estimate
rather than a calibrated figure.

**AO-7** gained the fit diagnostics - report agreement, mode changes seen, timer
start and the confidence note. Without them the phase reads authoritative even
when it rests on three reports.

Two attribute bugs of the kind that has bitten repeatedly, both caught by
rendering rather than by reading the code: the anomaly page used `mean_anom`
when the field is `ma`, and the link budget did `downlink_center or downlink`
where `downlink_center` is a **method** - so the bound method was compared as a
number. A test now renders every orbit page and fails on error text.

The remaining eight Orbital Analysis differences are wording (`At apogee` vs
`To apogee`) or fields on desktop pages not yet split; the five EME ones are
label wording for data the terminal already shows.

## Reported issues, round 4

**Transponder not seeded from the activation.** CardSat's `parseActivationFreq`
scans the activation's frequency field (then its comment), matches it against
each **two-way** transponder's downlink and uplink ranges with a +/-20 kHz
tolerance, and fixes that leg. Ported as `match_transponder()`: a downlink match
selects fixed-downlink anchored on DX RX, an uplink match fixed-uplink on DX TX.
Defaulting to the first transponder ignored what the operator had told you and
could show the wrong passband. `scan_freq_hz()` deliberately ignores bare
integers - "Max el 50" is not 50 MHz.

**Max elevation was always None.** The feed's figure is the *activator's* and is
usually absent. The column now computes **your** elevation for that pass, which
is the number that decides whether the activation is workable at all, and reads
an em dash when it cannot.

**No way to read the activation notes.** The feed carries a comment - what the
activator is doing, which pass, any conditions - with no way to see it. A
**Notes** button shows the full record.

**OrbitTerm could not enter an EME grid.** It was hardcoded to JO65. `e` now
edits it. That exposed a real robustness gap: `grid_to_latlon()` does **not**
validate - it turns "ZZZZ" into (202.5, 405.0) and "nonsense" into a
real-looking pair - so a new `valid_grid()` checks the form before any typed
grid is trusted, in the TUI settings too.

**TUI References was unreadable.** With 14 tables the horizontal chooser strip
ran off 80 columns and its truncated tail overlapped the next label. Replaced
with a paged indicator (`name (n/14)`, left/right to change). The fixed 8/16
column widths also truncated values; they now scale with the pane.

## Decay estimate was using the wrong model

Asked to double-check it against CardSat, and it was wrong: **both** orbit
screens called `analysis.estimate_decay_days` - the **pre-refit** formula - not
the recalibrated `engine.decay` model ported from CardSat 0.9.68. The gap is the
one CardSat documented:

| case | old (shown) | recalibrated |
| --- | --- | --- |
| ISS-like | 308 days | 2.7 years |
| 550 km cubesat | 14.4 years | 59.3 years |
| 300 km | 8 days | 70 days |
| GTO e=0.72 | 42.4 years | effectively stable |

So the screens were reporting roughly a fifth of the true remaining life -
exactly the error the refit existed to fix. Porting the model and then leaving
the callers pointed at the old one made the work invisible. Three call sites
switched (desktop, TUI elements page, TUI anomaly page), with a test that fails
if any screen calls the old function again.

Two related corrections: the estimate now shows **which anchor** it used
(observed decay rate or B*), and the solar min/max **range is only shown on the
B\* path** - anchoring on the observed n-dot cancels the solar scale by
construction, so low/high printed the same number twice and implied a confidence
interval that was not there.

## MUF: DXCC lookup

The region table answers "how is Europe"; `muf_to_dxcc()` answers "can I work JA
right now", matching on prefix or entity name and returning a row per match.
Both front-ends.

## A concurrency bug found by the test suite

The suite began aborting the interpreter. The cause was real, not a test
artifact: background workers call `root.after()` when they finish, and a worker
outliving its window raised "main thread is not in main loop" - and under test
could abort. A guarded `Screen._ui()` now drops the callback when the window has
gone, applied to 14 screens.

## Reported issues, round 5

**1. Seeding did not change the table.** Two faults. The passband was opened at
mid-band and called seeded - so the anchored dial sat at the transponder centre,
not the stated frequency. `solve_pb_for_dial()` now converges the offset so the
anchored dial actually reads it (verified holding 145.8650 MHz across a whole
window on CAS-4B's linear transponder), the same way CardSat's
`dxdStepAnchorDial` converges.

The second fault mattered more: **ISS's transponder is FM/single-channel**, and
a "fixed" mode there is meaningless - there is no passband to move, so the
"held" dial was just the stated frequency plus that station's Doppler, dressed
up as an anchor. Seeding now checks `is_linear` and leaves a single-channel bird
in true rule, saying so: *"activation names 437.8000 MHz on the downlink;
Voice Repeater is single-channel, so every dial Doppler-tracks"*.

**2. A CelesTrak 404 read as an error.** For a name query, 404 means *no object
matches*, not a broken request. It now returns an empty result (and caches it),
so the screen says the satellite is not in the catalog instead of showing an
HTTP status.

**3. Printing gaps.** A `_report` method with no button is not printable. Report
buttons added to 18 more screens including **Orbital History**, which now
produces a real PDF from its window and summary. A test walks every nav screen
and fails if one has neither a report control nor a `_report` method.

## Audit items C and D

**MUF map.** `muf_grid()` runs MINIMUF to a lat/lon grid and the MUF screen
shades it over the coastline basemap with the QTH marked. The region table gives
24 representative centres; the map shows the *shape* of the opening - where the
band edge actually falls - which rows cannot.

**Link margin vs elevation.** `link_margin_curve()` computes slant range from a
spherical Earth at each elevation and returns received power and margin from
horizon to zenith. At 500 km on 2 m that is a **14 dB** spread, and the horizon
rows are what decide a marginal link. Added as a Tools calculator.

**DXCC lookup.** Prefix or entity name to entity and coordinates, in Tools and
on the MUF screen.

**GP-fit diagnostics.** `fit_diagnostics()` reports what a state-vector fit
rests on - radius, speed, circular speed at that radius and their ratio - and
flags the unit mix-ups (metres for kilometres, m/s for km/s) that otherwise
produce a converged-looking element set from nonsense.

### One thing deliberately not built

CQ/ITU **zone** drill-downs. The bundled tables are ranges with regional
descriptions, not polygons, so a zone cannot be derived from a location. A first
cut tried and put **Japan in "17-19 Asiatic Russia"** - because that row's
description contains the word "Asia". A wrong zone in a contest log is worse
than no zone, so the lookup returns the entity and coordinates and leaves the
zone tables to be read directly. Doing this properly needs real zone boundary
data, which OrbitDeck does not ship.

Field weather and the Doppler-lock practice display remain unbuilt; the first
needs a new Open-Meteo integration, the second is a training aid rather than an
operating tool.

## Parity and text-fit sweep

**Parity.** Measured field by field: 41 desktop labels had no TUI counterpart,
but 33 were wording differences for data the terminal already shows ("Moon
azimuth" vs "Moon az / el"). The 8 genuine gaps are closed: eclipse depth,
two-way path loss, cold-sky temperature, moon illuminated fraction, closest
approach, and the planning/sites fields. Screen inventories match apart from
Learn, which is desktop-only by earlier decision.

**Text fit.** Both front-ends now measure clean.

*OrbitTerm* - swept every screen **and every page** at 80x24, flagging any line
wider than the terminal or any body line ending in an ellipsis. 32 problems
found, all fixed:

- **Passes** used `ljust(line, w - x0)` where `w` is already the content width,
  so every row was shortened twice and lost MAXEL and both azimuths - the three
  columns you plan a pass with. (Same bug I had fixed in the satellite list; it
  was in Passes too.)
- EME per-band, Orbital History summary and the MUF header were simply too wide;
  columns narrowed.
- The radar sub-point lost its longitude - the half that says where the
  satellite is - so it wraps to two lines now.
- Tools clipped full-precision values. That one cannot be solved by narrowing:
  a 17-digit float is one unbroken token and it is long *because* the digits are
  the point, so `_wrap()` breaks mid-token rather than discarding the answer.

*Desktop* - measured every mapped label against its own rendered text width. 58
clipped labels found. The Tools and References sidebars could not fit their own
longest entries ("Microstrip/stripline Z0", "Phonetic alphabet"); several status
and readout labels had no `wraplength` and simply ran out of widget.

Both sweeps are now regression tests, so neither can quietly regress.

## The passband solver assumed a response it never measured

Reported: an RS-44 activation naming a **145.95 MHz uplink** showed DX TX at
**145.9941**. The frequency match was correct - 145.95 is 15 kHz below RS-44's
published 145.965 uplink edge and lands inside the +/-20 kHz tolerance on the
uplink leg. The **solver** was wrong.

`solve_pb_for_dial()` nudged the passband by the error each iteration, which
assumes the anchored dial moves **1:1 and in the same direction** as the
passband. On an **inverting** transponder - which most linear birds are,
RS-44 included - the uplink dial moves the *opposite* way, so every step pushed
the offset further from the target. It ran the offset to -148 kHz and settled
about 12 kHz out.

I had verified only the downlink leg, where the assumption happens to hold. The
solver now **measures the derivative** with a probe and takes Newton steps, so
inversion, the ~0.4% Doppler ratio and either leg are all handled without
assuming anything. Verified to **0.0 Hz error on all four anchors** (my RX, my
TX, DX RX, DX TX) across a full window.

It also now returns 0 when the dial does not respond to the passband at all -
an FM or single-channel transponder - rather than a large bogus offset that
would look like a solved answer.

## Release packaging (0.38.0)

- **CHANGELOG** — the 0.38.0 entry had accumulated 337 bullets and 168 repeated
  section headers from per-round appends. Consolidated into one readable
  Added/Changed/Fixed entry.
- **README** — the screen table documented 23 of 38 screens; rebuilt in nav
  order with all 38. The OrbitTerm section was rewritten (37 screens, standalone
  configuration, 80x24, UTC).
- **orbitterm/README** — listed 11 of 37 screens and still documented the
  number-key navigation that was removed. Rebuilt.
- **MANUAL** — screen count corrected.
- **Packaging** — release dates updated in the metainfo and RPM changelog;
  version verified consistent at 0.38.0 across pyproject, RPM, Deb, PKGBUILD
  and metainfo. Wheel and sdist build, and the wheel installs into a clean venv
  with both `orbitdeck` and `orbitterm` entry points working.

**Screenshots were not regenerated.** Without a window manager the capture
leaves an unpainted block over part of the frame; adding openbox fixed the nav
and header but a Tk canvas region still only repaints on a real expose event.
Rather than commit images with a black rectangle through the middle, the
existing screenshots are left in place. The new screens (Propagation, the MUF
map, EME analysis, Orbital History views) still need capturing on a real
display.

## Screenshots — and the bug they uncovered

The black rectangle in earlier captures was not a repaint failure: it was the
**welcome dialog**, a Toplevel sitting over the app. Destroying any Toplevel
before capturing produced clean images immediately.

That unblocked the screenshots, and the first clean MUF capture then showed an
**empty table** - which turned out to be a real production bug.

**Worker results were being silently dropped.** `Screen._ui()` called
`root.after()` from the worker thread. Tk is not thread-safe and can refuse
that, and the bare `except Exception: pass` I had added earlier - to stop
workers crashing after their window closed - swallowed the refusal. The screen
sat on "Computing..." forever with no error. **Every threaded screen was
affected**: MUF, zones, conjunctions, transits, planning, sky-at-a-glance,
workable, orbital history.

The fix is a queue drained by the Tk main loop, started in `__init__` **on the
main thread** - starting it lazily from `_ui()` reproduced the same trap, since
the first call could itself come from a worker. Worker exceptions now surface
through `_worker_failed()` instead of leaving a plausible-looking status.

This is the second time a broad `except Exception: pass` turned a visible
failure into a silent one. Verified afterwards that no threaded screen stays
stuck, and the zones status label - which had never had content before - needed
a `wraplength` once it did.

**60 screenshots** are now current: 38 desktop screens plus 17 OrbitTerm screens
rendered from real 80x24 curses output. Every image reference in the READMEs and
manual resolves.

## 0.38.1 — standalone OrbitTerm for every platform

OrbitTerm was already in every Linux package (deb via pybuild, rpm explicitly,
Arch via the wheel, AppImage via `AppRun ... term`, Flatpak inside the sandbox)
and in the pip wheel. What it was **not** in was the PyInstaller standalone
downloads, which build only the GUI - so anyone grabbing a release binary for
Windows, macOS or a Pi got no terminal UI.

`orbitterm.spec` builds it separately. That is a deliberate choice rather than
adding a second binary to the desktop bundle: importing every OrbitTerm screen
pulls in **no** matplotlib, tkinter, numpy, cartopy, PIL or openpyxl - verified,
not assumed - so excluding them yields **8.6 MB** against the desktop bundle's
couple of hundred. One file, console mode, because a terminal app should be
something you `scp` to a headless box and run.

Built for five targets on a release tag: Windows, macOS arm64 **and x86_64**
(Intel Macs get no desktop bundle today, but a 9 MB terminal build costs
nothing), Linux x86_64 and Pi arm64. Windows pulls `windows-curses`, which its
console needs.

The workflow smoke-tests each binary through a **pty** and fails the build if no
screen renders - a `--version` check would prove nothing for a curses program.
Verified locally: the binary runs detached from the source tree and renders its
header and catalog.

Flatpak now documents `flatpak run --command=orbitterm ...`; OrbitTerm was
always installed there but only the desktop command was exported.

A packaging matrix in `PACKAGING.md` records which artifact carries what, since
"is OrbitTerm in this download?" had five different answers.

**Both front-ends now ship in the desktop bundle as well.** Asked whether
OrbitTerm was in the main builds, I checked rather than answered from the spec
alone - built the desktop bundle and searched every file including inside the
archives. It was **not** there: the spec never mentioned `orbitterm` and the GUI
never imports it, so PyInstaller had no path to discover it.

`orbitdeck.spec` now runs a second `Analysis` on `runterm.py` and `MERGE`s the
two, so shared dependencies are stored once. The bundle goes from **343 MB to
350 MB** - about 7 MB for a whole second application, because the Python
runtime, engine and data were already in there. Verified by copying the built
bundle elsewhere and running both binaries: OrbitTerm renders its header and
catalog, the GUI launches with no import errors.

The workflow now fails the build if `OrbitTerm` is missing from the bundle on
any platform. Without that check the second entry point could silently stop
building and the download would quietly lose the terminal UI again - which is
exactly the state 0.38.0 shipped in.

**One thing to watch:** the blanket 0.38.0 -> 0.38.1 version bump rewrote the
*existing* changelog entries in the RPM spec and `debian/changelog`, so 0.38.0's
history briefly claimed to be 0.38.1. Repaired, and worth remembering that a
global version replace is not safe in files that carry version history.

## 0.38.2 — OrbitTerm audit

**Settable values.** Audited every screen's `__init__` for literals never
reassigned anywhere else. Two were genuinely stuck: the **Mutual Windows DX
grid** (fixed at FN31) and the Planning target. The grid is now editable with
`e`, matching EME, Orbital History and Tools; a malformed locator is rejected
and the previous grid kept. Conjunctions' "other object" looked fixed but is
already cyclable.

**CelesTrak search.** OrbitTerm could not add a satellite missing from the local
catalog, so you had to open the desktop app for it. `s` on the Satellites screen
now searches CelesTrak by name or NORAD, lists the hits, and adds the selected
one — re-checking by NORAD first so an object already held under another name is
starred rather than duplicated.

A subtlety worth recording: the search block had to go at the **top** of
`handle_key`. Placed after the navigation keys, `j`/`k` and ENTER were consumed
by list movement while typing, so the field never saw them.

**Graphical distortion — measured, not guessed.** Braille dots are square (2
across, 4 down, against a roughly 1:2 cell), and the radar measured **0.94:1**,
so circles were already round. The real fault was the world map: an
equirectangular projection needs a **2:1** area and the map filled the pane
instead, stretching continents about **30% vertically**. Fitting the widest 2:1
box gives **2.04:1**.

The second fault was worse and mine: the map outlined a coarse land/sea
**rectangle mask**, and outlining a grid of rectangles can only produce
rectangles. It now draws the bundled coastline **vectors** the desktop map uses,
which is what braille is actually for. The result is a recognisable world map.

**Truncation audit.** Swept every screen and page at 80x24 for clipped lines and
for dates without a year. The important find is the one reported: Orbital
History showed `Sun 13 Dec` for its peak-rate date and axis endpoints, on an
archive spanning **2015 to 2026** — genuinely ambiguous. `fmt_clock(...)[:10]`
was slicing the year off. New `fmt_ymd` / `fmt_ymd_hm` are for any value not
confined to the next few days; `fmt_date` keeps its short form for pass tables,
where the year is never in doubt.

**Interface consistency.** `e` edits a value, `f` filters, `g` scans, `s`
searches remotely, `p` pages, ESC cancels. The Satellites screen labelled `/`
as "search" when it filters the local list, which made two different actions
look like one; it now reads "filter", with `s` for CelesTrak.

### Both closed

**QRZ** now has an OrbitTerm screen: lookup from Settings credentials, showing
name, class, grid, address and country, plus distance and bearing from your
station - the reason to look a call up mid-pass. The session key is cached for
the run; re-logging in per lookup would burn the account's query allowance.

**Activation detail** is mirrored. The terminal had windows and a Doppler table
but carried both faults the desktop had fixed in 0.38.0: it read
`.description` (which does not exist - the attribute is `.desc`) so every
transponder read "tp", and it opened mid-passband instead of the stated
frequency. Both fixed, including the single-channel case, where a "fixed" mode
is meaningless and true rule is the honest reading. A notes page shows the
activator's own comment. Sky-track polars remain desktop-only - two side-by-side
polar plots do not fit a terminal usefully.

Two layout faults surfaced while rendering it: the notes page wrote a second
header over the one already drawn ("Activation detailFN31"), and the four dial
columns did not fit 80 columns - the unit moved to the header.


## Polar plot geometry, measured

Asked to double-check the polar displays, the earlier measurement had only
covered the radar's ring **grid** (0.94:1, round) and never asked whether the
plotted **objects** landed on it. They did not.

A marker at the horizon is drawn at `+/-2*radius` cells and `+/-radius` rows -
`4*radius` dots either way, since a braille cell is 2 dots across and 4 down.
The ring canvas was sized `radius*2+1` by `radius+1`, giving a circle of about
`2*radius` dots: exactly **half**. Everything below roughly 60 degrees elevation
was plotted outside the drawn horizon ring, which makes the rings worse than
useless - they actively mislead about elevation.

Measured before: grid spanned columns 11-27 while markers ran 2-49. After
resizing the canvas to `radius*4+1` by `radius*2+1`, the ring is round at
0.97:1 and objects sit inside it.

The globe and OSCARLOCATOR both use `cols = rows*2`, which is the correct
relationship for square dots, and measured **exactly 1.00:1**. They draw their
grid and their objects on the same canvas in dot space, so the two cannot
disagree - which is the structural reason the radar was the only one wrong: it
was the only display drawing its grid on the canvas and its objects in
character cells.

## Legibility pass

Rendered every screen and page and read them, rather than checking for
exceptions.

**Palette.** Three faults, all in `ui.py`:

- `CLR_DIM` was **blue**. On a dark background that is the least legible colour
  in most terminal palettes, and it is by far the most-used pair - 166 call
  sites covering labels, units and help text. Now white with `A_DIM`.
- `CLR_HEADER` was the **same yellow as `CLR_WARN`**, so a column heading and a
  warning were indistinguishable. Headers are now white and bold.
- Both attributes now travel with the pair through `cp()`, so structure still
  reads on a terminal without colour instead of collapsing to flat text.

**Colour semantics.** Red was being used for *direction*: a receding satellite,
an eclipse, and the negative half of a Doppler curve all rendered as faults. If
red means "normal thing happening", it stops meaning "look at this". Red is now
reserved for genuine warnings - imminent decay, the now-marker - and direction
reads as green versus accent.

**Edge clipping.** Text cut flush at the pane edge carries no ellipsis, so a
truncated value reads as a complete one: "sat below horizon" appeared as
"sat below horiz", and the Radio screen's note as "...for current geomet".
Three strings shortened to fit. A test now walks every screen and fails on text
that ends flush at the pane edge in lower case, which is the signature of a
mid-word cut.

**A test of mine that was flaky by construction.** The workable-filter test
compared two live snapshots of what is under the footprint - which moves between
calls - so a prefix taken from one might not exist in the next. Rewritten to
assert properties within a single snapshot.
