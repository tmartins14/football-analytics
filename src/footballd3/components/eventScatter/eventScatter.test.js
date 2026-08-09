import { describe, expect, it } from "vitest";
import * as d3 from "d3";

import { createPitch } from "../pitch/pitch.js";
import { createEventScatter } from "./eventScatter.js";
import { CATEGORY_SHAPE } from "../actionFeed/actionFeed.js";

function makePitch() {
  document.body.innerHTML = '<svg id="test-svg"></svg>';
  return createPitch(d3.select("#test-svg"), { mode: "full", pxPerYard: 4 });
}

const PASS = {
  event_id: "e1", event_type: "Pass", seconds: 1.2,
  x: 40, y: 30, end_x: 55, end_y: 35, player: "Test Player", outcome: null,
};
const BALL_RECEIPT = {
  event_id: "e2", event_type: "Ball Receipt*", seconds: 2.0,
  x: 55, y: 35, end_x: null, end_y: null, player: "Test Player", outcome: null,
};

describe("createEventScatter", () => {
  it("mounts onto an existing pitch without throwing (regression: tooltip must not touch document at module scope)", () => {
    const pitch = makePitch();
    expect(() => createEventScatter(pitch, { events: [PASS] })).not.toThrow();
  });

  it("renders one arrow line and origin dot for an event with end coordinates", () => {
    const pitch = makePitch();
    createEventScatter(pitch, { events: [PASS] });
    expect(pitch.g.selectAll("g.es line").size()).toBe(1);
    expect(pitch.g.selectAll("g.es path.es-marker").size()).toBe(1);
  });

  it("excludes Ball Receipt* events by default", () => {
    const pitch = makePitch();
    createEventScatter(pitch, { events: [PASS, BALL_RECEIPT] });
    expect(pitch.g.selectAll("g.es path.es-marker").size()).toBe(1);
  });

  it("includes Ball Receipt* events when includeBallReceipt is true", () => {
    const pitch = makePitch();
    createEventScatter(pitch, { events: [PASS, BALL_RECEIPT] }, { includeBallReceipt: true });
    expect(pitch.g.selectAll("g.es path.es-marker").size()).toBe(2);
  });

  it("hovering a marker shows the tooltip lazily (created on first use, not at import time)", () => {
    const pitch = makePitch();
    createEventScatter(pitch, { events: [PASS] });
    const circle = pitch.g.select("g.es path.es-marker").node();
    circle.dispatchEvent(new window.MouseEvent("mouseover", { bubbles: true }));
    const tooltip = document.body.lastElementChild;
    expect(tooltip.style.display).toBe("block");
    expect(tooltip.innerHTML).toContain("Test Player");
  });

  it("update({events}) re-renders with a new event array", () => {
    const pitch = makePitch();
    const { update } = createEventScatter(pitch, { events: [PASS] });
    expect(pitch.g.selectAll("g.es path.es-marker").size()).toBe(1);

    update({ events: [PASS, { ...PASS, event_id: "e3", x: 10, y: 10, end_x: null, end_y: null } ] });
    expect(pitch.g.selectAll("g.es path.es-marker").size()).toBe(2);
  });

  describe("shape+fill category encoding (regression: J4, replaces the old color-coded markers)", () => {
    it("renders a filled marker for a successful Pass (no outcome)", () => {
      const pitch = makePitch();
      createEventScatter(pitch, { events: [PASS] }); // PASS has outcome: null
      const marker = pitch.g.select("g.es path.es-marker");
      expect(marker.attr("fill")).not.toBe("none");
      expect(Number(marker.attr("stroke-width"))).toBe(0);
    });

    it("renders a hollow marker for a failed Pass (a real outcome string)", () => {
      const pitch = makePitch();
      const failedPass = { ...PASS, event_id: "e6", outcome: "Incomplete" };
      createEventScatter(pitch, { events: [failedPass] });
      const marker = pitch.g.select("g.es path.es-marker");
      expect(marker.attr("fill")).toBe("none");
      expect(Number(marker.attr("stroke-width"))).toBeGreaterThan(0);
    });

    it("uses CATEGORY_SHAPE's shot symbol for a Shot event, shared with actionFeed.js", () => {
      const pitch = makePitch();
      const shot = { ...PASS, event_id: "e7", event_type: "Shot", end_x: null, end_y: null, outcome: "Goal" };
      createEventScatter(pitch, { events: [shot] });
      const marker = pitch.g.select("g.es path.es-marker");
      const expected = d3.symbol().type(CATEGORY_SHAPE.shot).size(4 * 5 * 5)();
      expect(marker.attr("d")).toBe(expected);
    });
  });

  describe("tooltip player/time fields are optional (regression: I3 'undefined' tooltip)", () => {
    it("shows the minute (not 'undefined') for an event with no player, only minute", () => {
      const pitch = makePitch();
      const noPlayer = { event_id: "e4", event_type: "Pass", minute: 23, x: 40, y: 30, end_x: null, end_y: null, outcome: null };
      createEventScatter(pitch, { events: [noPlayer] });
      const circle = pitch.g.select("g.es path.es-marker").node();
      circle.dispatchEvent(new window.MouseEvent("mouseover", { bubbles: true }));
      const tooltip = document.body.lastElementChild;
      expect(tooltip.innerHTML).not.toContain("undefined");
      expect(tooltip.innerHTML).toContain("23'");
    });

    it("falls back to possession-relative seconds when minute is absent (unchanged, other real consumer)", () => {
      const pitch = makePitch();
      createEventScatter(pitch, { events: [PASS] }); // PASS has seconds, no minute
      const circle = pitch.g.select("g.es path.es-marker").node();
      circle.dispatchEvent(new window.MouseEvent("mouseover", { bubbles: true }));
      const tooltip = document.body.lastElementChild;
      expect(tooltip.innerHTML).toContain("+1.2s");
      expect(tooltip.innerHTML).toContain("Test Player");
    });

    it("prefers minute over seconds when both are present", () => {
      const pitch = makePitch();
      const both = { event_id: "e5", event_type: "Pass", minute: 10, seconds: 42.0, x: 40, y: 30, end_x: null, end_y: null, outcome: null };
      createEventScatter(pitch, { events: [both] });
      const circle = pitch.g.select("g.es path.es-marker").node();
      circle.dispatchEvent(new window.MouseEvent("mouseover", { bubbles: true }));
      const tooltip = document.body.lastElementChild;
      expect(tooltip.innerHTML).toContain("10'");
      expect(tooltip.innerHTML).not.toContain("42.0s");
    });
  });
});
