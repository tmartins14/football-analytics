/**
 * Render a match momentum chart as a filled area curve crossing zero.
 *
 * Creates a standalone SVG inside the given selection. Supports two orientations:
 * "horizontal" (time on X, momentum on Y) and "vertical" (time on Y, momentum on X).
 * The SVG dimensions are swapped automatically when orientation changes via update().
 *
 * In horizontal mode: config.width drives the time axis, config.height drives momentum.
 * In vertical mode: those dimensions are swapped — the SVG becomes height×width so the
 * time axis spans config.width pixels and the momentum axis spans config.height pixels.
 *
 * @param {d3.Selection} selection   - D3 selection of the container element.
 * @param {Object}       data        - momentum_{match_id}.json contract:
 *   { home_team, away_team,
 *     minutes: [{minute, home_threat, away_threat, momentum}],
 *     secondary_minutes: [{minute, home_threat, away_threat, momentum}],
 *     goals: [{minute, team, player, is_own_goal}],
 *     red_cards: [{minute, team, player}],
 *     params, metadata }
 * @param {Object}  [config={}]                        - Rendering options.
 * @param {number}  [config.width=760]                 - Time-axis dimension in pixels.
 * @param {number}  [config.height=220]                - Momentum-axis dimension in pixels.
 * @param {Object}  [config.padding]                   - Inner padding for horizontal mode.
 *   Defaults: { top: 36, right: 24, bottom: 40, left: 52 }.
 * @param {string}  [config.homeColor="#1E3A5F"]       - Fill color for home territory.
 * @param {string}  [config.awayColor="#9F1239"]       - Fill color for away territory.
 * @param {boolean} [config.showGoals=true]            - Render goal event markers.
 * @param {boolean} [config.showCards=true]            - Render red card event markers.
 * @param {boolean} [config.showSecondaryWindow=true]  - Overlay the secondary window.
 * @param {string}  [config.orientation="horizontal"]  - "horizontal" or "vertical".
 * @returns {{
 *   svg:           d3.Selection,
 *   g:             d3.Selection,
 *   timeScale:     d3.ScaleLinear,
 *   momentumScale: d3.ScaleLinear,
 *   update:        function
 * }}
 *   svg:           The created SVG selection.
 *   g:             The main <g> group (use for custom overlays).
 *   timeScale:     Minutes → pixel scale (horizontal: maps to X; vertical: maps to Y).
 *   momentumScale: Momentum → pixel scale (horizontal: maps to Y; vertical: maps to X).
 *   update:        function({ data?, orientation?, showSecondaryWindow?, showGoals?, showCards? })
 *                  Re-renders with updated options. Any omitted key retains its current value.
 */
export function createMomentumChart(selection: d3.Selection<any, any, any, any>, data: any, config?: {
    width?: number;
    height?: number;
    padding?: any;
    homeColor?: string;
    awayColor?: string;
    showGoals?: boolean;
    showCards?: boolean;
    showSecondaryWindow?: boolean;
    orientation?: string;
}): {
    svg: d3.Selection<any, any, any, any>;
    g: d3.Selection<any, any, any, any>;
    timeScale: d3.ScaleLinear<any, any, never>;
    momentumScale: d3.ScaleLinear<any, any, never>;
    update: Function;
};
import * as d3 from "d3";
