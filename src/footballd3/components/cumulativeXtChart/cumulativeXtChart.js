/**
 * cumulativeXtChart.js — cumulative xT "running total" line for one player.
 *
 * Renders a single step-line: a player's running total of Expected Threat (xT)
 * across match time, rising or falling only at the instant of a credited Pass or
 * Carry and flat otherwise. Shot events are overlaid as "S" chips at the line's
 * value at that minute, so viewers can see where a shot fell relative to the
 * buildup threat the player generated.
 *
 * RELATIONSHIP TO xtSurface.js
 * xtSurface.js renders the STATIC 8×12 possession-value grid — a fixed reference
 * surface, mounted once, never re-filtered. This component renders a DIFFERENT
 * thing: one player's own cumulative xT contribution over time, a per-action data
 * plot. The two are complementary, not alternatives — xtSurface.js stays a
 * background layer; this is its own standalone chart.
 *
 * CLONE OF cumulativeXgChart.js, WITH DELIBERATE DIFFERENCES (not a blind copy)
 * - Single series (one player), not two teams — no home/away, no orientation
 *   toggle (horizontal only; the two-team chart's vertical mode exists to fit a
 *   narrow mobile column, a concern this single-line chart doesn't share).
 * - "Goal chips" become "shot chips" — same chip-rendering shape, keyed off Shot
 *   events instead of goals, labeled "S" instead of "G". Goals among those shots
 *   get a highlighted ring rather than a different chip shape.
 * - The running cumulative sum is computed here, client-side, from each event's
 *   already-computed `xt_delta` (Python's job — see extract_player_events.py).
 *   This is a prefix-sum reduction over already-computed per-event values, not a
 *   new analytical judgment (no grid, no thresholds, no statistics) — the same
 *   category of bookkeeping cumulativeXgChart.js's own _cumulativeAt() already
 *   does client-side for its tooltip lookups.
 *
 * STANDALONE CHART
 * Does not compose on pitch.js. Creates its own SVG inside the given selection.
 */

import * as d3 from "d3";

// ── Tooltip ───────────────────────────────────────────────────────────────────
// Created lazily (not at module scope) so this file can be imported in a
// server-rendering context without touching `document` on the server.

let _tooltip;
function getTooltip() {
  if (!_tooltip) {
    _tooltip = document.createElement("div");
    Object.assign(_tooltip.style, {
      position:      "fixed",
      pointerEvents: "none",
      display:       "none",
      background:    "var(--elevated, #FAF7F0)",
      border:        "1px solid var(--border, #E5E5E5)",
      borderRadius:  "2px",
      padding:       "8px 10px",
      fontFamily:    "Geist Mono, monospace",
      fontSize:      "12px",
      lineHeight:    "1.6",
      color:         "var(--text, #171717)",
      whiteSpace:    "nowrap",
      zIndex:        "100",
    });
    document.body.appendChild(_tooltip);
  }
  return _tooltip;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Build the player's cumulative-xT step-line series from their event array.
 *
 * Credits only Pass/Carry events with a non-null xt_delta (matches
 * extract_player_events.py's own credited-action set — shots are excluded from
 * xT credit there too). Anchors the series at kickoff (minute 0, cumulative_xt 0)
 * and at finalMinute (the running total held at that point) so the line always
 * spans the full chart domain even if the player's last credited action was
 * earlier.
 *
 * @param {Array}  events      - Player event array (player_events.json's `events`).
 * @param {number} finalMinute - Minute the chart's time axis extends to.
 * @returns {Array} Ordered points: { minute, second, cumulative_xt, event_id },
 *   anchored at both ends. The two anchor points carry event_id: null — they
 *   are not real events, so an inbound highlightEventId can never match one.
 */
function _buildSeries(events, finalMinute) {
  const credited = events
    .filter(e => (e.type === "Pass" || e.type === "Carry") && e.xt_delta != null)
    .slice()
    .sort((a, b) => (a.minute * 60 + a.second) - (b.minute * 60 + b.second));

  let running = 0;
  const points = credited.map(e => {
    running += e.xt_delta;
    return { minute: e.minute, second: e.second, cumulative_xt: running, event_id: e.event_id };
  });

  return [
    { minute: 0, cumulative_xt: 0, event_id: null },
    ...points,
    { minute: finalMinute, cumulative_xt: running, event_id: null },
  ];
}

/**
 * Return the cumulative xT value the series held at or before a given minute.
 *
 * @param {number} minute - Minute to evaluate at.
 * @param {Array}  series - Ordered series from _buildSeries (minute non-decreasing).
 * @returns {number} Cumulative xT at that minute, or 0 if before the first point.
 */
function _cumulativeAt(minute, series) {
  let val = 0;
  for (const p of series) {
    if (p.minute > minute) break;
    val = p.cumulative_xt;
  }
  return val;
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Render a cumulative xT "running total" line for one player.
 *
 * Creates a standalone SVG inside the given selection. Horizontal only: time on
 * the X axis, cumulative xT on the Y axis (zero at the bottom).
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object}       data      - player_events/{match_id}/{player_id}.json
 *   contract (or any object with the same shape): { events: [...] }. Pass/Carry
 *   events with xt_delta feed the line; Shot events become chip markers.
 * @param {Object}  [config={}]                 - Rendering options.
 * @param {number}  [config.width=760]          - SVG width in pixels.
 * @param {number}  [config.height=220]         - SVG height in pixels.
 * @param {Object}  [config.padding]            - Inner padding in pixels.
 *   Defaults: { top: 20, right: 60, bottom: 40, left: 48 }.
 * @param {number}  [config.finalMinute]        - Minute the time axis extends
 *   to. Defaults to the player's own last event minute — pass the shared
 *   scrubber's maxMinute explicitly to align this chart's domain with sibling
 *   panels driven by the same master scrubber.
 * @param {string}  [config.lineColor="#9F1239"]  - Cumulative-xT line stroke color.
 * @param {string}  [config.shotColor="#525252"]  - Shot chip fill color.
 * @param {string}  [config.goalRingColor="#9F1239"] - Extra ring stroke on goal chips.
 * @param {boolean} [config.showShots=true]      - Render shot chip markers.
 * @param {boolean} [config.showTotal=true]      - Render the end-of-line total label.
 * @param {Function} [config.onHover]            - onHover(point|null): called with
 *   the nearest series point on mousemove, and `null` on mouseleave. The point
 *   carries `event_id` (null for the two synthetic domain-anchor points) so a
 *   sibling panel can cross-link the exact hovered action. Fires alongside the
 *   built-in tooltip (not a replacement) unless showTooltip is false.
 * @param {boolean} [config.showTooltip=true]    - Render the built-in floating tooltip.
 * @param {string}  [config.highlightColor="#F59E0B"] - Inbound cross-link ring color.
 * @param {string|null} [config.highlightEventId=null] - Inbound cross-link: rings
 *   whichever point (a line point or a shot chip) carries this event_id — set
 *   this from a hover fired elsewhere (a pitch marker, feed row, sonar wedge, ...).
 * @returns {{
 *   svg:       d3.Selection,
 *   g:         d3.Selection,
 *   timeScale: d3.ScaleLinear,
 *   xtScale:   d3.ScaleLinear,
 *   update:    function
 * }}
 *   svg:       The created SVG selection.
 *   g:         The main <g> group (use for custom overlays).
 *   timeScale: Minutes → pixel scale (maps to X).
 *   xtScale:   Cumulative xT → pixel scale (maps to Y, inverted).
 *   update:    function({ data?, showShots?, showTotal? }) — re-renders with
 *              updated options. Any omitted key retains its current value.
 */
export function createCumulativeXtChart(selection, data, config = {}) {
  const {
    width         = 760,
    height        = 220,
    padding       = { top: 20, right: 60, bottom: 40, left: 48 },
    finalMinute,
    lineColor     = "#9F1239",
    shotColor     = "#525252",
    goalRingColor = "#9F1239",
    showShots     = true,
    showTotal     = true,
    onHover,
    showTooltip   = true,
    highlightColor = "#F59E0B",
    highlightEventId = null,
  } = config;

  const svg = selection.append("svg").attr("width", width).attr("height", height);
  const g   = svg.append("g").attr("transform", `translate(${padding.left},${padding.top})`);

  const innerW = width  - padding.left - padding.right;
  const innerH = height - padding.top  - padding.bottom;

  let _data      = data;
  let _showShots = showShots;
  let _showTotal = showTotal;
  let _highlightEventId = highlightEventId;

  let timeScale = d3.scaleLinear();
  let xtScale   = d3.scaleLinear();

  _render();

  /**
   * Resolve the time axis's final minute: the configured value if given,
   * otherwise the player's own last event minute.
   *
   * @param {Object} d - Full data object.
   * @returns {number} Minute the time axis extends to.
   */
  function _resolveFinalMinute(d) {
    if (finalMinute != null) return finalMinute;
    const minutes = d.events.map(e => e.minute);
    return minutes.length ? Math.max(...minutes) : 90;
  }

  function _render() {
    g.selectAll("*").remove();

    const d          = _data;
    const fm          = _resolveFinalMinute(d);
    const series      = _buildSeries(d.events, fm);
    const finalTotal  = series[series.length - 1].cumulative_xt;
    const maxTotal    = Math.max(...series.map(p => p.cumulative_xt), 0.01);
    const minTotal    = Math.min(...series.map(p => p.cumulative_xt), 0);
    const extentHigh  = maxTotal * 1.15;
    const extentLow   = minTotal < 0 ? minTotal * 1.15 : 0;

    timeScale = d3.scaleLinear().domain([0, fm]).range([0, innerW]);
    xtScale   = d3.scaleLinear().domain([extentLow, extentHigh]).range([innerH, 0]);

    // ── Background ───────────────────────────────────────────────────────────
    g.append("rect")
      .attr("width", innerW).attr("height", innerH)
      .attr("fill", "var(--elevated, #FAF7F0)").attr("rx", 2);

    // Zero line, when the domain dips negative (a player can have net-negative
    // cumulative xT if their actions moved play backward more than forward).
    if (extentLow < 0) {
      g.append("line")
        .attr("x1", 0).attr("y1", xtScale(0))
        .attr("x2", innerW).attr("y2", xtScale(0))
        .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 1);
    }

    // Half-time divider at minute 45.
    if (fm > 45) {
      const htX = timeScale(45);
      g.append("line")
        .attr("x1", htX).attr("y1", 0).attr("x2", htX).attr("y2", innerH)
        .attr("stroke", "var(--faint, #D4D4D4)").attr("stroke-width", 1).attr("stroke-dasharray", "4,4");
      g.append("text")
        .attr("x", htX + 3).attr("y", innerH - 4)
        .attr("font-family", "Geist Mono, monospace").attr("font-size", "9px")
        .attr("fill", "var(--faint, #A3A3A3)").text("HT");
    }

    // ── Step line ────────────────────────────────────────────────────────────
    const lineGen = d3.line()
      .x(p => timeScale(p.minute))
      .y(p => xtScale(p.cumulative_xt))
      .curve(d3.curveStepAfter);

    g.append("path").attr("class", "cxt-line")
      .datum(series).attr("d", lineGen)
      .attr("fill", "none").attr("stroke", lineColor).attr("stroke-width", 2);

    if (_showShots) _renderShotMarkers(d, series, fm);
    _renderAxes(fm, extentLow, extentHigh);
    if (_showTotal) _renderTotalLabel(finalTotal, fm);
    _renderHighlight(d, series);
    _renderTooltipOverlay(series, fm);
  }

  /**
   * Ring whichever point (a line point or a shot chip) carries
   * _highlightEventId — the inbound half of the event-scope cross-link.
   *
   * @param {Object} d      - Full data object.
   * @param {Array}  series - The built cumulative series (for line-point lookup).
   */
  function _renderHighlight(d, series) {
    if (_highlightEventId == null) return;

    const linePoint = series.find(p => p.event_id === _highlightEventId);
    const shot = !linePoint && d.events.find(e => e.event_id === _highlightEventId);
    if (!linePoint && !shot) return;

    const cx = timeScale(linePoint ? linePoint.minute : shot.minute);
    const cy = xtScale(linePoint ? linePoint.cumulative_xt : _cumulativeAt(shot.minute, series));

    g.append("circle").attr("class", "cxt-highlight")
      .attr("cx", cx).attr("cy", cy).attr("r", shot ? 14 : 9)
      .attr("fill", "none").attr("stroke", highlightColor).attr("stroke-width", 2.5)
      .attr("pointer-events", "none");
  }

  /**
   * Render Shot-event chip markers on the line, at the cumulative xT value the
   * line held at each shot's minute. Goals get an extra highlight ring.
   *
   * @param {Object} d      - Full data object.
   * @param {Array}  series - The built cumulative series (for value lookup).
   * @param {number} fm     - Final minute (time axis domain).
   */
  function _renderShotMarkers(d, series, fm) {
    const shots = d.events.filter(e => e.type === "Shot" && e.minute <= fm);
    shots.forEach(shot => {
      const cx = timeScale(shot.minute);
      const cy = xtScale(_cumulativeAt(shot.minute, series));
      const isGoal = shot.outcome === "Goal";

      if (isGoal) {
        g.append("circle").attr("class", "cxt-goal-ring")
          .attr("cx", cx).attr("cy", cy).attr("r", 11)
          .attr("fill", "none").attr("stroke", goalRingColor).attr("stroke-width", 2);
      }

      g.append("circle").attr("class", "cxt-shot-chip")
        .attr("cx", cx).attr("cy", cy).attr("r", 8)
        .attr("fill", shotColor).attr("fill-opacity", 0.9)
        .attr("stroke", "var(--elevated, #FAF7F0)").attr("stroke-width", 1.5)
        .on("mouseover", () => {
          const tooltip = getTooltip();
          tooltip.innerHTML =
            `<strong>${shot.minute}'</strong> — Shot<br>` +
            `${shot.outcome ?? ""}`;
          tooltip.style.display = "block";
        })
        .on("mousemove", event => {
          const tooltip = getTooltip();
          tooltip.style.left = (event.clientX + 14) + "px";
          tooltip.style.top  = (event.clientY - 28) + "px";
        })
        .on("mouseout", () => { getTooltip().style.display = "none"; });

      g.append("text").attr("class", "cxt-shot-label")
        .attr("x", cx).attr("y", cy + 1)
        .attr("text-anchor", "middle").attr("dominant-baseline", "middle")
        .attr("font-family", "Geist Mono, monospace")
        .attr("font-size", "8px").attr("font-weight", "700")
        .attr("fill", "#FAF7F0").attr("pointer-events", "none")
        .text("S");
    });
  }

  /**
   * Render time-axis minute ticks and cumulative-xT-axis value ticks.
   *
   * @param {number} fm         - Final minute (time axis domain).
   * @param {number} extentLow  - xT axis domain lower bound.
   * @param {number} extentHigh - xT axis domain upper bound.
   */
  function _renderAxes(fm, extentLow, extentHigh) {
    const stdTicks = [0, 15, 30, 45, 60, 75, 90];
    const minuteTicks = fm > 90 ? [...stdTicks, fm] : stdTicks.filter(t => t <= fm);

    minuteTicks.forEach(t => {
      const x = timeScale(t);
      g.append("line")
        .attr("x1", x).attr("y1", innerH).attr("x2", x).attr("y2", innerH + 5)
        .attr("stroke", "var(--faint, #D4D4D4)").attr("stroke-width", 1);
      g.append("text")
        .attr("x", x).attr("y", innerH + 16)
        .attr("text-anchor", "middle")
        .attr("font-family", "Geist Mono, monospace").attr("font-size", "10px")
        .attr("fill", "var(--muted, #525252)").text(`${t}'`);
    });

    g.append("line")
      .attr("x1", 0).attr("y1", innerH).attr("x2", innerW).attr("y2", innerH)
      .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 1);
    g.append("line")
      .attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", innerH)
      .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 1);

    const xtTicks = xtScale.ticks(4).filter(v => v !== 0 && v >= extentLow && v <= extentHigh);
    xtTicks.forEach(v => {
      const y = xtScale(v);
      g.append("line")
        .attr("x1", -4).attr("y1", y).attr("x2", 0).attr("y2", y)
        .attr("stroke", "var(--faint, #D4D4D4)").attr("stroke-width", 1);
      g.append("text")
        .attr("x", -7).attr("y", y + 1)
        .attr("text-anchor", "end").attr("dominant-baseline", "middle")
        .attr("font-family", "Geist Mono, monospace").attr("font-size", "9px")
        .attr("fill", "var(--faint, #A3A3A3)").text(v.toFixed(2));
      g.append("line")
        .attr("x1", 0).attr("y1", y).attr("x2", innerW).attr("y2", y)
        .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 0.75).attr("stroke-dasharray", "3,4");
    });
  }

  /**
   * Render the end-of-line cumulative total label.
   *
   * @param {number} finalTotal - The player's final cumulative xT value.
   * @param {number} fm         - Final minute (time axis domain).
   */
  function _renderTotalLabel(finalTotal, fm) {
    g.append("text").attr("class", "cxt-total-label")
      .attr("x", timeScale(fm) + 6).attr("y", xtScale(finalTotal) + 1)
      .attr("text-anchor", "start").attr("dominant-baseline", "middle")
      .attr("font-family", "Geist Mono, monospace")
      .attr("font-size", "11px").attr("font-weight", "600")
      .attr("fill", lineColor).text(finalTotal.toFixed(2));
  }

  /**
   * Attach an invisible overlay rect driving a minute-snapping crosshair + tooltip.
   *
   * @param {Array}  series - The built cumulative series.
   * @param {number} fm     - Final minute (time axis domain).
   */
  function _renderTooltipOverlay(series, fm) {
    const overlay = g.append("rect").attr("class", "cxt-overlay")
      .attr("width", innerW).attr("height", innerH)
      .attr("fill", "transparent").style("cursor", "crosshair");

    const crosshair = g.append("line").attr("class", "cxt-crosshair")
      .attr("y1", 0).attr("y2", innerH)
      .attr("stroke", "var(--muted, #525252)").attr("stroke-width", 1)
      .attr("stroke-dasharray", "3,3").attr("stroke-opacity", 0.5)
      .attr("pointer-events", "none").attr("display", "none");

    const bisect = d3.bisector(p => p.minute).left;

    overlay
      .on("mousemove", function (event) {
        const [px] = d3.pointer(event, this);
        const minute = Math.max(0, Math.min(fm, timeScale.invert(px)));
        const idx = bisect(series, minute);
        const before = series[idx - 1];
        const after  = series[idx];
        const nearest = !before ? after : !after ? before
          : (Math.abs(before.minute - minute) <= Math.abs(after.minute - minute) ? before : after);
        if (!nearest) return;

        const x = timeScale(nearest.minute);
        crosshair.attr("x1", x).attr("x2", x).attr("display", null);

        if (onHover) onHover(nearest);
        if (!showTooltip) return;

        const tooltip = getTooltip();
        tooltip.innerHTML =
          `<strong>${Math.round(nearest.minute)}'</strong><br>` +
          `cumulative xT ${nearest.cumulative_xt.toFixed(3)}`;
        tooltip.style.display = "block";
        tooltip.style.left = (event.clientX + 14) + "px";
        tooltip.style.top  = (event.clientY - 28) + "px";
      })
      .on("mouseout", function () {
        crosshair.attr("display", "none");
        if (onHover) onHover(null);
        if (showTooltip) getTooltip().style.display = "none";
      });
  }

  /**
   * Re-render the chart with updated data or toggled display options.
   *
   * @param {Object}  [opts={}]
   * @param {Object}  [opts.data]      - Replace the full data object.
   * @param {boolean} [opts.showShots] - Toggle shot chip markers.
   * @param {boolean} [opts.showTotal] - Toggle the end-of-line total label.
   * @param {string|null} [opts.highlightEventId] - Move the inbound cross-link ring.
   */
  function update(opts = {}) {
    if (opts.data      !== undefined) _data      = opts.data;
    if (opts.showShots !== undefined) _showShots = opts.showShots;
    if (opts.showTotal !== undefined) _showTotal = opts.showTotal;
    if (opts.highlightEventId !== undefined) _highlightEventId = opts.highlightEventId;
    _render();
  }

  return { svg, g, timeScale, xtScale, update };
}
