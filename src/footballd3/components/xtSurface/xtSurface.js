/**
 * xtSurface.js — xT (Expected Threat) grid surface overlay for a pitch.
 *
 * Composes on pitch.js: receives an existing pitch object and renders Karun Singh's
 * published xT grid as a colored heatmap layer beneath the pitch markings. Does not
 * create or re-render the pitch.
 *
 * Each of the 96 grid cells (8 rows x 12 cols) is drawn as a rect. Fill color encodes
 * the cell's xT value on a sequential scale from neutral (#E5E5E5) at low threat to
 * the focal accent (#9F1239) at high threat. Hovering a cell shows a tooltip with the
 * xT value (as a percentage) and the grid zone. The surface group sits between the
 * pitch background rects and the pitch markings so field lines render on top.
 *
 * Grid provenance: Karun Singh's open_xt_12x8_v1, trained on his own match corpus —
 * NOT StatsBomb data and NOT Euro 2024. Values are directionally meaningful but not
 * calibrated to Euro 2024. See README.md for the full provenance disclosure.
 *
 * Works with both "horizontal" and "vertical" pitch orientations — coordinate mapping
 * is delegated entirely to pitch.px() which is orientation-aware.
 */

const _COLOR_LOW  = "#E5E5E5";  // neutral — matches project structure token
const _COLOR_HIGH = "#9F1239";  // focal accent

const _tooltip = document.createElement("div");
Object.assign(_tooltip.style, {
  position:      "fixed",
  pointerEvents: "none",
  display:       "none",
  background:    "#FAF7F0",
  border:        "1px solid #E5E5E5",
  borderRadius:  "2px",
  padding:       "6px 10px",
  fontFamily:    "Geist Mono, monospace",
  fontSize:      "12px",
  lineHeight:    "1.6",
  color:         "#171717",
  whiteSpace:    "nowrap",
  zIndex:        "100",
});
document.body.appendChild(_tooltip);

/**
 * Render the xT grid as a colored surface on an existing pitch.
 *
 * Inserts a <g class="xt-surface"> as the first child of pitch.g, placing it behind
 * all pitch markings. Each grid cell maps to one <rect>; cell corners are computed
 * via pitch.px() so the surface is orientation-aware (horizontal / vertical).
 *
 * The color domain defaults to [0, gridMax] where gridMax is the maximum value in the
 * grid (typically ~0.257, the central attacking zone). Pass minValue / maxValue to
 * override — useful for comparing multiple matches on the same scale.
 *
 * @param {Object} pitch         - Return value of createPitch(). Must expose { g, px }.
 * @param {Object} data          - Parsed xt_grid.json contract.
 * @param {number} data.rows     - Number of grid rows (Y direction).
 * @param {number} data.cols     - Number of grid columns (X direction).
 * @param {Array}  data.values   - 2-D array: values[row][col] = xT probability.
 * @param {Object} data.cell_dims - { width_yards, height_yards } per cell.
 * @param {Object} [config={}]   - Rendering options.
 * @param {function} [config.colorScale] - Custom d3 sequential scale mapping [0,1] → color.
 *   Defaults to d3.interpolateRgb(_COLOR_LOW, _COLOR_HIGH) over [minValue, maxValue].
 * @param {number}   [config.opacity=0.7]    - Overall fill opacity for the surface group [0,1].
 * @param {number}   [config.minValue]       - Domain minimum for color scale. Defaults to 0.
 * @param {number}   [config.maxValue]       - Domain maximum for color scale. Defaults to
 *   the grid's own maximum value.
 * @returns {{ g: d3.Selection, update: function }}
 *   g:      D3 selection of the <g class="xt-surface"> group (inside pitch.g).
 *   update: function({ opacity?, colorScale? }) — re-styles cells without re-appending.
 *           Accepts the same keys as config.
 */
export function createXtSurface(pitch, data, config = {}) {
  const { g, px } = pitch;

  const gridMax = data.values.reduce(
    (m, row) => Math.max(m, ...row), 0
  );

  let _opacity    = config.opacity ?? 0.7;
  let _colorScale = config.colorScale ?? d3.scaleSequential()
    .domain([config.minValue ?? 0, config.maxValue ?? gridMax])
    .interpolator(d3.interpolateRgb(_COLOR_LOW, _COLOR_HIGH));

  const cellW = data.cell_dims.width_yards;
  const cellH = data.cell_dims.height_yards;

  // Insert after the two opaque background rects (children[0]=canvas, children[1]=pitch
  // surface) and before any pitch markings (children[2+]). The ":first-child" selector
  // lands behind both opaque rects and is invisible; children[2] is the first marking.
  const surfaceG = g.insert("g", function() { return this.children[2] || null; })
    .attr("class", "xt-surface");
  surfaceG.attr("opacity", _opacity);

  _drawCells(surfaceG, data, px, cellW, cellH, _colorScale);

  /**
   * Re-style the surface with updated opacity or color scale.
   *
   * Does not re-append cells — only updates fill and group opacity in place.
   * Call this after changing the color scale domain or toggling opacity.
   *
   * @param {Object} [opts={}]
   * @param {number}   [opts.opacity]     - New fill opacity [0,1].
   * @param {function} [opts.colorScale]  - New d3 sequential scale.
   */
  function update(opts = {}) {
    if (opts.opacity    !== undefined) _opacity    = opts.opacity;
    if (opts.colorScale !== undefined) _colorScale = opts.colorScale;

    surfaceG.attr("opacity", _opacity);
    surfaceG.selectAll("rect.xt-cell")
      .attr("fill", d => _colorScale(d));
  }

  return { g: surfaceG, update };
}

/**
 * Render one <rect> per grid cell into surfaceG.
 *
 * Cell position is computed from StatsBomb yard coordinates via pitch.px(). Using two
 * corner calls (top-left and bottom-right) and taking Math.min / Math.abs handles
 * both horizontal and vertical orientations without branching on config.
 *
 * @param {d3.Selection} surfaceG   - Group to append rects into.
 * @param {Object}       data       - Parsed xt_grid.json.
 * @param {function}     px         - pitch.px(sbX, sbY) -> [screenX, screenY].
 * @param {number}       cellW      - Cell width in StatsBomb yards.
 * @param {number}       cellH      - Cell height in StatsBomb yards.
 * @param {function}     colorScale - d3 scale mapping xT value -> fill color.
 */
function _drawCells(surfaceG, data, px, cellW, cellH, colorScale) {
  const cells = [];
  for (let row = 0; row < data.rows; row++) {
    for (let col = 0; col < data.cols; col++) {
      cells.push({ row, col, value: data.values[row][col] });
    }
  }

  surfaceG.selectAll("rect.xt-cell")
    .data(cells, d => `${d.row}-${d.col}`)
    .join("rect")
    .attr("class", "xt-cell")
    .attr("x", d => {
      const [ax] = px(d.col * cellW, d.row * cellH);
      const [bx] = px((d.col + 1) * cellW, (d.row + 1) * cellH);
      return Math.min(ax, bx);
    })
    .attr("y", d => {
      const [, ay] = px(d.col * cellW, d.row * cellH);
      const [, by] = px((d.col + 1) * cellW, (d.row + 1) * cellH);
      return Math.min(ay, by);
    })
    .attr("width", d => {
      const [ax] = px(d.col * cellW, d.row * cellH);
      const [bx] = px((d.col + 1) * cellW, (d.row + 1) * cellH);
      return Math.abs(bx - ax);
    })
    .attr("height", d => {
      const [, ay] = px(d.col * cellW, d.row * cellH);
      const [, by] = px((d.col + 1) * cellW, (d.row + 1) * cellH);
      return Math.abs(by - ay);
    })
    .attr("fill", d => colorScale(d.value))
    .attr("stroke", "none")
    .style("cursor", "crosshair")
    .on("mouseover", function(event, d) {
      _tooltip.innerHTML =
        `xT&nbsp;<span style="font-weight:600">${(d.value * 100).toFixed(2)}%</span>` +
        `<br><span style="color:#525252">zone&nbsp;[${d.row},&nbsp;${d.col}]</span>`;
      _tooltip.style.display = "block";
    })
    .on("mousemove", function(event) {
      _tooltip.style.left = (event.clientX + 14) + "px";
      _tooltip.style.top  = (event.clientY - 28) + "px";
    })
    .on("mouseout", function() {
      _tooltip.style.display = "none";
    });
}
