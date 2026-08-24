/**
 * Render a polar pass-sonar chart for one player.
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object} data - Object with an `events` array — the
 *   player_events/{match_id}/{player_id}.json contract (or any subset of it;
 *   non-Pass events are ignored, so callers may pass the full file unfiltered).
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {number}   [config.width=280]              - SVG width in pixels.
 * @param {number}   [config.height=280]             - SVG height in pixels.
 * @param {number}   [config.numBins=16]             - Angular sectors.
 * @param {string}   [config.attemptedColor="#9F1239"] - Outer wedge stroke color.
 * @param {string}   [config.completedColor="#9F1239"] - Inner wedge fill color.
 * @param {string}   [config.highlightColor="#F59E0B"] - Ring color for the
 *   bin containing config.highlightEventId.
 * @param {string|null} [config.highlightEventId=null] - Inbound cross-link:
 *   rings whichever bin contains a pass with this event_id.
 * @param {Function|null} [config.onHover=null] - onHover({ bin, eventIds } | null)
 *   fires on wedge hover/unhover. eventIds is every attempted pass's event_id
 *   in that sector (see module docstring for why this is plural).
 * @param {boolean}  [config.showTooltip=true] - Render the built-in floating tooltip.
 * @returns {{ svg: d3.Selection, g: d3.Selection, update: Function }}
 *   svg    — the created SVG selection.
 *   g      — the main <g> group, centered in the SVG.
 *   update({ data?, highlightEventId? }) — re-render with new events and/or
 *     move the inbound highlight ring. Any omitted key retains its current value.
 */
export function createPassSonar(selection: d3.Selection<any, any, any, any>, data: any, config?: {
    width?: number;
    height?: number;
    numBins?: number;
    attemptedColor?: string;
    completedColor?: string;
    highlightColor?: string;
    highlightEventId?: string | null;
    onHover?: Function | null;
    showTooltip?: boolean;
}): {
    svg: d3.Selection<any, any, any, any>;
    g: d3.Selection<any, any, any, any>;
    update: Function;
};
import * as d3 from "d3";
