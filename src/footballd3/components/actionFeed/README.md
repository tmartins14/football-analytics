# actionFeed.js

Scrollable, sortable chronological log of one player's actions. Each row:
minute, action type, outcome, and a signed xT-swing bar from a centered zero
baseline. Rows are color-coded to the app's shared layer taxonomy; shots are
visually distinct via that same coding.

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

## Signed xT-swing bar

Pass/Carry rows use their own `xt_delta` (can be negative — a backward safety
pass draws on the loss side). Shot rows have no `xt_delta` (only Pass/Carry
are credited toward cumulative xT, per `extract_player_events.py`) but still
need a bar, so they use `shot_xg` instead, always drawn on the gain side — a
shot is inherently threat-positive. Every other event type has no threat
value and renders a zero-width bar (a thin center tick, not a hidden row).

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
| `highlightEventId` | `null` | Inbound cross-link — tints/rings the row with this `event_id` |
| `onHoverRow` | `null` | `onHoverRow(eventId \| null)` on row hover/unhover |

## Extraction

No dedicated extractor — reads `extract_player_events.py`'s output directly,
same as `passSonar.js`, `cumulativeXtChart.js`, and `scrubber.js`.
