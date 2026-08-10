/**
 * Render a master minute-scrubber with a draggable playhead.
 *
 * Creates a standalone SVG inside the given selection. The playhead can be
 * moved by dragging, by clicking anywhere on the track, or via ArrowLeft/
 * ArrowRight when the handle has focus (1-minute steps; Shift+Arrow for
 * 5-minute steps). Every move calls config.onScrub(minute).
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {number}   [config.width=760]        - SVG width in pixels.
 * @param {number}   [config.height=56]        - SVG height in pixels.
 * @param {Object}   [config.padding]          - Inner padding in pixels.
 *   Defaults: { top: 10, right: 20, bottom: 22, left: 20 }.
 * @param {number}   [config.minMinute=0]      - Track domain minimum.
 * @param {number}   [config.maxMinute=94]     - Track domain maximum.
 * @param {number}   [config.initialMinute]    - Starting playhead position.
 *   Defaults to maxMinute (full match/window revealed).
 * @param {Array}    [config.events=[]]        - Objects with a `minute` field,
 *   used only to draw density-hint ticks along the track.
 * @param {Function} [config.onScrub]          - onScrub(minute): called with the
 *   new minute on every drag/click/keyboard move.
 * @param {string}   [config.trackColor="#E5E5E5"]   - Unplayed track color.
 * @param {string}   [config.playedColor="#9F1239"]  - Played (0..current) track color.
 * @param {string}   [config.handleColor="#9F1239"]  - Playhead handle fill color.
 * @param {number}   [config.handleRadius=8]         - Playhead handle radius in pixels.
 * @returns {{ svg: d3.Selection, g: d3.Selection, xScale: d3.ScaleLinear,
 *   update: function, seek: function }}
 *   svg:    The created SVG selection.
 *   g:      The main <g> group inside the SVG.
 *   xScale: The minute → pixel scale.
 *   update: function({ events? }) — replace the density-hint event array.
 *   seek:   function(minute) — programmatically move the playhead without
 *           firing onScrub (for initialization/sync from external state).
 */
export function createScrubber(selection: d3.Selection<any, any, any, any>, config?: {
    width?: number;
    height?: number;
    padding?: any;
    minMinute?: number;
    maxMinute?: number;
    initialMinute?: number;
    events?: any[];
    onScrub?: Function;
    trackColor?: string;
    playedColor?: string;
    handleColor?: string;
    handleRadius?: number;
}): {
    svg: d3.Selection<any, any, any, any>;
    g: d3.Selection<any, any, any, any>;
    xScale: d3.ScaleLinear<any, any, never>;
    update: Function;
    seek: Function;
};
import * as d3 from "d3";
