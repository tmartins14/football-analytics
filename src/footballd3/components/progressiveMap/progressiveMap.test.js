import { describe, expect, it } from "vitest";
import * as d3 from "d3";

import { createPitch } from "../pitch/pitch.js";
import { createProgressiveMap } from "./progressiveMap.js";

function makePitch() {
  document.body.innerHTML = '<svg id="test-svg"></svg>';
  return createPitch(d3.select("#test-svg"), { mode: "full", pxPerYard: 4 });
}

function makeAction(overrides = {}) {
  return {
    action_type: "pass",
    display_name: "Test Player",
    x0: 20, y0: 40, x1: 40, y1: 40,
    completed: true,
    progressive: false,
    distance_gained: 5,
    minute: 10,
    ...overrides,
  };
}

describe("createProgressiveMap update({actions})", () => {
  it("replaces the rendered arrow set with a new action array", () => {
    const pitch = makePitch();
    const initial = [makeAction(), makeAction()];
    const { update, g } = createProgressiveMap(pitch, { actions: initial });
    expect(g.selectAll("line").size()).toBe(initial.length);

    const replaced = [makeAction(), makeAction(), makeAction()];
    update({ actions: replaced });
    expect(g.selectAll("line").size()).toBe(replaced.length);
  });

  it("combines a replaced actions array with the existing toggle filter", () => {
    const pitch = makePitch();
    const actions = [
      makeAction({ action_type: "pass" }),
      makeAction({ action_type: "carry" }),
    ];
    const { update, g } = createProgressiveMap(pitch, { actions }, { toggle: "passes" });
    expect(g.selectAll("line").size()).toBe(1); // only the pass rendered

    const moreActions = [
      makeAction({ action_type: "pass" }),
      makeAction({ action_type: "pass" }),
      makeAction({ action_type: "carry" }),
    ];
    update({ actions: moreActions });
    expect(g.selectAll("line").size()).toBe(2); // toggle:"passes" still applied
  });

  it("combines a replaced actions array with the player filter", () => {
    const pitch = makePitch();
    const actions = [makeAction({ display_name: "Alice" }), makeAction({ display_name: "Bob" })];
    const { update, g } = createProgressiveMap(pitch, { actions }, { player: "Alice" });
    expect(g.selectAll("line").size()).toBe(1);

    update({
      actions: [
        makeAction({ display_name: "Alice" }),
        makeAction({ display_name: "Alice" }),
        makeAction({ display_name: "Bob" }),
      ],
    });
    expect(g.selectAll("line").size()).toBe(2);
  });

  it("still renders correctly on a fresh instance with only the data.actions field (no update() call)", () => {
    const pitch = makePitch();
    const { g } = createProgressiveMap(pitch, { actions: [makeAction(), makeAction(), makeAction()] });
    expect(g.selectAll("line").size()).toBe(3);
  });
});
