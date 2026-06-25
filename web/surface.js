// surface.js — a thin drawing abstraction so the same OSCARLOCATOR drawing code
// renders both to an on-screen <canvas> (preview) and to a jsPDF document
// (vector PDF download). Plus a PolarAxes that mirrors matplotlib's polar
// projection (configurable theta zero-location and direction) so the ported
// sheets register exactly like the desktop output.
//
// Coordinate model: everything is laid out in PAGE FRACTIONS (0..1, origin
// top-left, y increasing downward in screen terms) exactly as matplotlib's
// figure fractions, then mapped to device units. matplotlib figure fractions
// have y increasing UPWARD, so the surface flips y for us: a caller-supplied
// y_frac is the matplotlib fraction (0 = bottom, 1 = top).

(function (global) {
  "use strict";

  // ---------- Canvas surface ----------
  function CanvasSurface(ctx, wPx, hPx) {
    this.ctx = ctx;
    this.w = wPx;
    this.h = hPx;
  }
  CanvasSurface.prototype.fx = function (xf) { return xf * this.w; };
  CanvasSurface.prototype.fy = function (yf) { return (1 - yf) * this.h; };
  // length fractions: x-fraction*width, y-fraction*height
  CanvasSurface.prototype.line = function (pts, color, lwPt, dash, cap) {
    const c = this.ctx;
    c.save();
    c.beginPath();
    c.strokeStyle = color;
    // hairline floor: match matplotlib's heavier rendering of thin strokes so
    // the 0.5 pt rim ticks read as dark as on the desktop (geometry unchanged).
    c.lineWidth = Math.max(lwPt, 0.85) * this.ptPx;
    c.lineCap = cap || "butt";
    c.lineJoin = "round";
    if (dash && dash.length) c.setLineDash(dash.map(d => d * this.ptPx));
    else c.setLineDash([]);
    for (let i = 0; i < pts.length; i++) {
      const x = this.fx(pts[i][0]), y = this.fy(pts[i][1]);
      if (i === 0) c.moveTo(x, y); else c.lineTo(x, y);
    }
    c.stroke();
    c.restore();
  };
  CanvasSurface.prototype.text = function (s, xf, yf, opt) {
    opt = opt || {};
    const c = this.ctx;
    c.save();
    const fsPx = (opt.fs || 9) * this.ptPx;
    const weight = opt.bold ? "bold " : "";
    c.font = weight + fsPx + "px " + (opt.mono ? "monospace" : "sans-serif");
    c.fillStyle = opt.color || "#000000";
    c.textAlign = opt.ha || "center";
    c.textBaseline = ({ top: "top", bottom: "alphabetic",
                        center: "middle", baseline: "alphabetic" })[opt.va || "center"];
    const x = this.fx(xf), y = this.fy(yf);
    const lines = String(s).split("\n");
    const lh = fsPx * (opt.linespacing || 1.2);
    let y0 = y;
    if (lines.length > 1) {
      if ((opt.va || "center") === "center") y0 = y - lh * (lines.length - 1) / 2;
      else if ((opt.va || "center") === "bottom") y0 = y - lh * (lines.length - 1);
    }
    if (opt.bbox) {
      const pad = (opt.bbox.pad || 0.1) * fsPx + 2;
      let maxw = 0;
      for (const ln of lines) maxw = Math.max(maxw, c.measureText(ln).width);
      const totalh = lh * (lines.length - 1) + fsPx;
      let bx = x - maxw / 2 - pad;
      let by = y0 - fsPx * 0.8 - pad;
      if ((opt.va || "center") === "center") by = y - totalh / 2 - pad + fsPx * 0.1;
      c.fillStyle = opt.bbox.fc || "#ffffff";
      c.globalAlpha = opt.bbox.alpha === undefined ? 1 : opt.bbox.alpha;
      const rw = maxw + 2 * pad, rh = totalh + 2 * pad;
      roundRect(c, bx, by, rw, rh, Math.min(6, fsPx * 0.3));
      c.fill();
      if (opt.bbox.ec && opt.bbox.ec !== "none") {
        c.globalAlpha = 1;
        c.strokeStyle = opt.bbox.ec;
        c.lineWidth = (opt.bbox.lw || 1) * this.ptPx;
        roundRect(c, bx, by, rw, rh, Math.min(6, fsPx * 0.3));
        c.stroke();
      }
      c.globalAlpha = 1;
      c.fillStyle = opt.color || "#000000";
    }
    for (let i = 0; i < lines.length; i++) {
      c.fillText(lines[i], x, y0 + i * lh);
    }
    c.restore();
  };
  CanvasSurface.prototype.measureText = function (s, fs, bold, mono) {
    const c = this.ctx;
    c.save();
    c.font = (bold ? "bold " : "") + (fs * this.ptPx) + "px " +
             (mono ? "monospace" : "sans-serif");
    const w = c.measureText(s).width / this.ptPx;   // back to points
    c.restore();
    return w;
  };
  CanvasSurface.prototype.marker = function (xf, yf, kind, sizePt, color, mewPt) {
    const c = this.ctx;
    c.save();
    const x = this.fx(xf), y = this.fy(yf);
    const s = sizePt * this.ptPx * 0.5;
    c.strokeStyle = color;
    c.fillStyle = color;
    c.lineWidth = (mewPt || 1) * this.ptPx;
    c.lineCap = "butt";
    if (kind === "+") {
      c.beginPath();
      c.moveTo(x - s, y); c.lineTo(x + s, y);
      c.moveTo(x, y - s); c.lineTo(x, y + s);
      c.stroke();
    } else if (kind === "*") {
      c.beginPath();
      for (let k = 0; k < 5; k++) {
        const a1 = -Math.PI / 2 + k * 2 * Math.PI / 5;
        const a2 = a1 + Math.PI / 5;
        c.moveTo(x + s * Math.cos(a1), y + s * Math.sin(a1));
        c.lineTo(x + s * 0.45 * Math.cos(a2), y + s * 0.45 * Math.sin(a2));
        c.lineTo(x, y);
      }
      c.fill();
    }
    c.restore();
  };
  // arrowhead (filled triangle) at the end of a short segment
  CanvasSurface.prototype.arrowhead = function (fromXf, toXf, color, lwPt) {
    const c = this.ctx;
    const x1 = this.fx(fromXf[0]), y1 = this.fy(fromXf[1]);
    const x2 = this.fx(toXf[0]), y2 = this.fy(toXf[1]);
    const ang = Math.atan2(y2 - y1, x2 - x1);
    const len = (4.5 + lwPt * 1.4) * this.ptPx;
    const wid = (2.2 + lwPt * 0.95) * this.ptPx;
    c.save();
    c.fillStyle = color;
    c.beginPath();
    c.moveTo(x2, y2);
    c.lineTo(x2 - len * Math.cos(ang - 0.0) + wid * Math.cos(ang + Math.PI / 2),
             y2 - len * Math.sin(ang - 0.0) + wid * Math.sin(ang + Math.PI / 2));
    c.lineTo(x2 - len * Math.cos(ang) - wid * Math.cos(ang + Math.PI / 2),
             y2 - len * Math.sin(ang) - wid * Math.sin(ang + Math.PI / 2));
    c.closePath();
    c.fill();
    c.restore();
  };

  function roundRect(c, x, y, w, h, r) {
    c.beginPath();
    c.moveTo(x + r, y);
    c.arcTo(x + w, y, x + w, y + h, r);
    c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r);
    c.arcTo(x, y, x + w, y, r);
    c.closePath();
  }

  // ---------- jsPDF surface ----------
  // Maps page fractions to PDF points (72/in). y is flipped (PDF origin top-left,
  // matplotlib fraction 0=bottom).
  function PdfSurface(doc, wIn, hIn) {
    this.doc = doc;
    this.wPt = wIn * 72;
    this.hPt = hIn * 72;
  }
  PdfSurface.prototype.fx = function (xf) { return xf * this.wPt; };
  PdfSurface.prototype.fy = function (yf) { return (1 - yf) * this.hPt; };
  // matplotlib's Agg renders thin black strokes visually heavier than their
  // nominal point width (hairline snapping). jsPDF/PDF viewers do not, so very
  // thin lines (e.g. the 0.5 pt 1-degree rim ticks) come out far too light.
  // Floor the *stroke weight* to match the desktop output's visual weight; this
  // changes ink darkness only, not geometry.
  const HAIRLINE_FLOOR_PT = 0.85;
  PdfSurface.prototype.line = function (pts, color, lwPt, dash, cap) {
    const d = this.doc;
    d.setLineWidth(Math.max(lwPt, HAIRLINE_FLOOR_PT));
    d.setDrawColor(color);
    d.setLineCap(cap === "round" ? "round" : "butt");
    d.setLineJoin("round");
    if (dash && dash.length) d.setLineDashPattern(dash, 0);
    else d.setLineDashPattern([], 0);
    const xs = [];
    for (const p of pts) xs.push([this.fx(p[0]), this.fy(p[1])]);
    for (let i = 1; i < xs.length; i++) {
      d.line(xs[i - 1][0], xs[i - 1][1], xs[i][0], xs[i][1]);
    }
    d.setLineDashPattern([], 0);
  };
  PdfSurface.prototype.text = function (s, xf, yf, opt) {
    opt = opt || {};
    const d = this.doc;
    const fs = opt.fs || 9;
    d.setFont(opt.mono ? "courier" : "helvetica", opt.bold ? "bold" : "normal");
    d.setFontSize(fs);
    d.setTextColor(opt.color || "#000000");
    const x = this.fx(xf), y = this.fy(yf);
    const lines = String(s).split("\n");
    const lhPt = fs * (opt.linespacing || 1.2);
    const align = opt.ha || "center";
    // vertical anchor in PDF points
    let y0 = y;
    const va = opt.va || "center";
    if (va === "center") y0 = y - lhPt * (lines.length - 1) / 2;
    else if (va === "bottom") y0 = y - lhPt * (lines.length - 1);

    if (opt.bbox) {
      const padPt = (opt.bbox.pad || 0.1) * fs + 2;
      let maxw = 0;
      for (const ln of lines) maxw = Math.max(maxw, d.getTextWidth(ln));
      const totalh = lhPt * (lines.length - 1) + fs;
      let bx = x - maxw / 2 - padPt;
      let by;
      if (va === "center") by = y - totalh / 2 - padPt + fs * 0.30;
      else if (va === "top") by = y - padPt;
      else by = y0 - fs + (fs - lhPt) - padPt;
      const rw = maxw + 2 * padPt, rh = totalh + 2 * padPt;
      const rr = Math.min(5, fs * 0.3);
      const gs = (opt.bbox.alpha !== undefined)
        ? new d.GState({ opacity: opt.bbox.alpha }) : null;
      if (gs) d.setGState(gs);
      d.setFillColor(opt.bbox.fc || "#ffffff");
      if (opt.bbox.ec && opt.bbox.ec !== "none") {
        d.setDrawColor(opt.bbox.ec);
        d.setLineWidth(opt.bbox.lw || 1);
        d.roundedRect(bx, by, rw, rh, rr, rr, "FD");
      } else {
        d.roundedRect(bx, by, rw, rh, rr, rr, "F");
      }
      if (gs) d.setGState(new d.GState({ opacity: 1 }));
      d.setTextColor(opt.color || "#000000");
    }
    for (let i = 0; i < lines.length; i++) {
      // jsPDF text baseline default is alphabetic; pass align
      d.text(lines[i], x, y0 + i * lhPt + fs * 0.36, { align: align, baseline: "alphabetic" });
    }
  };
  PdfSurface.prototype.measureText = function (s, fs, bold, mono) {
    const d = this.doc;
    d.setFont(mono ? "courier" : "helvetica", bold ? "bold" : "normal");
    d.setFontSize(fs);
    return d.getTextWidth(s);   // already in points
  };
  PdfSurface.prototype.marker = function (xf, yf, kind, sizePt, color, mewPt) {
    const d = this.doc;
    const x = this.fx(xf), y = this.fy(yf);
    const s = sizePt * 0.5;
    if (kind === "+") {
      d.setDrawColor(color);
      d.setLineWidth(mewPt || 1);
      d.setLineCap("butt");
      d.line(x - s, y, x + s, y);
      d.line(x, y - s, x, y + s);
    } else if (kind === "*") {
      d.setFillColor(color);
      const pts = [];
      for (let k = 0; k < 5; k++) {
        const a1 = -Math.PI / 2 + k * 2 * Math.PI / 5;
        const a2 = a1 + Math.PI / 5;
        pts.push([x + s * Math.cos(a1), y + s * Math.sin(a1)]);
        pts.push([x + s * 0.45 * Math.cos(a2), y + s * 0.45 * Math.sin(a2)]);
      }
      d.lines(closedPathDeltas(pts), pts[0][0], pts[0][1], [1, 1], "F", true);
    }
  };
  PdfSurface.prototype.arrowhead = function (fromXf, toXf, color, lwPt) {
    const d = this.doc;
    const x1 = this.fx(fromXf[0]), y1 = this.fy(fromXf[1]);
    const x2 = this.fx(toXf[0]), y2 = this.fy(toXf[1]);
    const ang = Math.atan2(y2 - y1, x2 - x1);
    // match matplotlib's "-|>" head proportions at the given linewidth
    const len = 4.5 + lwPt * 1.4;
    const wid = 2.2 + lwPt * 0.95;
    const p1 = [x2, y2];
    const p2 = [x2 - len * Math.cos(ang) + wid * Math.cos(ang + Math.PI / 2),
                y2 - len * Math.sin(ang) + wid * Math.sin(ang + Math.PI / 2)];
    const p3 = [x2 - len * Math.cos(ang) - wid * Math.cos(ang + Math.PI / 2),
                y2 - len * Math.sin(ang) - wid * Math.sin(ang + Math.PI / 2)];
    d.setFillColor(color);
    d.lines(closedPathDeltas([p1, p2, p3]), p1[0], p1[1], [1, 1], "F", true);
  };
  function closedPathDeltas(pts) {
    const out = [];
    for (let i = 1; i < pts.length; i++) {
      out.push([pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]]);
    }
    return out;
  }

  global.OLSurface = { CanvasSurface, PdfSurface };
})(window);
