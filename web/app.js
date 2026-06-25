// app.js — UI controller for the OSCARLOCATOR Web Generator. Wires the controls
// to the ported sheet generators, fetches AMSAT GP elements through the same
// CORS-proxy chain the OSCARLOCATOR Simulator uses, renders a live canvas
// preview, and exports a vector PDF with jsPDF — all in the browser.

(function () {
  "use strict";

  const E = window.OLEngine;
  const Pages = window.OLPages;
  const Surf = window.OLSurface;
  const OL = window.OSCARLOCATOR;
  const Grid = window.OLGrid;
  const { jsPDF } = window.jspdf;

  // The Simulator's self-hosted CORS proxy is tried first, then public mirrors,
  // then a direct attempt (works only if AMSAT ever sends CORS headers).
  const AMSAT_GP_URL = "https://newark192.amsat.org/gpdata/current/daily-bulletin.json";
  const DEFAULT_PROXY = "https://oscarlocator-pwa.prstoetzer.workers.dev/";

  const COASTLINES = window.COASTLINES_110M || [];

  const $ = id => document.getElementById(id);
  const state = {
    sats: [],          // parsed SatEntry-like objects
    sat: null,         // currently selected
    obs: { lat: 38.82, lon: -77.08 },
    page: 0,
    pageDefs: null,    // {pages:[fn], meta}
  };

  // ---------------- status helpers ----------------
  function status(msg, kind, busy) {
    const el = $("status");
    el.className = kind || "";
    el.innerHTML = (busy ? '<span class="spinner"></span>' : "") + (msg || "&nbsp;");
  }

  // ---------------- AMSAT fetch chain ----------------
  function parseFlexible(text) {
    // accept a raw JSON array, or an allorigins {contents:"..."} wrapper
    let t = text;
    try {
      const j = JSON.parse(text);
      if (j && typeof j === "object" && !Array.isArray(j) && typeof j.contents === "string") {
        t = j.contents;
      }
    } catch (e) { /* not wrapped */ }
    return E.parse_gp_json(t);
  }

  async function fetchText(url, ms) {
    const ctl = new AbortController();
    const to = setTimeout(() => ctl.abort(), ms || 15000);
    try {
      const r = await fetch(url, { signal: ctl.signal });
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.text();
    } finally { clearTimeout(to); }
  }

  function proxyChain() {
    const enc = encodeURIComponent(AMSAT_GP_URL);
    const userProxy = ($("proxy").value || DEFAULT_PROXY).trim();
    const list = [];
    if (userProxy) {
      const base = userProxy.replace(/\/$/, "");
      const joiner = base.indexOf("?") >= 0 ? "&" : "?";
      list.push({ name: "proxy", url: base, tries: 2 });
      list.push({ name: "proxy(?url=)", url: base + joiner + "url=" + enc, tries: 2 });
    }
    list.push({ name: "allorigins/get", url: "https://api.allorigins.win/get?url=" + enc, tries: 3 });
    list.push({ name: "allorigins/raw", url: "https://api.allorigins.win/raw?url=" + enc, tries: 3 });
    list.push({ name: "direct", url: AMSAT_GP_URL, tries: 1 });
    return list;
  }

  async function loadAmsat() {
    status("Fetching AMSAT elements\u2026", "", true);
    const chain = proxyChain();
    for (const step of chain) {
      for (let t = 0; t < step.tries; t++) {
        try {
          const text = await fetchText(step.url, 15000);
          const sats = parseFlexible(text);
          if (sats && sats.length) {
            state.sats = sats.sort((x, y) => x.name.localeCompare(y.name));
            populatePicker();
            status("Loaded " + sats.length + " satellites (" + step.name + ").", "ok");
            return true;
          }
        } catch (e) { /* try next */ }
      }
    }
    status("Couldn't reach AMSAT. Enter elements manually under Advanced, or set a proxy.", "err");
    return false;
  }

  function populatePicker() {
    const sel = $("satpick");
    const prev = state.sat ? state.sat.norad : null;
    sel.innerHTML = "";
    for (const s of state.sats) {
      const o = document.createElement("option");
      o.value = String(s.norad);
      o.textContent = s.name + "  (" + s.norad + ")";
      sel.appendChild(o);
    }
    // prefer RS-44 if present, else keep previous, else first
    let pick = state.sats.find(s => s.norad === prev) ||
               state.sats.find(s => s.norad === 44909) || state.sats[0];
    if (pick) { sel.value = String(pick.norad); selectSat(pick); }
  }

  function selectSat(s) {
    state.sat = s;
    fillManual(s);
    rebuild();
  }

  function fillManual(s) {
    $("m_incl").value = s.incl;
    $("m_mm").value = s.mean_motion;
    $("m_ecc").value = s.ecc;
    $("m_argp").value = s.argp;
    $("m_raan").value = s.raan;
    $("m_name").value = s.name;
  }

  // ---------------- station ----------------
  function syncGridFromLatLon() {
    $("grid").value = Grid.latlon_to_grid(state.obs.lat, state.obs.lon);
  }
  function readLatLon() {
    const la = parseFloat($("lat").value), lo = parseFloat($("lon").value);
    if (!isNaN(la) && !isNaN(lo)) { state.obs.lat = la; state.obs.lon = lo; return true; }
    return false;
  }
  function writeLatLon() {
    $("lat").value = state.obs.lat.toFixed(4);
    $("lon").value = state.obs.lon.toFixed(4);
  }

  // ---------------- options ----------------
  function currentProjection() {
    const r = document.querySelector('input[name="proj"]:checked');
    return r ? r.value : "polar-auto";
  }

  // ---------------- build + render ----------------
  function rebuild() {
    if (!state.sat) return;
    const opts = {
      obs: { lat: state.obs.lat, lon: state.obs.lon },
      qth_name: Grid.latlon_to_grid(state.obs.lat, state.obs.lon),
      sat: state.sat,
      when_unix: Date.now() / 1000,
      projection: currentProjection(),
      footprint_on_qth: $("combined").checked,
      reduced_text: $("reduced").checked,
      segments: COASTLINES,
    };
    state.pageDefs = Pages.buildPages(opts);
    if (state.page >= state.pageDefs.pages.length) state.page = 0;
    renderReadout();
    renderPreview();
    renderPager();
  }

  const PAGE_TITLES = {
    base: ["Base map", "Range circle (transparency)", "Path arc (transparency)"],
    combined: ["Map + range circle", "Path arc (transparency)"],
  };
  function renderPager() {
    const n = state.pageDefs.pages.length;
    $("pageno").textContent = (state.page + 1) + " / " + n;
    const titles = $("combined").checked ? PAGE_TITLES.combined : PAGE_TITLES.base;
    $("sheettitle").textContent = titles[state.page] || ("Page " + (state.page + 1));
    $("prev").disabled = state.page === 0;
    $("next").disabled = state.page === n - 1;
  }

  function renderReadout() {
    const s = state.sat;
    const sma = E.semi_major_axis_km(s.mean_motion);
    const alt = sma > 0 ? Math.max(sma - E.RE_KM, 1.0) : 0;
    const foot = E.footprint_radius_deg(alt);
    const shift = E.node_shift_deg(s);
    const cells = [
      ["Satellite", s.name],
      ["NORAD", s.norad],
      ["Inclination", s.incl.toFixed(2) + "\u00b0"],
      ["Period", s.period_min.toFixed(1) + " min"],
      ["Mean alt", Math.round(alt) + " km"],
      ["Range circle", foot.toFixed(1) + "\u00b0 (~" + Math.round(foot * E.KM_PER_DEG / 10) * 10 + " km)"],
      ["Node advance", Math.abs(shift).toFixed(1) + "\u00b0 " + (shift < 0 ? "W" : "E") + "/pass"],
    ];
    $("readout").innerHTML = cells.map(c => "<div><b>" + c[0] + ":</b> " + c[1] + "</div>").join("");
  }

  function renderPreview() {
    const cv = $("preview");
    const [wIn, hIn] = OL.PAGE();
    const scale = 100;                 // px per inch for the preview bitmap
    cv.width = Math.round(wIn * scale);
    cv.height = Math.round(hIn * scale);
    const ctx = cv.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, cv.width, cv.height);
    const surf = new Surf.CanvasSurface(ctx, cv.width, cv.height);
    surf.ptPx = scale / 72;            // points -> preview px
    state.pageDefs.pages[state.page](surf);
  }

  // ---------------- PDF export ----------------
  function exportPdf() {
    const [wIn, hIn] = OL.PAGE();
    const doc = new jsPDF({ unit: "pt", format: [wIn * 72, hIn * 72], orientation: "portrait" });
    const defs = state.pageDefs;
    for (let i = 0; i < defs.pages.length; i++) {
      if (i > 0) doc.addPage([wIn * 72, hIn * 72], "portrait");
      const surf = new Surf.PdfSurface(doc, wIn, hIn);
      defs.pages[i](surf);
    }
    doc.setProperties({
      title: defs.meta.title, subject: defs.meta.subject, creator: defs.meta.creator,
      author: "Paul Stoetzer, N8HM",
    });
    const safe = (state.sat.name || "oscarlocator").replace(/[^\w.-]+/g, "_");
    doc.save("oscarlocator_" + safe + "_" + defs.meta.projection + ".pdf");
    return doc;
  }

  function printPdf() {
    const doc = (function () {
      const [wIn, hIn] = OL.PAGE();
      const d = new jsPDF({ unit: "pt", format: [wIn * 72, hIn * 72], orientation: "portrait" });
      for (let i = 0; i < state.pageDefs.pages.length; i++) {
        if (i > 0) d.addPage([wIn * 72, hIn * 72], "portrait");
        state.pageDefs.pages[i](new Surf.PdfSurface(d, wIn, hIn));
      }
      return d;
    })();
    doc.autoPrint();
    window.open(doc.output("bloburl"), "_blank");
  }

  // ---------------- events ----------------
  function bind() {
    $("satpick").addEventListener("change", e => {
      const s = state.sats.find(x => String(x.norad) === e.target.value);
      if (s) selectSat(s);
    });
    $("refresh").addEventListener("click", loadAmsat);

    $("geo").addEventListener("click", () => {
      if (!navigator.geolocation) { status("Geolocation not available.", "err"); return; }
      status("Locating\u2026", "", true);
      navigator.geolocation.getCurrentPosition(p => {
        state.obs.lat = p.coords.latitude; state.obs.lon = p.coords.longitude;
        writeLatLon(); syncGridFromLatLon(); status("Location set.", "ok"); rebuild();
      }, err => status("Location denied or unavailable.", "err"));
    });
    $("fromgrid").addEventListener("click", () => {
      const ll = Grid.grid_to_latlon($("grid").value);
      if (ll) { state.obs.lat = ll[0]; state.obs.lon = ll[1]; writeLatLon(); rebuild(); }
      else status("Enter at least a 4-character grid.", "err");
    });
    $("togrid").addEventListener("click", () => {
      if (readLatLon()) { syncGridFromLatLon(); rebuild(); }
      else status("Enter a numeric latitude and longitude.", "err");
    });
    $("lat").addEventListener("change", () => { if (readLatLon()) { syncGridFromLatLon(); rebuild(); } });
    $("lon").addEventListener("change", () => { if (readLatLon()) { syncGridFromLatLon(); rebuild(); } });
    $("grid").addEventListener("change", () => {
      const ll = Grid.grid_to_latlon($("grid").value);
      if (ll) { state.obs.lat = ll[0]; state.obs.lon = ll[1]; writeLatLon(); rebuild(); }
    });

    document.querySelectorAll('input[name="proj"]').forEach(r =>
      r.addEventListener("change", () => { state.page = 0; rebuild(); }));
    $("combined").addEventListener("change", () => { state.page = 0; rebuild(); });
    $("reduced").addEventListener("change", rebuild);

    $("prev").addEventListener("click", () => { if (state.page > 0) { state.page--; renderPreview(); renderPager(); } });
    $("next").addEventListener("click", () => {
      if (state.page < state.pageDefs.pages.length - 1) { state.page++; renderPreview(); renderPager(); }
    });

    $("download").addEventListener("click", exportPdf);
    $("print").addEventListener("click", printPdf);

    $("applyman").addEventListener("click", () => {
      const s = {
        name: $("m_name").value.trim() || "MANUAL",
        norad: state.sat ? state.sat.norad : 0,
        incl: parseFloat($("m_incl").value) || 0,
        mean_motion: parseFloat($("m_mm").value) || 0,
        ecc: parseFloat($("m_ecc").value) || 0,
        argp: parseFloat($("m_argp").value) || 0,
        raan: parseFloat($("m_raan").value) || 0,
      };
      s.period_min = E.period_min(s.mean_motion);
      if (s.mean_motion <= 0) { status("Mean motion must be > 0.", "err"); return; }
      state.sat = s; rebuild(); status("Using manual elements.", "ok");
    });
  }

  // ---------------- init ----------------
  function init() {
    writeLatLon();
    syncGridFromLatLon();
    bind();
    loadAmsat();
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else init();
})();
