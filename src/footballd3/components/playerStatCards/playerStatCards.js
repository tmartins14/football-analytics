/**
 * playerStatCards.js — six-metric stat-card row for one player.
 *
 * Six cards: progressive passes, xG, xA/xGChain (one combined card), pressures
 * + regains, PAdj defensive actions, duels won %. 3x2 on desktop, 2x3 on
 * narrow containers (the caller switches the CSS grid — see Config reference).
 * Hovering a card fires onHover(layer) so the caller can emphasize the
 * matching marker class on the Territory pitch.
 *
 * NOT ALL SIX CARDS ARE SCRUB-REACTIVE — A DELIBERATE V1 LIMIT
 * Four metrics are simple aggregations over a single player's own credited
 * events, so they recompute live from whatever scrub-filtered `events` slice
 * the caller passes in update({ events }):
 *   - progressivePasses: count of Pass events with is_progressive.
 *   - xg: sum of shot_xg across Shot events (both now on every event thanks
 *     to extract_player_events.py's shot fields — this one used to require
 *     the summary extractor and no longer does).
 *   - pressuresAndRegains: count of Pressure events with pressure_regain.
 *   - duelsWonPct: % of Duel events with a winning outcome.
 *
 * xA, xGChain, and padjDefensiveActions genuinely cannot be recomputed from
 * one player's own event slice — they aggregate across OTHER players' shots/
 * possessions/team-possession-share, which the per-player fetch model
 * deliberately does not ship to the client (see extract_player_events.py's
 * "fetched on selection, not loaded and filtered client-side" design note).
 * These three come from the separate `summary` prop — extract_player_match_summary.py's
 * match-total output — and do NOT change as the scrubber moves. This is
 * flagged visually (a small "match total" label) rather than silently
 * pretending they're live.
 */

const WON_DUEL_OUTCOMES = new Set(["Won", "Success In Play"]);

/**
 * The four scrub-reactive metrics, computed from a player's own event slice.
 *
 * @param {Array<Object>} events - Scrub-filtered player_events array.
 * @returns {{ progressivePasses: number, xg: number, pressuresAndRegains: number,
 *   duelsWonPct: number | null }} The live-recomputable subset of the six metrics.
 */
function reactiveMetrics(events) {
  const passes = events.filter((e) => e.type === "Pass");
  const shots = events.filter((e) => e.type === "Shot");
  const pressures = events.filter((e) => e.type === "Pressure");
  const duels = events.filter((e) => e.type === "Duel");

  const progressivePasses = passes.filter((e) => e.is_progressive).length;
  const xg = shots.reduce((sum, e) => sum + (e.shot_xg ?? 0), 0);
  const pressuresAndRegains = pressures.filter((e) => e.pressure_regain).length;
  const won = duels.filter((e) => WON_DUEL_OUTCOMES.has(e.outcome)).length;
  const duelsWonPct = duels.length ? Math.round((1000 * won) / duels.length) / 10 : null;

  return { progressivePasses, xg, pressuresAndRegains, duelsWonPct };
}

/**
 * Format a number to a fixed decimal count, or an em dash when null/undefined.
 *
 * @param {number | null} value - Value to format.
 * @param {number} decimals - Fixed decimal places.
 * @returns {string} Formatted value, or "—" for null/undefined.
 */
function fmt(value, decimals = 0) {
  return value === null || value === undefined ? "—" : value.toFixed(decimals);
}

const CARD_DEFS = [
  {
    key: "progressivePasses", layer: "progressive_pass", label: "PROGRESSIVE PASSES",
    render: (r) => fmt(r.progressivePasses),
  },
  {
    key: "xg", layer: "shot", label: "xG",
    render: (r) => fmt(r.xg, 2),
  },
  {
    key: "xaXgChain", layer: "key_pass", label: "xA / xG CHAIN", isMatchTotal: true,
    render: (r, s) => `${fmt(s?.xa, 2)} / ${fmt(s?.xg_chain, 2)}`,
  },
  {
    key: "pressuresAndRegains", layer: "pressure", label: "PRESSURES + REGAINS",
    render: (r) => fmt(r.pressuresAndRegains),
  },
  {
    key: "padjDefensiveActions", layer: "defensive", label: "PADJ DEFENSIVE ACTIONS", isMatchTotal: true,
    render: (r, s) => fmt(s?.padj_defensive_actions, 1),
  },
  {
    key: "duelsWonPct", layer: "duel", label: "DUELS WON %",
    render: (r) => (r.duelsWonPct === null ? "—" : `${fmt(r.duelsWonPct, 0)}%`),
  },
];

/**
 * Render the six-card player stat-card row.
 *
 * @param {d3.Selection} selection - D3 selection of the container element
 *   (an HTML element — this component renders div children, not an SVG root).
 * @param {Object} data - `{ events, summary }`.
 * @param {Array<Object>} data.events - Scrub-filtered player_events array,
 *   feeding the four reactive metrics.
 * @param {Object} data.summary - The player's extract_player_match_summary.py
 *   output (`{ xa, xg_chain, padj_defensive_actions, ... }`), feeding the two
 *   match-total metrics. Unlike `events`, this does not need to be scrub-filtered.
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {Function|null} [config.onHover=null] - onHover(layer | null) fires
 *   on card hover/unhover, where layer matches actionFeed.js's classifyLayer
 *   vocabulary plus "defensive" (the PAdj card's combined defensive-action set).
 * @returns {{ container: d3.Selection, update: Function }}
 *   container — the card-row D3 selection.
 *   update({ data? }) — re-renders with a new `{ events, summary }` object.
 */
export function createPlayerStatCards(selection, data, config = {}) {
  const { onHover = null } = config;

  const container = selection.append("div")
    .attr("class", "player-stat-cards")
    .style("display", "grid")
    .style("grid-template-columns", "repeat(3, 1fr)")
    .style("gap", "10px")
    .style("font-family", "Geist Mono, monospace");

  let currentData = data;

  function render() {
    container.selectAll("*").remove();

    const reactive = reactiveMetrics(currentData.events ?? []);
    const summary = currentData.summary ?? null;

    const cards = container.selectAll(".stat-card")
      .data(CARD_DEFS, (d) => d.key)
      .join("div")
      .attr("class", "stat-card")
      .style("border", "1px solid #E5E5E5")
      .style("border-radius", "8px")
      .style("padding", "10px 12px")
      .style("cursor", "pointer");

    cards.append("div")
      .attr("class", "stat-card-label")
      .style("font-size", "9px")
      .style("letter-spacing", "0.04em")
      .style("color", "#8A8578")
      .text((d) => d.label);

    cards.append("div")
      .attr("class", "stat-card-value")
      .style("font-size", "20px")
      .style("font-weight", "600")
      .style("color", "#171717")
      .text((d) => d.render(reactive, summary));

    cards.filter((d) => d.isMatchTotal)
      .append("div")
      .attr("class", "stat-card-note")
      .style("font-size", "9px")
      .style("color", "#A39E95")
      .text("match total");

    cards
      .on("mouseover", (event, d) => onHover && onHover(d.layer))
      .on("mouseout", () => onHover && onHover(null));
  }

  render();

  /**
   * Re-render with a new `{ events, summary }` object.
   *
   * @param {Object} [next={}] - Partial update.
   * @param {Object} [next.data] - Replacement `{ events, summary }` object.
   */
  function update(next = {}) {
    if (next.data !== undefined) currentData = next.data;
    render();
  }

  return { container, update };
}
