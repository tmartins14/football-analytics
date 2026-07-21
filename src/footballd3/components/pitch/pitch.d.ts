/**
 * Creates a blank pitch.
 *
 * @param {d3.Selection} selection - The D3 selection to render the pitch into.
 * @param {Object}  config - Configuration options for the pitch.
 * @param {string}  [config.mode="full"]          - "full" or "half".
 * @param {string}  [config.orientation="horizontal"] - "horizontal" or "vertical".
 * @param {number}  [config.pxPerYard=8]          - Pixels per StatsBomb yard.
 * @param {number}  [config.padding=24]            - Padding around the pitch in pixels.
 * @param {boolean} [config.showGoals=true]        - Render goal nets.
 * @param {string|Object} [config.theme="whiteboard"] - "whiteboard", "green", or a token object.
 * @param {boolean} [config.flipAttack=false]      - Vertical orientation only. When true, the
 *   attacking direction (high x) maps to the top of the screen and the defending end (low x)
 *   maps to the bottom. Useful for formation diagrams drawn with forwards at the top.
 * @returns {Object} { svg, g, xScale, yScale, px, width, height, config }
 */
export function createPitch(selection: d3.Selection<any, any, any, any>, config?: {
    mode?: string;
    orientation?: string;
    pxPerYard?: number;
    padding?: number;
    showGoals?: boolean;
    theme?: string | any;
    flipAttack?: boolean;
}): any;
import * as d3 from "d3";
