# timelineStrip.js

Single-possession elapsed-seconds timeline strip. Renders all events in one possession
along a horizontal real-time axis, showing *when* each event happened within the
possession's tempo.

This component does **not** compose on `pitch.js` — it is a standalone temporal chart,
not a spatial overlay.

## What it shows

Each event is a colored circle with a single-letter abbreviation, positioned at its true
elapsed seconds from the possession's first event. Events that occur within 0.4 seconds of
each other are stacked vertically (deterministic bin-based stacking) so nothing overlaps.
A thin connector line links each stacked glyph to its true position on the axis.

Tooltips on hover show the player name, full event type, outcome (if any), and elapsed
seconds.

## Glyph letter map

| Letter | Types |
|--------|-------|
| P | Pass |
| C | Carry |
| S | Shot |
| D | Pressure, Duel |
| I | Interception |
| B | Ball Recovery, Block |
| X | Clearance |
| R | Ball Receipt* |
| Ds | Dispossessed |
| 50 | 50/50 |
| ? | unmapped types |

## Color encoding (mirrors eventScatter.js)

| Category | Types | Color |
|----------|-------|-------|
| Movement | Pass, Carry, Dribble | `#9F1239` red |
| Defensive | Pressure, Duel, Interception, Block, Ball Recovery, Clearance | `#1E3A5F` navy |
| Terminal | Shot, Foul Won, Foul Committed | `#525252` gray |
| Other | everything else | `#D4D4D4` light gray |

## JSON contract

Reads the same file as `eventScatter.js`:
`src/footballd3/sample_data/possession_{match_id}_{possession}.json`

Only the `seconds` and `event_type` fields drive the layout; `player` and `outcome` appear
in the tooltip.

```json
{
  "events": [
    {
      "event_type": "Pass",
      "seconds":    0.0,
      "player":     "Marc Cucurella",
      "outcome":    null
    },
    {
      "event_type": "Carry",
      "seconds":    1.558,
      "player":     "Nico Williams",
      "outcome":    null
    }
  ]
}
```

Extracted by `src/statsbomb/extract_possession.py`.

## Usage

```js
import { createTimelineStrip } from "./timelineStrip.js";

fetch("../../sample_data/possession_3943043_60.json")
  .then(r => r.json())
  .then(data => {
    const { svg, g, xScale, update } = createTimelineStrip(
      d3.select("#container"),
      data,
      { width: 900, height: 120, glyphRadius: 8 }
    );

    // Later: filter to passes only
    update({ events: data.events.filter(e => e.event_type === "Pass") });
  });
```

## Returns

`{ svg, g, xScale, update }`:

- `svg` — the created SVG selection.
- `g` — the main `<g>` group (use for transforms or overlays).
- `xScale` — `d3.scaleLinear` mapping elapsed seconds → pixels. Exposed for future
  cross-component linking: when a user selects an event on `eventScatter.js`, a future
  slice can use `xScale(event.seconds)` to draw a highlight position on this strip.
- `update({ events? })` — re-renders with a new event array. Designed for additive
  linkage; the component does not need to be rebuilt.

## Notes

- **The axis is real elapsed seconds.** A short possession (3s) will look cramped; a long
  build-up (70s) shows tempo clearly. This is intentional — the strip is a narrative device
  about *when* things happened, not how many.
- **Collision handling is deterministic.** Binned within 0.4s windows; stacking offsets are
  computed from event order within the bin. The same data always renders the same layout.
- **Pair with eventScatter.js** via the shared possession contract. Both components load the
  same JSON file; cross-component selection (hover one, highlight the other) is a future
  additive slice — `xScale` and `update()` are designed to support it without rewrites.
- **Does not compose on pitch.js.** This is a temporal chart; it creates its own SVG.
