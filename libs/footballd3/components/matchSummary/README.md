# matchSummary.js

Headline, key stats, standout performers, and a free-prose tactics section
for one auto-generated match summary — the output of
`libs/statsbomb/generate_match_summary.py`. Renders HTML (not SVG), like
`actionFeed.js` — a headline, labeled stats, named performers, and prose
paragraphs read and flow naturally as DOM text.

## One-off documentation exception, not a general component

`docs/specs/match-summary/SPEC.md` scopes dashboard rendering of the match
summary generator's output **out** of the feature. This component is a
deliberate, small exception to that scope note. It's built here — this is
where football-analytics builds every footballd3 "view" — but *presented*
from `tylermartins.com`, not from this repo's own legacy
`pages/match-analysis/dashboard.js` (which doesn't render it at all). See
`components/charts/MatchSummaryModal.tsx` and `MatchSummaryPanel.tsx` in the
`tylermartins.com` repo for the actual consumer: a button in the match
header opens it as a modal over the dashboard, resolved via the workspace's
live `footballd3` symlink — no publish step needed.

Its disclaimer text is **hardcoded to match `3943043`'s specific known
issues**, found by the manual per-claim trace in
`docs/specs/match-summary/VERIFICATION-3943043.md`: an off-ball/on-ball
centroid mislabel, the resulting backwards spatial comparison, and a false
hull-membership claim about a player. If this component is ever reused for a
different match's `match_summary.json`, `DISCLAIMER_ISSUES` in
`matchSummary.js` must be revisited — it is not a generic "AI-generated, may
contain errors" notice, and is only accurate for the one match it was written
against.

## JSON contract (consumed)

The raw `match_summary.json` object, passed through unmodified — see
`generate_match_summary.py`'s own module docstring for the authoritative
shape:

```json
{
  "outcome": {
    "headline": "Spain edged England 2-1 in the Euro 2024 final...",
    "key_stats": [
      { "label": "Final Score", "value": "Spain 2 - 1 England", "source_field": "match_stats.home.score & match_stats.away.score" }
    ],
    "standout_performers": [
      { "player": "Aymeric Laporte", "team": "Spain", "reason": "Led Spain's buildup with 48 completed passes...", "source_field": "pass_network.home.windows[0].nodes[0].passes" }
    ]
  },
  "tactics": { "prose": "Both sides set up in a 4-2-3-1...\n\n...\n\n..." },
  "metadata": {
    "match_id": 3943043, "home_team": "Spain", "away_team": "England",
    "competition": "UEFA Euro 2024", "match_label": "Spain vs England", "model": "claude-sonnet-5"
  }
}
```

`tactics.prose` paragraphs are separated by a literal blank line (`"\n\n"`) —
this component does a plain double-newline split, not markdown rendering.
Each `key_stats`/`standout_performers` entry's `source_field` is shown as a
`title` tooltip attribute on its card/row, surfacing provenance without
cluttering the visible text.

## Usage

```js
import { createMatchSummary } from "./matchSummary.js";

const { update } = createMatchSummary(d3.select("#container"), matchSummary, {
  theme: { border, text, muted, faint, focal }, // optional, see Theming below
});
```

## Theming

This component has no live CSS variables of its own — like every other
footballd3 chart, it takes hex config and re-renders when it changes (see
`libs/footballd3/README.md`'s styling notes). `config.theme` accepts
`{ border, text, muted, faint, focal }`; any key you omit falls back to this
component's light-mode default. `update({ theme })` re-renders with a new
theme without unmounting, so a caller's own light/dark toggle can just call
`update` again rather than remount the whole component.

`tylermartins.com`'s `MatchSummaryPanel.tsx` is the reference consumer: it
resolves the active theme via `next-themes`' `useTheme()`, looks up the
matching table in `lib/chart-theme.ts`'s `CHART_THEME`, and passes that
straight through — the same pattern `ShotMapPanel.tsx` and every other
theme-aware chart wrapper there already uses.

## Returns

`{ container, update }`:

- `container` — the panel's root D3 selection.
- `update({ data?, theme? })` — re-renders with a new data and/or theme
  object, each merged over its previous value independently.

## Layout

Disclaimer renders first, above the headline — unmissable, not buried after
the tactics prose. Key stats render as a flat auto-fill CSS grid of cards
(closest existing precedent: `playerStatCards.js`'s `.stat-card` pattern,
under distinct `.match-summary-stat-*` class names to avoid collision if both
components ever load on the same page).

## Extraction

Reads `libs/statsbomb/generate_match_summary.py`'s output
(`data/euro-2024/{match_id}/match_summary.json`).
