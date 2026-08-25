import { describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { createScrubber } from "./scrubber.js";

function mount(config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createScrubber(d3.select("#test-container"), config);
}

describe("createScrubber", () => {
  it("seek() moves the handle label without firing onScrub", () => {
    const onScrub = vi.fn();
    const { seek, svg } = mount({ minMinute: 0, maxMinute: 90, initialMinute: 0, onScrub });

    seek(45);

    expect(onScrub).not.toHaveBeenCalled();
    expect(svg.select("g.scrub-handle text").text()).toBe("45'");
  });

  it("seek() clamps to the configured domain", () => {
    const { seek, svg } = mount({ minMinute: 0, maxMinute: 90, initialMinute: 0 });
    seek(999);
    expect(svg.select("g.scrub-handle text").text()).toBe("90'");
    seek(-50);
    expect(svg.select("g.scrub-handle text").text()).toBe("0'");
  });

  it("clicking the track fires onScrub", () => {
    // jsdom has no real layout (getBoundingClientRect is all zeros), so the
    // exact resulting minute from a simulated click isn't reliably
    // predictable here — this asserts the callback fires, not a pixel-exact
    // value. See docs/testing.md for why.
    const onScrub = vi.fn();
    const { svg } = mount({ minMinute: 0, maxMinute: 90, initialMinute: 0, onScrub });

    const track = svg.select("g.scrub-track line").node();
    track.dispatchEvent(new window.MouseEvent("click", { bubbles: true, clientX: 200, clientY: 0 }));

    expect(onScrub).toHaveBeenCalledTimes(1);
  });

  it("ArrowRight/ArrowLeft on the handle nudge the minute and fire onScrub", () => {
    // Re-query the handle node after each dispatch: every moveTo() re-renders
    // the handle group (removes and re-appends the circle), and while the
    // stale node reference would likely still work (its old listener reads
    // the same closured _minute), querying fresh avoids relying on that.
    const onScrub = vi.fn();
    const { seek, svg } = mount({ minMinute: 0, maxMinute: 90, initialMinute: 50, onScrub });
    seek(50); // establish a known starting point without triggering onScrub

    svg.select("g.scrub-handle circle").node()
      .dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    expect(onScrub).toHaveBeenCalledWith(51);

    svg.select("g.scrub-handle circle").node()
      .dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowLeft", shiftKey: true, bubbles: true }));
    expect(onScrub).toHaveBeenCalledWith(46);
  });

  it("update({ events }) changes the number of rendered density ticks", () => {
    const { update, svg } = mount({ events: [{ minute: 10 }, { minute: 20 }] });
    expect(svg.selectAll("g.scrub-density line").size()).toBe(2);

    update({ events: [{ minute: 5 }, { minute: 15 }, { minute: 25 }] });
    expect(svg.selectAll("g.scrub-density line").size()).toBe(3);
  });

  it("density ticks ignore events without a numeric minute field", () => {
    const { svg } = mount({ events: [{ minute: 10 }, { notMinute: 20 }, { minute: "20" }] });
    expect(svg.selectAll("g.scrub-density line").size()).toBe(1);
  });
});
