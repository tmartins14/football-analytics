/**
 * matchSummary.js — headline, key stats, standout performers, and free-prose
 * tactics paragraphs for one auto-generated match summary.
 *
 * Like actionFeed.js, this renders HTML (not SVG) — a headline, labeled
 * stats, named performers, and prose paragraphs read and flow naturally as
 * DOM text, not SVG text nodes.
 *
 * ONE-OFF DOCUMENTATION EXCEPTION, NOT A GENERAL COMPONENT
 * docs/specs/match-summary/SPEC.md scopes dashboard rendering of the match
 * summary generator's output OUT of the feature. This component is a
 * deliberate, small exception to that scope note, wired into
 * pages/match-analysis/dashboard.js only, for documentation purposes — it is
 * not meant to be a real feature surface.
 *
 * DISCLAIMER TEXT IS HARDCODED TO MATCH 3943043's KNOWN ISSUES
 * The disclaimer rendered above the headline names three specific defects
 * found in docs/specs/match-summary/VERIFICATION-3943043.md's manual
 * per-claim trace of THIS match's generated tactics prose (an off-ball/
 * on-ball centroid mislabel, the resulting backwards spatial comparison, and
 * a false hull-membership claim about a player). If this component is ever
 * reused for a different match's match_summary.json, DISCLAIMER_ISSUES below
 * must be revisited — it is not a generic "AI-generated" notice, and is only
 * accurate for the one match it was written against.
 */

const DISCLAIMER_ISSUES = [
  "The prose labels Spain's and England's shape centroids as \"on-ball\" — they are actually off-ball (out-of-possession) centroids from team_shape_spain.json/team_shape_england.json. The coordinate values are copied correctly; only the on-ball/off-ball label is wrong.",
  "Because of that mislabel, the claim that England sat more central than Spain is backwards: pitch center is y=40, and England's cited y (39.2) is actually closer to center than Spain's (41.4).",
  "The prose describes England's first-half possession hull as running \"through Stones and Guehi.\" Guehi is a real hull vertex, but Stones is not — his position places him inside the shape, not on its boundary.",
];

// Light-mode defaults — the legacy dashboard.js consumer doesn't pass a
// `theme` config, so these hex values preserve exactly what this component
// looked like before theming existed. A consumer with its own light/dark
// token table (e.g. tylermartins.com's CHART_THEME) overrides some or all of
// these via config.theme — the same "vendored component takes hex config,
// not live CSS vars" convention every other footballd3 chart wrapper uses.
const DEFAULT_THEME = {
  border: "#E5E5E5",
  text: "#171717",
  muted: "#525252",
  faint: "#8A8578",
  focal: "#9F1239",
};

/**
 * Render the match-summary panel: disclaimer, headline, key stats, standout
 * performers, and tactics prose.
 *
 * @param {d3.Selection} selection - D3 selection of the container element
 *   (an HTML element — this component renders div/p/ul children, not an SVG
 *   root).
 * @param {Object} data - The raw `match_summary.json` object, passed through
 *   unmodified.
 * @param {Object} data.outcome - `{ headline, key_stats, standout_performers }`.
 * @param {string} data.outcome.headline - One-sentence summary of the outcome.
 * @param {Array<Object>} data.outcome.key_stats - `{ label, value, source_field }` entries.
 * @param {Array<Object>} data.outcome.standout_performers - `{ player, team, reason, source_field }` entries.
 * @param {Object} data.tactics - `{ prose }` — free-prose tactics text,
 *   paragraphs separated by a literal blank line (`"\n\n"`).
 * @param {Object} data.metadata - `{ match_label, competition, model, ... }`,
 *   shown in the footer caption.
 * @param {Object} [config={}] - Rendering options.
 * @param {Object} [config.theme] - `{ border, text, muted, faint, focal }`
 *   hex colors, merged over the light-mode defaults. Pass a dark-mode table
 *   (e.g. a subset of tylermartins.com's `CHART_THEME.dark`) so the panel
 *   reads correctly on a dark surface — this component has no live CSS
 *   variables of its own to fall back on.
 * @returns {{ container: d3.Selection, update: Function }}
 *   container — the panel's root D3 selection.
 *   update({ data?, theme? }) — re-renders with a new data and/or theme
 *     object, each merged over its previous value independently.
 */
export function createMatchSummary(selection, data, config = {}) {
  const container = selection.append("div")
    .attr("class", "match-summary")
    // Long unbroken tokens (source-JSON filenames in the disclaimer, e.g.
    // "team_shape_spain.json/team_shape_england.json") can overflow a narrow
    // modal instead of wrapping. min-width:0 also guards the flexbox case —
    // both this legacy dashboard's .modal-panel and tylermartins.com's
    // Dialog.Popup are flex columns, where a flex item's default min-width
    // resists shrinking below its content's intrinsic width.
    .style("overflow-wrap", "break-word")
    .style("word-break", "break-word")
    .style("min-width", "0");

  let currentData = data;
  let currentTheme = { ...DEFAULT_THEME, ...(config.theme ?? {}) };

  function render() {
    container.selectAll("*").remove();

    const { outcome, tactics, metadata } = currentData;
    const theme = currentTheme;
    // Low-alpha tint of the theme's focal color — replaces a separate
    // hardcoded "soft" hex per theme, and adapts automatically to whatever
    // focal color the caller passes.
    const focalSoft = `${theme.focal}1F`;

    // ── Disclaimer — rendered first, above the headline, unmissable ──
    const disclaimer = container.append("div")
      .attr("class", "match-summary-disclaimer")
      .style("border", `1px solid ${theme.focal}`)
      .style("border-left", `4px solid ${theme.focal}`)
      .style("background", focalSoft)
      .style("border-radius", "6px")
      .style("padding", "14px 16px")
      .style("margin-bottom", "24px")
      .style("font-size", "13px")
      .style("line-height", "1.6")
      .style("color", theme.text);

    disclaimer.append("div")
      .attr("class", "match-summary-disclaimer-label")
      .style("font-family", "Geist Mono, monospace")
      .style("font-size", "11px")
      .style("font-weight", "600")
      .style("letter-spacing", "0.04em")
      .style("text-transform", "uppercase")
      .style("color", theme.focal)
      .style("margin-bottom", "8px")
      .text("⚠ AI-generated summary — verified issues below");

    disclaimer.append("p")
      .style("margin", "0 0 8px 0")
      .text(
        "This summary was generated by an LLM from structured match data and " +
        "manually verified once. The structured stats and performers below " +
        "(12 of 12 claims) were verified exactly correct. The tactics " +
        "paragraphs below (11 of 15 claims fully grounded) contain three " +
        "known issues, left uncorrected on purpose:"
      );

    disclaimer.append("ul")
      .attr("class", "match-summary-disclaimer-issues")
      .style("margin", "0 0 8px 0")
      .style("padding-left", "20px")
      .selectAll("li")
      .data(DISCLAIMER_ISSUES)
      .join("li")
      .style("margin-bottom", "6px")
      .text((d) => d);

    disclaimer.append("p")
      .style("margin", "0")
      .style("color", theme.muted)
      .text(
        "No automated evaluation exists yet for this feature — that's " +
        "Module 3 of the curriculum, not built here. Full claim-by-claim " +
        "trace: docs/specs/match-summary/VERIFICATION-3943043.md."
      );

    // ── Headline ──
    container.append("h2")
      .attr("class", "match-summary-headline")
      .style("font-family", "Fraunces, serif")
      .style("font-size", "20px")
      .style("font-weight", "900")
      .style("line-height", "1.25")
      .style("margin-bottom", "20px")
      .style("color", theme.text)
      .text(outcome.headline);

    // ── Key stats ──
    const stats = container.append("div")
      .attr("class", "match-summary-stats")
      .style("display", "grid")
      .style("grid-template-columns", "repeat(auto-fill, minmax(150px, 1fr))")
      .style("gap", "10px")
      .style("margin-bottom", "24px");

    const statCards = stats.selectAll(".match-summary-stat-card")
      .data(outcome.key_stats)
      .join("div")
      .attr("class", "match-summary-stat-card")
      .attr("title", (d) => d.source_field)
      .style("border", `1px solid ${theme.border}`)
      .style("border-radius", "8px")
      .style("padding", "10px 12px");

    statCards.append("div")
      .attr("class", "match-summary-stat-label")
      .style("font-family", "Geist Mono, monospace")
      .style("font-size", "10px")
      .style("letter-spacing", "0.04em")
      .style("text-transform", "uppercase")
      .style("color", theme.faint)
      .style("margin-bottom", "4px")
      .text((d) => d.label);

    statCards.append("div")
      .attr("class", "match-summary-stat-value")
      .style("font-size", "16px")
      .style("font-weight", "600")
      .style("color", theme.text)
      .text((d) => d.value);

    // ── Standout performers ──
    const performers = container.append("div")
      .attr("class", "match-summary-performers")
      .style("margin-bottom", "24px");

    performers.append("h3")
      .style("font-family", "Fraunces, serif")
      .style("font-size", "14px")
      .style("font-weight", "900")
      .style("margin-bottom", "10px")
      .style("color", theme.text)
      .text("Standout performers");

    const performerRows = performers.selectAll(".match-summary-performer-row")
      .data(outcome.standout_performers)
      .join("div")
      .attr("class", "match-summary-performer-row")
      .attr("title", (d) => d.source_field)
      .style("padding", "8px 0")
      .style("border-bottom", `1px solid ${theme.border}`);

    performerRows.append("span")
      .attr("class", "match-summary-performer-name")
      .style("font-weight", "600")
      .style("margin-right", "6px")
      .style("color", theme.text)
      .text((d) => d.player);

    performerRows.append("span")
      .attr("class", "match-summary-performer-team")
      .style("font-family", "Geist Mono, monospace")
      .style("font-size", "11px")
      .style("color", theme.muted)
      .text((d) => `(${d.team})`);

    performerRows.append("div")
      .attr("class", "match-summary-performer-reason")
      .style("color", theme.muted)
      .style("margin-top", "2px")
      .text((d) => d.reason);

    // ── Tactics prose ──
    const tacticsEl = container.append("div")
      .attr("class", "match-summary-tactics")
      .style("margin-bottom", "16px");

    tacticsEl.append("h3")
      .style("font-family", "Fraunces, serif")
      .style("font-size", "14px")
      .style("font-weight", "900")
      .style("margin-bottom", "10px")
      .style("color", theme.text)
      .text("Tactics");

    const paragraphs = (tactics.prose ?? "").split("\n\n").filter((p) => p.length > 0);
    tacticsEl.selectAll(".match-summary-tactics-p")
      .data(paragraphs)
      .join("p")
      .attr("class", "match-summary-tactics-p")
      .style("margin-bottom", "12px")
      .style("color", theme.text)
      .text((d) => d);

    // ── Footer caption ──
    container.append("div")
      .attr("class", "caption match-summary-footer")
      .style("font-family", "Geist Mono, monospace")
      .style("font-size", "10px")
      .style("color", theme.muted)
      .text(`${metadata.match_label} · ${metadata.competition} · model: ${metadata.model}`);
  }

  render();

  /**
   * Re-render with a new data and/or theme object.
   *
   * @param {Object} [next={}] - Partial update.
   * @param {Object} [next.data] - Replacement `match_summary.json` object —
   *   merged over the previous data, so passing a partial object only
   *   replaces the keys you pass.
   * @param {Object} [next.theme] - Replacement theme colors — merged over
   *   the previous theme, independently of `data`. Pass this when the
   *   caller's own color mode changes (e.g. a light/dark toggle) rather than
   *   unmounting and remounting the whole component.
   */
  function update(next = {}) {
    if (next.data !== undefined) currentData = { ...currentData, ...next.data };
    if (next.theme !== undefined) currentTheme = { ...currentTheme, ...next.theme };
    render();
  }

  return { container, update };
}
