import { describe, expect, it, vi } from "vitest";
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

  it("onHover fires with a point carrying the real event_id", () => {
    // jsdom has no real SVG layout (getBoundingClientRect is all zeros), so
    // d3.pointer falls back to raw clientX/clientY — dispatch a real
    // MouseEvent near minute 10's pixel position (same technique as
    // scrubber.test.js's click-the-track test) rather than asserting on an
    // exact bisected minute.
    const onHover = vi.fn();
    const events = [
      { event_id: "p-1", minute: 10, second: 0, type: "Pass", xt_delta: 0.05 },
    ];
    const { g } = mount(events, { finalMinute: 90, onHover });

    const overlay = g.select("rect.cxt-overlay").node();
    overlay.dispatchEvent(new window.MouseEvent("mousemove", { bubbles: true, clientX: 72, clientY: 50 }));

    expect(onHover).toHaveBeenCalledWith(expect.objectContaining({ event_id: "p-1" }));
  });

  it("highlightEventId rings the matching line point", () => {
    const events = [
      { event_id: "p-1", minute: 10, second: 0, type: "Pass", xt_delta: 0.05 },
      { event_id: "p-2", minute: 30, second: 0, type: "Pass", xt_delta: 0.03 },
    ];
    const { g, update } = mount(events, { finalMinute: 90, highlightEventId: "p-2" });
    expect(g.selectAll(".cxt-highlight").size()).toBe(1);

    update({ highlightEventId: null });
    expect(g.selectAll(".cxt-highlight").size()).toBe(0);
  });

  it("highlightEventId also rings a matching shot chip, not just line points", () => {
    const events = [
      { event_id: "p-1", minute: 10, second: 0, type: "Pass", xt_delta: 0.05 },
      { event_id: "s-1", minute: 50, second: 0, type: "Shot", xt_delta: null, outcome: "Saved" },
    ];
    const { g } = mount(events, { finalMinute: 90, highlightEventId: "s-1" });
    expect(g.selectAll(".cxt-highlight").size()).toBe(1);
  });

  it("highlightEventId matching nothing renders no highlight ring", () => {
    const events = [{ event_id: "p-1", minute: 10, second: 0, type: "Pass", xt_delta: 0.05 }];
    const { g } = mount(events, { finalMinute: 90, highlightEventId: "does-not-exist" });
    expect(g.selectAll(".cxt-highlight").size()).toBe(0);
  });
});
