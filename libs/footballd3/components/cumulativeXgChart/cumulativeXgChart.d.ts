/**
 * Render a cumulative xG "race chart" — a step-line per team over match time.
 *
 * Creates a standalone SVG inside the given selection. Supports two orientations:
 * "horizontal" (time on X, cumulative xG on Y) and "vertical" (time on Y,
 * cumulative xG on X). The SVG dimensions are swapped automatically when
 * orientation changes via update().
 *
 * @param {d3.Selection} selection   - D3 selection of the container element.
 * @param {Object}       data        - cumulative_xg_{match_id}.json contract:
 *   { home_team, away_team,
 *     points: [{minute, team, display_name, xg, cumulative_xg, outcome, is_goal}],
 *     final_minute, final_home_xg, final_away_xg,
 *     goals: [{minute, team, player, is_own_goal}],
 *     metadata }
 * @param {Object}  [config={}]                  - Rendering options.
 * @param {number}  [config.width=760]           - Time-axis dimension in pixels.
 * @param {number}  [config.height=220]          - xG-axis dimension in pixels.
 * @param {Object}  [config.padding]             - Inner padding for horizontal mode.
 *   Defaults: { top: 20, right: 88, bottom: 40, left: 48 }. Right padding is wider
 *   than a diverging chart's to fit end-of-line total labels.
 * @param {string}  [config.homeColor="#1E3A5F"] - Stroke color for the home team's line.
 * @param {string}  [config.awayColor="#9F1239"] - Stroke color for the away team's line.
 * @param {boolean} [config.showGoals=true]      - Render actual-goal "G" chip markers.
 * @param {boolean} [config.showTotals=true]     - Render end-of-line cumulative total labels.
 * @param {string}  [config.orientation="horizontal"] - "horizontal" or "vertical".
 * @param {Function} [config.onHover]            - onHover(point|null): called with the
 *   nearest shot point on mousemove, and `null` on mouseleave. Fires alongside the
 *   built-in tooltip (not a replacement) unless config.showTooltip is false.
 * @param {boolean} [config.showTooltip=true]    - Render the built-in floating
 *   tooltip on hover. Set false when the caller renders its own readout from
 *   onHover instead.
 * @returns {{
 *   svg:       d3.Selection,
 *   g:         d3.Selection,
 *   timeScale: d3.ScaleLinear,
 *   xgScale:   d3.ScaleLinear,
 *   update:    function
 * }}
 *   svg:       The created SVG selection.
 *   g:         The main <g> group (use for custom overlays).
 *   timeScale: Minutes → pixel scale (horizontal: maps to X; vertical: maps to Y).
 *   xgScale:   Cumulative xG → pixel scale (horizontal: maps to Y; vertical: maps to X).
 *   update:    function({ data?, orientation?, showGoals?, showTotals? })
 *              Re-renders with updated options. Any omitted key retains its current value.
 */
export function createCumulativeXgChart(selection: d3.Selection<any, any, any, any>, data: any, config?: {
    width?: number;
    height?: number;
    padding?: any;
    homeColor?: string;
    awayColor?: string;
    showGoals?: boolean;
    showTotals?: boolean;
    orientation?: string;
    onHover?: Function;
    showTooltip?: boolean;
}): {
    svg: d3.Selection<any, any, any, any>;
    g: d3.Selection<any, any, any, any>;
    timeScale: d3.ScaleLinear<any, any, never>;
    xgScale: d3.ScaleLinear<any, any, never>;
    update: Function;
};
import * as d3 from "d3";
