// footballd3/components/freezeFrame/freezeFrame.js
//
// Renders a static 360 freeze-frame snapshot as a layer on an existing pitch.
// Caller creates the pitch with createPitch(), then passes the returned object here.
// No pitch is re-rendered inside this component; all elements land on pitch.g.
//
// StatsBomb normalises all attacks left→right, so freeze-frame x-coords for
// attacking events (shots, goals) are always > 60. When the pitch uses
// mode:"half" (domain [0,60]), pass mirrorX:true to reflect x as 120-x,
// matching the same convention used by shotMap.js.
//
// Usage:
//   import { createPitch }       from "../pitch/pitch.js";
//   import { createFreezeFrame } from "../freezeFrame/freezeFrame.js";
//   const pitch = createPitch(d3.select("#svg"), { mode: "half", orientation: "vertical" });
//   const { update } = createFreezeFrame(pitch, goalFrameData, { mirrorX: true });
//   update(nextGoalFrameData);   // swap to a different freeze frame

const SB_PITCH_WIDTH = 120;

/**
 * Compute SVG polygon points string for a diamond centred at (cx, cy).
 *
 * The diamond's bounding box is 2r × 2r — the same footprint as a circle of
 * radius r — so keepers are visually comparable in size to field players.
 *
 * @param {number} cx - Centre x in pixels.
 * @param {number} cy - Centre y in pixels.
 * @param {number} r  - Half-diagonal in pixels (equals markerRadius).
 * @returns {string} SVG points attribute string "x1,y1 x2,y2 x3,y3 x4,y4".
 */
function diamondPoints(cx, cy, r) {
  return `${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`;
}

/**
 * Creates a 360 freeze-frame overlay on an existing pitch.
 *
 * Renders player positions and the ball for one instant of play. Players are
 * visually distinguished by team side (teammate vs opponent fill), role
 * (keeper = diamond shape), and actor (outer ring around the player who
 * performed the action). An optional broadcast field-of-view polygon can be
 * toggled via config.showVisibleArea.
 *
 * All coordinates are StatsBomb-native 120×80 yards; the pitch's px() function
 * handles pixel mapping. No pitch is re-rendered inside this component.
 *
 * @param {Object} pitch  - Return value of createPitch(): { svg, g, px, ... }.
 * @param {Object} data   - One freeze-frame snapshot (a single entry from goals[]).
 * @param {Object} [config] - Optional visual configuration.
 * @param {boolean} [config.showVisibleArea=false]    - Show the broadcast FOV polygon.
 * @param {boolean} [config.mirrorX=false]            - Reflect x as (120 - x) before calling px().
 *   Required when the pitch uses mode:"half" and the data contains attacking-half coordinates
 *   (x > 60). Mirrors the StatsBomb coordinate onto the [0,60] half-pitch domain — the same
 *   convention used by shotMap.js.
 * @param {string}  [config.teamColor="#1E3A5F"]      - Fill for teammate markers.
 * @param {string}  [config.opponentColor="#9F1239"]  - Fill for opponent markers.
 * @param {string}  [config.actorRingColor="#FAF7F0"] - Stroke colour of the actor ring.
 * @param {number}  [config.actorRingWidth=3]         - Stroke-width of the actor ring (px).
 * @param {number}  [config.actorRadiusBoost=2]       - Added to markerRadius for the ring radius.
 * @param {number}  [config.markerRadius=6]           - Base player marker radius (px).
 * @param {number}  [config.ballRadius=5]             - Ball marker radius (px).
 * @param {string}  [config.ballColor="#FAF7F0"]      - Ball fill colour.
 * @param {string}  [config.ballStroke="#171717"]     - Ball stroke colour.
 * @returns {{ g: d3.Selection, px: Function, update: Function }}
 *   g is pitch.g (append further overlays there).
 *   update(frameData) transitions the snapshot to new frame data without re-rendering the pitch.
 */
export function createFreezeFrame(pitch, data, config = {}) {
  const {
    showVisibleArea  = false,
    mirrorX          = false,
    teamColor        = "#1E3A5F",
    opponentColor    = "#9F1239",
    actorRingColor   = "#FAF7F0",
    actorRingWidth   = 3,
    actorRadiusBoost = 2,
    markerRadius     = 6,
    ballRadius       = 5,
    ballColor        = "#FAF7F0",
    ballStroke       = "#171717",
  } = config;

  const { g, px } = pitch;

  // Single group for all freeze-frame elements; cleared on update().
  const ffGroup = g.append("g").attr("class", "ff");

  function renderFrame(frameData, animate) {
    const dur = animate ? 250 : 0;

    // Coordinate helper: mirrors x onto the half-pitch domain when mirrorX is set.
    const pxM = (x, y) => px(mirrorX ? SB_PITCH_WIDTH - x : x, y);

    // 1. Visible-area polygon (broadcast FOV) — semi-transparent, dashed boundary.
    if (showVisibleArea && frameData.visible_area?.length >= 4) {
      const va = frameData.visible_area;
      const coords = [];
      for (let i = 0; i + 1 < va.length; i += 2) {
        coords.push(pxM(va[i], va[i + 1]));
      }
      const lineGen = d3.line().x(d => d[0]).y(d => d[1]);
      ffGroup.append("path")
        .attr("class", "ff-visible-area")
        .attr("d", lineGen(coords) + " Z")
        .attr("fill", "#1E3A5F")
        .attr("fill-opacity", 0)
        .attr("stroke", "#1E3A5F")
        .attr("stroke-opacity", 0)
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "4 3")
        .transition().duration(dur)
        .attr("fill-opacity", 0.06)
        .attr("stroke-opacity", 0.3);
    }

    // Partition: keepers get diamonds; field players get circles.
    const fieldPlayers = frameData.frame.filter(p => !p.keeper);
    const keepers      = frameData.frame.filter(p =>  p.keeper);
    const actor        = frameData.frame.find( p =>  p.actor);

    // 2. Opponent field-player circles, then 3. Teammate field-player circles.
    // Rendered in this order so teammates draw on top (higher visual priority).
    for (const [group, fill] of [
      [fieldPlayers.filter(p => !p.teammate), opponentColor],
      [fieldPlayers.filter(p =>  p.teammate), teamColor],
    ]) {
      ffGroup.selectAll(null)
        .data(group)
        .enter()
        .append("circle")
        .attr("class", "ff-player")
        .attr("cx", d => pxM(d.x, d.y)[0])
        .attr("cy", d => pxM(d.x, d.y)[1])
        .attr("r",  markerRadius)
        .attr("fill", fill)
        .style("opacity", 0)
        .transition().duration(dur)
        .style("opacity", 1);
    }

    // 4. Keeper diamonds — rotated-square polygon, same fill as their team side.
    for (const keeper of keepers) {
      const [kx, ky] = pxM(keeper.x, keeper.y);
      ffGroup.append("polygon")
        .attr("class", "ff-keeper")
        .attr("points", diamondPoints(kx, ky, markerRadius))
        .attr("fill", keeper.teammate ? teamColor : opponentColor)
        .style("opacity", 0)
        .transition().duration(dur)
        .style("opacity", 1);
    }

    // 5. Actor outer ring — concentric circle outline drawn on top of the actor's marker.
    if (actor) {
      const [ax, ay] = pxM(actor.x, actor.y);
      ffGroup.append("circle")
        .attr("class", "ff-actor-ring")
        .attr("cx", ax)
        .attr("cy", ay)
        .attr("r",  markerRadius + actorRadiusBoost)
        .attr("fill",         "none")
        .attr("stroke",       actorRingColor)
        .attr("stroke-width", actorRingWidth)
        .style("opacity", 0)
        .transition().duration(dur)
        .style("opacity", 1);
    }

    // 6. Ball — topmost; white fill + dark stroke for clear contrast against both themes.
    const [bx, by] = pxM(frameData.ball.x, frameData.ball.y);
    ffGroup.append("circle")
      .attr("class", "ff-ball")
      .attr("cx", bx)
      .attr("cy", by)
      .attr("r",  ballRadius)
      .attr("fill",         ballColor)
      .attr("stroke",       ballStroke)
      .attr("stroke-width", 1.5)
      .style("opacity", 0)
      .transition().duration(dur)
      .style("opacity", 1);
  }

  renderFrame(data, false);

  /**
   * Transition the freeze frame to a new snapshot without re-rendering the pitch.
   *
   * Old elements fade out over 150 ms, then the new frame fades in. If a second
   * update() call interrupts the fade-out transition, the catch handler ensures a
   * clean re-render regardless.
   *
   * @param {Object} frameData - New snapshot in the same shape as the original data
   *   argument: { ball: {x,y}, frame: [{x,y,teammate,actor,keeper}], visible_area, metadata }.
   */
  function update(frameData) {
    const current = ffGroup.selectAll("*");
    if (current.empty()) {
      renderFrame(frameData, true);
      return;
    }
    current
      .transition("ff-swap")
      .duration(150)
      .style("opacity", 0)
      .end()
      .then(() => {
        ffGroup.selectAll("*").remove();
        renderFrame(frameData, true);
      })
      .catch(() => {
        // Interrupted by a rapid second update; remove stale elements and re-render.
        ffGroup.selectAll("*").remove();
        renderFrame(frameData, true);
      });
  }

  return { g, px, update };
}
