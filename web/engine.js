// engine.js — faithful JS port of the OrbitDeck orbital math the OSCARLOCATOR
// PDF generator depends on. Mirrors orbitdeck/engine/analysis.py and the
// orbital-element handling in orbitdeck/engine/satdb.py so the web generator
// produces numerically identical sheets.

(function (global) {
  "use strict";

  const DEG = Math.PI / 180.0;
  const TWO_PI = 2.0 * Math.PI;
  const MU = 398600.8;            // km^3/s^2 (WGS72, matches predict.py)
  const RE_KM = 6378.135;
  const J2 = 0.00108262998905;
  const DPD = 57.29577951308232 * 86400.0;   // rad/s -> deg/day
  const SIDEREAL_DAY_S = 86164.0905;

  function semi_major_axis_km(mean_motion_revday) {
    if (mean_motion_revday <= 0) return 0.0;
    const n = mean_motion_revday * TWO_PI / 86400.0;   // rad/s
    return Math.pow(MU / (n * n), 1.0 / 3.0);
  }

  function period_min(mean_motion_revday) {
    return mean_motion_revday ? 1440.0 / mean_motion_revday : 0.0;
  }

  function footprint_radius_deg(alt_km) {
    const r = RE_KM + alt_km;
    if (r <= RE_KM) return 0.0;
    return Math.acos(RE_KM / r) / DEG;
  }

  function central_angle_for_elevation_deg(el_deg, alt_km) {
    const r = RE_KM + alt_km;
    if (r <= RE_KM) return null;
    const e = el_deg * DEG;
    const s = (RE_KM / r) * Math.cos(e);
    if (s < -1.0 || s > 1.0) return null;
    const eta = Math.asin(s);
    const gamma = Math.PI / 2.0 - e - eta;
    if (gamma < 0) return null;
    return gamma / DEG;
  }

  function j2_rates(mean_motion_revday, incl_deg, ecc) {
    const n = mean_motion_revday * TWO_PI / 86400.0;   // rad/s
    const a = semi_major_axis_km(mean_motion_revday);
    const ci = Math.cos(incl_deg * DEG);
    const p = a * (1.0 - ecc * ecc);
    if (p <= 0) return [0.0, 0.0];
    const re_p2 = Math.pow(RE_KM / p, 2);
    const node = -1.5 * n * J2 * re_p2 * ci * DPD;
    const perigee = 0.75 * n * J2 * re_p2 * (5 * ci * ci - 1.0) * DPD;
    return [node, perigee];
  }

  // ---- great-circle helpers (mirror oscarlocator.py) ----
  function central_angle_bearing(qlat, qlon, lat, lon) {
    const p1 = qlat * DEG, l1 = qlon * DEG;
    const p2 = lat * DEG, l2 = lon * DEG;
    const dl = l2 - l1;
    const ca = Math.acos(Math.max(-1.0, Math.min(1.0,
      Math.sin(p1) * Math.sin(p2) +
      Math.cos(p1) * Math.cos(p2) * Math.cos(dl))));
    const y = Math.sin(dl) * Math.cos(p2);
    const x = Math.cos(p1) * Math.sin(p2) -
              Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
    let br = (Math.atan2(y, x) / DEG + 360.0) % 360.0;
    return [ca / DEG, br];
  }

  function dest_point(lat, lon, dist_deg, bearing_deg) {
    const p1 = lat * DEG, l1 = lon * DEG;
    const d = dist_deg * DEG, brg = bearing_deg * DEG;
    const lat2 = Math.asin(Math.sin(p1) * Math.cos(d) +
                           Math.cos(p1) * Math.sin(d) * Math.cos(brg));
    const lon2 = l1 + Math.atan2(Math.sin(brg) * Math.sin(d) * Math.cos(p1),
                                 Math.cos(d) - Math.sin(p1) * Math.sin(lat2));
    return [lat2 / DEG, ((lon2 / DEG) + 540.0) % 360.0 - 180.0];
  }

  function footprint_locus(qlat, qlon, foot_deg, n) {
    n = n || 361;
    const p1 = qlat * DEG, l1 = qlon * DEG, d = foot_deg * DEG;
    const pts = [];
    for (let i = 0; i < n; i++) {
      const brg = (360.0 * i / (n - 1)) * DEG;
      const lat2 = Math.asin(Math.sin(p1) * Math.cos(d) +
                             Math.cos(p1) * Math.sin(d) * Math.cos(brg));
      const lon2 = l1 + Math.atan2(Math.sin(brg) * Math.sin(d) * Math.cos(p1),
                                   Math.cos(d) - Math.sin(p1) * Math.sin(lat2));
      pts.push([lat2 / DEG, ((lon2 / DEG) + 540.0) % 360.0 - 180.0]);
    }
    return pts;
  }

  // ---- node shift per orbit (mirror _node_shift_deg) ----
  function node_shift_deg(sat) {
    const period_s = sat.period_min ? sat.period_min * 60.0 : 5400.0;
    const earth_turn = -360.0 * period_s / SIDEREAL_DAY_S;
    let node_per_orbit = 0.0;
    try {
      const [node_dpd] = j2_rates(sat.mean_motion, sat.incl, sat.ecc);
      node_per_orbit = node_dpd * period_s / 86400.0;
    } catch (e) { node_per_orbit = 0.0; }
    return earth_turn + node_per_orbit;
  }

  // ---- Kepler's equation (mirror _kepler_E) ----
  function kepler_E(M, e, iters) {
    iters = iters || 8;
    M = ((M + Math.PI) % TWO_PI + TWO_PI) % TWO_PI - Math.PI;
    let E = e < 0.8 ? M : Math.PI;
    for (let i = 0; i < iters; i++) {
      E = E - (E - e * Math.sin(E) - M) / (1.0 - e * Math.cos(E));
    }
    return E;
  }

  // ---- canonical ground track (mirror _canonical_track) ----
  function canonical_track(sat, descending) {
    const incl = sat.incl * DEG;
    const ecc = Math.max(0.0, Math.min(sat.ecc || 0.0, 0.95));
    const argp = (sat.argp || 0.0) * DEG;
    const period_minv = sat.period_min ? sat.period_min : 95.0;
    const period_s = period_minv * 60.0;

    const u_node = descending ? Math.PI : 0.0;
    const nu_node = u_node - argp;
    const E_node = Math.atan2(Math.sqrt(1 - ecc * ecc) * Math.sin(nu_node),
                              ecc + Math.cos(nu_node));
    const M_node = E_node - ecc * Math.sin(E_node);

    const lon_node = Math.atan2(Math.cos(incl) * Math.sin(u_node),
                                Math.cos(u_node)) / DEG;

    const n = 361;
    const pts = [];
    for (let i = 0; i < n; i++) {
      const frac = i / (n - 1);
      const dt = frac * period_s;
      const M = M_node + 2.0 * Math.PI * dt / period_s;
      const E = kepler_E(M, ecc);
      const nu = Math.atan2(Math.sqrt(1 - ecc * ecc) * Math.sin(E),
                            Math.cos(E) - ecc);
      const u = argp + nu;
      const lat = Math.asin(Math.sin(incl) * Math.sin(u)) / DEG;
      const lon = Math.atan2(Math.cos(incl) * Math.sin(u),
                             Math.cos(u)) / DEG;
      const earth = -360.0 * dt / SIDEREAL_DAY_S;
      pts.push([lon - lon_node + earth, lat, frac * period_minv]);
    }
    return pts;
  }

  // ---- km ring step (mirror _km_ring_step) ----
  function km_ring_step(reach_km) {
    if (reach_km <= 1500) return 500;
    if (reach_km <= 3500) return 1000;
    if (reach_km <= 7000) return 2000;
    return 3000;
  }

  // ---- OMM parsing (mirror _parse_omm + _f) ----
  function _f(o, keys, dflt) {
    if (dflt === undefined) dflt = 0.0;
    for (const k of keys) {
      if (k in o && o[k] !== null && o[k] !== undefined) {
        const v = parseFloat(o[k]);
        if (!isNaN(v)) return v;
      }
    }
    return dflt;
  }

  function gp_epoch_to_unix(ep) {
    // EPOCH is an ISO-ish UTC string, e.g. "2024-06-01T12:34:56.789012".
    // Append Z if no timezone present so it is parsed as UTC.
    if (!ep) return 0.0;
    let s = String(ep);
    if (!/[zZ]|[+\-]\d\d:?\d\d$/.test(s)) s += "Z";
    const t = Date.parse(s);
    return isNaN(t) ? 0.0 : t / 1000.0;
  }

  function parse_omm(o) {
    const e = {};
    e.name = (o.AMSAT_NAME || o.OBJECT_NAME || o.NAME || "").slice(0, 25);
    e.norad = Math.trunc(_f(o, ["NORAD_CAT_ID"]));
    e.intl_des = (o.OBJECT_ID || "").slice(0, 11);
    e.epoch_unix = o.EPOCH ? gp_epoch_to_unix(o.EPOCH) : 0.0;
    e.incl = _f(o, ["INCLINATION"]);
    e.ecc = _f(o, ["ECCENTRICITY"]);
    e.raan = _f(o, ["RA_OF_ASC_NODE"]);
    e.argp = _f(o, ["ARG_OF_PERICENTER"]);
    e.ma = _f(o, ["MEAN_ANOMALY"]);
    e.mean_motion = _f(o, ["MEAN_MOTION"]);
    e.bstar = _f(o, ["BSTAR"]);
    e.rev_at_epoch = Math.trunc(_f(o, ["REV_AT_EPOCH"]));
    e.period_min = period_min(e.mean_motion);
    return e;
  }

  function parse_gp_json(text) {
    let data = JSON.parse(text);
    if (!Array.isArray(data)) data = [data];
    const out = [];
    for (const o of data) {
      try {
        const e = parse_omm(o);
        if (e.mean_motion > 0) out.push(e);
      } catch (err) { /* skip */ }
    }
    return out;
  }

  global.OLEngine = {
    DEG, TWO_PI, MU, RE_KM, J2, SIDEREAL_DAY_S,
    KM_PER_DEG: Math.PI / 180.0 * RE_KM,
    semi_major_axis_km, period_min, footprint_radius_deg,
    central_angle_for_elevation_deg, j2_rates,
    central_angle_bearing, dest_point, footprint_locus,
    node_shift_deg, kepler_E, canonical_track, km_ring_step,
    parse_gp_json, parse_omm,
  };
})(window);
