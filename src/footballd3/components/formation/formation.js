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
//   update(1); // transition to formation period index 1

import { createPitch } from "../pitch/pitch.js?v=3";

const NODE_R = 14;

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
});
document.body.appendChild(_tooltip);


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
 */
function renderPeriod(g, px, period, nodeColor, labelColor, bounds) {
  g.selectAll(".fm-player").remove();

  period.players.forEach(player => {
    const [rawCx, rawCy] = px(player.template_x, player.template_y);
    const cx = Math.max(bounds.minX, Math.min(bounds.maxX, rawCx));
    const cy = Math.max(bounds.minY, Math.min(bounds.maxY, rawCy));

    const playerG = g.append("g")
      .attr("class", "fm-player")
      .style("cursor", "pointer");

    playerG.append("circle")
      .attr("cx", cx).attr("cy", cy)
      .attr("r", NODE_R)
      .attr("fill", nodeColor)
      .attr("stroke", "#FAF7F0")
      .attr("stroke-width", 1.5);

    // Jersey number inside the circle.
    playerG.append("text")
      .attr("x", cx).attr("y", cy)
      .attr("dy", "0.36em")
      .attr("text-anchor", "middle")
      .attr("font-family", "Geist Mono, monospace")
      .attr("font-size", "11px")
      .attr("font-weight", "600")
      .attr("fill", "#FAF7F0")
      .attr("pointer-events", "none")
      .text(player.jersey_number);

    // Display name below the circle.
    playerG.append("text")
      .attr("x", cx).attr("y", cy + NODE_R + 9)
      .attr("text-anchor", "middle")
      .attr("font-family", "Geist, sans-serif")
      .attr("font-size", "9px")
      .attr("fill", labelColor)
      .attr("pointer-events", "none")
      .text(player.display_name);

    playerG
      .on("mouseover", () => {
        _tooltip.innerHTML =
          `<span style="font-weight:600">${player.display_name}</span><br>` +
          `#${player.jersey_number} &middot; ${player.position}`;
        _tooltip.style.display = "block";
      })
      .on("mousemove", event => {
        _tooltip.style.left = (event.clientX + 14) + "px";
        _tooltip.style.top  = (event.clientY - 28) + "px";
      })
      .on("mouseout", () => {
        _tooltip.style.display = "none";
      });
  });
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
 * @param {Object} [config] - Optional visual configuration.
 * @param {number}  [config.pxPerYard=7]          - Pixels per StatsBomb yard.
 * @param {string}  [config.theme="whiteboard"]    - Pitch theme ("whiteboard" or "green").
 * @param {string}  [config.nodeColor="#1E3A5F"]   - Player circle fill color.
 * @param {string}  [config.labelColor="#171717"]  - Surname label fill color.
 * @returns {{ svg: d3.Selection, g: d3.Selection, px: Function, update: Function }}
 *   svg — the SVG element.
 *   g   — the pitch group; append further overlays here.
 *   px  — pixel conversion fn: (sbX, sbY) => [screenX, screenY].
 *   update(periodIdx) — transition to a different formation period.
 */
export function createFormation(selection, data, config = {}) {
  const {
    pxPerYard  = 7,
    theme      = "whiteboard",
    nodeColor  = "#1E3A5F",
    labelColor = "#171717",
  } = config;

  const { svg, g, px, width, height, config: pitchCfg } = createPitch(selection, {
    mode:        "full",
    orientation: "vertical",
    flipAttack:  true,
    pxPerYard,
    theme,
    showGoals:   true,
  });

  // Keep node circles inside the pitch lines at all pxPerYard values.
  const pad = pitchCfg.padding;
  const bounds = {
    minX: pad + NODE_R,
    maxX: width  - pad - NODE_R,
    minY: pad + NODE_R,
    maxY: height - pad - NODE_R,
  };

  renderPeriod(g, px, data.periods[0], nodeColor, labelColor, bounds);

  /**
   * Transition the diagram to a different formation period.
   *
   * Removes existing player markers and re-renders for the new period.
   *
   * @param {number} periodIdx - Zero-based index into data.periods.
   */
  function update(periodIdx) {
    const period = data.periods[periodIdx];
    if (!period) return;
    renderPeriod(g, px, period, nodeColor, labelColor, bounds);
  }

  return { svg, g, px, update };
}
