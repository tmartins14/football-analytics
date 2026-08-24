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
export function createComparisonBars(selection: import("d3-selection").Selection<any, any, any, any>, data: {
    left: {
        label: string;
        color: string;
    };
    right: {
        label: string;
        color: string;
    };
    rows: Array<any>;
}, config?: {
    width?: number;
    rowHeight?: number;
    barHeight?: number;
    labelWidth?: number;
    headerHeight?: number;
    paddingY?: number;
    showHeader?: boolean;
}): {
    svg: import("d3-selection").Selection<any, any, any, any>;
    update: Function;
};
