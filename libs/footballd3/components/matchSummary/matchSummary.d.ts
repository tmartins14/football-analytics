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
export function createMatchSummary(selection: import("d3-selection").Selection<any, any, any, any>, data: {
    outcome: {
        headline: string;
        key_stats: Array<{
            label: string;
            value: string;
            source_field: string;
        }>;
        standout_performers: Array<{
            player: string;
            team: string;
            reason: string;
            source_field: string;
        }>;
    };
    tactics: {
        prose: string;
    };
    metadata: {
        match_id?: number;
        home_team?: string;
        away_team?: string;
        competition?: string;
        match_label?: string;
        model?: string;
        source_files?: any;
    };
}, config?: {
    theme?: {
        border?: string;
        text?: string;
        muted?: string;
        faint?: string;
        focal?: string;
    };
}): {
    container: import("d3-selection").Selection<any, any, any, any>;
    update: Function;
};
