/**
 * @module comparisonBars
 *
 * Generic mirrored opposed-bar chart. Two named sides (left vs right) are rendered
 * as a stacked list of rows, each with its own scale type and number format.
 *
 * Contains no domain knowledge. "Left" and "right" are opaque identity objects.
 * Row labels, values, and scale semantics come entirely from the caller.
 *
 * scaleType WARNING: using the wrong scaleType misrepresents the visual gap.
 * A "sum" row where one side is 0 fills the entire half-width for the other side,
 * correctly showing 100% share — but if the true maximum is an external reference,
 * use "max" instead to avoid implying 100% share of a fixed total.
 */

const DEFAULTS = {
  width:        480,
  rowHeight:    40,
  barHeight:    14,
  labelWidth:   130,
  headerHeight: 32,
  paddingY:     10,
  showHeader:   true,
};

// Pixels reserved at the inner edge (axis side) of each bar zone for value text.
const VAL_RESERVE = 44;
// Gap between label-zone edge and value text.
const VAL_PAD = 6;

/**
 * Format a numeric value according to the row format specifier.
 *
 * @param {number} v - The value to format.
 * @param {"int"|"pct"|"float1"} fmt - Format specifier.
 * @returns {string} Formatted string.
 */
function formatValue(v, fmt) {
  if (fmt === "pct")    return `${v.toFixed(1)}%`;
  if (fmt === "float1") return v.toFixed(1);
  return String(Math.round(v));
}

/**
 * Compute pixel bar width for one value given the row's scale type.
 *
 * @param {number} value - The side's numeric value.
 * @param {Object} row - Full row object (needs leftValue, rightValue, scaleType, maxValue).
 * @param {number} maxBarW - Maximum available bar width in pixels.
 * @returns {number} Bar width in pixels, clamped to [0, maxBarW].
 * @throws {Error} When scaleType is "max" and row.maxValue is missing or zero.
 */
function computeBarW(value, row, maxBarW) {
  let ratio = 0;
  if (row.scaleType === "sum") {
    const total = row.leftValue + row.rightValue;
    ratio = total === 0 ? 0 : value / total;
  } else if (row.scaleType === "fixed100") {
    ratio = value / 100;
  } else if (row.scaleType === "max") {
    if (!row.maxValue) {
      throw new Error(
        `comparisonBars: row "${row.label}" has scaleType "max" but no maxValue`
      );
    }
    ratio = value / row.maxValue;
  }
  return Math.max(0, Math.min(maxBarW, ratio * maxBarW));
}

/**
 * Draw all data rows into the given <g> element.
 *
 * @param {d3.Selection} rowsG - The <g class="cb-rows"> element to populate.
 * @param {Object} data - Chart data object (same shape as createComparisonBars data param).
 * @param {Object} cfg - Resolved config object.
 * @param {number} halfW - Total width of each half (bar zone + value reserve).
 * @param {number} maxBarW - Usable bar pixels per side.
 */
function drawRows(rowsG, data, cfg, halfW, maxBarW) {
  rowsG.selectAll("*").remove();

  data.rows.forEach((row, i) => {
    const cy = cfg.paddingY + i * cfg.rowHeight + cfg.rowHeight / 2;

    const g = rowsG.append("g").attr("class", "cb-row");

    const lw = computeBarW(row.leftValue,  row, maxBarW);
    const rw = computeBarW(row.rightValue, row, maxBarW);

    // Left bar — right-aligned to the inner axis edge
    const leftBarX = halfW - VAL_PAD - VAL_RESERVE - lw;
    g.append("rect")
      .attr("class", "cb-bar cb-bar--left")
      .attr("x",      leftBarX)
      .attr("y",      cy - cfg.barHeight / 2)
      .attr("width",  lw)
      .attr("height", cfg.barHeight)
      .attr("rx",     2)
      .attr("fill",   data.left.color);

    // Right bar — left-aligned from the inner axis edge
    const rightBarX = halfW + cfg.labelWidth + VAL_PAD + VAL_RESERVE;
    g.append("rect")
      .attr("class", "cb-bar cb-bar--right")
      .attr("x",      rightBarX)
      .attr("y",      cy - cfg.barHeight / 2)
      .attr("width",  rw)
      .attr("height", cfg.barHeight)
      .attr("rx",     2)
      .attr("fill",   data.right.color);

    // Label — centered in label zone
    g.append("text")
      .attr("class",            "cb-label")
      .attr("x",                cfg.width / 2)
      .attr("y",                cy)
      .attr("text-anchor",      "middle")
      .attr("dominant-baseline","middle")
      .attr("fill",             "#525252")
      .attr("font-family",      "var(--font-mono,'Geist Mono',monospace)")
      .attr("font-size",        "11px")
      .attr("letter-spacing",   "0.02em")
      .text(row.label);

    // Left value — right-aligned just inside the bar zone
    g.append("text")
      .attr("class",            "cb-val cb-val--left")
      .attr("x",                halfW - VAL_PAD)
      .attr("y",                cy)
      .attr("text-anchor",      "end")
      .attr("dominant-baseline","middle")
      .attr("fill",             "#171717")
      .attr("font-family",      "var(--font-mono,'Geist Mono',monospace)")
      .attr("font-size",        "12px")
      .attr("font-weight",      "500")
      .text(formatValue(row.leftValue, row.format));

    // Right value — left-aligned just inside the bar zone
    g.append("text")
      .attr("class",            "cb-val cb-val--right")
      .attr("x",                halfW + cfg.labelWidth + VAL_PAD)
      .attr("y",                cy)
      .attr("text-anchor",      "start")
      .attr("dominant-baseline","middle")
      .attr("fill",             "#171717")
      .attr("font-family",      "var(--font-mono,'Geist Mono',monospace)")
      .attr("font-size",        "12px")
      .attr("font-weight",      "500")
      .text(formatValue(row.rightValue, row.format));

    // Row separator (skip on last row)
    if (i < data.rows.length - 1) {
      g.append("line")
        .attr("x1",   0)
        .attr("x2",   cfg.width)
        .attr("y1",   cy + cfg.rowHeight / 2)
        .attr("y2",   cy + cfg.rowHeight / 2)
        .attr("stroke",        "#E5E5E5")
        .attr("stroke-width",  1);
    }
  });
}

/**
 * Create a generic mirrored opposed-bar chart.
 *
 * Renders a stack of rows where each row shows a left value/bar (in left.color)
 * and a right value/bar (in right.color) with a centered row label. Bar lengths
 * are determined per-row by scaleType; value text is always shown regardless of
 * bar length (including zero).
 *
 * @param {d3.Selection} selection - D3 selection to append the <svg> into.
 * @param {Object} data - Chart data.
 * @param {Object} data.left - Left-side identity.
 * @param {string} data.left.label - Display label for the left side (shown in header).
 * @param {string} data.left.color - Hex color for left bars.
 * @param {Object} data.right - Right-side identity.
 * @param {string} data.right.label - Display label for the right side (shown in header).
 * @param {string} data.right.color - Hex color for right bars.
 * @param {Array<Object>} data.rows - One entry per row.
 * @param {string}   data.rows[].label      - Row label, centered between bars.
 * @param {number}   data.rows[].leftValue  - Left-side numeric value.
 * @param {number}   data.rows[].rightValue - Right-side numeric value.
 * @param {"sum"|"fixed100"|"max"} data.rows[].scaleType - Bar scale method:
 *   "sum"      — bar width = value / (left + right) × maxBarW.
 *   "fixed100" — bar width = value / 100 × maxBarW (values must sum to 100).
 *   "max"      — bar width = value / maxValue × maxBarW (requires rows[].maxValue).
 * @param {"int"|"pct"|"float1"} data.rows[].format - Value display format:
 *   "int"    — Math.round(v).
 *   "pct"    — v.toFixed(1) + "%".
 *   "float1" — v.toFixed(1).
 * @param {number} [data.rows[].maxValue] - Required when scaleType is "max".
 * @param {Object} [config] - Visual configuration.
 * @param {number} [config.width=480]        - Total SVG width in pixels.
 * @param {number} [config.rowHeight=40]     - Height per data row in pixels.
 * @param {number} [config.barHeight=14]     - Bar rectangle height in pixels.
 * @param {number} [config.labelWidth=130]   - Center label zone width in pixels.
 * @param {number}  [config.headerHeight=32]  - Height of the side-label header in pixels.
 * @param {number}  [config.paddingY=10]      - Vertical padding above/below rows.
 * @param {boolean} [config.showHeader=true]  - Render the colored side-label header row.
 *   Pass false when the caller renders its own side labels (e.g. matchStats score headline).
 * @returns {{ svg: d3.Selection, update: Function }}
 *   svg — the appended SVG element.
 *   update(newData) — replace data and redraw rows without recreating the SVG.
 */
export function createComparisonBars(selection, data, config = {}) {
  const cfg = { ...DEFAULTS, ...config };
  // When header is suppressed, collapse its height so rows start at the top.
  const headerH = cfg.showHeader === false ? 0 : cfg.headerHeight;

  const halfW   = (cfg.width - cfg.labelWidth) / 2;
  const maxBarW = halfW - VAL_PAD - VAL_RESERVE;

  function totalHeight(rows) {
    return headerH + cfg.paddingY + rows.length * cfg.rowHeight + cfg.paddingY;
  }

  const svg = selection
    .append("svg")
    .attr("width",  cfg.width)
    .attr("height", totalHeight(data.rows));

  // ── Header (optional) ────────────────────────────────────────────────────────
  if (cfg.showHeader !== false) {
    const headerG = svg.append("g").attr("class", "cb-header");

    headerG.append("text")
      .attr("class",            "cb-side-label cb-side-label--left")
      .attr("x",                halfW - VAL_PAD)
      .attr("y",                headerH / 2)
      .attr("text-anchor",      "end")
      .attr("dominant-baseline","middle")
      .attr("fill",             data.left.color)
      .attr("font-family",      "var(--font-mono,'Geist Mono',monospace)")
      .attr("font-size",        "11px")
      .attr("font-weight",      "600")
      .attr("letter-spacing",   "0.06em")
      .attr("text-transform",   "uppercase")
      .text(data.left.label.toUpperCase());

    headerG.append("text")
      .attr("class",            "cb-side-label cb-side-label--right")
      .attr("x",                halfW + cfg.labelWidth + VAL_PAD)
      .attr("y",                headerH / 2)
      .attr("text-anchor",      "start")
      .attr("dominant-baseline","middle")
      .attr("fill",             data.right.color)
      .attr("font-family",      "var(--font-mono,'Geist Mono',monospace)")
      .attr("font-size",        "11px")
      .attr("font-weight",      "600")
      .attr("letter-spacing",   "0.06em")
      .text(data.right.label.toUpperCase());

    headerG.append("line")
      .attr("x1",  0).attr("x2",  cfg.width)
      .attr("y1",  headerH).attr("y2", headerH)
      .attr("stroke", "#E5E5E5").attr("stroke-width", 1);
  }

  // ── Rows ────────────────────────────────────────────────────────────────────
  const rowsG = svg
    .append("g")
    .attr("class",     "cb-rows")
    .attr("transform", `translate(0, ${headerH})`);

  drawRows(rowsG, data, cfg, halfW, maxBarW);

  /**
   * Replace the chart data and redraw all rows. The SVG size is adjusted to fit
   * the new row count. The header (side labels) is not redrawn.
   *
   * @param {Object} newData - Same shape as the original data parameter.
   */
  function update(newData) {
    svg.attr("height", totalHeight(newData.rows));
    drawRows(rowsG, newData, cfg, halfW, maxBarW);
  }

  return { svg, update };
}
