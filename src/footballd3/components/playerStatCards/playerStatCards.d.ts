/**
 * Render the six-card player stat-card row.
 *
 * @param {d3.Selection} selection - D3 selection of the container element
 *   (an HTML element — this component renders div children, not an SVG root).
 * @param {Object} data - `{ events, possessionShares, playerTeam, scrubbedMinute }`.
 * @param {Array<Object>} data.events - Scrub-filtered player_events array,
 *   feeding five of the six metrics directly.
 * @param {Object} [data.possessionShares] - extract_possession_shares.py's
 *   match-level output (shared across every player, not scrub-filtered by
 *   the caller — this component picks the right bucket itself).
 * @param {string} [data.playerTeam] - The selected player's own team name.
 * @param {number} [data.scrubbedMinute] - Current scrub position, for
 *   picking the PAdj defensive-actions bucket. Defaults to the max minute
 *   present in `events` when omitted.
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {Function|null} [config.onHover=null] - onHover(layer | null) fires
 *   on card hover/unhover, where layer matches actionFeed.js's classifyLayer
 *   vocabulary plus "defensive" (the PAdj card's combined defensive-action set).
 * @returns {{ container: d3.Selection, update: Function }}
 *   container — the card-row D3 selection.
 *   update({ data? }) — re-renders with a new data object. Any omitted key
 *     in the new data object falls back to its previous value.
 */
export function createPlayerStatCards(selection: import("d3-selection").Selection<any, any, any, any>, data: {
    events: Array<any>;
    possessionShares?: any;
    playerTeam?: string;
    scrubbedMinute?: number;
}, config?: {
    onHover?: Function | null;
}): {
    container: import("d3-selection").Selection<any, any, any, any>;
    update: Function;
};
