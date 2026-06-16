"""alarms.py - real-time event alarms for the selected satellite.

Watches the next pass and fires AOS / TCA / LOS notifications (status-bar +
optional system bell) as those moments arrive. Lightweight: it re-reads the
next pass when the satellite changes or the current pass elapses, and checks
once per app tick. No background threads.
"""

import time


class AlarmManager:
    def __init__(self, app):
        self.app = app
        self.enabled = False
        self._sat_norad = None
        self._pass = None
        self._fired = set()          # which events fired for the current pass
        self._lead_s = 60.0          # "pass starting soon" lead time

    def set_enabled(self, on):
        self.enabled = bool(on)
        self._reset()

    def _reset(self):
        self._pass = None
        self._fired = set()

    def _refresh_pass(self, store):
        s = store.selected_sat()
        if not s:
            self._pass = None
            return
        try:
            pred = store.pred
            ps = pred.predict_passes(
                time.time(), getattr(store, "min_el", 5.0), 1)
        except Exception:
            ps = []
        self._pass = ps[0] if ps else None
        self._fired = set()
        self._sat_norad = s.norad

    def tick(self):
        """Call once per app tick (about 1 Hz). Fires due alarms."""
        if not self.enabled:
            return
        store = self.app.store
        s = store.selected_sat()
        if not s:
            return
        # (re)load the pass if the satellite changed or we have none / it elapsed
        now = time.time()
        if (self._pass is None or s.norad != self._sat_norad
                or (self._pass.los and now > self._pass.los + 5)):
            self._refresh_pass(store)
        p = self._pass
        if not p:
            return
        self._maybe_fire("soon", p.aos - self._lead_s, now,
                         "%s rising in ~1 min (max el %.0f\u00b0)"
                         % (s.name, p.max_el))
        self._maybe_fire("aos", p.aos, now, "%s AOS \u2014 now rising" % s.name)
        self._maybe_fire("tca", p.tca, now,
                         "%s TCA \u2014 max elevation %.0f\u00b0"
                         % (s.name, p.max_el))
        self._maybe_fire("los", p.los, now, "%s LOS \u2014 pass over" % s.name)

    def _maybe_fire(self, key, when, now, message):
        if key in self._fired or when <= 0:
            return
        # fire when we've just crossed the event time (within one tick window)
        if now >= when and now - when < 3.0:
            self._fired.add(key)
            self._notify(message)
        elif now >= when:
            # already past (e.g. app just loaded mid-pass): mark fired silently
            self._fired.add(key)

    def _notify(self, message):
        try:
            self.app.set_status("\U0001f6f0 " + message)
        except Exception:
            pass
        try:
            # a gentle audible cue; harmless if the platform has no bell
            self.app.root.bell()
        except Exception:
            pass
