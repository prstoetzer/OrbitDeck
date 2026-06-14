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
import urllib.request

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


class Store:
    def __init__(self):
        self.db = SatDb()
        self.obs = Observer(lat=39.93, lon=-74.89, alt_m=20.0, valid=True)
        self.favorites = set()              # set of NORAD ids
        self.selected_norad = None
        self.min_el = 5.0                   # default pass-prediction minimum
        self.gp_source = {"kind": "amsat"}  # amsat | celestrak | custom
        self.pred = Predictor()
        self._load_config()
        self._load_catalog()

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
        items = [d for d in self._load_manual_sats()
                 if int(d.get("norad", -1)) != int(norad)]
        self._save_manual_sats(items)

    def add_manual_transponder(self, norad, tp):
        """Persist a user-entered Transponder for a satellite and attach it."""
        from ..engine.satdb import tx_to_dict
        by_norad = self._load_manual_tx()
        by_norad.setdefault(str(int(norad)), []).append(tx_to_dict(tp))
        self._save_manual_tx(by_norad)
        s = self.db.get(int(norad))
        if s is not None:
            s.transponders = list(s.transponders) + [tp]

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
            self.favorites = set(c.get("favorites", []))
            self.selected_norad = c.get("selected_norad")
            self.min_el = c.get("min_el", 5.0)
            src = c.get("gp_source")
            if isinstance(src, dict) and src.get("kind"):
                self.gp_source = src
        except Exception:
            pass

    def save_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        c = {
            "observer": {"lat": self.obs.lat, "lon": self.obs.lon,
                         "alt_m": self.obs.alt_m},
            "favorites": sorted(self.favorites),
            "selected_norad": self.selected_norad,
            "min_el": self.min_el,
            "gp_source": self.gp_source,
        }
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(c, f, indent=2)
        except Exception:
            pass


def _http_get(url, timeout=20):
    from .net import http_get
    return http_get(url, timeout=timeout)
