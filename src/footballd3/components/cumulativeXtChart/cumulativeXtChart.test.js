import { describe, expect, it } from "vitest";
import * as d3 from "d3";

import { createCumulativeXtChart } from "./cumulativeXtChart.js";

function mount(events, config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createCumulativeXtChart(d3.select("#test-container"), { events }, config);
}

describe("createCumulativeXtChart", () => {
  it("final total label matches the hand-computed cumulative sum", () => {
    const events = [
      { minute: 10, second: 0, type: "Pass", xt_delta: 0.05 },
      { minute: 20, second: 0, type: "Carry", xt_delta: 0.03 },
      { minute: 30, second: 0, type: "Pass", xt_delta: -0.01 },
    ];
    const { svg } = mount(events, { finalMinute: 90 });
    expect(svg.select("text.cxt-total-label").text()).toBe((0.05 + 0.03 - 0.01).toFixed(2));
  });

  it("ignores non-Pass/Carry events and events with a null xt_delta", () => {
    const events = [
      { minute: 10, second: 0, type: "Pass", xt_delta: 0.05 },
      { minute: 20, second: 0, type: "Pressure", xt_delta: null },
      { minute: 30, second: 0, type: "Shot", xt_delta: null, outcome: "Off T" },
    ];
    const { svg } = mount(events, { finalMinute: 90 });
    expect(svg.select("text.cxt-total-label").text()).toBe("0.05");
  });

  it("renders exactly one shot chip and one goal ring for a single goal", () => {
    const events = [
      { minute: 10, second: 0, type: "Pass", xt_delta: 0.05 },
      { minute: 50, second: 0, type: "Shot", xt_delta: null, outcome: "Goal" },
    ];
    const { g } = mount(events, { finalMinute: 90 });
    expect(g.selectAll("circle.cxt-shot-chip").size()).toBe(1);
    expect(g.selectAll("circle.cxt-goal-ring").size()).toBe(1);
  });

  it("a non-goal shot gets a chip but no ring", () => {
    const events = [
      { minute: 10, second: 0, type: "Pass", xt_delta: 0.05 },
      { minute: 50, second: 0, type: "Shot", xt_delta: null, outcome: "Saved" },
    ];
    const { g } = mount(events, { finalMinute: 90 });
    expect(g.selectAll("circle.cxt-shot-chip").size()).toBe(1);
    expect(g.selectAll("circle.cxt-goal-ring").size()).toBe(0);
  });

  it("showShots: false suppresses shot markers entirely", () => {
    const events = [
      { minute: 50, second: 0, type: "Shot", xt_delta: null, outcome: "Goal" },
    ];
    const { g } = mount(events, { finalMinute: 90, showShots: false });
    expect(g.selectAll("circle.cxt-shot-chip").size()).toBe(0);
  });

  it("update({data}) recomputes the line for new events", () => {
    const initial = [{ minute: 10, second: 0, type: "Pass", xt_delta: 0.05 }];
    const { svg, update } = mount(initial, { finalMinute: 90 });
    expect(svg.select("text.cxt-total-label").text()).toBe("0.05");

    update({ data: { events: [
      { minute: 10, second: 0, type: "Pass", xt_delta: 0.05 },
      { minute: 20, second: 0, type: "Pass", xt_delta: 0.10 },
    ] } });
    expect(svg.select("text.cxt-total-label").text()).toBe("0.15");
  });
});
