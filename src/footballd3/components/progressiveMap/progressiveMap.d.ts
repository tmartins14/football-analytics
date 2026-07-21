/**
 * Create a pass and carry arrow overlay on an existing pitch.
 *
 * Call createPitch() first and pass its return value here. This function
 * appends arrow elements to pitch.g and never touches the pitch background
 * or markings.
 *
 * By default all open-play actions are shown. Color encodes action type for
 * ALL actions — red for passes, navy for carries. Progressive actions are bold
 * with arrowheads; non-progressive are thin and faded (same type color). Set
 * progressiveOnly: true to show only progressive actions.
 *
 * Passes show completed and incomplete attempts (solid vs dashed red).
 * Carries show completed carries only — see README for the asymmetry rationale.
 *
 * @param {Object} pitch - Return value of createPitch(). Must expose { svg, g, px }.
 * @param {Object} data  - Progressive map JSON contract (progressive_map_*.json).
 * @param {Object} [config={}] - Rendering options.
 * @param {string}  [config.toggle="both"]           - Which action types to show:
 *   "passes" | "carries" | "both".
 * @param {string|null} [config.player=null]          - Restrict to one player by
 *   display_name. null renders all players.
 * @param {boolean} [config.progressiveOnly=false]    - When true, render only
 *   progressive actions (hides the muted background layer).
 * @param {boolean} [config.distanceWeight=false]     - When true, scale stroke-width
 *   of progressive arrows linearly by distance_gained. Off by default.
 * @returns {{ g: d3.Selection, update: function }}
 *   g:      The D3 selection of the arrow group (appended to pitch.g).
 *   update: function({ toggle?, player?, progressiveOnly? }) — re-renders with
 *           new filter state. Any omitted keys keep their previous value.
 */
export function createProgressiveMap(pitch: any, data: any, config?: {
    toggle?: string;
    player?: string | null;
    progressiveOnly?: boolean;
    distanceWeight?: boolean;
}): {
    g: d3.Selection<any, any, any, any>;
    update: Function;
};
import * as d3 from "d3";
