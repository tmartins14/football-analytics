// ============================================================
// footballd3/pitch.js
//
// StatsBomb coordinate space: 120 wide × 80 tall, origin top-left.
// Renders a pitch into a D3 selection. Returns an object with the
// scales and px() helper that downstream components use to place
// elements in StatsBomb coordinates.
//
// Usage:
//   import { createPitch } from "./pitch.js";
//   const { g, px } = createPitch(d3.select("svg"), { mode: "full" });
//   g.append("circle").attr("cx", px(60, 40)[0]).attr("cy", px(60, 40)[1]).attr("r", 5);
// ============================================================

// Themes — canonical color sets for the pitch surface.
// "whiteboard" is the signature default. Use "green" sparingly,
// only when the brief specifically calls for a broadcast-style look.
// Custom themes can be passed inline via the `theme` config (see below).
const THEMES = {
  whiteboard: {
    background: "#FAF7F0",
    lines:      "#1E4D2B",
    lineWeight: 1.2,
  },
  green: {
    background: "#1E4D2B",
    lines:      "#FAF7F0",
    lineWeight: 1.4,
  },
};

const SB = {
  pitchWidth:    120,
  pitchHeight:   80,
  penAreaLength: 18,
  penAreaWidth:  44,
  sixYardLength: 6,
  sixYardWidth:  20,
  centerCircleR: 10,
  penSpotDist:   12,
  cornerArcR:    1,
  goalWidth:     8,
  goalDepth:     1.5,
};

/**
 * Creates a blank pitch.
 *
 * @param {d3.Selection} selection - The D3 selection to render the pitch into.
 * @param {Object} config - Configuration options for the pitch.
 * @returns {Object} An object containing the pitch group and a pixel conversion function.
 */
export function createPitch(selection, config = {}) {
  const {
    mode        = "full",
    orientation = "horizontal",
    pxPerYard   = 8,
    padding     = 24,
    showGoals   = true,
    theme       = "whiteboard",
  } = config;

  // Resolve theme: string key looks up THEMES, object passes through
  const tokens = typeof theme === "string" ? THEMES[theme] : theme;
  if (!tokens) {
    throw new Error(`createPitch: unknown theme "${theme}". Use "whiteboard", "green", or pass a token object.`);
  }

  const sbW = mode === "full" ? SB.pitchWidth : SB.pitchWidth / 2;
  const sbH = SB.pitchHeight;

  // Inner dimensions derived from pxPerYard so pitch elements stay the same
  // visual size regardless of mode/orientation. Canvas size flexes instead.
  const innerSbW = orientation === "horizontal" ? sbW : sbH;
  const innerSbH = orientation === "horizontal" ? sbH : sbW;
  const innerW = innerSbW * pxPerYard;
  const innerH = innerSbH * pxPerYard;
  const width  = innerW + padding * 2;
  const height = innerH + padding * 2;

  const xDomain = orientation === "horizontal" ? [0, sbW] : [0, sbH];
  const yDomain = orientation === "horizontal" ? [0, sbH] : [0, sbW];

  const xScale = d3.scaleLinear().domain(xDomain).range([padding, padding + innerW]);
  const yScale = d3.scaleLinear().domain(yDomain).range([padding, padding + innerH]);

  const px = (sbX, sbY) => orientation === "horizontal"
    ? [xScale(sbX), yScale(sbY)]
    : [xScale(sbY), yScale(sbX)];

  const svg = selection
    .attr("width",  width)
    .attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`);

  svg.selectAll("*").remove();

  const g = svg.append("g").attr("class", "pitch");

  // Canvas
  g.append("rect")
    .attr("x", 0).attr("y", 0)
    .attr("width", width).attr("height", height)
    .attr("fill", tokens.background);

  // Pitch surface
  const [bx, by] = px(0, 0);
  const [ex, ey] = px(sbW, sbH);
  g.append("rect")
    .attr("x", Math.min(bx, ex)).attr("y", Math.min(by, ey))
    .attr("width",  Math.abs(ex - bx))
    .attr("height", Math.abs(ey - by))
    .attr("fill", tokens.background)
    .attr("stroke", tokens.lines)
    .attr("stroke-width", tokens.lineWeight);

  const line = (x1, y1, x2, y2) => {
    const [ax, ay] = px(x1, y1);
    const [bxl, byl] = px(x2, y2);
    g.append("line")
      .attr("x1", ax).attr("y1", ay)
      .attr("x2", bxl).attr("y2", byl)
      .attr("stroke", tokens.lines)
      .attr("stroke-width", tokens.lineWeight);
  };

  const rect = (x, y, w, h) => {
    const [rx, ry]   = px(x, y);
    const [rx2, ry2] = px(x + w, y + h);
    g.append("rect")
      .attr("x", Math.min(rx, rx2)).attr("y", Math.min(ry, ry2))
      .attr("width",  Math.abs(rx2 - rx))
      .attr("height", Math.abs(ry2 - ry))
      .attr("fill", "none")
      .attr("stroke", tokens.lines)
      .attr("stroke-width", tokens.lineWeight);
  };

  // Halfway line
  if (mode === "full") line(60, 0, 60, 80);

  // Penalty areas
  const paY = (80 - SB.penAreaWidth) / 2;
  rect(0, paY, SB.penAreaLength, SB.penAreaWidth);
  if (mode === "full") rect(120 - SB.penAreaLength, paY, SB.penAreaLength, SB.penAreaWidth);

  // Six-yard boxes
  const syY = (80 - SB.sixYardWidth) / 2;
  rect(0, syY, SB.sixYardLength, SB.sixYardWidth);
  if (mode === "full") rect(120 - SB.sixYardLength, syY, SB.sixYardLength, SB.sixYardWidth);

  // Centre circle + spot
  {
    const [cx, cy] = px(60, 40);
    const rPx = Math.abs(xScale(SB.centerCircleR) - xScale(0));
    if (mode === "full") {
      g.append("circle")
        .attr("cx", cx).attr("cy", cy).attr("r", rPx)
        .attr("fill", "none")
        .attr("stroke", tokens.lines)
        .attr("stroke-width", tokens.lineWeight);
    } else {
      // Half pitch: center sits on the boundary; draw only the inward-facing semicircle.
      // Horizontal → left semicircle (π–2π); vertical → top semicircle (-π/2–π/2).
      const [startAngle, endAngle] = orientation === "horizontal"
        ? [Math.PI, 2 * Math.PI]
        : [-Math.PI / 2, Math.PI / 2];
      const t = tokens.lineWeight / 2;
      const arc = d3.arc()
        .innerRadius(rPx - t).outerRadius(rPx + t)
        .startAngle(startAngle).endAngle(endAngle);
      g.append("path")
        .attr("d", arc())
        .attr("transform", `translate(${cx}, ${cy})`)
        .attr("fill", tokens.lines);
    }
    g.append("circle")
      .attr("cx", cx).attr("cy", cy).attr("r", 2)
      .attr("fill", tokens.lines);
  }

  // Penalty arcs + spots.
  // The arc is the portion of a circle (radius = centerCircleR) around the
  // penalty spot that lies OUTSIDE the penalty area.
  const distToBoundary = SB.penAreaLength - SB.penSpotDist;          // 6 yd
  const halfChord = Math.sqrt(SB.centerCircleR ** 2 - distToBoundary ** 2);  // 8 yd
  const halfAngle = (Math.atan2(halfChord, distToBoundary) * 180) / Math.PI; // ~53.13°
  const arcThickness = tokens.lineWeight / 2;

  const drawArc = (spotX) => {
    const [scx, scy] = px(spotX, 40);
    const rPx = Math.abs(xScale(SB.centerCircleR) - xScale(0));

    // d3.arc: 0° = up, clockwise. Horizontal: left arc bulges right (90°),
    // right arc bulges left (270°). Vertical orientation rotates by +90°.
    let centerA = spotX < 60 ? 90 : 270;
    if (orientation === "vertical") centerA += 90;

    const arc = d3.arc()
      .innerRadius(rPx - arcThickness).outerRadius(rPx + arcThickness)
      .startAngle(((centerA - halfAngle) * Math.PI) / 180)
      .endAngle(((centerA + halfAngle) * Math.PI) / 180);
    g.append("path")
      .attr("d", arc())
      .attr("transform", `translate(${scx}, ${scy})`)
      .attr("fill", tokens.lines);
    g.append("circle")
      .attr("cx", scx).attr("cy", scy).attr("r", 2)
      .attr("fill", tokens.lines);
  };
  drawArc(SB.penSpotDist);
  if (mode === "full") drawArc(120 - SB.penSpotDist);

  // Corner arcs — each occupies the 90° quadrant facing INTO the pitch.
  // Compute that direction from screen-space geometry so the math is
  // orientation-agnostic.
  const cornerPts = mode === "full"
    ? [[0, 0], [0, 80], [120, 0], [120, 80]]
    : [[0, 0], [0, 80]];
  const [centerScreenX, centerScreenY] = px(60, 40);
  cornerPts.forEach(([cx, cy]) => {
    const [pcx, pcy] = px(cx, cy);
    const rPx = Math.abs(xScale(SB.cornerArcR) - xScale(0));
    const dx = centerScreenX - pcx;
    const dy = centerScreenY - pcy;

    // d3.arc: 0=up, 90=right, 180=down, 270=left.
    let startA;
    if (dx > 0 && dy > 0) startA = 90;        // pitch is down-right
    else if (dx < 0 && dy > 0) startA = 180;  // pitch is down-left
    else if (dx < 0 && dy < 0) startA = 270;  // pitch is up-left
    else startA = 0;                          // pitch is up-right

    const arc = d3.arc()
      .innerRadius(rPx - arcThickness).outerRadius(rPx + arcThickness)
      .startAngle((startA * Math.PI) / 180)
      .endAngle(((startA + 90) * Math.PI) / 180);
    g.append("path")
      .attr("d", arc())
      .attr("transform", `translate(${pcx}, ${pcy})`)
      .attr("fill", tokens.lines);
  });

  // Goals
  if (showGoals) {
    const gHalfW = SB.goalWidth / 2;
    const drawGoal = (x, dir) => {
      const [gx, gy1] = px(x, 40 - gHalfW);
      const [,  gy2]  = px(x, 40 + gHalfW);
      if (orientation === "horizontal") {
        const depthPx = Math.abs(xScale(SB.goalDepth) - xScale(0)) * dir;
        g.append("rect")
          .attr("x", Math.min(gx, gx - depthPx))
          .attr("y", Math.min(gy1, gy2))
          .attr("width",  Math.abs(depthPx))
          .attr("height", Math.abs(gy2 - gy1))
          .attr("fill", "none")
          .attr("stroke", tokens.lines)
          .attr("stroke-width", tokens.lineWeight);
      } else {
        const depthPx = Math.abs(yScale(SB.goalDepth) - yScale(0)) * (x === 0 ? -1 : 1);
        g.append("rect")
          .attr("x", Math.min(gy1, gy2))
          .attr("y", Math.min(gx, gx + depthPx))
          .attr("width",  Math.abs(gy2 - gy1))
          .attr("height", Math.abs(depthPx))
          .attr("fill", "none")
          .attr("stroke", tokens.lines)
          .attr("stroke-width", tokens.lineWeight);
      }
    };
    drawGoal(0, -1);
    if (mode === "full") drawGoal(120, 1);
  }

  return { svg, g, xScale, yScale, px, width, height, config: { mode, orientation, padding, pxPerYard } };
}