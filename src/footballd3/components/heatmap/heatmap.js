// footballd3/components/heatmap/heatmap.js
//
// Renders a pre-computed KDE density surface as a colour overlay on an
// existing pitch.js instance. Python owns the KDE computation; this module
// only maps normalised grid values [0, 1] to colour and draws them.
//
// The heatmap layer is inserted UNDER the pitch markings (halfway line,
// penalty areas, etc.) so pitch lines stay visible at all densities.
//
// Usage:
//   import { createPitch }   from "../pitch/pitch.js";
//   import { createHeatmap } from "../heatmap/heatmap.js";
//   const pitch = createPitch(d3.select("#svg"), { mode: "full" });
//   const { update } = createHeatmap(pitch, data, { renderStyle: "smooth" });
//   update(newData);  // swap to a different player/match without re-drawing the pitch

/**
 * Bilinear interpolation of a normalised density value at sub-cell position.
 *
 * @param {number[][]} values - 2D grid [rows][cols] of normalised floats [0,1].
 * @param {number} cols - Number of grid columns.
 * @param {number} rows - Number of grid rows.
 * @param {number} gx   - Fractional column index (0 = left edge, cols = right edge).
 * @param {number} gy   - Fractional row index (0 = top edge, rows = bottom edge).
 * @returns {number} Interpolated density value in [0, 1].
 */
function bilinear(values, cols, rows, gx, gy) {
  const col0 = Math.max(0, Math.min(cols - 1, Math.floor(gx)));
  const row0 = Math.max(0, Math.min(rows - 1, Math.floor(gy)));
  const col1 = Math.min(cols - 1, col0 + 1);
  const row1 = Math.min(rows - 1, row0 + 1);
  const tx = gx - col0;
  const ty = gy - row0;
  const v00 = values[row0][col0];
  const v10 = values[row0][col1];
  const v01 = values[row1][col0];
  const v11 = values[row1][col1];
  return (v00 * (1 - tx) + v10 * tx) * (1 - ty) + (v01 * (1 - tx) + v11 * tx) * ty;
}

/**
 * Parse a CSS hex color string into [r, g, b] components (0–255 each).
 *
 * @param {string} hex - Six-digit hex color, e.g. "#9F1239".
 * @returns {[number, number, number]} RGB components.
 */
function hexToRgb(hex) {
  const h = hex.replace("#", "");
  return [
    parseInt(h.substring(0, 2), 16),
    parseInt(h.substring(2, 4), 16),
    parseInt(h.substring(4, 6), 16),
  ];
}

/**
 * Creates a KDE heatmap overlay on an existing pitch.
 *
 * Renders a pre-computed density grid — produced by the Python KDE extractor —
 * as a colour surface under the pitch markings. Python computed the surface;
 * this component only maps grid values to pixels.
 *
 * Two render styles are supported via config.renderStyle:
 *   "smooth" (default) — draws to an off-screen canvas with bilinear
 *     interpolation between grid cells, then embeds the result as an SVG
 *     <image>. Produces a continuous-looking surface with no grid seams.
 *   "raster" — appends one SVG <rect> per grid cell. Simple and fast; cell
 *     boundaries are faintly visible at low resolutions.
 *
 * The heatmap layer is inserted before the third child of pitch.g (i.e. after
 * the two background rects but before all pitch markings) so lines stay on top.
 *
 * @param {Object} pitch - Return value of createPitch(): { svg, g, px, width, height, config }.
 * @param {Object} data  - Parsed heatmap JSON: { grid: { cols, rows, values }, metadata }.
 * @param {Object} [config] - Optional visual configuration.
 * @param {string}  [config.renderStyle="smooth"] - "smooth" or "raster".
 * @param {string}  [config.colorLow="#FAF7F0"]   - Color at zero density.
 *   Should match the pitch background so empty zones are transparent.
 * @param {string}  [config.colorHigh="#9F1239"]  - Color at peak density.
 * @param {number}  [config.maxOpacity=0.85]      - Opacity at peak density.
 *   Faint zones approach zero opacity so pitch lines always remain legible.
 * @returns {{ g: d3.Selection, px: Function, update: Function }}
 *   g is pitch.g. update(newData) swaps the density surface to new grid data
 *   without re-rendering the pitch.
 */
export function createHeatmap(pitch, data, config = {}) {
  const {
    renderStyle = "smooth",
    colorLow    = "#FAF7F0",
    colorHigh   = "#9F1239",
    maxOpacity  = 0.85,
  } = config;

  const { g, px, width, height, config: pitchConfig } = pitch;
  const { padding, pxPerYard } = pitchConfig;

  // Insert the heatmap group before the third child of pitch.g so it renders
  // under pitch lines (which are children 3+ of g).
  const hmGroup = g.insert("g", ":nth-child(3)").attr("class", "hm");

  function renderGrid(gridData) {
    hmGroup.selectAll("*").remove();

    const { cols, rows, values } = gridData;

    if (renderStyle === "smooth") {
      _renderSmooth(hmGroup, values, cols, rows, px, padding, pxPerYard, colorLow, colorHigh, maxOpacity);
    } else {
      _renderRaster(hmGroup, values, cols, rows, px, colorLow, colorHigh, maxOpacity);
    }
  }

  renderGrid(data.grid);

  /**
   * Swap the density surface to new grid data without re-rendering the pitch.
   *
   * Clears the existing heatmap layer and draws from the new grid immediately.
   * Intended for switching between players or matches in the same pitch instance.
   *
   * @param {Object} newData - New heatmap JSON in the same shape as the original
   *   data argument: { grid: { cols, rows, values }, metadata }.
   */
  function update(newData) {
    renderGrid(newData.grid);
  }

  return { g, px, update };
}

/**
 * Render the density grid as a bilinearly-interpolated canvas image.
 *
 * Each output pixel samples the grid with bilinear interpolation between the
 * four nearest cell centres, producing a smooth surface with no visible seams.
 * The canvas is sized to cover the inner pitch area (excluding padding) so it
 * aligns with the pitch coordinate space.
 *
 * @param {d3.Selection} group     - SVG group to append the <image> into.
 * @param {number[][]}   values    - [rows][cols] normalised density values.
 * @param {number}       cols      - Grid column count.
 * @param {number}       rows      - Grid row count.
 * @param {Function}     px        - createPitch px() converting SB yards → [screenX, screenY].
 * @param {number}       padding   - Pitch padding in pixels (from pitchConfig).
 * @param {number}       pxPerYard - Pixels per yard (from pitchConfig).
 * @param {string}       colorLow  - Zero-density CSS hex color.
 * @param {string}       colorHigh - Peak-density CSS hex color.
 * @param {number}       maxOpacity - Opacity multiplier at peak density.
 */
function _renderSmooth(group, values, cols, rows, px, padding, pxPerYard, colorLow, colorHigh, maxOpacity) {
  // Determine the pixel bounds of the inner pitch area via px().
  const [x0px, y0px] = px(0, 0);
  const [x1px, y1px] = px(120, 80);
  const leftPx   = Math.min(x0px, x1px);
  const topPx    = Math.min(y0px, y1px);
  const innerW   = Math.abs(x1px - x0px);
  const innerH   = Math.abs(y1px - y0px);

  const canvasW = Math.round(innerW);
  const canvasH = Math.round(innerH);

  const canvas = document.createElement("canvas");
  canvas.width  = canvasW;
  canvas.height = canvasH;
  const ctx = canvas.getContext("2d");

  const imgData = ctx.createImageData(canvasW, canvasH);
  const buf = imgData.data;

  const [rL, gL, bL] = hexToRgb(colorLow);
  const [rH, gH, bH] = hexToRgb(colorHigh);

  for (let py = 0; py < canvasH; py++) {
    for (let px_ = 0; px_ < canvasW; px_++) {
      // Map canvas pixel to fractional grid position (cell-centre space).
      const gx = (px_ / canvasW) * cols;
      const gy = (py / canvasH) * rows;
      const v = bilinear(values, cols, rows, gx, gy);

      const r = Math.round(rL + (rH - rL) * v);
      const g = Math.round(gL + (gH - gL) * v);
      const b = Math.round(bL + (bH - bL) * v);
      const a = Math.round(v * maxOpacity * 255);

      const idx = (py * canvasW + px_) * 4;
      buf[idx]     = r;
      buf[idx + 1] = g;
      buf[idx + 2] = b;
      buf[idx + 3] = a;
    }
  }

  ctx.putImageData(imgData, 0, 0);

  const dataURL = canvas.toDataURL("image/png");
  group.append("image")
    .attr("class", "hm-surface")
    .attr("x", leftPx)
    .attr("y", topPx)
    .attr("width",  innerW)
    .attr("height", innerH)
    .attr("preserveAspectRatio", "none")
    .attr("href", dataURL);
}

/**
 * Render the density grid as individual SVG <rect> elements (one per cell).
 *
 * Each rect maps a single grid cell to its pitch-space bounding box via px().
 * Cells with near-zero density are skipped for performance.
 *
 * @param {d3.Selection} group      - SVG group to append rects into.
 * @param {number[][]}   values     - [rows][cols] normalised density values.
 * @param {number}       cols       - Grid column count.
 * @param {number}       rows       - Grid row count.
 * @param {Function}     px         - createPitch px() function.
 * @param {string}       colorLow   - Zero-density CSS hex color.
 * @param {string}       colorHigh  - Peak-density CSS hex color.
 * @param {number}       maxOpacity - Opacity at peak density.
 */
function _renderRaster(group, values, cols, rows, px, colorLow, colorHigh, maxOpacity) {
  const cellW = 120 / cols;
  const cellH = 80  / rows;
  const color = d3.interpolateRgb(colorLow, colorHigh);

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const v = values[row][col];
      if (v < 0.005) continue;

      const [x0, y0] = px(col * cellW,        row * cellH);
      const [x1, y1] = px((col + 1) * cellW, (row + 1) * cellH);

      group.append("rect")
        .attr("class", "hm-cell")
        .attr("x",      Math.min(x0, x1))
        .attr("y",      Math.min(y0, y1))
        .attr("width",  Math.abs(x1 - x0))
        .attr("height", Math.abs(y1 - y0))
        .attr("fill",   color(v))
        .attr("opacity", v * maxOpacity);
    }
  }
}
