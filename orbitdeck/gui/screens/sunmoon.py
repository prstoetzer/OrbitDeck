"""sunmoon.py - Sun and Moon position/illumination for the observer site."""

import math
from tkinter import ttk

from . import (Screen, MplPanel, KVPanel, COL_PANEL, COL_MUTED,
               COL_ACCENT, COL_WARN, COL_GRID, fmt_utc, now_unix, compass)
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
        self.header("Sun / Moon \u2014 sky view")
        body = ttk.Frame(self.frame, style="TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        # left: data panel
        left = ttk.Frame(body, style="Panel.TFrame")
        left.pack(side="left", fill="y", padx=(0, 8))
        self.kv = KVPanel(left, label_width=11)
        self.kv.pack(fill="y", padx=6, pady=8)

        # right: polar sky dome
        right = ttk.Frame(body, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.mpl = MplPanel(right, figsize=(5.2, 5.2), polar=True)
        self.mpl.pack(fill="both", expand=True, padx=6, pady=6)

    def on_show(self):
        self._render(now_unix())

    def on_tick(self, now_dt):
        self._render(now_dt.timestamp())

    def _render(self, t):
        lat, lon = self.store.obs.lat, self.store.obs.lon
        saz, sel = _sun_altaz(lat, lon, t)
        maz, mel, phase, illum = _moon_altaz_phase(lat, lon, t)

        k = self.kv
        k.begin()
        k.section("Observer")
        k.row("Site", "%.2f, %.2f" % (lat, lon))
        k.row("Grid", self.store.my_grid())
        k.row("Time", fmt_utc(t, "%H:%M:%S"))
        k.section("Sun")
        k.row("Azimuth", "%.1f\u00b0 %s" % (saz, compass(saz)))
        k.row("Elevation", "%+.1f\u00b0" % sel,
              COL_WARN if sel > 0 else COL_MUTED, big=True)
        k.row("State", "up" if sel > 0 else
              ("twilight" if sel > -18 else "night"))
        k.section("Moon")
        k.row("Azimuth", "%.1f\u00b0 %s" % (maz, compass(maz)))
        k.row("Elevation", "%+.1f\u00b0" % mel,
              COL_ACCENT if mel > 0 else COL_MUTED, big=True)
        k.row("Phase", _phase_name(phase))
        k.row("Illuminated", "%.0f%%" % (illum * 100))
        k.end()

        self._draw_dome(saz, sel, maz, mel, illum, phase)

    def _draw_dome(self, saz, sel, maz, mel, illum, phase):
        import math
        ax = self.mpl.ax
        ax.clear()
        self.mpl._style_axes()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(90, 0)             # zenith centre, horizon rim
        # ring labels follow the radius (90 at centre .. 0 at rim) so a body
        # high in the sky reads as a high elevation rather than near-horizon
        ax.set_rgrids([0, 30, 60, 90], labels=["0", "30", "60", "90"],
                      color=COL_MUTED, fontsize=7)
        ax.set_thetagrids(range(0, 360, 45),
                          labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                          color=COL_MUTED, fontsize=9)
        ax.grid(True, color=COL_GRID, linewidth=0.6)

        # Sun: rayed yellow disc (faint just outside rim if below horizon)
        s_r = sel if sel >= 0 else -1.5
        sthe = math.radians(saz)
        if sel >= 0:
            for ang in range(0, 360, 30):
                ax.plot([sthe, sthe], [s_r, max(0, s_r - 4)],
                        color=COL_WARN, linewidth=0.8, alpha=0.5)
            ax.plot([sthe], [s_r], "o", color=COL_WARN, markersize=18,
                    alpha=0.95)
            ax.plot([sthe], [s_r], "o", color="#ffe08a", markersize=11)
        else:
            # below the horizon: park a faint marker at the horizon rim in the
            # body's compass direction (not at the zenith centre, where it would
            # sit on top of the "90" ring label), with the label nudged outward
            ax.plot([sthe], [2.0], "o", color=COL_WARN, markersize=7,
                    alpha=0.4, clip_on=False)
            ax.annotate("Sun \u25bc", (sthe, 0), color=COL_MUTED, fontsize=7,
                        ha="center", va="bottom",
                        xytext=(0, 4), textcoords="offset points",
                        annotation_clip=False)

        # Moon: disc shaded by illumination
        mthe = math.radians(maz)
        m_r = mel if mel >= 0 else 90
        if mel >= 0:
            ax.plot([mthe], [m_r], "o", color="#cfe3ff", markersize=15,
                    alpha=0.9)
            # dark overlay sized by (1-illum) to suggest the phase
            shade = 1.0 - illum
            if shade > 0.05:
                ax.plot([mthe], [m_r], "o", color=COL_PANEL,
                        markersize=15 * shade, alpha=0.85)
        else:
            # below the horizon: faint marker at the horizon rim in the moon's
            # direction with the label nudged outward, so neither sits on the
            # "90" zenith ring label at the centre
            ax.plot([mthe], [2.0], "o", color="#cfe3ff", markersize=6,
                    alpha=0.4, clip_on=False)
            ax.annotate("Moon \u25bc", (mthe, 0), color=COL_MUTED, fontsize=7,
                        ha="center", va="bottom",
                        xytext=(0, 4), textcoords="offset points",
                        annotation_clip=False)
        self.mpl.draw()
