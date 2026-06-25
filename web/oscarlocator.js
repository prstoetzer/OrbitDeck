// oscarlocator.js — faithful port of orbitdeck/gui/oscarlocator.py drawing code.
// Renders the OSCARLOCATOR sheets onto an OLSurface (canvas preview or jsPDF).
// All layout is in matplotlib FIGURE FRACTIONS so it matches the desktop output
// page-for-page. The credit footer reads
//   "OSCARLOCATOR Web Generator \u2014 Paul Stoetzer, N8HM".

(function (global) {
  "use strict";

  const E = global.OLEngine;
  const DEG = E.DEG;
  const RE_KM = E.RE_KM;
  const KM_PER_DEG = E.KM_PER_DEG;
  const SIDEREAL_DAY_S = E.SIDEREAL_DAY_S;

  // Page + plot geometry (mirror module constants)
  let PAGE_W_IN = 8.5, PAGE_H_IN = 11.0;
  const PLOT_DIAMETER_IN = 6.6;
  const MAP_RADIUS_DEG = 90.0;

  // line weights / font sizes (mirror constants)
  const LW_GRID = 0.9, LW_RING = 1.3, LW_SPOKE = 0.9, LW_COAST = 0.8,
        LW_TRACK = 2.6, LW_FOOT = 3.0, LW_INDICATOR = 2.4;
  const FS_TITLE = 18, FS_SUBTITLE = 11, FS_CARDINAL = 14, FS_AZLABEL = 9,
        FS_RINGLABEL = 8, FS_TICKLABEL = 8, FS_NOTE = 9, FS_BIGLABEL = 11;
  const MARK_CROSS = 16, MEW_CROSS = 2.4;
  const MARGIN_X = 0.08;
  const TEXT_L = MARGIN_X, TEXT_R = 1.0 - MARGIN_X, TEXT_W = TEXT_R - TEXT_L;
  const POLAR_RANGE_CIRCLE_INFLATION = 1.065;

  const VERSION = (global.OL_VERSION || "");

  // ---------- text wrapping (mirror _wrap_to_width) ----------
  function wrap_to_width(s, fontsize, width_frac) {
    if (width_frac === undefined) width_frac = TEXT_W;
    const avg_char_in = fontsize * 0.0090;
    const usable_in = width_frac * PAGE_W_IN;
    const ncols = Math.max(12, Math.trunc(usable_in / Math.max(avg_char_in, 0.01)));
    const sentinel = "\x00";
    const protectedStr = s.replace(/\u00a0/g, sentinel);
    const lines = textwrap(protectedStr, ncols);
    const out = lines.map(ln => ln.replace(new RegExp(sentinel, "g"), "\u00a0")).join("\n");
    return out || s;
  }
  // greedy word wrap, like Python textwrap.wrap (break_long_words default True)
  function textwrap(text, width) {
    const words = text.split(/\s+/).filter(w => w.length);
    const lines = [];
    let cur = "";
    for (let w of words) {
      while (w.length > width) {
        if (cur) { lines.push(cur); cur = ""; }
        lines.push(w.slice(0, width));
        w = w.slice(width);
      }
      if (!cur) cur = w;
      else if ((cur + " " + w).length <= width) cur += " " + w;
      else { lines.push(cur); cur = w; }
    }
    if (cur) lines.push(cur);
    return lines;
  }

  function fit_sat_name(name, suffix, min_fs, width_frac) {
    min_fs = min_fs || 13.0;
    width_frac = width_frac || TEXT_W;
    const avg_char_in = min_fs * 0.0102;
    const usable_in = width_frac * PAGE_W_IN;
    const max_chars = Math.max(8, Math.trunc(usable_in / Math.max(avg_char_in, 0.01)));
    let budget = max_chars - suffix.length;
    if (budget < 6) budget = 6;
    if (name.length <= budget) return name;
    return name.slice(0, Math.max(1, budget - 1)).replace(/\s+$/, "") + "\u2026";
  }

  // ---------- title / footer / branding ----------
  function draw_title(surf, title, subtitle) {
    // measured shrink: use surface.measureText to mirror matplotlib's renderer
    let fs = FS_TITLE;
    const maxw_pt = TEXT_W * PAGE_W_IN * 72;
    while (fs > 9 && surf.measureText(title, fs, true) > maxw_pt) fs -= 0.5;
    surf.text(title, 0.5, 0.955, { fs: fs, bold: true, va: "top", ha: "center" });
    if (subtitle) {
      const wrapped = wrap_to_width(subtitle, FS_SUBTITLE);
      surf.text(wrapped, 0.5, 0.917, { fs: FS_SUBTITLE, va: "top", ha: "center",
        color: "#222222", linespacing: 1.3 });
    }
  }
  function draw_footer(surf, note, y, width_frac) {
    if (y === undefined) y = 0.072;
    if (width_frac === undefined) width_frac = TEXT_W;
    const wrapped = wrap_to_width(note, FS_NOTE, width_frac);
    surf.text(wrapped, 0.5, y, { fs: FS_NOTE, va: "bottom", ha: "center",
      color: "#333333", linespacing: 1.3 });
  }
  function draw_branding(surf) {
    const tag = "OSCARLOCATOR Web Generator \u2014 Paul Stoetzer, N8HM";
    surf.text(tag, 0.5, 0.045, { fs: 6.5, va: "bottom", ha: "center",
      color: "#9a9a9a" });
  }

  // ---------- Projection (mirror _Projection) ----------
  function Projection(mode, qlat, qlon) {
    this.mode = mode || "qth";
    this.qlat = qlat || 0.0;
    this.qlon = qlon || 0.0;
  }
  Projection.prototype.project = function (lat, lon) {
    if (this.mode === "polar") return [90.0 - lat, ((lon % 360) + 360) % 360];
    if (this.mode === "polar-south") return [90.0 + lat, ((lon % 360) + 360) % 360];
    return E.central_angle_bearing(this.qlat, this.qlon, lat, lon);
  };
  Object.defineProperty(Projection.prototype, "is_polar", {
    get: function () { return this.mode === "polar" || this.mode === "polar-south"; }
  });
  Object.defineProperty(Projection.prototype, "is_south", {
    get: function () { return this.mode === "polar-south"; }
  });

  // ---------- PolarAxes: emulate matplotlib polar projection ----------
  // The plotting disc occupies a fixed PLOT_DIAMETER_IN, centred on the page via
  // the same fractional math as _polar_axes. r maps linearly 0..rmax to
  // 0..radius_frac. theta is measured per the zero-location and direction.
  function PolarAxes(surf, rmax, proj, opts) {
    opts = opts || {};
    this.surf = surf;
    this.rmax = rmax;
    const w = PLOT_DIAMETER_IN / PAGE_W_IN;
    const h = PLOT_DIAMETER_IN / PAGE_H_IN;
    this.left = (1 - w) / 2;
    this.bottom = (1 - h) / 2 - 0.02;
    this.wf = w; this.hf = h;
    this.cx = this.left + w / 2;
    this.cy = this.bottom + h / 2;
    // theta orientation
    if (proj && proj.is_polar) {
      if (proj.is_south) { this.zeroLoc = "S"; this.dir = -1; }
      else { this.zeroLoc = "S"; this.dir = 1; }
    } else {
      this.zeroLoc = "N"; this.dir = -1;   // compass azimuth, clockwise
    }
    this.show_rim = opts.show_rim !== false;
  }
  // theta (radians, data) -> screen angle (radians, standard math, CCW from +x)
  PolarAxes.prototype._screenAngle = function (theta) {
    // matplotlib: offset for zero location, then direction.
    // zero "N" => 0 deg at top (+y); "S" => 0 at bottom (-y).
    // We compute the on-screen angle measured CCW from +x axis (page coords with
    // y up). For drawing we convert to fractions with cx,cy and radius scaling.
    let base = (this.zeroLoc === "N") ? Math.PI / 2 : -Math.PI / 2;
    return base + this.dir * theta;
  };
  // map (theta, r) -> [xf, yf] in figure fractions (y up)
  PolarAxes.prototype.pt = function (theta, r) {
    const a = this._screenAngle(theta);
    const rr = (r / this.rmax) * (this.wf / 2);    // x-fraction radius
    const rry = (r / this.rmax) * (this.hf / 2);   // y-fraction radius
    return [this.cx + rr * Math.cos(a), this.cy + rry * Math.sin(a)];
  };
  // polyline in (theta,r) data space
  PolarAxes.prototype.plot = function (thetas, rs, color, lw, dash, cap) {
    const pts = [];
    for (let i = 0; i < thetas.length; i++) pts.push(this.pt(thetas[i], rs[i]));
    this.surf.line(pts, color, lw, dash, cap);
  };
  PolarAxes.prototype.textAt = function (theta, r, s, opt) {
    const p = this.pt(theta, r);
    this.surf.text(s, p[0], p[1], opt);
  };
  PolarAxes.prototype.markerAt = function (theta, r, kind, sizePt, color, mewPt) {
    const p = this.pt(theta, r);
    this.surf.marker(p[0], p[1], kind, sizePt, color, mewPt);
  };
  // full circle at radius r
  PolarAxes.prototype.ring = function (r, color, lw, dash, step) {
    step = step || 2;
    const th = [], rr = [];
    for (let a = 0; a <= 360; a += step) { th.push(a * DEG); rr.push(r); }
    this.plot(th, rr, color, lw, dash);
  };
  PolarAxes.prototype.drawRim = function () {
    if (this.show_rim) this.ring(this.rmax, "#000000", 0.8, null, 1);
  };

  // helper: range of values
  function range(a, b, step) {
    step = step || 1;
    const out = [];
    if (step > 0) for (let v = a; v < b; v += step) out.push(v);
    else for (let v = a; v > b; v += step) out.push(v);
    return out;
  }

  global.OSCARLOCATOR = {
    Projection, PolarAxes,
    PAGE: function () { return [PAGE_W_IN, PAGE_H_IN]; },
    setPage: function (w, h) { PAGE_W_IN = w; PAGE_H_IN = h; },
    consts: {
      PLOT_DIAMETER_IN, MAP_RADIUS_DEG, LW_GRID, LW_RING, LW_SPOKE, LW_COAST,
      LW_TRACK, LW_FOOT, LW_INDICATOR, FS_TITLE, FS_SUBTITLE, FS_CARDINAL,
      FS_AZLABEL, FS_RINGLABEL, FS_TICKLABEL, FS_NOTE, FS_BIGLABEL, MARK_CROSS,
      MEW_CROSS, TEXT_W, POLAR_RANGE_CIRCLE_INFLATION,
    },
    helpers: { wrap_to_width, fit_sat_name, draw_title, draw_footer,
      draw_branding, range },
  };
})(window);
