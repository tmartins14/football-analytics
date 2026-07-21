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
export function createXtSurface(pitch: any, data: {
    rows: number;
    cols: number;
    values: any[];
    cell_dims: any;
}, config?: {
    colorScale?: Function;
    opacity?: number;
    minValue?: number;
    maxValue?: number;
}): {
    g: d3.Selection<any, any, any, any>;
    update: Function;
};
import * as d3 from "d3";
