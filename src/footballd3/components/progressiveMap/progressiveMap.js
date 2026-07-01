/**
 * progressiveMap.js — pass and carry arrow overlay for a pitch.
 *
 * Composes on pitch.js: receives an existing pitch object and draws arrows
 * onto pitch.g using pitch.px() for coordinate conversion. Does not create
 * or re-render the pitch.
 *
 * Default view shows all open-play passes and carries: progressive actions are
 * highlighted with bold colour-coded arrows; non-progressive actions appear as
 * thin muted lines in the background. Set progressiveOnly: true to show only
 * progressive actions.
 *
 * Progressive = StatsBomb's 25%-of-remaining-distance-to-goal-centre rule,
 * set pieces excluded, threshold configurable. See README.md for the full
 * definition, the pass/carry asymmetry, and a note on definition comparability.
 *
 * Encoding — color encodes action TYPE for all actions:
 *   Progressive completed pass:   #9F1239 (red),  solid,        opacity 0.75, 1.5px, arrow
 *   Progressive incomplete pass:  #9F1239 (red),  dashed (5,3), opacity 0.28, 1.5px, arrow
 *   Progressive carry:            #1E3A5F (navy), solid,         opacity 0.75, 2.5px, arrow
 *   Non-progressive pass:         #9F1239 (red),  solid,  opacity 0.18, 1.5px, arrow
 *   Non-progressive carry:        #1E3A5F (navy), solid,  opacity 0.18, 2.5px, arrow
 */

const _tooltip = document.createElement("div");
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
  zIndex:        "100",
});
document.body.appendChild(_tooltip);

const COLOR_PASS  = "#9F1239";
const COLOR_CARRY = "#1E3A5F";

const STROKE_PASS  = 1.5;
const STROKE_CARRY = 2.5;

const OPACITY_COMPLETE   = 0.75;
const OPACITY_INCOMPLETE = 0.28;
const OPACITY_MUTED      = 0.18;

const DASH_INCOMPLETE = "5,3";

/**
 * Create a pass and carry arrow overlay on an existing pitch.
 *
 * Call createPitch() first and pass its return value here. This function
 * appends arrow elements to pitch.g and never touches the pitch background
 * or markings.
 *
 * By default all open-play actions are shown. Color encodes action type for
 * ALL actions — red for passes, navy for carries. Progressive actions are bold
 * with arrowheads; non-progressive are thin and faded (same type color). Set
 * progressiveOnly: true to show only progressive actions.
 *
 * Passes show completed and incomplete attempts (solid vs dashed red).
 * Carries show completed carries only — see README for the asymmetry rationale.
 *
 * @param {Object} pitch - Return value of createPitch(). Must expose { svg, g, px }.
 * @param {Object} data  - Progressive map JSON contract (progressive_map_*.json).
 * @param {Object} [config={}] - Rendering options.
 * @param {string}  [config.toggle="both"]           - Which action types to show:
 *   "passes" | "carries" | "both".
 * @param {string|null} [config.player=null]          - Restrict to one player by
 *   display_name. null renders all players.
 * @param {boolean} [config.progressiveOnly=false]    - When true, render only
 *   progressive actions (hides the muted background layer).
 * @param {boolean} [config.distanceWeight=false]     - When true, scale stroke-width
 *   of progressive arrows linearly by distance_gained. Off by default.
 * @returns {{ g: d3.Selection, update: function }}
 *   g:      The D3 selection of the arrow group (appended to pitch.g).
 *   update: function({ toggle?, player?, progressiveOnly? }) — re-renders with
 *           new filter state. Any omitted keys keep their previous value.
 */
export function createProgressiveMap(pitch, data, config = {}) {
  const {
    toggle         = "both",
    player         = null,
    progressiveOnly = false,
    distanceWeight = false,
  } = config;

  const { svg, g, px } = pitch;

  // Ensure <defs> exists; re-use if already present (e.g. from the pitch itself).
  let defs = svg.select("defs");
  if (defs.empty()) defs = svg.append("defs");

  // Add arrow markers only once per SVG — guard against repeated calls.
  if (defs.select("#pm-arrow-red").empty()) {
    _addMarker(defs, "pm-arrow-red",  COLOR_PASS);
  }
  if (defs.select("#pm-arrow-navy").empty()) {
    _addMarker(defs, "pm-arrow-navy", COLOR_CARRY);
  }

  const arrowsG = g.append("g").attr("class", "pm-arrows");

  // Distance-weight scale for progressive arrows: distance_gained → stroke multiplier.
  const distMax = data.actions
    .filter(a => a.progressive)
    .reduce((m, a) => Math.max(m, a.distance_gained), 1);
  const wScale = d3.scaleLinear().domain([0, distMax]).range([0.8, 2.5]).clamp(true);

  let _toggle         = toggle;
  let _player         = player;
  let _progressiveOnly = progressiveOnly;

  render();

  /**
   * Re-render arrows with new filter options.
   *
   * @param {Object} [opts={}]
   * @param {string}      [opts.toggle]           - "passes" | "carries" | "both"
   * @param {string|null} [opts.player]            - display_name filter, or null for all
   * @param {boolean}     [opts.progressiveOnly]   - true = progressive only; false = all
   */
  function update(opts = {}) {
    if (opts.toggle          !== undefined) _toggle          = opts.toggle;
    if (opts.player          !== undefined) _player          = opts.player;
    if (opts.progressiveOnly !== undefined) _progressiveOnly = opts.progressiveOnly;
    render();
  }

  function render() {
    arrowsG.selectAll("*").remove();

    // Apply type and player filters to everything first.
    const filtered = data.actions.filter(a => {
      if (_toggle === "passes"  && a.action_type !== "pass")  return false;
      if (_toggle === "carries" && a.action_type !== "carry") return false;
      if (_player !== null && a.display_name !== _player)     return false;
      return true;
    });

    const nonProgressive = filtered.filter(a => !a.progressive);
    const progressive    = filtered.filter(a =>  a.progressive);

    // ── Non-progressive background layer (rendered first, behind progressive) ──
    if (!_progressiveOnly) {
      nonProgressive.forEach(a => {
        const [x0, y0] = px(a.x0, a.y0);
        const [x1, y1] = px(a.x1, a.y1);
        const mutedColor = a.action_type === "carry" ? COLOR_CARRY : COLOR_PASS;

        const mutedStroke = a.action_type === "carry" ? STROKE_CARRY : STROKE_PASS;

        const mutedMarker = a.action_type === "carry" ? "url(#pm-arrow-navy)" : "url(#pm-arrow-red)";

        arrowsG.append("line")
          .attr("x1", x0).attr("y1", y0)
          .attr("x2", x1).attr("y2", y1)
          .attr("stroke",         mutedColor)
          .attr("stroke-width",   mutedStroke)
          .attr("stroke-opacity", OPACITY_MUTED)
          .attr("stroke-linecap", "round")
          .attr("marker-end",     mutedMarker)
          .on("mouseover", () => {
            const typeLabel = a.action_type === "carry" ? "carry" : "pass";
            _tooltip.innerHTML =
              `<span style="font-weight:600">${a.display_name}</span><br>` +
              `${typeLabel} &middot; min. ${a.minute}`;
            _tooltip.style.display = "block";
          })
          .on("mousemove", event => {
            _tooltip.style.left = (event.clientX + 14) + "px";
            _tooltip.style.top  = (event.clientY - 28) + "px";
          })
          .on("mouseout", () => {
            _tooltip.style.display = "none";
          });
      });
    }

    // ── Progressive actions (rendered on top) ─────────────────────────────────
    progressive.forEach(a => {
      const [x0, y0] = px(a.x0, a.y0);
      const [x1, y1] = px(a.x1, a.y1);

      const isCarry = a.action_type === "carry";
      const isDone  = a.completed;

      const stroke  = isCarry ? COLOR_CARRY : COLOR_PASS;
      const marker  = isCarry ? "url(#pm-arrow-navy)" : "url(#pm-arrow-red)";
      const opacity = (!isCarry && !isDone) ? OPACITY_INCOMPLETE : OPACITY_COMPLETE;
      const baseW   = isCarry ? STROKE_CARRY : STROKE_PASS;
      const sw      = distanceWeight ? wScale(a.distance_gained) * (isCarry ? 1.67 : 1) : baseW;

      const line = arrowsG.append("line")
        .attr("x1", x0).attr("y1", y0)
        .attr("x2", x1).attr("y2", y1)
        .attr("stroke",         stroke)
        .attr("stroke-width",   sw)
        .attr("stroke-opacity", opacity)
        .attr("stroke-linecap", "round")
        .attr("marker-end",     marker)
        .style("cursor", "default");

      if (!isCarry && !isDone) {
        line.attr("stroke-dasharray", DASH_INCOMPLETE);
      }

      line
        .on("mouseover", () => {
          const typeLabel = isCarry
            ? "carry"
            : (isDone ? "pass ✓" : "pass ✗");
          _tooltip.innerHTML =
            `<span style="font-weight:600">${a.display_name}</span><br>` +
            `${typeLabel} &middot; min. ${a.minute}<br>` +
            `<span style="color:#525252">${a.distance_gained.toFixed(1)} yds gained</span>`;
          _tooltip.style.display = "block";
        })
        .on("mousemove", event => {
          _tooltip.style.left = (event.clientX + 14) + "px";
          _tooltip.style.top  = (event.clientY - 28) + "px";
        })
        .on("mouseout", () => {
          _tooltip.style.display = "none";
        });
    });
  }

  return { g: arrowsG, update };
}

/**
 * Append an SVG arrowhead marker to a <defs> selection.
 *
 * @param {d3.Selection} defs  - D3 selection of the <defs> element.
 * @param {string}       id    - Marker element id attribute.
 * @param {string}       color - Fill color for the arrowhead.
 */
function _addMarker(defs, id, color) {
  defs.append("marker")
    .attr("id",           id)
    .attr("viewBox",      "0 -4 8 8")
    .attr("refX",         8)
    .attr("refY",         0)
    .attr("markerWidth",  4)
    .attr("markerHeight", 4)
    .attr("orient",       "auto")
    .append("path")
    .attr("d",    "M0,-4L8,0L0,4Z")
    .attr("fill", color);
}
