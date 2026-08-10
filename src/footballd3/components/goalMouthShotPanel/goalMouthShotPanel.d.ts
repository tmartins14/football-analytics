/**
 * Render a goal-frame shot panel for one player.
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object} data - Object with an `events` array — the
 *   player_events/{match_id}/{player_id}.json contract (or any subset of
 *   it). Non-Shot events and shots without a shot_end_location are ignored,
 *   so callers may pass the full unfiltered file.
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {number}   [config.width=320]  - SVG width in pixels. SVG height is
 *   always derived from this at the regulation goal ratio
 *   (GOAL_WIDTH_YARDS / CROSSBAR_HEIGHT_YARDS, ~3:1), not independently
 *   configurable — a fixed height paired with a narrower-than-expected
 *   container previously squashed the frame toward square.
 * @param {number|null} [config.minRadius=null] - Smallest shot-marker radius
 *   in pixels. Defaults to a size proportionate to the (width-derived) frame
 *   height rather than a fixed pixel value, so markers look the same
 *   relative size at any container width.
 * @param {number|null} [config.maxRadius=null] - Largest shot-marker radius
 *   in pixels (at the highest shot_xg in the data) — same proportional
 *   default behavior as minRadius.
 * @param {string}   [config.frameColor="#1E3A5F"]     - Goal-frame stroke color.
 * @param {string}   [config.onTargetColor="#525252"]  - On-target shot fill/stroke color.
 * @param {string}   [config.goalColor="#9F1239"]      - Goal fill + ring color.
 * @param {string}   [config.highlightColor="#F59E0B"] - Inbound cross-link ring color.
 * @param {string|null} [config.highlightEventId=null] - Inbound cross-link:
 *   rings the shot with this event_id.
 * @param {Function|null} [config.onHover=null] - onHover(eventId | null)
 *   fires on shot hover/unhover.
 * @param {boolean}  [config.showTooltip=true] - Render the built-in floating tooltip.
 * @param {boolean}  [config.showLegend=true]  - Render the on/off/xG-radius legend.
 * @returns {{ svg: d3.Selection, g: d3.Selection, update: Function }}
 *   svg — the created SVG selection.
 *   g   — the main `<g>` group.
 *   update({ data?, highlightEventId? }) — re-render with new events and/or
 *     move the inbound highlight ring. Any omitted key retains its current value.
 */
export function createGoalMouthShotPanel(selection: d3.Selection<any, any, any, any>, data: any, config?: {
    width?: number;
    minRadius?: number | null;
    maxRadius?: number | null;
    frameColor?: string;
    onTargetColor?: string;
    goalColor?: string;
    highlightColor?: string;
    highlightEventId?: string | null;
    onHover?: Function | null;
    showTooltip?: boolean;
    showLegend?: boolean;
}): {
    svg: d3.Selection<any, any, any, any>;
    g: d3.Selection<any, any, any, any>;
    update: Function;
};
import * as d3 from "d3";
