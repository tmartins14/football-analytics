# actionFeed.js

Scrollable, sortable chronological log of one player's actions. Each row:
a shape+fill category glyph, minute, action type, outcome, a formatted
xT/xG value, and a signed xT-swing bar from a centered zero baseline.

## HTML, not SVG

Unlike every other `footballd3` component, this one renders HTML rows (not an
SVG root) inside a fixed-height, scrollable `<div>` — a chronological log
reads and scrolls more naturally as DOM text, and native scroll behavior
(`overflow-y: auto`) is simpler than an SVG viewport hack. Each row still gets
a small inline SVG for its signed xT-swing bar, matching the rest of the
library's visual language.

## Layer classification is shared, not local

`classifyLayer(event)` is a **named export**, not a private helper — the
design's layer-toggle chips ("Progressive pass | Key pass | Pressure | Duel |
Turnover | Shot") must filter both the Territory pitch markers and this feed
identically. Import it wherever `activeLayers` filtering happens rather than
re-deriving the classification:

| Layer | Rule |
|---|---|
| `shot` | `type === "Shot"` |
| `key_pass` | `type === "Pass" && key_pass` |
| `progressive_pass` | `(type === "Pass" \|\| type === "Carry") && is_progressive` |
| `pressure` | `type === "Pressure"` |
| `duel` | `type === "Duel"` |
| `turnover` | `type === "Dispossessed" \|\| type === "Miscontrol"` |
| `other` | everything else |

## Shape + fill category glyph

Each row's leading glyph replaces the old per-category color scheme with two
independent visual channels — shared with `eventScatter.js`'s pitch markers
via the exported `CATEGORY_SHAPE` map, so both consumers speak the same
visual language:

- **Shape** encodes the layer category (`CATEGORY_SHAPE`, a d3-symbol type
  per category): `shot` → circle, `progressive_pass` → triangle, `key_pass`
  → diamond, `pressure` → square, `duel` → cross, `turnover` → star, `other`
  → wye.
- **Ink color** (`config.iconColor`, default `#525252`) is a single flat
  color for every glyph — a caller with a team/player color scheme (e.g.
  the Player Match Analysis page) passes the selected player's team color
  instead, so a Spain player's feed renders in Spain red and an England
  player's in England blue.
- **Filled vs. hollow** encodes whether the event succeeded
  (`isSuccessfulEvent(event)`, also exported): filled means it succeeded,
  hollow means it didn't. Shot succeeds iff `is_goal`; Duel succeeds unless
  its `outcome` names a loss (StatsBomb's real vocabulary is "Success In
  Play"/"Won" vs. "Lost In Play"/"Lost Out" — matched by substring, not an
  exact list); Pass/Carry succeed when `outcome` is `null` (StatsBomb's own
  convention: a populated outcome on those types names the failure); every
  other type has no real success/fail concept and defaults to filled.

## Signed xT-swing value + bar

Pass/Carry rows use their own `xt_delta` (can be negative — a backward safety
pass draws on the loss side). Shot rows have no `xt_delta` (only Pass/Carry
are credited toward cumulative xT, per `extract_player_events.py`) but still
need a bar, so they use `shot_xg` instead, always drawn on the gain side — a
shot is inherently threat-positive. Every other event type has no threat
value and renders a zero-width bar (a thin center tick, not a hidden row).

Next to the bar, a formatted text value (`formatSwing()`): signed 3-decimal
`+0.220 xT` / `-0.045 xT` for Pass/Carry, unsigned 2-decimal `xG 0.32` for
Shot, and blank for every other event type — a literal `0.000 xT` on every
zero-tick row would be noise, not information.

## JSON contract (consumed)

Same `player_events/{match_id}/{player_id}.json` shape every other panel
reads. Pass the caller's own scrub-filtered slice (`minute <= scrubbedMinute`)
— this component does not filter by minute itself, matching
`cumulativeXtChart.js`'s convention of trusting the caller's slice.

## Usage

```js
import { createActionFeed, classifyLayer } from "./actionFeed.js";

const { update } = createActionFeed(d3.select("#feed-container"), data, {
  height: 320,
  sortBy: "minute",
  sortDir: "asc",
  onHoverRow: (eventId) => {
    // eventId or null — cross-highlight the matching pitch marker/xT point/sonar bin.
  },
});

// Player picks "Sort by xT, descending":
update({ sortBy: "xt", sortDir: "desc" });

// Scrub advances, and a pitch marker elsewhere is hovered:
update({
  data: { events: playerEvents.filter((e) => e.minute <= scrubbedMinute) },
  highlightEventId: hoveredEventId,
});
```

## Returns

`{ container, update }`:

- `container` — the scroll-container D3 selection (the `<div class="action-feed">`).
- `update({ data?, sortBy?, sortDir?, highlightEventId? })` — re-renders with
  new events, a new sort, and/or a new inbound highlight. Any omitted key
  retains its current value.

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `height` | `320` | Scroll container height in pixels |
| `sortBy` | `"minute"` | `"minute"` \| `"xt"` |
| `sortDir` | `"asc"` | `"asc"` \| `"desc"` |
| `iconColor` | `"#525252"` | Ink color for each row's shape+fill/hollow category glyph — a caller with a team/player color scheme overrides this per player |
| `highlightEventId` | `null` | Inbound cross-link — tints/rings the row with this `event_id` |
| `onHoverRow` | `null` | `onHoverRow(eventId \| null)` on row hover/unhover |

## Extraction

No dedicated extractor — reads `extract_player_events.py`'s output directly,
same as `passSonar.js`, `cumulativeXtChart.js`, and `scrubber.js`.
