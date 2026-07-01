/**
 * convexHull.js — territory-shape convex hull overlay for freeze-frame snapshots.
 *
 * Renders semi-transparent convex hull polygon(s) for one or both teams over an
 * existing freeze-frame + pitch render. This component does NOT re-render the
 * pitch or the player dots — it overlays hull geometry on top by inserting a
 * dedicated <g class="ch"> group into pitch.g, positioned below the freeze-frame
 * dot layer (<g class="ff">) regardless of call order.
 *
 * Coordinates flow unchanged from the Python extractor (StatsBomb-native 120×80 yards);
 * pitch.px() maps them to SVG screen space exactly as the freeze-frame layer does.
 *
 * OFFENSE / DEFENSE LABELING
 * "Offense" means the team in possession at the moment of the event, resolved from
 * possession_team_id in the Python extractor. "Defense" is the other team. These are
 * structural labels, not a judgment about who is "really" attacking.
 *
 * KEEPER EXCLUSION
 * Goalkeepers are excluded from hull computation by default (a deep keeper far from
 * the group balloons the hull into unoccupied dead space). The keeper marker remains
 * visible from the underlying freeze-frame layer. The Python extractor controls whether
 * keepers are included; includeKeeper in hull metadata reflects that choice.
 *
 * LIMITATIONS (read before interpreting hull area)
 * 1. Visible-player subset only: 360 data captures the broadcast view framed around
 *    the ball. The hull encloses only the on-screen players, not the full team.
 *    Hull area is not reliably comparable frame-to-frame because the visible set
 *    changes with camera framing.
 * 2. Asymmetric sampling: The camera often captures the two teams to different
 *    completeness. Comparing offense vs defense hull areas compares two differently-
 *    complete samples — read shape and position, not a territory scoreboard.
 * 3. Convex overstatement: When one player is far from the group the hull encloses
 *    unoccupied space between them. A concave/alpha-shape variant is a noted future
 *    option.
 */

/**
 * Render convex hull polygon(s) over an existing pitch+freeze-frame layer.
 *
 * Inserts a <g class="ch"> group into pitch.g, placed before <g class="ff"> so
 * hull polygons sit behind player dots. Safe to call before or after
 * createFreezeFrame().
 *
 * @param {Object} pitch - Return value of createPitch(). Uses pitch.g and pitch.px.
 * @param {Object} data  - One hull entry from convex_hull_{match_id}_goals.json:
 *   { sides: [{ side, team_name, hull_vertices, area, player_count }], metadata }
 *   where side is "offense"|"defense", hull_vertices is [[x,y],...] in StatsBomb
 *   120×80 yards, area is in square yards, and player_count is the outfield-only count.
 * @param {Object} [config={}] - Rendering options:
 *   @param {string}  [config.toggle="both"]         - Which hull(s) to show:
 *                                                     "offense" | "defense" | "both"
 *   @param {string}  [config.offenseColor="#9F1239"] - Fill/stroke for offense hull.
 *   @param {string}  [config.defenseColor="#1E3A5F"] - Fill/stroke for defense hull.
 *   @param {number}  [config.fillOpacity=0.18]       - Hull fill opacity.
 *   @param {number}  [config.strokeOpacity=0.55]     - Hull stroke opacity.
 *   @param {number}  [config.strokeWidth=1.5]        - Hull stroke width in px.
 *   @param {boolean} [config.mirrorX=false]          - Mirror x as 120-x before px().
 *                                                      Must match the mirrorX value
 *                                                      passed to createFreezeFrame().
 * @returns {{ g: d3.Selection, px: Function }}
 *   g  — the <g class="ch"> group appended to pitch.g.
 *   px — the coordinate mapper used (pitch.px, optionally with mirrorX applied).
 */
export function createConvexHull(pitch, data, config = {}) {
  const {
    toggle        = "both",
    offenseColor  = "#9F1239",
    defenseColor  = "#1E3A5F",
    fillOpacity   = 0.18,
    strokeOpacity = 0.55,
    strokeWidth   = 1.5,
    mirrorX       = false,
  } = config;

  // Wrap pitch.px with optional mirrorX to match the freeze-frame coordinate space.
  const px = mirrorX
    ? (sbX, sbY) => pitch.px(120 - sbX, sbY)
    : (sbX, sbY) => pitch.px(sbX, sbY);

  // Insert hull group before .ff so hulls render behind player dots, regardless
  // of whether createFreezeFrame was called before or after this function.
  const ffG  = pitch.g.select("g.ff");
  const hullG = ffG.empty()
    ? pitch.g.append("g").attr("class", "ch")
    : pitch.g.insert("g", "g.ff").attr("class", "ch");

  const colorBySide = { offense: offenseColor, defense: defenseColor };

  for (const side of data.sides) {
    if (toggle !== "both" && toggle !== side.side) continue;

    const color  = colorBySide[side.side] ?? "#888";
    const pts    = side.hull_vertices.map(([x, y]) => px(x, y));

    // Build SVG path: move to first vertex, line to each subsequent, close.
    const d = "M" + pts.map(p => p.join(",")).join("L") + "Z";

    hullG
      .append("path")
      .attr("class", `ch-hull ch-hull-${side.side}`)
      .attr("d", d)
      .attr("fill", color)
      .attr("fill-opacity", fillOpacity)
      .attr("stroke", color)
      .attr("stroke-opacity", strokeOpacity)
      .attr("stroke-width", strokeWidth)
      .attr("stroke-linejoin", "round");
  }

  return { g: hullG, px };
}
