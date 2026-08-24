/**
 * momentumChart.js — match momentum chart built from per-minute xT threat.
 *
 * Renders a filled area curve that crosses a zero baseline across match minutes.
 * Positive values indicate the home team generating more attacking threat; negative
 * values indicate the away team. The curve is a recency-weighted rolling window over
 * per-minute peak xT deltas — not a possession count or pass volume.
 *
 * ORIENTATIONS
 * "horizontal" (default): time flows left→right on the X axis; home fills above
 *   the zero baseline, away fills below. Matches the conventional xT timeline layout.
 * "vertical": time flows top→bottom on the Y axis; home territory fills to the right
 *   of the zero baseline, away to the left. Useful for stacking alongside a vertical
 *   pitch map or for match-report layouts where time runs down the page.
 *
 * READING THE CHART
 * Distance from zero = relative attacking-threat gap at that minute. The curve is
 * smooth by design (3-min default window). When both window curves are shown, divergence
 * between them means the narrative is window-sensitive — treat with caution.
 *
 * LIMITATIONS
 * Attacking-threat momentum only — sees the team on the ball, not defensive resistance
 * or off-ball pressure. See README.md for full construction caveats.
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
 * Format a momentum value for display, always showing sign.
 * @param {number} v
 * @returns {string}
 */
function _fmtMomentum(v) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(4)}`;
}

/**
 * Format an xT threat value for display (4 decimal places).
 * @param {number} v
 * @returns {string}
 */
function _fmtThreat(v) {
  return v.toFixed(4);
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Render a match momentum chart as a filled area curve crossing zero.
 *
 * Creates a standalone SVG inside the given selection. Supports two orientations:
 * "horizontal" (time on X, momentum on Y) and "vertical" (time on Y, momentum on X).
 * The SVG dimensions are swapped automatically when orientation changes via update().
 *
 * In horizontal mode: config.width drives the time axis, config.height drives momentum.
 * In vertical mode: those dimensions are swapped — the SVG becomes height×width so the
 * time axis spans config.width pixels and the momentum axis spans config.height pixels.
 *
 * @param {d3.Selection} selection   - D3 selection of the container element.
 * @param {Object}       data        - momentum_{match_id}.json contract:
 *   { home_team, away_team,
 *     minutes: [{minute, home_threat, away_threat, momentum}],
 *     secondary_minutes: [{minute, home_threat, away_threat, momentum}],
 *     goals: [{minute, team, player, is_own_goal}],
 *     red_cards: [{minute, team, player}],
 *     params, metadata }
 * @param {Object}  [config={}]                        - Rendering options.
 * @param {number}  [config.width=760]                 - Time-axis dimension in pixels.
 * @param {number}  [config.height=220]                - Momentum-axis dimension in pixels.
 * @param {Object}  [config.padding]                   - Inner padding for horizontal mode.
 *   Defaults: { top: 36, right: 24, bottom: 40, left: 52 }.
 * @param {string}  [config.homeColor="#1E3A5F"]       - Fill color for home territory.
 * @param {string}  [config.awayColor="#9F1239"]       - Fill color for away territory.
 * @param {boolean} [config.showGoals=true]            - Render goal event markers.
 * @param {boolean} [config.showCards=true]            - Render red card event markers.
 * @param {boolean} [config.showSecondaryWindow=true]  - Overlay the secondary window.
 * @param {string}  [config.orientation="horizontal"]  - "horizontal" or "vertical".
 * @returns {{
 *   svg:           d3.Selection,
 *   g:             d3.Selection,
 *   timeScale:     d3.ScaleLinear,
 *   momentumScale: d3.ScaleLinear,
 *   update:        function
 * }}
 *   svg:           The created SVG selection.
 *   g:             The main <g> group (use for custom overlays).
 *   timeScale:     Minutes → pixel scale (horizontal: maps to X; vertical: maps to Y).
 *   momentumScale: Momentum → pixel scale (horizontal: maps to Y; vertical: maps to X).
 *   update:        function({ data?, orientation?, showSecondaryWindow?, showGoals?, showCards? })
 *                  Re-renders with updated options. Any omitted key retains its current value.
 */
export function createMomentumChart(selection, data, config = {}) {
  const {
    width               = 760,
    height              = 220,
    padding             = { top: 36, right: 24, bottom: 40, left: 52 },
    homeColor           = "#1E3A5F",
    awayColor           = "#9F1239",
    showGoals           = true,
    showCards           = true,
    showSecondaryWindow = true,
    orientation         = "horizontal",
  } = config;

  // Vertical mode uses different padding defaults: left needs room for minute labels,
  // right/left need room for goal chips, bottom for momentum axis labels.
  const _vPad = { top: 20, right: 44, bottom: 36, left: 44 };

  const svg = selection.append("svg");
  const g   = svg.append("g");

  // ── Mutable state ─────────────────────────────────────────────────────────────
  let _data                = data;
  let _showGoals           = showGoals;
  let _showCards           = showCards;
  let _showSecondaryWindow = showSecondaryWindow;
  let _orientation         = orientation;

  // Exposed scales — updated on every render so external callers always get current refs.
  let timeScale     = d3.scaleLinear();
  let momentumScale = d3.scaleLinear();

  // ── Scales ────────────────────────────────────────────────────────────────────

  /**
   * Build time and momentum scales for the given inner dimensions and orientation.
   *
   * timeScale always maps match minutes to pixels — to X in horizontal mode, to Y
   * in vertical mode. momentumScale always maps the momentum value to pixels — to Y
   * (inverted) in horizontal, to X in vertical.
   *
   * @param {Object} d    - Full data object.
   * @param {number} iW   - Inner chart width in pixels.
   * @param {number} iH   - Inner chart height in pixels.
   * @param {boolean} isH - True for horizontal orientation.
   * @returns {{ timeScale, momentumScale, maxMinute, extent }}
   */
  function _buildScales(d, iW, iH, isH) {
    const maxMinute = Math.max(...d.minutes.map(m => m.minute));
    const allMomentum = [
      ...d.minutes.map(m => m.momentum),
      ...d.secondary_minutes.map(m => m.momentum),
    ];
    const maxAbs = Math.max(...allMomentum.map(Math.abs), 0.001);
    const extent = maxAbs * 1.15;

    const ts = d3.scaleLinear()
      .domain([0, maxMinute + 1])
      .range(isH ? [0, iW] : [0, iH]);

    // Horizontal: invert range so positive momentum → higher up (smaller Y).
    // Vertical: positive momentum → rightward (larger X).
    const ms = d3.scaleLinear()
      .domain([-extent, extent])
      .range(isH ? [iH, 0] : [0, iW]);

    return { timeScale: ts, momentumScale: ms, maxMinute, extent };
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
    timeScale     = scales.timeScale;
    momentumScale = scales.momentumScale;
    const { maxMinute, extent } = scales;

    // ── Background ─────────────────────────────────────────────────────────────
    g.append("rect")
      .attr("width", iW).attr("height", iH)
      .attr("fill", "var(--elevated, #FAF7F0)").attr("rx", 2);

    // Zero baseline.
    const z = momentumScale(0);
    g.append("line")
      .attr("class", "mc-zero-line")
      .attr(isH ? "x1" : "x1", isH ? 0    : z)
      .attr(isH ? "y1" : "y1", isH ? z    : 0)
      .attr(isH ? "x2" : "x2", isH ? iW   : z)
      .attr(isH ? "y2" : "y2", isH ? z    : iH)
      .attr("stroke", "var(--border-strong, #D4D4D4)")
      .attr("stroke-width", 1.5);

    // Soft gridlines at ±60% of the momentum extent.
    [extent * 0.6, -extent * 0.6].forEach(v => {
      const p = momentumScale(v);
      g.append("line")
        .attr("x1", isH ? 0  : p).attr("y1", isH ? p  : 0)
        .attr("x2", isH ? iW : p).attr("y2", isH ? p  : iH)
        .attr("stroke", "var(--border, #E5E5E5)")
        .attr("stroke-width", 0.75)
        .attr("stroke-dasharray", "3,4");
    });

    // Half-time divider at minute 45.
    if (maxMinute > 45) {
      const htPos = timeScale(45);
      g.append("line")
        .attr("class", "mc-ht-line")
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

    // ── Filled areas ───────────────────────────────────────────────────────────
    const curve = d3.curveCatmullRom.alpha(0.5);

    let homeArea, awayArea, momentumLine;
    if (isH) {
      homeArea = d3.area()
        .x(m => timeScale(m.minute))
        .y0(z).y1(m => momentumScale(Math.max(0, m.momentum)))
        .curve(curve);
      awayArea = d3.area()
        .x(m => timeScale(m.minute))
        .y0(z).y1(m => momentumScale(Math.min(0, m.momentum)))
        .curve(curve);
      momentumLine = d3.line()
        .x(m => timeScale(m.minute))
        .y(m => momentumScale(m.momentum))
        .curve(curve);
    } else {
      homeArea = d3.area()
        .y(m => timeScale(m.minute))
        .x0(z).x1(m => momentumScale(Math.max(0, m.momentum)))
        .curve(curve);
      awayArea = d3.area()
        .y(m => timeScale(m.minute))
        .x0(z).x1(m => momentumScale(Math.min(0, m.momentum)))
        .curve(curve);
      momentumLine = d3.line()
        .y(m => timeScale(m.minute))
        .x(m => momentumScale(m.momentum))
        .curve(curve);
    }

    g.append("path").attr("class", "mc-home-area")
      .datum(d.minutes).attr("d", homeArea)
      .attr("fill", homeColor).attr("fill-opacity", 0.25).attr("stroke", "none");

    g.append("path").attr("class", "mc-away-area")
      .datum(d.minutes).attr("d", awayArea)
      .attr("fill", awayColor).attr("fill-opacity", 0.25).attr("stroke", "none");

    g.append("path").attr("class", "mc-primary-line")
      .datum(d.minutes).attr("d", momentumLine)
      .attr("fill", "none")
      .attr("stroke", "var(--muted, #525252)").attr("stroke-width", 1.5).attr("stroke-opacity", 0.6);

    // Secondary window overlay.
    if (_showSecondaryWindow && d.secondary_minutes?.length > 0) {
      g.append("path").attr("class", "mc-secondary-line")
        .datum(d.secondary_minutes).attr("d", momentumLine)
        .attr("fill", "none")
        .attr("stroke", "var(--muted, #525252)").attr("stroke-width", 1)
        .attr("stroke-opacity", 0.3).attr("stroke-dasharray", "5,4");
    }

    // ── Team labels ────────────────────────────────────────────────────────────
    if (isH) {
      g.append("text")
        .attr("x", 4).attr("y", padding.top * -0.55)
        .attr("font-family", "Geist, sans-serif")
        .attr("font-size", "11px").attr("font-weight", "600")
        .attr("fill", homeColor).text(`${d.home_team} ▲`);

      g.append("text")
        .attr("x", 4).attr("y", iH + padding.bottom * 0.7)
        .attr("font-family", "Geist, sans-serif")
        .attr("font-size", "11px").attr("font-weight", "600")
        .attr("fill", awayColor).text(`${d.away_team} ▼`);
    } else {
      // Vertical: labels sit above the chart, flanking the zero line.
      g.append("text")
        .attr("x", momentumScale(extent * 0.45)).attr("y", -6)
        .attr("text-anchor", "middle")
        .attr("font-family", "Geist, sans-serif")
        .attr("font-size", "11px").attr("font-weight", "600")
        .attr("fill", homeColor).text(`${d.home_team} →`);

      g.append("text")
        .attr("x", momentumScale(-extent * 0.45)).attr("y", -6)
        .attr("text-anchor", "middle")
        .attr("font-family", "Geist, sans-serif")
        .attr("font-size", "11px").attr("font-weight", "600")
        .attr("fill", awayColor).text(`← ${d.away_team}`);
    }

    // ── Event markers, axes, tooltip ───────────────────────────────────────────
    if (_showGoals) _renderGoalMarkers(d, isH, iW, iH);
    if (_showCards) _renderCardMarkers(d, isH, iW, iH);
    _renderAxes(d, isH, iW, iH, maxMinute);
    _renderTooltipOverlay(d, isH, iW, iH);
  }

  // ── Goal markers ──────────────────────────────────────────────────────────────

  /**
   * Render goal event markers — dashed lines + G chips + scorer label.
   *
   * Horizontal: vertical dashed line at the goal minute; chip above axis for home,
   *   below for away; last-name label flanking the chip.
   * Vertical: horizontal dashed line at the goal minute; chip to the right of zero
   *   for home, left for away; label beside the chip along the time axis.
   *
   * @param {Object}  d    - Full data object.
   * @param {boolean} isH  - True for horizontal orientation.
   * @param {number}  iW   - Inner width.
   * @param {number}  iH   - Inner height.
   */
  function _renderGoalMarkers(d, isH, iW, iH) {
    d.goals.forEach(goal => {
      const isHome = goal.team === d.home_team;
      const color  = isHome ? homeColor : awayColor;
      const tp     = timeScale(goal.minute);

      const nameParts = goal.player.split(" ");
      const shortName = nameParts[nameParts.length - 1];

      // Dashed line through full chart.
      g.append("line")
        .attr("class", "mc-goal-line")
        .attr("x1", isH ? tp : 0 ).attr("y1", isH ? 0    : tp)
        .attr("x2", isH ? tp : iW).attr("y2", isH ? iH   : tp)
        .attr("stroke", color).attr("stroke-width", 1.2)
        .attr("stroke-dasharray", "3,3").attr("stroke-opacity", 0.7);

      if (isH) {
        // Chip above zero for home, below for away.
        const chipY = isHome ? -14 : iH + 14;
        g.append("circle")
          .attr("cx", tp).attr("cy", chipY)
          .attr("r", 8).attr("fill", color).attr("fill-opacity", 0.9);

        g.append("text")
          .attr("x", tp).attr("y", chipY + 1)
          .attr("text-anchor", "middle").attr("dominant-baseline", "middle")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "8px").attr("font-weight", "700")
          .attr("fill", "#FAF7F0").attr("pointer-events", "none")
          .text("G");

        const labelY = isHome ? -26 : iH + 26;
        g.append("text").attr("class", "mc-goal-label")
          .attr("x", tp).attr("y", labelY)
          .attr("text-anchor", "middle")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "9px").attr("fill", color).attr("fill-opacity", 0.85)
          .text(`${shortName} ${goal.minute}'`);

      } else {
        // Vertical: chip to the right of zero for home, left for away.
        const z      = momentumScale(0);
        const chipX  = isHome ? z + 14 : z - 14;
        g.append("circle")
          .attr("cx", chipX).attr("cy", tp)
          .attr("r", 8).attr("fill", color).attr("fill-opacity", 0.9);

        g.append("text")
          .attr("x", chipX).attr("y", tp + 1)
          .attr("text-anchor", "middle").attr("dominant-baseline", "middle")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "8px").attr("font-weight", "700")
          .attr("fill", "#FAF7F0").attr("pointer-events", "none")
          .text("G");

        // Label alongside chip in the direction away from zero.
        const labelX   = isHome ? chipX + 12 : chipX - 12;
        const labelAnchor = isHome ? "start" : "end";
        g.append("text").attr("class", "mc-goal-label")
          .attr("x", labelX).attr("y", tp + 1)
          .attr("text-anchor", labelAnchor).attr("dominant-baseline", "middle")
          .attr("font-family", "Geist Mono, monospace")
          .attr("font-size", "9px").attr("fill", color).attr("fill-opacity", 0.85)
          .text(`${shortName} ${goal.minute}'`);
      }
    });
  }

  // ── Card markers ──────────────────────────────────────────────────────────────

  /**
   * Render red card event markers — dashed lines + R chips.
   *
   * Horizontal: vertical dashed line centered on the chart height.
   * Vertical: horizontal dashed line centered on the chart width.
   *
   * @param {Object}  d    - Full data object.
   * @param {boolean} isH  - True for horizontal orientation.
   * @param {number}  iW   - Inner width.
   * @param {number}  iH   - Inner height.
   */
  function _renderCardMarkers(d, isH, iW, iH) {
    const cardColor = "#7F1D1D";
    d.red_cards.forEach(card => {
      const tp = timeScale(card.minute);

      g.append("line")
        .attr("class", "mc-card-line")
        .attr("x1", isH ? tp : 0 ).attr("y1", isH ? 0    : tp)
        .attr("x2", isH ? tp : iW).attr("y2", isH ? iH   : tp)
        .attr("stroke", cardColor).attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "3,3").attr("stroke-opacity", 0.8);

      const chipX = isH ? tp      : iW / 2;
      const chipY = isH ? iH / 2  : tp;
      g.append("circle")
        .attr("cx", chipX).attr("cy", chipY)
        .attr("r", 7).attr("fill", cardColor).attr("fill-opacity", 0.9);

      g.append("text")
        .attr("x", chipX).attr("y", chipY + 1)
        .attr("text-anchor", "middle").attr("dominant-baseline", "middle")
        .attr("font-family", "Geist Mono, monospace")
        .attr("font-size", "8px").attr("font-weight", "700")
        .attr("fill", "#FAF7F0").attr("pointer-events", "none")
        .text("R");
    });
  }

  // ── Axes ──────────────────────────────────────────────────────────────────────

  /**
   * Render time-axis minute ticks and momentum-axis value ticks.
   *
   * Horizontal: minute ticks on the bottom X axis; momentum ticks on the left Y axis.
   * Vertical:   minute ticks on the left Y axis; momentum ticks on the bottom X axis.
   *
   * @param {Object}  d          - Full data object.
   * @param {boolean} isH        - True for horizontal orientation.
   * @param {number}  iW         - Inner width.
   * @param {number}  iH         - Inner height.
   * @param {number}  maxMinute  - Maximum minute in the data.
   */
  function _renderAxes(d, isH, iW, iH, maxMinute) {
    const stdMinuteTicks = [0, 15, 30, 45, 60, 75, 90];
    const minuteTicks = maxMinute > 90
      ? [...stdMinuteTicks, maxMinute]
      : stdMinuteTicks.filter(t => t <= maxMinute);

    // Time ticks (minute axis).
    minuteTicks.forEach(t => {
      const tp = timeScale(t);
      if (isH) {
        // Bottom X axis.
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
        // Left Y axis.
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
    if (isH) {
      g.append("line")  // X axis bottom border
        .attr("x1", 0).attr("y1", iH).attr("x2", iW).attr("y2", iH)
        .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 1);
      g.append("line")  // Y axis left border
        .attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", iH)
        .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 1);
    } else {
      g.append("line")  // Y axis left border
        .attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", iH)
        .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 1);
      g.append("line")  // X axis bottom border
        .attr("x1", 0).attr("y1", iH).attr("x2", iW).attr("y2", iH)
        .attr("stroke", "var(--border, #E5E5E5)").attr("stroke-width", 1);
    }

    // Momentum ticks (value axis) — top, zero, bottom of domain.
    const mDomain = momentumScale.domain();
    const mTicks  = [mDomain[1] * 0.6, 0, mDomain[0] * 0.6];
    mTicks.forEach(v => {
      const mp = momentumScale(v);
      if (isH) {
        // Left Y axis momentum ticks.
        g.append("line")
          .attr("x1", -4).attr("y1", mp).attr("x2", 0).attr("y2", mp)
          .attr("stroke", "var(--border-strong, #D4D4D4)").attr("stroke-width", 1);

        if (v !== 0) {
          g.append("text")
            .attr("x", -7).attr("y", mp + 1)
            .attr("text-anchor", "end").attr("dominant-baseline", "middle")
            .attr("font-family", "Geist Mono, monospace")
            .attr("font-size", "9px").attr("fill", "var(--faint, #A3A3A3)")
            .text(_fmtMomentum(v));
        }
      } else {
        // Bottom X axis momentum ticks.
        g.append("line")
          .attr("x1", mp).attr("y1", iH).attr("x2", mp).attr("y2", iH + 4)
          .attr("stroke", "var(--border-strong, #D4D4D4)").attr("stroke-width", 1);

        if (v !== 0) {
          g.append("text")
            .attr("x", mp).attr("y", iH + 14)
            .attr("text-anchor", "middle")
            .attr("font-family", "Geist Mono, monospace")
            .attr("font-size", "9px").attr("fill", "var(--faint, #A3A3A3)")
            .text(_fmtMomentum(v));
        }
      }
    });
  }

  // ── Tooltip overlay ───────────────────────────────────────────────────────────

  /**
   * Attach an invisible overlay rect that drives a minute-snapping crosshair and tooltip.
   *
   * Horizontal: crosshair is a vertical line; pointer snaps by X position.
   * Vertical:   crosshair is a horizontal line; pointer snaps by Y position.
   *
   * @param {Object}  d    - Full data object.
   * @param {boolean} isH  - True for horizontal orientation.
   * @param {number}  iW   - Inner width.
   * @param {number}  iH   - Inner height.
   */
  function _renderTooltipOverlay(d, isH, iW, iH) {
    const overlay = g.append("rect")
      .attr("class", "mc-overlay")
      .attr("width", iW).attr("height", iH)
      .attr("fill", "transparent")
      .style("cursor", "crosshair");

    // Crosshair line — vertical for H, horizontal for V.
    const crosshair = g.append("line")
      .attr("class", "mc-crosshair")
      .attr("x1", isH ? 0   : 0 ).attr("y1", isH ? 0    : 0 )
      .attr("x2", isH ? 0   : iW).attr("y2", isH ? iH   : 0 )
      .attr("stroke", "var(--muted, #525252)").attr("stroke-width", 1)
      .attr("stroke-dasharray", "3,3").attr("stroke-opacity", 0.5)
      .attr("pointer-events", "none").attr("display", "none");

    overlay
      .on("mousemove", function (ev) {
        const [px, py] = d3.pointer(ev, this);
        const rawMinute = isH ? timeScale.invert(px) : timeScale.invert(py);
        const minute = Math.round(rawMinute);
        const idx = d.minutes.findIndex(m => m.minute === minute);
        if (idx < 0) return;

        const m  = d.minutes[idx];
        const sm = d.secondary_minutes?.[idx];
        const tp = timeScale(minute);

        crosshair.attr("display", null);
        if (isH) {
          crosshair.attr("x1", tp).attr("x2", tp);
        } else {
          crosshair.attr("y1", tp).attr("y2", tp);
        }

        const homeLabel = `<span style="color:${homeColor};font-weight:600">${d.home_team}</span>`;
        const awayLabel = `<span style="color:${awayColor};font-weight:600">${d.away_team}</span>`;
        const secLine = sm
          ? `<span style="color:#A3A3A3">secondary  ${_fmtMomentum(sm.momentum)}</span><br>`
          : "";

        const tooltip = getTooltip();
        tooltip.innerHTML =
          `<strong>${minute}'</strong><br>` +
          `${homeLabel} ${_fmtThreat(m.home_threat)}<br>` +
          `${awayLabel} ${_fmtThreat(m.away_threat)}<br>` +
          `momentum  ${_fmtMomentum(m.momentum)}<br>` +
          secLine;
        tooltip.style.display = "block";
        tooltip.style.left = (ev.clientX + 14) + "px";
        tooltip.style.top  = (ev.clientY - 28) + "px";
      })
      .on("mouseout", function () {
        crosshair.attr("display", "none");
        getTooltip().style.display = "none";
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
   * @param {Object}  [opts.data]                  - Replace the full data object.
   * @param {string}  [opts.orientation]            - "horizontal" or "vertical".
   * @param {boolean} [opts.showSecondaryWindow]    - Toggle the secondary window overlay.
   * @param {boolean} [opts.showGoals]              - Toggle goal markers.
   * @param {boolean} [opts.showCards]              - Toggle red card markers.
   */
  function update(opts = {}) {
    if (opts.data                !== undefined) _data                = opts.data;
    if (opts.orientation         !== undefined) _orientation         = opts.orientation;
    if (opts.showSecondaryWindow !== undefined) _showSecondaryWindow = opts.showSecondaryWindow;
    if (opts.showGoals           !== undefined) _showGoals           = opts.showGoals;
    if (opts.showCards           !== undefined) _showCards           = opts.showCards;
    _render();
  }

  return { svg, g, timeScale, momentumScale, update };
}
