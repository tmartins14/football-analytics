/**
 * Auto-select up to 5 standout moments from a player's full-match events:
 * every goal, then the single highest-xG non-goal shot, then the top 3
 * positive-xt_delta Pass/Carry actions — combined and sorted chronologically,
 * then truncated to 5. This is a plain chronological truncation with no
 * goal-priority protection: with more than 5 combined candidates, the
 * latest-occurring ones are dropped even if one is a goal.
 *
 * @param {Array<Object>} events - Full player_events array (not scrub-filtered).
 * @returns {Array<{ minute: number, location: [number, number],
 *   end_location: [number, number]|null, kind: string, note: string,
 *   event_id: string }>} Chronologically ordered moments, at most 5.
 */
export function selectMoments(events: Array<any>): Array<{
    minute: number;
    location: [number, number];
    end_location: [number, number] | null;
    kind: string;
    note: string;
    event_id: string;
}>;
/**
 * Build every event's own moment record, in chronological order — the "all
 * events" mode's moment list, one step per event rather than a curated
 * top-5. Reuses selectMoments()'s exact copy for Goal/Shot/Pass/Carry so the
 * two modes read consistently, and adds a generic fallback (`"{type}"`, or
 * `"{type} · {outcome}"` when there's an outcome) for every other event type
 * (Pressure, Duel, Ball Recovery, etc.), which selectMoments() never needs to
 * describe since it only ever selects goals/shots/positive-xT passes-carries.
 *
 * @param {Array<Object>} events - Full player_events array (not scrub-filtered).
 * @returns {Array<Object>} Every event as a moment record (see _moment),
 *   sorted chronologically by minute.
 */
export function allEventsMoments(events: Array<any>): Array<any>;
/**
 * Render a highlight reel for one player.
 *
 * @param {d3.Selection} selection - D3 selection of the container element
 *   (an HTML element — this component renders div children, not an SVG root).
 * @param {Object} data - Object with an `events` array — the
 *   player_events/{match_id}/{player_id}.json contract (full match, not
 *   scrub-filtered — the reel always selects from every credited event
 *   regardless of the current scrub position).
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {string}   [config.mode="highlights"] - "highlights" (up to 5
 *   curated moments via selectMoments()) or "all" (every event via
 *   allEventsMoments(), chronological, no progress dots).
 * @param {number}   [config.stepDurationMs=1800] - Milliseconds between
 *   moments during Play.
 * @param {string}   [config.teamColor] - Accepted for API-shape parity with
 *   the design spec, but intentionally unused — the reference implementation
 *   this component is built against never reads it either; every reel color
 *   comes from the focal/text/faint/border tokens below.
 * @param {Function|null} [config.onScrubTo=null] - onScrubTo(minute) fires
 *   on every step (Play advancing, or a manual prev/next/dot click/click).
 * @param {Function|null} [config.onHoverEvent=null] - onHoverEvent(eventId | null)
 *   fires on hover/unhover of the current moment's description.
 * @param {string} [config.borderColor="#E5E5E5"] - Transport button border.
 * @param {string} [config.buttonBackground="#FFFFFF"] - Prev/next button fill.
 * @param {string} [config.textColor="#171717"] - Body text color.
 * @param {string} [config.faintColor="#8A8578"] - Label/empty-state text color.
 * @param {string} [config.focalColor="#9F1239"] - Accent color (minute, Play
 *   button fill, active dot).
 * @param {string} [config.focalTextColor="#FAF7F0"] - Text color on the
 *   (always-filled) Play button — the theme's own background color.
 * @param {string} [config.inactiveDotColor="#D6D3CC"] - Inactive progress dot fill.
 * @returns {{ container: d3.Selection, update: Function, play: Function,
 *   pause: Function, step: Function }}
 *   container — the reel's root D3 selection.
 *   update({ data?, mode?, stepDurationMs? }) — re-render, optionally with a
 *     new events array and/or mode (re-selects moments, resets to index 0,
 *     stops any active playback) and/or a new step cadence.
 *   play() — begin playback from the start.
 *   pause() — stop playback without changing the current index.
 *   step(delta) — move the current index by delta (e.g. 1 or -1), clamped to
 *     the moment list, firing onScrubTo immediately.
 */
export function createHighlightReel(selection: import("d3-selection").Selection<any, any, any, any>, data: any, config?: {
    mode?: string;
    stepDurationMs?: number;
    teamColor?: string;
    onScrubTo?: Function | null;
    onHoverEvent?: Function | null;
    borderColor?: string;
    buttonBackground?: string;
    textColor?: string;
    faintColor?: string;
    focalColor?: string;
    focalTextColor?: string;
    inactiveDotColor?: string;
}): {
    container: import("d3-selection").Selection<any, any, any, any>;
    update: Function;
    play: Function;
    pause: Function;
    step: Function;
};
