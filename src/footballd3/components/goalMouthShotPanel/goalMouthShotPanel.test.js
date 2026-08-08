import { describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { createGoalMouthShotPanel } from "./goalMouthShotPanel.js";

function mount(events, config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createGoalMouthShotPanel(d3.select("#test-container"), { events }, config);
}

// shot_end_location is StatsBomb's full-pitch [x, y, z] — NOT [y, z] — verified
// against real match data (e.g. an actual goal's end_location is
// [120.0, 42.4, 0.2]): x sits at the goal line, y is goal-mouth position, z is
// height. These fixtures deliberately use a realistic x (≈120) rather than a
// bare [y, z] pair, so a regression back to reading index [0] as y would fail
// the "correct goal-mouth position" test below instead of silently passing.
const GOAL = {
  event_id: "s-goal", type: "Shot", minute: 72, outcome: "Goal",
  shot_xg: 0.32, shot_end_location: [120, 40, 1.8], is_goal: true,
};
const SAVED = {
  event_id: "s-saved", type: "Shot", minute: 40, outcome: "Saved",
  shot_xg: 0.1, shot_end_location: [120, 38, 0.5], is_goal: false,
};
const OFF_TARGET = {
  event_id: "s-off", type: "Shot", minute: 55, outcome: "Off T",
  shot_xg: 0.05, shot_end_location: [121, 47, 3.1], is_goal: false,
};
const NON_SHOT = { event_id: "p-1", type: "Pass" };

describe("createGoalMouthShotPanel", () => {
  it("classifies Goal/Saved as on-target and everything else as off-target", () => {
    const { g } = mount([GOAL, SAVED, OFF_TARGET, NON_SHOT]);
    expect(g.selectAll(".gmsp-on").size()).toBe(2);
    expect(g.selectAll(".gmsp-off").size()).toBe(1);
  });

  it("ignores non-Shot events and shots with no shot_end_location", () => {
    const noEndLoc = { event_id: "s-x", type: "Shot", outcome: "Blocked", shot_end_location: null };
    const { g } = mount([NON_SHOT, noEndLoc]);
    expect(g.selectAll(".gmsp-on, .gmsp-off").size()).toBe(0);
  });

  it("goals get a solid fill; saved on-target shots do not", () => {
    const { g } = mount([GOAL, SAVED]);
    const goalMark = g.selectAll(".gmsp-on").filter((d) => d.event_id === "s-goal");
    const savedMark = g.selectAll(".gmsp-on").filter((d) => d.event_id === "s-saved");
    expect(goalMark.attr("fill")).not.toBe("none");
    expect(savedMark.attr("fill")).toBe("none");
  });

  it("off-target shots get a dashed stroke", () => {
    const { g } = mount([OFF_TARGET]);
    expect(g.select(".gmsp-off").attr("stroke-dasharray")).toBe("2,2");
  });

  it("hovering a shot fires onHover with its event_id, mouseout fires null", () => {
    const onHover = vi.fn();
    const { g } = mount([GOAL], { onHover });
    const mark = g.select(".gmsp-on");
    mark.dispatch("mouseover");
    expect(onHover).toHaveBeenCalledWith("s-goal");
    mark.dispatch("mouseout");
    expect(onHover).toHaveBeenLastCalledWith(null);
  });

  it("highlightEventId renders exactly one highlight ring for the matching shot", () => {
    const { g, update } = mount([GOAL, SAVED], { highlightEventId: "s-goal" });
    expect(g.selectAll(".gmsp-highlight").size()).toBe(1);

    update({ highlightEventId: null });
    expect(g.selectAll(".gmsp-highlight").size()).toBe(0);
  });

  it("update({data}) re-renders with a new shot set", () => {
    const { g, update } = mount([GOAL]);
    expect(g.selectAll(".gmsp-on, .gmsp-off").size()).toBe(1);

    update({ data: { events: [GOAL, SAVED, OFF_TARGET] } });
    expect(g.selectAll(".gmsp-on, .gmsp-off").size()).toBe(3);
  });

  it("a higher-xG shot gets a larger radius than a lower-xG shot", () => {
    const { g } = mount([GOAL, OFF_TARGET]); // 0.32 vs 0.05
    const goalR = +g.select(".gmsp-on").attr("r");
    const offR = +g.select(".gmsp-off").attr("r");
    expect(goalR).toBeGreaterThan(offR);
  });

  it("positions an on-target shot inside the drawn goal frame (regression: index [1]/[2], not [0]/[1])", () => {
    const { g } = mount([GOAL], { width: 320, height: 220 });
    const frame = g.select(".gmsp-frame");
    const frameX = +frame.attr("x");
    const frameY = +frame.attr("y");
    const frameWidth = +frame.attr("width");
    const frameHeight = +frame.attr("height");

    const mark = g.select(".gmsp-on");
    const cx = +mark.attr("cx");
    const cy = +mark.attr("cy");

    // A center-of-goal shot (y=40, the domain midpoint) must land inside the
    // frame's horizontal span — reading shot_end_location[0] (≈120, the pitch
    // x) as the goal-mouth y here would place it far outside frameX..frameX+frameWidth.
    expect(cx).toBeGreaterThanOrEqual(frameX);
    expect(cx).toBeLessThanOrEqual(frameX + frameWidth);
    expect(cy).toBeGreaterThanOrEqual(frameY);
    expect(cy).toBeLessThanOrEqual(frameY + frameHeight);
  });

  it("renders a net-mesh pattern and references it from the frame's mesh fill (regression: D5 net redesign)", () => {
    const { svg, g } = mount([GOAL]);
    const pattern = svg.select("defs pattern");
    expect(pattern.empty()).toBe(false);

    const patternId = pattern.attr("id");
    const meshFill = g.select(".gmsp-frame-mesh").attr("fill");
    expect(meshFill).toBe(`url(#${patternId})`);
  });

  it("gives each mounted instance its own net-mesh pattern id (no cross-instance collision)", () => {
    document.body.innerHTML = '<div id="a"></div><div id="b"></div>';
    const { svg: svgA } = createGoalMouthShotPanel(d3.select("#a"), { events: [GOAL] });
    const { svg: svgB } = createGoalMouthShotPanel(d3.select("#b"), { events: [GOAL] });
    const idA = svgA.select("defs pattern").attr("id");
    const idB = svgB.select("defs pattern").attr("id");
    expect(idA).not.toBe(idB);
  });

  it("renders side net panels and a ground line beneath the frame", () => {
    const { g } = mount([GOAL], { width: 320, height: 220 });
    expect(g.selectAll(".gmsp-side-net").size()).toBe(2);
    expect(g.select(".gmsp-ground-line").empty()).toBe(false);

    const frame = g.select(".gmsp-frame");
    const groundY = +frame.attr("y") + +frame.attr("height");
    expect(+g.select(".gmsp-ground-line").attr("y1")).toBeCloseTo(groundY, 5);
  });
});
