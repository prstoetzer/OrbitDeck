# OrbitDeck — Session Handoff Memo

_Last updated at the close of the v0.36.10 session. Read this top-to-bottom before touching anything._

---

## 0. The single most important thing

**The git repo does not persist between chat sessions.** The working tree lives at `/tmp/orbitwork` and is wiped when the session ends. Every session must begin by re-establishing the repo from the most recently delivered zip in `/mnt/user-data/outputs/` (currently `orbitdeck-0.36.9.zip`). Unzip it into `/tmp/orbitwork` and re-init git if you need commit history (the delivered zip is a `git archive` snapshot — it has the files but not the `.git` history). Practically: you start each session from the source tree, make changes, and re-deliver a new zip. Don't assume prior commits, branches, or `/tmp` helper scripts are still there.

---

## 1. What OrbitDeck is

A free, MIT-licensed, cross-platform **desktop amateur-radio satellite tracker**. Pure Python (≥3.8), Tkinter + matplotlib UI, with its own vendored pure-Python SGP4/SDP4 propagator. It is a **tracking and analysis** tool only — radio CAT control and antenna-rotator control are explicitly out of scope. Author: **Paul Stoetzer, N8HM** (AMSAT Executive Vice President). The user *is* Paul. Repo: `https://github.com/prstoetzer/OrbitDeck`. The OSCARLOCATOR web reference the sim is modeled on: `https://oscarlocator.n8hm.radio/`.

The app is a desktop port of analysis tools originally from a CardSat ESP32 hardware tracker.

**Current version: 0.36.10.** The codebase is ~50 Python files under `orbitdeck/`, 23 navigation screens, 206 test functions (202 pass, 4 skipped — the skips are environment-gated, not failures).

---

## 2. Working style (Paul's expectations)

Paul writes **terse, outcome-focused** requests, often one or two sentences naming a symptom ("Pointing tab is unclickable on macOS," "rove sheet overlaps the branding"). He expects a **complete turn**: diagnose → implement → test → screenshot-verify → version-bump → changelog → package → fresh-extract verify → deliver, all in one go. He does not want to be asked to do the legwork himself.

Things he values, learned over the session:
- **Honesty about verification limits.** Several fixes are macOS- or frozen-build-specific and cannot be reproduced in the Linux/headless sandbox. Say so plainly, explain what you *did* verify, and tell him exactly what to check on his Mac. Do not claim a macOS bug is "fixed" when you only verified it on Linux.
- **Don't over-claim.** When a fix is structurally sound but unverifiable here, call it "should fix, needs confirmation," not "fixed."
- **Own mistakes.** The v0.36.4 size-reduction shipped broke his builds; the right response was a clean revert in v0.36.6 plus an apology and a caution note, not defensiveness.
- He reads the screenshots. Render and visually confirm UI/report changes; don't just assert them.

---

## 3. Environment setup (run at the start of every session)

```bash
pip install matplotlib numpy pytest openpyxl ruff pyinstaller --break-system-packages
apt-get install -y python3-tk xvfb x11-apps imagemagick poppler-utils
# ruff lands in $HOME/.local/bin -> export PATH="$HOME/.local/bin:$PATH"
# node/npm with docx@9.6.1 is used for the AMSAT Journal .docx article builds
```

All GUI work runs headless under xvfb:
```bash
PYTHONPATH=/tmp/orbitwork xvfb-run -a --server-args="-screen 0 1280x720x24" python3 <script>
# screenshot a running Tk app: subprocess "import -window root /tmp/x.png" (ImageMagick)
# PDFs: pdftoppm -png -r 120 file.pdf /tmp/out  ; then view the PNG
```

**Critical gotcha — config must be cleared before any pytest/screenshot/harness run:**
```bash
rm -f ~/.orbitdeck/config.json      # do this EVERY time, or onboarding/state leaks in
```
In-process, dismiss the welcome/onboarding via `app.store.save_config(onboarded=True)`. Select a satellite with `app.store.select(norad)`. Toggle a favorite with `app.store.toggle_fav(norad)`. The default catalog is the **6-satellite bundled demo set** — fine for most tests; RS-44 (norad 44909) is the standard test bird (a linear inverting transponder).

---

## 4. The release ritual (follow exactly — this is non-negotiable)

Every shippable change goes through all of these, in order:

1. `ruff check orbitdeck tests` — must be clean.
2. `pytest` under xvfb — full suite green.
3. **23-screen harness:** `python3 ht_full.py` → expect `23/23 screens OK`.
4. **Scroll audit:** `python3 /tmp/scroll_audit.py` → `ALL scrollable widgets have a scrollbar sibling`.
5. Clean working tree, then commit: `git -c user.email=dev@orbitdeck.local -c user.name=orbitdeck-dev commit -q -am "..."`.
6. Package: `git archive HEAD | tar -x -C /tmp/pkg && (cd /tmp/pkg && zip -rq /tmp/orbitdeck.zip .)`.
7. **Fresh-extract verification (DO NOT SKIP):** unzip the archive into a clean `/tmp/verify`, then re-run ruff + pytest + the screen check there. **This step has caught real lint errors that a cached `ruff` run falsely passed.** Always trust the fresh-extract result over a cached one. Also confirm no `ht_full.py`/helper scripts leaked into the zip (they're gitignored and must not ship).
8. Deliver the zip as `orbitdeck-<version>.zip` plus `CHANGELOG.md` to `/mnt/user-data/outputs/` via `present_files`. Include a demo PNG when the change is visual.
9. Remove the prior-version zip from outputs.

### Version bump touches MANY files — update ALL of them every time:
- `orbitdeck/__init__.py` (`__version__`)
- `pyproject.toml` (`version`)
- `orbitdeck.spec` (`CFBundleShortVersionString`)
- `tests/test_analysis.py` — rename `test_version_is_0_36_X` **and** its assertion
- `packaging/PKGBUILD` (`pkgver`)
- `packaging/orbitdeck.spec.rpm` (`Version:` and prepend a `%changelog` entry)
- `packaging/debian/changelog` (prepend an entry)
- `packaging/.SRCINFO` (`pkgver` + tarball URL + `prefix=`)
- `packaging/PKGBUILD-git` and `packaging/.SRCINFO-git` (seed `0.XX.Y.r0.g0000000`)
- `packaging/io.github.prstoetzer.OrbitDeck.metainfo.xml` (`version=` and the `<release version date>`)
- version example strings in `packaging/BUILD.md`, `packaging/PACKAGING.md`, `docs/INSTALL.md` (sed)
- `CHANGELOG.md` (prepend a section)

After bumping, verify: `pytest tests/test_analysis.py` (the version test), the metainfo XML parses, and `grep -rn "0\.36\.<old>"` across `packaging/ docs/ README.md` returns only the historical changelog lines.

---

## 5. Helper scripts (live in `/tmp`, gitignored, NEVER shipped)

These were rebuilt during the session and must be recreated if missing (they don't persist):
- `ht_full.py` — 23-screen harness, prints `23/23 screens OK`. **This one lives in the repo root working dir but is gitignored** — recreate from memory/prior zip if absent.
- `/tmp/scroll_audit.py` — asserts every scrollable widget has a scrollbar sibling.
- `/tmp/verify_screens.py` — lighter screen check used in fresh-extract verify.
- `/tmp/reach_sweep.py` — per-screen overflow-vs-viewport detector (built this session; see §7).
- `/tmp/reach_tabs.py` — per-tab/per-group/per-mode overflow detector (built this session).
- `/tmp/shot_*.py` — many one-off screenshot helpers.

If you do a reachability audit, recreate `reach_sweep.py` and `reach_tabs.py` — they measure `frame.winfo_reqheight()` vs `winfo_height()` and check for a `Canvas` ancestor (= scrollable). See §7 for the pattern.

---

## 6. Architecture cheat-sheet

### Engine (`orbitdeck/engine/`) — no Tk, pure computation, well tested
- **`predict.py`** — `Predictor`: the core. `set_site(Observer)`, `set_sat(SatEntry)`, `look(unix)->LiveLook` (has `az`, `el`, `range_rate` km/s, +receding), `azel_at`, `predict_passes(frm, min_el, max_n, horizon_end=0.0, coarse_step=30.0)`, `predict_eclipses`, `passband_freqs` (static). Internals: `_eci_state` (SGP4 memoised on `round(unix,3)`, bounded 4096, cleared on `set_sat`), `_azel_range`, `_observer_teme`, `_geodetic_to_ecef`. **As of v0.36.9, `set_site` caches the observer ECEF position + latitude trig (`_obs_ecef`, `_obs_slat`, `_obs_clat`, `_obs_lon_rad`); `__init__` primes it via `set_site(Observer())`.** Constants: `C_LIGHT`, `RE_KM`, `E2`, `DEG`.
- **`dxdoppler.py`** — `dx_doppler(...)`, `dx_doppler_table(...)`. Modes `TRUE_RULE`/`FIXED_DL`/`FIXED_UL`; anchors `ME_RX`/`ME_TX`/`DX_RX`/`DX_TX`. `doppler_dials(dl, ul, rr)`: `rx = dl*(1-beta)`, `tx = ul/(1-beta)`, `beta = rr*1000/c` (+receding). Verified physically correct: approaching → RX higher / TX lower.
- **`planning.py`** — `best_passes_for_target`, `rove_stop_passes`, `sky_coverage_grid`.
- **`satdb.py`** — `SatDb` (`load_gp_json`), `SatEntry`, `Transponder(downlink, downlink_high, uplink, uplink_high, invert, is_linear)`, `.bandwidth()`. Linear inverting test birds: RS-44 (44909), CAS-4B (42761).
- **`sgp4_lite.py`** — the propagator. `sgp4()` is ~30% of engine runtime; it's the inherent floor. Left untouched on purpose — micro-optimizing it risks correctness. The realistic next speed lever is NumPy vectorization (big rewrite) or accepting approximation; not worth it for the gain so far.
- **`linkbudget.py`, `analysis.py`, `celestial.py`, `propagator.py`.**

### GUI (`orbitdeck/gui/`)
- **`app.py`** — `OrbitDeckApp`, `NAV_ITEMS` (the 23 screens, in nav order), the once-per-second `_tick` (only updates the current screen if it's `live`), font-scaling (`_set_font_scale` rescales the Tk named fonts including `TkDefaultFont`).
- **`screens/__init__.py`** — base `Screen`; **`KVPanel`** (grouped key/value readout; `begin/section/row/note/end`; matches rows by label to update in place and avoid flicker; `self.outer` is its frame); **`TabBar`** (see §8 — it has macOS-specific subtleties); `MplPanel` (`.draw()` → `draw_idle()`, already optimal); **`make_vscroll_frame(parent) -> (container, interior)`** (the auto-hiding vertical scroller used to fix every "content taller than window" bug — see §7); `make_scrolled_tree`, `autohide_scrollbar`. Color constants: `COL_BG="#0d1117"`, `COL_PANEL="#161b22"`, `COL_ACCENT="#2f81f7"`, `COL_TEXT="#e6edf3"`, `COL_MUTED="#8b949e"`, `COL_GRID="#30363d"`. Tab font: `TAB_FONT="TkDefaultFont"` (NOT "DejaVu Sans" — see §8).
- **23 screen files** in `screens/`: home, track, globe (3D), radar, passes, passdetail, groundtrack, tenday (Pass Progression), orbit (Orbital Analysis), illum, mutual (Mutual Windows), grids (Workable), radio, planning, oscarsim, learn, exportscreen, sunmoon, celestial, spacewx, satellites, sites, location (Settings). (`analytics.py` is a shared base for several analysis screens.)
- **PDF/print generators** (each carries the centered footer credit "OrbitDeck v<ver> • Paul Stoetzer, N8HM" at `y=0.045`):
  - **`reports.py`** — the big one. `_PdfFlow` flow-layout engine (cursor `self.y`, `ensure(need)` floor now **0.085**, `_new_page`, `paragraph/table/kv_two_col`). `_brand_fig` (y=0.045). Generators: satellite, favorites_passes, site_comparison, mutual_passes, progression, eclipse, polar_passes. `_pass_polar_grid` (shared grid; cell floor **0.10**).
  - **`rovesheet.py`** — `generate_rove_sheet_pdf`. **Separate generator, does NOT use `_PdfFlow`.** Rewritten in v0.36.9 to paginate by measured entry height with `BRAND_FLOOR=0.10`, align label+value with shared `va="top"`, and keep full DXCC names.
  - **`learnsheet.py`** — `generate_orbits_101_pdf` (the "Handouts" — fixed reference content, verified clear of branding; a margin-constraint comment was added).
  - **`doppler_sheet.py`** — single-page Doppler playbook; bounded, fine.
  - **`refsheet.py`** — reference-orbits sheet. **This is an OSCARLOCATOR companion — leave it alone** (see §9).
  - **`oscarlocator.py`** — OSCARLOCATOR map/sheet rendering. **Leave alone** (see §9).
- **`store.py`** (`app.store`: config, favorites, selection, observer), `alarms.py`, `net.py`, `pagesize.py` (Letter vs A4), `exports.py`, `lab.py`/`labdialog.py` (lab orbit editor + Challenges), `mapdraw.py`, `passcard.py`, `radioedu.py`, `spacewx.py`.

---

## 7. The recurring bug pattern: "content taller than the window"

This class of bug surfaced **four+ times** this session (Settings, lab Challenges launcher, Orbital Analysis Info readout, Radio link-budget readout). The pattern: a screen or panel packs more content than the viewport height, with no scrollbar, so the bottom is silently clipped and looks "missing" or "dropped."

**The fix every time:** wrap the overflowing content in `make_vscroll_frame(parent)`, which returns `(container, interior)`. Pack the container where the old frame went; parent the content to `interior`. For panels swapped in/out (like orbit's KV vs plot surfaces), swap the **scroller container**, not the inner panel's `.outer`.

**The detector** (`/tmp/reach_sweep.py`): for each screen, compare `frame.winfo_reqheight()` to `winfo_height()`; if it overflows AND there's no `Canvas` in the widget subtree, it's clipped-without-scroll. `/tmp/reach_tabs.py` extends this by exercising every TabBar tab/group and every oscarsim drive mode, because **clipping can hide inside a non-default tab or mode** (that's how the lab Challenges bug hid).

**As of v0.36.9 the full sweep is clean** — all 23 screens in default state, every tab on every tabbed screen (Learn's 5 groups, Radio, Orbital Analysis's pages, Planning, Settings), and all oscarsim modes are reachable. **If you add or substantially change a screen, re-run the sweep.** A worthwhile longer-term refactor Paul might appreciate: make the screen container scroll by default instead of patching panels one at a time — but scope it carefully, it's a bigger change.

---

## 8. macOS / TabBar subtleties (don't regress these)

The `TabBar` in `screens/__init__.py` had two macOS-specific bugs fixed this session. **Linux/xvfb cannot reproduce macOS Aqua event delivery**, so these were fixed structurally and confirmed by Paul on his Mac (from source — see §10 for the open item):
- **Click delivery:** Aqua does not reliably deliver `<Button-1>` to a `tk.Label` nested in frames. Tabs now bind **both `<Button-1>` and `<ButtonRelease-1>`** on the holder, label, AND indicator strip; handlers return `"break"`. (v0.36.3 bound the whole holder; v0.36.5 added the release event, which was the actual fix.)
- **Font:** the tab strip uses `TAB_FONT="TkDefaultFont"`, not the Linux-only `"DejaVu Sans"` (which macOS silently substitutes with different metrics, perturbing the wrap layout).
- **Wrap layout:** `select_group` defers a re-layout via `after_idle` using the true bar width (early `winfo_width()` can be stale/1), grows the bar to fit wrapped rows, and **preserves the current tab** on reflow/deferred-relayout instead of snapping to the group's first tab.

General principle: **any tab/click/focus fix needs confirmation on a real Mac.** State that explicitly when you ship one.

---

## 9. Hard "do not touch" list

- **OSCARLOCATOR outputs** — `oscarlocator.py` and the reference-orbits sheet `refsheet.py`. Paul explicitly said OSCARLOCATOR sheets are fine; do not apply report/branding/layout changes to them. They already clear the footer by design.
- **`sgp4_lite.py` `sgp4()`** — core propagation math. Don't micro-optimize it.
- **Re-enabling UPX** in `orbitdeck.spec` — UPX corrupts native DLLs (numpy, matplotlib's `ft2font`, PROJ) → "DLL load failed" crashes. It's disabled on purpose. Never turn it back on.
- **Aggressive bundle-size trimming** — the v0.36.4 attempt (a `_trim_datas` data filter + scipy/pandas excludes) broke all builds and was reverted in v0.36.6. The frozen app needs more of the conda-forge geospatial payload than static analysis suggests (cartopy reaches for it at runtime). `BUILD.md` documents this with a caution. If you ever retry, you MUST build and smoke-test every platform's artifact first — which you can't do in this sandbox, so effectively: don't, unless Paul has a real build loop.

---

## 10. Open items / things to confirm

- **macOS frozen-build confirmation (OPEN).** Paul confirmed v0.36.5 fixed the unclickable tabs **from source** on macOS, but had **not yet tested the GitHub-built (PyInstaller-frozen) macOS app**. The fix uses `TkDefaultFont` (present in bundled Tk) and plain Tk events, so it should hold in the frozen app — but this is unconfirmed. Ask him to run the GitHub build and click Pointing / Link budget. If still broken, the key diagnostic question is: *does the tab highlight (text turns blue) but content not switch, or does nothing happen at all?* — that separates a selection-event problem from a render problem.
- **CI / Raspberry Pi build (`build.yml`).** The arm64 Pi target (`ubuntu-22.04-arm` → `OrbitDeck-raspberrypi-arm64`) is present and was hardened: per-OS "Verify build output" steps, GEOS/PROJ via apt for the cartopy sdist (no arm64 wheel), `setup-python` confirmed to support 22.04-arm. **22.04 is on a deprecation path** (26.04 GA'd June 2026); when it's retired, move to the oldest arm64 image whose glibc ≤ the target Pi OS (Bookworm = 2.36), or a self-hosted Pi runner. None of the CI has been confirmed green by an actual run from this sandbox — Paul should trigger a build once and watch the Pi job's cartopy-from-sdist + verify-output steps.
- **Speed.** v0.36.9 added the observer-geometry cache (~14% on engine-heavy work, bit-identical). The remaining floor is `sgp4()`. A profile of a **full-catalog load** (not the 6-sat demo) would show whether catalog-scale costs justify more work — worth doing if Paul reports sluggishness with a big satellite set.
- **The "content taller than window" pattern** (§7) keeps recurring; a default-scrolling screen container is the real fix if Paul wants to invest in it.

---

## 11. Session changelog (v0.36.1 → v0.36.9) — what shipped and why

- **v0.36.1** `fe731ba` — Flattened stray label backgrounds (`Muted/Mono/Panel.TLabel`, `Panel.TFrame`, etc. → `COL_BG`; `KVPanel`'s deliberate `COL_PANEL` cards kept). Added `make_vscroll_frame`; made Settings scroll on short displays.
- **CI** `3b8d24b`/`c55c827` — Raspberry Pi arm64 build target + per-OS build-output verification; setup-python arm64 support confirmed; deprecation guidance in BUILD.md.
- **v0.36.2** `bccf67e` — DX Doppler: show dial frequencies to the **Hz** (was kHz-rounded), so the home station's small near-overhead Doppler is visible instead of looking frozen. Engine + CSV were already correct; display-only fix. Verified inversion + DX-anchor locking.
- **v0.36.3** `ddfdc48` — Made the whole tab area clickable (holder+label+indicator), not just the label text. (Helped but did NOT fully fix macOS — see v0.36.5.)
- **v0.36.4** `ffea2e7` — **Bundle-size reduction. THIS BROKE ALL BUILDS. Reverted in v0.36.6.** Do not resurrect.
- **v0.36.5** `c284fc1` — The real macOS tab fix: `<ButtonRelease-1>` binding + `TkDefaultFont` + timing-robust wrap layout that preserves the selected tab. Confirmed by Paul from source on macOS.
- **v0.36.6** `d12349f` — Reverted the v0.36.4 size changes (spec now byte-identical to pre-0.36.4). Fixed printed reports overlapping the footer branding: raised the progression timeline chart bottom, the `_PdfFlow.ensure` floor (0.06→0.085), table header floor (→0.10), polar-grid cell floor (→0.10), mutual-row floor (→0.10). OSCARLOCATOR sheets untouched.
- **v0.36.7** `e23a8e9` — Made the OSCARLOCATOR Sim control column scrollable so the lab "Challenges…" launcher (and Trace-orbits control) at the bottom are reachable. The feature was never dropped — it was clipped below an overflowing column.
- **v0.36.8** `657e3ec` — Reachability sweep across all screens/tabs/modes; wrapped the Orbital Analysis Info readout and the Radio link-budget readout in scrollers (their lower sections were clipped). Built `reach_sweep.py`/`reach_tabs.py`.
- **v0.36.9** `f79fd39` — Rove plan sheet: fixed label/value alignment (shared `va="top"`), branding overlap (measured-height pagination, `BRAND_FLOOR=0.10`), and full DXCC names (was truncating "United States"→"United"). Speed: cached observer ECEF/lat-trig in the predictor (~14%, bit-identical).

Also delivered this session (non-code, in `/mnt/user-data/outputs/`): the **AMSAT Journal article** `.docx` (credited to Paul, with the "generated by Claude, edited by the author" disclaimer), an **iOS porting reference** `.docx`, a `.pptx`, the standalone `build.yml`, and many demo PNGs.

---

## 12. Quick-start checklist for the next session

1. Unzip `orbitdeck-0.36.9.zip` (or whatever is newest in outputs) into `/tmp/orbitwork`; `git init` + initial commit if you want history.
2. Install deps (§3); `export PATH="$HOME/.local/bin:$PATH"`.
3. Recreate `ht_full.py`, `/tmp/scroll_audit.py`, `/tmp/verify_screens.py` if absent.
4. Sanity: `rm -f ~/.orbitdeck/config.json && ruff check orbitdeck tests && xvfb-run -a python3 -m pytest tests/ -q` → expect 202 passed / 4 skipped.
5. Read Paul's request, reproduce the symptom (render/screenshot or profile — don't fix blind), then follow the release ritual (§4) end-to-end.
6. Be honest about what you could and couldn't verify here, especially anything macOS- or frozen-build-specific.
