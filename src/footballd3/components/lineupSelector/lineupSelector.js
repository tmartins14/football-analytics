/**
 * lineupSelector.js — dual-team selectable formation + bench, on one pitch.
 *
 * formation.js renders ONE team's declared shape across the FULL pitch
 * length (template_x spans the whole 0-120 attacking axis) — correct for a
 * single-team diagram, but two formation.js instances can't share one pitch
 * without overlapping at midfield. This component instead creates a single
 * full vertical pitch (via pitch.js) and compresses each team's own
 * template_x (0=own goal, 120=opponent goal) into HALF of the shared
 * pitch's length, so both teams' shapes meet at the halfway line instead of
 * overlapping:
 *
 *   topTeam:    fieldX = (template_x / 120) * 60           -> range [0, 60]
 *   bottomTeam: fieldX = 120 - (template_x / 120) * 60      -> range [60, 120]
 *
 * With the pitch's default (non-flipped) vertical orientation, increasing
 * fieldX moves DOWN the screen — so topTeam's keeper (template_x=0) sits at
 * the very top (fieldX=0) attacking down toward the halfway line
 * (fieldX=60), and bottomTeam's keeper sits at the very bottom (fieldX=120)
 * attacking up toward the halfway line (fieldX=60) — exactly the "both
 * teams meet at midfield, attacking toward each other" layout the design
 * calls for, using pitch.js's existing px() unchanged (no flipAttack, no
 * pitch.js modification).
 *
 * template_y (0-80, lateral position) is used as-is for both teams — no
 * compression needed on that axis.
 *
 * GOALKEEPERS ARE NEVER SELECTABLE
 * Matches formation.js's own rule, for a stronger reason here: this whole
 * feature's data pipeline (extract_substitutes.get_eligible_players,
 * extract_player_events.py, extract_player_match_summary.py) explicitly
 * excludes goalkeepers as "not eligible" — no player_events/summary file
 * exists for one. Making a keeper node clickable would select a player with
 * no data to show.
 */

import * as d3 from "d3";
import { createPitch } from "../pitch/pitch.js";

const NODE_R = 13;

let _tooltip;
function getTooltip() {
  if (!_tooltip) {
    _tooltip = document.createElement("div");
    Object.assign(_tooltip.style, {
      position: "fixed", pointerEvents: "none", display: "none",
      background: "#FAF7F0", border: "1px solid #E5E5E5", borderRadius: "2px",
      padding: "8px 10px", fontFamily: "Geist Mono, monospace", fontSize: "12px",
      lineHeight: "1.6", color: "#171717", whiteSpace: "nowrap", zIndex: "1000",
    });
    document.body.appendChild(_tooltip);
  }
  return _tooltip;
}

/**
 * Last whitespace-separated token of a display name.
 *
 * @param {string} displayName - Full/nickname display name.
 * @returns {string} The surname heuristic used under pitch nodes and in the
 *   bench list — the simple last-token rule used throughout this app rather
 *   than a full name-parsing library, since StatsBomb display names are
 *   already resolved to a single conventional football-shirt name.
 */
function surname(displayName) {
  const parts = String(displayName).trim().split(/\s+/);
  return parts[parts.length - 1];
}

/**
 * Compress one team's template_x into their half of the shared pitch.
 *
 * @param {number} templateX - StatsBomb-space template_x (0-120, that
 *   team's own attacking axis).
 * @param {"top"|"bottom"} half - Which half of the shared pitch this team
 *   occupies.
 * @returns {number} fieldX in the shared pitch's 0-120 coordinate space.
 */
function compressFieldX(templateX, half) {
  const scaled = (templateX / 120) * 60;
  return half === "top" ? scaled : 120 - scaled;
}

/**
 * Render a dual-team selectable lineup (formation + bench) on one pitch.
 *
 * @param {d3.Selection} selection - SVG element to render into.
 * @param {Object} data - `{ top, bottom, bench }`.
 * @param {Object} data.top - `{ team, periods }` — formation.js's own
 *   contract (see extract_formation.py) for the team drawn in the top half,
 *   attacking down toward the halfway line. Only `periods[0]` (Starting XI)
 *   is used.
 * @param {Object} data.bottom - Same shape as `data.top`, for the team drawn
 *   in the bottom half, attacking up toward the halfway line.
 * @param {Object} data.bench - `{ teams: { [teamName]: [...] } }` —
 *   extract_substitutes.py's own contract, keyed by each team's `team` name
 *   (must match `data.top.team` / `data.bottom.team`).
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {number}  [config.pxPerYard=4.4]        - Pixels per StatsBomb yard.
 * @param {number}  [config.padding=20]           - Padding around the pitch in pixels.
 * @param {string|Object} [config.theme="whiteboard"] - Pitch theme.
 * @param {string}  [config.topColor="#1E3A5F"]    - Top team node fill color.
 * @param {string}  [config.bottomColor="#9F1239"] - Bottom team node fill color.
 * @param {string}  [config.labelColor="#171717"]  - Surname/bench label color.
 * @param {string}  [config.selectedColor="#F59E0B"] - Active-selection ring color.
 * @param {number|null} [config.selectedId=null]   - Currently selected player_id.
 * @param {Function|null} [config.onSelect=null]    - onSelect(playerId, team)
 *   fires on any non-goalkeeper starter node or bench row click.
 * @returns {{ svg: d3.Selection, g: d3.Selection, update: Function }}
 *   svg — the SVG element.
 *   g   — the pitch group; the bench list is a sibling `<g>` below it.
 *   update({ selectedId? }) — move the active-selection ring without a full
 *     re-render of formation/bench geometry.
 */
export function createLineupSelector(selection, data, config = {}) {
  const {
    pxPerYard      = 4.4,
    padding        = 20,
    theme          = "whiteboard",
    topColor       = "#1E3A5F",
    bottomColor    = "#9F1239",
    labelColor     = "#171717",
    selectedColor  = "#F59E0B",
    onSelect       = null,
  } = config;
  let { selectedId = null } = config;

  const pitch = createPitch(selection, {
    mode: "full", orientation: "vertical", pxPerYard, padding, theme, showGoals: true,
  });
  const { svg, g, px, width, height, config: pitchCfg } = pitch;

  const pad = pitchCfg.padding;
  const bounds = {
    minX: pad + NODE_R, maxX: width - pad - NODE_R,
    minY: pad + NODE_R, maxY: height - pad - NODE_R,
  };

  const nodesLayer = g.append("g").attr("class", "ls-nodes");
  const benchLayer = svg.append("g")
    .attr("class", "ls-bench")
    .attr("transform", `translate(0, ${height + 16})`);

  const teamOf = { top: data.top.team, bottom: data.bottom.team };
  const colorOf = { [data.top.team]: topColor, [data.bottom.team]: bottomColor };

  function starterNodes() {
    const top = (data.top.periods?.[0]?.players ?? []).map((p) => ({
      ...p, team: data.top.team, half: "top",
    }));
    const bottom = (data.bottom.periods?.[0]?.players ?? []).map((p) => ({
      ...p, team: data.bottom.team, half: "bottom",
    }));
    return [...top, ...bottom];
  }

  function renderNodes() {
    nodesLayer.selectAll("*").remove();

    const players = nodesLayer.selectAll(".ls-player")
      .data(starterNodes(), (d) => d.player_id)
      .join("g")
      .attr("class", "ls-player")
      .style("cursor", (d) => (d.position === "Goalkeeper" ? "default" : "pointer"));

    players.each(function (d) {
      const fieldX = compressFieldX(d.template_x, d.half);
      const [rawCx, rawCy] = px(fieldX, d.template_y);
      const cx = Math.max(bounds.minX, Math.min(bounds.maxX, rawCx));
      const cy = Math.max(bounds.minY, Math.min(bounds.maxY, rawCy));
      d3.select(this).attr("data-cx", cx).attr("data-cy", cy);

      const node = d3.select(this);
      node.append("circle")
        .attr("class", "ls-ring")
        .attr("cx", cx).attr("cy", cy).attr("r", NODE_R + 4)
        .attr("fill", "none").attr("stroke", selectedColor).attr("stroke-width", 2.5)
        .style("display", d.player_id === selectedId ? null : "none");

      node.append("circle")
        .attr("cx", cx).attr("cy", cy).attr("r", NODE_R)
        .attr("fill", colorOf[d.team])
        .attr("stroke", "#FAF7F0").attr("stroke-width", 1.5);

      node.append("text")
        .attr("x", cx).attr("y", cy).attr("dy", "0.36em")
        .attr("text-anchor", "middle")
        .attr("font-family", "Geist Mono, monospace")
        .attr("font-size", Math.max(9, NODE_R * 0.8))
        .attr("font-weight", "600").attr("fill", "#FAF7F0")
        .attr("pointer-events", "none")
        .text(d.jersey_number);

      node.append("text")
        .attr("x", cx).attr("y", cy + NODE_R + 9)
        .attr("text-anchor", "middle")
        .attr("font-family", "Geist, sans-serif")
        .attr("font-size", "9px").attr("fill", labelColor)
        .attr("pointer-events", "none")
        .text(surname(d.display_name));
    });

    players
      .filter((d) => d.position !== "Goalkeeper")
      .on("click", (event, d) => onSelect && onSelect(d.player_id, d.team))
      .on("mouseover", (event, d) => {
        const tooltip = getTooltip();
        tooltip.innerHTML =
          `<span style="font-weight:600">${d.display_name}</span><br>` +
          `#${d.jersey_number} &middot; ${d.position}`;
        tooltip.style.display = "block";
      })
      .on("mousemove", (event) => {
        const tooltip = getTooltip();
        tooltip.style.left = (event.clientX + 14) + "px";
        tooltip.style.top = (event.clientY - 28) + "px";
      })
      .on("mouseout", () => getTooltip().style.display = "none");
  }

  function renderBench() {
    benchLayer.selectAll("*").remove();

    benchLayer.append("line")
      .attr("x1", padding).attr("x2", width - padding).attr("y1", 0).attr("y2", 0)
      .attr("stroke", "#E5E5E5").attr("stroke-width", 1);

    const columnWidth = (width - padding * 2) / 2;
    const columns = [
      { team: teamOf.bottom, x: padding },
      { team: teamOf.top, x: padding + columnWidth },
    ];

    columns.forEach(({ team, x }) => {
      const subs = data.bench?.teams?.[team] ?? [];
      const col = benchLayer.append("g").attr("transform", `translate(${x}, 14)`);

      const rows = col.selectAll(".ls-bench-row")
        .data(subs, (d) => d.player_id)
        .join("g")
        .attr("class", "ls-bench-row")
        .attr("transform", (d, i) => `translate(0, ${i * 22})`)
        .style("cursor", "pointer");

      rows.append("rect")
        .attr("class", "ls-bench-ring")
        .attr("x", -4).attr("y", -12).attr("width", columnWidth - 12).attr("height", 20)
        .attr("rx", 4)
        .attr("fill", "none").attr("stroke", selectedColor).attr("stroke-width", 2)
        .style("display", (d) => (d.player_id === selectedId ? null : "none"));

      rows.append("text")
        .attr("font-family", "Geist Mono, monospace").attr("font-size", "11px")
        .attr("fill", colorOf[team]).attr("font-weight", "600")
        .text((d) => `#${d.jersey_number}`);

      rows.append("text")
        .attr("x", 34)
        .attr("font-family", "Geist, sans-serif").attr("font-size", "11px")
        .attr("fill", labelColor)
        .text((d) => surname(d.display_name));

      rows.append("text")
        .attr("x", columnWidth - 16).attr("text-anchor", "end")
        .attr("font-family", "Geist Mono, monospace").attr("font-size", "10px")
        .attr("fill", "#8A8578")
        .text((d) => `on ${d.on_minute}'`);

      rows.on("click", (event, d) => onSelect && onSelect(d.player_id, team));
    });
  }

  function renderSelection() {
    nodesLayer.selectAll(".ls-ring")
      .style("display", function () {
        const d = d3.select(this.parentNode).datum();
        return d.player_id === selectedId ? null : "none";
      });
    benchLayer.selectAll(".ls-bench-ring")
      .style("display", function () {
        const d = d3.select(this.parentNode).datum();
        return d.player_id === selectedId ? null : "none";
      });
  }

  renderNodes();
  renderBench();

  /**
   * Move the active-selection ring without a full re-render of
   * formation/bench geometry.
   *
   * @param {Object} [next={}] - Partial update.
   * @param {number|null} [next.selectedId] - New selected player_id.
   */
  function update(next = {}) {
    if (next.selectedId !== undefined) {
      selectedId = next.selectedId;
      renderSelection();
    }
  }

  return { svg, g, update };
}
