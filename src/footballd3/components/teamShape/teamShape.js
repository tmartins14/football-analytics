// footballd3/components/teamShape/teamShape.js
//
// Renders the empirical team shape on an existing pitch instance.
// Caller creates the pitch with createPitch(), then passes the returned object here.
// No pitch is re-rendered inside this component; all elements land on pitch.g.
//
// Two views, toggled via update():
//   on-ball  — identified, event-based: mean positions per player + convex hull.
//   off-ball — anonymous, frame-based: density surface + centroid + thirds-spine
//              + covariance ellipse + percentile-depth line.
//
// IMPORTANT: the two views use DIFFERENT methods and are NOT the same measurement.
// On-ball positions come from named players' events; off-ball positions come from
// pooled, anonymous 360 frame dots. Do not compare them as equivalent.
//
// Usage:
//   import { createPitch }     from "../pitch/pitch.js";
//   import { createTeamShape } from "../teamShape/teamShape.js";
//   const pitch = createPitch(d3.select("#ts-svg"), { mode: "full" });
//   const { update } = createTeamShape(pitch, data, { view: "on-ball" });
//   update("off-ball");

const SPINE_POINT_R = 4;
const NODE_R        = 7;
const DEPTH_LABEL_OFFSET = 8;

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
 * Bilinearly interpolate a normalized density value at fractional grid position (gx, gy).
 *
 * @param {number[][]} values - 2D array [rows][cols] of density values in [0, 1].
 * @param {number}     cols   - Grid column count.
 * @param {number}     rows   - Grid row count.
 * @param {number}     gx    - Fractional column index (0 … cols-1).
 * @param {number}     gy    - Fractional row index (0 … rows-1).
 * @returns {number} Interpolated density value in [0, 1].
 */
function bilinear(values, cols, rows, gx, gy) {
  const x0 = Math.max(0, Math.min(cols - 2, Math.floor(gx)));
  const y0 = Math.max(0, Math.min(rows - 2, Math.floor(gy)));
  const tx = gx - x0;
  const ty = gy - y0;
  return (
    values[y0    ][x0    ] * (1 - tx) * (1 - ty) +
    values[y0    ][x0 + 1] *      tx  * (1 - ty) +
    values[y0 + 1][x0    ] * (1 - tx) *      ty  +
    values[y0 + 1][x0 + 1] *      tx  *      ty
  );
}

/**
 * Parse a CSS hex color string into [r, g, b] components (0–255).
 *
 * @param {string} hex - Hex color string, e.g. "#9F1239" or "#FAF7F0".
 * @returns {[number, number, number]} [r, g, b] each in 0–255.
 */
function hexToRgb(hex) {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

/**
 * Render the off-ball density surface as a bilinearly-interpolated canvas image.
 *
 * Paints the grid to an off-screen canvas using bilinear interpolation between
 * cell centres, then embeds the result as an SVG <image>. This duplicates the
 * smooth-render approach from heatmap.js — kept inline to avoid coupling these
 * two independent components.
 *
 * @param {d3.Selection} g          - Pitch group from createPitch().
 * @param {Object}       grid       - Density grid: { cols, rows, values }.
 * @param {Function}     px         - Pixel conversion: (sbX, sbY) => [screenX, screenY].
 * @param {number}       padding    - Pitch padding from createPitch().config.
 * @param {number}       pxPerYard  - Pixels per StatsBomb yard.
 * @param {string}       colorLow   - CSS hex color at zero density.
 * @param {string}       colorHigh  - CSS hex color at peak density.
 * @param {number}       maxOpacity - Opacity multiplier at peak density (0–1).
 * @returns {d3.Selection} The appended <image> element (class "ts-density").
 */
function renderDensity(g, grid, px, padding, pxPerYard, colorLow, colorHigh, maxOpacity) {
  const { cols, rows, values } = grid;
  const [rLow,  gLow,  bLow ] = hexToRgb(colorLow);
  const [rHigh, gHigh, bHigh] = hexToRgb(colorHigh);

  // Canvas covers the full pitch inner area (no padding).
  const pitchW = 120 * pxPerYard;
  const pitchH = 80  * pxPerYard;

  const canvas  = document.createElement("canvas");
  canvas.width  = pitchW;
  canvas.height = pitchH;
  const ctx     = canvas.getContext("2d");
  const imgData = ctx.createImageData(pitchW, pitchH);
  const buf     = imgData.data;

  for (let py = 0; py < pitchH; py++) {
    for (let px2 = 0; px2 < pitchW; px2++) {
      // Map pixel position to fractional grid index.
      const gx = (px2 / pitchW) * (cols - 1);
      const gy = (py / pitchH) * (rows - 1);
      const t  = bilinear(values, cols, rows, gx, gy);

      const alpha = Math.round(t * maxOpacity * 255);
      const r = Math.round(rLow + (rHigh - rLow) * t);
      const gc = Math.round(gLow + (gHigh - gLow) * t);
      const b = Math.round(bLow + (bHigh - bLow) * t);

      const idx = (py * pitchW + px2) * 4;
      buf[idx    ] = r;
      buf[idx + 1] = gc;
      buf[idx + 2] = b;
      buf[idx + 3] = alpha;
    }
  }

  ctx.putImageData(imgData, 0, 0);

  // Insert after the two background rects (children 1 and 2) but before pitch
  // markings (child 3 onward), so the density surface sits under the lines.
  return g.insert("image", ":nth-child(3)")
    .attr("class", "ts-density")
    .attr("x", padding)
    .attr("y", padding)
    .attr("width",  pitchW)
    .attr("height", pitchH)
    .attr("href", canvas.toDataURL());
}

/**
 * Draw the on-ball view for a single lineup period: player mean-position nodes
 * and their convex hull.
 *
 * Nodes are placed at mean event positions (normalised coordinates, team attacks
 * right). Hull is drawn as a low-opacity filled polygon. No player labels by
 * default; enable via config.showLabels. All elements share class "ts-on-ball"
 * for bulk removal when switching views or periods.
 *
 * @param {d3.Selection} g          - Pitch group.
 * @param {Function}     px         - (sbX, sbY) => [screenX, screenY].
 * @param {Object}       period     - One entry from data.on_ball.periods:
 *                                    { nodes, hull, from_minute, to_minute, ... }.
 * @param {string}       nodeColor  - Fill color for player circles.
 * @param {boolean}      showLabels - Render player surname labels if true.
 */
function drawOnBall(g, px, period, nodeColor, showLabels) {
  if (!period || !period.nodes || period.nodes.length === 0) return;

  // Convex hull polygon.
  if (period.hull && period.hull.length >= 3) {
    const hullPoints = period.hull.map(([hx, hy]) => px(hx, hy).join(",")).join(" ");
    g.append("polygon")
      .attr("class", "ts-on-ball")
      .attr("points", hullPoints)
      .attr("fill", nodeColor)
      .attr("fill-opacity", 0.08)
      .attr("stroke", nodeColor)
      .attr("stroke-opacity", 0.4)
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "4,3");
  }

  // Player nodes.
  period.nodes.forEach(node => {
    const [cx, cy] = px(node.x, node.y);
    const grp = g.append("g")
      .attr("class", "ts-on-ball")
      .style("cursor", "pointer");

    grp.append("circle")
      .attr("cx", cx).attr("cy", cy)
      .attr("r", NODE_R)
      .attr("fill", nodeColor)
      .attr("fill-opacity", 0.85)
      .attr("stroke", "#FAF7F0")
      .attr("stroke-width", 1.2);

    if (showLabels) {
      grp.append("text")
        .attr("x", cx).attr("y", cy + NODE_R + 9)
        .attr("text-anchor", "middle")
        .attr("font-family", "Geist, sans-serif")
        .attr("font-size", "8px")
        .attr("fill", "#171717")
        .attr("pointer-events", "none")
        .text(node.display_name);
    }

    grp
      .on("mouseover", () => {
        _tooltip.innerHTML =
          `<span style="font-weight:600">${node.display_name}</span><br>` +
          `<span style="color:#525252">${node.event_count} on-ball events</span>`;
        _tooltip.style.display = "block";
      })
      .on("mousemove", event => {
        _tooltip.style.left = (event.clientX + 14) + "px";
        _tooltip.style.top  = (event.clientY - 28) + "px";
      })
      .on("mouseout", () => { _tooltip.style.display = "none"; });
  });
}

/**
 * Draw the off-ball view: density surface, centroid, thirds-spine, ellipse, depth line.
 *
 * All markers are statistics of the anonymous cloud of out-of-possession 360 frame
 * dots — they do NOT represent individual players. The density surface is rendered
 * before pitch markings so lines remain visible on top. All elements share class
 * "ts-off-ball" for bulk removal when switching views.
 *
 * @param {d3.Selection} g          - Pitch group.
 * @param {Function}     px         - (sbX, sbY) => [screenX, screenY].
 * @param {Object}       offBall    - data.off_ball: { density_grid, centroid, thirds_spine, ellipse, depth_line }.
 * @param {number}       pxPerYard  - Pixels per StatsBomb yard (from pitch config).
 * @param {number}       padding    - Pitch padding in pixels (from pitch config).
 * @param {string}       accentColor - Fill/stroke color for markers.
 */
function drawOffBall(g, px, offBall, pxPerYard, padding, accentColor) {
  // Density surface (inserted before existing pitch markings).
  renderDensity(
    g,
    offBall.density_grid,
    px,
    padding,
    pxPerYard,
    "#FAF7F0",
    accentColor,
    0.75,
  );

  // Covariance ellipse — statistics of the cloud, not an individual player shape.
  const [ecx, ecy] = px(offBall.ellipse.cx, offBall.ellipse.cy);
  g.append("ellipse")
    .attr("class", "ts-off-ball")
    .attr("cx", ecx).attr("cy", ecy)
    .attr("rx", offBall.ellipse.rx * pxPerYard)
    .attr("ry", offBall.ellipse.ry * pxPerYard)
    .attr("transform", `rotate(${offBall.ellipse.angle_deg}, ${ecx}, ${ecy})`)
    .attr("fill", "none")
    .attr("stroke", accentColor)
    .attr("stroke-width", 1.5)
    .attr("stroke-dasharray", "5,3")
    .attr("stroke-opacity", 0.7);

  // Thirds-spine: connect centroid of each pitch third.
  const spinePoints = offBall.thirds_spine.map(s => px(s.x, s.y));
  for (let i = 0; i < spinePoints.length - 1; i++) {
    g.append("line")
      .attr("class", "ts-off-ball")
      .attr("x1", spinePoints[i][0]).attr("y1", spinePoints[i][1])
      .attr("x2", spinePoints[i + 1][0]).attr("y2", spinePoints[i + 1][1])
      .attr("stroke", accentColor)
      .attr("stroke-width", 2)
      .attr("stroke-opacity", 0.6);
  }
  offBall.thirds_spine.forEach(s => {
    const [sx, sy] = px(s.x, s.y);
    g.append("circle")
      .attr("class", "ts-off-ball")
      .attr("cx", sx).attr("cy", sy)
      .attr("r", SPINE_POINT_R)
      .attr("fill", accentColor)
      .attr("fill-opacity", 0.8)
      .attr("stroke", "#FAF7F0")
      .attr("stroke-width", 1)
      .on("mouseover", () => {
        _tooltip.innerHTML =
          `<span style="font-weight:600">${s.third} third</span><br>` +
          `<span style="color:#525252">cloud centre of mass</span>`;
        _tooltip.style.display = "block";
      })
      .on("mousemove", event => {
        _tooltip.style.left = (event.clientX + 14) + "px";
        _tooltip.style.top  = (event.clientY - 28) + "px";
      })
      .on("mouseout", () => { _tooltip.style.display = "none"; });
  });

  // Centroid marker — mean position of all pooled dots.
  const [ccx, ccy] = px(offBall.centroid.x, offBall.centroid.y);
  g.append("circle")
    .attr("class", "ts-off-ball")
    .attr("cx", ccx).attr("cy", ccy)
    .attr("r", 5)
    .attr("fill", accentColor)
    .attr("stroke", "#FAF7F0")
    .attr("stroke-width", 2)
    .on("mouseover", () => {
      _tooltip.innerHTML =
        `<span style="font-weight:600">off-ball centroid</span><br>` +
        `<span style="color:#525252">mean out-of-possession position<br>of the cloud (not a player)</span>`;
      _tooltip.style.display = "block";
    })
    .on("mousemove", event => {
      _tooltip.style.left = (event.clientX + 14) + "px";
      _tooltip.style.top  = (event.clientY - 28) + "px";
    })
    .on("mouseout", () => { _tooltip.style.display = "none"; });

  // Percentile depth line — how deep the team sits out of possession.
  const [dlx] = px(offBall.depth_line.x, 40);
  const [, top]    = px(offBall.depth_line.x, 0);
  const [, bottom] = px(offBall.depth_line.x, 80);
  g.append("line")
    .attr("class", "ts-off-ball")
    .attr("x1", dlx).attr("y1", top)
    .attr("x2", dlx).attr("y2", bottom)
    .attr("stroke", accentColor)
    .attr("stroke-width", 1.5)
    .attr("stroke-dasharray", "6,4")
    .attr("stroke-opacity", 0.85);
  g.append("text")
    .attr("class", "ts-off-ball")
    .attr("x", dlx + DEPTH_LABEL_OFFSET)
    .attr("y", top + 14)
    .attr("font-family", "Geist Mono, monospace")
    .attr("font-size", "9px")
    .attr("fill", accentColor)
    .attr("fill-opacity", 0.9)
    .text(`p${offBall.depth_line.percentile}`);
}

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
 * @returns {{ g: d3.Selection, px: Function, update: Function, updatePeriod: Function }}
 *   g             — pitch.g (append further overlays here).
 *   px            — pitch.px (sbX, sbY) => [screenX, screenY].
 *   update(view)  — switch to "on-ball" or "off-ball" view.
 *   updatePeriod(idx) — jump to lineup period idx (on-ball view only; clamped to valid range).
 */
export function createTeamShape(pitch, data, config = {}) {
  const {
    view        = "on-ball",
    nodeColor   = "#1E3A5F",
    accentColor = "#9F1239",
    showLabels  = false,
  } = config;

  const { g, px } = pitch;
  const pxPerYard = pitch.config.pxPerYard;
  const padding   = pitch.config.padding;

  let _currentView      = null;
  let _currentPeriodIdx = 0;

  /**
   * Switch the displayed view to "on-ball" or "off-ball".
   *
   * Removes all current view elements and redraws the requested view.
   * On-ball renders the period at the current _currentPeriodIdx.
   * No pitch re-render occurs; only overlay elements change.
   *
   * @param {string} newView - "on-ball" or "off-ball".
   */
  function update(newView) {
    if (newView === _currentView) return;
    _currentView = newView;

    g.selectAll(".ts-on-ball, .ts-off-ball, .ts-density").remove();

    if (newView === "on-ball") {
      drawOnBall(g, px, data.on_ball.periods[_currentPeriodIdx], nodeColor, showLabels);
    } else {
      drawOffBall(g, px, data.off_ball, pxPerYard, padding, accentColor);
    }
  }

  /**
   * Change the active lineup period in the on-ball view.
   *
   * If the current view is "on-ball", clears and redraws immediately. If the
   * current view is "off-ball", stores the index for when on-ball is next shown.
   *
   * @param {number} idx - Zero-based period index; clamped to [0, periods.length - 1].
   */
  function updatePeriod(idx) {
    const max = data.on_ball.periods.length - 1;
    _currentPeriodIdx = Math.max(0, Math.min(max, idx));
    if (_currentView === "on-ball") {
      g.selectAll(".ts-on-ball").remove();
      drawOnBall(g, px, data.on_ball.periods[_currentPeriodIdx], nodeColor, showLabels);
    }
  }

  update(view);

  return { g, px, update, updatePeriod };
}
