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
export function createHeatmap(pitch: any, data: any, config?: {
    renderStyle?: string;
    colorLow?: string;
    colorHigh?: string;
    maxOpacity?: number;
}): {
    g: d3.Selection<any, any, any, any>;
    px: Function;
    update: Function;
};
import * as d3 from "d3";
