# footballd3 — component gallery

Local test harness for the footballd3 component library. Open the gallery in a browser, edit a component file, refresh.

## Running

From the repo root:

```bash
python -m http.server 8000
```

Then open: `http://localhost:8000/footballd3/index.html`

The server is required because ES modules don't load over `file://`.

## Structure

```
footballd3/
  index.html      ← gallery harness
  pitch.js        ← component
  README.md       ← this file
style/
  style.css       ← signature design tokens (CSS variables, Google Fonts)
sample_data/
  sample_corners.json  ← synthetic fixture for harness testing
```

## Adding a new component

1. Create `footballd3/<componentName>.js`. Export a function that takes a D3 selection (or the object returned by `createPitch()`) plus a config object.
2. Open `index.html` and copy the placeholder section block (the one labeled "PLACEHOLDER PATTERN"). Replace its contents with variants of the new component.
3. Import the new module at the bottom of `index.html`: `import { yourFn } from "./yourComponent.js";`
4. Render variants into the section's SVG elements.

## Notes

- Sample data in `sample_data/` is synthetic. Real component testing uses StatsBomb data exported from notebooks as JSON snapshots.
- The harness is for component development, not publication. Publication stack (Quarto / Astro / Observable) is deferred until the first analysis is substantively complete.