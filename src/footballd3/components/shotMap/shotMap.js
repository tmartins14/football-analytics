import * as d3 from "d3";
import { createPitch } from "../pitch/pitch.js";

// StatsBomb normalises all attacks left→right, so shot x-coords are always > 60.
// Mirror onto the half-pitch by reflecting: mirroredX = 120 - shot.x.
const SB_PITCH_WIDTH = 120;

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
 * Creates a shot map given a blank pitch.
 *
 * @param {d3.Selection} selection - The D3 selection to render the shot map into.
 * @param {Array} shots - An array of shot objects, each containing x, y, xg, is_goal, player, outcome, and minute properties.
 * @param {Object} config - Configuration options for the shot map (see createPitch for shared options).
 * @param {number} [config.pxPerYard=8] - Pixels per StatsBomb yard.
 * @param {string} [config.orientation="horizontal"] - Pitch orientation passed to createPitch ("horizontal" or "vertical").
 * @param {string|Object} [config.theme="whiteboard"] - Pitch theme.
 * @param {string} [config.color="#1E3A5F"] - Team color for shot markers.
 * @param {"opacity"|"tier"} [config.styleMode="opacity"] - Marker style:
 *   "opacity" (default, unchanged) — uniform color/stroke, goals at full opacity,
 *   non-goals at 0.35, radius from a sqrt xG scale.
 *   "tier" — three-tier outcome encoding: goals get a solid color fill + heavier
 *   solid stroke; on-target/saved shots get a soft-tint fill + solid stroke;
 *   everything else (off-target, blocked, wayward) gets no fill + a dashed muted
 *   stroke. Radius is `(5 + xg*40) * shotScale`.
 * @param {number} [config.shotScale=1] - Multiplier on marker radius (both modes).
 * @param {string} [config.softColor] - Soft-tint fill for "tier" mode's on-target
 *   shots. Defaults to `color` at 13% opacity if not supplied.
 * @param {string} [config.mutedColor="#525252"] - Stroke for "tier" mode's
 *   off-target/blocked shots.
 * @param {Function} [config.onHover] - onHover(shot|null): called with the hovered
 *   shot object on mouseenter, and `null` on mouseleave. Fires alongside the
 *   built-in tooltip (not a replacement) unless config.showTooltip is false.
 * @param {boolean} [config.showTooltip=true] - Render the built-in floating
 *   tooltip on hover. Set false when the caller renders its own readout from
 *   onHover instead.
 * @returns {Object} An object containing the shot map group and a pixel conversion function.
 * @throws Will throw an error if the shots array is not properly formatted.
 */
export function createShotMap(selection, shots, config = {}) {
  const {
    pxPerYard   = 8,
    orientation = "horizontal",
    theme       = "whiteboard",
    color       = "#1E3A5F",
    styleMode   = "opacity",
    shotScale   = 1,
    softColor,
    mutedColor  = "#525252",
    onHover,
    showTooltip = true,
  } = config;

  const { g, px } = createPitch(selection, {
    mode: "half",
    orientation,
    pxPerYard,
    theme,
    showGoals: true,
  });

  const rScale = d3.scaleSqrt().domain([0, 0.5]).range([3, 14]);
  const soft = softColor || d3.color(color).copy({ opacity: 0.13 });

  shots.forEach(shot => {
    const [cx, cy] = px(SB_PITCH_WIDTH - shot.x, shot.y);
    const onTarget = shot.outcome === "Saved";
    const circle = g.append("circle")
      .attr("cx", cx)
      .attr("cy", cy);

    if (styleMode === "tier") {
      circle
        .attr("r", (5 + shot.xg * 40) * shotScale)
        .attr("fill", shot.is_goal ? color : (onTarget ? soft : "none"))
        .attr("stroke", shot.is_goal || onTarget ? color : mutedColor)
        .attr("stroke-width", shot.is_goal ? 1.7 : 1.2)
        .attr("stroke-dasharray", shot.is_goal || onTarget ? "0" : "3 2");
    } else {
      circle
        .attr("r", rScale(shot.xg) * shotScale)
        .attr("fill", color)
        .attr("fill-opacity", shot.is_goal ? 1 : 0.35)
        .attr("stroke", "var(--elevated, #FAF7F0)")
        .attr("stroke-width", 1);
    }

    circle
      .style("cursor", "pointer")
      .on("mouseover", () => {
        if (onHover) onHover(shot);
        if (!showTooltip) return;
        const tooltip = getTooltip();
        tooltip.innerHTML =
          `<span style="font-weight:600">${shot.display_name}</span><br>` +
          `${shot.outcome} &middot; min. ${shot.minute}<br>` +
          `<span style="color:#525252">xG ${shot.xg.toFixed(2)}</span>`;
        tooltip.style.display = "block";
      })
      .on("mousemove", event => {
        if (!showTooltip) return;
        const tooltip = getTooltip();
        tooltip.style.left = (event.clientX + 14) + "px";
        tooltip.style.top  = (event.clientY - 28) + "px";
      })
      .on("mouseout", () => {
        if (onHover) onHover(null);
        if (showTooltip) getTooltip().style.display = "none";
      });
  });

  return { g, px };
}
