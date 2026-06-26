"""orbitterm/state.py - thin adapter over OrbitDeck's Store.

OrbitTerm reuses the exact OrbitDeck Store (it imports cleanly headless, with no
tkinter dependency), so the catalog, observer site, ~/.orbitdeck config, AMSAT
cache and the configured Predictor are all shared with the desktop GUI. This
guarantees OrbitTerm computes the same numbers the GUI does.

This module adds only TUI-convenience helpers on top.
"""

import time

from orbitdeck.gui.store import Store
from orbitdeck.engine.predict import Observer


class AppState:
    def __init__(self):
        self.store = Store()
        # The currently-focused satellite for detail screens. Default to the
        # store's remembered selection, else the first catalog entry.
        nor = self.store.selected_norad
        if nor is None and self.store.db.count():
            nor = self.store.db.sats[0].norad
        self.selected_norad = nor
        self.status = ""
        self.status_until = 0.0
        # cache of the last pass scan so screens can share it
        self._pass_cache = {}

    # ---- satellite selection ----
    @property
    def sats(self):
        return self.store.db.sats

    @property
    def sat(self):
        if self.selected_norad is None:
            return None
        return self.store.db.get(self.selected_norad)

    def select(self, norad):
        self.selected_norad = norad
        self.store.selected_norad = norad
        try:
            self.store.save_config()
        except Exception:
            pass

    def pred_for(self, sat):
        """Return the shared Predictor configured for a given satellite."""
        p = self.store.pred
        p.set_site(self.store.obs)
        p.set_sat(sat)
        return p

    # ---- observer ----
    @property
    def obs(self) -> Observer:
        return self.store.obs

    def grid(self):
        return self.store.my_grid()

    def set_site(self, lat, lon, alt_m=0.0, name=None):
        self.store.set_site(lat, lon, alt_m)
        if name:
            try:
                self.store.set_observer_name(name)
            except Exception:
                pass
        try:
            self.store.save_config()
        except Exception:
            pass

    @property
    def min_el(self):
        return self.store.min_el

    def set_min_el(self, v):
        self.store.min_el = max(0.0, float(v))
        try:
            self.store.save_config()
        except Exception:
            pass

    # ---- catalog ----
    def using_sample(self):
        return getattr(self.store, "_using_sample", False)

    def catalog_age_days(self):
        try:
            return self.store.catalog_age_days()
        except Exception:
            return None

    def refresh_catalog(self, progress=None):
        """Fetch a fresh GP catalog online. Returns (ok, message)."""
        try:
            self.store.update_gp_online(progress=progress)
            if self.selected_norad is None or \
                    self.store.db.get(self.selected_norad) is None:
                if self.store.db.count():
                    self.selected_norad = self.store.db.sats[0].norad
            return True, "Catalog updated (%d satellites)." % self.store.db.count()
        except Exception as e:
            return False, str(e)

    # ---- favorites ----
    def is_favorite(self, norad):
        return norad in self.store.favorites

    def toggle_favorite(self, norad):
        if norad in self.store.favorites:
            self.store.favorites.discard(norad)
        else:
            self.store.favorites.add(norad)
        try:
            self.store.save_config()
        except Exception:
            pass

    # ---- transient status line ----
    def flash(self, msg, secs=4.0):
        self.status = msg
        self.status_until = time.time() + secs

    def current_status(self):
        if self.status and time.time() < self.status_until:
            return self.status
        return ""
