/**
 * passSonar.js — polar bearing/length chart of one player's passes.
 *
 * Standalone chart — creates its own SVG inside the given selection, does not
 * compose on pitch.js. Bins every Pass event in the data by its bearing
 * (direction of travel) into equal angular sectors and draws two nested
 * wedges per sector: an outer stroked-only wedge sized to the sector's total
 * ATTEMPTED pass count, and an inner filled wedge sized to its COMPLETED
 * count. Radius encodes count directly (not area) — a sector with twice the
 * attempts of another gets twice the radius, per the design spec.
 *
 * FORWARD = UP, ALWAYS (no per-team flip needed)
 * StatsBomb locations are stored per-ACTING-team, not per real-world stadium
 * end: a team's x-axis always runs from their own goal (x=0) toward the
 * opponent's goal (x=120), for both halves, for both teams — verified against
 * this match's shot locations (every team's shots cluster near x≈105-108 in
 * both periods; if the axis flipped at half-time or between teams, one side's
 * shots would cluster near x≈15 instead). So "forward" is always +x in the
 * raw location/end_location pair, with no attacking-direction config needed —
 * unlike pitch.js/formation.js, which DO need a flip config because they draw
 * on a shared two-team surface.
 *
 * BEARING -> SCREEN ANGLE
 * bearing = atan2(dy, dx) where dx = end_x - x (forward component), dy =
 * end_y - y (lateral component, StatsBomb y increases toward one touchline).
 * Screen angle places bearing 0 (pure forward) at 12 o'clock and increases
 * clockwise for positive dy — i.e. screenAngle = bearing, drawn with d3.arc's
 * own clockwise-from-12-o'clock convention (startAngle 0 = up).
 *
 * MANY-EVENTS-PER-WEDGE HOVER LINKING
 * A wedge aggregates every pass in its bin, so it cannot map to a single
 * event_id the way a pitch marker or feed row can. onHover fires with
 * { bin, eventIds: string[] } (every underlying pass's event_id) rather than
 * one id. Going the other direction, update({ highlightEventId }) rings
 * whichever bin CONTAINS that event_id — a many-to-one version of the app's
 * usual one-to-one event-scope highlight, documented here since it's a
 * deliberate deviation from the single-event convention used elsewhere.
 */

import * as d3 from "d3";

const DEFAULT_BINS = 16;

let _tooltip;
function getTooltip() {
  if (!_tooltip) {
    _tooltip = document.createElement("div");
    Object.assign(_tooltip.style, {
      position:      "fixed",
      pointerEvents: "none",
      display:       "none",
      background:    "#FAF7F0",
      border:        "1px solid #E5E5E5",
      borderRadius:  "2px",
      padding:       "8px 10px",
      fontFamily:    "Geist Mono, monospace",
      fontSize:      "12px",
      lineHeight:    "1.6",
      color:         "#171717",
      whiteSpace:    "nowrap",
      zIndex:        "1000",
    });
    document.body.appendChild(_tooltip);
  }
  return _tooltip;
}

/**
 * Bin a player's Pass events by bearing.
 *
 * @param {Array<Object>} events - Full player_events array (any event types;
 *   non-Pass events and passes without an end_location are ignored).
 * @param {number} numBins - Number of equal angular sectors.
 * @returns {Array<{ bin: number, attempted: Array<Object>, completed: Array<Object> }>}
 *   One entry per bin, in ascending bin-index order. `attempted` holds every
 *   pass event in the sector; `completed` holds the subset with outcome ===
 *   null (StatsBomb's completed-pass convention, same as utils.pass_outcome).
 */
function binPasses(events, numBins) {
  const bins = Array.from({ length: numBins }, (_, i) => ({
    bin: i, attempted: [], completed: [],
  }));
  const sectorSize = (2 * Math.PI) / numBins;

  for (const event of events) {
    if (event.type !== "Pass" || !event.end_location) continue;
    const [x, y] = event.location;
    const [ex, ey] = event.end_location;
    const dx = ex - x;
    const dy = ey - y;
    if (dx === 0 && dy === 0) continue;

    const bearing = Math.atan2(dy, dx); // 0 = forward, +pi/2 = toward +y touchline
    const normalized = ((bearing % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
    const binIndex = Math.min(numBins - 1, Math.floor(normalized / sectorSize));

    bins[binIndex].attempted.push(event);
    if (event.outcome === null || event.outcome === undefined) {
      bins[binIndex].completed.push(event);
    }
  }
  return bins;
}

/**
 * Render a polar pass-sonar chart for one player.
 *
 * @param {d3.Selection} selection - D3 selection of the container element.
 * @param {Object} data - Object with an `events` array — the
 *   player_events/{match_id}/{player_id}.json contract (or any subset of it;
 *   non-Pass events are ignored, so callers may pass the full file unfiltered).
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {number}   [config.width=280]              - SVG width in pixels.
 * @param {number}   [config.height=280]             - SVG height in pixels.
 * @param {number}   [config.numBins=16]             - Angular sectors.
 * @param {string}   [config.attemptedColor="#9F1239"] - Outer wedge stroke color.
 * @param {string}   [config.completedColor="#9F1239"] - Inner wedge fill color.
 * @param {string}   [config.highlightColor="#F59E0B"] - Ring color for the
 *   bin containing config.highlightEventId.
 * @param {string|null} [config.highlightEventId=null] - Inbound cross-link:
 *   rings whichever bin contains a pass with this event_id.
 * @param {Function|null} [config.onHover=null] - onHover({ bin, eventIds } | null)
 *   fires on wedge hover/unhover. eventIds is every attempted pass's event_id
 *   in that sector (see module docstring for why this is plural).
 * @param {boolean}  [config.showTooltip=true] - Render the built-in floating tooltip.
 * @returns {{ svg: d3.Selection, g: d3.Selection, update: Function }}
 *   svg    — the created SVG selection.
 *   g      — the main <g> group, centered in the SVG.
 *   update({ data?, highlightEventId? }) — re-render with new events and/or
 *     move the inbound highlight ring. Any omitted key retains its current value.
 */
export function createPassSonar(selection, data, config = {}) {
  let {
    width           = 280,
    height          = 280,
    numBins         = DEFAULT_BINS,
    attemptedColor  = "#9F1239",
    completedColor  = "#9F1239",
    highlightColor  = "#F59E0B",
    highlightEventId = null,
    onHover         = null,
    showTooltip     = true,
  } = config;

  const svg = selection.append("svg").attr("width", width).attr("height", height);
  const cx = width / 2;
  const cy = height / 2;
  const g = svg.append("g").attr("transform", `translate(${cx},${cy})`);
  const maxOuterRadius = Math.min(width, height) / 2 - 24;

  let currentData = data;

  function render() {
    g.selectAll("*").remove();

    const bins = binPasses(currentData.events ?? [], numBins);
    const maxAttempted = d3.max(bins, (d) => d.attempted.length) || 1;
    const radiusScale = d3.scaleLinear().domain([0, maxAttempted]).range([0, maxOuterRadius]);
    const sectorSize = (2 * Math.PI) / numBins;

    // Reference rings + spokes.
    const ringTicks = radiusScale.ticks(3).filter((t) => t > 0);
    g.selectAll(".sonar-ring")
      .data(ringTicks)
      .join("circle")
      .attr("class", "sonar-ring")
      .attr("r", (d) => radiusScale(d))
      .attr("fill", "none")
      .attr("stroke", "#E5E5E5")
      .attr("stroke-width", 1);

    g.append("line")
      .attr("x1", 0).attr("y1", -maxOuterRadius).attr("x2", 0).attr("y2", maxOuterRadius)
      .attr("stroke", "#E5E5E5").attr("stroke-width", 1);
    g.append("line")
      .attr("x1", -maxOuterRadius).attr("y1", 0).attr("x2", maxOuterRadius).attr("y2", 0)
      .attr("stroke", "#E5E5E5").attr("stroke-width", 1);

    const arc = d3.arc().innerRadius(0);

    const wedges = g.selectAll(".sonar-wedge")
      .data(bins)
      .join("g")
      .attr("class", "sonar-wedge")
      .style("cursor", (d) => (d.attempted.length ? "pointer" : "default"));

    wedges.append("path")
      .attr("class", "sonar-attempted")
      .attr("d", (d) => arc({
        startAngle: d.bin * sectorSize,
        endAngle:   (d.bin + 1) * sectorSize,
        outerRadius: radiusScale(d.attempted.length),
      }))
      .attr("fill", "none")
      .attr("stroke", attemptedColor)
      .attr("stroke-width", 1.25)
      .attr("opacity", 0.7);

    wedges.append("path")
      .attr("class", "sonar-completed")
      .attr("d", (d) => arc({
        startAngle: d.bin * sectorSize,
        endAngle:   (d.bin + 1) * sectorSize,
        outerRadius: radiusScale(d.completed.length),
      }))
      .attr("fill", completedColor)
      .attr("opacity", 0.55)
      .attr("pointer-events", "none");

    wedges.append("path")
      .attr("class", "sonar-highlight")
      .attr("d", (d) => arc({
        startAngle: d.bin * sectorSize,
        endAngle:   (d.bin + 1) * sectorSize,
        outerRadius: Math.max(radiusScale(d.attempted.length), 10),
      }))
      .attr("fill", "none")
      .attr("stroke", highlightColor)
      .attr("stroke-width", 2)
      .attr("pointer-events", "none")
      .style("display", (d) =>
        highlightEventId && d.attempted.some((e) => e.event_id === highlightEventId)
          ? null : "none"
      );

    wedges
      .on("mouseover", (event, d) => {
        if (!d.attempted.length) return;
        if (onHover) onHover({ bin: d.bin, eventIds: d.attempted.map((e) => e.event_id) });
        if (showTooltip) {
          const tooltip = getTooltip();
          tooltip.innerHTML =
            `<span style="font-weight:600">${d.attempted.length} attempted</span> · ` +
            `${d.completed.length} completed`;
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
