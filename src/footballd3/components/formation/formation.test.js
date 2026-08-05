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

function mount(config = {}) {
  document.body.innerHTML = '<svg id="test-svg"></svg>';
  const svg = d3.select("#test-svg");
  createFormation(svg, makeData(), config);
  return svg;
}

describe("createFormation onPlayerClick", () => {
  it("fires for a non-goalkeeper marker with the correct player record", () => {
    const onPlayerClick = vi.fn();
    const svg = mount({ onPlayerClick });

    const markers = svg.selectAll("g.fm-player").nodes();
    expect(markers.length).toBe(2);

    const defenderMarker = markers[1]; // second player in the input array
    defenderMarker.dispatchEvent(new Event("click", { bubbles: true }));

    expect(onPlayerClick).toHaveBeenCalledTimes(1);
    expect(onPlayerClick.mock.calls[0][0].display_name).toBe("Test Defender");
  });

  it("does not fire for the goalkeeper marker, and its cursor is default", () => {
    const onPlayerClick = vi.fn();
    const svg = mount({ onPlayerClick });

    const gkMarker = svg.selectAll("g.fm-player").nodes()[0];
    expect(gkMarker.style.cursor).toBe("default");

    gkMarker.dispatchEvent(new Event("click", { bubbles: true }));
    expect(onPlayerClick).not.toHaveBeenCalled();
  });

  it("outfield marker cursor is pointer when onPlayerClick is provided", () => {
    const svg = mount({ onPlayerClick: vi.fn() });
    const defenderMarker = svg.selectAll("g.fm-player").nodes()[1];
    expect(defenderMarker.style.cursor).toBe("pointer");
  });

  it("no click handler and default cursor when onPlayerClick is omitted", () => {
    const svg = mount({});
    const defenderMarker = svg.selectAll("g.fm-player").nodes()[1];
    expect(defenderMarker.style.cursor).toBe("default");
    // Dispatching a click must not throw even with no handler attached.
    expect(() => defenderMarker.dispatchEvent(new Event("click", { bubbles: true }))).not.toThrow();
  });
});
