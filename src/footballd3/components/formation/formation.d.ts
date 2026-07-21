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
 * @param {number}  [config.padding=24]           - Padding around the pitch in pixels.
 * @param {string|Object} [config.theme="whiteboard"] - Pitch theme ("whiteboard", "green", or a token object).
 * @param {string}  [config.nodeColor="#1E3A5F"]   - Player circle fill color.
 * @param {string}  [config.labelColor="#171717"]  - Surname label fill color.
 * @param {string}  [config.backgroundColor="#FAF7F0"] - Stroke color separating player
 *   circles from the pitch surface — pass the current theme's page background so the
 *   separator matches in both light and dark themes.
 * @param {number}  [config.nodeRadius=14]        - Player circle radius in pixels.
 * @returns {{ svg: d3.Selection, g: d3.Selection, px: Function, update: Function }}
 *   svg — the SVG element.
 *   g   — the pitch group; append further overlays here.
 *   px  — pixel conversion fn: (sbX, sbY) => [screenX, screenY].
 *   update(periodIdx) — transition to a different formation period.
 */
export function createFormation(selection: d3.Selection<any, any, any, any>, data: {
    periods: Array<any>;
    metadata: {
        coordinate_note: string;
    };
}, config?: {
    pxPerYard?: number;
    padding?: number;
    theme?: string | any;
    nodeColor?: string;
    labelColor?: string;
    backgroundColor?: string;
    nodeRadius?: number;
}): {
    svg: d3.Selection<any, any, any, any>;
    g: d3.Selection<any, any, any, any>;
    px: Function;
    update: Function;
};
import * as d3 from "d3";
