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
export function createShotMap(selection: d3.Selection<any, any, any, any>, shots: any[], config?: {
    pxPerYard?: number;
    orientation?: string;
    theme?: string | any;
    color?: string;
    styleMode?: "opacity" | "tier";
    shotScale?: number;
    softColor?: string;
    mutedColor?: string;
    onHover?: Function;
    showTooltip?: boolean;
}): any;
import * as d3 from "d3";
