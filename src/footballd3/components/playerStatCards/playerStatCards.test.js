import { describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { createPlayerStatCards } from "./playerStatCards.js";

function mount(events, summary, config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createPlayerStatCards(d3.select("#test-container"), { events, summary }, config);
}

function cardValue(container, label) {
  return container.selectAll(".stat-card")
    .filter(function (d) { return d.label === label; })
    .select(".stat-card-value")
    .text();
}

describe("createPlayerStatCards", () => {
  it("renders exactly six cards", () => {
    const { container } = mount([], null);
    expect(container.selectAll(".stat-card").size()).toBe(6);
  });

  it("counts progressive passes from the event slice", () => {
    const events = [
      { type: "Pass", is_progressive: true },
      { type: "Pass", is_progressive: false },
      { type: "Carry", is_progressive: true }, // not a Pass — excluded
    ];
    const { container } = mount(events, null);
    expect(cardValue(container, "PROGRESSIVE PASSES")).toBe("1");
  });

  it("sums shot_xg across Shot events", () => {
    const events = [
      { type: "Shot", shot_xg: 0.1 },
      { type: "Shot", shot_xg: 0.25 },
    ];
    const { container } = mount(events, null);
    expect(cardValue(container, "xG")).toBe("0.35");
  });

  it("counts pressure_regain among Pressure events", () => {
    const events = [
      { type: "Pressure", pressure_regain: true },
      { type: "Pressure", pressure_regain: false },
    ];
    const { container } = mount(events, null);
    expect(cardValue(container, "PRESSURES + REGAINS")).toBe("1");
  });

  it("computes duels won % from winning outcomes", () => {
    const events = [
      { type: "Duel", outcome: "Won" },
      { type: "Duel", outcome: "Success In Play" },
      { type: "Duel", outcome: "Lost Out" },
      { type: "Duel", outcome: "Lost In Play" },
    ];
    const { container } = mount(events, null);
    expect(cardValue(container, "DUELS WON %")).toBe("50%");
  });

  it("shows an em dash for duels won % with zero duels", () => {
    const { container } = mount([], null);
    expect(cardValue(container, "DUELS WON %")).toBe("—");
  });

  it("xA/xGChain and PAdj come from the summary prop, not the event slice", () => {
    const summary = { xa: 0.12, xg_chain: 0.65, padj_defensive_actions: 8.4 };
    const { container } = mount([], summary);
    expect(cardValue(container, "xA / xG CHAIN")).toBe("0.12 / 0.65");
    expect(cardValue(container, "PADJ DEFENSIVE ACTIONS")).toBe("8.4");
  });

  it("hovering a card fires onHover with its layer, mouseout fires null", () => {
    const onHover = vi.fn();
    const { container } = mount([], null, { onHover });
    const xgCard = container.selectAll(".stat-card").filter((d) => d.key === "xg");
    xgCard.dispatch("mouseover");
    expect(onHover).toHaveBeenCalledWith("shot");
    xgCard.dispatch("mouseout");
    expect(onHover).toHaveBeenLastCalledWith(null);
  });

  it("update({data}) recomputes reactive cards for a new event slice", () => {
    const { container, update } = mount([{ type: "Shot", shot_xg: 0.1 }], null);
    expect(cardValue(container, "xG")).toBe("0.10");

    update({ data: { events: [{ type: "Shot", shot_xg: 0.1 }, { type: "Shot", shot_xg: 0.4 }], summary: null } });
    expect(cardValue(container, "xG")).toBe("0.50");
  });
});
