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
SATNOGS_TX_URL = ("https://db.satnogs.org/api/transmitters/"
                  "?format=json&satellite__norad_cat_id=")
SATNOGS_ALL_TX_URL = "https://db.satnogs.org/api/transmitters/?format=json"

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".orbitdeck")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
GP_CACHE = os.path.join(CONFIG_DIR, "gp.json")
SPACEWX_CACHE = os.path.join(CONFIG_DIR, "spacewx.json")
TX_CACHE = os.path.join(CONFIG_DIR, "transmitters.json")


class Store:
    def __init__(self):
        self.db = SatDb()
        self.obs = Observer(lat=39.93, lon=-74.89, alt_m=20.0, valid=True)
        self.favorites = set()              # set of NORAD ids
        self.selected_norad = None
        self.min_el = 5.0                   # default pass-prediction minimum
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
        self._sync_predictor()

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
    def update_gp_online(self, progress=None):
        if progress:
            progress("Fetching GP catalog from AMSAT...")
        txt = _http_get(AMSAT_GP_URL, timeout=30)
        n = self.db.load_gp_json(txt)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(GP_CACHE, "w") as f:
            f.write(txt)
        self._using_sample = False
        if (self.selected_norad is None or
                self.db.get(self.selected_norad) is None) and self.db.count():
            self.selected_norad = self.db.sats[0].norad
        self._sync_predictor()
        if progress:
            progress("Loaded %d satellites (freshest element %.1f days old)."
                     % (n, self.catalog_age_days()))
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
        }
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(c, f, indent=2)
        except Exception:
            pass


def _http_get(url, timeout=20):
    from .net import http_get
    return http_get(url, timeout=timeout)
