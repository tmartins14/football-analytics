# playerStatCards.js

Six-metric stat-card row for one player: progressive passes, xG, xA/xGChain
(one combined card), pressures + regains, PAdj defensive actions, duels won
%. Hovering a card fires `onHover(layer)` so the caller can emphasize the
matching marker class on the Territory pitch.

## Not all six cards are scrub-reactive — a deliberate v1 limit

Four metrics are simple aggregations over a single player's own credited
events, so they recompute live from whatever scrub-filtered `events` slice
the caller passes into `update({ data: { events } })`:

| Card | Rule |
|---|---|
| Progressive passes | count of Pass events with `is_progressive` |
| xG | sum of `shot_xg` across Shot events |
| Pressures + regains | count of Pressure events with `pressure_regain` |
| Duels won % | % of Duel events with a winning outcome (`"Won"` or `"Success In Play"`) |

**xA, xGChain, and PAdj defensive actions cannot be recomputed from one
player's own event slice** — they aggregate across *other* players' shots,
possessions, and team-possession-share, which the per-player fetch model
deliberately does not ship to the client (see `extract_player_events.py`'s
"fetched on selection, not loaded and filtered client-side" design note).
These come from the separate `summary` prop — `extract_player_match_summary.py`'s
match-total output — and do **not** change as the scrubber moves. The card
shows a small "match total" label rather than silently pretending they're live.

## JSON contract (consumed)

Two inputs, passed together as `data`:

- `events` — the `player_events/{match_id}/{player_id}.json` contract
  (`{ events: [...] }`), scrub-filtered by the caller.
- `summary` — the `player_match_summary/{match_id}/{player_id}.json`
  contract's top-level fields (`{ xa, xg_chain, padj_defensive_actions, ... }`),
  from `extract_player_match_summary.py`. Not scrub-filtered.

## Usage

```js
import { createPlayerStatCards } from "./playerStatCards.js";

const { update } = createPlayerStatCards(d3.select("#cards-container"), {
  events: playerEvents,
  summary: playerMatchSummary,
}, {
  onHover: (layer) => {
    // layer or null — matches actionFeed.js's classifyLayer vocabulary,
    // plus "defensive" for the PAdj card's combined defensive-action set.
  },
});

// Scrubber moves — only the four reactive cards actually change value.
update({ data: {
  events: playerEvents.filter((e) => e.minute <= scrubbedMinute),
  summary: playerMatchSummary,
} });
```

## Returns

`{ container, update }`:

- `container` — the card-row D3 selection (a CSS grid `<div>`).
- `update({ data? })` — re-renders with a new `{ events, summary }` object.

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

Reads `extract_player_events.py`'s output for the four reactive cards and
`extract_player_match_summary.py`'s output for the two match-total cards.
