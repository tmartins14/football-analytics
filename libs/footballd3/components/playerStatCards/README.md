# playerStatCards.js

Six-metric stat-card row for one player: progressive passes, xG, xA/xGChain
(one combined card), pressures + regains, PAdj defensive actions, duels won
%. Hovering a card fires `onHover(layer)` so the caller can emphasize the
matching marker class on the Territory pitch.

## All six cards are scrub-reactive

Every metric recomputes live from whatever scrub-filtered `events` slice the
caller passes into `update({ data: { events } })`:

| Card | Rule |
|---|---|
| Progressive passes | count of Pass events with `is_progressive` |
| xG | sum of `shot_xg` across Shot events |
| xA | sum of `assisted_shot_xg` across Pass events |
| xGChain | sum of `possession_shot_xg`, once per **distinct** `possession` id touched |
| Pressures + regains | count of Pressure events with `pressure_regain` |
| Duels won % | % of Duel events with a winning outcome (`"Won"` or `"Success In Play"`) |
| PAdj defensive actions | raw defensive-action count ÷ (opponent possession % at the scrubbed minute ÷ 50) |

Five of the six live entirely on the player's own `player_events` record —
`assisted_shot_xg` and `possession_shot_xg` were added to
`extract_player_events.py` specifically so xA and xGChain wouldn't need a
separate summary fetch. **PAdj defensive actions is the one exception**: it
needs whole-match opponent-possession context, which a single player's own
event slice can't carry. That comes from the separate `possessionShares` prop
— `extract_possession_shares.py`'s match-level (not per-player), minute-
bucketed output — plus `playerTeam` to know which of the bucket's two teams
is the opponent. Missing either renders `"—"` rather than a stale number.

This replaces an earlier design where xA/xGChain/PAdj came from a per-player
`extract_player_match_summary.py` file as fixed match-totals that didn't move
with the scrubber — superseded once the two fields above landed on
`extract_player_events.py` and `extract_possession_shares.py` supplied the
one genuinely match-wide input.

## JSON contract (consumed)

Four inputs, passed together as `data`:

- `events` — the `player_events/{match_id}/{player_id}.json` contract
  (`{ events: [...] }`), scrub-filtered by the caller.
- `possessionShares` — `possession_shares_{match_id}.json`'s contents
  (`{ buckets: [{ upto_minute, team_possession_pct }, ...] }`), from
  `extract_possession_shares.py`. Shared across every player — fetch once per
  match, not per selection, and don't scrub-filter it (this component picks
  the right bucket itself).
- `playerTeam` — the selected player's own team name (must match one of
  `possessionShares`' bucket keys).
- `scrubbedMinute` — current scrub position, for picking the PAdj bucket.
  Defaults to the max minute present in `events` when omitted.

## Usage

```js
import { createPlayerStatCards } from "./playerStatCards.js";

const { update } = createPlayerStatCards(d3.select("#cards-container"), {
  events: playerEvents,
  possessionShares,
  playerTeam: "Spain",
  scrubbedMinute: 90,
}, {
  onHover: (layer) => {
    // layer or null — matches actionFeed.js's classifyLayer vocabulary,
    // plus "defensive" for the PAdj card's combined defensive-action set.
  },
});

// Scrubber moves — a bare {events} tick is enough; update() merges over the
// previous possessionShares/playerTeam rather than requiring them every call.
update({ data: {
  events: playerEvents.filter((e) => e.minute <= scrubbedMinute),
  scrubbedMinute,
} });
```

## Returns

`{ container, update }`:

- `container` — the card-row D3 selection (a CSS grid `<div>`).
- `update({ data? })` — re-renders with a new data object, merged over the
  previous one (only the keys you pass are replaced).

## Layout

Renders a 3-column CSS grid by default (3×2). For the design's <560px
breakpoint (2×3), the caller should override
`container.style("grid-template-columns", "repeat(2, 1fr)")` — this component
doesn't do its own container-width measurement (the React panel wrapper owns
`ResizeObserver`/breakpoint logic, matching every other panel in this app).

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `onHover` | `null` | `onHover(layer \| null)` on card hover/unhover |

## Extraction

Reads `extract_player_events.py`'s output (five of six cards) and
`extract_possession_shares.py`'s output (PAdj defensive actions).
