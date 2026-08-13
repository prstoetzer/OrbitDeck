"""orbitdeck.engine.basichost - live data for Tiny BASIC's system names.

The interpreter knows nothing about satellites; this supplies the numbers behind
`SATAZ`, `MYLAT`, `UTCH`, `SFI` and the rest, plus `SATSEL` and `TXSEL`.

Two rules carried over from the card, because they are what let a program be
written once and run anywhere:

  * every value is a **number**, and an unavailable one reads **0** with its
    matching `...OK` flag at 0. A program branches on `SATOK` rather than
    halting, so a catalog scan survives a satellite with a dead element set.
  * `SATSEL` treats a bad *index* as an error but a satellite that cannot be
    propagated as merely `SATOK = 0`.
"""

import time

from .tinybasic import SYS_NAMES as _ALL


class BasicHost:
    """Supplies system values from a Store, without the interpreter knowing."""

    def __init__(self, store, now=None):
        self.store = store
        self.now = now if now is not None else time.time()
        self._sat = None          # the SATSELed satellite, if any
        self._pred = None

    # ---- helpers ---------------------------------------------------------
    def _obs(self):
        return getattr(self.store, "obs", None)

    def _spacewx(self):
        try:
            return self.store.load_spacewx_cache() or {}
        except Exception:
            return {}

    def _predictor(self, sat):
        from .predict import Predictor
        pred = Predictor()
        obs = self._obs()
        if obs is not None:
            pred.set_site(obs)
        if not pred.set_sat(sat):
            return None
        return pred

    # ---- the snapshot ----------------------------------------------------
    def snapshot(self):
        """Every system value at the moment the program starts."""
        out = {name: 0.0 for name in _ALL}
        tm = time.gmtime(self.now)
        out.update({
            "UTCH": float(tm.tm_hour), "UTCM": float(tm.tm_min),
            "UTCS": float(tm.tm_sec), "UTCDAY": float(tm.tm_mday),
            "UTCMON": float(tm.tm_mon), "UTCYR": float(tm.tm_year),
            "TIMEOK": 1.0,
            "UPTIME": 0.0,
        })
        obs = self._obs()
        if obs is not None and getattr(obs, "valid", True):
            out.update({"MYLAT": float(obs.lat), "MYLON": float(obs.lon),
                        "MYALT": float(getattr(obs, "alt_m", 0.0)),
                        "POSOK": 1.0})
        db = getattr(self.store, "db", None)
        if db is not None:
            out["NSAT"] = float(len(getattr(db, "sats", []) or []))
        out["NFAV"] = float(len(getattr(self.store, "favorites", ()) or ()))

        sw = self._spacewx()
        got = False
        for name, key in (("SFI", "flux"), ("KP", "kp"), ("AINDEX", "a_index"),
                          ("SSN", "ssn")):
            v = sw.get(key)
            if v is not None:
                out[name] = float(v)
                got = True
        if got:
            out["SPWXOK"] = 1.0
            try:
                from .propagation import simple_muf_mhz
                muf = simple_muf_mhz(sw.get("flux"), sw.get("kp") or 0.0, True)
                if muf:
                    out["MUF"] = float(muf)
            except Exception:
                pass

        # Sun and Moon from the observer's site.
        if obs is not None and getattr(obs, "valid", True):
            try:
                from .celestial import moon_azel
                from .transits import _sun_azel
                saz, sel = _sun_azel(obs.lat, obs.lon, self.now)
                maz, mel = moon_azel(obs.lat, obs.lon, self.now)
                out.update({"SUNAZ": float(saz), "SUNEL": float(sel),
                            "MOONAZ": float(maz), "MOONEL": float(mel)})
            except Exception:
                pass

        # The currently selected satellite, so a program that never calls
        # SATSEL still sees something sensible - as on the card.
        try:
            sat = self.store.selected_sat()
        except Exception:
            sat = None
        if sat is not None:
            out.update(self._sat_values(sat) or {})
        return out

    # ---- SATSEL / TXSEL --------------------------------------------------
    def select_sat(self, index):
        """Values for catalog entry ``index``, or None if the index is bad."""
        db = getattr(self.store, "db", None)
        sats = list(getattr(db, "sats", []) or []) if db else []
        if not 0 <= index < len(sats):
            return None                      # a bad INDEX is an error
        sat = sats[index]
        self._sat = sat
        vals = self._sat_values(sat)
        if vals is None:
            # Valid index but no fix or a dead element set: SATOK = 0 so the
            # program can skip it and carry on scanning.
            self._pred = None
            return {"SATOK": 0.0,
                    "NTX": float(len(getattr(sat, "transponders", []) or []))}
        return vals

    def _sat_values(self, sat):
        pred = self._predictor(sat)
        ntx = float(len(getattr(sat, "transponders", []) or []))
        if pred is None:
            return None
        self._pred = pred
        try:
            look = pred.look(self.now)
            lat, lon, alt = pred.subpoint_at(self.now)
        except Exception:
            return None
        out = {
            "SATAZ": float(look.az), "SATEL": float(look.el),
            "SATRNG": float(look.range_km), "SATRR": float(look.range_rate),
            "SATLAT": float(lat), "SATLON": float(lon), "SATALT": float(alt),
            "SATSUN": 1.0 if getattr(look, "sunlit", False) else 0.0,
            "SATINC": float(sat.incl), "SATECC": float(sat.ecc),
            "SATRAAN": float(sat.raan), "SATMM": float(sat.mean_motion),
            "SATNOR": float(sat.norad), "SATOK": 1.0, "NTX": ntx,
        }
        # Doppler on the two common satellite bands, as the card reports.
        c = 299792.458
        out["DOPPRX"] = -145.8e6 * look.range_rate / c
        out["DOPPTX"] = -435.0e6 * look.range_rate / c
        try:
            from . import decay as DK
            days, _src = DK.estimate_decay_days(
                sat.mean_motion, sat.ecc, sat.bstar,
                getattr(sat, "ndot", 0.0) or 0.0)
            out["DECAYD"] = 0.0 if days in (None, float("inf")) or days < 0 \
                else float(days)
        except Exception:
            pass
        # Next pass, so a program can decide whether to bother.
        try:
            min_el = float(getattr(self.store, "min_el", 0.0) or 0.0)
            passes = pred.predict_passes(self.now, min_el, 1)
            if passes:
                p = passes[0]
                out.update({
                    "AOSIN": max(0.0, float(p.aos - self.now)),
                    "LOSIN": max(0.0, float(p.los - self.now)),
                    "PASSEL": float(p.max_el), "PASSOK": 1.0,
                    "PASSN": float(len(passes)),
                })
        except Exception:
            pass
        return out

    def select_tx(self, index):
        """Transponder ``index`` of the SATSELed satellite, or None."""
        sat = self._sat
        if sat is None:
            try:
                sat = self.store.selected_sat()
            except Exception:
                sat = None
        tps = list(getattr(sat, "transponders", []) or []) if sat else []
        if not 0 <= index < len(tps):
            return None
        tp = tps[index]
        dl = float(getattr(tp, "downlink", 0) or 0)
        ul = float(getattr(tp, "uplink", 0) or 0)
        try:
            bw = float(tp.bandwidth())
        except Exception:
            bw = 0.0
        return {
            "TXDL": dl, "TXUL": ul, "TXBW": bw,
            "TXINV": 1.0 if getattr(tp, "invert", False) else 0.0,
            "TXLIN": 1.0 if getattr(tp, "is_linear", False) else 0.0,
        }
