"""
satdb.py - satellite catalog (port of CardSat's satdb).

Holds GP/OMM mean elements per satellite plus transponder data, and parses
the AMSAT GP JSON and SatNOGS transmitters JSON the device uses.
"""

import json
import math
import datetime as _dt
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Transponder:
    desc: str = ""
    downlink: int = 0          # Hz (low edge / single channel)
    downlink_high: int = 0     # Hz (high edge; 0 if single-channel)
    uplink: int = 0
    uplink_high: int = 0
    mode: str = ""
    invert: bool = False
    is_linear: bool = False
    tone_hz: float = 0.0
    tx_type: str = ""          # SatNOGS "type": Transmitter/Transceiver/Transponder
    baud: float = 0.0          # data rate, if any
    service: str = ""          # Amateur, etc.

    def bandwidth(self) -> int:
        return (self.downlink_high - self.downlink) if self.downlink_high > self.downlink else 0

    def downlink_center(self) -> int:
        """Center frequency of the downlink. For a linear transponder this is
        the midpoint of the passband (not the low edge); for a single-channel
        transmitter it's just the downlink frequency."""
        if self.downlink_high and self.downlink_high > self.downlink:
            return (self.downlink + self.downlink_high) // 2
        return self.downlink

    def uplink_center(self) -> int:
        if self.uplink_high and self.uplink_high > self.uplink:
            return (self.uplink + self.uplink_high) // 2
        return self.uplink

    def kind(self) -> str:
        """A short human label for the transponder type."""
        m = (self.mode or "").upper()
        if self.is_linear:
            return "Linear (inverting)" if self.invert else "Linear"
        if "FM" in m:
            return "FM"
        if "CW" in m or "BEACON" in (self.desc or "").upper():
            return "CW/Beacon"
        # digital / data modes
        for tag in ("BPSK", "GMSK", "FSK", "AFSK", "GFSK", "QPSK", "MSK",
                    "LORA", "DUV", "APRS", "AX.25", "AX25"):
            if tag in m or tag in (self.desc or "").upper():
                return "Data (%s)" % tag
        if self.tx_type:
            return self.tx_type
        return m or "Transmitter"


@dataclass
class SatEntry:
    name: str = ""
    norad: int = 0
    intl_des: str = ""
    epoch_unix: float = 0.0
    incl: float = 0.0          # deg
    ecc: float = 0.0
    raan: float = 0.0          # deg
    argp: float = 0.0          # deg
    ma: float = 0.0            # deg
    mean_motion: float = 0.0   # rev/day
    bstar: float = 0.0
    ndot: float = 0.0          # rev/day^2
    nddot: float = 0.0         # rev/day^3
    rev_at_epoch: int = 0
    elset_num: int = 0
    amsat_status: int = 0      # 0 none,1 heard,2 not heard,3 telemetry only
    transponders: List[Transponder] = field(default_factory=list)
    is_manual: bool = False    # user-entered, persists across GP refreshes

    @property
    def jdsatepoch(self) -> float:
        return self.epoch_unix / 86400.0 + 2440587.5

    @property
    def period_min(self) -> float:
        return 1440.0 / self.mean_motion if self.mean_motion else 0.0

    @property
    def apogee_km(self) -> float:
        a = self._semi_major_km()
        return a * (1.0 + self.ecc) - 6378.135

    @property
    def perigee_km(self) -> float:
        a = self._semi_major_km()
        return a * (1.0 - self.ecc) - 6378.135

    def _semi_major_km(self) -> float:
        mu = 398600.8
        n = self.mean_motion * 2.0 * math.pi / 86400.0  # rad/s
        if n <= 0:
            return 0.0
        return (mu / (n * n)) ** (1.0 / 3.0)


def _gp_epoch_to_unix(s: str) -> float:
    """Parse an OMM EPOCH 'YYYY-MM-DDTHH:MM:SS.ffffff' (or space sep) to unix."""
    s = s.strip().replace('T', ' ')
    if '.' in s:
        main, frac = s.split('.')
        frac = float('0.' + frac)
    else:
        main, frac = s, 0.0
    dt = _dt.datetime.strptime(main, '%Y-%m-%d %H:%M:%S')
    dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.timestamp() + frac


class SatDb:
    def __init__(self):
        self.sats: List[SatEntry] = []

    def count(self) -> int:
        return len(self.sats)

    def index_of_norad(self, norad: int) -> int:
        for i, s in enumerate(self.sats):
            if s.norad == norad:
                return i
        return -1

    def get(self, norad: int) -> Optional[SatEntry]:
        i = self.index_of_norad(norad)
        return self.sats[i] if i >= 0 else None

    # ---- GP / OMM JSON ----
    def load_gp_json(self, text: str) -> int:
        data = json.loads(text)
        self.sats = []
        return self._ingest(data, replace=True)

    def append_gp_json(self, text: str) -> int:
        data = json.loads(text)
        return self._ingest(data, replace=False)

    def _ingest(self, data, replace: bool) -> int:
        if isinstance(data, dict):
            data = [data]
        n = 0
        for o in data:
            try:
                e = _parse_omm(o)
            except Exception:
                continue
            if not replace:
                idx = self.index_of_norad(e.norad)
                if idx >= 0:
                    e.transponders = self.sats[idx].transponders
                    self.sats[idx] = e
                    n += 1
                    continue
            self.sats.append(e)
            n += 1
        return n

    # ---- SatNOGS transmitters ----
    @staticmethod
    def parse_transmitters_json(text: str, max_n: int = 64) -> List[Transponder]:
        arr = json.loads(text)
        out: List[Transponder] = []
        for t in arr:
            if len(out) >= max_n:
                break
            if t.get('status') and t.get('status') != 'active':
                continue
            tp = Transponder()
            tp.desc = (t.get('description') or '')[:60]
            dl = t.get('downlink_low')
            dlh = t.get('downlink_high')
            ul = t.get('uplink_low')
            ulh = t.get('uplink_high')
            tp.downlink = int(dl) if dl else 0
            tp.downlink_high = int(dlh) if dlh else 0
            tp.uplink = int(ul) if ul else 0
            tp.uplink_high = int(ulh) if ulh else 0
            tp.mode = (t.get('mode') or '')[:12]
            tp.invert = bool(t.get('invert'))
            tp.is_linear = tp.downlink_high and tp.downlink_high > tp.downlink
            tp.tx_type = (t.get('type') or '')[:20]
            try:
                tp.baud = float(t.get('baud')) if t.get('baud') else 0.0
            except (ValueError, TypeError):
                tp.baud = 0.0
            tp.service = (t.get('service') or '')[:20]
            out.append(tp)
        return out


# ---- manual entry: build / serialize satellites and transponders ----
def make_manual_sat(name, norad, epoch_unix, incl, raan, ecc, argp, ma,
                    mean_motion, bstar=0.0, intl_des=""):
    """Construct a user-entered SatEntry from GP mean elements."""
    e = SatEntry()
    e.name = name.strip() or ("NORAD %s" % norad)
    e.norad = int(norad)
    e.intl_des = intl_des
    e.epoch_unix = float(epoch_unix)
    e.incl = float(incl)
    e.raan = float(raan)
    e.ecc = float(ecc)
    e.argp = float(argp)
    e.ma = float(ma)
    e.mean_motion = float(mean_motion)
    e.bstar = float(bstar)
    e.is_manual = True
    return e


def sat_to_dict(e: SatEntry) -> dict:
    return {
        "name": e.name, "norad": e.norad, "intl_des": e.intl_des,
        "epoch_unix": e.epoch_unix, "incl": e.incl, "ecc": e.ecc,
        "raan": e.raan, "argp": e.argp, "ma": e.ma,
        "mean_motion": e.mean_motion, "bstar": e.bstar,
        "rev_at_epoch": e.rev_at_epoch,
    }


def sat_from_dict(d: dict) -> SatEntry:
    e = make_manual_sat(
        d.get("name", ""), d.get("norad", 0), d.get("epoch_unix", 0.0),
        d.get("incl", 0.0), d.get("raan", 0.0), d.get("ecc", 0.0),
        d.get("argp", 0.0), d.get("ma", 0.0), d.get("mean_motion", 0.0),
        d.get("bstar", 0.0), d.get("intl_des", ""))
    e.rev_at_epoch = int(d.get("rev_at_epoch", 0))
    return e


def make_manual_transponder(downlink, uplink=0, downlink_high=0,
                            uplink_high=0, invert=False, mode="",
                            desc="Manual"):
    """Construct a user-entered Transponder. Linear if downlink_high > downlink
    and an uplink is present; otherwise single-channel."""
    tp = Transponder()
    tp.desc = desc or "Manual"
    tp.downlink = int(downlink or 0)
    tp.uplink = int(uplink or 0)
    tp.downlink_high = int(downlink_high or 0)
    tp.mode = (mode or "")[:12]
    tp.invert = bool(invert)
    tp.is_linear = bool(tp.downlink_high and tp.downlink_high > tp.downlink
                        and tp.uplink)
    if tp.is_linear:
        # default uplink_high to same bandwidth as the downlink if not given
        if uplink_high and int(uplink_high) > tp.uplink:
            tp.uplink_high = int(uplink_high)
        else:
            tp.uplink_high = tp.uplink + (tp.downlink_high - tp.downlink)
    return tp


def tx_to_dict(tp: Transponder) -> dict:
    return {
        "desc": tp.desc, "downlink": tp.downlink, "uplink": tp.uplink,
        "downlink_high": tp.downlink_high, "uplink_high": tp.uplink_high,
        "mode": tp.mode, "invert": tp.invert, "is_linear": tp.is_linear,
    }


def tx_from_dict(d: dict) -> Transponder:
    tp = Transponder()
    tp.desc = d.get("desc", "Manual")
    tp.downlink = int(d.get("downlink", 0))
    tp.uplink = int(d.get("uplink", 0))
    tp.downlink_high = int(d.get("downlink_high", 0))
    tp.uplink_high = int(d.get("uplink_high", 0))
    tp.mode = d.get("mode", "")
    tp.invert = bool(d.get("invert", False))
    tp.is_linear = bool(d.get("is_linear",
                               tp.downlink_high > tp.downlink and tp.uplink))
    return tp


def _f(o, *keys, default=0.0):
    for k in keys:
        if k in o and o[k] is not None:
            try:
                return float(o[k])
            except Exception:
                pass
    return default


def _parse_omm(o: dict) -> SatEntry:
    e = SatEntry()
    e.name = (o.get('AMSAT_NAME') or o.get('OBJECT_NAME') or
              o.get('NAME') or '')[:25]
    e.norad = int(_f(o, 'NORAD_CAT_ID'))
    e.intl_des = (o.get('OBJECT_ID') or '')[:11]
    ep = o.get('EPOCH')
    e.epoch_unix = _gp_epoch_to_unix(ep) if ep else 0.0
    e.incl = _f(o, 'INCLINATION')
    e.ecc = _f(o, 'ECCENTRICITY')
    e.raan = _f(o, 'RA_OF_ASC_NODE')
    e.argp = _f(o, 'ARG_OF_PERICENTER')
    e.ma = _f(o, 'MEAN_ANOMALY')
    e.mean_motion = _f(o, 'MEAN_MOTION')
    e.bstar = _f(o, 'BSTAR')
    e.ndot = _f(o, 'MEAN_MOTION_DOT')
    e.nddot = _f(o, 'MEAN_MOTION_DDOT')
    e.rev_at_epoch = int(_f(o, 'REV_AT_EPOCH'))
    e.elset_num = int(_f(o, 'ELEMENT_SET_NO'))
    return e
