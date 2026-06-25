/**
 * @module matchStats
 *
 * Match statistics breakdown for a football match. Owns all football logic:
 * team identity, score rendering, stat labels, xG attribution, card icon rendering,
 * and the home→left / away→right mapping to the generic comparisonBars renderer.
 *
 * This component composes comparisonBars — it does NOT re-implement bar rendering.
 * comparisonBars knows nothing about football; all football semantics live here.
 *
 * Data source: match_stats_{match_id}.json, produced by extract_match_stats.py.
 * xG values are StatsBomb's own shot_statsbomb_xg — not a custom model.
 * Possession % is the share of distinct StatsBomb possession sequences per team.
 */

import { createComparisonBars } from "../comparisonBars/comparisonBars.js";

/** Card icon dimensions in pixels. */
const CARD_W = 8;
const CARD_H = 11;

/** Canonical card colours (football conventions, not project palette). */
const CARD_COLORS = {
  yellow: "#FACC15",
  red:    "#DC2626",
};

/** Row labels that represent disciplinary cards. */
const CARD_COLOR_BY_LABEL = {
  "Yellow Cards": CARD_COLORS.yellow,
  "Red Cards":    CARD_COLORS.red,
};

/**
 * Inject CSS for matchStats chrome into the document <head> if not already present.
 *
 * All selectors use the `.ms-` prefix and do not affect comparisonBars internals.
 */
function ensureStyles() {
  if (document.getElementById("ms-styles")) return;
  const style = document.createElement("style");
  style.id = "ms-styles";
  style.textContent = `
    .ms-root { display: inline-block; }
    .ms-match-label {
      font-family: var(--font-mono, 'Geist Mono', monospace);
      font-size: 10px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #525252;
      margin-bottom: 12px;
    }
    .ms-score-block {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 20px;
      margin-bottom: 20px;
    }
    .ms-team {
      font-family: var(--font-display, 'Fraunces', Georgia, serif);
      font-weight: 700;
      font-size: 18px;
      min-width: 80px;
    }
    .ms-team--home { text-align: right; }
    .ms-team--away { text-align: left;  }
    .ms-score {
      font-family: var(--font-display, 'Fraunces', Georgia, serif);
      font-weight: 900;
      font-size: 48px;
      line-height: 1;
      color: #171717;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .ms-score-sep { font-size: 32px; color: #525252; }
    .ms-tier-toggle { display: flex; gap: 8px; margin-bottom: 12px; }
    .ms-tier-btn {
      font-family: var(--font-mono, 'Geist Mono', monospace);
      font-size: 11px;
      padding: 3px 10px;
      border: 1px solid #E5E5E5;
      background: #FAF7F0;
      color: #525252;
      cursor: pointer;
      border-radius: 2px;
    }
    .ms-tier-btn.active { border-color: #171717; color: #171717; }
  `;
  document.head.appendChild(style);
}

/**
 * Populate a score-block container with team names and the score.
 *
 * @param {d3.Selection} scoreEl - The .ms-score-block div to populate.
 * @param {Object}       data    - matchStats JSON contract.
 */
function fillScoreBlock(scoreEl, data) {
  scoreEl.selectAll("*").remove();

  scoreEl.append("div")
    .attr("class", "ms-team ms-team--home")
    .style("color", data.home.color)
    .text(data.home.team);

  const scoreNum = scoreEl.append("div").attr("class", "ms-score");
  scoreNum.append("span").attr("class", "ms-score-num").text(data.home.score);
  scoreNum.append("span").attr("class", "ms-score-sep").text("–");
  scoreNum.append("span").attr("class", "ms-score-num").text(data.away.score);

  scoreEl.append("div")
    .attr("class", "ms-team ms-team--away")
    .style("color", data.away.color)
    .text(data.away.team);
}

/**
 * Append SVG card icons next to value text for disciplinary card rows.
 *
 * Positioned by reading the expected x-coordinates used by comparisonBars.
 * Icons are appended to the comparisonBars SVG element and rendered on top of bars.
 * Only rows with at least one card on a side receive an icon on that side.
 *
 * @param {d3.Selection} svg      - SVG element returned by createComparisonBars.
 * @param {Object}       data     - matchStats JSON contract.
 * @param {Object}       barCfg   - comparisonBars config object (width, labelWidth, …).
 * @param {Array<Object>} barRows - The filtered rows actually passed to comparisonBars.
 */
function renderCardIcons(svg, data, barCfg, barRows) {
  const halfW   = (barCfg.width - barCfg.labelWidth) / 2;
  const VAL_PAD = 6;
  // Mirror comparisonBars' own header-height resolution so icons align with bars.
  const headerH = barCfg.showHeader === false ? 0 : (barCfg.headerHeight ?? 32);
  const padY    = barCfg.paddingY;

  barRows.forEach((barRow, i) => {
    const cardColor = CARD_COLOR_BY_LABEL[barRow.label];
    if (!cardColor) return;

    // Match barRow back to the original data row to get home/away values.
    const orig = data.rows.find(r => r.label === barRow.label);
    if (!orig) return;

    const cy = headerH + padY + i * barCfg.rowHeight + barCfg.rowHeight / 2;

    // Home cards → just right of the left value text (text-anchor=end at halfW - VAL_PAD)
    if (orig.home_value > 0) {
      svg.append("rect")
        .attr("class",  "ms-card-icon ms-card-icon--home")
        .attr("x",      halfW - VAL_PAD + 3)
        .attr("y",      cy - CARD_H / 2)
        .attr("width",  CARD_W)
        .attr("height", CARD_H)
        .attr("rx",     1)
        .attr("fill",   cardColor);
    }

    // Away cards → just right of the right value text (text-anchor=start at halfW+labelWidth+VAL_PAD)
    if (orig.away_value > 0) {
      const awayDigits = String(Math.round(orig.away_value)).length;
      const awayValW   = awayDigits * 8 + 4;
      svg.append("rect")
        .attr("class",  "ms-card-icon ms-card-icon--away")
        .attr("x",      halfW + barCfg.labelWidth + VAL_PAD + awayValW)
        .attr("y",      cy - CARD_H / 2)
        .attr("width",  CARD_W)
        .attr("height", CARD_H)
        .attr("rx",     1)
        .attr("fill",   cardColor);
    }
  });
}

/**
 * Map a matchStats row to the comparisonBars row contract (home→left, away→right).
 *
 * @param {Object} row - One row from the matchStats JSON `rows` array.
 * @returns {Object} comparisonBars row object.
 */
function toBarRow(row) {
  return {
    label:       row.label,
    leftValue:   row.home_value,
    rightValue:  row.away_value,
    scaleType:   row.scale_type,
    format:      row.format,
    ...(row.max_value !== undefined ? { maxValue: row.max_value } : {}),
  };
}

/**
 * Create a match statistics breakdown component.
 *
 * Renders a score headline (home – away), optional tier toggle (basic / all),
 * and a comparisonBars chart for the stat rows. Disciplinary card rows receive
 * additional SVG card icons that are appended inside this component — not inside
 * comparisonBars, which remains unaware of card semantics.
 *
 * @param {d3.Selection} selection - D3 selection of the container element to render into.
 * @param {Object} data - matchStats JSON contract.
 * @param {Object} data.home - Home team.
 * @param {string} data.home.team  - Home team name.
 * @param {string} data.home.color - Home team hex color.
 * @param {number} data.home.score - Home team goals scored.
 * @param {Object} data.away - Away team.
 * @param {string} data.away.team  - Away team name.
 * @param {string} data.away.color - Away team hex color.
 * @param {number} data.away.score - Away team goals scored.
 * @param {Array<Object>} data.rows - Stat rows. Each carries:
 *   label (str), home_value (number), away_value (number),
 *   scale_type ("sum"|"fixed100"|"max"), format ("int"|"pct"|"float1"),
 *   tier ("basic"|"advanced"), and optionally max_value (number).
 * @param {Object} data.metadata - Match metadata.
 * @param {number} data.metadata.match_id    - StatsBomb match ID.
 * @param {string} data.metadata.competition - Competition name.
 * @param {string} data.metadata.match_label - Human-readable match label.
 * @param {Object} [config] - Component configuration.
 * @param {"basic"|"all"} [config.tier="basic"] - Initial tier filter:
 *   "basic" shows only tier="basic" rows; "all" shows every row.
 * @param {boolean} [config.showTierToggle=true] - Show the basic/all tier toggle.
 * @param {number} [config.width=480]        - Passed through to comparisonBars.
 * @param {number} [config.rowHeight=40]     - Passed through to comparisonBars.
 * @param {number} [config.barHeight=14]     - Passed through to comparisonBars.
 * @param {number} [config.labelWidth=130]   - Passed through to comparisonBars.
 * @param {number} [config.headerHeight=32]  - Passed through to comparisonBars.
 * @param {number} [config.paddingY=10]      - Passed through to comparisonBars.
 * @returns {{ root: d3.Selection, update: Function }}
 *   root — the root `.ms-root` div element.
 *   update(newData, newConfig?) — replace data and re-render. Tier state is preserved
 *   unless overridden via newConfig.tier.
 */
export function createMatchStats(selection, data, config = {}) {
  ensureStyles();

  const cfg = {
    tier:           "basic",
    showTierToggle: true,
    width:          480,
    rowHeight:      40,
    barHeight:      14,
    labelWidth:     130,
    headerHeight:   32,
    paddingY:       10,
    ...config,
  };

  const barCfg = {
    width:        cfg.width,
    rowHeight:    cfg.rowHeight,
    barHeight:    cfg.barHeight,
    labelWidth:   cfg.labelWidth,
    headerHeight: cfg.headerHeight,
    paddingY:     cfg.paddingY,
    showHeader:   false,
  };

  let activeTier = cfg.tier;

  // ── Root ────────────────────────────────────────────────────────────────────
  const root = selection.append("div").attr("class", "ms-root");

  // Match label
  const matchLabelEl = root.append("div").attr("class", "ms-match-label");

  // Score headline — same width as the chart so justify-content:center sits over the bars
  const scoreEl = root.append("div")
    .attr("class", "ms-score-block")
    .style("width", `${cfg.width}px`);

  // Tier toggle (optional)
  let btnBasic, btnAll;
  if (cfg.showTierToggle) {
    const toggleRow = root.append("div").attr("class", "ms-tier-toggle");
    btnBasic = toggleRow.append("button")
      .attr("class", "ms-tier-btn" + (activeTier === "basic" ? " active" : ""))
      .text("basic");
    btnAll = toggleRow.append("button")
      .attr("class", "ms-tier-btn" + (activeTier === "all" ? " active" : ""))
      .text("all");

    btnBasic.on("click", () => {
      activeTier = "basic";
      btnBasic.attr("class", "ms-tier-btn active");
      btnAll.attr("class",   "ms-tier-btn");
      redrawBars(currentData);
    });
    btnAll.on("click", () => {
      activeTier = "all";
      btnBasic.attr("class", "ms-tier-btn");
      btnAll.attr("class",   "ms-tier-btn active");
      redrawBars(currentData);
    });
  }

  // Bar chart container
  const barContainer = root.append("div").attr("class", "ms-bars");

  let currentData = data;

  /**
   * Redraw only the bar section (clears barContainer, re-renders comparisonBars
   * and card icons). Called on tier toggle and on update().
   *
   * @param {Object} d - matchStats JSON contract.
   */
  function redrawBars(d) {
    barContainer.selectAll("*").remove();

    const filteredRows = d.rows.filter(r => activeTier === "all" || r.tier === "basic");
    const barRows      = filteredRows.map(toBarRow);

    const barData = {
      left:  { label: d.home.team, color: d.home.color },
      right: { label: d.away.team, color: d.away.color },
      rows:  barRows,
    };

    const { svg } = createComparisonBars(barContainer, barData, barCfg);

    // Card icons are football-specific chrome — appended here, not inside comparisonBars.
    renderCardIcons(svg, d, barCfg, barRows);
  }

  // Initial render
  function initialRender(d) {
    matchLabelEl.text(`${d.metadata.match_label} · ${d.metadata.competition}`);
    fillScoreBlock(scoreEl, d);
    redrawBars(d);
  }

  initialRender(data);

  /**
   * Replace component data and re-render.
   *
   * The match label, score, and bars are all updated. Tier state is preserved unless
   * newConfig.tier is supplied.
   *
   * @param {Object} newData    - New matchStats JSON contract.
   * @param {Object} [newConfig] - Optional config overrides (e.g. { tier: "all" }).
   */
  function update(newData, newConfig = {}) {
    currentData = newData;
    if (newConfig.tier !== undefined) {
      activeTier = newConfig.tier;
      if (btnBasic) {
        btnBasic.attr("class", "ms-tier-btn" + (activeTier === "basic" ? " active" : ""));
        btnAll.attr("class",   "ms-tier-btn" + (activeTier === "all"   ? " active" : ""));
      }
    }
    matchLabelEl.text(`${newData.metadata.match_label} · ${newData.metadata.competition}`);
    fillScoreBlock(scoreEl, newData);
    redrawBars(newData);
  }

  return { root, update };
}
