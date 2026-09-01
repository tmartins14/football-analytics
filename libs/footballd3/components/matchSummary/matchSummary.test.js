import { describe, expect, it } from "vitest";
import * as d3 from "d3";

import { createMatchSummary } from "./matchSummary.js";

function baseData(overrides = {}) {
  return {
    outcome: {
      headline: "Spain edged England 2-1 in the Euro 2024 final.",
      key_stats: [
        { label: "Final Score", value: "Spain 2 - 1 England", source_field: "match_stats.home.score" },
        { label: "Shots", value: "Spain 16 - England 9", source_field: "match_stats.rows[0]" },
      ],
      standout_performers: [
        { player: "Aymeric Laporte", team: "Spain", reason: "Led the buildup.", source_field: "pass_network.home.windows[0].nodes[0].passes" },
      ],
    },
    tactics: { prose: "Paragraph one.\n\nParagraph two." },
    metadata: { match_label: "Spain vs England", competition: "UEFA Euro 2024", model: "claude-sonnet-5" },
    ...overrides,
  };
}

function mount(data, config) {
  document.body.innerHTML = '<div id="test-container"></div>';
  return createMatchSummary(d3.select("#test-container"), data, config);
}

describe("createMatchSummary", () => {
  it("renders the headline text", () => {
    const { container } = mount(baseData());
    expect(container.select(".match-summary-headline").text()).toBe(
      "Spain edged England 2-1 in the Euro 2024 final."
    );
  });

  it("renders one stat card per key_stats entry with correct label/value/title", () => {
    const { container } = mount(baseData());
    const cards = container.selectAll(".match-summary-stat-card");
    expect(cards.size()).toBe(2);

    const first = d3.select(cards.nodes()[0]);
    expect(first.select(".match-summary-stat-label").text()).toBe("Final Score");
    expect(first.select(".match-summary-stat-value").text()).toBe("Spain 2 - 1 England");
    expect(first.attr("title")).toBe("match_stats.home.score");
  });

  it("renders one row per standout_performers entry with player/team/reason", () => {
    const { container } = mount(baseData());
    const rows = container.selectAll(".match-summary-performer-row");
    expect(rows.size()).toBe(1);

    const row = d3.select(rows.nodes()[0]);
    expect(row.select(".match-summary-performer-name").text()).toBe("Aymeric Laporte");
    expect(row.select(".match-summary-performer-team").text()).toBe("(Spain)");
    expect(row.select(".match-summary-performer-reason").text()).toBe("Led the buildup.");
    expect(row.attr("title")).toBe("pass_network.home.windows[0].nodes[0].passes");
  });

  it.each([
    ["no separator", "Just one paragraph.", 1],
    ["one separator", "Paragraph one.\n\nParagraph two.", 2],
    ["two separators (real-data shape)", "P1.\n\nP2.\n\nP3.", 3],
  ])("splits tactics.prose into <p> tags: %s", (_label, prose, expectedCount) => {
    const { container } = mount(baseData({ tactics: { prose } }));
    expect(container.selectAll(".match-summary-tactics-p").size()).toBe(expectedCount);
  });

  it("renders the disclaimer before the headline in DOM order", () => {
    const { container } = mount(baseData());
    const children = container.node().children;
    const disclaimerIdx = [...children].findIndex((el) => el.classList.contains("match-summary-disclaimer"));
    const headlineIdx = [...children].findIndex((el) => el.classList.contains("match-summary-headline"));
    expect(disclaimerIdx).toBeGreaterThanOrEqual(0);
    expect(headlineIdx).toBeGreaterThan(disclaimerIdx);
  });

  it("disclaimer names the three specific known issues, not a generic notice", () => {
    const { container } = mount(baseData());
    const text = container.select(".match-summary-disclaimer").node().textContent;

    expect(text).toMatch(/off-ball/i);
    expect(text).toMatch(/on-ball/i);
    expect(text).toMatch(/England sat more central than Spain/i);
    expect(text).toMatch(/Stones/i);
    expect(text).toMatch(/Guehi/i);

    // Guards against someone later genericizing the disclaimer away —
    // exactly three named issues, not zero and not a vague catch-all.
    expect(container.selectAll(".match-summary-disclaimer-issues li").size()).toBe(3);
  });

  it("disclaimer states plainly that no automated evaluation exists yet", () => {
    const { container } = mount(baseData());
    const text = container.select(".match-summary-disclaimer").node().textContent;
    expect(text).toMatch(/no automated evaluation/i);
    expect(text).toMatch(/Module 3/i);
  });

  it("renders the footer caption from metadata", () => {
    const { container } = mount(baseData());
    expect(container.select(".match-summary-footer").text()).toBe(
      "Spain vs England · UEFA Euro 2024 · model: claude-sonnet-5"
    );
  });

  it("update({data}) re-renders with new headline/stats, merged over previous data", () => {
    const { container, update } = mount(baseData());
    expect(container.select(".match-summary-headline").text()).toBe(
      "Spain edged England 2-1 in the Euro 2024 final."
    );

    update({
      data: {
        outcome: {
          headline: "Updated headline.",
          key_stats: [],
          standout_performers: [],
        },
      },
    });

    expect(container.select(".match-summary-headline").text()).toBe("Updated headline.");
    expect(container.selectAll(".match-summary-stat-card").size()).toBe(0);
    // metadata wasn't in the update payload — merge keeps the previous value.
    expect(container.select(".match-summary-footer").text()).toBe(
      "Spain vs England · UEFA Euro 2024 · model: claude-sonnet-5"
    );
  });

  it("defaults to light-mode colors when no theme is given", () => {
    const { container } = mount(baseData());
    expect(container.select(".match-summary-disclaimer").style("border")).toContain("rgb(159, 18, 57)"); // #9F1239
    expect(container.select(".match-summary-headline").style("color")).toBe("rgb(23, 23, 23)"); // #171717
  });

  it("config.theme overrides the default colors", () => {
    const { container } = mount(baseData(), {
      theme: { text: "#F5F0E6", focal: "#F43F5E" },
    });
    expect(container.select(".match-summary-headline").style("color")).toBe("rgb(245, 240, 230)"); // #F5F0E6
    expect(container.select(".match-summary-disclaimer").style("border")).toContain("rgb(244, 63, 94)"); // #F43F5E
  });

  it("update({theme}) re-renders with new theme colors without needing new data", () => {
    const { container, update } = mount(baseData());
    expect(container.select(".match-summary-headline").style("color")).toBe("rgb(23, 23, 23)"); // #171717

    update({ theme: { text: "#F5F0E6" } });

    expect(container.select(".match-summary-headline").style("color")).toBe("rgb(245, 240, 230)"); // #F5F0E6
    // Data is untouched — the headline text itself didn't change, only its color.
    expect(container.select(".match-summary-headline").text()).toBe(
      "Spain edged England 2-1 in the Euro 2024 final."
    );
  });
});
