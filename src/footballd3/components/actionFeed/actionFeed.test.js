import { describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { classifyLayer, createActionFeed } from "./actionFeed.js";

function mount(events, config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createActionFeed(d3.select("#test-container"), { events }, config);
}

function rowTexts(container) {
  return container.selectAll(".action-feed-row").nodes().map((n) => n.textContent);
}

describe("classifyLayer", () => {
  it("classifies a key pass over a plain progressive pass", () => {
    const event = { type: "Pass", key_pass: true, is_progressive: true };
    expect(classifyLayer(event)).toBe("key_pass");
  });

  it("classifies a progressive carry", () => {
    expect(classifyLayer({ type: "Carry", is_progressive: true })).toBe("progressive_pass");
  });

  it("classifies Dispossessed/Miscontrol as turnover", () => {
    expect(classifyLayer({ type: "Dispossessed" })).toBe("turnover");
    expect(classifyLayer({ type: "Miscontrol" })).toBe("turnover");
  });

  it("classifies a plain non-progressive pass as other", () => {
    expect(classifyLayer({ type: "Pass", is_progressive: false, key_pass: false })).toBe("other");
  });

  it("classifies Shot", () => {
    expect(classifyLayer({ type: "Shot" })).toBe("shot");
  });
});

describe("createActionFeed", () => {
  const events = [
    { event_id: "e-30", minute: 30, second: 0, type: "Pass", outcome: null, xt_delta: 0.02 },
    { event_id: "e-10", minute: 10, second: 0, type: "Pass", outcome: "Incomplete", xt_delta: -0.01 },
    { event_id: "e-70", minute: 70, second: 0, type: "Shot", outcome: "Goal", shot_xg: 0.4 },
  ];

  it("sorts by minute ascending by default", () => {
    const { container } = mount(events);
    const ids = container.selectAll(".action-feed-row").data().map((d) => d.event_id);
    expect(ids).toEqual(["e-10", "e-30", "e-70"]);
  });

  it("sortDir desc reverses the order", () => {
    const { container } = mount(events, { sortDir: "desc" });
    const ids = container.selectAll(".action-feed-row").data().map((d) => d.event_id);
    expect(ids).toEqual(["e-70", "e-30", "e-10"]);
  });

  it("sortBy xt orders by signed swing value", () => {
    const { container } = mount(events, { sortBy: "xt", sortDir: "asc" });
    const ids = container.selectAll(".action-feed-row").data().map((d) => d.event_id);
    // -0.01 (e-10) < 0.02 (e-30) < 0.4 shot_xg (e-70)
    expect(ids).toEqual(["e-10", "e-30", "e-70"]);
  });

  it("row hover fires onHoverRow with the event_id, mouseout fires null", () => {
    const onHoverRow = vi.fn();
    const { container } = mount(events, { onHoverRow });
    const firstRow = container.select(".action-feed-row");
    firstRow.dispatch("mouseover");
    expect(onHoverRow).toHaveBeenCalledWith("e-10");
    firstRow.dispatch("mouseout");
    expect(onHoverRow).toHaveBeenLastCalledWith(null);
  });

  it("renders one row per event", () => {
    const { container } = mount(events);
    expect(rowTexts(container).length).toBe(3);
  });

  it("update({sortBy}) re-sorts without needing new data", () => {
    const { container, update } = mount(events);
    update({ sortBy: "xt", sortDir: "desc" });
    const ids = container.selectAll(".action-feed-row").data().map((d) => d.event_id);
    expect(ids).toEqual(["e-70", "e-30", "e-10"]);
  });

  it("update({data}) replaces the row set", () => {
    const { container, update } = mount(events);
    update({ data: { events: [events[0]] } });
    expect(container.selectAll(".action-feed-row").size()).toBe(1);
  });

  describe("xT/xG value text (regression: H2)", () => {
    function valueFor(container, eventId) {
      const row = container.selectAll(".action-feed-row").filter((d) => d.event_id === eventId);
      return row.select(".action-feed-value");
    }

    it("shows a signed xT value for a positive-swing Pass/Carry, colored navy", () => {
      const { container } = mount(events);
      const value = valueFor(container, "e-30"); // xt_delta: 0.02
      expect(value.text()).toBe("+0.020 xT");
      expect(value.style("color")).toBe("rgb(30, 58, 95)"); // #1E3A5F
    });

    it("shows a signed xT value for a negative-swing Pass/Carry, colored focal", () => {
      const { container } = mount(events);
      const value = valueFor(container, "e-10"); // xt_delta: -0.01
      expect(value.text()).toBe("-0.010 xT");
      expect(value.style("color")).toBe("rgb(159, 18, 57)"); // #9F1239
    });

    it("shows an unsigned xG value for a Shot", () => {
      const { container } = mount(events);
      const value = valueFor(container, "e-70"); // shot_xg: 0.4
      expect(value.text()).toBe("xG 0.40");
    });

    it("shows no value for an event type with no swing (e.g. Pressure)", () => {
      const pressureEvent = { event_id: "e-50", minute: 50, second: 0, type: "Pressure", outcome: null };
      const { container } = mount([...events, pressureEvent]);
      const value = valueFor(container, "e-50");
      expect(value.text()).toBe("");
    });
  });
});
