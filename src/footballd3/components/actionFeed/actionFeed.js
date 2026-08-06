/**
 * actionFeed.js — scrollable, sortable chronological log of one player's actions.
 *
 * Unlike every other footballd3 component, this one renders HTML rows (not
 * SVG) inside a fixed-height, scrollable container — a chronological log
 * reads and scrolls more naturally as DOM text than as SVG text nodes, and a
 * scroll container is native HTML behavior. Each row still gets a small
 * inline SVG for its signed xT-swing bar, matching the rest of the library's
 * visual language.
 *
 * LAYER CLASSIFICATION IS SHARED, NOT LOCAL
 * classifyLayer() is a named export (not a private helper) because the design
 * spec's layer-toggle chips ("Progressive pass | Key pass | Pressure | Duel |
 * Turnover | Shot") must filter BOTH the Territory pitch markers and this
 * feed identically — "Each chip isolates a marker class and filters the
 * Action feed" only holds if both consumers agree on what a "turnover" or
 * "key pass" event actually is. Import it wherever activeLayers filtering
 * happens, rather than re-deriving the classification.
 *
 * SIGNED xT-SWING BAR
 * Pass/Carry events use their own xt_delta (can be negative — a backward
 * safety pass). Shot events have no xt_delta (only Pass/Carry are credited,
 * per extract_player_events.py/extract_xt.py) but the design still wants a
 * bar for them, so Shot rows use shot_xg instead — always drawn on the
 * positive (gain) side, since a shot is inherently threat-positive. Every
 * other event type (Pressure, Duel, Interception, etc.) has no threat value
 * and renders a zero-width bar (a thin center tick, not an empty row) rather
 * than being hidden.
 */

import * as d3 from "d3";

const LAYER_COLORS = {
  shot:              "#525252",
  progressive_pass:  "#9F1239",
  key_pass:          "#F59E0B",
  pressure:          "#1E3A5F",
  duel:              "#1E3A5F",
  turnover:          "#78716C",
  other:             "#A39E95",
};

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
export function classifyLayer(event) {
  if (event.type === "Shot") return "shot";
  if (event.type === "Pass" && event.key_pass) return "key_pass";
  if ((event.type === "Pass" || event.type === "Carry") && event.is_progressive) {
    return "progressive_pass";
  }
  if (event.type === "Pressure") return "pressure";
  if (event.type === "Duel") return "duel";
  if (event.type === "Dispossessed" || event.type === "Miscontrol") return "turnover";
  return "other";
}

/**
 * The signed threat-swing value for one row's bar.
 *
 * @param {Object} event - One event from the player_events contract.
 * @returns {number} xt_delta for Pass/Carry, shot_xg (always >= 0) for Shot,
 *   0 for every other type.
 */
function swingValue(event) {
  if (event.type === "Shot") return event.shot_xg ?? 0;
  if (event.type === "Pass" || event.type === "Carry") return event.xt_delta ?? 0;
  return 0;
}

const SORT_KEYS = {
  minute: (e) => e.minute * 60 + e.second,
  xt:     (e) => swingValue(e),
};

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
export function createActionFeed(selection, data, config = {}) {
  let {
    height           = 320,
    sortBy           = "minute",
    sortDir          = "asc",
    highlightEventId = null,
    onHoverRow       = null,
  } = config;

  const container = selection.append("div")
    .attr("class", "action-feed")
    .style("height", `${height}px`)
    .style("overflow-y", "auto")
    .style("font-family", "Geist Mono, monospace")
    .style("font-size", "12px");

  let currentData = data;

  function render() {
    container.selectAll("*").remove();

    const events = [...(currentData.events ?? [])];
    const keyFn = SORT_KEYS[sortBy] ?? SORT_KEYS.minute;
    events.sort((a, b) => (sortDir === "desc" ? keyFn(b) - keyFn(a) : keyFn(a) - keyFn(b)));

    const maxAbsSwing = d3.max(events, (e) => Math.abs(swingValue(e))) || 1;
    const barScale = d3.scaleLinear().domain([0, maxAbsSwing]).range([0, 28]);

    const rows = container.selectAll(".action-feed-row")
      .data(events, (d) => d.event_id)
      .join("div")
      .attr("class", "action-feed-row")
      .style("display", "flex")
      .style("align-items", "center")
      .style("gap", "8px")
      .style("padding", "4px 8px")
      .style("cursor", "pointer")
      .style("background", (d) =>
        d.event_id === highlightEventId ? "rgba(245,158,11,0.15)" : "transparent"
      )
      .style("border-left", (d) =>
        `3px solid ${LAYER_COLORS[classifyLayer(d)] ?? LAYER_COLORS.other}`
      );

    rows.append("span")
      .style("width", "34px")
      .style("color", "#8A8578")
      .text((d) => `${d.minute}'`);

    rows.append("span")
      .style("flex", "0 0 90px")
      .style("color", "#171717")
      .text((d) => d.type);

    rows.append("span")
      .style("flex", "1 1 auto")
      .style("color", "#525252")
      .style("overflow", "hidden")
      .style("text-overflow", "ellipsis")
      .style("white-space", "nowrap")
      .text((d) => d.outcome ?? (d.type === "Pass" || d.type === "Carry" ? "Complete" : ""));

    const barCells = rows.append("span").style("flex", "0 0 60px");
    const barSvg = barCells.append("svg").attr("width", 60).attr("height", 14);
    const barCenter = 30;

    barSvg.append("line")
      .attr("x1", barCenter).attr("x2", barCenter).attr("y1", 0).attr("y2", 14)
      .attr("stroke", "#E5E5E5").attr("stroke-width", 1);

    barSvg.append("rect")
      .attr("y", 3).attr("height", 8)
      .attr("x", (d) => (swingValue(d) >= 0 ? barCenter : barCenter - barScale(-swingValue(d))))
      .attr("width", (d) => barScale(Math.abs(swingValue(d))))
      .attr("fill", (d) => (swingValue(d) >= 0 ? "#1E3A5F" : "#9F1239"));

    rows
      .on("mouseover", (event, d) => onHoverRow && onHoverRow(d.event_id))
      .on("mouseout", () => onHoverRow && onHoverRow(null));
  }

  render();

  /**
   * Re-render with new events, a new sort, and/or a new inbound highlight.
   *
   * @param {Object} [next={}] - Partial update.
   * @param {Object} [next.data] - Replacement `{ events: [...] }` object.
   * @param {string} [next.sortBy] - "minute" | "xt".
   * @param {string} [next.sortDir] - "asc" | "desc".
   * @param {string|null} [next.highlightEventId] - New inbound-highlight event_id.
   */
  function update(next = {}) {
    if (next.data !== undefined) currentData = next.data;
    if (next.sortBy !== undefined) sortBy = next.sortBy;
    if (next.sortDir !== undefined) sortDir = next.sortDir;
    if (next.highlightEventId !== undefined) highlightEventId = next.highlightEventId;
    render();
  }

  return { container, update };
}
