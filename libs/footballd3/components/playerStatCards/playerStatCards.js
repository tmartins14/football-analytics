/**
 * playerStatCards.js — six-metric stat-card row for one player.
 *
 * Six cards: progressive passes, xG, xA/xGChain (one combined card), pressures
 * + regains, PAdj defensive actions, duels won %. 3x2 on desktop, 2x3 on
 * narrow containers (the caller switches the CSS grid — see Config reference).
 * Hovering a card fires onHover(layer) so the caller can emphasize the
 * matching marker class on the Territory pitch.
 *
 * ALL SIX CARDS ARE SCRUB-REACTIVE
 * Every metric recomputes live from whatever scrub-filtered `events` slice
 * the caller passes into update({ data: { events } }):
 *   - progressivePasses: count of Pass events with is_progressive.
 *   - xg: sum of shot_xg across Shot events.
 *   - xa: sum of assisted_shot_xg across Pass events (the xG of whatever shot
 *     each key-pass fed — extract_player_events.py's own pass->shot join, on
 *     the event record already, no separate lookup needed).
 *   - xgChain: sum of possession_shot_xg across the DISTINCT possessions
 *     touched (deduped by `possession` id — every event in a possession
 *     carries the same possession_shot_xg value, so summing per-event would
 *     double count a possession the player touched more than once).
 *   - pressuresAndRegains: count of Pressure events with pressure_regain.
 *   - duelsWonPct: % of Duel events with a winning outcome.
 *   - padjDefensiveActions: raw defensive-action count (Pressure, Duel,
 *     Interception, Block, Ball Recovery, Clearance) from `events`, scaled by
 *     the opponent's possession share AT THE SCRUBBED MINUTE — the one metric
 *     that can't live on a single player's own event record, since it needs
 *     whole-match opponent-possession context. Sourced from the separate
 *     `possessionShares` prop (extract_possession_shares.py's match-level,
 *     not per-player, minute-bucketed output) plus `playerTeam` (to know
 *     which of the bucket's two teams is "opponent") and `scrubbedMinute`
 *     (to pick the nearest bucket <= that minute). Returns null (renders
 *     "—") when either input is missing, rather than a stale/wrong number.
 *
 * This replaces an earlier design where xA/xGChain/PAdj came from a
 * per-player extract_player_match_summary.py file as fixed match-totals —
 * superseded once assisted_shot_xg/possession_shot_xg landed on
 * extract_player_events.py's own per-event record and
 * extract_possession_shares.py supplied the one genuinely match-wide input.
 */

const DEFENSIVE_ACTION_TYPES = new Set([
  "Pressure", "Duel", "Interception", "Block", "Ball Recovery", "Clearance",
]);
const WON_DUEL_OUTCOMES = new Set(["Won", "Success In Play"]);
const POSSESSION_BASELINE_PCT = 50;

/**
 * The possession-share bucket in effect at a given scrub minute.
 *
 * @param {Object|null} possessionShares - extract_possession_shares.py's
 *   `{ buckets: [{ upto_minute, team_possession_pct }, ...] }` output, or null.
 * @param {number} scrubbedMinute - Current scrub position.
 * @returns {Object|null} The bucket with the largest upto_minute <=
 *   scrubbedMinute, or null if none qualifies yet (very start of the match)
 *   or possessionShares itself is absent.
 */
function nearestPossessionBucket(possessionShares, scrubbedMinute) {
  const buckets = possessionShares?.buckets ?? [];
  let nearest = null;
  for (const bucket of buckets) {
    if (bucket.upto_minute > scrubbedMinute) break;
    nearest = bucket;
  }
  return nearest;
}

/**
 * Possession-adjusted defensive-action count at the scrubbed minute.
 *
 * raw_count / (opponent_possession_pct / 50) — a player facing a
 * below-50%-possession opponent (their own team dominated the ball, so there
 * were fewer defensive opportunities) gets their raw count scaled up, and
 * vice versa. Mirrors the formula extract_player_match_summary.py used
 * match-wide, now evaluated at the nearest possession-share bucket instead.
 *
 * @param {Array<Object>} events - Scrub-filtered player_events array.
 * @param {Object|null} possessionShares - extract_possession_shares.py's output.
 * @param {string|null} playerTeam - The player's own team name (must match
 *   one of the bucket's team_possession_pct keys).
 * @param {number} scrubbedMinute - Current scrub position.
 * @returns {number|null} Possession-adjusted count, or null when
 *   possessionShares/playerTeam aren't available yet or no bucket qualifies.
 */
function padjDefensiveActions(events, possessionShares, playerTeam, scrubbedMinute) {
  if (!possessionShares || !playerTeam) return null;
  const bucket = nearestPossessionBucket(possessionShares, scrubbedMinute);
  if (!bucket) return null;

  const opponentEntry = Object.entries(bucket.team_possession_pct)
    .find(([team]) => team !== playerTeam);
  if (!opponentEntry) return null;
  const opponentPct = opponentEntry[1];

  const rawCount = events.filter((e) => DEFENSIVE_ACTION_TYPES.has(e.type)).length;
  const floorPct = Math.max(opponentPct, 1);
  return rawCount / (floorPct / POSSESSION_BASELINE_PCT);
}

/**
 * All six metrics, computed from a player's own scrub-filtered event slice
 * plus the shared possession-share buckets.
 *
 * @param {Array<Object>} events - Scrub-filtered player_events array.
 * @param {Object|null} possessionShares - extract_possession_shares.py's output.
 * @param {string|null} playerTeam - The player's own team name.
 * @param {number} scrubbedMinute - Current scrub position.
 * @returns {{ progressivePasses: number, xg: number, xa: number,
 *   xgChain: number, pressuresAndRegains: number, duelsWonPct: number|null,
 *   padjDefensiveActions: number|null }} All six stat-card values.
 */
function computeMetrics(events, possessionShares, playerTeam, scrubbedMinute) {
  const passes = events.filter((e) => e.type === "Pass");
  const shots = events.filter((e) => e.type === "Shot");
  const pressures = events.filter((e) => e.type === "Pressure");
  const duels = events.filter((e) => e.type === "Duel");

  const progressivePasses = passes.filter((e) => e.is_progressive).length;
  const xg = shots.reduce((sum, e) => sum + (e.shot_xg ?? 0), 0);
  const xa = passes.reduce((sum, e) => sum + (e.assisted_shot_xg ?? 0), 0);

  const possessionXgById = new Map();
  for (const e of events) {
    if (!possessionXgById.has(e.possession)) {
      possessionXgById.set(e.possession, e.possession_shot_xg ?? 0);
    }
  }
  const xgChain = [...possessionXgById.values()].reduce((sum, v) => sum + v, 0);

  const pressuresAndRegains = pressures.filter((e) => e.pressure_regain).length;
  const won = duels.filter((e) => WON_DUEL_OUTCOMES.has(e.outcome)).length;
  const duelsWonPct = duels.length ? Math.round((1000 * won) / duels.length) / 10 : null;

  return {
    progressivePasses,
    xg,
    xa,
    xgChain,
    pressuresAndRegains,
    duelsWonPct,
    padjDefensiveActions: padjDefensiveActions(events, possessionShares, playerTeam, scrubbedMinute),
  };
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
    render: (m) => fmt(m.progressivePasses),
  },
  {
    key: "xg", layer: "shot", label: "xG",
    render: (m) => fmt(m.xg, 2),
  },
  {
    key: "xaXgChain", layer: "key_pass", label: "xA / xG CHAIN",
    render: (m) => `${fmt(m.xa, 2)} / ${fmt(m.xgChain, 2)}`,
  },
  {
    key: "pressuresAndRegains", layer: "pressure", label: "PRESSURES + REGAINS",
    render: (m) => fmt(m.pressuresAndRegains),
  },
  {
    key: "padjDefensiveActions", layer: "defensive", label: "PADJ DEFENSIVE ACTIONS",
    render: (m) => fmt(m.padjDefensiveActions, 1),
  },
  {
    key: "duelsWonPct", layer: "duel", label: "DUELS WON %",
    render: (m) => (m.duelsWonPct === null ? "—" : `${fmt(m.duelsWonPct, 0)}%`),
  },
];

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

    const events = currentData.events ?? [];
    const scrubbedMinute = currentData.scrubbedMinute
      ?? Math.max(0, ...events.map((e) => e.minute));
    const metrics = computeMetrics(
      events, currentData.possessionShares ?? null, currentData.playerTeam ?? null, scrubbedMinute
    );

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
      .text((d) => d.render(metrics));

    cards
      .on("mouseover", (event, d) => onHover && onHover(d.layer))
      .on("mouseout", () => onHover && onHover(null));
  }

  render();

  /**
   * Re-render with a new data object.
   *
   * @param {Object} [next={}] - Partial update.
   * @param {Object} [next.data] - Replacement `{ events, possessionShares,
   *   playerTeam, scrubbedMinute }` object — merged over the previous data,
   *   so passing only `{ events }` on every scrub tick is enough.
   */
  function update(next = {}) {
    if (next.data !== undefined) currentData = { ...currentData, ...next.data };
    render();
  }

  return { container, update };
}
