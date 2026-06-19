"""alarms.py - real-time pass alarms for all favorite satellites.

Watches the next pass of every favorited satellite and fires AOS / TCA / LOS
notifications (status-bar + a distinctive multi-beep cue) as those moments
arrive. Lightweight: it re-reads each favorite's next pass when the favorites
set changes or a pass elapses, and checks once per app tick. No background
threads -- the audible cue is scheduled with root.after so it never blocks.
"""

import time


# distinctive beep patterns per event, expressed as a list of millisecond
# delays at which to ring the bell. A short rising flutter for "soon", a firm
# double for AOS, a single mid chime for TCA, and a descending pair for LOS, so
# the four events sound clearly different from one another and from a stray
# system bell.
_PATTERNS = {
    "soon": (0, 90, 180),
    "aos": (0, 140),
    "tca": (0,),
    "los": (0, 220, 440),
}


class AlarmManager:
    def __init__(self, app):
        self.app = app
        self.enabled = False
        self._lead_s = 60.0          # "pass starting soon" lead time
        # per-norad state: {norad: {"pass": PassPredict, "fired": set()}}
        self._watch = {}
        self._fav_key = None         # detects when the favorites set changes

    def set_enabled(self, on):
        self.enabled = bool(on)
        self._watch = {}
        self._fav_key = None

    # ---- pass bookkeeping ----
    def _favorites(self, store):
        return [s for s in store.db.sats if s.norad in store.favorites]

    def _refresh_watch(self, store):
        """Rebuild the per-favorite next-pass table. Preserves already-fired
        events for passes that are still the same, so toggling other state
        doesn't replay alarms."""
        favs = self._favorites(store)
        new = {}
        now = time.time()
        for s in favs:
            try:
                pred = store.predictor_for(s) if hasattr(
                    store, "predictor_for") else self._pred_for(store, s)
                ps = pred.predict_passes(now, getattr(store, "min_el", 5.0), 1)
            except Exception:
                ps = []
            p = ps[0] if ps else None
            if not p:
                continue
            prev = self._watch.get(s.norad)
            # keep fired-state if it's the same pass (same AOS within a second)
            if prev and prev.get("pass") and abs(
                    prev["pass"].aos - p.aos) < 1.0:
                new[s.norad] = {"pass": p, "fired": prev["fired"]}
            else:
                new[s.norad] = {"pass": p, "fired": set()}
        self._watch = new

    def _pred_for(self, store, s):
        from ..engine.predict import Predictor
        p = Predictor()
        p.set_site(store.obs)
        p.set_sat(s)
        return p

    def tick(self):
        """Call once per app tick (about 1 Hz). Fires due alarms for every
        favorite satellite."""
        if not self.enabled:
            return
        store = self.app.store
        now = time.time()
        # rebuild the watch table if the favorites set changed or a watched pass
        # has elapsed
        fav_key = tuple(sorted(store.favorites))
        need_refresh = (fav_key != self._fav_key)
        for st in self._watch.values():
            p = st.get("pass")
            if p and p.los and now > p.los + 5:
                need_refresh = True
                break
        if need_refresh or not self._watch:
            self._refresh_watch(store)
            self._fav_key = fav_key

        for norad, st in self._watch.items():
            p = st.get("pass")
            if not p:
                continue
            s = store.db.get(norad)
            if not s:
                continue
            fired = st["fired"]
            self._maybe_fire(fired, "soon", p.aos - self._lead_s, now,
                             "%s rising in ~1 min (max el %.0f\u00b0)"
                             % (s.name, p.max_el))
            self._maybe_fire(fired, "aos", p.aos, now,
                             "%s AOS \u2014 now rising" % s.name)
            self._maybe_fire(fired, "tca", p.tca, now,
                             "%s TCA \u2014 max elevation %.0f\u00b0"
                             % (s.name, p.max_el))
            self._maybe_fire(fired, "los", p.los, now,
                             "%s LOS \u2014 pass over" % s.name)

    def _maybe_fire(self, fired, key, when, now, message):
        if key in fired or when <= 0:
            return
        if now >= when and now - when < 3.0:
            fired.add(key)
            self._notify(key, message)
        elif now >= when:
            # already past (e.g. app loaded mid-pass): mark fired silently
            fired.add(key)

    def _notify(self, key, message):
        try:
            self.app.set_status("\U0001f6f0 " + message)
        except Exception:
            pass
        # native desktop toast for the actionable events (pass starting soon /
        # AOS), so OrbitDeck is useful as a background companion. Gated on a
        # preference (default on) so users can silence OS toasts independently
        # of the audible cue.
        if key in ("soon", "aos"):
            try:
                prefs = getattr(self.app.store, "config", {})
                if prefs.get("desktop_notifications", True):
                    from .notify import send
                    send("OrbitDeck \u2014 pass alert", message)
            except Exception:
                pass
        self._play(_PATTERNS.get(key, (0,)))

    def _play(self, delays_ms):
        """Ring the bell in a distinctive rhythm using root.after so the UI is
        never blocked. Each entry is a delay (ms) from now at which to ring."""
        root = getattr(self.app, "root", None)
        if root is None:
            return
        for d in delays_ms:
            try:
                if d <= 0:
                    root.bell()
                else:
                    root.after(int(d), root.bell)
            except Exception:
                pass
