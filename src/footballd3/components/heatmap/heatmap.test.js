import { describe, expect, it } from "vitest";
import * as d3 from "d3";

import { createPitch } from "../pitch/pitch.js";
import { createHeatmap, invertPx } from "./heatmap.js";

function makeGrid(cols, rows, hotCol, hotRow) {
  const values = Array.from({ length: rows }, (_, r) =>
    Array.from({ length: cols }, (_, c) => (r === hotRow && c === hotCol ? 1.0 : 0.0))
  );
  return { grid: { cols, rows, values }, metadata: {} };
}

describe("invertPx", () => {
  it("round-trips through px() for horizontal orientation (identity mapping)", () => {
    document.body.innerHTML = '<svg id="test-svg"></svg>';
    const pitch = createPitch(d3.select("#test-svg"), { mode: "full", orientation: "horizontal", pxPerYard: 4 });
    const [screenX, screenY] = pitch.px(90, 10); // top-right-ish, StatsBomb space
    const [sbX, sbY] = invertPx(screenX, screenY, pitch.xScale, pitch.yScale, "horizontal");
    expect(sbX).toBeCloseTo(90, 5);
    expect(sbY).toBeCloseTo(10, 5);
  });

  it("round-trips through px() for vertical orientation (swapped axes)", () => {
    document.body.innerHTML = '<svg id="test-svg"></svg>';
    const pitch = createPitch(d3.select("#test-svg"), { mode: "full", orientation: "vertical", pxPerYard: 4 });
    const [screenX, screenY] = pitch.px(90, 10);
    const [sbX, sbY] = invertPx(screenX, screenY, pitch.xScale, pitch.yScale, "vertical");
    expect(sbX).toBeCloseTo(90, 5);
    expect(sbY).toBeCloseTo(10, 5);
  });
});

describe("createHeatmap", () => {
  it("mounts a raster surface onto an existing pitch without throwing (any orientation)", () => {
    document.body.innerHTML = '<svg id="test-svg"></svg>';
    const pitch = createPitch(d3.select("#test-svg"), { mode: "full", orientation: "vertical", pxPerYard: 4 });
    const data = makeGrid(10, 8, 8, 1); // dense cell near top-right in StatsBomb (x, y) terms
    expect(() => createHeatmap(pitch, data, { renderStyle: "raster" })).not.toThrow();
    expect(pitch.g.selectAll("g.hm rect").size()).toBeGreaterThan(0);
  });

  it("raster mode places the densest cell in the correct screen quadrant under vertical orientation (regression: D4 misalignment)", () => {
    // A vertical pitch swaps StatsBomb x/y onto screen y/x (see pitch.js's px()).
    // A hot cell near StatsBomb (x=110, y=8) — attacking-end, touchline-adjacent —
    // must render near the corresponding screen position, not transposed.
    document.body.innerHTML = '<svg id="test-svg"></svg>';
    const pitch = createPitch(d3.select("#test-svg"), { mode: "full", orientation: "vertical", pxPerYard: 4 });
    const cols = 12, rows = 8;
    const hotCol = 11; // rightmost column → StatsBomb x ≈ 120 (near max)
    const hotRow = 0;  // topmost row → StatsBomb y ≈ 0 (near min)
    const data = makeGrid(cols, rows, hotCol, hotRow);
    createHeatmap(pitch, data, { renderStyle: "raster" });

    const rects = pitch.g.selectAll("g.hm rect").nodes();
    let densest = null;
    let maxOpacity = -1;
    for (const node of rects) {
      const opacity = parseFloat(node.getAttribute("opacity") || "0");
      if (opacity > maxOpacity) {
        maxOpacity = opacity;
        densest = node;
      }
    }
    expect(densest).not.toBeNull();

    // The hot cell is at StatsBomb (x≈120, y≈0). Under createPitch's vertical
    // px(), screen-x comes from sbY (≈0, near the left) and screen-y comes
    // from sbX (≈120, near the top, since flipAttack defaults false and
    // yDomain is [0, sbW] unflipped — high x maps to the yScale's high end,
    // i.e. bottom of screen... concretely: assert it lands in the same
    // half as px(120, 0) rather than the opposite half, which is what the
    // pre-fix transposed mapping would have produced.
    const [expectedX, expectedY] = pitch.px(120, 0);
    const rectX = parseFloat(densest.getAttribute("x"));
    const rectY = parseFloat(densest.getAttribute("y"));
    const rectW = parseFloat(densest.getAttribute("width"));
    const rectH = parseFloat(densest.getAttribute("height"));
    const rectCx = rectX + rectW / 2;
    const rectCy = rectY + rectH / 2;

    expect(Math.abs(rectCx - expectedX)).toBeLessThan(rectW * 1.5);
    expect(Math.abs(rectCy - expectedY)).toBeLessThan(rectH * 1.5);
  });

  it("update(newData) swaps the grid without re-rendering the pitch", () => {
    document.body.innerHTML = '<svg id="test-svg"></svg>';
    const pitch = createPitch(d3.select("#test-svg"), { mode: "full", orientation: "horizontal", pxPerYard: 4 });
    const data1 = makeGrid(10, 8, 0, 0);
    const { update } = createHeatmap(pitch, data1, { renderStyle: "raster" });
    const countBefore = pitch.g.selectAll("g.hm rect").size();

    const data2 = makeGrid(10, 8, 9, 7);
    update(data2);
    const countAfter = pitch.g.selectAll("g.hm rect").size();
    expect(countAfter).toBe(countBefore);
  });
});
