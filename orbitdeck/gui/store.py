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

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".orbitdeck")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
GP_CACHE = os.path.join(CONFIG_DIR, "gp.json")


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
                loaded = self.db.count() > 0
            except Exception:
                loaded = False
        if not loaded:
            self.db.load_gp_json(sample_gp_json())
            for s in self.db.sats:
                self._attach_sample_tx(s)
        self.pred.set_site(self.obs)
        if self.db.count() and self.selected_norad is None:
            self.selected_norad = self.db.sats[0].norad
        self._sync_predictor()

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

    # ---- online update ----
    def update_gp_online(self, progress=None):
        if progress:
            progress("Fetching GP catalog from AMSAT...")
        txt = _http_get(AMSAT_GP_URL, timeout=30)
        n = self.db.load_gp_json(txt)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(GP_CACHE, "w") as f:
            f.write(txt)
        if self.selected_norad is None and self.db.count():
            self.selected_norad = self.db.sats[0].norad
        self._sync_predictor()
        if progress:
            progress("Loaded %d satellites." % n)
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
    req = urllib.request.Request(url, headers={"User-Agent": "OrbitDeck/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")
