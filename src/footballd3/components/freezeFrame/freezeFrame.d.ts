/**
 * Creates a 360 freeze-frame overlay on an existing pitch.
 *
 * Renders player positions and the ball for one instant of play. Players are
 * visually distinguished by team side (teammate vs opponent fill), role
 * (keeper = diamond shape), and actor (white fill + team-colour border on the
 * player who performed the action). An optional broadcast field-of-view polygon
 * can be toggled via config.showVisibleArea.
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
 * @param {number}  [config.actorRingWidth=2]         - Stroke-width of the actor circle border (px).
 * @param {number}  [config.markerRadius=6]           - Base player marker radius (px).
 * @param {number}  [config.ballRadius=3]             - Ball marker radius (px).
 * @param {string}  [config.ballColor="#171717"]      - Ball fill colour.
 * @param {string}  [config.ballStroke="none"]        - Ball stroke colour.
 * @returns {{ g: d3.Selection, px: Function, update: Function }}
 *   g is pitch.g (append further overlays there).
 *   update(frameData) transitions the snapshot to new frame data without re-rendering the pitch.
 */
export function createFreezeFrame(pitch: any, data: any, config?: {
    showVisibleArea?: boolean;
    mirrorX?: boolean;
    teamColor?: string;
    opponentColor?: string;
    actorRingWidth?: number;
    markerRadius?: number;
    ballRadius?: number;
    ballColor?: string;
    ballStroke?: string;
}): {
    g: d3.Selection<any, any, any, any>;
    px: Function;
    update: Function;
};
import * as d3 from "d3";
