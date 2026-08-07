// footballd3/components/formation/formation.js
//
// Renders a declared formation diagram on a full pitch. Positions are canonical
// template slots derived from StatsBomb position labels — the coach's stated shape.
// They are NOT measured from play.
//
// Usage:
//   import { createPitch } from "../pitch/pitch.js";
//   import { createFormation } from "../formation/formation.js";
//   const pitch = createPitch(d3.select("#formation-svg"), { mode: "full" });
//   const { update } = createFormation(pitch, data);
//   update({ periodIdx: 1 }); // transition to formation period index 1
//
// SELECTION + BENCH (optional, additive)
// selectedId/onPlayerClick turn starter nodes into a player selector (a ring
// on the matching node); passing data.bench additionally renders a clickable
// substitute list below the pitch, in the same selection. Both are opt-in —
// omitting them renders exactly as before, so existing single-purpose
// consumers (e.g. the match dashboard's read-only FormationPanel) are
// unaffected. This is the "one team at a time" lineup selector: pass whichever
// team's formation+bench data is currently toggled into view; a team switch
// is the caller's concern (swap `data` and re-mount, or call createFormation
// again), not something this component owns.

import * as d3 from "d3";
import { createPitch } from "../pitch/pitch.js?v=3";

const NODE_R = 14;
const BENCH_ROW_HEIGHT = 22;
const BENCH_COLUMNS = 2;

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
    });
    document.body.appendChild(_tooltip);
  }
  return _tooltip;
}


/**
 * Render one formation period onto the pitch group.
 *
 * Removes existing player markers (class "fm-player") before drawing the new
 * period, so calling this repeatedly is safe.
 *
 * @param {d3.Selection} g - Pitch group from createPitch().
 * @param {Function} px - Pixel conversion fn from createPitch(): (sbX, sbY) => [screenX, screenY].
 * @param {Object} period - One period from formation JSON: { formation, players }.
 * @param {string} nodeColor - Fill color for player circles.
 * @param {string} labelColor - Fill color for surname labels.
 * @param {Object} bounds - Clamping box to keep circles inside pitch lines.
 * @param {number} bounds.minX - Minimum screen X for node center.
 * @param {number} bounds.maxX - Maximum screen X for node center.
 * @param {number} bounds.minY - Minimum screen Y for node center.
 * @param {number} bounds.maxY - Maximum screen Y for node center.
 * @param {string} backgroundColor - Stroke color separating nodes from the pitch surface.
 * @param {number} nodeRadius - Player circle radius in pixels.
 * @param {Function|null} onPlayerClick - Called with the player record on marker
 *   click. Suppressed for the Goalkeeper marker (cursor stays default, no
 *   handler attached) — a goalkeeper is not a selectable outfield player.
 * @param {number|string|null} selectedId - player_id of the currently selected
 *   player, or null. The matching node gets a highlight ring.
 * @param {string} selectedColor - Stroke color for the selection ring.
 */
function renderPeriod(g, px, period, nodeColor, labelColor, bounds, backgroundColor, nodeRadius, onPlayerClick, selectedId, selectedColor) {
  g.selectAll(".fm-player").remove();

  period.players.forEach(player => {
    const [rawCx, rawCy] = px(player.template_x, player.template_y);
    const cx = Math.max(bounds.minX, Math.min(bounds.maxX, rawCx));
    const cy = Math.max(bounds.minY, Math.min(bounds.maxY, rawCy));

    const isGoalkeeper = player.position === "Goalkeeper";
    const clickable = onPlayerClick && !isGoalkeeper;

    const playerG = g.append("g")
      .attr("class", "fm-player")
      .style("cursor", clickable ? "pointer" : "default");

    if (clickable) {
      playerG.on("click", () => onPlayerClick(player));
    }

    if (player.player_id === selectedId) {
      playerG.append("circle")
        .attr("class", "fm-selected-ring")
        .attr("cx", cx).attr("cy", cy)
        .attr("r", nodeRadius + 4)
        .attr("fill", "none")
        .attr("stroke", selectedColor)
        .attr("stroke-width", 2.5);
    }

    playerG.append("circle")
      .attr("cx", cx).attr("cy", cy)
      .attr("r", nodeRadius)
      .attr("fill", nodeColor)
      .attr("stroke", backgroundColor)
      .attr("stroke-width", 1.5);

    // Jersey number inside the circle.
    playerG.append("text")
      .attr("x", cx).attr("y", cy)
      .attr("dy", "0.36em")
      .attr("text-anchor", "middle")
      .attr("font-family", "Geist Mono, monospace")
      .attr("font-size", Math.max(9, nodeRadius * 0.8))
      .attr("font-weight", "600")
      .attr("fill", "#FAF7F0")
      .attr("pointer-events", "none")
      .text(player.jersey_number);

    // Display name below the circle.
    playerG.append("text")
      .attr("x", cx).attr("y", cy + nodeRadius + 9)
      .attr("text-anchor", "middle")
      .attr("font-family", "Geist, sans-serif")
      .attr("font-size", "9px")
      .attr("fill", labelColor)
      .attr("pointer-events", "none")
      .text(player.display_name);

    playerG
      .on("mouseover", () => {
        const tooltip = getTooltip();
        tooltip.innerHTML =
          `<span style="font-weight:600">${player.display_name}</span><br>` +
          `#${player.jersey_number} &middot; ${player.position}`;
        tooltip.style.display = "block";
      })
      .on("mousemove", event => {
        const tooltip = getTooltip();
        tooltip.style.left = (event.clientX + 14) + "px";
        tooltip.style.top  = (event.clientY - 28) + "px";
      })
      .on("mouseout", () => {
        getTooltip().style.display = "none";
      });
  });
}

/**
 * Render a clickable substitute bench list below the pitch.
 *
 * Wraps rows into BENCH_COLUMNS columns (left-to-right, top-to-bottom) rather
 * than one long column, keeping a typical 5-9 player bench compact. Each row:
 * jersey number, surname (last whitespace-separated token of display_name —
 * the same simple heuristic used throughout this app, not a name-parsing
 * library), and "on NN'". Goalkeeper substitutes are rendered but not
 * clickable, for the same reason starter Goalkeeper markers aren't — no
 * player-analysis data exists for a keeper.
 *
 * @param {d3.Selection} benchG - The `<g class="fm-bench">` group to render into.
 * @param {Array<Object>} bench - Substitute records: { player_id, display_name,
 *   jersey_number, position, on_minute }.
 * @param {number} innerWidth - Available width in pixels (pitch width minus padding).
 * @param {string} nodeColor - Jersey-number text color.
 * @param {string} labelColor - Surname/minute text color.
 * @param {number|string|null} selectedId - player_id of the currently selected
 *   player, or null.
 * @param {string} selectedColor - Highlight color for the selected row.
 * @param {Function|null} onPlayerClick - Called with the player record on row click.
 * @returns {number} Total bench height in pixels (for sizing the SVG).
 */
function renderBench(benchG, bench, innerWidth, nodeColor, labelColor, selectedId, selectedColor, onPlayerClick) {
  benchG.selectAll("*").remove();
  if (!bench || !bench.length) return 0;

  const columnWidth = innerWidth / BENCH_COLUMNS;
  const rows = Math.ceil(bench.length / BENCH_COLUMNS);

  const rowGroups = benchG.selectAll(".fm-bench-row")
    .data(bench)
    .join("g")
    .attr("class", "fm-bench-row")
    .attr("transform", (d, i) => {
      const col = Math.floor(i / rows);
      const row = i % rows;
      return `translate(${col * columnWidth}, ${row * BENCH_ROW_HEIGHT})`;
    })
    .style("cursor", d => (d.position === "Goalkeeper" ? "default" : "pointer"));

  rowGroups.append("rect")
    .attr("class", "fm-bench-ring")
    .attr("x", -4).attr("y", -14).attr("width", columnWidth - 10).attr("height", 20)
    .attr("rx", 4)
    .attr("fill", "none").attr("stroke", selectedColor).attr("stroke-width", 2)
    .style("display", d => (d.player_id === selectedId ? null : "none"));

  rowGroups.append("text")
    .attr("font-family", "Geist Mono, monospace").attr("font-size", "11px")
    .attr("fill", nodeColor).attr("font-weight", "600")
    .text(d => `#${d.jersey_number}`);

  rowGroups.append("text")
    .attr("x", 32)
    .attr("font-family", "Geist, sans-serif").attr("font-size", "11px")
    .attr("fill", labelColor)
    .text(d => surname(d.display_name));

  rowGroups.append("text")
    .attr("x", columnWidth - 16).attr("text-anchor", "end")
    .attr("font-family", "Geist Mono, monospace").attr("font-size", "10px")
    .attr("fill", "#8A8578")
    .text(d => `on ${d.on_minute}'`);

  rowGroups
    .filter(d => d.position !== "Goalkeeper" && onPlayerClick)
    .on("click", (event, d) => onPlayerClick(d));

  return rows * BENCH_ROW_HEIGHT;
}

/**
 * Last whitespace-separated token of a display name.
 *
 * @param {string} displayName - Full/nickname display name.
 * @returns {string} The surname heuristic used in the bench list.
 */
function surname(displayName) {
  const parts = String(displayName).trim().split(/\s+/);
  return parts[parts.length - 1];
}

/**
 * Creates a formation diagram on a full pitch.
 *
 * Renders the declared tactical formation for one team, using canonical
 * template-slot positions. Template coordinates are the coach's stated shape
 * derived from StatsBomb position labels — NOT measured from play. Each player
 * marker shows the jersey number and surname. A period index controls which
 * formation period (Starting XI or subsequent Tactical Shift) is displayed.
 *
 * Composes on pitch.js: calls createPitch() internally and appends all
 * formation elements onto the returned pitch group.
 *
 * @param {d3.Selection} selection - SVG element to render into.
 * @param {Object} data - Formation JSON contract.
 * @param {Array<Object>} data.periods - Ordered formation periods, each with:
 *   formation (str), from_minute (int), to_minute (int),
 *   players (Array<{ player, jersey_number, position, template_x, template_y }>).
 * @param {Object} data.metadata - Match and coordinate metadata.
 * @param {string} data.metadata.coordinate_note - States that template_x/y are
 *   canonical slots, not measured positions.
 * @param {Array<Object>} [data.bench] - Optional substitute list (the
 *   substitutes_{match_id}.json contract's one-team array): { player_id,
 *   display_name, jersey_number, position, on_minute }. Omit for a
 *   bench-less diagram (e.g. the match dashboard's read-only view) — the SVG
 *   is only sized taller than the pitch when this is provided.
 * @param {Object} [config] - Optional visual configuration.
 * @param {number}  [config.pxPerYard=7]          - Pixels per StatsBomb yard.
 * @param {number}  [config.padding=24]           - Padding around the pitch in pixels.
 * @param {string|Object} [config.theme="whiteboard"] - Pitch theme ("whiteboard", "green", or a token object).
 * @param {string}  [config.nodeColor="#1E3A5F"]   - Player circle fill color.
 * @param {string}  [config.labelColor="#171717"]  - Surname label fill color.
 * @param {string}  [config.backgroundColor="#FAF7F0"] - Stroke color separating player
 *   circles from the pitch surface — pass the current theme's page background so the
 *   separator matches in both light and dark themes.
 * @param {number}  [config.nodeRadius=14]        - Player circle radius in pixels.
 * @param {Function|null} [config.onPlayerClick=null] - Called with the player
 *   record ({ player_id, player, display_name, jersey_number, position,
 *   template_x, template_y } for a starter, or the bench record shape for a
 *   substitute) on marker/bench-row click. Suppressed for any Goalkeeper —
 *   a goalkeeper is not a selectable outfield player, so it gets
 *   cursor: default and no click handler instead of cursor: pointer.
 * @param {number|string|null} [config.selectedId=null] - player_id of the
 *   currently selected player (starter or bench), or null. The matching node/
 *   row gets a highlight ring — this is what turns the diagram into a
 *   selector rather than a read-only view.
 * @param {string}  [config.selectedColor="#F59E0B"] - Selection ring color.
 * @returns {{ svg: d3.Selection, g: d3.Selection, px: Function, update: Function }}
 *   svg — the SVG element.
 *   g   — the pitch group; append further overlays here.
 *   px  — pixel conversion fn: (sbX, sbY) => [screenX, screenY].
 *   update({ periodIdx?, selectedId? }) — transition to a different formation
 *     period and/or move the selection ring. Any omitted key retains its
 *     current value.
 */
export function createFormation(selection, data, config = {}) {
  const {
    pxPerYard       = 7,
    padding,
    theme           = "whiteboard",
    nodeColor       = "#1E3A5F",
    labelColor      = "#171717",
    backgroundColor = "#FAF7F0",
    nodeRadius      = NODE_R,
    onPlayerClick   = null,
    selectedColor   = "#F59E0B",
  } = config;
  let { selectedId = null } = config;

  const { svg, g, px, width, height, config: pitchCfg } = createPitch(selection, {
    mode:        "full",
    orientation: "vertical",
    flipAttack:  true,
    pxPerYard,
    ...(padding !== undefined ? { padding } : {}),
    theme,
    showGoals:   true,
  });

  // Keep node circles inside the pitch lines at all pxPerYard values.
  const pad = pitchCfg.padding;
  const bounds = {
    minX: pad + nodeRadius,
    maxX: width  - pad - nodeRadius,
    minY: pad + nodeRadius,
    maxY: height - pad - nodeRadius,
  };

  const benchG = svg.append("g")
    .attr("class", "fm-bench")
    .attr("transform", `translate(${pad}, ${height + 16})`);

  let currentPeriodIdx = 0;

  function render() {
    renderPeriod(
      g, px, data.periods[currentPeriodIdx], nodeColor, labelColor, bounds,
      backgroundColor, nodeRadius, onPlayerClick, selectedId, selectedColor
    );

    const benchHeight = renderBench(
      benchG, data.bench, width - pad * 2, nodeColor, labelColor,
      selectedId, selectedColor, onPlayerClick
    );

    // The pitch SVG is created at a fixed (pitch-only) height by pitch.js —
    // grow both the height attribute AND the viewBox together when a bench
    // is present, so the added space renders at true 1-unit-per-pixel scale
    // instead of vertically stretching the whole diagram to fill a taller
    // box with an unchanged viewBox.
    const totalHeight = height + (benchHeight ? benchHeight + 16 : 0);
    svg.attr("height", totalHeight).attr("viewBox", `0 0 ${width} ${totalHeight}`);
  }

  render();

  /**
   * Transition to a different formation period and/or move the selection ring.
   *
   * @param {Object} [opts={}] - Partial update.
   * @param {number} [opts.periodIdx] - Zero-based index into data.periods.
   * @param {number|string|null} [opts.selectedId] - New selected player_id.
   */
  function update(opts = {}) {
    if (opts.periodIdx !== undefined && data.periods[opts.periodIdx]) {
      currentPeriodIdx = opts.periodIdx;
    }
    if (opts.selectedId !== undefined) selectedId = opts.selectedId;
    render();
  }

  return { svg, g, px, update };
}
