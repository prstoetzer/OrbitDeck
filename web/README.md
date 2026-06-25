# OSCARLOCATOR Web Generator

A browser-based generator for printable **OSCARLOCATOR** sheets — the classic
paper satellite tracker — produced as **vector PDFs entirely in your browser**.
It is a faithful port of [OrbitDeck](https://github.com/prstoetzer/OrbitDeck)'s
OSCARLOCATOR PDF export: same geometry, same layout, same coastlines, with the
credit footer reading *"OSCARLOCATOR Web Generator — Paul Stoetzer, N8HM"*.

Companion to the live [OSCARLOCATOR Simulator](https://oscarlocator.n8hm.radio/).

## What it makes

For a chosen satellite and station, the generator produces a print-ready set of
sheets, all drawn to the same angular scale so the transparency overlays
register on top of the base map:

- **Base map** (print on paper/card) — azimuthal-equidistant map centred on your
  QTH, or a pole-centred polar great-circle map.
- **Range-circle overlay** (print on transparency) — the satellite's coverage
  circle, with an azimuth rose and km distance rings.
- **Path-arc overlay** (print on transparency) — the rotatable ground-track arc
  with one-minute ticks, the EQX alignment marker, and the per-pass rotation
  indicator.

Options:

- **Map projection** — QTH-centred, polar North, polar South, or polar auto-N/S.
- **Range circle on the QTH map** — a two-sheet set with the range circle drawn
  directly at your station (no separate range-circle transparency).
- **Clean transparencies** — keep the overlay sheets free of text outside their
  circle; the base map carries all the how-to-use instructions.

Print every sheet at **100% / actual size** so the overlays register.

## How it runs

Everything runs client-side. The only network calls are:

1. **AMSAT GP elements** — fetched from AMSAT's daily bulletin. Because AMSAT's
   server does not send CORS headers, the fetch goes through the same CORS-proxy
   chain the OSCARLOCATOR Simulator uses (a small Cloudflare Worker, with public
   mirrors as fallbacks). You can override the proxy under **Advanced**, or skip
   the fetch entirely and type orbital elements by hand.
2. **Your location** — only if you press *Use my location* (browser geolocation).

No data is uploaded; the PDF is built in the browser with
[jsPDF](https://github.com/parallax/jsPDF).

Coastlines are Natural Earth 110m (the same dataset OrbitDeck uses via cartopy),
bundled in `coastlines.js`.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | UI, preview, and download controls |
| `engine.js` | Orbital math (footprint, J2 node drift, ground-track, OMM parsing) |
| `surface.js` | Drawing abstraction with canvas (preview) and jsPDF (vector) backends |
| `oscarlocator.js` | Page geometry and the matplotlib-style polar axes |
| `sheets.js` | Sheet primitives (graticule, az-grid, rim ticks, footprint overlay) |
| `pages.js` | The four page generators and the build orchestrator |
| `grid.js` | Maidenhead grid ↔ lat/lon |
| `app.js` | UI controller, AMSAT fetch chain, preview render, PDF export |
| `coastlines.js` | Natural Earth 110m coastlines |

Pure static files — no build step, no framework, no bundler.

## Deploying on GitHub Pages (subdomain of n8hm.radio)

1. Put these files at the repository root (or in `/docs`) and enable **GitHub
   Pages** in the repo settings, pointing at that branch/folder.
2. Set the custom domain to your chosen subdomain (e.g.
   `oscarlocator-pdf.n8hm.radio`). GitHub writes this into the `CNAME` file (one
   is included here as a placeholder — edit it to your actual subdomain).
3. At your DNS provider, add a **CNAME record** for the subdomain pointing to
   `<your-github-username>.github.io`.
4. Wait for DNS to propagate, then enable **Enforce HTTPS** in Pages settings.

That's it — the page is fully static and needs no server-side component.

## Local preview

Any static file server works, for example:

```sh
python3 -m http.server 8000
# then open http://localhost:8000/
```

Opening `index.html` directly via `file://` mostly works, but a few browsers
restrict `fetch`/geolocation on `file://`, so a local server is recommended.

## Fidelity

The output has been verified page-for-page against OrbitDeck's PDF export across
all projections, the combined and clean-transparency variants, and satellites
with prograde, retrograde, and southern-hemisphere geometry.

---

*OSCARLOCATOR Web Generator — Paul Stoetzer, N8HM. MIT-licensed, like OrbitDeck.*
