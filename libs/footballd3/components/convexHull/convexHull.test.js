import { describe, expect, it } from "vitest";
import * as d3 from "d3";

import { createPitch } from "../pitch/pitch.js";
import { createConvexHull } from "./convexHull.js";

function makePitch() {
  document.body.innerHTML = '<svg id="test-svg"></svg>';
  return createPitch(d3.select("#test-svg"), { mode: "full", pxPerYard: 4 });
}

describe("createConvexHull points mode", () => {
  it("renders a hull path for a 4-point square", () => {
    const pitch = makePitch();
    createConvexHull(pitch, { points: [[20, 20], [20, 60], [60, 60], [60, 20]] });
    expect(pitch.g.select("path.ch-hull-points").empty()).toBe(false);
  });

  it("renders nothing for fewer than 3 points", () => {
    const pitch = makePitch();
    createConvexHull(pitch, { points: [[20, 20], [60, 60]] });
    expect(pitch.g.select("path.ch-hull-points").empty()).toBe(true);
  });

  it("renders a degenerate (2-point) hull for 3 collinear points, not nothing", () => {
    // d3.polygonHull only returns null for fewer than 3 points — for 3+
    // collinear points it returns the two extremes as a degenerate hull,
    // verified empirically (see convexHull.js's _renderPointsHull docs).
    const pitch = makePitch();
    createConvexHull(pitch, { points: [[10, 10], [20, 20], [30, 30]] });
    expect(pitch.g.select("path.ch-hull-points").empty()).toBe(false);
  });

  it("uses pointsColor for the fill/stroke", () => {
    const pitch = makePitch();
    createConvexHull(
      pitch,
      { points: [[20, 20], [20, 60], [60, 60], [60, 20]] },
      { pointsColor: "#123456" }
    );
    const path = pitch.g.select("path.ch-hull-points");
    expect(path.attr("fill")).toBe("#123456");
  });

  it("update() swaps points-mode for sides-mode and clears the old hull", () => {
    const pitch = makePitch();
    const { update } = createConvexHull(pitch, {
      points: [[20, 20], [20, 60], [60, 60], [60, 20]],
    });
    expect(pitch.g.select("path.ch-hull-points").empty()).toBe(false);

    update({
      sides: [
        {
          side: "offense", team_name: "A",
          hull_vertices: [[20, 20], [20, 60], [60, 60]],
          area: 800, player_count: 3,
        },
      ],
    });

    expect(pitch.g.select("path.ch-hull-points").empty()).toBe(true);
    expect(pitch.g.select("path.ch-hull-offense").empty()).toBe(false);
  });
});

describe("createConvexHull sides mode (existing behavior, unregressed)", () => {
  it("renders one hull path per side", () => {
    const pitch = makePitch();
    createConvexHull(pitch, {
      sides: [
        {
          side: "offense", team_name: "A",
          hull_vertices: [[20, 20], [20, 60], [60, 60]],
          area: 800, player_count: 3,
        },
        {
          side: "defense", team_name: "B",
          hull_vertices: [[70, 20], [70, 60], [100, 40]],
          area: 600, player_count: 3,
        },
      ],
    });

    expect(pitch.g.select("path.ch-hull-offense").empty()).toBe(false);
    expect(pitch.g.select("path.ch-hull-defense").empty()).toBe(false);
  });

  it("respects the toggle option", () => {
    const pitch = makePitch();
    createConvexHull(
      pitch,
      {
        sides: [
          {
            side: "offense", team_name: "A",
            hull_vertices: [[20, 20], [20, 60], [60, 60]],
            area: 800, player_count: 3,
          },
          {
            side: "defense", team_name: "B",
            hull_vertices: [[70, 20], [70, 60], [100, 40]],
            area: 600, player_count: 3,
          },
        ],
      },
      { toggle: "offense" }
    );

    expect(pitch.g.select("path.ch-hull-offense").empty()).toBe(false);
    expect(pitch.g.select("path.ch-hull-defense").empty()).toBe(true);
  });
});
