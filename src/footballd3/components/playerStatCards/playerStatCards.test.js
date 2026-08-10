import { describe, expect, it, vi } from "vitest";
import * as d3 from "d3";

import { createPlayerStatCards } from "./playerStatCards.js";

const POSSESSION_SHARES = {
  buckets: [
    { upto_minute: 5, team_possession_pct: { Spain: 60, England: 40 } },
    { upto_minute: 10, team_possession_pct: { Spain: 55, England: 45 } },
  ],
};

function mount(data, config = {}) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createPlayerStatCards(d3.select("#test-container"), data, config);
}

function cardValue(container, label) {
  return container.selectAll(".stat-card")
    .filter(function (d) { return d.label === label; })
    .select(".stat-card-value")
    .text();
}

describe("createPlayerStatCards", () => {
  it("renders exactly six cards", () => {
    const { container } = mount({ events: [] });
    expect(container.selectAll(".stat-card").size()).toBe(6);
  });

  it("counts progressive passes from the event slice", () => {
    const events = [
      { type: "Pass", is_progressive: true },
      { type: "Pass", is_progressive: false },
      { type: "Carry", is_progressive: true }, // not a Pass — excluded
    ];
    const { container } = mount({ events });
    expect(cardValue(container, "PROGRESSIVE PASSES")).toBe("1");
  });

  it("sums shot_xg across Shot events", () => {
    const events = [
      { type: "Shot", shot_xg: 0.1 },
      { type: "Shot", shot_xg: 0.25 },
    ];
    const { container } = mount({ events });
    expect(cardValue(container, "xG")).toBe("0.35");
  });

  it("sums assisted_shot_xg across Pass events for xA", () => {
    const events = [
      { type: "Pass", assisted_shot_xg: 0.12 },
      { type: "Pass", assisted_shot_xg: null },
      { type: "Carry", assisted_shot_xg: 0.5 }, // not a Pass — excluded
    ];
    const { container } = mount({ events });
    expect(cardValue(container, "xA / xG CHAIN")).toBe("0.12 / 0.00");
  });

  it("sums possession_shot_xg once per distinct possession for xGChain", () => {
    const events = [
      { type: "Pass", possession: 1, possession_shot_xg: 0.3 },
      { type: "Carry", possession: 1, possession_shot_xg: 0.3 }, // same possession — not double counted
      { type: "Pass", possession: 2, possession_shot_xg: 0.2 },
    ];
    const { container } = mount({ events });
    expect(cardValue(container, "xA / xG CHAIN")).toBe("0.00 / 0.50");
  });

  it("counts pressure_regain among Pressure events", () => {
    const events = [
      { type: "Pressure", pressure_regain: true },
      { type: "Pressure", pressure_regain: false },
    ];
    const { container } = mount({ events });
    expect(cardValue(container, "PRESSURES + REGAINS")).toBe("1");
  });

  it("computes duels won % from winning outcomes", () => {
    const events = [
      { type: "Duel", outcome: "Won" },
      { type: "Duel", outcome: "Success In Play" },
      { type: "Duel", outcome: "Lost Out" },
      { type: "Duel", outcome: "Lost In Play" },
    ];
    const { container } = mount({ events });
    expect(cardValue(container, "DUELS WON %")).toBe("50%");
  });

  it("shows an em dash for duels won % with zero duels", () => {
    const { container } = mount({ events: [] });
    expect(cardValue(container, "DUELS WON %")).toBe("—");
  });

  it("PAdj defensive actions scales with the opponent's possession share at the scrubbed minute", () => {
    const events = [{ type: "Pressure" }, { type: "Duel" }];
    // At minute 5: England (opponent) has 40% -> scaled up relative to 50% baseline.
    const { container } = mount({
      events, possessionShares: POSSESSION_SHARES, playerTeam: "Spain", scrubbedMinute: 5,
    });
    expect(cardValue(container, "PADJ DEFENSIVE ACTIONS")).toBe("2.5");
  });

  it("PAdj picks the nearest bucket <= scrubbedMinute", () => {
    const events = [{ type: "Duel" }];
    const { container } = mount({
      events, possessionShares: POSSESSION_SHARES, playerTeam: "Spain", scrubbedMinute: 9,
    });
    // Nearest bucket <= 9 is upto_minute 5 (England 40%): 1 / (40/50) = 1.25.
    expect(cardValue(container, "PADJ DEFENSIVE ACTIONS")).toBe("1.3");
  });

  it("shows an em dash for PAdj when possessionShares/playerTeam are absent", () => {
    const { container } = mount({ events: [{ type: "Duel" }] });
    expect(cardValue(container, "PADJ DEFENSIVE ACTIONS")).toBe("—");
  });

  it("hovering a card fires onHover with its layer, mouseout fires null", () => {
    const onHover = vi.fn();
    const { container } = mount({ events: [] }, { onHover });
    const xgCard = container.selectAll(".stat-card").filter((d) => d.key === "xg");
    xgCard.dispatch("mouseover");
    expect(onHover).toHaveBeenCalledWith("shot");
    xgCard.dispatch("mouseout");
    expect(onHover).toHaveBeenLastCalledWith(null);
  });

  it("update({data}) recomputes reactive cards for a new event slice", () => {
    const { container, update } = mount({ events: [{ type: "Shot", shot_xg: 0.1 }] });
    expect(cardValue(container, "xG")).toBe("0.10");

    update({ data: { events: [{ type: "Shot", shot_xg: 0.1 }, { type: "Shot", shot_xg: 0.4 }] } });
    expect(cardValue(container, "xG")).toBe("0.50");
  });

  it("update({data}) merges over previous data, so a bare {events} tick keeps possessionShares/playerTeam", () => {
    const { container, update } = mount({
      events: [{ type: "Duel" }],
      possessionShares: POSSESSION_SHARES,
      playerTeam: "Spain",
      scrubbedMinute: 5,
    });
    expect(cardValue(container, "PADJ DEFENSIVE ACTIONS")).toBe("1.3");

    update({ data: { events: [{ type: "Duel" }, { type: "Pressure" }] } });
    expect(cardValue(container, "PADJ DEFENSIVE ACTIONS")).toBe("2.5");
  });
});
