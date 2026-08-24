/**
 * cumulativeXgChart.js — cumulative xG "race chart" built from raw shot events.
 *
 * Renders a step-line per team: each team's running total of expected goals (xG)
 * across match time, rising only at the instant of a shot and flat otherwise.
 * Actual goals are overlaid as "G" chips directly on the scoring team's line so
 * viewers can compare expected scoring against what actually happened.
 *
 * ORIENTATIONS
 * "horizontal" (default): time flows left→right on the X axis; cumulative xG grows
 *   upward on the Y axis (zero at the bottom). End-of-line totals sit at the right edge.
 * "vertical": time flows top→bottom on the Y axis; cumulative xG grows rightward on
 *   the X axis (zero at the left). End-of-line totals sit near the bottom edge.
 *
 * READING THE CHART
 * Each line only steps upward at a shot event — flat stretches are periods with no
 * shots from that team. A line "ahead" of the other reflects more/better shot chances
 * created, not more goals scored — see README.md for the full caveats on interpreting
 * xG as shot quality, not a score prediction.
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

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Build a team's step-line series from the flat, chronological points array.
 *
 * Filters points to one team, then anchors the series at kickoff (minute 0,
 * cumulative_xg 0) and at full time (final_minute, finalTotal) so the line
 * always spans the whole match even if that team's last shot was minutes
 * before the final whistle.
 *
 * @param {Array}  points      - Full chronological points array (both teams).
 * @param {string} team        - Team name to filter to.
 * @param {number} finalMinute - True match-ending minute.
 * @param {number} finalTotal  - That team's final cumulative xG.
 * @returns {Array} Points for this team only, anchored at both ends.
 */
function _teamSeries(points, team, finalMinute, finalTotal) {
  const teamPoints = points
    .filter(p => p.team === team)
    .map(p => ({ minute: p.minute, cumulative_xg: p.cumulative_xg }));
  return [
    { minute: 0, cumulative_xg: 0 },
    ...teamPoints,
    { minute: finalMinute, cumulative_xg: finalTotal },
  ];
}

/**
 * Return a team's cumulative xG total at or before a given minute.
 *
 * Points are assumed chronologically ordered (minute non-decreasing across
 * both teams combined) — the scan stops as soon as it passes the target minute.
 *
 * @param {string} team   - Team name.
 * @param {number} minute - Minute to evaluate at.
 * @param {Array}  points - Full chronological points array (both teams).
 * @returns {number} That team's cumulative xG at the given minute, or 0 if none yet.
 */
function _cumulativeAt(team, minute, points) {
  let val = 0;
  for (const p of points) {
    if (p.minute > minute) break;
    if (p.team === team) val = p.cumulative_xg;
  }
  return val;
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Render a cumulative xG "race chart" — a step-line per team over match time.
 *
 * Creates a standalone SVG inside the given selection. Supports two orientations:
 * "horizontal" (time on X, cumulative xG on Y) and "vertical" (time on Y,
 * cumulative xG on X). The SVG dimensions are swapped automatically when
 * orientation changes via update().
 *
 * @param {d3.Selection} selection   - D3 selection of the container element.
 * @param {Object}       data        - cumulative_xg_{match_id}.json contract:
 *   { home_team, away_team,
 *     points: [{minute, team, display_name, xg, cumulative_xg, outcome, is_goal}],
 *     final_minute, final_home_xg, final_away_xg,
 *     goals: [{minute, team, player, is_own_goal}],
 *     metadata }
 * @param {Object}  [config={}]                  - Rendering options.
 * @param {number}  [config.width=760]           - Time-axis dimension in pixels.
 * @param {number}  [config.height=220]          - xG-axis dimension in pixels.
 * @param {Object}  [config.padding]             - Inner padding for horizontal mode.
 *   Defaults: { top: 20, right: 88, bottom: 40, left: 48 }. Right padding is wider
 *   than a diverging chart's to fit end-of-line total labels.
 * @param {string}  [config.homeColor="#1E3A5F"] - Stroke color for the home team's line.
 * @param {string}  [config.awayColor="#9F1239"] - Stroke color for the away team's line.
 * @param {boolean} [config.showGoals=true]      - Render actual-goal "G" chip markers.
 * @param {boolean} [config.showTotals=true]     - Render end-of-line cumulative total labels.
 * @param {string}  [config.orientation="horizontal"] - "horizontal" or "vertical".
 * @param {Function} [config.onHover]            - onHover(point|null): called with the
 *   nearest shot point on mousemove, and `null` on mouseleave. Fires alongside the
 *   built-in tooltip (not a replacement) unless config.showTooltip is false.
 * @param {boolean} [config.showTooltip=true]    - Render the built-in floating
 *   tooltip on hover. Set false when the caller renders its own readout from
 *   onHover instead.
 * @returns {{
 *   svg:       d3.Selection,
 *   g:         d3.Selection,
 *   timeScale: d3.ScaleLinear,
 *   xgScale:   d3.ScaleLinear,
 *   update:    function
 * }}
 *   svg:       The created SVG selection.
 *   g:         The main <g> group (use for custom overlays).
 *   timeScale: Minutes → pixel scale (horizontal: maps to X; vertical: maps to Y).
 *   xgScale:   Cumulative xG → pixel scale (horizontal: maps to Y; vertical: maps to X).
 *   update:    function({ data?, orientation?, showGoals?, showTotals? })
 *              Re-renders with updated options. Any omitted key retains its current value.
 */
export function createCumulativeXgChart(selection, data, config = {}) {
  const {
    width       = 760,
    height      = 220,
    padding     = { top: 20, right: 88, bottom: 40, left: 48 },
    homeColor   = "#1E3A5F",
    awayColor   = "#9F1239",
    showGoals   = true,
    showTotals  = true,
    orientation = "horizontal",
    onHover,
    showTooltip = true,
  } = config;

  // Vertical mode: time runs top-to-bottom, so total labels stack below the
  // xG-axis tick row instead of sitting beside the right edge — needs more
  // bottom padding, less right/left.
  const _vPad = { top: 20, right: 44, bottom: 70, left: 44 };

  const svg = selection.append("svg");
  const g   = svg.append("g");

  // ── Mutable state ─────────────────────────────────────────────────────────────
  let _data        = data;
  let _showGoals    = showGoals;
  let _showTotals   = showTotals;
  let _orientation  = orientation;

  // Exposed scales — updated on every render so external callers always get current refs.
  let timeScale = d3.scaleLinear();
  let xgScale   = d3.scaleLinear();

  // ── Scales ────────────────────────────────────────────────────────────────────

  /**
   * Build time and xG scales for the given inner dimensions and orientation.
   *
   * timeScale always maps match minutes to pixels — to X in horizontal mode, to Y
   * in vertical mode. xgScale always maps cumulative xG to pixels — to Y (inverted,
   * zero at the bottom) in horizontal, to X (zero at the left) in vertical.
   *
   * @param {Object}  d   - Full data object.
   * @param {number}  iW  - Inner chart width in pixels.
   * @param {number}  iH  - Inner chart height in pixels.
   * @param {boolean} isH - True for horizontal orientation.
   * @returns {{ timeScale, xgScale, finalMinute, extent }}
   */
  function _buildScales(d, iW, iH, isH) {
    const finalMinute = d.final_minute;
    const maxTotal = Math.max(d.final_home_xg, d.final_away_xg, 0.01);
    const extent = maxTotal * 1.15;

    const ts = d3.scaleLinear()
      .domain([0, finalMinute])
      .range(isH ? [0, iW] : [0, iH]);

    // Horizontal: zero at the bottom, growing upward. Vertical: zero at the left,
    // growing rightward. Unlike a diverging chart, this domain never goes negative.
    const xs = d3.scaleLinear()
      .domain([0, extent])
      .range(isH ? [iH, 0] : [0, iW]);

    return { timeScale: ts, xgScale: xs, finalMinute, extent };
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  _render();

  function _render() {
    const isH  = _orientation === "horizontal";
    const pad  = isH ? padding : _vPad;
    const svgW = isH ? width  : height;
    const svgH = isH ? height : width;

    svg.attr("width", svgW).attr("height", svgH);
    g.attr("transform", `translate(${pad.left},${pad.top})`);

    const iW = svgW - pad.left - pad.right;
    const iH = svgH - pad.top  - pad.bottom;

    g.selectAll("*").remove();

    const d = _data;
    const scales = _buildScales(d, iW, iH, isH);
    timeScale = scales.timeScale;
    xgScale   = scales.xgScale;
    const { finalMinute, extent } = scales;

    // ── Background ─────────────────────────────────────────────────────────────
    g.append("rect")
      .attr("width", iW).attr("height", iH)
      .attr("fill", "var(--elevated, #FAF7F0)").attr("rx", 2);

    // Half-time divider at minute 45.
    if (finalMinute > 45) {
      const htPos = timeScale(45);
      g.append("line")
        .attr("class", "cxg-ht-line")
        .attr("x1", isH ? htPos : 0 ).attr("y1", isH ? 0    : htPos)
        .attr("x2", isH ? htPos : iW).attr("y2", isH ? iH   : htPos)
        .attr("stroke", "var(--border-strong, #D4D4D4)")
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "4,4");

      g.append("text")
        .attr("x", isH ? htPos + 3 : iW - 2)
        .attr("y", isH ? iH - 4    : htPos - 3)
        .attr("text-anchor", isH ? "start" : "end")
        .attr("font-family", "Geist Mono, monospace")
        .attr("font-size", "9px")
        .attr("fill", "var(--faint, #A3A3A3)")
        .text("HT");
    }

    // ── Step lines ─────────────────────────────────────────────────────────────
    const homeSeries = _teamSeries(d.points, d.home_team, finalMinute, d.final_home_xg);
    const awaySeries = _teamSeries(d.points, d.away_team, finalMinute, d.final_away_xg);

    const lineGen = isH
      ? d3.line().x(p => timeScale(p.minute)).y(p => xgScale(p.cumulative_xg)).curve(d3.curveStepAfter)
      : d3.line().y(p => timeScale(p.minute)).x(p => xgScale(p.cumulative_xg)).curve(d3.curveStepAfter);

    g.append("path").attr("class", "cxg-away-line")
      .datum(awaySeries).attr("d", lineGen)
      .attr("fill", "none").attr("stroke", awayColor).attr("stroke-width", 2);

    g.append("path").attr("class", "cxg-home-line")
      .datum(homeSeries).attr("d", lineGen)
      .attr("fill", "none").attr("stroke", homeColor).attr("stroke-width", 2);

    // ── Markers, axes, labels, tooltip ─────────────────────────────────────────
    if (_showGoals) _renderGoalMarkers(d, isH, iW, iH);
    _renderAxes(d, isH, iW, iH, finalMinute, extent);
    if (_showTotals) _renderTotalLabels(d, isH, iW, iH);
    _renderTooltipOverlay(d, isH, iW, iH);
  }

  // ── Goal markers ──────────────────────────────────────────────────────────────

  /**
   * Render actual-goal markers — dashed line + "G" chip directly on the scoring
   * team's step-line, at the cumulative xG value that line held at that minute.
   *
   * Own goals: goal.team is the shot-taking team as recorded on the underlying
   * Shot event, matching extract_momentum.py's convention — the chip therefore
   * lands on the shooting team's own line, not the beneficiary's.
   *
   * @param {Object}  d   - Full data object.
   * @param {boolean} isH - True for horizontal orientation.
   * @param {number}  iW  - Inner width.
   * @param {number}  iH  - Inner height.
   */
  function _renderGoalMarkers(d, isH, iW, iH) {
    d.goals.forEach(goal => {
      const isHome = goal.team === d.home_team;
      const color  = isHome ? homeColor : awayColor;
      const tp     = timeScale(goal.minute);
      const cum    = _cumulativeAt(goal.team, goal.minute, d.points);
      const vp     = xgScale(cum);

      const nameParts = goal.player.split(" ");
      const shortName = nameParts[nameParts.length - 1];

      const cx = isH ? tp : vp;
      const cy = isH ? vp : tp;

      g.append("circle").attr("class", "cxg-goal-chip")
        .attr("cx", cx).attr("cy", cy)
        .attr("r", 8).attr("fill", color).attr("fill-opacity", 0.9)
        .attr("stroke", "var(--elevated, #FAF7F0)").attr("stroke-width", 1.5);

      g.append("text")
        .attr("x", cx).attr("y", cy + 1)
        .attr("text-anchor", "middle").attr("dominant-baseline", "middle")
        .attr("font-family", "Geist Mono, monospace")
        .attr("font-size", "8px").attr("font-weight", "700")
        .attr("fill", "#FAF7F0").attr("pointer-events", "none")
        .text("G");

      const labelDy = isHome ? -13 : 13;
      g.append("text").attr("class", "cxg-goal-label")
        .attr("x", cx).attr("y", cy + labelDy)
        .attr("text-anchor", "middle")
        .attr("font-family", "Geist Mono, monospace")
        .attr("font-size", "9px").attr("fill", color).attr("fill-opacity", 0.85)
        .text(`${shortName} ${goal.minute}'`);
    });
  }

  // ── Total labels ──────────────────────────────────────────────────────────────

  /**
   * Render end-of-line cumulative total labels ("Team 1.73") for each team.
   *
   * Horizontal: labels sit beside each line's terminus, in the wide right padding.
   * Vertical: the line's terminus is always near the bottom edge (full time), too
   * close to the xG-axis value ticks to label in place — instead, labels are
   * stacked below the tick row, each still aligned to its team's final xG position
   * on the value axis.
   *
   * @param {Object}  d   - Full data object.
   * @param {boolean} isH - True for horizontal orientation.
   * @param {number}  iW  - Inner width.
   * @param {number}  iH  - Inner height.
   */
  function _renderTotalLabels(d, isH, iW, iH) {
    const tp      = timeScale(d.final_minute);
    const homeVp  = xgScale(d.final_home_xg);
    const awayVp  = xgScale(d.final_away_xg);

    [
      { team: d.home_team, total: d.final_home_xg, vp: homeVp, color: homeColor, vRow: iH + 32 },
      { team: d.away_team, total: d.final_away_xg, vp: awayVp, color: awayColor, vRow: iH + 46 },
    ].forEach(({ team, total, vp, color, vRow }) => {
      g.append("text").attr("class", "cxg-total-label")
        .attr("x", isH ? tp + 6 : vp)
        .attr("y", isH ? vp + 1 : vRow)
        .attr("text-anchor", isH ? "start" : "middle")
        .attr("dominant-baseline", "middle")
        .attr("font-family", "Geist Mono, monospace")
        .attr("font-size", "11px").attr("font-weight", "600")
        .attr("fill", color)
        .text(`${team} ${total.toFixed(2)}`);
    });
  }

  // ── Axes ──────────────────────────────────────────────────────────────────────

  /**
   * Render time-axis minute ticks and cumulative-xG-axis value ticks.
   *
   * Horizontal: minute ticks on the bottom X axis; xG ticks on the left Y axis.
   * Vertical:   minute ticks on the left Y axis; xG ticks on the bottom X axis.
   *
   * @param {Object}  d           - Full data object.
   * @param {boolean} isH         - True for horizontal orientation.
   * @param {number}  iW          - Inner width.
   * @param {number}  iH          - Inner height.
   * @param {number}  finalMinute - True match-ending minute.
   * @param {number}  extent      - xG-axis domain upper bound.
   */
  function _renderAxes(d, isH, iW, iH, finalMinute, extent) {
    const stdMinuteTicks = [0, 15, 30, 45, 60, 75, 90];
    const minuteTicks = finalMinute > 90
      ? [...stdMinuteTicks, finalMinute]
      : stdMinuteTicks.filter(t => t <= finalMinute);

    minuteTicks.forEach(t => {
      const tp = timeScale(t);
      if (isH) {
        g.append("line")
          .attr("x1", tp).attr("y1", iH)
          .attr("x2", tp).attr("y2", iH + 5)
          .attr("stroke", "var(--border-strong, #D4D4D4)").attr("stroke-width", 1);

        g.append("text")
          .attr("x", tp).attr("y", iH + 16)
          .attr("text-anchor", "middle")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "10px").attr("fill", "var(--muted, #525252)")
          .text(`${t}'`);
      } else {
        g.append("line")
          .attr("x1", -5).attr("y1", tp)
          .attr("x2", 0 ).attr("y2", tp)
          .attr("stroke", "var(--border-strong, #D4D4D4)").attr("stroke-width", 1);

        g.append("text")
          .attr("x", -8).attr("y", tp)
          .attr("text-anchor", "end").attr("dominant-baseline", "middle")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "10px").attr("fill", "var(--muted, #525252)")
          .text(`${t}'`);
      }
    });

    // Axis border lines.
    g.append("line")
      .attr("x1", 0).attr("y1", iH).attr("x2", iW).attr("y2", iH)
      .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 1);
    g.append("line")
      .attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", iH)
      .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 1);

    // xG value ticks (zero omitted — it coincides with the axis border).
    const xgTicks = xgScale.ticks(4).filter(v => v > 0 && v <= extent);
    xgTicks.forEach(v => {
      const vp = xgScale(v);
      if (isH) {
        g.append("line")
          .attr("x1", -4).attr("y1", vp).attr("x2", 0).attr("y2", vp)
          .attr("stroke", "var(--border-strong, #D4D4D4)").attr("stroke-width", 1);
        g.append("text")
          .attr("x", -7).attr("y", vp + 1)
          .attr("text-anchor", "end").attr("dominant-baseline", "middle")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "9px").attr("fill", "var(--faint, #A3A3A3)")
          .text(v.toFixed(1));
        g.append("line")
          .attr("x1", 0).attr("y1", vp).attr("x2", iW).attr("y2", vp)
          .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 0.75)
          .attr("stroke-dasharray", "3,4");
      } else {
        g.append("line")
          .attr("x1", vp).attr("y1", iH).attr("x2", vp).attr("y2", iH + 4)
          .attr("stroke", "var(--border-strong, #D4D4D4)").attr("stroke-width", 1);
        g.append("text")
          .attr("x", vp).attr("y", iH + 14)
          .attr("text-anchor", "middle")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "9px").attr("fill", "var(--faint, #A3A3A3)")
          .text(v.toFixed(1));
        g.append("line")
          .attr("x1", vp).attr("y1", 0).attr("x2", vp).attr("y2", iH)
          .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 0.75)
          .attr("stroke-dasharray", "3,4");
      }
    });
  }

  // ── Tooltip overlay ───────────────────────────────────────────────────────────

  /**
   * Attach an invisible overlay rect that drives a shot-snapping crosshair and tooltip.
   *
   * Unlike a dense per-minute series, shots are sparse — the overlay uses a bisector
   * over both teams' points (merged, sorted by minute) to snap to the nearest shot
   * rather than an exact-minute lookup.
   *
   * @param {Object}  d   - Full data object.
   * @param {boolean} isH - True for horizontal orientation.
   * @param {number}  iW  - Inner width.
   * @param {number}  iH  - Inner height.
   */
  function _renderTooltipOverlay(d, isH, iW, iH) {
    const overlay = g.append("rect")
      .attr("class", "cxg-overlay")
      .attr("width", iW).attr("height", iH)
      .attr("fill", "transparent")
      .style("cursor", "crosshair");

    const crosshair = g.append("line")
      .attr("class", "cxg-crosshair")
      .attr("x1", isH ? 0  : 0 ).attr("y1", isH ? 0  : 0 )
      .attr("x2", isH ? 0  : iW).attr("y2", isH ? iH : 0 )
      .attr("stroke", "var(--muted, #525252)").attr("stroke-width", 1)
      .attr("stroke-dasharray", "3,3").attr("stroke-opacity", 0.5)
      .attr("pointer-events", "none").attr("display", "none");

    const sortedPoints = [...d.points].sort((a, b) => a.minute - b.minute);
    const bisect = d3.bisector(p => p.minute).left;

    overlay
      .on("mousemove", function (ev) {
        if (sortedPoints.length === 0) return;
        const [px, py] = d3.pointer(ev, this);
        const rawMinute = isH ? timeScale.invert(px) : timeScale.invert(py);
        const minute = Math.max(0, Math.min(d.final_minute, rawMinute));

        const idx = bisect(sortedPoints, minute);
        const before = sortedPoints[idx - 1];
        const after  = sortedPoints[idx];
        const nearest = !before ? after : !after ? before
          : (Math.abs(before.minute - minute) <= Math.abs(after.minute - minute) ? before : after);
        if (!nearest) return;

        const tp = timeScale(nearest.minute);
        crosshair.attr("display", null);
        if (isH) {
          crosshair.attr("x1", tp).attr("x2", tp);
        } else {
          crosshair.attr("y1", tp).attr("y2", tp);
        }

        const homeCum = _cumulativeAt(d.home_team, nearest.minute, d.points);
        const awayCum = _cumulativeAt(d.away_team, nearest.minute, d.points);

        if (onHover) onHover({ ...nearest, homeCum, awayCum });
        if (!showTooltip) return;

        const homeLabel = `<span style="color:${homeColor};font-weight:600">${d.home_team}</span>`;
        const awayLabel = `<span style="color:${awayColor};font-weight:600">${d.away_team}</span>`;

        const tooltip = getTooltip();
        tooltip.innerHTML =
          `<strong>${nearest.minute}'</strong> — ${nearest.team}<br>` +
          `${nearest.display_name} · ${nearest.outcome} · xG ${nearest.xg.toFixed(2)}<br>` +
          `${homeLabel} ${homeCum.toFixed(2)}<br>` +
          `${awayLabel} ${awayCum.toFixed(2)}`;
        tooltip.style.display = "block";
        tooltip.style.left = (ev.clientX + 14) + "px";
        tooltip.style.top  = (ev.clientY - 28) + "px";
      })
      .on("mouseout", function () {
        crosshair.attr("display", "none");
        if (onHover) onHover(null);
        if (showTooltip) getTooltip().style.display = "none";
      });
  }

  // ── Update ────────────────────────────────────────────────────────────────────

  /**
   * Re-render the chart with updated data or toggled display options.
   *
   * Changing orientation resizes the SVG (width↔height swap) and redraws all content.
   * All other options re-render in-place without layout change.
   *
   * @param {Object}  [opts={}]
   * @param {Object}  [opts.data]        - Replace the full data object.
   * @param {string}  [opts.orientation] - "horizontal" or "vertical".
   * @param {boolean} [opts.showGoals]   - Toggle actual-goal chip markers.
   * @param {boolean} [opts.showTotals]  - Toggle end-of-line total labels.
   */
  function update(opts = {}) {
    if (opts.data        !== undefined) _data        = opts.data;
    if (opts.orientation !== undefined) _orientation  = opts.orientation;
    if (opts.showGoals   !== undefined) _showGoals    = opts.showGoals;
    if (opts.showTotals  !== undefined) _showTotals   = opts.showTotals;
    _render();
  }

  return { svg, g, timeScale, xgScale, update };
}
