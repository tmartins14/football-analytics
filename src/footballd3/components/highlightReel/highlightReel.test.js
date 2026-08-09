import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { allEventsMoments, createHighlightReel, selectMoments } from "./highlightReel.js";

function mount(events, config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createHighlightReel(d3.select("#test-container"), { events }, config);
}

describe("selectMoments", () => {
  it("includes every goal, formatted with its xG", () => {
    const events = [
      { event_id: "g1", type: "Shot", is_goal: true, shot_xg: 0.42, minute: 72, location: [110, 40] },
    ];
    const moments = selectMoments(events);
    expect(moments).toHaveLength(1);
    expect(moments[0]).toMatchObject({ minute: 72, kind: "Goal", note: "Goal · xG 0.42", event_id: "g1" });
  });

  it("includes only the single highest-xG non-goal shot, not every shot", () => {
    const events = [
      { event_id: "s-low", type: "Shot", is_goal: false, shot_xg: 0.05, outcome: "Off T", minute: 10, location: [100, 30] },
      { event_id: "s-high", type: "Shot", is_goal: false, shot_xg: 0.31, outcome: "Saved", minute: 20, location: [110, 40] },
    ];
    const moments = selectMoments(events);
    expect(moments).toHaveLength(1);
    expect(moments[0]).toMatchObject({ kind: "Shot", note: "Shot · xG 0.31 · Saved", event_id: "s-high" });
  });

  it("takes the top 3 positive-xt_delta pass/carry events, excluding non-positive ones", () => {
    const events = [
      { event_id: "p1", type: "Pass", xt_delta: 0.05, is_progressive: false, minute: 5, location: [40, 40], end_location: [50, 40] },
      { event_id: "p2", type: "Carry", xt_delta: 0.12, is_progressive: true, minute: 15, location: [50, 40], end_location: [65, 40] },
      { event_id: "p3", type: "Pass", xt_delta: 0.08, is_progressive: false, minute: 25, location: [60, 40], end_location: [75, 40] },
      { event_id: "p4", type: "Pass", xt_delta: -0.2, is_progressive: false, minute: 30, location: [30, 40], end_location: [20, 40] },
      { event_id: "p5", type: "Pass", xt_delta: 0.01, is_progressive: false, minute: 35, location: [45, 40], end_location: [46, 40] },
    ];
    const moments = selectMoments(events);
    const ids = moments.map((m) => m.event_id);
    // Top 3 by xt_delta: p2 (0.12), p3 (0.08), p1 (0.05) — p4 excluded (negative), p5 excluded (lowest of the positives).
    expect(ids.sort()).toEqual(["p1", "p2", "p3"]);
  });

  it("labels progressive vs non-progressive pass/carry moments distinctly", () => {
    const events = [
      { event_id: "prog", type: "Pass", xt_delta: 0.1, is_progressive: true, minute: 10, location: [40, 40], end_location: [60, 40] },
      { event_id: "plain", type: "Carry", xt_delta: 0.08, is_progressive: false, minute: 20, location: [40, 40], end_location: [50, 40] },
    ];
    const moments = selectMoments(events);
    const prog = moments.find((m) => m.event_id === "prog");
    const plain = moments.find((m) => m.event_id === "plain");
    expect(prog).toMatchObject({ kind: "Prog. pass", note: "Progressive pass · +0.100 xT" });
    expect(plain).toMatchObject({ kind: "Carry", note: "carry · +0.080 xT" });
  });

  it("combines all three tiers, sorted chronologically, capped at 5", () => {
    const events = [
      { event_id: "g1", type: "Shot", is_goal: true, shot_xg: 0.5, minute: 80, location: [110, 40] },
      { event_id: "g2", type: "Shot", is_goal: true, shot_xg: 0.3, minute: 10, location: [110, 40] },
      { event_id: "s1", type: "Shot", is_goal: false, shot_xg: 0.2, outcome: "Off T", minute: 50, location: [100, 40] },
      { event_id: "a1", type: "Pass", xt_delta: 0.3, is_progressive: true, minute: 5, location: [40, 40], end_location: [60, 40] },
      { event_id: "a2", type: "Carry", xt_delta: 0.2, is_progressive: false, minute: 60, location: [50, 40], end_location: [65, 40] },
      { event_id: "a3", type: "Pass", xt_delta: 0.15, is_progressive: false, minute: 90, location: [55, 40], end_location: [70, 40] },
    ];
    const moments = selectMoments(events);
    // 6 candidates total (2 goals + 1 shot + 3 actions) — capped to 5,
    // chronological truncation drops the latest-occurring one (a3, minute 90).
    expect(moments).toHaveLength(5);
    expect(moments.map((m) => m.event_id)).not.toContain("a3");
    expect(moments.map((m) => m.minute)).toEqual([5, 10, 50, 60, 80]);
  });

  it("keeps location/end_location and event_id on each moment", () => {
    const events = [
      { event_id: "p1", type: "Pass", xt_delta: 0.1, is_progressive: false, minute: 10, location: [40, 40], end_location: [55, 42] },
    ];
    const [moment] = selectMoments(events);
    expect(moment.location).toEqual([40, 40]);
    expect(moment.end_location).toEqual([55, 42]);
    expect(moment.event_id).toBe("p1");
  });

  it("returns an empty array when there are no qualifying moments", () => {
    const events = [{ event_id: "p1", type: "Pressure", minute: 10, location: [40, 40] }];
    expect(selectMoments(events)).toEqual([]);
  });
});

describe("allEventsMoments (J1: 'all events' mode)", () => {
  it("includes every event, not just curated ones, in chronological order", () => {
    const events = [
      { event_id: "pr1", type: "Pressure", minute: 30, location: [40, 40] },
      { event_id: "p1", type: "Pass", xt_delta: -0.05, is_progressive: false, minute: 5, location: [40, 40], end_location: [50, 40] },
      { event_id: "g1", type: "Shot", is_goal: true, shot_xg: 0.42, minute: 72, location: [110, 40] },
    ];
    const moments = allEventsMoments(events);
    expect(moments.map((m) => m.event_id)).toEqual(["p1", "pr1", "g1"]);
  });

  it("describes a negative-xT pass (unlike selectMoments, which excludes these)", () => {
    const events = [
      { event_id: "p1", type: "Pass", xt_delta: -0.045, is_progressive: false, minute: 5, location: [40, 40], end_location: [30, 40] },
    ];
    const [moment] = allEventsMoments(events);
    expect(moment).toMatchObject({ kind: "Pass", note: "pass · -0.045 xT" });
  });

  it("describes a type with an outcome using a generic '{type} · {outcome}' fallback", () => {
    const events = [{ event_id: "d1", type: "Duel", outcome: "Lost In Play", minute: 40, location: [40, 40] }];
    const [moment] = allEventsMoments(events);
    expect(moment).toMatchObject({ kind: "Duel", note: "Duel · Lost In Play" });
  });

  it("describes a type with no outcome using the bare type name", () => {
    const events = [{ event_id: "pr1", type: "Pressure", minute: 30, location: [40, 40] }];
    const [moment] = allEventsMoments(events);
    expect(moment).toMatchObject({ kind: "Pressure", note: "Pressure" });
  });
});

describe("createHighlightReel", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const events = [
    { event_id: "p1", type: "Pass", xt_delta: 0.3, is_progressive: false, minute: 10, location: [40, 40], end_location: [55, 40] },
    { event_id: "p2", type: "Pass", xt_delta: 0.2, is_progressive: false, minute: 20, location: [50, 40], end_location: [65, 40] },
    { event_id: "g1", type: "Shot", is_goal: true, shot_xg: 0.4, minute: 72, location: [110, 40] },
  ];

  it("shows the first moment initially without firing onScrubTo", () => {
    const onScrubTo = vi.fn();
    const { container } = mount(events, { onScrubTo });
    expect(container.select(".reel-minute").text()).toBe("10'");
    expect(onScrubTo).not.toHaveBeenCalled();
  });

  it("step(1) advances to the next moment and fires onScrubTo with its minute", () => {
    const onScrubTo = vi.fn();
    const { container, step } = mount(events, { onScrubTo });
    step(1);
    expect(onScrubTo).toHaveBeenCalledWith(20);
    expect(container.select(".reel-minute").text()).toBe("20'");
  });

  it("step() clamps at the list boundaries", () => {
    const { step, container } = mount(events);
    step(-1);
    expect(container.select(".reel-minute").text()).toBe("10'"); // stays at index 0
  });

  it("play() jumps straight to the first moment (no separate reset step), then steps every interval, stopping at the end", () => {
    const onScrubTo = vi.fn();
    const { play } = mount(events, { onScrubTo, stepDurationMs: 1000 });

    play();
    expect(onScrubTo).toHaveBeenCalledTimes(1);
    expect(onScrubTo).toHaveBeenCalledWith(10);

    vi.advanceTimersByTime(1000);
    expect(onScrubTo).toHaveBeenCalledWith(20);

    vi.advanceTimersByTime(1000);
    expect(onScrubTo).toHaveBeenCalledWith(72);

    // No further timer scheduled past the last moment.
    vi.advanceTimersByTime(5000);
    expect(onScrubTo).toHaveBeenCalledTimes(3);
  });

  it("clicking Play again while playing stops it (same button toggles both)", () => {
    const onScrubTo = vi.fn();
    const { container, play } = mount(events, { onScrubTo, stepDurationMs: 1000 });
    play();
    expect(container.select(".reel-play").text()).toBe("❚❚ Stop");

    container.select(".reel-play").dispatch("click");
    expect(container.select(".reel-play").text()).toBe("▶ Play");

    vi.advanceTimersByTime(5000);
    expect(onScrubTo).toHaveBeenCalledTimes(1); // only the initial jump-to-first-moment call
  });

  it("clicking a dot stops playback and jumps straight to that moment", () => {
    const onScrubTo = vi.fn();
    const { container, play } = mount(events, { onScrubTo, stepDurationMs: 1000 });
    play();
    const dots = container.selectAll(".reel-dot");
    d3.select(dots.nodes()[2]).dispatch("click");
    expect(onScrubTo).toHaveBeenLastCalledWith(72);

    vi.advanceTimersByTime(5000);
    expect(onScrubTo).toHaveBeenCalledTimes(2); // play's initial jump + the dot click, no timer firing after
  });

  it("hovering the moment description fires onHoverEvent with the current event_id, unhover fires null", () => {
    const onHoverEvent = vi.fn();
    const { container } = mount(events, { onHoverEvent });
    const desc = container.select(".reel-moment");
    desc.dispatch("mouseenter");
    expect(onHoverEvent).toHaveBeenCalledWith("p1");
    desc.dispatch("mouseleave");
    expect(onHoverEvent).toHaveBeenLastCalledWith(null);
  });

  it("update({data}) re-selects moments and resets to index 0", () => {
    const { container, update } = mount(events);
    const newEvents = [
      { event_id: "p9", type: "Pass", xt_delta: 0.9, is_progressive: false, minute: 5, location: [40, 40], end_location: [60, 40] },
    ];
    update({ data: { events: newEvents } });
    expect(container.select(".reel-minute").text()).toBe("5'");
  });

  it("renders the empty-state message and no controls when there are no moments", () => {
    const { container } = mount([]);
    expect(container.select(".reel-empty").text()).toBe("No standout moments in the revealed window.");
    expect(container.select(".reel-play").empty()).toBe(true);
  });

  describe("mode (J1: combined Timeline card)", () => {
    const allEvents = [
      { event_id: "pr1", type: "Pressure", minute: 3, location: [40, 40] },
      { event_id: "p1", type: "Pass", xt_delta: 0.3, is_progressive: false, minute: 10, location: [40, 40], end_location: [55, 40] },
      { event_id: "g1", type: "Shot", is_goal: true, shot_xg: 0.4, minute: 72, location: [110, 40] },
    ];

    it("mode: 'all' plays through every event, including ones selectMoments would drop", () => {
      const { container } = mount(allEvents, { mode: "all" });
      expect(container.select(".reel-minute").text()).toBe("3'");
      expect(container.select(".reel-moment-label").text()).toContain("Moment 1 / 3");
    });

    it("mode: 'all' renders no progress dots", () => {
      const { container } = mount(allEvents, { mode: "all" });
      expect(container.selectAll(".reel-dot").size()).toBe(0);
    });

    it("mode: 'highlights' (default) still renders dots", () => {
      const { container } = mount(allEvents);
      expect(container.selectAll(".reel-dot").size()).toBeGreaterThan(0);
    });

    it("update({mode}) switches moment lists and resets to index 0", () => {
      const { container, update } = mount(allEvents, { mode: "highlights" });
      expect(container.select(".reel-minute").text()).toBe("10'"); // Pressure isn't a curated moment

      update({ mode: "all" });
      expect(container.select(".reel-minute").text()).toBe("3'");
      expect(container.selectAll(".reel-dot").size()).toBe(0);
    });
  });
});
