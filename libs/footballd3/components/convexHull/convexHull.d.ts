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
 * Accepts two data shapes:
 * - `{ sides: [...] }` — the original two-hull (offense/defense) shape sourced
 *   from a 360 freeze-frame snapshot of both teams' visible players at one
 *   instant (see extract_convex_hull.py).
 * - `{ points: [[x,y],...] }` — a single flat list of StatsBomb-space points
 *   (e.g. one player's accumulated touch locations). The hull is computed
 *   client-side via d3.polygonHull — pure geometry over an already-filtered
 *   point set, not statistical/analytical judgment, so this stays within the
 *   "Python owns analysis, D3 only renders" seam. Renders nothing for fewer
 *   than 3 points (d3.polygonHull returns null there). For 3+ collinear
 *   points d3.polygonHull does NOT return null — it returns a degenerate
 *   2-point "hull" (the two extremes), which still renders as a thin line;
 *   this is d3.polygonHull's own documented behavior, not a bug here.
 *
 * @param {Object} pitch - Return value of createPitch(). Uses pitch.g and pitch.px.
 * @param {Object} data  - Either the `{ sides }` or `{ points }` shape described above.
 * @param {Object} [config={}] - Rendering options:
 *   @param {string}  [config.toggle="both"]         - Which hull(s) to show in
 *                                                     `sides` mode: "offense" |
 *                                                     "defense" | "both". Ignored
 *                                                     in `points` mode.
 *   @param {string}  [config.offenseColor="#9F1239"] - Fill/stroke for the offense hull.
 *   @param {string}  [config.defenseColor="#1E3A5F"] - Fill/stroke for the defense hull.
 *   @param {string}  [config.pointsColor="#9F1239"]  - Fill/stroke for the single
 *                                                      hull rendered in `points` mode.
 *   @param {number}  [config.fillOpacity=0.18]       - Hull fill opacity.
 *   @param {number}  [config.strokeOpacity=0.55]     - Hull stroke opacity.
 *   @param {number}  [config.strokeWidth=1.5]        - Hull stroke width in px.
 *   @param {boolean} [config.mirrorX=false]          - Mirror x as 120-x before px().
 *                                                      Must match the mirrorX value
 *                                                      passed to createFreezeFrame().
 * @returns {{ g: d3.Selection, px: Function, update: function }}
 *   g  — the <g class="ch"> group appended to pitch.g.
 *   px — the coordinate mapper used (pitch.px, optionally with mirrorX applied).
 *   update(newData) — replace the data (either shape) and re-render.
 */
export function createConvexHull(pitch: any, data: any, config?: {
    toggle?: string;
    offenseColor?: string;
    defenseColor?: string;
    pointsColor?: string;
    fillOpacity?: number;
    strokeOpacity?: number;
    strokeWidth?: number;
    mirrorX?: boolean;
}): {
    g: d3.Selection<any, any, any, any>;
    px: Function;
    update: Function;
};
import * as d3 from "d3";
