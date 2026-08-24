/**
 * Creates a pass network overlay on an existing pitch.
 *
 * Nodes are placed at each player's average pass-origin position within the
 * active window. Node size encodes pass volume (sqrt scale). In directed mode
 * (default), edges are quadratic Bézier arcs with arrowheads; A→B and B→A bow
 * to opposite sides of the AB line. In undirected mode, both directions are
 * merged into one straight line per pair (count = sum of both directions).
 *
 * All scales are calibrated across ALL windows so sizes remain comparable when
 * animating between substitution windows via update().
 *
 * @param {Object} pitch - Return value of createPitch(): { svg, g, px, ... }.
 * @param {Object} data  - Pass network JSON with windows, substitutions, metadata fields.
 * @param {Object} [config] - Optional visual configuration.
 * @param {number}  [config.window=0]            - Initial substitution window index (0-indexed).
 * @param {boolean} [config.directed=true]        - When true, draws curved arcs with arrowheads.
 *   When false, merges A→B and B→A per pair (count = sum) and draws straight undirected lines.
 * @param {number}  [config.minEdgeCount=3]       - Hide edges with count below this threshold.
 * @param {string}  [config.nodeColor="#1E3A5F"]  - Fill for player nodes.
 * @param {string}  [config.edgeColor="#1E3A5F"]  - Stroke for arcs/lines and arrowheads.
 * @param {string}  [config.labelColor="#FAF7F0"] - Fill for player display_name labels. Pick a
 *   color that contrasts with whatever `labelPosition` places the label against (the node
 *   fill for "onNode", the pitch surface for "below").
 * @param {"onNode"|"below"} [config.labelPosition="onNode"] - Label placement. "onNode"
 *   (default, unchanged): centered on the node — sized for a name shorter than the node
 *   diameter, or a caller-supplied halo/stroke; a name wider than the node will overflow
 *   onto the pitch surface. "below": positioned under the node like formation.js's surname
 *   labels, clear of the node entirely — use this when names are wider than the nodes.
 * @param {[number,number]} [config.nodeRadius=[5,18]] - Node circle radius range in pixels,
 *   scaled by pass volume (sqrt scale).
 * @param {[number,number]} [config.edgeWidth=[0.8,5]] - Edge stroke-width range in pixels,
 *   scaled by pass count (linear scale, clamped).
 * @returns {{ g: d3.Selection, px: Function, update: Function }}
 *   g is pitch.g (append further overlays there). update(idx) transitions to window idx.
 */
export function createPassNetwork(pitch: any, data: any, config?: {
    window?: number;
    directed?: boolean;
    minEdgeCount?: number;
    nodeColor?: string;
    edgeColor?: string;
    labelColor?: string;
    labelPosition?: "onNode" | "below";
    nodeRadius?: [number, number];
    edgeWidth?: [number, number];
}): {
    g: d3.Selection<any, any, any, any>;
    px: Function;
    update: Function;
};
import * as d3 from "d3";
