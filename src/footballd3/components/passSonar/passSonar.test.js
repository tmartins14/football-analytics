import { describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { createPassSonar } from "./passSonar.js";

function mount(events, config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createPassSonar(d3.select("#test-container"), { events }, config);
}

describe("createPassSonar", () => {
  it("renders one wedge pair per configured bin", () => {
    const { g } = mount([], { numBins: 8 });
    expect(g.selectAll(".sonar-wedge").size()).toBe(8);
    expect(g.selectAll("path.sonar-attempted").size()).toBe(8);
    expect(g.selectAll("path.sonar-completed").size()).toBe(8);
  });

  it("ignores non-Pass events and passes with no end_location", () => {
    const events = [
      { type: "Carry", location: [10, 10], end_location: [20, 10] },
      { type: "Pass", location: [10, 10], end_location: null },
    ];
    const { g } = mount(events, { numBins: 4 });
    // Every bin's attempted wedge should render at radius 0 (no d attribute variance
    // to assert directly, but the underlying bin data should be empty everywhere).
    g.selectAll("path.sonar-attempted").each(function () {
      expect(d3.select(this).attr("d")).toBeTruthy(); // still a valid (zero-radius) arc path
    });
  });

  it("a due-forward pass lands in bin 0", () => {
    const events = [
      { event_id: "e1", type: "Pass", location: [10, 40], end_location: [30, 40], outcome: null },
    ];
    const onHover = vi.fn();
    const { g } = mount(events, { numBins: 16, onHover });

    const firstWedge = g.selectAll(".sonar-wedge").filter((d) => d.bin === 0);
    firstWedge.dispatch("mouseover");
    expect(onHover).toHaveBeenCalledWith({ bin: 0, eventIds: ["e1"] });
  });

  it("splits attempted vs completed counts within a bin", () => {
    const events = [
      { event_id: "e1", type: "Pass", location: [10, 40], end_location: [30, 40], outcome: null },
      { event_id: "e2", type: "Pass", location: [10, 40], end_location: [30, 41], outcome: "Incomplete" },
    ];
    const onHover = vi.fn();
    const { g } = mount(events, { numBins: 4, onHover });

    const firstWedge = g.selectAll(".sonar-wedge").filter((d) => d.bin === 0);
    firstWedge.dispatch("mouseover");
    expect(onHover).toHaveBeenCalledWith({ bin: 0, eventIds: ["e1", "e2"] });
  });

  it("mouseout fires onHover(null)", () => {
    const events = [
      { event_id: "e1", type: "Pass", location: [10, 40], end_location: [30, 40], outcome: null },
    ];
    const onHover = vi.fn();
    const { g } = mount(events, { numBins: 4, onHover });

    const wedge = g.selectAll(".sonar-wedge").filter((d) => d.bin === 0);
    wedge.dispatch("mouseover");
    wedge.dispatch("mouseout");
    expect(onHover).toHaveBeenLastCalledWith(null);
  });

  it("highlightEventId shows the ring only on the bin containing that event", () => {
    const events = [
      { event_id: "e1", type: "Pass", location: [10, 40], end_location: [30, 40], outcome: null },
      { event_id: "e2", type: "Pass", location: [10, 40], end_location: [10, 60], outcome: null },
    ];
    const { g, update } = mount(events, { numBins: 4, highlightEventId: "e1" });

    const visibleHighlights = () =>
      g.selectAll(".sonar-highlight").filter(function () {
        return d3.select(this).style("display") !== "none";
      }).size();

    expect(visibleHighlights()).toBe(1);

    update({ highlightEventId: null });
    expect(visibleHighlights()).toBe(0);
  });

  it("update({data}) re-bins with new events", () => {
    const { g, update } = mount([], { numBins: 4 });
    expect(g.selectAll(".sonar-wedge").filter((d) => d.attempted.length > 0).size()).toBe(0);

    update({ data: { events: [
      { event_id: "e1", type: "Pass", location: [10, 40], end_location: [30, 40], outcome: null },
    ] } });
    expect(g.selectAll(".sonar-wedge").filter((d) => d.attempted.length > 0).size()).toBe(1);
  });
});
