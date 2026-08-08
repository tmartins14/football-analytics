/**
 * eventScatter.js — general-purpose event scatter overlay for a StatsBomb pitch.
 *
 * Composes on pitch.js: receives an existing pitch object and draws event markers
 * onto pitch.g using pitch.px() for coordinate conversion. Does not create or
 * re-render the pitch.
 *
 * Events are rendered as colored circles at their (x, y) origin. Events that carry
 * end coordinates (Pass, Carry, Shot) also draw an arrow from origin to destination.
 * Arrows are rendered first (behind circles), so the origin dot sits on top.
 *
 * EVENT TYPE ENCODING — color encodes semantic category:
 *   Ball movement (Pass, Carry, Dribble):                    #9F1239  red
 *   Defensive   (Pressure, Duel, Interception, Block, etc.): #1E3A5F  navy
 *   Terminal    (Shot, Foul Won, Foul Committed):             #525252  gray
 *   Other / unmapped:                                         #E5E5E5  light gray
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

// ── Color encoding ────────────────────────────────────────────────────────────

const _TYPE_CATEGORY = {
  // Ball movement
  Pass:    "movement",
  Carry:   "movement",
  Dribble: "movement",
  // Defensive
  Pressure:       "defense",
  Duel:           "defense",
  Interception:   "defense",
  "Ball Recovery": "defense",
  Clearance:      "defense",
  Block:          "defense",
  // Terminal
  Shot:             "terminal",
  "Foul Won":       "terminal",
  "Foul Committed": "terminal",
};

const _CATEGORY_COLOR = {
  movement: "#9F1239",
  defense:  "#1E3A5F",
  terminal: "#525252",
  other:    "#E5E5E5",
};

// Marker IDs are prefixed "es-" to avoid collisions with progressiveMap's markers.
const _MARKER_IDS = {
  "#9F1239": "es-arrow-red",
  "#1E3A5F": "es-arrow-navy",
  "#525252": "es-arrow-gray",
  "#E5E5E5": "es-arrow-light",
};

function _typeColor(eventType) {
  const cat = _TYPE_CATEGORY[eventType] ?? "other";
  return _CATEGORY_COLOR[cat];
}

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
 * Events are color-coded by semantic category (see module comment). Events with
 * end_x/end_y (Pass, Carry, Shot) render an arrow from origin to destination;
 * all events render a filled circle at their origin (x, y).
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
 *   than rendering "undefined").
 * @param {Object} [config={}] - Rendering options.
 * @param {number}   [config.markerRadius=5]          - Circle radius in pixels.
 * @param {boolean}  [config.showArrows=true]          - Draw arrow lines for events
 *   that have end_x/end_y.
 * @param {boolean}  [config.includeBallReceipt=false] - Include "Ball Receipt*" events.
 *   Excluded by default because they cluster on top of Pass end-points.
 * @param {Function} [config.colorScale]               - Override the default event_type
 *   → color function. Receives event_type string, returns a CSS color string.
 * @returns {{ g: d3.Selection, update: function }}
 *   g:      The <g class="es"> group appended to pitch.g.
 *   update: function({ events?, filter? }) — re-renders with a new event array
 *           (`events`) or a predicate function (`filter`). Omit both to re-render
 *           with current state. Omit one key to keep its previous value.
 */
export function createEventScatter(pitch, data, config = {}) {
  const {
    markerRadius       = 5,
    showArrows         = true,
    includeBallReceipt = false,
    colorScale         = _typeColor,
  } = config;

  const { svg, g, px } = pitch;

  // Ensure <defs> exists; re-use if already present (e.g. from the pitch itself).
  let defs = svg.select("defs");
  if (defs.empty()) defs = svg.append("defs");

  // Register arrow markers for each category color (guard against duplicates).
  Object.entries(_MARKER_IDS).forEach(([color, id]) => {
    if (defs.select(`#${id}`).empty()) {
      _addMarker(defs, id, color);
    }
  });

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

    // ── Arrow lines (rendered behind origin dots) ─────────────────────────────
    withArrows.forEach(e => {
      const [x0, y0] = px(e.x,     e.y);
      const [x1, y1] = px(e.end_x, e.end_y);
      const color    = colorScale(e.event_type);
      const markerId = _MARKER_IDS[color] ?? "es-arrow-gray";

      scatterG.append("line")
        .attr("x1", x0).attr("y1", y0)
        .attr("x2", x1).attr("y2", y1)
        .attr("stroke",       color)
        .attr("stroke-width", 1.5)
        .attr("stroke-opacity", 0.6)
        .attr("stroke-linecap", "round")
        .attr("marker-end",   `url(#${markerId})`)
        .on("mouseover", (ev) => _showTooltip(ev, e))
        .on("mousemove", _moveTooltip)
        .on("mouseout",  _hideTooltip);
    });

    // ── Origin dots (all events, rendered on top of arrows) ───────────────────
    [...withArrows, ...withoutArrows].forEach(e => {
      const [cx, cy] = px(e.x, e.y);
      const color    = colorScale(e.event_type);

      // Outer ring for events with an outcome (completed pass = no ring, failure = ring).
      const isFailedPass = e.event_type === "Pass" && e.outcome != null;
      if (isFailedPass) {
        scatterG.append("circle")
          .attr("cx", cx).attr("cy", cy)
          .attr("r",  markerRadius + 3)
          .attr("fill", "none")
          .attr("stroke", color)
          .attr("stroke-width", 1)
          .attr("stroke-opacity", 0.5);
      }

      scatterG.append("circle")
        .attr("cx", cx).attr("cy", cy)
        .attr("r",  markerRadius)
        .attr("fill", color)
        .attr("fill-opacity", 0.85)
        .style("cursor", "default")
        .on("mouseover", (ev) => _showTooltip(ev, e))
        .on("mousemove", _moveTooltip)
        .on("mouseout",  _hideTooltip);
    });
  }

  return { g: scatterG, update };
}
