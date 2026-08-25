/**
 * Whether an event succeeded — the second half of the shape+fill encoding
 * (shape = category, fill = outcome: filled means succeeded, hollow means
 * failed). Types with no real success/fail concept (Pressure, Ball Recovery,
 * Clearance, etc.) default to filled.
 *
 * @param {Object} event - One event from the player_events contract.
 * @returns {boolean} true if the event should render filled.
 */
export function isSuccessfulEvent(event: any): boolean;
/**
 * Classify one player_events event into the app's shared layer taxonomy.
 *
 * Mirrors the Territory panel's marker categories exactly: progressive
 * passes/carries, key passes, pressures, duels, turnovers (Dispossessed/
 * Miscontrol), and shots. Anything else (Interception, Ball Recovery,
 * Clearance, Block, plain non-progressive Pass/Carry) is "other".
 *
 * @param {Object} event - One event from the player_events contract.
 * @returns {string} One of "shot", "progressive_pass", "key_pass",
 *   "pressure", "duel", "turnover", "other".
 */
export function classifyLayer(event: any): string;
/**
 * Render a scrollable, sortable action feed for one player.
 *
 * @param {d3.Selection} selection - D3 selection of the container element
 *   (an HTML element — this component renders div/svg children, not an SVG root).
 * @param {Object} data - Object with an `events` array — the
 *   player_events/{match_id}/{player_id}.json contract, already filtered by
 *   the caller to `minute <= scrubbedMinute` (this component does not filter
 *   by minute itself, matching cumulativeXtChart.js's convention).
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {number}   [config.height=320]        - Scroll container height in pixels.
 * @param {string}   [config.sortBy="minute"]    - "minute" | "xt".
 * @param {string}   [config.sortDir="asc"]      - "asc" | "desc".
 * @param {string}   [config.iconColor="#525252"] - Ink color for each row's
 *   shape+fill/hollow category glyph (see CATEGORY_SHAPE/isSuccessfulEvent) —
 *   a caller with a team/player color scheme overrides this per player.
 * @param {string|null} [config.highlightEventId=null] - Inbound cross-link:
 *   rings/tints the row with this event_id.
 * @param {Function|null} [config.onHoverRow=null] - onHoverRow(eventId | null)
 *   fires on row hover/unhover.
 * @returns {{ container: d3.Selection, update: Function }}
 *   container — the scroll-container D3 selection.
 *   update({ data?, sortBy?, sortDir?, highlightEventId? }) — re-render with
 *     new events, a new sort, and/or a new inbound highlight. Any omitted key
 *     retains its current value.
 */
export function createActionFeed(selection: d3.Selection<any, any, any, any>, data: any, config?: {
    height?: number;
    sortBy?: string;
    sortDir?: string;
    iconColor?: string;
    highlightEventId?: string | null;
    onHoverRow?: Function | null;
}): {
    container: d3.Selection<any, any, any, any>;
    update: Function;
};
export namespace CATEGORY_SHAPE {
    let shot: d3.SymbolType;
    let progressive_pass: d3.SymbolType;
    let key_pass: d3.SymbolType;
    let pressure: d3.SymbolType;
    let duel: d3.SymbolType;
    let turnover: d3.SymbolType;
    let other: d3.SymbolType;
}
import * as d3 from "d3";
