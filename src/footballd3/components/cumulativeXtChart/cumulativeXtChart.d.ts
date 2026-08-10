/**
 * Render a cumulative xT "running total" line for one player.
 *
 * Creates a standalone SVG inside the given selection. Horizontal only: time on
 * the X axis, cumulative xT on the Y axis (zero at the bottom).
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object}       data      - player_events/{match_id}/{player_id}.json
 *   contract (or any object with the same shape): { events: [...] }. Pass/Carry
 *   events with xt_delta feed the line; Shot events become chip markers.
 * @param {Object}  [config={}]                 - Rendering options.
 * @param {number}  [config.width=760]          - SVG width in pixels.
 * @param {number}  [config.height=220]         - SVG height in pixels.
 * @param {Object}  [config.padding]            - Inner padding in pixels.
 *   Defaults: { top: 20, right: 60, bottom: 40, left: 48 }.
 * @param {number}  [config.finalMinute]        - Minute the time axis extends
 *   to. Defaults to the player's own last event minute — pass the shared
 *   scrubber's maxMinute explicitly to align this chart's domain with sibling
 *   panels driven by the same master scrubber.
 * @param {string}  [config.lineColor="#9F1239"]  - Cumulative-xT line stroke color.
 * @param {string}  [config.shotColor="#525252"]  - Shot chip fill color.
 * @param {string}  [config.goalRingColor="#9F1239"] - Extra ring stroke on goal chips.
 * @param {boolean} [config.showShots=true]      - Render shot chip markers.
 * @param {boolean} [config.showTotal=true]      - Render the end-of-line total label.
 * @param {Function} [config.onHover]            - onHover(point|null): called with
 *   the nearest series point on mousemove, and `null` on mouseleave. The point
 *   carries `event_id` (null for the two synthetic domain-anchor points) so a
 *   sibling panel can cross-link the exact hovered action. Fires alongside the
 *   built-in tooltip (not a replacement) unless showTooltip is false.
 * @param {boolean} [config.showTooltip=true]    - Render the built-in floating tooltip.
 * @param {string}  [config.highlightColor="#F59E0B"] - Inbound cross-link ring color.
 * @param {string|null} [config.highlightEventId=null] - Inbound cross-link: rings
 *   whichever point (a line point or a shot chip) carries this event_id — set
 *   this from a hover fired elsewhere (a pitch marker, feed row, sonar wedge, ...).
 * @returns {{
 *   svg:       d3.Selection,
 *   g:         d3.Selection,
 *   timeScale: d3.ScaleLinear,
 *   xtScale:   d3.ScaleLinear,
 *   update:    function
 * }}
 *   svg:       The created SVG selection.
 *   g:         The main <g> group (use for custom overlays).
 *   timeScale: Minutes → pixel scale (maps to X).
 *   xtScale:   Cumulative xT → pixel scale (maps to Y, inverted).
 *   update:    function({ data?, showShots?, showTotal? }) — re-renders with
 *              updated options. Any omitted key retains its current value.
 */
export function createCumulativeXtChart(selection: d3.Selection<any, any, any, any>, data: any, config?: {
    width?: number;
    height?: number;
    padding?: any;
    finalMinute?: number;
    lineColor?: string;
    shotColor?: string;
    goalRingColor?: string;
    showShots?: boolean;
    showTotal?: boolean;
    onHover?: Function;
    showTooltip?: boolean;
    highlightColor?: string;
    highlightEventId?: string | null;
}): {
    svg: d3.Selection<any, any, any, any>;
    g: d3.Selection<any, any, any, any>;
    timeScale: d3.ScaleLinear<any, any, never>;
    xtScale: d3.ScaleLinear<any, any, never>;
    update: Function;
};
import * as d3 from "d3";
