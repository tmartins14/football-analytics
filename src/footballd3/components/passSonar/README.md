# passSonar.js

Polar bearing/length chart of one player's passes. Bins every Pass event by
its direction of travel into equal angular sectors and draws two nested
wedges per sector: an outer stroked-only wedge sized to that sector's total
**attempted** pass count, and an inner filled wedge sized to its **completed**
count.

## Forward is always up — no per-team flip needed

Unlike `pitch.js`/`formation.js` (which draw both teams on one shared surface
and so need a `flipAttack`/orientation config), a pass sonar is per-player and
per-team. StatsBomb stores each event's location relative to the **acting
team's own attacking direction** — x always runs from that team's own goal
(0) toward the opponent's goal (120), for both halves and both teams. This
was verified against the Euro 2024 Final's shot locations: every team's shots
cluster near x≈105–108 in *both* periods; a coordinate flip at half-time or
between teams would put one side's shots near x≈15 instead. So "forward" is
always `end_x - x > 0` — no attacking-direction prop to configure or get wrong.

## Bearing → screen angle

`bearing = atan2(dy, dx)` where `dx = end_x - x` (forward) and
`dy = end_y - y` (lateral — StatsBomb y increases toward one touchline).
Bearing 0 (pure forward) is drawn at 12 o'clock; positive bearing sweeps
clockwise toward the `+y` touchline side.

## Many-events-per-wedge hover linking

A wedge aggregates every pass in its bin, so — unlike a single pitch marker
or feed row — it can't map to one `event_id`. `onHover` fires with
`{ bin, eventIds: string[] }` (every underlying pass's `event_id`), and the
inbound `highlightEventId` rings whichever bin **contains** that id. This is
a deliberate many-to-one version of the app's usual one-to-one event-scope
highlight — see the module docstring for the full reasoning.

## JSON contract (consumed)

Same `player_events/{match_id}/{player_id}.json` shape every other panel
reads (from `extract_player_events.py`) — or any object with the same
`{ events: [...] }` shape. Non-Pass events and passes without an
`end_location` are ignored, so callers may pass the full unfiltered file.

```json
{
  "events": [
    { "event_id": "...", "type": "Pass", "location": [60, 40],
      "end_location": [75, 32], "outcome": null },
    { "event_id": "...", "type": "Pass", "location": [55, 20],
      "end_location": [40, 25], "outcome": "Incomplete" }
  ]
}
```

`outcome === null` means completed (same convention as `utils.pass_outcome`
and every other panel reading this contract).

## Usage

```js
import { createPassSonar } from "./passSonar.js";

const { update } = createPassSonar(d3.select("#sonar-container"), data, {
  width: 280,
  height: 280,
  numBins: 16,
  onHover: (hover) => {
    // hover is { bin, eventIds } or null — cross-highlight every eventIds
    // entry on the pitch/feed/xT-line, per the app's event-scope linking.
  },
});

// Scrub-filtered subset + an inbound highlight from a hovered feed row:
update({
  data: { events: playerEvents.filter((e) => e.minute <= scrubbedMinute) },
  highlightEventId: hoveredEventId,
});
```

## Returns

`{ svg, g, update }`:

- `svg` — the created SVG selection.
- `g` — the main `<g>` group, centered in the SVG.
- `update({ data?, highlightEventId? })` — re-renders with new events and/or
  moves the inbound highlight ring. Any omitted key retains its current value.

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `width` | `280` | SVG width in pixels |
| `height` | `280` | SVG height in pixels |
| `numBins` | `16` | Angular sectors |
| `attemptedColor` | `"#9F1239"` | Outer wedge stroke color |
| `completedColor` | `"#9F1239"` | Inner wedge fill color |
| `highlightColor` | `"#F59E0B"` | Ring color for the bin containing `highlightEventId` |
| `highlightEventId` | `null` | Inbound cross-link — rings whichever bin contains a pass with this `event_id` |
| `onHover` | `null` | `onHover({ bin, eventIds } \| null)` on wedge hover/unhover |
| `showTooltip` | `true` | Render the built-in floating tooltip (attempted/completed counts) |

## Extraction

No dedicated extractor — reads `extract_player_events.py`'s output directly,
same as `cumulativeXtChart.js` and `scrubber.js`.
