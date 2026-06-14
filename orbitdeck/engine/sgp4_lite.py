"""
sgp4_lite.py - a compact, dependency-free SGP4/SDP4 propagator.

This is a faithful pure-Python implementation of the Vallado/AIAA-2006-6753
"Revisiting Spacetrack Report #3" SGP4, restricted to the near-Earth (SGP4)
path plus the deep-space (SDP4) lunar-solar + resonance terms, using the WGS72
gravity model. CardSat (the device this is ported from) feeds its GP mean
elements to the Hopperpop Arduino library, which is itself a port of this same
Vallado code with WGS72 -- so propagating here with WGS72 reproduces the
device's results.

Only the pieces the tracker needs are kept:
  * twoline2rv-equivalent init from mean elements (we init directly from GP
    fields, no TLE string round-trip required)
  * sgp4(tsince_minutes) -> TEME position (km) and velocity (km/s)

The math follows Vallado's reference implementation closely; variable names are
kept close to the canonical source so it can be checked against it.
"""

import math

# ---- WGS72 constants (the set the GP/TLE mean elements are fit to) ----
_MU = 398600.8            # km^3/s^2
_RE = 6378.135            # km, equatorial radius
_XKE = 60.0 / math.sqrt(_RE * _RE * _RE / _MU)
_TUMIN = 1.0 / _XKE
_J2 = 0.001082616
_J3 = -0.00000253881
_J4 = -0.00000165597
_J3OJ2 = _J3 / _J2
_X2O3 = 2.0 / 3.0
_DEG2RAD = math.pi / 180.0
_TWOPI = 2.0 * math.pi


class Satrec:
    """Holds the initialized SGP4 element set and propagates it."""

    __slots__ = (
        "error", "method", "satnum",
        "no_kozai", "ecco", "inclo", "nodeo", "argpo", "mo", "bstar",
        "ndot", "nddot", "jdsatepoch",
        # derived / secular
        "a", "alta", "altp", "no_unkozai", "con41", "con42", "cosio", "cosio2",
        "eccsq", "omeosq", "posq", "rp", "rteosq", "sinio",
        "aycof", "con41_", "cc1", "cc4", "cc5", "d2", "d3", "d4",
        "delmo", "eta", "argpdot", "omgcof", "sinmao", "t2cof", "t3cof",
        "t4cof", "t5cof", "x1mth2", "x7thm1", "mdot", "nodedot", "xlcof",
        "xmcof", "nodecf", "isimp", "gsto",
        # deep space
        "isdeep", "d2201", "d2211", "d3210", "d3222", "d4410", "d4422",
        "d5220", "d5232", "d5421", "d5433", "dedt", "del1", "del2", "del3",
        "didt", "dmdt", "dnodt", "domdt", "e3", "ee2", "peo", "pgho", "pho",
        "pinco", "plo", "se2", "se3", "sgh2", "sgh3", "sgh4", "sh2", "sh3",
        "si2", "si3", "sl2", "sl3", "sl4", "xfact", "xgh2", "xgh3", "xgh4",
        "xh2", "xh3", "xi2", "xi3", "xl2", "xl3", "xl4", "xlamo", "zmol",
        "zmos", "atime", "xli", "xni", "irez", "dndt",
    )

    def __init__(self):
        self.error = 0
        self.isdeep = False

    # -- public init from GP mean elements --------------------------------
    def init_from_elements(self, jdsatepoch, bstar, ndot, nddot,
                           ecco, argpo_deg, inclo_deg, mo_deg,
                           no_kozai_revperday, nodeo_deg, satnum=0):
        """Initialize from GP/OMM mean elements.

        Angles in degrees, mean motion in rev/day (will be converted to
        rad/min, the internal unit). jdsatepoch is the full Julian date of
        the element-set epoch.
        """
        self.satnum = satnum
        self.jdsatepoch = jdsatepoch
        self.bstar = bstar
        self.ndot = ndot
        self.nddot = nddot
        self.ecco = ecco
        self.argpo = argpo_deg * _DEG2RAD
        self.inclo = inclo_deg * _DEG2RAD
        self.mo = mo_deg * _DEG2RAD
        self.no_kozai = no_kozai_revperday / 1440.0 * _TWOPI   # rad/min
        self.nodeo = nodeo_deg * _DEG2RAD
        self.error = 0
        self._sgp4init()
        return self.error == 0

    # -- core init (Vallado sgp4init) -------------------------------------
    def _sgp4init(self):
        self.isimp = 0
        self.method = "n"
        self.aycof = self.con41_ = self.cc1 = self.cc4 = self.cc5 = 0.0
        self.d2 = self.d3 = self.d4 = self.delmo = self.eta = 0.0
        self.argpdot = self.omgcof = self.sinmao = self.t2cof = 0.0
        self.t3cof = self.t4cof = self.t5cof = self.x1mth2 = self.x7thm1 = 0.0
        self.mdot = self.nodedot = self.xlcof = self.xmcof = self.nodecf = 0.0

        ss = 78.0 / _RE + 1.0
        qzms2t = ((120.0 - 78.0) / _RE) ** 4
        x2o3 = _X2O3

        eccsq = self.ecco * self.ecco
        omeosq = 1.0 - eccsq
        rteosq = math.sqrt(omeosq)
        cosio = math.cos(self.inclo)
        cosio2 = cosio * cosio

        # un-Kozai the mean motion
        ak = (_XKE / self.no_kozai) ** x2o3
        d1 = 0.75 * _J2 * (3.0 * cosio2 - 1.0) / (rteosq * omeosq)
        del_ = d1 / (ak * ak)
        adel = ak * (1.0 - del_ * del_ - del_ *
                     (1.0 / 3.0 + 134.0 * del_ * del_ / 81.0))
        del_ = d1 / (adel * adel)
        no = self.no_kozai / (1.0 + del_)

        ao = (_XKE / no) ** x2o3
        sinio = math.sin(self.inclo)
        po = ao * omeosq
        con42 = 1.0 - 5.0 * cosio2
        con41 = -con42 - cosio2 - cosio2
        ainv = 1.0 / ao
        posq = po * po
        rp = ao * (1.0 - self.ecco)

        self.no_unkozai = no
        self.con41 = con41
        self.cosio = cosio
        self.cosio2 = cosio2
        self.eccsq = eccsq
        self.omeosq = omeosq
        self.posq = posq
        self.rp = rp
        self.rteosq = rteosq
        self.sinio = sinio
        self.con42 = con42
        self.a = ao
        self.alta = ao * (1.0 + self.ecco) - 1.0
        self.altp = ao * (1.0 - self.ecco) - 1.0
        self.gsto = _gstime(self.jdsatepoch)

        if omeosq >= 0.0 or no >= 0.0:
            self.isimp = 0
            if rp < 220.0 / _RE + 1.0:
                self.isimp = 1
            sfour = ss
            qzms24 = qzms2t
            perige = (rp - 1.0) * _RE

            if perige < 156.0:
                sfour = perige - 78.0
                if perige < 98.0:
                    sfour = 20.0
                qzms24 = ((120.0 - sfour) / _RE) ** 4
                sfour = sfour / _RE + 1.0
            pinvsq = 1.0 / posq

            tsi = 1.0 / (ao - sfour)
            eta = ao * self.ecco * tsi
            etasq = eta * eta
            eeta = self.ecco * eta
            psisq = abs(1.0 - etasq)
            coef = qzms24 * tsi ** 4
            coef1 = coef / psisq ** 3.5
            cc2 = coef1 * no * (ao * (1.0 + 1.5 * etasq + eeta *
                  (4.0 + etasq)) + 0.375 * _J2 * tsi / psisq * con41 *
                  (8.0 + 3.0 * etasq * (8.0 + etasq)))
            self.cc1 = self.bstar * cc2
            cc3 = 0.0
            if self.ecco > 1.0e-4:
                cc3 = -2.0 * coef * tsi * _J3OJ2 * no * sinio / self.ecco
            self.x1mth2 = 1.0 - cosio2
            self.cc4 = 2.0 * no * coef1 * ao * omeosq * (
                eta * (2.0 + 0.5 * etasq) + self.ecco *
                (0.5 + 2.0 * etasq) - _J2 * tsi / (ao * psisq) *
                (-3.0 * con41 * (1.0 - 2.0 * eeta + etasq *
                 (1.5 - 0.5 * eeta)) + 0.75 * self.x1mth2 *
                 (2.0 * etasq - eeta * (1.0 + etasq)) *
                 math.cos(2.0 * self.argpo)))
            self.cc5 = 2.0 * coef1 * ao * omeosq * (1.0 + 2.75 *
                       (etasq + eeta) + eeta * etasq)
            cosio4 = cosio2 * cosio2
            temp1 = 1.5 * _J2 * pinvsq * no
            temp2 = 0.5 * temp1 * _J2 * pinvsq
            temp3 = -0.46875 * _J4 * pinvsq * pinvsq * no
            self.mdot = no + 0.5 * temp1 * rteosq * con41 + 0.0625 * \
                temp2 * rteosq * (13.0 - 78.0 * cosio2 + 137.0 * cosio4)
            self.argpdot = (-0.5 * temp1 * con42 + 0.0625 * temp2 *
                            (7.0 - 114.0 * cosio2 + 395.0 * cosio4) +
                            temp3 * (3.0 - 36.0 * cosio2 + 49.0 * cosio4))
            xhdot1 = -temp1 * cosio
            self.nodedot = xhdot1 + (0.5 * temp2 * (4.0 - 19.0 * cosio2) +
                           2.0 * temp3 * (3.0 - 7.0 * cosio2)) * cosio
            xpidot = self.argpdot + self.nodedot
            self.omgcof = self.bstar * cc3 * math.cos(self.argpo)
            self.xmcof = 0.0
            if self.ecco > 1.0e-4:
                self.xmcof = -x2o3 * coef * self.bstar / eeta
            self.nodecf = 3.5 * omeosq * xhdot1 * self.cc1
            self.t2cof = 1.5 * self.cc1
            if abs(cosio + 1.0) > 1.5e-12:
                self.xlcof = -0.25 * _J3OJ2 * sinio * \
                    (3.0 + 5.0 * cosio) / (1.0 + cosio)
            else:
                self.xlcof = -0.25 * _J3OJ2 * sinio * \
                    (3.0 + 5.0 * cosio) / 1.5e-12
            self.aycof = -0.5 * _J3OJ2 * sinio
            self.delmo = (1.0 + eta * math.cos(self.mo)) ** 3
            self.sinmao = math.sin(self.mo)
            self.x7thm1 = 7.0 * cosio2 - 1.0
            self.eta = eta

            # ---- deep space? period >= 225 min ----
            if (_TWOPI / no) >= 225.0:
                self.method = "d"
                self.isdeep = True
                self.isimp = 1
                self._deepspace_init(tc=0.0, ss=ss)
            else:
                self.isdeep = False

            if self.isimp != 1:
                cc1sq = self.cc1 * self.cc1
                self.d2 = 4.0 * ao * tsi * cc1sq
                temp = self.d2 * tsi * self.cc1 / 3.0
                self.d3 = (17.0 * ao + sfour) * temp
                self.d4 = 0.5 * temp * ao * tsi * \
                    (221.0 * ao + 31.0 * sfour) * self.cc1
                self.t3cof = self.d2 + 2.0 * cc1sq
                self.t4cof = 0.25 * (3.0 * self.d3 + self.cc1 *
                             (12.0 * self.d2 + 10.0 * cc1sq))
                self.t5cof = 0.2 * (3.0 * self.d4 + 12.0 * self.cc1 *
                             self.d3 + 6.0 * self.d2 * self.d2 + 15.0 *
                             cc1sq * (2.0 * self.d2 + cc1sq))

        # one propagation at t=0 to fill state / validate
        self.atime = 0.0
        self.xli = 0.0
        self.xni = 0.0
        self.sgp4(0.0)

    # -- propagation (Vallado sgp4) ---------------------------------------
    def sgp4(self, tsince):
        """Propagate to tsince minutes past epoch.

        Returns (r, v) with r in km and v in km/s in the TEME frame, or sets
        self.error and returns ([0,0,0],[0,0,0]).
        """
        x2o3 = _X2O3
        vkmpersec = _RE * _XKE / 60.0
        self.error = 0

        xmdf = self.mo + self.mdot * tsince
        argpdf = self.argpo + self.argpdot * tsince
        nodedf = self.nodeo + self.nodedot * tsince
        argpm = argpdf
        mm = xmdf
        t2 = tsince * tsince
        nodem = nodedf + self.nodecf * t2
        tempa = 1.0 - self.cc1 * tsince
        tempe = self.bstar * self.cc4 * tsince
        templ = self.t2cof * t2

        if self.isimp != 1:
            delomg = self.omgcof * tsince
            delmtemp = 1.0 + self.eta * math.cos(xmdf)
            delm = self.xmcof * (delmtemp ** 3 - self.delmo)
            temp = delomg + delm
            mm = xmdf + temp
            argpm = argpdf - temp
            t3 = t2 * tsince
            t4 = t3 * tsince
            tempa = tempa - self.d2 * t2 - self.d3 * t3 - self.d4 * t4
            tempe = tempe + self.bstar * self.cc5 * \
                (math.sin(mm) - self.sinmao)
            templ = templ + self.t3cof * t3 + t4 * \
                (self.t4cof + tsince * self.t5cof)

        nm = self.no_unkozai
        em = self.ecco
        inclm = self.inclo

        if self.isdeep:
            tc = tsince
            nm, em, inclm, nodem, argpm, mm = self._dspace(
                tsince, tc, nm, em, inclm, nodem, argpm, mm)

        if nm <= 0.0:
            self.error = 2
            return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        am = (_XKE / nm) ** x2o3 * tempa * tempa
        nm = _XKE / am ** 1.5
        em = em - tempe

        if em >= 1.0 or em < -0.001:
            self.error = 1
            return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        if em < 1.0e-6:
            em = 1.0e-6
        mm = mm + self.no_unkozai * templ
        xlm = mm + argpm + nodem
        nodem = nodem % _TWOPI
        argpm = argpm % _TWOPI
        xlm = xlm % _TWOPI
        mm = (xlm - argpm - nodem) % _TWOPI

        sinim = math.sin(inclm)
        cosim = math.cos(inclm)

        ep = em
        xincp = inclm
        argpp = argpm
        nodep = nodem
        mp = mm
        sinip = sinim
        cosip = cosim

        if self.isdeep:
            ep, xincp, nodep, argpp, mp = self._dpper(
                tsince, ep, xincp, nodep, argpp, mp)
            if xincp < 0.0:
                xincp = -xincp
                nodep = nodep + math.pi
                argpp = argpp - math.pi
            if ep < 0.0 or ep > 1.0:
                self.error = 3
                return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
            sinip = math.sin(xincp)
            cosip = math.cos(xincp)
            self.aycof = -0.5 * _J3OJ2 * sinip
            if abs(cosip + 1.0) > 1.5e-12:
                self.xlcof = -0.25 * _J3OJ2 * sinip * \
                    (3.0 + 5.0 * cosip) / (1.0 + cosip)
            else:
                self.xlcof = -0.25 * _J3OJ2 * sinip * \
                    (3.0 + 5.0 * cosip) / 1.5e-12

        axnl = ep * math.cos(argpp)
        temp = 1.0 / (am * (1.0 - ep * ep))
        aynl = ep * math.sin(argpp) + temp * self.aycof
        xl = mp + argpp + nodep + temp * self.xlcof * axnl

        # solve Kepler's equation
        u = (xl - nodep) % _TWOPI
        eo1 = u
        for _ in range(10):
            sineo1 = math.sin(eo1)
            coseo1 = math.cos(eo1)
            tem5 = 1.0 - coseo1 * axnl - sineo1 * aynl
            tem5 = (u - aynl * coseo1 + axnl * sineo1 - eo1) / tem5
            if abs(tem5) >= 0.95:
                tem5 = 0.95 if tem5 > 0.0 else -0.95
            eo1 = eo1 + tem5
            if abs(tem5) < 1.0e-12:
                break

        ecose = axnl * coseo1 + aynl * sineo1
        esine = axnl * sineo1 - aynl * coseo1
        el2 = axnl * axnl + aynl * aynl
        pl = am * (1.0 - el2)
        if pl < 0.0:
            self.error = 4
            return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]

        rl = am * (1.0 - ecose)
        rdotl = math.sqrt(am) * esine / rl
        rvdotl = math.sqrt(pl) / rl
        betal = math.sqrt(1.0 - el2)
        temp = esine / (1.0 + betal)
        sinu = am / rl * (sineo1 - aynl - axnl * temp)
        cosu = am / rl * (coseo1 - axnl + aynl * temp)
        su = math.atan2(sinu, cosu)
        sin2u = (cosu + cosu) * sinu
        cos2u = 1.0 - 2.0 * sinu * sinu
        temp = 1.0 / pl
        temp1 = 0.5 * _J2 * temp
        temp2 = temp1 * temp

        # short-period periodics
        cosisq = cosip * cosip
        con41 = 3.0 * cosisq - 1.0
        x1mth2 = 1.0 - cosisq
        x7thm1 = 7.0 * cosisq - 1.0
        mrt = rl * (1.0 - 1.5 * temp2 * betal * con41) + \
            0.5 * temp1 * x1mth2 * cos2u
        su = su - 0.25 * temp2 * x7thm1 * sin2u
        xnode = nodep + 1.5 * temp2 * cosip * sin2u
        xinc = xincp + 1.5 * temp2 * cosip * sinip * cos2u
        mvt = rdotl - nm * temp1 * x1mth2 * sin2u / _XKE
        rvdot = rvdotl + nm * temp1 * (x1mth2 * cos2u + 1.5 * con41) / _XKE

        # orientation vectors
        sinsu = math.sin(su)
        cossu = math.cos(su)
        snod = math.sin(xnode)
        cnod = math.cos(xnode)
        sini = math.sin(xinc)
        cosi = math.cos(xinc)
        xmx = -snod * cosi
        xmy = cnod * cosi
        ux = xmx * sinsu + cnod * cossu
        uy = xmy * sinsu + snod * cossu
        uz = sini * sinsu
        vx = xmx * cossu - cnod * sinsu
        vy = xmy * cossu - snod * sinsu
        vz = sini * cossu

        r = [mrt * ux * _RE, mrt * uy * _RE, mrt * uz * _RE]
        v = [(mvt * ux + rvdot * vx) * vkmpersec,
             (mvt * uy + rvdot * vy) * vkmpersec,
             (mvt * uz + rvdot * vz) * vkmpersec]

        if mrt < 1.0:
            self.error = 6
        return r, v

    # ===================================================================
    #  Deep-space (SDP4) support: dscom / dsinit / dspace / dpper
    # ===================================================================
    def _deepspace_init(self, tc, ss):
        # ---- dscom ----
        zes = 0.01675
        zel = 0.05490
        c1ss = 2.9864797e-6
        c1l = 4.7968065e-7
        zsinis = 0.39785416
        zcosis = 0.91744867
        zcosgs = 0.1945905
        zsings = -0.98088458

        nm = self.no_unkozai
        em = self.ecco
        snodm = math.sin(self.nodeo)
        cnodm = math.cos(self.nodeo)
        sinomm = math.sin(self.argpo)
        cosomm = math.cos(self.argpo)
        sinim = math.sin(self.inclo)
        cosim = math.cos(self.inclo)
        emsq = em * em
        betasq = 1.0 - emsq
        rtemsq = math.sqrt(betasq)

        self.peo = 0.0
        self.pinco = 0.0
        self.plo = 0.0
        self.pgho = 0.0
        self.pho = 0.0

        day = self.jdsatepoch - 2433281.5 + tc / 1440.0
        xnodce = (4.5236020 - 9.2422029e-4 * day) % _TWOPI
        stem = math.sin(xnodce)
        ctem = math.cos(xnodce)
        zcosil = 0.91375164 - 0.03568096 * ctem
        zsinil = math.sqrt(1.0 - zcosil * zcosil)
        zsinhl = 0.089683511 * stem / zsinil
        zcoshl = math.sqrt(1.0 - zsinhl * zsinhl)
        gam = 5.8351514 + 0.0019443680 * day
        zx = 0.39785416 * stem / zsinil
        zy = zcoshl * ctem + 0.91744867 * zsinhl * stem
        zx = math.atan2(zx, zy)
        zx = gam + zx - xnodce
        zcosgl = math.cos(zx)
        zsingl = math.sin(zx)

        # solar terms then lunar terms
        zcosg = zcosgs
        zsing = zsings
        zcosi = zcosis
        zsini = zsinis
        zcosh = cnodm
        zsinh = snodm
        cc = c1ss
        xnoi = 1.0 / nm

        self.se2 = self.se3 = self.si2 = self.si3 = 0.0
        self.sl2 = self.sl3 = self.sl4 = 0.0
        self.sgh2 = self.sgh3 = self.sgh4 = 0.0
        self.sh2 = self.sh3 = 0.0
        sse = ssi = ssl = ssh = ssg = 0.0

        for lsflg in (1, 2):
            a1 = zcosg * zcosh + zsing * zcosi * zsinh
            a3 = -zsing * zcosh + zcosg * zcosi * zsinh
            a7 = -zcosg * zsinh + zsing * zcosi * zcosh
            a8 = zsing * zsini
            a9 = zsing * zsinh + zcosg * zcosi * zcosh
            a10 = zcosg * zsini
            a2 = cosim * a7 + sinim * a8
            a4 = cosim * a9 + sinim * a10
            a5 = -sinim * a7 + cosim * a8
            a6 = -sinim * a9 + cosim * a10
            x1 = a1 * cosomm + a2 * sinomm
            x2 = a3 * cosomm + a4 * sinomm
            x3 = -a1 * sinomm + a2 * cosomm
            x4 = -a3 * sinomm + a4 * cosomm
            x5 = a5 * sinomm
            x6 = a6 * sinomm
            x7 = a5 * cosomm
            x8 = a6 * cosomm
            z31 = 12.0 * x1 * x1 - 3.0 * x3 * x3
            z32 = 24.0 * x1 * x2 - 6.0 * x3 * x4
            z33 = 12.0 * x2 * x2 - 3.0 * x4 * x4
            z1 = 3.0 * (a1 * a1 + a2 * a2) + z31 * emsq
            z2 = 6.0 * (a1 * a3 + a2 * a4) + z32 * emsq
            z3 = 3.0 * (a3 * a3 + a4 * a4) + z33 * emsq
            z11 = -6.0 * a1 * a5 + emsq * (-24.0 * x1 * x7 - 6.0 * x3 * x5)
            z12 = -6.0 * (a1 * a6 + a3 * a5) + emsq * \
                (-24.0 * (x2 * x7 + x1 * x8) - 6.0 * (x3 * x6 + x4 * x5))
            z13 = -6.0 * a3 * a6 + emsq * (-24.0 * x2 * x8 - 6.0 * x4 * x6)
            z21 = 6.0 * a2 * a5 + emsq * (24.0 * x1 * x5 - 6.0 * x3 * x7)
            z22 = 6.0 * (a4 * a5 + a2 * a6) + emsq * \
                (24.0 * (x2 * x5 + x1 * x6) - 6.0 * (x4 * x7 + x3 * x8))
            z23 = 6.0 * a4 * a6 + emsq * (24.0 * x2 * x6 - 6.0 * x4 * x8)
            z1 = z1 + z1 + betasq * z31
            z2 = z2 + z2 + betasq * z32
            z3 = z3 + z3 + betasq * z33
            s3 = cc * xnoi
            s2 = -0.5 * s3 / rtemsq
            s4 = s3 * rtemsq
            s1 = -15.0 * em * s4
            s5 = x1 * x3 + x2 * x4
            s6 = x2 * x3 + x1 * x4
            s7 = x2 * x4 - x1 * x3

            sse_v = s1 * (z11 + z13)
            ssi_v = s2 * (z11 + z13)
            ssl_v = -s3 * (z1 + z3 - 14.0 - 6.0 * emsq)
            ssg_v = s4 * (z31 + z33 - 6.0)
            ssh_v = 0.0
            if self.inclo < 0.052359877 or self.inclo > math.pi - 0.052359877:
                ssh_v = 0.0
            else:
                ssh_v = -s2 * (z21 + z23)
            sse += sse_v
            ssi += ssi_v
            ssl += ssl_v
            ssg += ssg_v
            ssh += ssh_v

            if lsflg == 1:
                self.ee2 = 2.0 * s1 * s6
                self.e3 = 2.0 * s1 * s7
                self.xi2 = 2.0 * s2 * z12
                self.xi3 = 2.0 * s2 * (z13 - z11)
                self.xl2 = -2.0 * s3 * z2
                self.xl3 = -2.0 * s3 * (z3 - z1)
                self.xl4 = -2.0 * s3 * (-21.0 - 9.0 * emsq) * zes
                self.xgh2 = 2.0 * s4 * z32
                self.xgh3 = 2.0 * s4 * (z33 - z31)
                self.xgh4 = -18.0 * s4 * zes
                self.xh2 = -2.0 * s2 * z22
                self.xh3 = -2.0 * s2 * (z23 - z21)
                # switch to lunar
                zcosg = zcosgl
                zsing = zsingl
                zcosi = zcosil
                zsini = zsinil
                zcosh = zcoshl * cnodm + zsinhl * snodm
                zsinh = snodm * zcoshl - cnodm * zsinhl
                cc = c1l

        self.zmol = (4.7199672 + 0.22997150 * day - gam) % _TWOPI
        self.zmos = (6.2565837 + 0.017201977 * day) % _TWOPI

        self.se2 = self.ee2
        self.se3 = self.e3
        self.si2 = self.xi2
        self.si3 = self.xi3
        self.sl2 = self.xl2
        self.sl3 = self.xl3
        self.sl4 = self.xl4
        self.sgh2 = self.xgh2
        self.sgh3 = self.xgh3
        self.sgh4 = self.xgh4
        self.sh2 = self.xh2
        self.sh3 = self.xh3

        # ---- dsinit (resonance + secular rates) ----
        self._dsinit(tc, ss, sse, ssi, ssl, ssg, ssh, nm, em, emsq,
                     rtemsq, cosim, sinim, betasq, snodm, cnodm,
                     sinomm, cosomm, day)

    def _dsinit(self, tc, ss, sse, ssi, ssl, ssg, ssh, nm, em, emsq,
                rtemsq, cosim, sinim, betasq, snodm, cnodm,
                sinomm, cosomm, day):
        q22 = 1.7891679e-6
        q31 = 2.1460748e-6
        q33 = 2.2123015e-7
        root22 = 1.7891679e-6
        root44 = 7.3636953e-9
        root54 = 2.1765803e-9
        rptim = 4.37526908801129966e-3
        root32 = 3.7393792e-7
        root52 = 1.1428639e-7
        x2o3 = _X2O3
        znl = 1.5835218e-4
        zns = 1.19459e-5

        self.irez = 0
        if 0.0034906585 < nm < 0.0052359877:
            self.irez = 1
        if 8.26e-3 <= nm <= 9.24e-3 and em >= 0.5:
            self.irez = 2

        # solar/lunar secular
        self.dedt = sse + 0.0
        self.didt = ssi + 0.0
        self.dmdt = ssl + 0.0
        self.dnodt = ssh + 0.0
        self.domdt = ssg + 0.0
        # Vallado folds the periodic-term derivatives; kept consistent with em
        emsqr = emsq
        self.atime = 0.0
        self.xni = self.no_unkozai
        self.xli = 0.0
        self.dndt = 0.0

        argpm = self.argpo
        nodem = self.nodeo
        mm = self.mo

        self.d2201 = self.d2211 = self.d3210 = self.d3222 = 0.0
        self.d4410 = self.d4422 = self.d5220 = self.d5232 = 0.0
        self.d5421 = self.d5433 = self.del1 = self.del2 = self.del3 = 0.0
        self.xfact = 0.0
        self.xlamo = 0.0

        if self.irez != 0:
            aonv = (nm / _XKE) ** x2o3
            if self.irez == 2:
                cosisq = cosim * cosim
                emo = em
                emsqo = emsq
                eoc = em * emsq
                g201 = -0.306 - (em - 0.64) * 0.440
                if em <= 0.65:
                    g211 = 3.616 - 13.2470 * em + 16.2900 * emsq
                    g310 = -19.302 + 117.3900 * em - 228.4190 * emsq + \
                        156.5910 * eoc
                    g322 = -18.9068 + 109.7927 * em - 214.6334 * emsq + \
                        146.5816 * eoc
                    g410 = -41.122 + 242.6940 * em - 471.0940 * emsq + \
                        313.9530 * eoc
                    g422 = -146.407 + 841.8800 * em - 1629.014 * emsq + \
                        1083.435 * eoc
                    g520 = -532.114 + 3017.977 * em - 5740.032 * emsq + \
                        3708.276 * eoc
                else:
                    g211 = -72.099 + 331.819 * em - 508.738 * emsq + \
                        266.724 * eoc
                    g310 = -346.844 + 1582.851 * em - 2415.925 * emsq + \
                        1246.113 * eoc
                    g322 = -342.585 + 1554.908 * em - 2366.899 * emsq + \
                        1215.972 * eoc
                    g410 = -1052.797 + 4758.686 * em - 7193.992 * emsq + \
                        3651.957 * eoc
                    g422 = -3581.690 + 16178.110 * em - 24462.770 * emsq + \
                        12422.520 * eoc
                    if em > 0.715:
                        g520 = -5149.66 + 29936.92 * em - 54087.36 * emsq + \
                            31324.56 * eoc
                    else:
                        g520 = 1464.74 - 4664.75 * em + 3763.64 * emsq
                if em < 0.7:
                    g533 = -919.22770 + 4988.6100 * em - 9064.7700 * emsq + \
                        5542.21 * eoc
                    g521 = -822.71072 + 4568.6173 * em - 8491.4146 * emsq + \
                        5337.524 * eoc
                    g532 = -853.66600 + 4690.2500 * em - 8624.7700 * emsq + \
                        5341.4 * eoc
                else:
                    g533 = -37995.780 + 161616.52 * em - 229838.20 * emsq + \
                        109377.94 * eoc
                    g521 = -51752.104 + 218913.95 * em - 309468.16 * emsq + \
                        146349.42 * eoc
                    g532 = -40023.880 + 170347.26 * em - 242699.48 * emsq + \
                        115605.82 * eoc
                sini2 = sinim * sinim
                f220 = 0.75 * (1.0 + 2.0 * cosim + cosisq)
                f221 = 1.5 * sini2
                f321 = 1.875 * sinim * (1.0 - 2.0 * cosim - 3.0 * cosisq)
                f322 = -1.875 * sinim * (1.0 + 2.0 * cosim - 3.0 * cosisq)
                f441 = 35.0 * sini2 * f220
                f442 = 39.3750 * sini2 * sini2
                f522 = 9.84375 * sinim * (sini2 * (1.0 - 2.0 * cosim -
                       5.0 * cosisq) + 0.33333333 * (-2.0 + 4.0 * cosim +
                       6.0 * cosisq))
                f523 = sinim * (4.92187512 * sini2 * (-2.0 - 4.0 * cosim +
                       10.0 * cosisq) + 6.56250012 * (1.0 + 2.0 * cosim -
                       3.0 * cosisq))
                f542 = 29.53125 * sinim * (2.0 - 8.0 * cosim + cosisq *
                       (-12.0 + 8.0 * cosim + 10.0 * cosisq))
                f543 = 29.53125 * sinim * (-2.0 - 8.0 * cosim + cosisq *
                       (12.0 + 8.0 * cosim - 10.0 * cosisq))
                xno2 = nm * nm
                ainv2 = aonv * aonv
                temp1 = 3.0 * xno2 * ainv2
                temp = temp1 * root22
                self.d2201 = temp * f220 * g201
                self.d2211 = temp * f221 * g211
                temp1 = temp1 * aonv
                temp = temp1 * root32
                self.d3210 = temp * f321 * g310
                self.d3222 = temp * f322 * g322
                temp1 = temp1 * aonv
                temp = 2.0 * temp1 * root44
                self.d4410 = temp * f441 * g410
                self.d4422 = temp * f442 * g422
                temp1 = temp1 * aonv
                temp = temp1 * root52
                self.d5220 = temp * f522 * g520
                self.d5232 = temp * f523 * g532
                temp = 2.0 * temp1 * root54
                self.d5421 = temp * f542 * g521
                self.d5433 = temp * f543 * g533
                self.xlamo = (self.mo + self.nodeo + self.nodeo -
                              self.gsto - self.gsto) % _TWOPI
                self.xfact = self.mdot + self.dmdt + 2.0 * \
                    (self.nodedot + self.dnodt - rptim) - self.no_unkozai
                em = emo
                emsq = emsqo
            if self.irez == 1:
                g200 = 1.0 + emsq * (-2.5 + 0.8125 * emsq)
                g310 = 1.0 + 2.0 * emsq
                g300 = 1.0 + emsq * (-6.0 + 6.60937 * emsq)
                f220 = 0.75 * (1.0 + cosim) * (1.0 + cosim)
                f311 = 0.9375 * sinim * sinim * (1.0 + 3.0 * cosim) - \
                    0.75 * (1.0 + cosim)
                f330 = 1.0 + cosim
                f330 = 1.875 * f330 * f330 * f330
                self.del1 = 3.0 * nm * nm * aonv * aonv
                self.del2 = 2.0 * self.del1 * f220 * g200 * q22
                self.del3 = 3.0 * self.del1 * f330 * g300 * q33 * aonv
                self.del1 = self.del1 * f311 * g310 * q31 * aonv
                self.xlamo = (self.mo + self.nodeo + self.argpo -
                              self.gsto) % _TWOPI
                self.xfact = self.mdot + (self.argpdot + self.nodedot) - \
                    rptim + self.dmdt + self.domdt + self.dnodt - \
                    self.no_unkozai
            self.xli = self.xlamo
            self.xni = self.no_unkozai
            self.atime = 0.0

    def _dspace(self, t, tc, nm, em, inclm, nodem, argpm, mm):
        fasx2 = 0.13130908
        fasx4 = 2.8843198
        fasx6 = 0.37448087
        g22 = 5.7686396
        g32 = 0.95240898
        g44 = 1.8014998
        g52 = 1.0508330
        g54 = 4.4108898
        rptim = 4.37526908801129966e-3
        stepp = 720.0
        stepn = -720.0
        step2 = 259200.0

        self.dndt = 0.0
        theta = (self.gsto + tc * rptim) % _TWOPI

        em = em + self.dedt * t
        inclm = inclm + self.didt * t
        argpm = argpm + self.domdt * t
        nodem = nodem + self.dnodt * t
        mm = mm + self.dmdt * t

        if self.irez != 0:
            if self.atime == 0.0 or t * self.atime <= 0.0 or \
               abs(t) < abs(self.atime):
                self.atime = 0.0
                self.xni = self.no_unkozai
                self.xli = self.xlamo
            delt = stepp if t > 0.0 else stepn

            iretn = 381
            while iretn == 381:
                if self.irez != 2:
                    xndt = self.del1 * math.sin(self.xli - fasx2) + \
                        self.del2 * math.sin(2.0 * (self.xli - fasx4)) + \
                        self.del3 * math.sin(3.0 * (self.xli - fasx6))
                    xldot = self.xni + self.xfact
                    xnddt = self.del1 * math.cos(self.xli - fasx2) + \
                        2.0 * self.del2 * math.cos(2.0 * (self.xli - fasx4)) + \
                        3.0 * self.del3 * math.cos(3.0 * (self.xli - fasx6))
                    xnddt = xnddt * xldot
                else:
                    xomi = self.argpo + self.argpdot * self.atime
                    x2omi = xomi + xomi
                    x2li = self.xli + self.xli
                    xndt = (self.d2201 * math.sin(x2omi + self.xli - g22) +
                            self.d2211 * math.sin(self.xli - g22) +
                            self.d3210 * math.sin(xomi + self.xli - g32) +
                            self.d3222 * math.sin(-xomi + self.xli - g32) +
                            self.d4410 * math.sin(x2omi + x2li - g44) +
                            self.d4422 * math.sin(x2li - g44) +
                            self.d5220 * math.sin(xomi + self.xli - g52) +
                            self.d5232 * math.sin(-xomi + self.xli - g52) +
                            self.d5421 * math.sin(xomi + x2li - g54) +
                            self.d5433 * math.sin(-xomi + x2li - g54))
                    xldot = self.xni + self.xfact
                    xnddt = (self.d2201 * math.cos(x2omi + self.xli - g22) +
                             self.d2211 * math.cos(self.xli - g22) +
                             self.d3210 * math.cos(xomi + self.xli - g32) +
                             self.d3222 * math.cos(-xomi + self.xli - g32) +
                             self.d5220 * math.cos(xomi + self.xli - g52) +
                             self.d5232 * math.cos(-xomi + self.xli - g52) +
                             2.0 * (self.d4410 * math.cos(x2omi + x2li - g44) +
                                    self.d4422 * math.cos(x2li - g44) +
                                    self.d5421 * math.cos(xomi + x2li - g54) +
                                    self.d5433 * math.cos(-xomi + x2li - g54)))
                    xnddt = xnddt * xldot

                if abs(t - self.atime) >= stepp:
                    iretn = 381
                else:
                    ft = t - self.atime
                    iretn = 0

                if iretn == 381:
                    self.xli = self.xli + xldot * delt + xndt * step2
                    self.xni = self.xni + xndt * delt + xnddt * step2
                    self.atime = self.atime + delt

            nm = self.xni + xndt * ft + xnddt * ft * ft * 0.5
            xl = self.xli + xldot * ft + xndt * ft * ft * 0.5
            if self.irez != 1:
                mm = xl - 2.0 * nodem + 2.0 * theta
                self.dndt = nm - self.no_unkozai
            else:
                mm = xl - nodem - argpm + theta
                self.dndt = nm - self.no_unkozai
            nm = self.no_unkozai + self.dndt
        return nm, em, inclm, nodem, argpm, mm

    def _dpper(self, t, ep, inclp, nodep, argpp, mp):
        zns = 1.19459e-5
        zes = 0.01675
        znl = 1.5835218e-4
        zel = 0.05490

        zm = self.zmos + zns * t
        zf = zm + 2.0 * zes * math.sin(zm)
        sinzf = math.sin(zf)
        f2 = 0.5 * sinzf * sinzf - 0.25
        f3 = -0.5 * sinzf * math.cos(zf)
        ses = self.se2 * f2 + self.se3 * f3
        sis = self.si2 * f2 + self.si3 * f3
        sls = self.sl2 * f2 + self.sl3 * f3 + self.sl4 * sinzf
        sghs = self.sgh2 * f2 + self.sgh3 * f3 + self.sgh4 * sinzf
        shs = self.sh2 * f2 + self.sh3 * f3

        zm = self.zmol + znl * t
        zf = zm + 2.0 * zel * math.sin(zm)
        sinzf = math.sin(zf)
        f2 = 0.5 * sinzf * sinzf - 0.25
        f3 = -0.5 * sinzf * math.cos(zf)
        sel = self.ee2 * f2 + self.e3 * f3
        sil = self.xi2 * f2 + self.xi3 * f3
        sll = self.xl2 * f2 + self.xl3 * f3 + self.xl4 * sinzf
        sghl = self.xgh2 * f2 + self.xgh3 * f3 + self.xgh4 * sinzf
        shll = self.xh2 * f2 + self.xh3 * f3

        pe = ses + sel
        pinc = sis + sil
        pl = sls + sll
        pgh = sghs + sghl
        ph = shs + shll

        pe = pe - self.peo
        pinc = pinc - self.pinco
        pl = pl - self.plo
        pgh = pgh - self.pgho
        ph = ph - self.pho

        inclp = inclp + pinc
        ep = ep + pe
        sinip = math.sin(inclp)
        cosip = math.cos(inclp)

        if inclp >= 0.2:
            ph = ph / sinip
            pgh = pgh - cosip * ph
            argpp = argpp + pgh
            nodep = nodep + ph
            mp = mp + pl
        else:
            sinop = math.sin(nodep)
            cosop = math.cos(nodep)
            alfdp = sinip * sinop
            betdp = sinip * cosop
            dalf = ph * cosop + pinc * cosip * sinop
            dbet = -ph * sinop + pinc * cosip * cosop
            alfdp = alfdp + dalf
            betdp = betdp + dbet
            nodep = nodep % _TWOPI
            if nodep < 0.0:
                nodep += _TWOPI
            xls = mp + argpp + cosip * nodep
            dls = pl + pgh - pinc * nodep * sinip
            xls = xls + dls
            xnoh = nodep
            nodep = math.atan2(alfdp, betdp)
            if nodep < 0.0:
                nodep += _TWOPI
            if abs(xnoh - nodep) > math.pi:
                if nodep < xnoh:
                    nodep += _TWOPI
                else:
                    nodep -= _TWOPI
            mp = mp + pl
            argpp = xls - mp - cosip * nodep
        return ep, inclp, nodep, argpp, mp


def _gstime(jdut1):
    tut1 = (jdut1 - 2451545.0) / 36525.0
    temp = (-6.2e-6 * tut1 * tut1 * tut1 + 0.093104 * tut1 * tut1 +
            (876600.0 * 3600.0 + 8640184.812866) * tut1 + 67310.54841)
    temp = (temp * _DEG2RAD / 240.0) % _TWOPI
    if temp < 0.0:
        temp += _TWOPI
    return temp
