import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { createHighlightReel, selectMoments } from "./highlightReel.js";

function mount(events, config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createHighlightReel(d3.select("#test-container"), { events }, config);
}

describe("selectMoments", () => {
  it("puts every goal first, chronologically, then re-sorts the whole set by time", () => {
    const events = [
      { event_id: "g1", type: "Shot", is_goal: true, minute: 72, second: 0 },
      { event_id: "p1", type: "Pass", xt_delta: 0.3, minute: 10, second: 0 },
      { event_id: "p2", type: "Pass", xt_delta: 0.1, minute: 40, second: 0 },
    ];
    const moments = selectMoments(events, 5);
    expect(moments.map((m) => m.eventId)).toEqual(["p1", "p2", "g1"]);
  });

  it("fills remaining slots with the highest |xt_delta| actions, excluding goals", () => {
    const events = [
      { event_id: "g1", type: "Shot", is_goal: true, minute: 72, second: 0 },
      { event_id: "p-big", type: "Pass", xt_delta: 0.5, minute: 10, second: 0 },
      { event_id: "p-neg", type: "Carry", xt_delta: -0.4, minute: 20, second: 0 },
      { event_id: "p-small", type: "Pass", xt_delta: 0.05, minute: 30, second: 0 },
    ];
    const moments = selectMoments(events, 3);
    const ids = moments.map((m) => m.eventId);
    expect(ids).toContain("g1");
    expect(ids).toContain("p-big");
    expect(ids).toContain("p-neg"); // |−0.4| beats |0.05|
    expect(ids).not.toContain("p-small");
  });

  it("caps at maxMoments even with more goals than that", () => {
    const events = Array.from({ length: 6 }, (_, i) => ({
      event_id: `g${i}`, type: "Shot", is_goal: true, minute: i * 10, second: 0,
    }));
    expect(selectMoments(events, 5)).toHaveLength(5);
  });

  it("returns fewer than the minimum when the player has few events", () => {
    const events = [{ event_id: "p1", type: "Pass", xt_delta: 0.1, minute: 10, second: 0 }];
    expect(selectMoments(events, 5)).toHaveLength(1);
  });

  it("annotates a goal as 'Goal' and an action with its signed xT", () => {
    const events = [
      { event_id: "g1", type: "Shot", is_goal: true, minute: 72, second: 0 },
      { event_id: "p1", type: "Pass", xt_delta: 0.08, minute: 10, second: 0 },
    ];
    const moments = selectMoments(events, 5);
    expect(moments.find((m) => m.eventId === "g1").annotation).toBe("Goal");
    expect(moments.find((m) => m.eventId === "p1").annotation).toBe("Pass +0.08 xT");
  });
});

describe("createHighlightReel", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const events = [
    { event_id: "p1", type: "Pass", xt_delta: 0.3, minute: 10, second: 0 },
    { event_id: "p2", type: "Pass", xt_delta: 0.2, minute: 20, second: 0 },
    { event_id: "g1", type: "Shot", is_goal: true, minute: 72, second: 0 },
  ];

  it("shows the first moment initially without firing onMoment", () => {
    const onMoment = vi.fn();
    const { container } = mount(events, { onMoment });
    expect(container.select(".reel-moment").text()).toContain("10'");
    expect(onMoment).not.toHaveBeenCalled();
  });

  it("step(1) advances to the next moment and fires onMoment", () => {
    const onMoment = vi.fn();
    const { container, step } = mount(events, { onMoment });
    step(1);
    expect(onMoment).toHaveBeenCalledWith(expect.objectContaining({ eventId: "p2" }), 1);
    expect(container.select(".reel-moment").text()).toContain("20'");
  });

  it("step() clamps at the list boundaries", () => {
    const { step, container } = mount(events);
    step(-1);
    expect(container.select(".reel-moment").text()).toContain("10'"); // stays at index 0
  });

  it("play() calls onReset then steps through every moment on a timer, and stops at the end", () => {
    const onReset = vi.fn();
    const onMoment = vi.fn();
    const { play } = mount(events, { onReset, onMoment, stepDurationMs: 1000 });

    play();
    expect(onReset).toHaveBeenCalledTimes(1);
    expect(onMoment).toHaveBeenCalledWith(expect.objectContaining({ eventId: "p1" }), 0);

    vi.advanceTimersByTime(1000);
    expect(onMoment).toHaveBeenCalledWith(expect.objectContaining({ eventId: "p2" }), 1);

    vi.advanceTimersByTime(1000);
    expect(onMoment).toHaveBeenCalledWith(expect.objectContaining({ eventId: "g1" }), 2);

    // No further timer scheduled past the last moment.
    vi.advanceTimersByTime(5000);
    expect(onMoment).toHaveBeenCalledTimes(3);
  });

  it("pause() stops playback without resetting the current index", () => {
    const onMoment = vi.fn();
    const { play, pause } = mount(events, { onMoment, stepDurationMs: 1000 });
    play();
    vi.advanceTimersByTime(1000); // now at index 1
    pause();
    vi.advanceTimersByTime(5000);
    expect(onMoment).toHaveBeenCalledTimes(2); // index 0 (play) + index 1 (one tick), no more
  });

  it("clicking a dot pauses playback and jumps straight to that moment", () => {
    const onMoment = vi.fn();
    const { container, play } = mount(events, { onMoment, stepDurationMs: 1000 });
    play();
    const dots = container.selectAll(".reel-dot");
    d3.select(dots.nodes()[2]).dispatch("click");
    expect(onMoment).toHaveBeenLastCalledWith(expect.objectContaining({ eventId: "g1" }), 2);

    vi.advanceTimersByTime(5000);
    expect(onMoment).toHaveBeenCalledTimes(2); // play's index 0 + the dot click, no timer firing after
  });

  it("update({data}) re-selects moments and resets to index 0", () => {
    const { container, update } = mount(events);
    const newEvents = [{ event_id: "p9", type: "Pass", xt_delta: 0.9, minute: 5, second: 0 }];
    update({ data: { events: newEvents } });
    expect(container.select(".reel-moment").text()).toContain("5'");
  });

  it("renders a fallback message with no moments", () => {
    const { container } = mount([]);
    expect(container.select(".reel-moment").text()).toBe("No standout moments");
  });
});
