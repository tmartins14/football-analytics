/**
 * scrubber.js — master minute-scrubber for driving a cross-component match view.
 *
 * Standalone chart — creates its own SVG inside the given selection, does not
 * compose on pitch.js. Renders a horizontal 0–maxMinute track with a draggable
 * playhead. Every interaction (drag, click on the track, arrow-key nudge) calls
 * config.onScrub(minute) — this component is a CONTROLLER, not a display: it owns
 * no rendering logic for match data itself, it only reports "the scrubbed minute
 * changed" so sibling components can filter/update in response.
 *
 * This is intentionally a separate component from timelineStrip.js rather than an
 * extension of it. timelineStrip.js's whole purpose is narrative tempo within one
 * possession — a real elapsed-seconds axis sized for a handful of events, with a
 * read-only future-linkage design (xScale exposed for a sibling to read, not for
 * this component to drive others). A 0–90+-minute master scrubber that WRITES to
 * five sibling components is a different domain scale and a different
 * responsibility; conflating the two would double timelineStrip.js's branching for
 * two genuinely different concerns.
 *
 * DENSITY HINTS
 * Passing an `events` array (any objects with a `minute` field — e.g. a player's
 * event stream) draws light tick marks at each event's minute along the track,
 * purely as a visual density hint. This does not filter or interpret the events —
 * it only reads the minute field to place a mark.
 */

import * as d3 from "d3";

const _STEP_MINUTES = [0, 15, 30, 45, 60, 75, 90];

/**
 * Render a master minute-scrubber with a draggable playhead.
 *
 * Creates a standalone SVG inside the given selection. The playhead can be
 * moved by dragging, by clicking anywhere on the track, or via ArrowLeft/
 * ArrowRight when the handle has focus (1-minute steps; Shift+Arrow for
 * 5-minute steps). Every move calls config.onScrub(minute).
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {number}   [config.width=760]        - SVG width in pixels.
 * @param {number}   [config.height=56]        - SVG height in pixels.
 * @param {Object}   [config.padding]          - Inner padding in pixels.
 *   Defaults: { top: 10, right: 20, bottom: 22, left: 20 }.
 * @param {number}   [config.minMinute=0]      - Track domain minimum.
 * @param {number}   [config.maxMinute=94]     - Track domain maximum.
 * @param {number}   [config.initialMinute]    - Starting playhead position.
 *   Defaults to maxMinute (full match/window revealed).
 * @param {Array}    [config.events=[]]        - Objects with a `minute` field,
 *   used only to draw density-hint ticks along the track.
 * @param {Function} [config.onScrub]          - onScrub(minute): called with the
 *   new minute on every drag/click/keyboard move.
 * @param {string}   [config.trackColor="#E5E5E5"]   - Unplayed track color.
 * @param {string}   [config.playedColor="#9F1239"]  - Played (0..current) track color.
 * @param {string}   [config.handleColor="#9F1239"]  - Playhead handle fill color.
 * @param {number}   [config.handleRadius=8]         - Playhead handle radius in pixels.
 * @returns {{ svg: d3.Selection, g: d3.Selection, xScale: d3.ScaleLinear,
 *   update: function, seek: function }}
 *   svg:    The created SVG selection.
 *   g:      The main <g> group inside the SVG.
 *   xScale: The minute → pixel scale.
 *   update: function({ events? }) — replace the density-hint event array.
 *   seek:   function(minute) — programmatically move the playhead without
 *           firing onScrub (for initialization/sync from external state).
 */
export function createScrubber(selection, config = {}) {
  const {
    width         = 760,
    height        = 56,
    padding       = { top: 10, right: 20, bottom: 22, left: 20 },
    minMinute     = 0,
    maxMinute     = 94,
    initialMinute = config.maxMinute ?? 94,
    events        = [],
    onScrub,
    trackColor    = "#E5E5E5",
    playedColor   = "#9F1239",
    handleColor   = "#9F1239",
    handleRadius  = 8,
  } = config;

  const innerW = width  - padding.left - padding.right;
  const innerH = height - padding.top  - padding.bottom;
  const midY   = innerH / 2;

  const svg = selection.append("svg")
    .attr("width", width)
    .attr("height", height);

  const g = svg.append("g")
    .attr("transform", `translate(${padding.left},${padding.top})`);

  const xScale = d3.scaleLinear().domain([minMinute, maxMinute]).range([0, innerW]).clamp(true);

  let _events  = events;
  let _minute  = Math.max(minMinute, Math.min(maxMinute, initialMinute));

  const trackG   = g.append("g").attr("class", "scrub-track");
  const tickG    = g.append("g").attr("class", "scrub-ticks");
  const densityG = g.append("g").attr("class", "scrub-density");
  const playedG  = g.append("g").attr("class", "scrub-played");
  const handleG  = g.append("g").attr("class", "scrub-handle");

  renderTrack();
  renderTicks();
  renderDensity();
  renderPlayed();
  renderHandle();
  attachInteraction();

  /**
   * Draw the full-width unplayed track line.
   */
  function renderTrack() {
    trackG.selectAll("*").remove();
    trackG.append("line")
      .attr("x1", 0).attr("y1", midY)
      .attr("x2", innerW).attr("y2", midY)
      .attr("stroke", trackColor)
      .attr("stroke-width", 3)
      .attr("stroke-linecap", "round");
  }

  /**
   * Draw minute tick marks and labels at standard 15-minute intervals, plus
   * the true final minute if the match ran long (added time).
   */
  function renderTicks() {
    tickG.selectAll("*").remove();
    const ticks = maxMinute > 90
      ? [..._STEP_MINUTES.filter(t => t <= maxMinute), maxMinute]
      : _STEP_MINUTES.filter(t => t <= maxMinute);

    ticks.forEach(t => {
      const x = xScale(t);
      tickG.append("line")
        .attr("x1", x).attr("y1", midY - 3)
        .attr("x2", x).attr("y2", midY + 3)
        .attr("stroke", "#D4D4D4")
        .attr("stroke-width", 1);
      tickG.append("text")
        .attr("x", x)
        .attr("y", innerH)
        .attr("text-anchor", "middle")
        .attr("font-family", "Geist Mono, monospace")
        .attr("font-size", "9px")
        .attr("fill", "#525252")
        .text(`${t}'`);
    });
  }

  /**
   * Draw light density-hint ticks at each event's minute, from the current
   * `_events` array. Purely visual — reads only the minute field.
   */
  function renderDensity() {
    densityG.selectAll("*").remove();
    _events.forEach(e => {
      if (typeof e.minute !== "number") return;
      const x = xScale(e.minute);
      densityG.append("line")
        .attr("x1", x).attr("y1", midY - 8)
        .attr("x2", x).attr("y2", midY - 4)
        .attr("stroke", "#E5E5E5")
        .attr("stroke-width", 1)
        .attr("stroke-opacity", 0.8);
    });
  }

  /**
   * Draw the played segment of the track, from minMinute to the current minute.
   */
  function renderPlayed() {
    playedG.selectAll("*").remove();
    playedG.append("line")
      .attr("x1", xScale(minMinute)).attr("y1", midY)
      .attr("x2", xScale(_minute)).attr("y2", midY)
      .attr("stroke", playedColor)
      .attr("stroke-width", 3)
      .attr("stroke-linecap", "round");
  }

  /**
   * Draw the draggable/focusable playhead handle at the current minute.
   */
  function renderHandle() {
    handleG.selectAll("*").remove();
    handleG.append("circle")
      .attr("cx", xScale(_minute)).attr("cy", midY)
      .attr("r", handleRadius)
      .attr("fill", handleColor)
      .attr("stroke", "#FAF7F0")
      .attr("stroke-width", 2)
      .style("cursor", "grab");
    handleG.append("text")
      .attr("x", xScale(_minute)).attr("y", midY - handleRadius - 6)
      .attr("text-anchor", "middle")
      .attr("font-family", "Geist Mono, monospace")
      .attr("font-size", "10px")
      .attr("font-weight", "600")
      .attr("fill", "#171717")
      .attr("pointer-events", "none")
      .text(`${Math.round(_minute)}'`);
  }

  /**
   * Move the playhead to a new minute, re-render the played segment/handle,
   * and fire onScrub unless this is a silent (programmatic) move.
   *
   * @param {number} minute - Target minute, clamped to [minMinute, maxMinute].
   * @param {boolean} silent - When true, skip the onScrub callback.
   */
  function moveTo(minute, silent = false) {
    _minute = Math.max(minMinute, Math.min(maxMinute, minute));
    renderPlayed();
    renderHandle();
    attachInteraction(); // re-bind drag to the freshly-rendered handle
    if (!silent && onScrub) onScrub(_minute);
  }

  /**
   * Wire up drag-the-handle, click-the-track, and arrow-key interaction.
   */
  function attachInteraction() {
    const drag = d3.drag()
      .on("drag", event => {
        moveTo(xScale.invert(event.x));
      });
    handleG.select("circle").call(drag);

    handleG.select("circle")
      .attr("tabindex", 0)
      .attr("role", "slider")
      .attr("aria-valuemin", minMinute)
      .attr("aria-valuemax", maxMinute)
      .attr("aria-valuenow", Math.round(_minute))
      .on("keydown", event => {
        const step = event.shiftKey ? 5 : 1;
        if (event.key === "ArrowLeft")  { moveTo(_minute - step); event.preventDefault(); }
        if (event.key === "ArrowRight") { moveTo(_minute + step); event.preventDefault(); }
      });

    trackG.select("line")
      .style("cursor", "pointer")
      .on("click", event => {
        const [mx] = d3.pointer(event, trackG.node());
        moveTo(xScale.invert(mx));
      });
  }

  /**
   * Replace the density-hint event array and re-render the ticks.
   *
   * @param {Object} [opts={}]
   * @param {Array} [opts.events] - New events array (objects with a minute field).
   */
  function update(opts = {}) {
    if (opts.events !== undefined) _events = opts.events;
    renderDensity();
  }

  /**
   * Programmatically move the playhead without firing onScrub — for
   * initialization or syncing from external state.
   *
   * @param {number} minute - Target minute, clamped to [minMinute, maxMinute].
   */
  function seek(minute) {
    moveTo(minute, true);
  }

  return { svg, g, xScale, update, seek };
}
