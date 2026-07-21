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
 * @param {boolean} [config.showHeader=true] - Render the match-label + score-block
 *   headline above the bars. Pass false when the caller renders its own match header
 *   elsewhere (e.g. a dashboard's dedicated header card) so it isn't duplicated here.
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
export function createMatchStats(selection: import("d3-selection").Selection<any, any, any, any>, data: {
    home: {
        team: string;
        color: string;
        score: number;
    };
    away: {
        team: string;
        color: string;
        score: number;
    };
    rows: Array<any>;
    metadata: {
        match_id: number;
        competition: string;
        match_label: string;
    };
}, config?: {
    tier?: "basic" | "all";
    showTierToggle?: boolean;
    showHeader?: boolean;
    width?: number;
    rowHeight?: number;
    barHeight?: number;
    labelWidth?: number;
    headerHeight?: number;
    paddingY?: number;
}): {
    root: import("d3-selection").Selection<any, any, any, any>;
    update: Function;
};
