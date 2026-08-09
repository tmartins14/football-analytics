/**
 * eventScatter.js — general-purpose event scatter overlay for a StatsBomb pitch.
 *
 * Composes on pitch.js: receives an existing pitch object and draws event markers
 * onto pitch.g using pitch.px() for coordinate conversion. Does not create or
 * re-render the pitch.
 *
 * Events are rendered as shaped markers at their (x, y) origin. Events that carry
 * end coordinates (Pass, Carry, Shot) also draw an arrow from origin to destination.
 * Arrows are rendered first (behind markers), so the origin marker sits on top.
 *
 * EVENT TYPE ENCODING — shape encodes category, fill/hollow encodes outcome:
 * markers use CATEGORY_SHAPE (imported from actionFeed.js — the same shared
 * taxonomy/shape table its own row glyphs use, so the Territory pitch and the
 * Action Feed speak one consistent visual language) and render filled when
 * the event succeeded, hollow when it didn't. Classification and success are
 * re-derived locally (_classify/_isSuccessful below) rather than importing
 * classifyLayer/isSuccessfulEvent directly — this component's general
 * possession contract uses `event_type` (not `type`) and, for its other real
 * consumer (a possession-scoped showcase demo), doesn't carry
 * is_progressive/key_pass/is_goal at all. The category *keys* still match
 * classifyLayer's output exactly, so a caller that does have those fields
 * (e.g. TerritoryPanel.tsx, passing them through per-event) gets markers
 * that agree with the Action Feed's own classification.
 *
 * Ball Receipt* events are excluded by default (they cluster on top of Pass
 * end-points with no additional spatial information). Set includeBallReceipt: true
 * to include them.
 *
 * The component is designed to be general: it accepts any flat events array and
 * renders it. A possession is just one filtered event set; you can pass match-level
 * events, player-filtered events, or any other subset.
 *
 * The returned update() handle accepts a new event array or a filter function so
 * a later cross-component selection slice can highlight or isolate events without
 * rebuilding the component.
 */

import * as d3 from "d3";
import { CATEGORY_SHAPE } from "../actionFeed/actionFeed.js";

// ── Shape + outcome encoding ──────────────────────────────────────────────────

const _TURNOVER_TYPES = new Set(["Dispossessed", "Miscontrol"]);

/**
 * Classify one event into the app's shared layer taxonomy — mirrors
 * actionFeed.js's classifyLayer() exactly, adapted to this component's own
 * `event_type` field naming and to fields (`is_progressive`, `key_pass`)
 * that may simply be absent on this component's other, more general
 * consumer (see module comment).
 *
 * @param {Object} event - One event in this component's contract.
 * @returns {string} One of "shot", "progressive_pass", "key_pass",
 *   "pressure", "duel", "turnover", "other".
 */
function _classify(event) {
  const type = event.event_type;
  if (type === "Shot") return "shot";
  if (type === "Pass" && event.key_pass) return "key_pass";
  if ((type === "Pass" || type === "Carry") && event.is_progressive) return "progressive_pass";
  if (type === "Pressure") return "pressure";
  if (type === "Duel") return "duel";
  if (_TURNOVER_TYPES.has(type)) return "turnover";
  return "other";
}

/**
 * Whether an event succeeded — mirrors actionFeed.js's isSuccessfulEvent()
 * exactly, adapted to this component's `event_type`/`outcome` fields (no
 * `is_goal` field exists in the general possession contract, so a Shot's
 * success is read off `outcome === "Goal"` instead).
 *
 * @param {Object} event - One event in this component's contract.
 * @returns {boolean} true if the marker should render filled.
 */
function _isSuccessful(event) {
  const type = event.event_type;
  if (type === "Shot") return event.outcome === "Goal";
  if (type === "Duel") return !(event.outcome && /lost/i.test(event.outcome));
  if (type === "Pass" || type === "Carry") return event.outcome == null;
  return true;
}

// Single ink color for every marker now that shape (not color) encodes
// category — override via config.markerColor for theme integration.
const _MARKER_ID = "es-arrow";

// ── Shared tooltip ────────────────────────────────────────────────────────────
// Created lazily (not at module scope) so this file can be imported in a
// server-rendering context without touching `document` on the server — a
// module-top-level document.createElement() here previously crashed Next.js
// SSR the first time this component was actually used inside a Next.js app
// (ReferenceError: document is not defined). Every other footballd3
// component already uses this lazy pattern; this brings eventScatter.js
// into line with it.

let _tooltip;
function getTooltip() {
  // isConnected (not just truthiness) so the tooltip gets re-appended if its
  // old parent was ever removed from the document — real apps never nuke
  // document.body wholesale, but this keeps the singleton correct if they did.
  if (!_tooltip || !_tooltip.isConnected) {
    _tooltip = document.createElement("div");
    Object.assign(_tooltip.style, {
      position:      "fixed",
      pointerEvents: "none",
      display:       "none",
      background:    "#FAF7F0",
      border:        "1px solid #E5E5E5",
      borderRadius:  "2px",
      padding:       "8px 10px",
      fontFamily:    "Geist Mono, monospace",
      fontSize:      "12px",
      lineHeight:    "1.6",
      color:         "#171717",
      whiteSpace:    "nowrap",
      zIndex:        "100",
    });
    document.body.appendChild(_tooltip);
  }
  return _tooltip;
}

function _showTooltip(event, d) {
  const outcome = d.outcome ? ` · ${d.outcome}` : "";
  // Prefer an absolute match minute (whole-match/single-player consumers,
  // e.g. TerritoryPanel.tsx) over the possession-relative elapsed-seconds
  // format (the showcase gallery's per-possession consumer, where multiple
  // players' events share one possession and "+X.Xs since it started" is
  // the meaningful timestamp) — a caller supplies whichever fits its data.
  const time = typeof d.minute === "number" ? `${d.minute}'` : `+${d.seconds.toFixed(1)}s`;
  const playerLine = d.player ? `<span style="font-weight:600">${d.player}</span><br>` : "";
  const tooltip = getTooltip();
  tooltip.innerHTML =
    playerLine +
    `${d.event_type}${outcome}<br>` +
    `<span style="color:#525252">${time}</span>`;
  tooltip.style.display = "block";
}

function _moveTooltip(event) {
  const tooltip = getTooltip();
  tooltip.style.left = (event.clientX + 14) + "px";
  tooltip.style.top  = (event.clientY - 28) + "px";
}

function _hideTooltip() {
  getTooltip().style.display = "none";
}

// ── Marker helpers ────────────────────────────────────────────────────────────

/**
 * Append an SVG arrowhead marker to a <defs> selection.
 *
 * @param {d3.Selection} defs  - D3 selection of the <defs> element.
 * @param {string}       id    - Marker element id attribute.
 * @param {string}       color - Fill color for the arrowhead.
 */
function _addMarker(defs, id, color) {
  defs.append("marker")
    .attr("id",           id)
    .attr("viewBox",      "0 -4 8 8")
    .attr("refX",         8)
    .attr("refY",         0)
    .attr("markerWidth",  4)
    .attr("markerHeight", 4)
    .attr("orient",       "auto")
    .append("path")
    .attr("d",    "M0,-4L8,0L0,4Z")
    .attr("fill", color);
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Render event markers onto an existing pitch as a scatter overlay.
 *
 * Appends a <g class="es"> group to pitch.g. Does not touch the pitch background
 * or markings. Call createPitch() first and pass its return value as `pitch`.
 *
 * Events are shape-coded by semantic category and filled/hollow by outcome
 * (see module comment). Events with end_x/end_y (Pass, Carry, Shot) render
 * an arrow from origin to destination; all events render a shaped marker at
 * their origin (x, y).
 *
 * @param {Object} pitch - Return value of createPitch(). Must expose { svg, g, px }.
 * @param {Object} data  - Possession JSON contract (possession_{match_id}_{possession}.json)
 *   or any object with an `events` array of { event_type, x, y, end_x, end_y,
 *   outcome }, plus EITHER `minute` (an absolute match minute, shown as
 *   `{minute}'` in the tooltip — for whole-match/single-player consumers) OR
 *   `seconds` (possession-relative elapsed seconds, shown as `+X.Xs` — for
 *   per-possession consumers where `minute` isn't meaningful per event).
 *   `player` is optional — omit it when every event already belongs to one
 *   known player (the tooltip's player-name line is skipped entirely rather
 *   than rendering "undefined"). `is_progressive`/`key_pass` are optional —
 *   when present, they let shape-classification agree exactly with
 *   actionFeed.js's classifyLayer() for the same events (see module comment).
 * @param {Object} [config={}] - Rendering options.
 * @param {number}   [config.markerRadius=5]          - Marker size scale in pixels
 *   (roughly the equivalent radius of the old circle marker).
 * @param {string}   [config.markerColor="#171717"]    - Single ink color for every
 *   marker/arrow — shape and fill/hollow now carry the encoding, not color.
 * @param {boolean}  [config.showArrows=true]          - Draw arrow lines for events
 *   that have end_x/end_y.
 * @param {boolean}  [config.includeBallReceipt=false] - Include "Ball Receipt*" events.
 *   Excluded by default because they cluster on top of Pass end-points.
 * @returns {{ g: d3.Selection, update: function }}
 *   g:      The <g class="es"> group appended to pitch.g.
 *   update: function({ events?, filter? }) — re-renders with a new event array
 *           (`events`) or a predicate function (`filter`). Omit both to re-render
 *           with current state. Omit one key to keep its previous value.
 */
export function createEventScatter(pitch, data, config = {}) {
  const {
    markerRadius       = 5,
    markerColor        = "#171717",
    showArrows         = true,
    includeBallReceipt = false,
  } = config;

  const { svg, g, px } = pitch;

  // Ensure <defs> exists; re-use if already present (e.g. from the pitch itself).
  let defs = svg.select("defs");
  if (defs.empty()) defs = svg.append("defs");

  // A single arrow marker now that there's one ink color (guard against duplicates).
  if (defs.select(`#${_MARKER_ID}`).empty()) {
    _addMarker(defs, _MARKER_ID, markerColor);
  }

  const scatterG = g.append("g").attr("class", "es");

  let _events = data.events;
  let _filter = null;

  render();

  /**
   * Re-render the scatter with a new event array or filter predicate.
   *
   * @param {Object} [opts={}]
   * @param {Array}    [opts.events] - Replace the event array entirely.
   * @param {Function} [opts.filter] - Predicate (event) => boolean applied to
   *   the current event array. Replaces any previously set filter.
   */
  function update(opts = {}) {
    if (opts.events !== undefined) _events = opts.events;
    if (opts.filter !== undefined) _filter = opts.filter;
    render();
  }

  function render() {
    scatterG.selectAll("*").remove();

    let visible = _events;
    if (!includeBallReceipt) {
      visible = visible.filter(e => e.event_type !== "Ball Receipt*");
    }
    if (_filter) {
      visible = visible.filter(_filter);
    }

    const withArrows    = visible.filter(e => showArrows && e.end_x != null && e.end_y != null);
    const withoutArrows = visible.filter(e => !showArrows || e.end_x == null || e.end_y == null);

    // ── Arrow lines (rendered behind origin markers) ──────────────────────────
    withArrows.forEach(e => {
      const [x0, y0] = px(e.x,     e.y);
      const [x1, y1] = px(e.end_x, e.end_y);

      scatterG.append("line")
        .attr("x1", x0).attr("y1", y0)
        .attr("x2", x1).attr("y2", y1)
        .attr("stroke",       markerColor)
        .attr("stroke-width", 1.5)
        .attr("stroke-opacity", 0.6)
        .attr("stroke-linecap", "round")
        .attr("marker-end",   `url(#${_MARKER_ID})`)
        .on("mouseover", (ev) => _showTooltip(ev, e))
        .on("mousemove", _moveTooltip)
        .on("mouseout",  _hideTooltip);
    });

    // ── Origin markers (all events, rendered on top of arrows) ───────────────
    // Shape encodes category (CATEGORY_SHAPE via _classify); fill vs. hollow
    // encodes outcome (_isSuccessful) — see module comment.
    const symbolSize = 4 * markerRadius * markerRadius;
    [...withArrows, ...withoutArrows].forEach(e => {
      const [cx, cy] = px(e.x, e.y);
      const shape = CATEGORY_SHAPE[_classify(e)] ?? CATEGORY_SHAPE.other;
      const filled = _isSuccessful(e);

      scatterG.append("path")
        .attr("class", "es-marker")
        .attr("transform", `translate(${cx},${cy})`)
        .attr("d", d3.symbol().type(shape).size(symbolSize)())
        .attr("fill", filled ? markerColor : "none")
        .attr("fill-opacity", 0.85)
        .attr("stroke", markerColor)
        .attr("stroke-width", filled ? 0 : 1.5)
        .style("cursor", "default")
        .on("mouseover", (ev) => _showTooltip(ev, e))
        .on("mousemove", _moveTooltip)
        .on("mouseout",  _hideTooltip);
    });
  }

  return { g: scatterG, update };
}
