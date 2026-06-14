"""sunmoon.py - Sun and Moon position/illumination for the observer site."""

import math
import tkinter as tk
from tkinter import ttk

from . import (Screen, COL_TEXT, COL_MUTED, FONT_MONO, fmt_utc, now_unix,
               compass)
from ...engine.predict import _sun_eci_unit, _gmst_rad, jd_of, DEG


def _sun_altaz(lat, lon, t):
    jd = jd_of(t)
    sx, sy, sz = _sun_eci_unit(jd)
    th = _gmst_rad(jd)
    lst = th + lon * DEG
    ss, cs = math.sin(lst), math.cos(lst)
    slat, clat = math.sin(lat * DEG), math.cos(lat * DEG)
    e = -ss * sx + cs * sy
    n = -slat * cs * sx - slat * ss * sy + clat * sz
    u = clat * cs * sx + clat * ss * sy + slat * sz
    el = math.degrees(math.atan2(u, math.hypot(e, n)))
    az = math.degrees(math.atan2(e, n)) % 360
    return az, el


def _moon_eci_unit(jd):
    # Low-precision lunar position (Meeus-ish), ecliptic -> equatorial unit.
    d = jd - 2451545.0
    L = math.radians((218.316 + 13.176396 * d) % 360)
    M = math.radians((134.963 + 13.064993 * d) % 360)
    F = math.radians((93.272 + 13.229350 * d) % 360)
    lon = L + math.radians(6.289) * math.sin(M)
    lat = math.radians(5.128) * math.sin(F)
    eps = math.radians(23.439)
    x = math.cos(lat) * math.cos(lon)
    y = (math.cos(eps) * math.cos(lat) * math.sin(lon) -
         math.sin(eps) * math.sin(lat))
    z = (math.sin(eps) * math.cos(lat) * math.sin(lon) +
         math.cos(eps) * math.sin(lat))
    return x, y, z


def _moon_altaz_phase(lat, lon, t):
    jd = jd_of(t)
    mx, my, mz = _moon_eci_unit(jd)
    th = _gmst_rad(jd)
    lst = th + lon * DEG
    ss, cs = math.sin(lst), math.cos(lst)
    slat, clat = math.sin(lat * DEG), math.cos(lat * DEG)
    e = -ss * mx + cs * my
    n = -slat * cs * mx - slat * ss * my + clat * mz
    u = clat * cs * mx + clat * ss * my + slat * mz
    el = math.degrees(math.atan2(u, math.hypot(e, n)))
    az = math.degrees(math.atan2(e, n)) % 360
    # phase: angle between sun and moon ecliptic longitudes
    d = jd - 2451545.0
    sun_lon = (280.460 + 0.9856474 * d) % 360
    moon_lon = (218.316 + 13.176396 * d) % 360
    phase = (moon_lon - sun_lon) % 360
    illum = (1 - math.cos(math.radians(phase))) / 2
    return az, el, phase, illum


def _phase_name(phase):
    names = ["New", "Waxing crescent", "First quarter", "Waxing gibbous",
             "Full", "Waning gibbous", "Last quarter", "Waning crescent"]
    return names[int(((phase + 22.5) % 360) / 45)]


class SunMoonScreen(Screen):
    live = True

    def build(self):
        self.header("Sun / Moon")
        self.text = tk.Text(self.frame, bg="#161b22", fg=COL_TEXT,
                            font=FONT_MONO, borderwidth=0, height=16, wrap="word")
        self.text.pack(fill="both", expand=True, padx=16, pady=10)

    def on_show(self):
        self._render(now_unix())

    def on_tick(self, now_dt):
        self._render(now_dt.timestamp())

    def _render(self, t):
        lat, lon = self.store.obs.lat, self.store.obs.lon
        saz, sel = _sun_altaz(lat, lon, t)
        maz, mel, phase, illum = _moon_altaz_phase(lat, lon, t)
        lines = [
            "Observer  %.3f, %.3f  (grid %s)" % (lat, lon, self.store.my_grid()),
            "Time      %s" % fmt_utc(t),
            "",
            "SUN",
            "  Azimuth    %.1f\u00b0 %s" % (saz, compass(saz)),
            "  Elevation  %+.1f\u00b0  (%s)" % (
                sel, "up" if sel > 0 else ("twilight" if sel > -18 else "night")),
            "",
            "MOON",
            "  Azimuth    %.1f\u00b0 %s" % (maz, compass(maz)),
            "  Elevation  %+.1f\u00b0" % mel,
            "  Phase      %s  (%.0f%% illuminated)" % (_phase_name(phase),
                                                       illum * 100),
        ]
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
