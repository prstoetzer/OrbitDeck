// grid.js — Maidenhead grid <-> lat/lon, ported verbatim from
// orbitdeck/engine/predict.py so the displayed grid matches the desktop app.

(function (global) {
  "use strict";
  const A = "A".charCodeAt(0), Z0 = "0".charCodeAt(0), a = "a".charCodeAt(0);

  function latlon_to_grid(lat, lon) {
    lon += 180.0; lat += 90.0;
    const g = [];
    g.push(String.fromCharCode(A + Math.trunc(lon / 20)));
    g.push(String.fromCharCode(A + Math.trunc(lat / 10)));
    g.push(String.fromCharCode(Z0 + Math.trunc((lon % 20) / 2)));
    g.push(String.fromCharCode(Z0 + Math.trunc(lat % 10)));
    g.push(String.fromCharCode(a + Math.trunc((lon % 2) * 12)));
    g.push(String.fromCharCode(a + Math.trunc((lat % 1) * 24)));
    return g.join("");
  }

  function grid_to_latlon(grid) {
    const g = (grid || "").trim().toUpperCase();
    if (g.length < 4) return null;
    let lon = (g.charCodeAt(0) - A) * 20 - 180;
    let lat = (g.charCodeAt(1) - A) * 10 - 90;
    lon += (g.charCodeAt(2) - Z0) * 2;
    lat += (g.charCodeAt(3) - Z0) * 1;
    if (g.length >= 6) {
      lon += (g.charCodeAt(4) - A) * (2.0 / 24.0) + 1.0 / 24.0;
      lat += (g.charCodeAt(5) - A) * (1.0 / 24.0) + 0.5 / 24.0;
    } else { lon += 1.0; lat += 0.5; }
    return [lat, lon];
  }

  global.OLGrid = { latlon_to_grid, grid_to_latlon };
})(window);
