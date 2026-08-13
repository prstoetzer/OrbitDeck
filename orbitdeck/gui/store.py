"""
store.py - application state and controller shared across GUI screens.

Holds the catalog, the observer site, favorites, and the active predictor,
plus persistence (JSON config) and optional online GP/transponder fetch.
Network fetches use only the Python standard library so there are no required
pip dependencies.
"""

import json
import os
import time

from ..engine import SatDb, Predictor, Observer, latlon_to_grid, grid_to_latlon
from ..data.sample_data import sample_gp_json, sample_tx_for, SAMPLE_TX

AMSAT_GP_URL = "https://newark192.amsat.org/gpdata/current/daily-bulletin.json"
# CelesTrak GP groups (OMM JSON). The user can pick a category or a custom URL.
CELESTRAK_BASE = "https://celestrak.org/NORAD/elements/gp.php?FORMAT=json&GROUP="
CELESTRAK_GROUPS = [
    ("Amateur Radio", "amateur"),
    ("CubeSats", "cubesat"),
    ("Space Stations", "stations"),
    ("Last 30 Days' Launches", "last-30-days"),
    ("Active Satellites", "active"),
    ("Weather", "weather"),
    ("NOAA", "noaa"),
    ("GOES", "goes"),
    ("Earth Resources", "resource"),
    ("Galileo", "galileo"),
    ("GPS Operational", "gps-ops"),
    ("Science", "science"),
    ("Geostationary", "geo"),
    # debris groups - useful loaded as the catalog source and screened against
    # a favorite in the Conjunctions screen
    ("Debris: Fengyun-1C", "1999-025"),
    ("Debris: Iridium-33", "iridium-33-debris"),
    ("Debris: Cosmos-2251", "cosmos-2251-debris"),
    ("Debris: Cosmos-1408", "cosmos-1408-debris"),
    ("Analyst Satellites", "analyst"),
]
SATNOGS_TX_URL = ("https://db.satnogs.org/api/transmitters/"
                  "?format=json&satellite__norad_cat_id=")
SATNOGS_ALL_TX_URL = "https://db.satnogs.org/api/transmitters/?format=json"

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".orbitdeck")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
GP_CACHE = os.path.join(CONFIG_DIR, "gp.json")
SPACEWX_CACHE = os.path.join(CONFIG_DIR, "spacewx.json")
TX_CACHE = os.path.join(CONFIG_DIR, "transmitters.json")
MANUAL_SATS = os.path.join(CONFIG_DIR, "manual_sats.json")
MANUAL_TX = os.path.join(CONFIG_DIR, "manual_tx.json")
# "extras": objects added by searching CelesTrak that the primary GP source does
# not carry. Unlike manual sats these ARE re-fetched from CelesTrak on every GP
# update so their elements never go stale.
EXTRAS_SATS = os.path.join(CONFIG_DIR, "extras.json")


class Store:
    def __init__(self):
        self.db = SatDb()
        self.obs = Observer(lat=39.93, lon=-74.89, alt_m=20.0, valid=True)
        self.obs_name = "Home"              # nickname for the primary site
        self.sites = []                     # secondary sites: list of dicts
        #   {"name": str, "lat": float, "lon": float, "alt_m": float}
        self.favorites = set()              # set of NORAD ids
        self.selected_norad = None
        self.min_el = 5.0                   # default pass-prediction minimum
        self.tp_index_by_norad = {}         # norad -> selected transponder idx
        self.gp_source = {"kind": "amsat"}  # amsat | celestrak | custom
        self.prefs = {}                     # free-form UI/app preferences
        # CelesTrak-search courtesy limiting (shared IPs must not get banned):
        # >=10 s between searches, identical query within 2 h served from cache,
        # extras re-fetch at most once / 2 h (timestamp persisted in prefs).
        self._last_search_t = 0.0
        self._search_cache = {}             # query -> (unix_t, results)
        self.pred = Predictor()
        self._load_config()
        self._load_catalog()

    @property
    def config(self):
        """Read-only view of persisted UI/app preferences."""
        return self.prefs if isinstance(self.prefs, dict) else {}

    # ---- catalog loading ----
    def _load_catalog(self):
        loaded = False
        if os.path.exists(GP_CACHE):
            try:
                with open(GP_CACHE) as f:
                    self.db.load_gp_json(f.read())
                # Reject a stale cache: if even the newest element is well past
                # SGP4's useful window, fall back to fresh (today-stamped)
                # sample data rather than predict from dead elements.
                loaded = self.db.count() > 0 and self.catalog_age_days() < 21
            except Exception:
                loaded = False
        if not loaded:
            self.db.load_gp_json(sample_gp_json())
            for s in self.db.sats:
                self._attach_sample_tx(s)
            self._using_sample = True
        else:
            self._using_sample = False
        self.pred.set_site(self.obs)
        if self.db.count() and self.selected_norad is None:
            self.selected_norad = self.db.sats[0].norad
        # if the remembered selection isn't in this catalog, pick the first
        if self.selected_norad is not None and \
                self.db.get(self.selected_norad) is None and self.db.count():
            self.selected_norad = self.db.sats[0].norad
        # apply any cached transponder DB to the whole catalog
        self._apply_tx_cache()
        # merge user-entered satellites and transponders (persist across refreshes)
        self._merge_manual()
        self._merge_extras()
        self._sync_predictor()

    # ---- manual (user-entered) satellites and transponders ----
    def _load_manual_sats(self):
        try:
            with open(MANUAL_SATS) as f:
                return json.load(f)
        except Exception:
            return []

    def _save_manual_sats(self, items):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(MANUAL_SATS, "w") as f:
                json.dump(items, f)
        except Exception:
            pass

    def _load_manual_tx(self):
        try:
            with open(MANUAL_TX) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_manual_tx(self, by_norad):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(MANUAL_TX, "w") as f:
                json.dump(by_norad, f)
        except Exception:
            pass

    def _merge_manual(self):
        """Add user-entered satellites to the catalog and append user-entered
        transponders to each satellite. Called after every catalog/cache load so
        manual data survives GP and transponder refreshes."""
        from ..engine.satdb import sat_from_dict, tx_from_dict
        # manual satellites: add if not already present (manual overrides)
        for d in self._load_manual_sats():
            try:
                e = sat_from_dict(d)
            except Exception:
                continue
            idx = self.db.index_of_norad(e.norad)
            if idx >= 0:
                # keep any transponders already attached, replace elements
                e.transponders = self.db.sats[idx].transponders
                self.db.sats[idx] = e
            else:
                self.db.sats.append(e)
        # manual transponders: append to the satellite's existing list
        by_norad = self._load_manual_tx()
        for s in self.db.sats:
            extra = by_norad.get(str(s.norad))
            if extra:
                s.transponders = list(s.transponders) + [
                    tx_from_dict(d) for d in extra]

    def add_manual_sat(self, entry):
        """Persist a user-entered SatEntry and add it to the live catalog."""
        from ..engine.satdb import sat_to_dict
        items = [d for d in self._load_manual_sats()
                 if int(d.get("norad", -1)) != entry.norad]
        items.append(sat_to_dict(entry))
        self._save_manual_sats(items)
        idx = self.db.index_of_norad(entry.norad)
        if idx >= 0:
            entry.transponders = self.db.sats[idx].transponders
            self.db.sats[idx] = entry
        else:
            self.db.sats.append(entry)
        self.select(entry.norad)

    def remove_manual_sat(self, norad):
        """Delete a user-entered satellite from the persisted store AND the live
        catalog. If it was the selected satellite, selection is cleared."""
        norad = int(norad)
        items = [d for d in self._load_manual_sats()
                 if int(d.get("norad", -1)) != norad]
        self._save_manual_sats(items)
        # also drop any manual transponders attached to it
        by_norad = self._load_manual_tx()
        if str(norad) in by_norad:
            del by_norad[str(norad)]
            self._save_manual_tx(by_norad)
        # remove from the live catalog
        idx = self.db.index_of_norad(norad)
        if idx >= 0:
            del self.db.sats[idx]
        if self.selected_norad == norad:
            self.selected_norad = (self.db.sats[0].norad
                                   if self.db.sats else None)
            self._sync_predictor()
        self.favorites.discard(norad)

    def update_manual_sat(self, entry):
        """Update an existing manual satellite in place (same NORAD). This is
        add_manual_sat with replace semantics; the NORAD is the key."""
        self.add_manual_sat(entry)

    def add_manual_transponder(self, norad, tp):
        """Persist a user-entered Transponder for a satellite and attach it."""
        from ..engine.satdb import tx_to_dict
        by_norad = self._load_manual_tx()
        by_norad.setdefault(str(int(norad)), []).append(tx_to_dict(tp))
        self._save_manual_tx(by_norad)
        s = self.db.get(int(norad))
        if s is not None:
            s.transponders = list(s.transponders) + [tp]

    def load_tx_cache(self):
        """The cached SatNOGS transmitter database, grouped by NORAD id.

        Returns {} when nothing is cached yet, so a caller can decide whether
        to fetch rather than being handed a silent empty result.
        """
        try:
            with open(TX_CACHE) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def cache_transmitters(self, norad, records):
        """Store transmitter records already in hand under the shared cache.

        Data fetched for one purpose should not be thrown away and fetched
        again for the next: the caller has the records, so adding a satellite
        needs no further network.
        """
        if not records:
            return False
        data = self.load_tx_cache()
        data[str(int(norad))] = list(records)
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(TX_CACHE, "w") as f:
                json.dump(data, f)
        except Exception:
            return False
        try:
            self._apply_tx_cache()
            self._merge_manual()
        except Exception:
            pass
        return True

    def _apply_tx_cache(self):
        """Attach transponders from a cached SatNOGS dump (by NORAD) to every
        matching satellite in the catalog, if the cache exists."""
        try:
            with open(TX_CACHE) as f:
                by_norad = json.load(f)
        except Exception:
            return 0
        attached = 0
        for s in self.db.sats:
            lst = by_norad.get(str(s.norad))
            if lst:
                s.transponders = SatDb.parse_transmitters_json(
                    json.dumps(lst))
                attached += 1
        return attached

    def catalog_age_days(self):
        """Age (days) of the freshest element in the catalog, or a large
        number if empty. Smaller is better; > ~14 means predictions drift."""
        if not self.db.count():
            return 1e9
        now = time.time()
        newest = max(s.epoch_unix for s in self.db.sats)
        return (now - newest) / 86400.0

    def using_sample(self):
        return getattr(self, "_using_sample", True)

    def _attach_sample_tx(self, sat):
        if sat.norad in SAMPLE_TX:
            sat.transponders = SatDb.parse_transmitters_json(
                sample_tx_for(sat.norad))

    def _sync_predictor(self):
        s = self.selected_sat()
        if s:
            self.pred.set_site(self.obs)
            self.pred.set_sat(s)

    # ---- selection ----
    def selected_sat(self):
        if self.selected_norad is None:
            return None
        return self.db.get(self.selected_norad)

    def select(self, norad):
        self.selected_norad = norad
        self._sync_predictor()

    # ---- CelesTrak "extras" (searched-and-added, auto-updating) ----
    def _load_extras(self):
        try:
            with open(EXTRAS_SATS) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_extras(self, items):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(EXTRAS_SATS, "w") as f:
                json.dump(items, f)
        except Exception:
            pass

    def _merge_extras(self):
        """Fold CelesTrak-sourced extra objects into the live catalog.

        Called after every catalog/cache load. Unlike manual sats, extras are
        refreshed from CelesTrak by refresh_extras(); here we just add their
        (possibly cached) elements if the primary source doesn't carry them.
        """
        from ..engine.satdb import _parse_omm
        for d in self._load_extras():
            rec = d.get("omm") or {}
            try:
                e = _parse_omm(rec)
            except Exception:
                continue
            if e.norad and self.db.index_of_norad(e.norad) < 0:
                self.db.sats.append(e)

    def is_extra(self, norad):
        return any(int(d.get("norad", -1)) == int(norad)
                   for d in self._load_extras())

    def add_extra_sat(self, hit, make_favorite=True):
        """Add a CelesTrak search hit as an auto-updating extra + favorite.

        ``hit`` is a dict from satsearch.parse_results (norad, name, omm).
        Persisted to extras.json and merged into the live catalog immediately;
        later GP updates re-fetch its elements from CelesTrak.
        """
        from ..engine.satdb import _parse_omm
        norad = int(hit["norad"])
        items = [d for d in self._load_extras()
                 if int(d.get("norad", -1)) != norad]
        items.append({"norad": norad, "name": hit.get("name", "?"),
                      "omm": hit.get("omm", {})})
        self._save_extras(items)
        try:
            e = _parse_omm(hit.get("omm", {}))
            idx = self.db.index_of_norad(norad)
            if idx >= 0:
                e.transponders = self.db.sats[idx].transponders
                self.db.sats[idx] = e
            else:
                self.db.sats.append(e)
        except Exception:
            pass
        if make_favorite:
            self.favorites.add(norad)
            self.save_config()
        return norad

    def remove_extra_sat(self, norad):
        """Delete a CelesTrak extra from the persisted store and live catalog."""
        norad = int(norad)
        items = [d for d in self._load_extras()
                 if int(d.get("norad", -1)) != norad]
        self._save_extras(items)
        idx = self.db.index_of_norad(norad)
        if idx >= 0:
            del self.db.sats[idx]
        if self.selected_norad == norad:
            self.selected_norad = (self.db.sats[0].norad
                                   if self.db.sats else None)
            self._sync_predictor()
        self.favorites.discard(norad)

    def search_celestrak(self, query, force=False):
        """Search the entire CelesTrak catalog by name or NORAD number.

        Courtesy limits: >=10 s between distinct searches, and an identical query
        within 2 h is served from the in-memory cache. Returns a list of hit
        dicts (satsearch.parse_results). Raises ValueError with a friendly
        message on a too-soon or rate-limit condition.
        """
        import time as _time
        from . import satsearch
        q = (query or "").strip()
        if not q:
            return []
        now = _time.time()
        cached = self._search_cache.get(q.lower())
        if cached and not force and (now - cached[0]) < 7200:
            return cached[1]
        if not force and (now - self._last_search_t) < 10.0:
            wait = max(1, int(10.0 - (now - self._last_search_t) + 0.5))
            raise ValueError("Please wait %d s between CelesTrak searches "
                             "(their servers are shared)." % wait)
        url, _kind = satsearch.search_url(q)
        self._last_search_t = now
        try:

            txt = _http_get(url, timeout=20)

        except RuntimeError as exc:

            msg = str(exc)

            if "404" in msg:

                # CelesTrak answers 404 for a query that matches

                # nothing, which is an empty result, not a failure.

                self._search_cache[q.lower()] = (now, [])

                return []

            raise
        # A 404 from a NAME query means CelesTrak has no object matching it -
        # not a broken URL. Reporting the raw HTTP status made "this satellite
        # is not in the catalog" look like a bug in OrbitDeck.
        if satsearch.looks_rate_limited(txt):
            raise ValueError("CelesTrak is rate-limiting requests \u2014 wait a "
                             "couple of hours and try again.")
        results = satsearch.parse_results(txt)
        self._search_cache[q.lower()] = (now, results)
        return results

    def refresh_extras(self, progress=None, force=False):
        """Re-fetch each extra's current elements from CelesTrak.

        Honors a 2 h minimum interval (timestamp persisted in prefs), spaces
        object fetches by 2 s, and caps at 25 objects per run. Returns the count
        refreshed. Safe to call from update_gp_online.
        """
        import time as _time
        from . import satsearch
        extras = self._load_extras()
        if not extras:
            return 0
        now = _time.time()
        last = (float(self.prefs.get("extras_refreshed_at", 0))
                if isinstance(self.prefs, dict) else 0.0)
        if not force and (now - last) < 7200:
            return 0
        updated = []
        n = 0
        for d in extras[:25]:
            norad = int(d.get("norad", -1))
            if norad < 0:
                updated.append(d)
                continue
            if n > 0:
                _time.sleep(2.0)
            try:
                txt = _http_get(satsearch.catnr_url(norad), timeout=20)
                hits = satsearch.parse_results(txt)
            except Exception:
                hits = []
            if hits:
                d = {"norad": norad,
                     "name": hits[0].get("name", d.get("name")),
                     "omm": hits[0].get("omm", {})}
                n += 1
                # update the live catalog entry in place with fresh elements
                try:
                    from ..engine.satdb import _parse_omm
                    e = _parse_omm(d["omm"])
                    idx = self.db.index_of_norad(norad)
                    if e.norad and idx >= 0:
                        e.transponders = self.db.sats[idx].transponders
                        self.db.sats[idx] = e
                    elif e.norad:
                        self.db.sats.append(e)
                except Exception:
                    pass
                if progress:
                    progress("Refreshed %s from CelesTrak" % d["name"])
            updated.append(d)
        updated.extend(extras[25:])
        self._save_extras(updated)
        if isinstance(self.prefs, dict):
            self.prefs["extras_refreshed_at"] = now
            self.save_config()
        if n:
            self._sync_predictor()
        return n

    def ensure_transponders(self, sat, online=False):
        if sat.transponders:
            return
        if sat.norad in SAMPLE_TX:
            self._attach_sample_tx(sat)
            return
        if online:
            try:
                txt = _http_get(SATNOGS_TX_URL + str(sat.norad), timeout=15)
                sat.transponders = SatDb.parse_transmitters_json(txt)
            except Exception:
                pass

    # ---- favorites ----
    def toggle_fav(self, norad):
        if norad in self.favorites:
            self.favorites.discard(norad)
        else:
            self.favorites.add(norad)
        self.save_config()

    def is_fav(self, norad):
        return norad in self.favorites

    # ---- observer ----
    def set_site(self, lat, lon, alt_m):
        self.obs = Observer(lat=lat, lon=lon, alt_m=alt_m, valid=True)
        self.pred.set_site(self.obs)
        self._sync_predictor()
        self.save_config()

    def set_site_from_grid(self, grid):
        ll = grid_to_latlon(grid)
        if ll:
            self.set_site(ll[0], ll[1], self.obs.alt_m)
            return True
        return False

    def my_grid(self):
        return latlon_to_grid(self.obs.lat, self.obs.lon)

    # ---- secondary sites ----
    def set_obs_name(self, name):
        self.obs_name = name or "Home"
        self.save_config()

    def add_site(self, name, lat, lon, alt_m=0.0):
        """Add a secondary observer site. Names are made unique."""
        base = (name or "Site").strip() or "Site"
        existing = {s["name"] for s in self.sites} | {self.obs_name}
        name = base
        n = 2
        while name in existing:
            name = "%s %d" % (base, n)
            n += 1
        self.sites.append({"name": name, "lat": float(lat),
                           "lon": float(lon), "alt_m": float(alt_m)})
        self.save_config()
        return name

    def remove_site(self, index):
        if 0 <= index < len(self.sites):
            self.sites.pop(index)
            self.save_config()

    def site_observer(self, site):
        """Return an Observer for a secondary-site dict."""
        return Observer(lat=site["lat"], lon=site["lon"],
                        alt_m=site.get("alt_m", 0.0), valid=True)

    def all_sites(self):
        """Return [(name, Observer), ...] with the primary first."""
        out = [(self.obs_name, self.obs)]
        for s in self.sites:
            out.append((s["name"], self.site_observer(s)))
        return out

    # ---- selected transponder (shared between Track and Radio) ----
    def selected_tp_index(self, sat):
        if sat is None:
            return 0
        idx = self.tp_index_by_norad.get(sat.norad, 0)
        n = len(getattr(sat, "transponders", []) or [])
        if n == 0:
            return 0
        return idx if 0 <= idx < n else 0

    def set_selected_tp_index(self, sat, idx):
        if sat is not None:
            self.tp_index_by_norad[sat.norad] = idx

    def selected_transponder(self, sat):
        tps = getattr(sat, "transponders", []) or [] if sat else []
        if not tps:
            return None
        return tps[self.selected_tp_index(sat)]

    # ---- transponder database (bulk) ----
    def update_transponders_online(self, progress=None):
        """Fetch the entire SatNOGS transmitter DB once, cache it grouped by
        NORAD id, and attach to every matching satellite in the catalog.
        Far faster than per-satellite fetches for a full GP catalog."""
        if progress:
            progress("Fetching transponder database from SatNOGS\u2026")
        txt = _http_get(SATNOGS_ALL_TX_URL, timeout=60)
        arr = json.loads(txt)
        by_norad = {}
        for t in arr:
            nid = t.get("norad_cat_id")
            if nid is None:
                continue
            by_norad.setdefault(str(int(nid)), []).append(t)
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(TX_CACHE, "w") as f:
                json.dump(by_norad, f)
        except Exception:
            pass
        attached = self._apply_tx_cache()
        self._merge_manual()        # keep user-entered transponders attached
        if progress:
            progress("Cached transponders for %d satellites (%d transmitters)."
                     % (attached, len(arr)))
        return attached

    # ---- space weather ----
    def load_spacewx_cache(self):
        try:
            with open(SPACEWX_CACHE) as f:
                return json.load(f)
        except Exception:
            return None

    def update_spacewx(self):
        """Fetch current indices and cache them. Returns the data dict."""
        from . import spacewx
        data = spacewx.fetch()
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(SPACEWX_CACHE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass
        return data

    # ---- online update ----
    def gp_source_url(self):
        """Resolve the configured GP source to a fetch URL and a label."""
        src = self.gp_source or {"kind": "amsat"}
        kind = src.get("kind", "amsat")
        if kind == "celestrak":
            grp = src.get("group", "amateur")
            return CELESTRAK_BASE + grp, "CelesTrak (%s)" % grp
        if kind == "custom":
            url = src.get("url", "").strip()
            if url:
                return url, "custom URL"
        return AMSAT_GP_URL, "AMSAT"

    def update_gp_online(self, progress=None):
        url, label = self.gp_source_url()
        if progress:
            progress("Fetching GP catalog from %s..." % label)
        txt = _http_get(url, timeout=30)

        # CelesTrak (and some mirrors) return an HTTP 200 with a plain-text or
        # HTML error body instead of JSON -- most often "Invalid query" or a
        # rate-limit notice (their limit is strict, a few requests per couple of
        # hours per IP). Detect that and report it clearly instead of failing
        # with a cryptic JSON error or wiping the existing catalog.
        stripped = txt.lstrip()
        if not stripped or stripped[0] not in "[{":
            snippet = " ".join(txt.split())[:120]
            low = snippet.lower()
            if "invalid query" in low or "no data" in low or not snippet:
                hint = ("%s returned no data for this group. Check the group "
                        "name or try another source." % label)
            elif "rate" in low or "throttl" in low or "limit" in low:
                hint = ("%s is rate-limiting requests. CelesTrak allows only a "
                        "few queries per couple of hours per IP \u2014 wait a "
                        "while and try again, or use AMSAT." % label)
            else:
                hint = ("%s did not return GP JSON (got: %s). The existing "
                        "catalog was kept." % (label, snippet or "empty response"))
            raise ValueError(hint)

        # parse into a temporary db so a malformed/empty payload can't clobber
        # the working catalog
        try:
            tmp = SatDb()
            n = tmp.load_gp_json(txt)
        except Exception:
            raise ValueError("%s did not return valid GP JSON. The existing "
                             "catalog was kept." % label)
        if n == 0:
            raise ValueError("%s returned an empty catalog (0 satellites). The "
                             "existing catalog was kept." % label)

        # success -- commit
        self.db.sats = tmp.sats
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(GP_CACHE, "w") as f:
            f.write(txt)
        self._using_sample = False
        # re-apply cached + manual transponders and manual satellites
        self._apply_tx_cache()
        self._merge_manual()
        # refresh CelesTrak "extras" (searched-added objects) so their elements
        # never go stale, then fold them in. Rate-limited internally (>=2 h),
        # network failures are swallowed so a GP update still succeeds offline.
        try:
            self.refresh_extras(progress=progress)
        except Exception:
            pass
        self._merge_extras()
        if (self.selected_norad is None or
                self.db.get(self.selected_norad) is None) and self.db.count():
            self.selected_norad = self.db.sats[0].norad
        self._sync_predictor()
        if progress:
            progress("Loaded %d satellites from %s (freshest element "
                     "%.1f days old)." % (n, label, self.catalog_age_days()))
        return n

    # ---- config persistence ----
    def _load_config(self):
        try:
            with open(CONFIG_PATH) as f:
                c = json.load(f)
            o = c.get("observer", {})
            self.obs = Observer(lat=o.get("lat", 39.93),
                                lon=o.get("lon", -74.89),
                                alt_m=o.get("alt_m", 20.0), valid=True)
            self.obs_name = c.get("observer_name", "Home")
            sites = c.get("sites", [])
            if isinstance(sites, list):
                self.sites = [s for s in sites
                              if isinstance(s, dict) and "lat" in s and "lon" in s]
            self.favorites = set(c.get("favorites", []))
            self.selected_norad = c.get("selected_norad")
            self.min_el = c.get("min_el", 5.0)
            src = c.get("gp_source")
            if isinstance(src, dict) and src.get("kind"):
                self.gp_source = src
            # arbitrary UI/app preferences (onboarding flag, ui_scale,
            # notifications, etc.) kept in a free-form dict
            p = c.get("prefs")
            if isinstance(p, dict):
                self.prefs = p
        except Exception:
            pass

    def save_config(self, **prefs):
        """Persist config. Any keyword arguments are merged into a free-form
        ``prefs`` dict (UI scale, onboarding flag, notification settings, ...)
        and saved alongside the structured config."""
        if not hasattr(self, "prefs") or not isinstance(self.prefs, dict):
            self.prefs = {}
        self.prefs.update(prefs)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        c = {
            "observer": {"lat": self.obs.lat, "lon": self.obs.lon,
                         "alt_m": self.obs.alt_m},
            "observer_name": self.obs_name,
            "sites": self.sites,
            "favorites": sorted(self.favorites),
            "selected_norad": self.selected_norad,
            "min_el": self.min_el,
            "gp_source": self.gp_source,
            "prefs": self.prefs,
        }
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(c, f, indent=2)
        except Exception:
            pass


def _http_get(url, timeout=20):
    from .net import http_get
    return http_get(url, timeout=timeout)


def _http_post(url, body, timeout=25):
    from .net import http_post_json
    return http_post_json(url, body, timeout=timeout)
