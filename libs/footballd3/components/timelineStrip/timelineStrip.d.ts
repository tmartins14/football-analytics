/**
 * Render a single-possession elapsed-seconds timeline strip.
 *
 * Creates its own SVG inside the given selection. Does not compose on pitch.js.
 * Events are positioned on a real elapsed-seconds X axis; glyphs are colored circles
 * with a single-letter type abbreviation. Events within 0.4s of each other are
 * stacked vertically so nothing overlaps.
 *
 * The X axis is real tempo — a 3-second possession looks cramped and a 70-second
 * build-up spreads out clearly. This is intentional: the strip is a narrative device
 * showing when things happened, not how many.
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object}       data      - Possession JSON contract
 *   (possession_{match_id}_{possession}.json). Must expose an `events` array of
 *   { event_type, seconds, player, outcome }.
 * @param {Object}  [config={}]             - Rendering options.
 * @param {number}  [config.width=760]      - SVG width in pixels.
 * @param {number}  [config.height=120]     - SVG height in pixels. Should be large
 *   enough to accommodate vertical stacking (stackStep × max_cluster_depth × 2).
 * @param {Object}  [config.padding]        - Inner padding in pixels.
 *   Defaults: { top: 24, right: 24, bottom: 32, left: 24 }.
 * @param {number}  [config.glyphRadius=8]  - Glyph circle radius in pixels.
 * @param {number}  [config.stackStep=20]   - Vertical offset between stacked glyphs.
 * @param {number}  [config.binWindow=0.4]  - Seconds window for collision binning.
 * @param {Function} [config.colorScale]    - Override event_type → color function.
 * @returns {{ svg: d3.Selection, g: d3.Selection, xScale: d3.ScaleLinear, update: function }}
 *   svg:    The created SVG selection.
 *   g:      The main <g> group inside the SVG.
 *   xScale: The elapsed-seconds → pixel scale (exposed for future cross-component linkage).
 *   update: function({ events? }) — re-renders with a new event array. Omit to re-render
 *           with current state.
 */
export function createTimelineStrip(selection: d3.Selection<any, any, any, any>, data: any, config?: {
    width?: number;
    height?: number;
    padding?: any;
    glyphRadius?: number;
    stackStep?: number;
    binWindow?: number;
    colorScale?: Function;
}): {
    svg: d3.Selection<any, any, any, any>;
    g: d3.Selection<any, any, any, any>;
    xScale: d3.ScaleLinear<any, any, never>;
    update: Function;
};
import * as d3 from "d3";
