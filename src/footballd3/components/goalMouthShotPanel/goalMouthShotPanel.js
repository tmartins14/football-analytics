/**
 * goalMouthShotPanel.js — goal-frame view of one player's shots.
 *
 * A goal-frame view, NOT a pitch — distinct from shotMap.js (which plots
 * shot ORIGIN on a half-pitch). This plots shot END point relative to the
 * goal mouth: on-target shots inside the frame, off-target shots in a
 * labelled zone above the crossbar. Radius encodes shot_xg.
 *
 * GOAL FRAME GEOMETRY (StatsBomb 120x80-yard pitch)
 * A regulation goal is 8 yards wide, centered on the pitch's y midpoint (40),
 * so its posts sit at y=36 and y=44. Height is a standard 8ft crossbar,
 * expressed here in StatsBomb's yard units (~2.67yd). These are fixed
 * constants, not read from data — StatsBomb does not vary goal geometry
 * per match.
 *
 * ON-TARGET / OFF-TARGET CLASSIFICATION
 * Uses the Shot event's own `outcome` string (the same field every other
 * panel already reads via extract_player_events.py's outcome column) rather
 * than re-deriving it from shot_end_location's coordinates — StatsBomb's
 * outcome vocabulary is the ground truth for "did this reach the frame":
 *   on-target:  "Goal", "Saved"
 *   off-target: everything else credited as a shot ("Off T", "Post",
 *               "Blocked", "Wayward", ...)
 *
 * OFF-TARGET PLACEMENT IS SYMBOLIC, NOT A TRUE TRAJECTORY PLOT
 * A blocked shot's shot_end_location is the block point (often nowhere near
 * the goal line), and a wide/over shot's end_location is only sometimes a
 * clean goal-line crossing point. Rather than mis-plotting these as if they
 * were precise trajectories, off-target shots are placed in a fixed strip
 * above the crossbar, horizontally positioned by shot_end_location's y
 * (clamped to the strip's width) — "this shot missed, roughly to this side"
 * is the honest claim being made, not "the ball crossed exactly here."
 */

import * as d3 from "d3";

const GOAL_WIDTH_YARDS = 8;
const GOAL_Y_MIN = 36;
const GOAL_Y_MAX = 44;
const CROSSBAR_HEIGHT_YARDS = 2.67;
const OFF_TARGET_STRIP_HEIGHT = 0.9; // yards, visual height of the "off target" zone above the bar
const OFF_TARGET_Y_MIN = 30; // wider than the frame so wide misses have room to spread
const OFF_TARGET_Y_MAX = 50;

const ON_TARGET_OUTCOMES = new Set(["Goal", "Saved"]);

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
 * True when a shot's outcome counts as on-target (reached/entered the frame).
 *
 * @param {Object} shot - One Shot event from the player_events contract.
 * @returns {boolean} True for "Goal"/"Saved"; false for every other outcome.
 */
function isOnTarget(shot) {
  return ON_TARGET_OUTCOMES.has(shot.outcome);
}

/**
 * Render a goal-frame shot panel for one player.
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object} data - Object with an `events` array — the
 *   player_events/{match_id}/{player_id}.json contract (or any subset of
 *   it). Non-Shot events and shots without a shot_end_location are ignored,
 *   so callers may pass the full unfiltered file.
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {number}   [config.width=320]  - SVG width in pixels.
 * @param {number}   [config.height=220] - SVG height in pixels.
 * @param {number}   [config.minRadius=4]  - Smallest shot-marker radius in pixels.
 * @param {number}   [config.maxRadius=22] - Largest shot-marker radius in pixels
 *   (at the highest shot_xg in the data).
 * @param {string}   [config.frameColor="#1E3A5F"]     - Goal-frame stroke color.
 * @param {string}   [config.onTargetColor="#525252"]  - On-target shot fill/stroke color.
 * @param {string}   [config.goalColor="#9F1239"]      - Goal fill + ring color.
 * @param {string}   [config.highlightColor="#F59E0B"] - Inbound cross-link ring color.
 * @param {string|null} [config.highlightEventId=null] - Inbound cross-link:
 *   rings the shot with this event_id.
 * @param {Function|null} [config.onHover=null] - onHover(eventId | null)
 *   fires on shot hover/unhover.
 * @param {boolean}  [config.showTooltip=true] - Render the built-in floating tooltip.
 * @param {boolean}  [config.showLegend=true]  - Render the on/off/xG-radius legend.
 * @returns {{ svg: d3.Selection, g: d3.Selection, update: Function }}
 *   svg — the created SVG selection.
 *   g   — the main `<g>` group.
 *   update({ data?, highlightEventId? }) — re-render with new events and/or
 *     move the inbound highlight ring. Any omitted key retains its current value.
 */
export function createGoalMouthShotPanel(selection, data, config = {}) {
  let {
    width            = 320,
    height           = 220,
    minRadius        = 4,
    maxRadius        = 22,
    frameColor       = "#1E3A5F",
    onTargetColor    = "#525252",
    goalColor        = "#9F1239",
    highlightColor   = "#F59E0B",
    highlightEventId = null,
    onHover          = null,
    showTooltip      = true,
    showLegend       = true,
  } = config;

  const legendHeight = showLegend ? 24 : 0;
  const stripHeight = 40;
  const frameTop = legendHeight + stripHeight;
  const frameHeight = height - frameTop - 16;
  const frameWidth = Math.min(width - 32, frameHeight * (GOAL_WIDTH_YARDS / CROSSBAR_HEIGHT_YARDS));
  const frameLeft = (width - frameWidth) / 2;

  const yScale = d3.scaleLinear().domain([GOAL_Y_MIN, GOAL_Y_MAX]).range([frameLeft, frameLeft + frameWidth]);
  const zScale = d3.scaleLinear().domain([0, CROSSBAR_HEIGHT_YARDS]).range([frameTop + frameHeight, frameTop]);
  const offTargetXScale = d3.scaleLinear()
    .domain([OFF_TARGET_Y_MIN, OFF_TARGET_Y_MAX])
    .range([frameLeft - 20, frameLeft + frameWidth + 20])
    .clamp(true);

  const svg = selection.append("svg").attr("width", width).attr("height", height);
  const g = svg.append("g");

  let currentData = data;

  function shotsFrom(rawData) {
    return (rawData.events ?? []).filter(
      (e) => e.type === "Shot" && Array.isArray(e.shot_end_location)
    );
  }

  function render() {
    g.selectAll("*").remove();

    const shots = shotsFrom(currentData);
    const maxXg = d3.max(shots, (s) => s.shot_xg ?? 0) || 0.01;
    const radiusScale = d3.scaleSqrt().domain([0, maxXg]).range([minRadius, maxRadius]);

    if (showLegend) {
      const legend = g.append("g").attr("class", "gmsp-legend").attr("transform", "translate(4,4)");
      legend.append("circle").attr("cx", 6).attr("cy", 6).attr("r", 5)
        .attr("fill", "none").attr("stroke", onTargetColor).attr("stroke-width", 1.5);
      legend.append("text").attr("x", 16).attr("y", 10).attr("font-size", "10px")
        .attr("font-family", "Geist Mono, monospace").attr("fill", "#525252").text("on target");

      legend.append("circle").attr("cx", 88).attr("cy", 6).attr("r", 5)
        .attr("fill", "none").attr("stroke", onTargetColor).attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "2,2");
      legend.append("text").attr("x", 98).attr("y", 10).attr("font-size", "10px")
        .attr("font-family", "Geist Mono, monospace").attr("fill", "#525252").text("off target");

      legend.append("circle").attr("cx", 190).attr("cy", 6).attr("r", 5)
        .attr("fill", "none").attr("stroke", "#8A8578").attr("stroke-width", 1);
      legend.append("text").attr("x", 200).attr("y", 10).attr("font-size", "10px")
        .attr("font-family", "Geist Mono, monospace").attr("fill", "#525252").text("○ = xG");
    }

    // Off-target strip.
    g.append("rect")
      .attr("x", frameLeft - 20).attr("width", frameWidth + 40)
      .attr("y", legendHeight).attr("height", stripHeight - 6)
      .attr("fill", "none").attr("stroke", "#E5E5E5").attr("stroke-dasharray", "3,3");
    g.append("text")
      .attr("x", frameLeft - 16).attr("y", legendHeight + 14)
      .attr("font-size", "9px").attr("font-family", "Geist Mono, monospace")
      .attr("fill", "#8A8578").text("OFF TARGET");

    // Goal frame (posts + crossbar).
    g.append("rect")
      .attr("class", "gmsp-frame")
      .attr("x", frameLeft).attr("y", frameTop)
      .attr("width", frameWidth).attr("height", frameHeight)
      .attr("fill", "#FAF7F0").attr("stroke", frameColor).attr("stroke-width", 2);

    const onTarget = shots.filter(isOnTarget);
    const offTarget = shots.filter((s) => !isOnTarget(s));

    const onTargetMarks = g.selectAll(".gmsp-on")
      .data(onTarget, (d) => d.event_id)
      .join("circle")
      .attr("class", "gmsp-on")
      .attr("cx", (d) => yScale(d.shot_end_location[0]))
      .attr("cy", (d) => zScale(Math.min(d.shot_end_location[1] ?? 0, CROSSBAR_HEIGHT_YARDS)))
      .attr("r", (d) => radiusScale(d.shot_xg ?? 0))
      .attr("fill", (d) => (d.is_goal ? goalColor : "none"))
      .attr("fill-opacity", 0.85)
      .attr("stroke", (d) => (d.is_goal ? goalColor : onTargetColor))
      .attr("stroke-width", (d) => (d.is_goal ? 2.5 : 1.5));

    const offTargetMarks = g.selectAll(".gmsp-off")
      .data(offTarget, (d) => d.event_id)
      .join("circle")
      .attr("class", "gmsp-off")
      .attr("cx", (d) => offTargetXScale(d.shot_end_location[0]))
      .attr("cy", legendHeight + stripHeight / 2 - 3)
      .attr("r", (d) => radiusScale(d.shot_xg ?? 0))
      .attr("fill", "none")
      .attr("stroke", onTargetColor)
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "2,2");

    const allMarks = onTargetMarks.merge(offTargetMarks);

    g.selectAll(".gmsp-highlight")
      .data(shots.filter((d) => d.event_id === highlightEventId), (d) => d.event_id)
      .join("circle")
      .attr("class", "gmsp-highlight")
      .attr("cx", (d) => (isOnTarget(d)
        ? yScale(d.shot_end_location[0])
        : offTargetXScale(d.shot_end_location[0])))
      .attr("cy", (d) => (isOnTarget(d)
        ? zScale(Math.min(d.shot_end_location[1] ?? 0, CROSSBAR_HEIGHT_YARDS))
        : legendHeight + stripHeight / 2 - 3))
      .attr("r", (d) => radiusScale(d.shot_xg ?? 0) + 4)
      .attr("fill", "none")
      .attr("stroke", highlightColor)
      .attr("stroke-width", 2)
      .attr("pointer-events", "none");

    allMarks
      .style("cursor", "pointer")
      .on("mouseover", (event, d) => {
        if (onHover) onHover(d.event_id);
        if (showTooltip) {
          const tooltip = getTooltip();
          tooltip.innerHTML =
            `<span style="font-weight:600">${d.minute}'</span> · ${d.outcome ?? ""} · ` +
            `xG ${(d.shot_xg ?? 0).toFixed(2)}`;
          tooltip.style.display = "block";
        }
      })
      .on("mousemove", (event) => {
        if (!showTooltip) return;
        const tooltip = getTooltip();
        tooltip.style.left = (event.clientX + 14) + "px";
        tooltip.style.top = (event.clientY - 28) + "px";
      })
      .on("mouseout", () => {
        if (onHover) onHover(null);
        if (showTooltip) getTooltip().style.display = "none";
      });
  }

  render();

  /**
   * Re-render with new events and/or move the inbound highlight ring.
   *
   * @param {Object} [next={}] - Partial update.
   * @param {Object} [next.data] - Replacement `{ events: [...] }` object.
   * @param {string|null} [next.highlightEventId] - New inbound-highlight event_id.
   */
  function update(next = {}) {
    if (next.data !== undefined) currentData = next.data;
    if (next.highlightEventId !== undefined) highlightEventId = next.highlightEventId;
    render();
  }

  return { svg, g, update };
}
