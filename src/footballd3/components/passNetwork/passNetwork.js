// footballd3/components/passNetwork/passNetwork.js
//
// Renders an avg-position pass network as a layer on an existing pitch instance.
// Caller creates the pitch with createPitch(), then passes the returned object here.
// No pitch is re-rendered inside this component; all elements land on pitch.g.
//
// Usage:
//   import { createPitch } from "../pitch/pitch.js";
//   import { createPassNetwork } from "../passNetwork/passNetwork.js";
//   const pitch = createPitch(d3.select("#svg"), { mode: "full" });
//   const { update } = createPassNetwork(pitch, data, { window: 0 });
//   update(1);   // animate to substitution window 1

// Perpendicular offset for directed arc pairs (px). A→B curves one way,
// B→A curves the other; this constant controls how much they bow apart.
const CURVE_OFFSET = 14;

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

/**
 * Compute a quadratic Bézier path string and control point for a directed edge.
 *
 * Uses the left-perpendicular of the from→to direction for the control point,
 * so A→B and B→A automatically bow to opposite sides of the AB line — no
 * direction flag needed.
 *
 * @param {number} ax - From-node screen x.
 * @param {number} ay - From-node screen y.
 * @param {number} bx - To-node screen x.
 * @param {number} by - To-node screen y.
 * @returns {{ cpx: number, cpy: number, pathD: string }}
 */
function arcPath(ax, ay, bx, by) {
  const mx  = (ax + bx) / 2;
  const my  = (ay + by) / 2;
  const dx  = bx - ax;
  const dy  = by - ay;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const cpx = mx + (-dy / len) * CURVE_OFFSET;
  const cpy = my + (dx  / len) * CURVE_OFFSET;
  return { cpx, cpy, pathD: `M ${ax} ${ay} Q ${cpx} ${cpy} ${bx} ${by}` };
}

/**
 * Move a Bézier endpoint back along its terminal tangent by r pixels.
 *
 * This clips the drawn path to the boundary of the to-node circle so
 * the arrowhead lands at the edge of the circle rather than the centre.
 *
 * @param {number} bx  - To-node centre x.
 * @param {number} by  - To-node centre y.
 * @param {number} cpx - Bézier control point x.
 * @param {number} cpy - Bézier control point y.
 * @param {number} r   - To-node radius in pixels.
 * @returns {[number, number]} Adjusted endpoint [x, y].
 */
function clipEndpoint(bx, by, cpx, cpy, r) {
  const tx  = bx - cpx;
  const ty  = by - cpy;
  const len = Math.sqrt(tx * tx + ty * ty) || 1;
  return [bx - (tx / len) * r, by - (ty / len) * r];
}

/**
 * Move a Bézier start point forward along its initial tangent by r pixels.
 *
 * Clips the drawn path to the boundary of the from-node circle.
 *
 * @param {number} ax  - From-node centre x.
 * @param {number} ay  - From-node centre y.
 * @param {number} cpx - Bézier control point x.
 * @param {number} cpy - Bézier control point y.
 * @param {number} r   - From-node radius in pixels.
 * @returns {[number, number]} Adjusted start point [x, y].
 */
function clipStartpoint(ax, ay, cpx, cpy, r) {
  const tx  = cpx - ax;
  const ty  = cpy - ay;
  const len = Math.sqrt(tx * tx + ty * ty) || 1;
  return [ax + (tx / len) * r, ay + (ty / len) * r];
}

/**
 * Extract the last name token from a StatsBomb full player name.
 *
 * StatsBomb names can be very long ("Lamine Yamal Nasraoui Ebana"); the last
 * token is the most recognisable identifier in a pitch context.
 *
 * @param {string} fullName - Full player name string.
 * @returns {string} Last whitespace-delimited token.
 */
function lastName(fullName) {
  const parts = fullName.trim().split(/\s+/);
  return parts[parts.length - 1];
}

/**
 * Creates a pass network overlay on an existing pitch.
 *
 * Nodes are placed at each player's average pass-origin position within the
 * active window. Node size encodes pass volume (sqrt scale). Directed edges are
 * quadratic Bézier arcs; A→B and B→A bow to opposite sides of the AB line.
 * Edge width encodes pass count in that direction.
 *
 * All scales are calibrated across ALL windows so sizes remain comparable when
 * animating between substitution windows via update().
 *
 * @param {Object} pitch - Return value of createPitch(): { svg, g, px, ... }.
 * @param {Object} data  - Pass network JSON with windows, substitutions, metadata fields.
 * @param {Object} [config] - Optional visual configuration.
 * @param {number} [config.window=0]          - Initial substitution window index (0-indexed).
 * @param {number} [config.minEdgeCount=3]    - Hide directed edges with count below this threshold.
 * @param {string} [config.nodeColor="#1E3A5F"] - Fill for player nodes.
 * @param {string} [config.edgeColor="#1E3A5F"] - Stroke for directed arcs and arrowheads.
 * @param {string} [config.labelColor="#FAF7F0"] - Fill for player last-name labels inside nodes.
 * @returns {{ g: d3.Selection, px: Function, update: Function }}
 *   g is pitch.g (append further overlays there). update(idx) transitions to window idx.
 */
export function createPassNetwork(pitch, data, config = {}) {
  const {
    window: initialWindow = 0,
    minEdgeCount = 3,
    nodeColor    = "#1E3A5F",
    edgeColor    = "#1E3A5F",
    labelColor   = "#FAF7F0",
  } = config;

  const { svg, g, px } = pitch;

  // Inject SVG arrowhead marker into <defs>; safe to call multiple times.
  const markerId = "pn-arrow";
  let defs = svg.select("defs");
  if (defs.empty()) defs = svg.insert("defs", ":first-child");
  if (defs.select(`#${markerId}`).empty()) {
    defs.append("marker")
      .attr("id", markerId)
      .attr("markerWidth", 5)
      .attr("markerHeight", 5)
      .attr("refX", 4.5)
      .attr("refY", 2.5)
      .attr("orient", "auto")
      .append("path")
        .attr("d", "M 0 0 L 0 5 L 5 2.5 z")
        .attr("fill", edgeColor);
  }

  // Global pass/count ranges so visual weight is consistent across all windows.
  const allPasses = data.windows.flatMap(w => w.nodes.map(n => n.passes));
  const allCounts = data.windows.flatMap(w => w.edges.map(e => e.count));
  const globalMaxPasses = d3.max(allPasses) || 1;
  const globalMaxCount  = d3.max(allCounts)  || 1;

  const rScale = d3.scaleSqrt()
    .domain([0, globalMaxPasses])
    .range([5, 18]);

  const wScale = d3.scaleLinear()
    .domain([0, globalMaxCount])
    .range([0.8, 5])
    .clamp(true);

  // Layering: edges first so nodes render on top, then labels topmost.
  const edgesG  = g.append("g").attr("class", "pn-edges");
  const nodesG  = g.append("g").attr("class", "pn-nodes");
  const labelsG = g.append("g").attr("class", "pn-labels");

  function renderWindow(idx, animate) {
    const win = data.windows[idx];
    if (!win) return;

    const posMap = new Map(win.nodes.map(n => [n.player, n]));
    const dur    = animate ? 400 : 0;

    // ── Edges ────────────────────────────────────────────────────────────────
    const visibleEdges = win.edges.filter(
      e => e.count >= minEdgeCount && posMap.has(e.from) && posMap.has(e.to)
    );

    const edgeSel = edgesG.selectAll(".pn-edge")
      .data(visibleEdges, d => `${d.from}→${d.to}`);

    edgeSel.exit()
      .transition().duration(dur)
      .style("opacity", 0)
      .remove();

    const edgeEnter = edgeSel.enter().append("path")
      .attr("class", "pn-edge")
      .attr("fill", "none")
      .attr("stroke", edgeColor)
      .attr("marker-end", `url(#${markerId})`)
      .style("opacity", 0);

    edgeEnter.merge(edgeSel)
      .on("mouseover", (event, d) => {
        _tooltip.innerHTML =
          `<span style="font-weight:600">${d.from}</span> → ${d.to}<br>` +
          `<span style="color:#525252">${d.count} passes</span>`;
        _tooltip.style.display = "block";
      })
      .on("mousemove", event => {
        _tooltip.style.left = (event.clientX + 14) + "px";
        _tooltip.style.top  = (event.clientY - 28) + "px";
      })
      .on("mouseout", () => { _tooltip.style.display = "none"; })
      .transition().duration(dur)
      .style("opacity", d => 0.2 + 0.65 * (d.count / globalMaxCount))
      .attr("stroke-width", d => wScale(d.count))
      .attr("d", d => {
        const from = posMap.get(d.from);
        const to   = posMap.get(d.to);
        const [ax, ay] = px(from.x, from.y);
        const [bx, by] = px(to.x,   to.y);
        const { cpx, cpy } = arcPath(ax, ay, bx, by);
        const fromR = rScale(from.passes);
        const toR   = rScale(to.passes);
        const [sx, sy] = clipStartpoint(ax, ay, cpx, cpy, fromR);
        const [ex, ey] = clipEndpoint(bx, by, cpx, cpy, toR);
        return `M ${sx} ${sy} Q ${cpx} ${cpy} ${ex} ${ey}`;
      });

    // ── Nodes ────────────────────────────────────────────────────────────────
    const nodeSel = nodesG.selectAll(".pn-node")
      .data(win.nodes, d => d.player);

    nodeSel.exit()
      .transition().duration(dur)
      .style("opacity", 0)
      .remove();

    const nodeEnter = nodeSel.enter().append("circle")
      .attr("class", "pn-node")
      .attr("fill", nodeColor)
      .attr("stroke", "#FAF7F0")
      .attr("stroke-width", 2)
      .style("opacity", 0)
      .style("cursor", "pointer")
      .attr("cx", d => px(d.x, d.y)[0])
      .attr("cy", d => px(d.x, d.y)[1])
      .attr("r",  d => rScale(d.passes));

    nodeEnter.merge(nodeSel)
      .on("mouseover", (event, d) => {
        _tooltip.innerHTML =
          `<span style="font-weight:600">${d.player}</span><br>` +
          `<span style="color:#525252">${d.passes} passes</span>`;
        _tooltip.style.display = "block";
      })
      .on("mousemove", event => {
        _tooltip.style.left = (event.clientX + 14) + "px";
        _tooltip.style.top  = (event.clientY - 28) + "px";
      })
      .on("mouseout", () => { _tooltip.style.display = "none"; })
      .transition().duration(dur)
      .style("opacity", 1)
      .attr("r",  d => rScale(d.passes))
      .attr("cx", d => px(d.x, d.y)[0])
      .attr("cy", d => px(d.x, d.y)[1]);

    // ── Labels ───────────────────────────────────────────────────────────────
    const labelSel = labelsG.selectAll(".pn-label")
      .data(win.nodes, d => d.player);

    labelSel.exit()
      .transition().duration(dur)
      .style("opacity", 0)
      .remove();

    const labelEnter = labelSel.enter().append("text")
      .attr("class", "pn-label")
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr("font-family", "Geist Mono, monospace")
      .attr("font-size", 9)
      .attr("font-weight", 600)
      .attr("fill", labelColor)
      .attr("pointer-events", "none")
      .style("opacity", 0)
      .attr("x", d => px(d.x, d.y)[0])
      .attr("y", d => px(d.x, d.y)[1])
      .text(d => lastName(d.player));

    labelEnter.merge(labelSel)
      .transition().duration(dur)
      .style("opacity", 1)
      .attr("x", d => px(d.x, d.y)[0])
      .attr("y", d => px(d.x, d.y)[1]);
  }

  renderWindow(initialWindow, false);

  /**
   * Animate the pass network to a different substitution window.
   *
   * Nodes slide to their new average positions, radii rescale to new pass
   * volumes, and edges transition to new widths and curves. Players who enter
   * or leave the active lineup fade in or out.
   *
   * @param {number} idx - Window index to transition to (0-indexed, matches data.windows[].index).
   */
  function update(idx) {
    renderWindow(idx, true);
  }

  return { g, px, update };
}
