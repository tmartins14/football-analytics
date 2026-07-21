/**
 * Creates a team-shape overlay on an existing pitch.
 *
 * Renders the empirical team shape in two togglable views:
 *
 * ON-BALL (identified, event-based): mean position per named player from that
 *   team's open-play events while in possession. Data is split into lineup
 *   periods (one per substitution boundary); use updatePeriod(idx) to step
 *   through them. Each period shows the 11 players on the pitch at that time.
 *
 * OFF-BALL (anonymous, frame-based): pooled 360 frame dots for the team while
 *   OUT of possession (open play only). Rendered as density surface + centroid +
 *   thirds-spine + covariance ellipse + percentile-depth line. THE MARKERS ARE
 *   STATISTICS OF THE DOT CLOUD — NOT INDIVIDUAL PLAYERS. The two views use
 *   different methods and cannot be directly compared.
 *
 * NOTE ON CAMERA BIAS: 360 frames follow the ball. The visible subset of
 * out-of-possession positions is biased toward areas near the ball. The camera
 * artifact and the real defensive shape point in the same direction and cannot
 * be cleanly separated. Interpret the off-ball view accordingly.
 *
 * All coordinates are StatsBomb-native 120×80 yards, normalised so the team
 * always attacks right (increasing x). The pitch's px() function maps to pixels.
 *
 * @param {Object} pitch - Return value of createPitch(): { svg, g, px, width, height, config }.
 * @param {Object} data  - Team shape JSON contract.
 * @param {Object} data.on_ball  - On-ball shape: { periods: Array }.
 * @param {Object} data.off_ball - Off-ball shape: { density_grid, centroid, thirds_spine, ellipse, depth_line }.
 * @param {Object} data.metadata - Match metadata and caveat strings.
 * @param {Object} [config] - Optional visual configuration.
 * @param {string}  [config.view="on-ball"]      - Initial view: "on-ball" or "off-ball".
 * @param {string}  [config.nodeColor="#1E3A5F"] - Node fill color (on-ball view).
 * @param {string}  [config.accentColor="#9F1239"] - Accent color for off-ball markers.
 * @param {boolean} [config.showLabels=false]    - Show player surname labels on nodes.
 * @param {string}  [config.backgroundColor="#FAF7F0"] - Resolved hex for the off-ball
 *   density surface's zero-value color and node-stroke separators — pass the current
 *   theme's page background so both recolor correctly in light and dark themes.
 * @returns {{ g: d3.Selection, px: function(number,number):[number,number], update: function(string):void, updatePeriod: function(number):void }}
 *   g             — pitch.g (append further overlays here).
 *   px            — pitch.px (sbX, sbY) => [screenX, screenY].
 *   update(view)  — switch to "on-ball" or "off-ball" view.
 *   updatePeriod(idx) — jump to lineup period idx (on-ball view only; clamped to valid range).
 */
export function createTeamShape(pitch: any, data: {
    on_ball: any;
    off_ball: any;
    metadata: any;
}, config?: {
    view?: string;
    nodeColor?: string;
    accentColor?: string;
    showLabels?: boolean;
    backgroundColor?: string;
}): {
    g: d3.Selection<any, any, any, any>;
    px: (arg0: number, arg1: number) => [number, number];
    update: (arg0: string) => void;
    updatePeriod: (arg0: number) => void;
};
import * as d3 from "d3";
