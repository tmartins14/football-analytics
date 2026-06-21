import { createPitch } from "./pitch.js";

// StatsBomb normalises all attacks left→right, so shot x-coords are always > 60.
// Mirror onto the half-pitch by reflecting: mirroredX = 120 - shot.x.
const SB_PITCH_WIDTH = 120;

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

export function createShotMap(selection, shots, config = {}) {
  const {
    pxPerYard   = 8,
    orientation = "horizontal",
    theme       = "whiteboard",
  } = config;

  const { g, px } = createPitch(selection, {
    mode: "half",
    orientation,
    pxPerYard,
    theme,
    showGoals: true,
  });

  const rScale = d3.scaleSqrt().domain([0, 0.5]).range([3, 14]);

  shots.forEach(shot => {
    const [cx, cy] = px(SB_PITCH_WIDTH - shot.x, shot.y);
    g.append("circle")
      .attr("cx", cx)
      .attr("cy", cy)
      .attr("r", rScale(shot.xg))
      .attr("fill", shot.is_goal ? "#9F1239" : "#1E3A5F")
      .attr("fill-opacity", shot.is_goal ? 0.9 : 0.45)
      .attr("stroke", "#FAF7F0")
      .attr("stroke-width", 1)
      .on("mouseover", () => {
        _tooltip.innerHTML =
          `<span style="font-weight:600">${shot.player}</span><br>` +
          `${shot.outcome} &middot; min. ${shot.minute}<br>` +
          `<span style="color:#525252">xG ${shot.xg.toFixed(2)}</span>`;
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

  return { g, px };
}
