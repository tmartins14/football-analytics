/**
 * timelineStrip.js — single-possession elapsed-seconds event timeline.
 *
 * Renders a horizontal strip showing one possession's events positioned on a real
 * elapsed-seconds axis. This is a standalone chart — it does NOT compose on pitch.js.
 * The unit is one possession; the axis is wall-clock tempo within that possession.
 *
 * READING THE STRIP
 * X position = true elapsed seconds from the possession's first event. A short 3-second
 * possession will look cramped; a 70-second build-up shows tempo clearly — that's
 * intentional. The strip is a narrative device, not a frequency histogram.
 *
 * GLYPHS
 * Each event is a colored circle with a single letter abbreviating its type:
 *   P = Pass        C = Carry       S = Shot        D = Duel / Pressure
 *   I = Interception  B = Ball Recovery / Block   X = Clearance
 *   R = Ball Receipt*   ? = unmapped types
 *
 * Color encoding matches eventScatter.js categories:
 *   Movement (Pass, Carry, Dribble):    #9F1239  red
 *   Defensive (Pressure, Duel, etc.):   #1E3A5F  navy
 *   Terminal  (Shot, Foul):             #525252  gray
 *   Other / unmapped:                   #E5E5E5  light gray
 *
 * COLLISION HANDLING
 * Events within 0.4s of each other are binned together and stacked vertically with
 * alternating offsets (index 0 at center, index 1 at −stackStep, index 2 at +stackStep,
 * …). The X position is always the true seconds value — never shifted.
 *
 * FUTURE LINKAGE
 * xScale is returned so a future cross-component selection slice can highlight the
 * corresponding seconds position when the user hovers an event on eventScatter.js.
 * That linkage is additive; no infrastructure is built here for it.
 */

import * as d3 from "d3";

// ── Shared encoding (mirrors eventScatter.js) ─────────────────────────────────

const _TYPE_CATEGORY = {
  Pass:    "movement",
  Carry:   "movement",
  Dribble: "movement",
  Pressure:        "defense",
  Duel:            "defense",
  Interception:    "defense",
  "Ball Recovery": "defense",
  Clearance:       "defense",
  Block:           "defense",
  Shot:             "terminal",
  "Foul Won":       "terminal",
  "Foul Committed": "terminal",
};

const _CATEGORY_COLOR = {
  movement: "#9F1239",
  defense:  "#1E3A5F",
  terminal: "#525252",
  other:    "#D4D4D4",
};

const _TYPE_LETTER = {
  Pass:            "P",
  Carry:           "C",
  Shot:            "S",
  Pressure:        "D",
  Duel:            "D",
  Interception:    "I",
  "Ball Recovery": "B",
  Block:           "B",
  Clearance:       "X",
  Dribble:         "Dr",
  "Dribbled Past": "Dp",
  "Ball Receipt*": "R",
  Dispossessed:    "Ds",
  "50/50":         "50",
};

function _typeColor(eventType) {
  const cat = _TYPE_CATEGORY[eventType] ?? "other";
  return _CATEGORY_COLOR[cat];
}

function _typeLetter(eventType) {
  return _TYPE_LETTER[eventType] ?? "?";
}

// ── Collision handling ────────────────────────────────────────────────────────

/**
 * Assign vertical stack offsets to events that overlap on the time axis.
 *
 * Events within BIN_WINDOW seconds of the bin's first event are grouped into
 * a bin. Within each bin, offsets alternate: center, −step, +step, −2×step, … .
 * The X position (seconds) is never modified.
 *
 * @param {Array}  events    - Array of event objects with a `seconds` field.
 * @param {number} binWindow - Max seconds gap to consider events part of the same bin.
 * @param {number} stackStep - Vertical pixels between stacked glyphs.
 * @returns {Array} Same events with an added `_stackY` offset field (pixels).
 */
function _assignStackOffsets(events, binWindow, stackStep) {
  const sorted = [...events].sort((a, b) => a.seconds - b.seconds);
  const result = [];
  let i = 0;
  while (i < sorted.length) {
    const binStart = sorted[i].seconds;
    const bin = [];
    while (i < sorted.length && sorted[i].seconds - binStart <= binWindow) {
      bin.push(sorted[i]);
      i++;
    }
    // Alternating offsets: 0, -1, +1, -2, +2, ... (× stackStep).
    bin.forEach((e, idx) => {
      const sign   = idx === 0 ? 0 : (idx % 2 === 1 ? -1 : 1);
      const level  = Math.ceil(idx / 2);
      result.push({ ...e, _stackY: sign * level * stackStep });
    });
  }
  return result;
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

const _tooltip = document.createElement("div");
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

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Render a single-possession elapsed-seconds timeline strip.
 *
 * Creates its own SVG inside the given selection. Does not compose on pitch.js.
 * Events are positioned on a real elapsed-seconds X axis; glyphs are colored circles
 * with a single-letter type abbreviation. Events within 0.4s of each other are
 * stacked vertically so nothing overlaps.
 *
 * The X axis is real tempo — a 3-second possession looks cramped and a 70-second
 * build-up spreads out clearly. This is intentional: the strip is a narrative device
 * showing when things happened, not how many.
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object}       data      - Possession JSON contract
 *   (possession_{match_id}_{possession}.json). Must expose an `events` array of
 *   { event_type, seconds, player, outcome }.
 * @param {Object}  [config={}]             - Rendering options.
 * @param {number}  [config.width=760]      - SVG width in pixels.
 * @param {number}  [config.height=120]     - SVG height in pixels. Should be large
 *   enough to accommodate vertical stacking (stackStep × max_cluster_depth × 2).
 * @param {Object}  [config.padding]        - Inner padding in pixels.
 *   Defaults: { top: 24, right: 24, bottom: 32, left: 24 }.
 * @param {number}  [config.glyphRadius=8]  - Glyph circle radius in pixels.
 * @param {number}  [config.stackStep=20]   - Vertical offset between stacked glyphs.
 * @param {number}  [config.binWindow=0.4]  - Seconds window for collision binning.
 * @param {Function} [config.colorScale]    - Override event_type → color function.
 * @returns {{ svg: d3.Selection, g: d3.Selection, xScale: d3.ScaleLinear, update: function }}
 *   svg:    The created SVG selection.
 *   g:      The main <g> group inside the SVG.
 *   xScale: The elapsed-seconds → pixel scale (exposed for future cross-component linkage).
 *   update: function({ events? }) — re-renders with a new event array. Omit to re-render
 *           with current state.
 */
export function createTimelineStrip(selection, data, config = {}) {
  const {
    width       = 760,
    height      = 120,
    padding     = { top: 24, right: 24, bottom: 32, left: 24 },
    glyphRadius = 8,
    stackStep   = 20,
    binWindow   = 0.4,
    colorScale  = _typeColor,
  } = config;

  const innerW = width  - padding.left - padding.right;
  const innerH = height - padding.top  - padding.bottom;

  const svg = selection.append("svg")
    .attr("width",  width)
    .attr("height", height);

  svg.selectAll("*").remove();

  const g = svg.append("g")
    .attr("transform", `translate(${padding.left},${padding.top})`);

  const maxSec = Math.max(...data.events.map(e => e.seconds), 1);
  const xScale = d3.scaleLinear().domain([0, maxSec]).range([0, innerW]);

  // Baseline Y (center of the strip, where un-stacked glyphs sit).
  const midY = innerH / 2;

  let _events = data.events;

  renderAxis();
  render();

  function renderAxis() {
    g.append("line")
      .attr("x1", 0).attr("y1", midY)
      .attr("x2", innerW).attr("y2", midY)
      .attr("stroke", "#E5E5E5")
      .attr("stroke-width", 1);

    // Tick every second; label every 5 seconds for readability on longer possessions.
    const tickEvery = maxSec > 30 ? 5 : maxSec > 10 ? 2 : 1;
    const ticks = d3.range(0, Math.ceil(maxSec) + 1, tickEvery);

    ticks.forEach(t => {
      const x = xScale(t);
      g.append("line")
        .attr("x1", x).attr("y1", midY - 4)
        .attr("x2", x).attr("y2", midY + 4)
        .attr("stroke", "#D4D4D4")
        .attr("stroke-width", 1);

      g.append("text")
        .attr("x", x)
        .attr("y", innerH)
        .attr("text-anchor", "middle")
        .attr("font-family", "Geist Mono, monospace")
        .attr("font-size", "10px")
        .attr("fill", "#525252")
        .text(`${t}s`);
    });
  }

  /**
   * Re-render glyphs with a new event array.
   *
   * @param {Object} [opts={}]
   * @param {Array}  [opts.events] - Replace the displayed event array.
   */
  function update(opts = {}) {
    if (opts.events !== undefined) _events = opts.events;
    render();
  }

  function render() {
    g.selectAll(".ts-glyph-group").remove();

    const stacked = _assignStackOffsets(_events, binWindow, stackStep);

    stacked.forEach(e => {
      const cx     = xScale(e.seconds);
      const cy     = midY + e._stackY;
      const color  = colorScale(e.event_type);
      const letter = _typeLetter(e.event_type);

      // Invert label color for light-gray "other" events so text is readable.
      const labelColor = color === _CATEGORY_COLOR.other ? "#525252" : "#FAF7F0";

      const group = g.append("g").attr("class", "ts-glyph-group");

      group.append("circle")
        .attr("cx", cx)
        .attr("cy", cy)
        .attr("r",  glyphRadius)
        .attr("fill", color)
        .attr("fill-opacity", 0.88)
        .style("cursor", "default");

      group.append("text")
        .attr("x", cx)
        .attr("y", cy + 1)
        .attr("text-anchor",   "middle")
        .attr("dominant-baseline", "middle")
        .attr("font-family",   "Geist Mono, monospace")
        .attr("font-size",     letter.length > 1 ? "6px" : "8px")
        .attr("font-weight",   "600")
        .attr("fill", labelColor)
        .attr("pointer-events", "none")
        .text(letter);

      // Connector line from glyph to axis when stacked off-center.
      if (e._stackY !== 0) {
        group.append("line")
          .attr("x1", cx).attr("y1", cy + (e._stackY < 0 ? glyphRadius : -glyphRadius))
          .attr("x2", cx).attr("y2", midY)
          .attr("stroke", color)
          .attr("stroke-width", 1)
          .attr("stroke-opacity", 0.3)
          .attr("pointer-events", "none");
      }

      group
        .on("mouseover", (ev) => {
          const sec     = e.seconds.toFixed(2);
          const outcome = e.outcome ? ` · ${e.outcome}` : "";
          _tooltip.innerHTML =
            `<span style="font-weight:600">${e.player}</span><br>` +
            `${e.event_type}${outcome}<br>` +
            `<span style="color:#525252">+${sec}s</span>`;
          _tooltip.style.display = "block";
        })
        .on("mousemove", (ev) => {
          _tooltip.style.left = (ev.clientX + 14) + "px";
          _tooltip.style.top  = (ev.clientY - 28) + "px";
        })
        .on("mouseout", () => {
          _tooltip.style.display = "none";
        });
    });
  }

  return { svg, g, xScale, update };
}
