import { describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { createGoalMouthShotPanel } from "./goalMouthShotPanel.js";

function mount(events, config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createGoalMouthShotPanel(d3.select("#test-container"), { events }, config);
}

const GOAL = {
  event_id: "s-goal", type: "Shot", minute: 72, outcome: "Goal",
  shot_xg: 0.32, shot_end_location: [40, 1.8], is_goal: true,
};
const SAVED = {
  event_id: "s-saved", type: "Shot", minute: 40, outcome: "Saved",
  shot_xg: 0.1, shot_end_location: [38, 0.5], is_goal: false,
};
const OFF_TARGET = {
  event_id: "s-off", type: "Shot", minute: 55, outcome: "Off T",
  shot_xg: 0.05, shot_end_location: [47, 3.1], is_goal: false,
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
});
