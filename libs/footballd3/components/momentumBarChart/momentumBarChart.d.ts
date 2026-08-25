/**
 * Render a 2-minute-binned diverging momentum bar chart.
 *
 * Creates a standalone SVG inside the given selection. Bars are hoverable via a
 * full-height transparent strip per bin (bars themselves can be too short to
 * reliably hover near zero momentum) — hover fires config.onHover(bin), leave
 * fires config.onHover(null).
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object} data - momentum_{match_id}.json contract (same shape momentumChart.js reads):
 *   { home_team, away_team, minutes: [{minute, home_threat, away_threat, momentum}],
 *     goals: [{minute, team, player, is_own_goal}], red_cards, params, metadata }
 * @param {Object}   [config={}]                  - Rendering options.
 * @param {number}   [config.width=316]           - SVG width in pixels.
 * @param {number}   [config.height=210]          - SVG height in pixels.
 * @param {"horizontal"|"vertical"} [config.orientation="horizontal"] - Axis layout.
 *   "horizontal" (default, unchanged): time on X, magnitude on Y, diverging from a
 *   horizontal centerline — suited to a wide, short box. "vertical": time on Y
 *   (top = minute 0, increasing downward), magnitude on X, diverging from a
 *   vertical centerline — suited to a narrow, tall box.
 * @param {string}   [config.homeColor="#1E3A5F"] - Fill color for home-leaning bars.
 * @param {string}   [config.awayColor="#9F1239"] - Fill color for away-leaning bars.
 * @param {boolean}  [config.showGoals=true]      - Render goal event markers.
 * @param {Function} [config.onHover=null]        - onHover(bin|null): called with the
 *   hovered bin `{start, end, value}` on hover, and `null` on leave. No internal
 *   tooltip is rendered — callers own the readout UI.
 * @returns {{ svg: d3.Selection, g: d3.Selection, update: Function }}
 *   svg:    The created SVG selection.
 *   g:      The main <g> group (use for custom overlays).
 *   update: function({ data?, showGoals? }) — re-renders with updated options.
 */
export function createMomentumBarChart(selection: d3.Selection<any, any, any, any>, data: any, config?: {
    width?: number;
    height?: number;
    orientation?: "horizontal" | "vertical";
    homeColor?: string;
    awayColor?: string;
    showGoals?: boolean;
    onHover?: Function;
}): {
    svg: d3.Selection<any, any, any, any>;
    g: d3.Selection<any, any, any, any>;
    update: Function;
};
import * as d3 from "d3";
