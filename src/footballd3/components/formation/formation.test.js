import { describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { createFormation } from "./formation.js";

function makeData() {
  return {
    periods: [
      {
        formation: "4-3-3",
        from_minute: 0,
        to_minute: 90,
        players: [
          {
            player_id: 1, player: "Test Keeper", display_name: "Test Keeper",
            jersey_number: 1, position: "Goalkeeper", template_x: 6, template_y: 40,
          },
          {
            player_id: 2, player: "Test Defender", display_name: "Test Defender",
            jersey_number: 4, position: "Center Back", template_x: 20, template_y: 40,
          },
        ],
      },
    ],
    metadata: {
      match_id: 1, team: "Test", competition: "Test",
      match_label: "Test", coordinate_note: "",
    },
  };
}

function makeBench() {
  return [
    { player_id: 10, display_name: "Sub Keeper", jersey_number: 13, position: "Goalkeeper", on_minute: 80 },
    { player_id: 11, display_name: "Sub Forward", jersey_number: 19, position: "Center Forward", on_minute: 60 },
  ];
}

function mount(config = {}, data = makeData()) {
  document.body.innerHTML = '<svg id="test-svg"></svg>';
  const svg = d3.select("#test-svg");
  const result = createFormation(svg, data, config);
  return { svg, ...result };
}

describe("createFormation onPlayerClick", () => {
  it("fires for a non-goalkeeper marker with the correct player record", () => {
    const onPlayerClick = vi.fn();
    const { svg } = mount({ onPlayerClick });

    const markers = svg.selectAll("g.fm-player").nodes();
    expect(markers.length).toBe(2);

    const defenderMarker = markers[1]; // second player in the input array
    defenderMarker.dispatchEvent(new Event("click", { bubbles: true }));

    expect(onPlayerClick).toHaveBeenCalledTimes(1);
    expect(onPlayerClick.mock.calls[0][0].display_name).toBe("Test Defender");
  });

  it("does not fire for the goalkeeper marker, and its cursor is default", () => {
    const onPlayerClick = vi.fn();
    const { svg } = mount({ onPlayerClick });

    const gkMarker = svg.selectAll("g.fm-player").nodes()[0];
    expect(gkMarker.style.cursor).toBe("default");

    gkMarker.dispatchEvent(new Event("click", { bubbles: true }));
    expect(onPlayerClick).not.toHaveBeenCalled();
  });

  it("outfield marker cursor is pointer when onPlayerClick is provided", () => {
    const { svg } = mount({ onPlayerClick: vi.fn() });
    const defenderMarker = svg.selectAll("g.fm-player").nodes()[1];
    expect(defenderMarker.style.cursor).toBe("pointer");
  });

  it("no click handler and default cursor when onPlayerClick is omitted", () => {
    const { svg } = mount({});
    const defenderMarker = svg.selectAll("g.fm-player").nodes()[1];
    expect(defenderMarker.style.cursor).toBe("default");
    // Dispatching a click must not throw even with no handler attached.
    expect(() => defenderMarker.dispatchEvent(new Event("click", { bubbles: true }))).not.toThrow();
  });
});

describe("createFormation selection ring", () => {
  it("shows the ring only on the node matching selectedId", () => {
    const { svg } = mount({ selectedId: 2 });
    const rings = svg.selectAll(".fm-selected-ring");
    expect(rings.size()).toBe(1);
  });

  it("no ring when selectedId is null", () => {
    const { svg } = mount({ selectedId: null });
    expect(svg.selectAll(".fm-selected-ring").size()).toBe(0);
  });

  it("update({selectedId}) moves the ring without needing new data", () => {
    const { svg, update } = mount({ selectedId: null });
    expect(svg.selectAll(".fm-selected-ring").size()).toBe(0);

    update({ selectedId: 2 });
    expect(svg.selectAll(".fm-selected-ring").size()).toBe(1);
  });

  it("selected node's own circle stroke switches to selectedColor (regression: G3)", () => {
    const { svg } = mount({ selectedId: 2, selectedColor: "#9F1239", backgroundColor: "#FAF7F0" });
    const nodes = svg.selectAll("g.fm-player").nodes();
    const selectedCircle = d3.select(nodes[1]).select("circle:not(.fm-selected-ring)");
    const unselectedCircle = d3.select(nodes[0]).select("circle:not(.fm-selected-ring)");

    expect(selectedCircle.attr("stroke")).toBe("#9F1239");
    expect(+selectedCircle.attr("stroke-width")).toBe(2);
    expect(unselectedCircle.attr("stroke")).toBe("#FAF7F0");
    expect(+unselectedCircle.attr("stroke-width")).toBe(1.5);
  });
});

describe("createFormation bench (optional)", () => {
  it("renders no bench group content when data.bench is omitted", () => {
    const { svg } = mount({});
    expect(svg.selectAll(".fm-bench-row").size()).toBe(0);
  });

  it("renders one row per bench player when data.bench is provided", () => {
    const data = { ...makeData(), bench: makeBench() };
    const { svg } = mount({}, data);
    expect(svg.selectAll(".fm-bench-row").size()).toBe(2);
  });

  it("fires onPlayerClick for a non-goalkeeper bench row", () => {
    const onPlayerClick = vi.fn();
    const data = { ...makeData(), bench: makeBench() };
    const { svg } = mount({ onPlayerClick }, data);

    const forwardRow = svg.selectAll(".fm-bench-row").filter(d => d.player_id === 11);
    forwardRow.dispatch("click");

    expect(onPlayerClick).toHaveBeenCalledWith(expect.objectContaining({ player_id: 11 }));
  });

  it("does not fire onPlayerClick for a goalkeeper bench row, and its cursor is default", () => {
    const onPlayerClick = vi.fn();
    const data = { ...makeData(), bench: makeBench() };
    const { svg } = mount({ onPlayerClick }, data);

    const keeperRow = svg.selectAll(".fm-bench-row").filter(d => d.player_id === 10);
    expect(keeperRow.style("cursor")).toBe("default");

    keeperRow.dispatch("click");
    expect(onPlayerClick).not.toHaveBeenCalled();
  });

  it("shows the bench ring only on the row matching selectedId", () => {
    const data = { ...makeData(), bench: makeBench() };
    const { svg } = mount({ selectedId: 11 }, data);

    const visibleRings = svg.selectAll(".fm-bench-ring").filter(function () {
      return d3.select(this).style("display") !== "none";
    });
    expect(visibleRings.size()).toBe(1);
  });

  it("fills the selected bench row's background and recolors its text (regression: G4)", () => {
    const data = { ...makeData(), bench: makeBench() };
    const { svg } = mount({ selectedId: 11, selectedColor: "#9F1239", nodeColor: "#1E3A5F", labelColor: "#171717" }, data);

    const selectedRow = svg.selectAll(".fm-bench-row").filter(d => d.player_id === 11);
    const ring = selectedRow.select(".fm-bench-ring");
    expect(ring.style("display")).not.toBe("none");
    expect(ring.attr("fill")).toBe("#9F1239");
    expect(+ring.attr("fill-opacity")).toBeCloseTo(0.13, 5);

    const texts = selectedRow.selectAll("text").nodes();
    texts.forEach((node) => expect(node.getAttribute("fill")).toBe("#9F1239"));

    const unselectedRow = svg.selectAll(".fm-bench-row").filter(d => d.player_id === 10);
    expect(unselectedRow.select(".fm-bench-ring").style("display")).toBe("none");
  });

  it("shows the hover fill on mouseenter and hides it on mouseleave, except for the selected row", () => {
    const data = { ...makeData(), bench: makeBench() };
    const { svg } = mount({ selectedId: 11 }, data);

    const unselectedRow = svg.selectAll(".fm-bench-row").filter(d => d.player_id === 10);
    const hover = unselectedRow.select(".fm-bench-hover");
    expect(hover.style("display")).toBe("none");
    unselectedRow.dispatch("mouseenter");
    expect(hover.style("display")).not.toBe("none");
    unselectedRow.dispatch("mouseleave");
    expect(hover.style("display")).toBe("none");

    // The already-selected row's hover rect never shows — its permanent
    // .fm-bench-ring fill already communicates the same state.
    const selectedRow = svg.selectAll(".fm-bench-row").filter(d => d.player_id === 11);
    selectedRow.dispatch("mouseenter");
    expect(selectedRow.select(".fm-bench-hover").style("display")).toBe("none");
  });

  it("grows the SVG height to fit the bench, and shrinks back when bench is removed", () => {
    const withBench = { ...makeData(), bench: makeBench() };
    const { svg: svgWithBench } = mount({}, withBench);
    const { svg: svgWithoutBench } = mount({}, makeData());

    expect(+svgWithBench.attr("height")).toBeGreaterThan(+svgWithoutBench.attr("height"));
  });
});
