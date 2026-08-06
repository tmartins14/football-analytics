import { describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { createLineupSelector } from "./lineupSelector.js";

function makeTeamFormation(team, players) {
  return { team, periods: [{ formation: "4-4-2", from_minute: 0, to_minute: 90, players }] };
}

function makeData() {
  const topTeam = makeTeamFormation("England", [
    { player_id: 1, display_name: "Test Keeper", jersey_number: 1, position: "Goalkeeper", template_x: 6, template_y: 40 },
    { player_id: 2, display_name: "Test Defender", jersey_number: 4, position: "Center Back", template_x: 20, template_y: 40 },
  ]);
  const bottomTeam = makeTeamFormation("Spain", [
    { player_id: 3, display_name: "Otro Portero", jersey_number: 1, position: "Goalkeeper", template_x: 6, template_y: 40 },
    { player_id: 4, display_name: "Otro Delantero", jersey_number: 9, position: "Center Forward", template_x: 100, template_y: 40 },
  ]);
  const bench = {
    teams: {
      England: [{ player_id: 5, display_name: "Sub One", jersey_number: 17, on_minute: 60 }],
      Spain: [{ player_id: 6, display_name: "Sub Dos", jersey_number: 20, on_minute: 70 }],
    },
  };
  return { top: topTeam, bottom: bottomTeam, bench };
}

function mount(config = {}) {
  document.body.innerHTML = '<svg id="test-svg"></svg>';
  const svg = d3.select("#test-svg");
  const result = createLineupSelector(svg, makeData(), config);
  return { svg, ...result };
}

describe("createLineupSelector", () => {
  it("renders one node per starter across both teams", () => {
    const { svg } = mount();
    expect(svg.selectAll("g.ls-player").size()).toBe(4);
  });

  it("fires onSelect for a non-goalkeeper starter with its player_id and team", () => {
    const onSelect = vi.fn();
    const { svg } = mount({ onSelect });

    const forward = svg.selectAll("g.ls-player").filter((d) => d.player_id === 4);
    forward.dispatch("click");

    expect(onSelect).toHaveBeenCalledWith(4, "Spain");
  });

  it("does not fire onSelect for a goalkeeper node, and its cursor is default", () => {
    const onSelect = vi.fn();
    const { svg } = mount({ onSelect });

    const keeper = svg.selectAll("g.ls-player").filter((d) => d.player_id === 1);
    expect(keeper.style("cursor")).toBe("default");

    keeper.dispatch("click");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("renders both bench columns with the correct row counts", () => {
    const { svg } = mount();
    expect(svg.selectAll("g.ls-bench-row").size()).toBe(2);
  });

  it("fires onSelect for a bench row click", () => {
    const onSelect = vi.fn();
    const { svg } = mount({ onSelect });
    const subRow = svg.selectAll("g.ls-bench-row").filter((d) => d.player_id === 5);
    subRow.dispatch("click");
    expect(onSelect).toHaveBeenCalledWith(5, "England");
  });

  it("shows the selection ring only on the node matching selectedId", () => {
    const { svg } = mount({ selectedId: 4 });
    const visibleRings = () =>
      svg.selectAll(".ls-ring").filter(function () { return d3.select(this).style("display") !== "none"; }).size();
    expect(visibleRings()).toBe(1);
  });

  it("update({selectedId}) moves the ring without re-fetching geometry", () => {
    const { svg, update } = mount({ selectedId: null });
    const visibleRings = () =>
      svg.selectAll(".ls-ring").filter(function () { return d3.select(this).style("display") !== "none"; }).size();
    expect(visibleRings()).toBe(0);

    update({ selectedId: 2 });
    expect(visibleRings()).toBe(1);
  });

  it("update({selectedId}) also moves the bench ring", () => {
    const { svg, update } = mount({ selectedId: null });
    update({ selectedId: 6 });
    const benchRing = svg.selectAll(".ls-bench-ring")
      .filter(function (d) { return d.player_id === 6; });
    expect(benchRing.style("display")).not.toBe("none");
  });

  it("uses the last token of display_name as the surname label", () => {
    const { svg } = mount();
    const forwardLabel = svg.selectAll("g.ls-player").filter((d) => d.player_id === 4)
      .selectAll("text").nodes().map((n) => n.textContent);
    expect(forwardLabel).toContain("Delantero");
  });
});
