// sheets.js — the OSCARLOCATOR sheet drawing primitives and the four page
// generators, ported faithfully from oscarlocator.py. Each generator takes an
// OLSurface and draws one full page; the caller flushes the page (canvas clear
// or pdf.addPage) between pages.

(function (global) {
  "use strict";

  const E = global.OLEngine;
  const OL = global.OSCARLOCATOR;
  const C = OL.consts;
  const H = OL.helpers;
  const DEG = E.DEG;
  const KM_PER_DEG = E.KM_PER_DEG;
  const RE_KM = E.RE_KM;
  const PolarAxes = OL.PolarAxes;
  const Projection = OL.Projection;
  const range = H.range;

  function PAGE_W() { return OL.PAGE()[0]; }
  function PAGE_H() { return OL.PAGE()[1]; }

  // ---------- _draw_rim_ticks ----------
  function draw_rim_ticks(ax) {
    const rmax = ax.rmax;
    const minor = rmax * 0.010, mid = rmax * 0.020, major = rmax * 0.032;
    for (let deg = 0; deg < 360; deg++) {
      let ln, lw;
      if (deg % 10 === 0) { ln = major; lw = 1.1; }
      else if (deg % 5 === 0) { ln = mid; lw = 0.8; }
      else { ln = minor; lw = 0.5; }
      const a = deg * DEG;
      ax.plot([a, a], [rmax - ln, rmax], "#000000", lw, null, "butt");
    }
  }

  // ---------- projected polyline (mirror _project_polyline) ----------
  function project_polyline(ax, proj, pts, color, lw, dash) {
    const rmax = ax.rmax;
    let th = [], rr = [], prev_br = null;
    const flush = () => { if (th.length > 1) ax.plot(th, rr, color, lw, dash); };
    for (const [lon, lat] of pts) {
      const [ca, br] = proj.project(lat, lon);
      if (ca > rmax) { flush(); th = []; rr = []; prev_br = null; continue; }
      if (prev_br !== null && Math.abs(br - prev_br) > 180) { flush(); th = []; rr = []; }
      th.push(br * DEG); rr.push(ca); prev_br = br;
    }
    flush();
  }

  function draw_coastlines(ax, proj, segments) {
    for (const seg of segments)
      project_polyline(ax, proj, seg, "#4d6b80", C.LW_COAST, null);
  }

  // ---------- _draw_graticule ----------
  function draw_graticule(ax, proj) {
    let lat_lo, lat_hi, par_lo, par_hi;
    if (proj.is_south) { lat_lo = -90; lat_hi = 1; par_lo = -75; par_hi = 1; }
    else if (proj.is_polar) { lat_lo = 0; lat_hi = 91; par_lo = 0; par_hi = 76; }
    else { lat_lo = -90; lat_hi = 91; par_lo = -75; par_hi = 76; }
    for (let lon = -180; lon < 180; lon += 15) {
      const pts = [];
      for (let j = lat_lo; j < lat_hi; j += 2) pts.push([lon, j]);
      project_polyline(ax, proj, pts, "#c4c4c4", C.LW_GRID, null);
    }
    for (let lat = par_lo; lat < par_hi; lat += 15) {
      const pts = [];
      for (let k = -180; k < 181; k += 2) pts.push([k, lat]);
      project_polyline(ax, proj, pts, "#c4c4c4", C.LW_GRID, null);
    }
  }

  // ---------- _draw_az_grid ----------
  function draw_az_grid(ax, proj, opts) {
    opts = opts || {};
    const rmax = ax.rmax;
    const alt_km = opts.alt_km || null;
    const skip_horizon = !!opts.skip_horizon;
    const dist_rings = !!opts.dist_rings;
    const dist_max_deg = opts.dist_max_deg;
    const label_el = opts.label_el !== false;

    if (proj.is_polar) {
      for (let a = 0; a < 360; a += 30) {
        ax.plot([a * DEG, a * DEG], [0, rmax], "#b0b0b0", C.LW_SPOKE);
        const disp = a <= 180 ? a : a - 360;
        const hemi = (0 < disp && disp < 180) ? "E" : (disp < 0 ? "W" : "");
        const cardinal = (a === 0 || a === 90 || a === 180 || a === 270);
        const r_label = (a === 0 || a === 180) ? rmax * 1.065 : rmax * 1.10;
        const bbox = cardinal ? { pad: 0.10, fc: "white", ec: "none", alpha: 0.9 } : null;
        ax.textAt(a * DEG, r_label, Math.abs(disp) + "\u00b0" + hemi,
          { ha: "center", va: "center", fs: C.FS_AZLABEL, color: "#444444",
            bold: true, bbox: bbox });
      }
      for (let lat_abs = 15; lat_abs < 91; lat_abs += 15) {
        const ring = 90 - lat_abs;
        if (ring <= 0) continue;
        ax.ring(ring, "#9a9a9a", C.LW_RING);
        const lat_label = proj.is_south ? -lat_abs : lat_abs;
        ax.textAt(62 * DEG, ring, lat_label + "\u00b0",
          { fs: C.FS_RINGLABEL, color: "#555555", ha: "center", va: "center",
            bold: true, bbox: { pad: 0.12, fc: "white", ec: "none", alpha: 0.85 } });
      }
      for (const a of [0, 90, 180, 270])
        ax.plot([a * DEG, a * DEG], [rmax * 0.97, rmax], "#000000", 2.2, null, "butt");
      ax.markerAt(0, 0, "+", C.MARK_CROSS, "#000000", C.MEW_CROSS);
      return;
    }
    // QTH-centred
    for (let az = 0; az < 360; az += 15)
      ax.plot([az * DEG, az * DEG], [0, rmax], "#b0b0b0", C.LW_SPOKE);
    for (let az = 0; az < 360; az += 30) {
      if (az === 0 || az === 90 || az === 180 || az === 270) continue;
      ax.textAt(az * DEG, rmax * 1.05, az + "\u00b0",
        { ha: "center", va: "center", fs: C.FS_AZLABEL, color: "#444444", bold: true });
    }
    for (const [az, name] of [[0, "N"], [90, "E"], [180, "S"], [270, "W"]]) {
      ax.textAt(az * DEG, rmax * 1.07, name, { ha: "center", va: "center",
        fs: C.FS_CARDINAL, bold: true, color: "#000000" });
      ax.plot([az * DEG, az * DEG], [rmax * 0.97, rmax], "#000000", 2.2, null, "butt");
    }
    if (alt_km) {
      const label_brg = 45;
      const ring_specs = [];
      for (const el of [0, 10, 30, 60]) {
        if (el === 0 && skip_horizon) continue;
        const rho = E.central_angle_for_elevation_deg(el, alt_km);
        if (rho === null || rho > rmax) continue;
        ring_specs.push([el, rho]);
      }
      for (const [el, rho] of ring_specs) {
        const lw = el === 0 ? C.LW_RING + 0.5 : C.LW_RING;
        const col = el === 0 ? "#7a7a7a" : "#9a9a9a";
        ax.ring(rho, col, lw);
      }
      const min_gap = rmax * 0.05;
      const placed = [];
      const sorted = ring_specs.slice().sort((a, b) => b[1] - a[1]);
      for (const [el, rho] of sorted) {
        if (!label_el) break;
        if (rho < rmax * 0.06) continue;
        if (placed.some(pr => Math.abs(rho - pr) < min_gap)) continue;
        placed.push(rho);
        ax.textAt(label_brg * DEG, rho, el + "\u00b0 el",
          { fs: C.FS_RINGLABEL, color: el === 0 ? "#444444" : "#555555",
            ha: "center", va: "bottom", bold: true });
      }
      if (dist_rings) {
        const reach_deg = Math.min(dist_max_deg || rmax, rmax);
        const reach_km = reach_deg * KM_PER_DEG;
        const step_km = E.km_ring_step(reach_km);
        let km = step_km;
        while (km < reach_km - step_km * 0.25) {
          const rho = km / KM_PER_DEG;
          if (rho < rmax * 0.05) { km += step_km; continue; }
          ax.ring(rho, "#bdbdbd", C.LW_GRID, [4, 3]);
          ax.textAt(135 * DEG, rho, km + "\u00a0km",
            { fs: C.FS_RINGLABEL, color: "#777777", ha: "center", va: "bottom", bold: true });
          km += step_km;
        }
      } else {
        const mid = Math.round(rmax / 2.0 / 10.0) * 10.0;
        if (0 < mid && mid < rmax) {
          ax.ring(mid, "#cccccc", C.LW_GRID, [4, 3]);
          ax.textAt(225 * DEG, mid, roundTo(mid * KM_PER_DEG, -2) + " km",
            { fs: C.FS_RINGLABEL, color: "#888888", ha: "center", va: "bottom" });
        }
      }
    } else {
      for (let rho = 30; rho <= Math.trunc(rmax); rho += 30) {
        ax.ring(rho, "#9a9a9a", C.LW_RING);
        ax.textAt(45 * DEG, rho, roundTo(rho * KM_PER_DEG, -2) + " km",
          { fs: C.FS_RINGLABEL, color: "#555555", ha: "center", va: "bottom", bold: true });
      }
    }
    ax.markerAt(0, 0, "+", C.MARK_CROSS, "#000000", C.MEW_CROSS);
  }

  function roundTo(x, ndigits) {
    const f = Math.pow(10, -ndigits);
    return Math.round(x / f) * f;
  }

  // ---------- _draw_footprint_overlay ----------
  function draw_footprint_overlay(ax, foot_deg, with_rose, center) {
    const rmax = ax.rmax;
    center = center || [0.0, 0.0];
    const fr = Math.min(foot_deg, rmax);
    const c_rho = center[0];
    const concentric = c_rho <= 1e-6;

    if (with_rose && concentric) {
      for (let az = 0; az < 360; az += 30)
        ax.plot([az * DEG, az * DEG], [0, fr], "#a0a0a0", C.LW_SPOKE);
      const edge_cap = rmax * (PAGE_W() / C.PLOT_DIAMETER_IN) * 0.95;
      const gap = Math.max(4.0, rmax * 0.06);
      let deg_r = Math.min(fr + gap, edge_cap - gap);
      let card_r = Math.min(fr + gap * 2.2, edge_cap);
      if (card_r <= deg_r) card_r = deg_r + gap;
      for (let az = 0; az < 360; az += 30) {
        if (az % 90 !== 0)
          ax.textAt(az * DEG, deg_r, az + "\u00b0", { ha: "center", va: "center",
            fs: C.FS_AZLABEL, color: "#444444", bold: true });
      }
      for (const [az, name] of [[0, "N"], [90, "E"], [180, "S"], [270, "W"]])
        ax.textAt(az * DEG, card_r, name, { ha: "center", va: "center",
          fs: C.FS_CARDINAL, bold: true, color: "#000000" });

      const foot_km = foot_deg * KM_PER_DEG;
      const step_km = E.km_ring_step(foot_km);
      let km = step_km;
      while (km < foot_km - step_km * 0.25) {
        const rho = km / KM_PER_DEG;
        ax.ring(rho, "#9a9a9a", C.LW_RING);
        ax.textAt(135 * DEG, rho, km + "\u00a0km", { fs: C.FS_RINGLABEL,
          color: "#555555", ha: "center", va: "bottom", bold: true });
        km += step_km;
      }
    }
    if (concentric) {
      ax.ring(fr, "#cc0000", C.LW_FOOT, null, 1);
      ax.markerAt(0, 0, "+", C.MARK_CROSS, "#000000", C.MEW_CROSS);
    }
  }

  // ---------- _draw_qth_rings_projected ----------
  function draw_qth_rings_projected(ax, proj, obs, alt_km, foot_deg) {
    const rmax = ax.rmax;
    if (!alt_km) return;
    for (const el of [10, 30, 60]) {
      const rho = E.central_angle_for_elevation_deg(el, alt_km);
      if (rho === null || rho >= foot_deg) continue;
      const locus = E.footprint_locus(obs.lat, obs.lon, rho);
      project_polyline(ax, proj, locus.map(([lat, lon]) => [lon, lat]),
        "#9a9a9a", C.LW_RING, null);
    }
    const foot_km = foot_deg * KM_PER_DEG;
    const step_km = E.km_ring_step(foot_km);
    let km = step_km;
    while (km < foot_km - step_km * 0.25) {
      const rdeg = km / KM_PER_DEG;
      const locus = E.footprint_locus(obs.lat, obs.lon, rdeg);
      project_polyline(ax, proj, locus.map(([lat, lon]) => [lon, lat]),
        "#bdbdbd", C.LW_GRID, null);
      const [llat, llon] = E.dest_point(obs.lat, obs.lon, rdeg, 135.0);
      const [lr, lb] = proj.project(llat, llon);
      if (lr <= rmax)
        ax.textAt(lb * DEG, lr, km + "\u00a0km", { fs: C.FS_RINGLABEL,
          color: "#777777", ha: "center", va: "bottom", bold: true });
      km += step_km;
    }
  }

  global.OLSheets = {
    draw_rim_ticks, project_polyline, draw_coastlines, draw_graticule,
    draw_az_grid, draw_footprint_overlay, draw_qth_rings_projected, roundTo,
  };
})(window);
