/**
 * Render event markers onto an existing pitch as a scatter overlay.
 *
 * Appends a <g class="es"> group to pitch.g. Does not touch the pitch background
 * or markings. Call createPitch() first and pass its return value as `pitch`.
 *
 * Events are shape-coded by semantic category and filled/hollow by outcome
 * (see module comment). Events with end_x/end_y (Pass, Carry, Shot) render
 * an arrow from origin to destination; all events render a shaped marker at
 * their origin (x, y).
 *
 * @param {Object} pitch - Return value of createPitch(). Must expose { svg, g, px }.
 * @param {Object} data  - Possession JSON contract (possession_{match_id}_{possession}.json)
 *   or any object with an `events` array of { event_type, seconds, x, y,
 *   end_x, end_y, player, outcome }.
 * @param {Object} [config={}] - Rendering options.
 * @param {number}   [config.markerRadius=5]          - Marker size scale in pixels
 *   (roughly the equivalent radius of the old circle marker).
 * @param {string}   [config.markerColor="#171717"]    - Single ink color for every
 *   marker/arrow — shape and fill/hollow now carry the encoding, not color.
 * @param {boolean}  [config.showArrows=true]          - Draw arrow lines for events
 *   that have end_x/end_y.
 * @param {boolean}  [config.includeBallReceipt=false] - Include "Ball Receipt*" events.
 *   Excluded by default because they cluster on top of Pass end-points.
 * @returns {{ g: d3.Selection, update: function }}
 *   g:      The <g class="es"> group appended to pitch.g.
 *   update: function({ events?, filter? }) — re-renders with a new event array
 *           (`events`) or a predicate function (`filter`). Omit both to re-render
 *           with current state. Omit one key to keep its previous value.
 */
export function createEventScatter(pitch: any, data: any, config?: {
    markerRadius?: number;
    markerColor?: string;
    showArrows?: boolean;
    includeBallReceipt?: boolean;
}): {
    g: d3.Selection<any, any, any, any>;
    update: Function;
};
import * as d3 from "d3";
