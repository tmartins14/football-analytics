/**
 * momentumBarChart.js — 2-minute-binned attacking-momentum bar chart.
 *
 * Renders a diverging bar per 2-minute window of match time: bars rise above a
 * center baseline when the home team generated more attacking threat (xT) across
 * that window, and fall below when the away team did. Each bar's value is the sum
 * of the window's two per-minute momentum values — a rate summed over the window,
 * not averaged, so a bar reads as "how much threat swung this way in these two
 * minutes," not a smoothed instantaneous rate.
 *
 * WHY A SEPARATE COMPONENT FROM momentumChart.js
 * momentumChart.js draws a smoothed, continuous area/line — appropriate for reading
 * momentum as an overall trend. This component draws discrete per-window bars —
 * appropriate for a compact panel where individual 2-minute swings matter more than
 * the overall shape. Different visual semantics get a dedicated component rather
 * than a render-mode flag, the same reasoning documented in cumulativeXgChart.js.
 *
 * NO INTERNAL TOOLTIP
 * Unlike most footballd3 components, this one has no floating tooltip. It exists to
 * back a compact panel with its own inline readout row driven by the onHover
 * callback — a floating tooltip would be redundant chrome in that layout.
 *
 * STANDALONE CHART
 * Does not compose on pitch.js. Creates its own SVG inside the given selection.
 */

import * as d3 from "d3";

/**
 * Bin per-minute momentum entries into 2-minute windows by summing.
 *
 * @param {Array<{minute:number, momentum:number}>} minutes - momentum_{match_id}.json's `minutes` array.
 * @returns {Array<{start:number, end:number, value:number}>} One entry per 2-minute window.
 */
function _binMinutes(minutes) {
  const bins = [];
  for (let i = 0; i < minutes.length; i += 2) {
    const a = minutes[i];
    const b = minutes[i + 1];
    const value = a.momentum + (b ? b.momentum : 0);
    bins.push({ start: a.minute, end: b ? b.minute : a.minute, value: +value.toFixed(4) });
  }
  return bins;
}

/**
 * Render a 2-minute-binned diverging momentum bar chart.
 *
 * Creates a standalone SVG inside the given selection. Bars are hoverable via a
 * full-height transparent strip per bin (bars themselves can be too short to
 * reliably hover near zero momentum) — hover fires config.onHover(bin), leave
 * fires config.onHover(null).
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object} data - momentum_{match_id}.json contract (same shape momentumChart.js reads):
 *   { home_team, away_team, minutes: [{minute, home_threat, away_threat, momentum}],
 *     goals: [{minute, team, player, is_own_goal}], red_cards, params, metadata }
 * @param {Object}   [config={}]                  - Rendering options.
 * @param {number}   [config.width=316]           - SVG width in pixels.
 * @param {number}   [config.height=210]          - SVG height in pixels.
 * @param {"horizontal"|"vertical"} [config.orientation="horizontal"] - Axis layout.
 *   "horizontal" (default, unchanged): time on X, magnitude on Y, diverging from a
 *   horizontal centerline — suited to a wide, short box. "vertical": time on Y
 *   (top = minute 0, increasing downward), magnitude on X, diverging from a
 *   vertical centerline — suited to a narrow, tall box.
 * @param {string}   [config.homeColor="#1E3A5F"] - Fill color for home-leaning bars.
 * @param {string}   [config.awayColor="#9F1239"] - Fill color for away-leaning bars.
 * @param {boolean}  [config.showGoals=true]      - Render goal event markers.
 * @param {Function} [config.onHover=null]        - onHover(bin|null): called with the
 *   hovered bin `{start, end, value}` on hover, and `null` on leave. No internal
 *   tooltip is rendered — callers own the readout UI.
 * @returns {{ svg: d3.Selection, g: d3.Selection, update: Function }}
 *   svg:    The created SVG selection.
 *   g:      The main <g> group (use for custom overlays).
 *   update: function({ data?, showGoals? }) — re-renders with updated options.
 */
export function createMomentumBarChart(selection, data, config = {}) {
  const {
    width = 316,
    height = 210,
    orientation = "horizontal",
    homeColor = "#1E3A5F",
    awayColor = "#9F1239",
    showGoals = true,
    onHover = null,
  } = config;

  const svg = selection.append("svg").attr("width", width).attr("height", height);
  const g = svg.append("g");

  let _data = data;
  let _showGoals = showGoals;

  _render();

  /**
   * Stateless full redraw of bars, baseline, and goal markers — dispatches to the
   * horizontal or vertical layout based on config.orientation.
   */
  function _render() {
    g.selectAll("*").remove();
    if (orientation === "vertical") _renderVertical();
    else _renderHorizontal();
  }

  function _renderHorizontal() {
    const bins = _binMinutes(_data.minutes);
    const maxAbs = Math.max(...bins.map((b) => Math.abs(b.value)), 0.001);
    const maxMinute = bins.length ? bins[bins.length - 1].end : 0;

    const padX = 8, padTop = 8, padBottom = 20;
    const innerW = width - padX * 2;
    const base = padTop + (height - padTop - padBottom) * 0.52;
    const scaleH = (height - padTop - padBottom) * 0.42;

    const x = (m) => padX + (m / (maxMinute || 1)) * innerW;
    const barW = Math.max(2, (innerW / (bins.length || 1)) * 0.62);

    g.append("line")
      .attr("x1", padX).attr("y1", base).attr("x2", width - padX).attr("y2", base)
      .attr("stroke", "var(--border-strong, #D6D3CC)").attr("stroke-width", 1);

    bins.forEach((bin) => {
      const isHome = bin.value >= 0;
      const barH = (Math.abs(bin.value) / maxAbs) * scaleH;
      const cx = x((bin.start + bin.end) / 2);

      g.append("rect")
        .attr("class", "mb-bar")
        .attr("x", cx - barW / 2)
        .attr("y", isHome ? base - barH : base)
        .attr("width", barW)
        .attr("height", barH)
        .attr("rx", 1)
        .attr("fill", isHome ? homeColor : awayColor)
        .attr("fill-opacity", 0.85);

      g.append("rect")
        .attr("class", "mb-hover-strip")
        .attr("x", cx - barW / 2 - 1)
        .attr("y", padTop)
        .attr("width", barW + 2)
        .attr("height", height - padTop - padBottom)
        .attr("fill", "transparent")
        .style("cursor", "crosshair")
        .on("mouseenter", () => { if (onHover) onHover(bin); })
        .on("mouseleave", () => { if (onHover) onHover(null); });
    });

    if (_showGoals) {
      _data.goals.forEach((goal) => {
        const isHome = goal.team === _data.home_team;
        const color = isHome ? homeColor : awayColor;
        const gx = x(goal.minute);

        g.append("line")
          .attr("class", "mb-goal-line")
          .attr("x1", gx).attr("y1", padTop).attr("x2", gx).attr("y2", height - padBottom)
          .attr("stroke", color).attr("stroke-width", 1)
          .attr("stroke-dasharray", "3,3").attr("stroke-opacity", 0.7);

        g.append("circle")
          .attr("cx", gx).attr("cy", padTop + 4).attr("r", 3.5).attr("fill", color);

        g.append("text")
          .attr("class", "mb-goal-label")
          .attr("x", gx).attr("y", height - 4)
          .attr("text-anchor", "middle")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "9px")
          .attr("fill", "var(--faint, #8A8578)")
          .text(`${goal.minute}'`);
      });
    }
  }

  /**
   * Vertical mirror of _renderHorizontal(): time runs down the Y axis, magnitude
   * diverges left/right of a vertical centerline. Same 0.52/0.42 baseline-bias and
   * max-deflection fractions, same hover-strip/goal-marker semantics, axes swapped.
   */
  function _renderVertical() {
    const bins = _binMinutes(_data.minutes);
    const maxAbs = Math.max(...bins.map((b) => Math.abs(b.value)), 0.001);
    const maxMinute = bins.length ? bins[bins.length - 1].end : 0;

    const padTop = 8, padBottom = 20, padLeft = 8, padRight = 8;
    const innerH = height - padTop - padBottom;
    const baseX = padLeft + (width - padLeft - padRight) * 0.52;
    const scaleW = (width - padLeft - padRight) * 0.42;

    const yPos = (m) => padTop + (m / (maxMinute || 1)) * innerH;
    const barThickness = Math.max(2, (innerH / (bins.length || 1)) * 0.62);

    g.append("line")
      .attr("x1", baseX).attr("y1", padTop).attr("x2", baseX).attr("y2", height - padBottom)
      .attr("stroke", "var(--border-strong, #D6D3CC)").attr("stroke-width", 1);

    bins.forEach((bin) => {
      const isHome = bin.value >= 0;
      const barW = (Math.abs(bin.value) / maxAbs) * scaleW;
      const cy = yPos((bin.start + bin.end) / 2);

      g.append("rect")
        .attr("class", "mb-bar")
        .attr("x", isHome ? baseX - barW : baseX)
        .attr("y", cy - barThickness / 2)
        .attr("width", barW)
        .attr("height", barThickness)
        .attr("rx", 1)
        .attr("fill", isHome ? homeColor : awayColor)
        .attr("fill-opacity", 0.85);

      g.append("rect")
        .attr("class", "mb-hover-strip")
        .attr("x", padLeft)
        .attr("y", cy - barThickness / 2 - 1)
        .attr("width", width - padLeft - padRight)
        .attr("height", barThickness + 2)
        .attr("fill", "transparent")
        .style("cursor", "crosshair")
        .on("mouseenter", () => { if (onHover) onHover(bin); })
        .on("mouseleave", () => { if (onHover) onHover(null); });
    });

    if (_showGoals) {
      _data.goals.forEach((goal) => {
        const isHome = goal.team === _data.home_team;
        const color = isHome ? homeColor : awayColor;
        const gy = yPos(goal.minute);

        g.append("line")
          .attr("class", "mb-goal-line")
          .attr("x1", padLeft).attr("y1", gy).attr("x2", width - padRight).attr("y2", gy)
          .attr("stroke", color).attr("stroke-width", 1)
          .attr("stroke-dasharray", "3,3").attr("stroke-opacity", 0.7);

        g.append("circle")
          .attr("cx", padLeft + 4).attr("cy", gy).attr("r", 3.5).attr("fill", color);

        g.append("text")
          .attr("class", "mb-goal-label")
          .attr("x", width - padRight).attr("y", gy - 5)
          .attr("text-anchor", "end")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "9px")
          .attr("fill", "var(--faint, #8A8578)")
          .text(`${goal.minute}'`);
      });
    }
  }

  /**
   * Replace data or toggle goal markers and re-render.
   *
   * @param {Object}  [opts={}]
   * @param {Object}  [opts.data]       - Replace the full data object.
   * @param {boolean} [opts.showGoals]  - Toggle goal event markers.
   */
  function update(opts = {}) {
    if (opts.data !== undefined) _data = opts.data;
    if (opts.showGoals !== undefined) _showGoals = opts.showGoals;
    _render();
  }

  return { svg, g, update };
}
