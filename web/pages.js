// pages.js — the four OSCARLOCATOR page generators and the top-level generate()
// orchestrator. Ported from oscarlocator.py (_base_map_page, _footprint_page,
// _arc_page, _base_map_with_footprint_page, _generate_oscarlocator_pdf_body).
//
// A "page" object {newPage()} lets a generator request a fresh surface; the
// renderer wires that to canvas-clear (preview) or pdf.addPage (download).

(function (global) {
  "use strict";

  const E = global.OLEngine;
  const OL = global.OSCARLOCATOR;
  const S = global.OLSheets;
  const C = OL.consts;
  const H = OL.helpers;
  const DEG = E.DEG;
  const KM_PER_DEG = E.KM_PER_DEG;
  const RE_KM = E.RE_KM;
  const PolarAxes = OL.PolarAxes;
  const Projection = OL.Projection;

  const POLAR_INFLATE = C.POLAR_RANGE_CIRCLE_INFLATION;
  function PAGE_W() { return OL.PAGE()[0]; }

  function polar_range_circle_deg(foot_deg) { return foot_deg * POLAR_INFLATE; }

  // ---------- base map page ----------
  function base_map_page(surf, proj, qth_name, segments, rmax, opts) {
    opts = opts || {};
    const alt_km = opts.alt_km || null;
    const sat_name = opts.sat_name || "";
    const reduced_text = !!opts.reduced_text;
    const ring_alt = reduced_text ? null : alt_km;
    let title, sub, pole;
    if (proj.is_polar) {
      const hemi = proj.is_south ? "southern" : "northern";
      pole = proj.is_south ? "South" : "North";
      title = "OSCARLOCATOR \u2014 Polar Base Map (" + hemi + ")";
      sub = "Polar great-circle map of the " + hemi + " hemisphere " +
            "(generic \u2014 use with any QTH via the EQX list)";
    } else {
      if (sat_name && !reduced_text) {
        const suffix = " \u2014 OSCARLOCATOR Base Map";
        title = H.fit_sat_name(sat_name, suffix) + suffix;
      } else {
        title = "OSCARLOCATOR \u2014 Base Map";
      }
      if (ring_alt) {
        sub = "Azimuthal-equidistant map centred on " + qth_name + "  (" +
              proj.qlat.toFixed(3) + ", " + proj.qlon.toFixed(3) +
              ") \u2014 rings are elevation at " + Math.round(ring_alt) + "\u00a0km altitude";
      } else {
        sub = "Azimuthal-equidistant map centred on " + qth_name + "  (" +
              proj.qlat.toFixed(3) + ", " + proj.qlon.toFixed(3) + ")";
      }
    }
    const ax = new PolarAxes(surf, rmax, proj);
    ax.drawRim();
    H.draw_title(surf, title, sub);
    S.draw_graticule(ax, proj);
    S.draw_coastlines(ax, proj, segments);
    S.draw_az_grid(ax, proj, { alt_km: proj.is_polar ? null : ring_alt });
    S.draw_rim_ticks(ax);
    let note;
    if (reduced_text) {
      if (proj.is_polar) {
        note = "Print this base map on paper/card and the range-circle and " +
          "path-arc overlays on transparency film, all at 100% (actual " +
          "size). Centre is the " + pole + " Pole; rings are latitude (15\u00b0), " +
          "spokes are longitude, rim ticks 1\u00b0. Align overlay centres " +
          "on the pole; rotate the path-arc to the ascending-node longitude " +
          "from the Crossings List. The satellite is workable while its " +
          "track is inside the range circle \u2014 read AOS/LOS where it crosses.";
        H.draw_footer(surf, note, undefined, 0.96);
      } else {
        note = "OSCARLOCATOR \u2014 print this base map on paper/card at 100% " +
          "(actual size); print the range-circle and path-arc overlays on " +
          "transparency film at 100%. Pin the overlays through the centre " +
          "cross over your station. Spokes are azimuth, rim ticks are 1\u00b0. " +
          "The satellite is workable while its ground track (path-arc) is " +
          "inside the range circle; read AOS/LOS where the track crosses the circle.";
        H.draw_footer(surf, note);
      }
      H.draw_branding(surf);
      return;
    }
    if (proj.is_polar) {
      note = "Print on paper or card at 100% (actual size). Centre is the " +
        pole + " Pole; rings are latitude (15\u00b0), spokes are longitude. " +
        "Black rim ticks register stacked overlays. Lay the path-arc " +
        "and range-circle overlays on top.";
    } else if (alt_km) {
      note = "Print on paper or card at 100% (actual size). Overlays " +
        "register on the centre cross and the black rim ticks; rings " +
        "show the satellite's elevation angle (the 0\u00b0 el ring is its " +
        "range-circle edge), spokes are azimuth.";
    } else {
      note = "Print on paper or card at 100% (actual size). Overlays " +
        "register on the centre cross; rings are great-circle distance, " +
        "spokes are azimuth, grey graticule is lat/lon (15\u00b0).";
    }
    H.draw_footer(surf, note);
    H.draw_branding(surf);
  }

  // ---------- footprint (range-circle) page ----------
  function footprint_page(surf, sat_name, alt_km, proj, rmax, reduced_text) {
    const foot_deg = E.footprint_radius_deg(alt_km);
    const polar_fit = proj.is_polar;
    const draw_deg = polar_fit ? polar_range_circle_deg(foot_deg) : foot_deg;
    const fr = Math.min(draw_deg, rmax);
    if (reduced_text) {
      const ax = new PolarAxes(surf, rmax, null, { show_rim: false });
      S.draw_footprint_overlay(ax, draw_deg, true);
      ax.textAt(0, fr * 0.18, sat_name, { ha: "center", va: "center",
        fs: 9, color: "#888888" });
      return;
    }
    let sub;
    if (polar_fit) {
      sub = "Range-circle radius " + foot_deg.toFixed(1) + "\u00b0 (~" +
        S.roundTo(foot_deg * KM_PER_DEG, -1) + " km) at " + Math.round(alt_km) +
        " km mean altitude \u2014 enlarged ~" +
        Math.round((POLAR_INFLATE - 1.0) * 100.0) + "% to best fit the polar map across latitudes";
    } else {
      sub = "Range-circle radius " + foot_deg.toFixed(1) + "\u00b0 (~" +
        S.roundTo(foot_deg * KM_PER_DEG, -1) + " km) at " + Math.round(alt_km) +
        " km mean altitude";
    }
    const suffix = " \u2014 OSCARLOCATOR Range Circle Overlay";
    const ax = new PolarAxes(surf, rmax, null, { show_rim: false });
    H.draw_title(surf, H.fit_sat_name(sat_name, suffix) + suffix, sub);
    S.draw_footprint_overlay(ax, draw_deg, true);
    let note = "Print on transparency at 100%. Pin the centre cross over " +
      "your QTH at the map centre. The red circle is the range " +
      "circle: the satellite is in range whenever its ground track " +
      "(path-arc overlay) is INSIDE the circle. Read AOS and LOS " +
      "where the arc crosses the red circle; inner rings are ground " +
      "distance, spokes are azimuth. Scale matches the base map.";
    if (polar_fit) {
      note += " (On the polar map the true coverage edge is a slight oval; " +
        "this generic circle is sized to fit it well at most latitudes.)";
    }
    H.draw_footer(surf, note);
    H.draw_branding(surf);
  }

  // ---------- path-arc page ----------
  function arc_page(surf, sat, proj, rmax, reduced_text) {
    const shift = E.node_shift_deg(sat);
    let ax;
    if (reduced_text) {
      ax = new PolarAxes(surf, rmax, proj);
    } else {
      const arc_suffix = proj.is_polar
        ? " \u2014 OSCARLOCATOR Path Arc (orbit)"
        : " \u2014 OSCARLOCATOR Path Arc Overlay";
      const title = H.fit_sat_name(sat.name, arc_suffix) + arc_suffix;
      const sub = "Ground-track \u2014 incl. " + sat.incl.toFixed(1) +
        "\u00b0, period " + sat.period_min.toFixed(1) + "\u00a0min \u2014 advance " +
        Math.abs(shift).toFixed(1) + "\u00b0\u00a0" + (shift < 0 ? "W" : "E") + " per pass.";
      ax = new PolarAxes(surf, rmax, proj);
      H.draw_title(surf, title, sub);
    }
    S.draw_rim_ticks(ax);
    for (let rho = 30; rho <= Math.trunc(rmax); rho += 30)
      ax.ring(rho, "#cccccc", C.LW_GRID);

    const track = E.canonical_track(sat, proj.is_south);
    let th = [], rr = [];
    const segs = [], ticks = [];
    let prev_br = null;
    for (const [lon_rel, lat, minute] of track) {
      const ca = proj.is_south ? (90.0 + lat) : (90.0 - lat);
      const br = ((lon_rel % 360) + 360) % 360;
      if (ca > rmax) {
        if (th.length > 1) segs.push([th.slice(), rr.slice()]);
        th = []; rr = []; prev_br = null; continue;
      }
      if (prev_br !== null && Math.abs(br - prev_br) > 180) {
        if (th.length > 1) segs.push([th.slice(), rr.slice()]);
        th = []; rr = [];
      }
      th.push(br * DEG); rr.push(ca);
      ticks.push([br * DEG, ca, minute]);
      prev_br = br;
    }
    if (th.length > 1) segs.push([th, rr]);
    for (const [sth, srr] of segs) ax.plot(sth, srr, "#0033bb", C.LW_TRACK);

    // minute ticks (perpendicular marks)
    const _xy = (theta, rho) => [rho * Math.sin(theta), rho * Math.cos(theta)];
    const _rt = (x, y) => [Math.atan2(x, y), Math.hypot(x, y)];
    let last_min = null;
    const minor_len = 1.7, major_len = 3.4;
    const npts = ticks.length;
    const per = sat.period_min ? sat.period_min : 95.0;
    let label_step = 10;
    let found = false;
    for (const cand of [10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300]) {
      if (per / cand <= 14) { label_step = cand; found = true; break; }
    }
    if (!found) label_step = Math.max(10, Math.round(per / 14.0 / 10.0) * 10);
    const n_labels = Math.max(1, Math.trunc(per / label_step) + 1);
    const label_fs = n_labels <= 12 ? C.FS_TICKLABEL + 1
      : (n_labels <= 18 ? C.FS_TICKLABEL : C.FS_TICKLABEL - 1.5);

    const tickStep = sat.period_min / (track.length - 1);
    for (let i = 0; i < ticks.length; i++) {
      const [thb, ca, minute] = ticks[i];
      const mm = Math.round(minute);
      if (mm === last_min) continue;
      if (Math.abs(minute - mm) > tickStep / 2 + 1e-6) continue;
      const major = (mm % label_step === 0);
      const j0 = Math.max(i - 1, 0), j1 = Math.min(i + 1, npts - 1);
      const [x0, y0] = _xy(ticks[j0][0], ticks[j0][1]);
      const [x1, y1] = _xy(ticks[j1][0], ticks[j1][1]);
      const dx = x1 - x0, dy = y1 - y0;
      const dn = Math.hypot(dx, dy) || 1.0;
      const px = -dy / dn, py = dx / dn;
      const [cx, cy] = _xy(thb, ca);
      const hl = major ? major_len : minor_len;
      const pts_x = [cx - px * hl, cx + px * hl];
      const pts_y = [cy - py * hl, cy + py * hl];
      const seg_t = [], seg_r = [];
      for (let k = 0; k < 2; k++) { const [t, r] = _rt(pts_x[k], pts_y[k]); seg_t.push(t); seg_r.push(r); }
      ax.plot(seg_t, seg_r, major ? "#001f7a" : "#2255cc",
        major ? 3.0 : 1.8, null, "butt");
      if (major && mm !== 0) {
        const lx = cx + px * (hl + 3.2), ly = cy + py * (hl + 3.2);
        const [lt, lr] = _rt(lx, ly);
        ax.textAt(lt, lr, String(mm), { fs: label_fs, color: "#001f7a",
          ha: "center", va: "center", bold: true });
      }
      last_min = mm;
    }

    // EQX arrow
    const eqx_th = 0.0;
    const tail = ax.pt(eqx_th, 0);
    const headpt = ax.pt(eqx_th, rmax);
    surf.line([tail, headpt], "#cc0000", C.LW_INDICATOR);
    surf.arrowhead(ax.pt(eqx_th, rmax * 0.96), headpt, "#cc0000", C.LW_INDICATOR);

    const lbl_th = proj.is_south ? 290 * DEG : 250 * DEG;
    const node_label = proj.is_south ? "descending node\n(S sheet)" : "ascending node\n(N sheet)";
    ax.textAt(lbl_th, rmax * 0.52, "EQX \u2014 0 min\n" + node_label + "\nline up on map",
      { color: "#cc0000", fs: C.FS_BIGLABEL - 3, bold: true, ha: "center",
        va: "center", linespacing: 1.3,
        bbox: { pad: 0.25, fc: "white", ec: "#cc0000", lw: 1.0, alpha: 0.92 } });

    ax.markerAt(0, 0, "+", 14, "#000000", 2);

    // per-pass rotation indicator. North-up azimuthal view: seen from above the
    // North Pole, Earth spins CCW, so eastward is CCW and WESTWARD is CW. The
    // node drifts west each pass, so a northern overlay rotates CLOCKWISE; the
    // southern sheet mirrors longitude, flipping the sense to counter-clockwise.
    const west = shift < 0;
    const ccw = proj.is_south ? west : (!west);
    if (!reduced_text) {
      const r_ind = rmax * 1.18;
      const half = Math.abs(shift) * DEG / 2.0;
      const top = proj.is_polar ? Math.PI : 0.0;
      const a_lo = top - half, a_hi = top + half;
      const arc = [];
      for (let k = 0; k <= 60; k++) arc.push(a_lo + (a_hi - a_lo) * k / 60);
      ax.plot(arc, arc.map(() => r_ind), "#cc0000", C.LW_INDICATOR, null, "round");
      // which end is screen-left? compare projected x of both ends
      const plo = ax.pt(a_lo, r_ind), phi = ax.pt(a_hi, r_ind);
      const left_ang = plo[0] <= phi[0] ? a_lo : a_hi;
      const right_ang = plo[0] <= phi[0] ? a_hi : a_lo;
      const tip = ccw ? left_ang : right_ang;
      const pre = tip + Math.sign(top - tip) * (0.6 * DEG);
      surf.arrowhead(ax.pt(pre, r_ind), ax.pt(tip, r_ind), "#cc0000", C.LW_INDICATOR);
    }
    const geo = west ? "west" : "east";
    const sense = ccw ? "counter-clockwise" : "clockwise";
    if (!reduced_text) {
      surf.text("rotate sheet " + Math.abs(shift).toFixed(1) + "\u00b0 " + sense +
        " (node moves " + geo + ") each pass", 0.5, 0.862,
        { ha: "center", va: "bottom", fs: C.FS_BIGLABEL, color: "#cc0000", bold: true });
    }

    if (reduced_text) {
      const occupied = new Set();
      for (const [tth, trho] of ticks) {
        if (0.30 * rmax <= trho && trho <= 0.92 * rmax)
          occupied.add(Math.trunc(tth / DEG) % 360);
      }
      const eqx_deg = proj.is_south ? 290 : 250;
      for (let d = eqx_deg - 28; d < eqx_deg + 29; d++) occupied.add(((d % 360) + 360) % 360);
      for (const d of [...range0(0, 12), ...range0(348, 360)]) occupied.add(d % 360);
      const free = [];
      for (let d = 0; d < 360; d++) if (!occupied.has(d)) free.push(d);
      let best_centre = 200;
      if (free.length) {
        const runs = [];
        let start = free[0], prev = free[0];
        const ext = free.slice(1).concat([free[0] + 360]);
        for (const d of ext) {
          if (d === prev + 1) prev = d;
          else { runs.push([start, prev]); start = d < 360 ? d % 360 : d - 360; prev = d; }
        }
        if (runs.length) {
          let best = runs[0];
          for (const r of runs) if (r[1] - r[0] > best[1] - best[0]) best = r;
          best_centre = Math.trunc((best[0] + best[1]) / 2.0) % 360;
        }
      }
      const info = sat.name + "\nincl " + sat.incl.toFixed(1) + "\u00b0   \u2022   period " +
        sat.period_min.toFixed(1) + " min\nadvance " + Math.abs(shift).toFixed(1) +
        "\u00b0 " + (shift < 0 ? "W" : "E") + " per pass";
      ax.textAt(best_centre * DEG, rmax * 0.6, info, { color: "#333333", fs: 8.5,
        ha: "center", va: "center", linespacing: 1.5,
        bbox: { pad: 0.4, fc: "white", ec: "#cccccc", lw: 0.8, alpha: 0.9 } });
      return;
    }

    let note;
    if (proj.is_polar) {
      const node = proj.is_south ? "descending node" : "ascending node";
      note = "Print on transparency at 100%. Lay over the polar base map " +
        "with centres aligned and the " + node + " at the EQX longitude, then " +
        "rotate the whole sheet " + Math.abs(shift).toFixed(1) + "\u00b0 " +
        (shift < 0 ? "westward" : "eastward") + " about the centre for each " +
        "successive pass (see the rim arrow). Tick marks count minutes " +
        "after the EQX, with longer labelled marks every 10 minutes.";
    } else {
      note = "Print on transparency at 100%. Pin the centre cross over the " +
        "station, then rotate the arc " + Math.abs(shift).toFixed(1) + "\u00b0 " +
        (shift < 0 ? "westward" : "eastward") + " about the centre for " +
        "each successive pass (see the rim arrow). Tick marks count " +
        "minutes after the EQX, with longer labelled marks every 10 minutes.";
    }
    H.draw_footer(surf, note);
    H.draw_branding(surf);
  }

  function range0(a, b) { const o = []; for (let i = a; i < b; i++) o.push(i); return o; }

  // ---------- combined base-map + range-circle page ----------
  function base_map_with_footprint_page(surf, proj, obs, qth_name, segments,
                                        rmax, foot_deg, opts) {
    opts = opts || {};
    const sat_name = opts.sat_name || "";
    const alt_km = opts.alt_km || null;
    const reduced_text = !!opts.reduced_text;
    const foot_km = S.roundTo(foot_deg * KM_PER_DEG, -1);
    let size = "range-circle radius " + foot_deg.toFixed(1) + "\u00b0 (~" + foot_km + "\u00a0km)";
    if (alt_km) size += " at " + Math.round(alt_km) + "\u00a0km mean altitude";
    let title, sub;
    if (proj.is_polar) {
      const hemi = proj.is_south ? "southern" : "northern";
      const suffix = " \u2014 OSCARLOCATOR \u2014 Map + Range Circle at QTH (" + hemi + ")";
      const nm = sat_name ? H.fit_sat_name(sat_name, suffix) : "";
      title = nm ? (nm + suffix) : ("OSCARLOCATOR \u2014 Map + Range Circle at QTH (" + hemi + ")");
      sub = "Range circle over " + qth_name + " on the " + hemi + " polar map \u2014 " + size;
    } else {
      const suffix = " \u2014 OSCARLOCATOR \u2014 Map + Range Circle at QTH";
      const nm = sat_name ? H.fit_sat_name(sat_name, suffix) : "";
      title = nm ? (nm + suffix) : "OSCARLOCATOR \u2014 Map + Range Circle at QTH";
      sub = "Range circle over " + qth_name + " (" + obs.lat.toFixed(3) + ", " +
        obs.lon.toFixed(3) + ") \u2014 " + size;
    }
    const ax = new PolarAxes(surf, rmax, proj);
    ax.drawRim();
    H.draw_title(surf, title, sub);
    S.draw_graticule(ax, proj);
    S.draw_coastlines(ax, proj, segments);
    S.draw_rim_ticks(ax);

    if (proj.is_polar) {
      S.draw_az_grid(ax, proj, { alt_km: null, skip_horizon: true });
      S.draw_qth_rings_projected(ax, proj, obs, alt_km, foot_deg);
      const locus = E.footprint_locus(obs.lat, obs.lon, Math.min(foot_deg, rmax));
      S.project_polyline(ax, proj, locus.map(([lat, lon]) => [lon, lat]),
        "#cc0000", C.LW_FOOT, null);
      const [q_rho, q_br] = proj.project(obs.lat, obs.lon);
      if (q_rho <= rmax) {
        ax.markerAt(q_br * DEG, q_rho, "+", C.MARK_CROSS, "#000000", C.MEW_CROSS);
        ax.markerAt(q_br * DEG, q_rho, "*", 13, "#cc0000");
      }
    } else {
      S.draw_az_grid(ax, proj, { alt_km: alt_km, skip_horizon: true,
        dist_rings: false, label_el: false });
      S.draw_footprint_overlay(ax, foot_deg, false);
      ax.markerAt(0, 0, "*", 13, "#cc0000");
    }
    let note;
    if (reduced_text) {
      note = "Print this sheet on paper/card and the path-arc overlay on " +
        "transparency, both at 100% (actual size). The red circle is the " +
        "satellite's range circle, centred on your station (red star); " +
        "spokes are azimuth, rim ticks 1\u00b0. Pin the path-arc through the " +
        "centre, rotate it to the node longitude from the Crossings List, " +
        "then by the per-pass advance for each pass. The satellite is " +
        "workable while its track is inside the red circle \u2014 read " +
        "AOS/LOS where it crosses.";
      H.draw_footer(surf, note, undefined, proj.is_polar ? 0.96 : C.TEXT_W);
    } else {
      note = "Print on paper or card at 100%. The red circle is the satellite's " +
        "range circle when it is directly over your station (red star). The " +
        "base map's spokes give azimuth and the rings inside the circle give " +
        "elevation and ground distance to the sub-point. Use the separate " +
        "path-arc overlay to see when the satellite enters this circle.";
      H.draw_footer(surf, note);
    }
    H.draw_branding(surf);
  }

  // ---------- orchestrator: returns an array of page-draw callbacks ----------
  // Each callback takes a fresh surface and draws one page. The caller decides
  // how surfaces are produced (canvas preview vs jsPDF pages).
  function buildPages(opts) {
    // opts: { obs:{lat,lon}, qth_name, sat, when_unix, projection,
    //         footprint_on_qth, reduced_text, segments }
    const obs = opts.obs;
    const qth_name = opts.qth_name;
    const sat = opts.sat;
    let projection = opts.projection || "qth";
    const footprint_on_qth = !!opts.footprint_on_qth;
    const reduced_text = !!opts.reduced_text;
    const segments = opts.segments;

    if (projection === "polar-auto") projection = obs.lat < 0 ? "polar-south" : "polar";

    let proj, rmax;
    if (projection === "polar") { proj = new Projection("polar"); rmax = 90.0; }
    else if (projection === "polar-south") { proj = new Projection("polar-south"); rmax = 90.0; }
    else {
      proj = new Projection("qth", obs.lat, obs.lon);
      rmax = Math.max(50.0, Math.min(80.0, Math.abs(obs.lat) + 25.0));
    }

    const sma = E.semi_major_axis_km(sat.mean_motion);
    const alt_km = sma > 0 ? Math.max(sma - RE_KM, 1.0) : 800.0;
    const foot_deg = E.footprint_radius_deg(alt_km);

    const pages = [];
    if (footprint_on_qth) {
      pages.push(surf => base_map_with_footprint_page(surf, proj, obs, qth_name,
        segments, rmax, foot_deg, { sat_name: sat.name, alt_km: alt_km, reduced_text }));
      pages.push(surf => arc_page(surf, sat, proj, rmax, reduced_text));
    } else {
      pages.push(surf => base_map_page(surf, proj, qth_name, segments, rmax,
        { alt_km: alt_km, sat_name: sat.name, reduced_text }));
      pages.push(surf => footprint_page(surf, sat.name, alt_km, proj, rmax, reduced_text));
      pages.push(surf => arc_page(surf, sat, proj, rmax, reduced_text));
    }
    const kind = { polar: "polar-north", "polar-south": "polar-south" }[projection] || "QTH-centred";
    return {
      pages: pages,
      meta: {
        title: "OSCARLOCATOR (" + kind + ") \u2014 " + sat.name,
        subject: "Printable base map, footprint and orbit overlays",
        creator: "OSCARLOCATOR Web Generator",
        projection: projection,
      },
    };
  }

  global.OLPages = {
    base_map_page, footprint_page, arc_page, base_map_with_footprint_page,
    buildPages, polar_range_circle_deg,
  };
})(window);
