# eventScatter.js

General-purpose event scatter overlay for a StatsBomb 120×80 pitch. Renders any flat
events array as color-coded markers on the pitch; events with end coordinates (Pass, Carry,
Shot) also draw an arrow from origin to destination.

This component is not possession-specific. A possession is one filtered event set; you can
pass match-level events, player-filtered events, or any other subset. The encoding (colors,
arrows) is driven by `event_type` and is fully configurable via `colorScale`.

## What it shows

- **Circle at (x, y)**: every event's origin position, color-coded by semantic category.
- **Arrow to (end_x, end_y)**: drawn for events that carry a destination (Pass, Carry, Shot).
  Failed passes get an outer ring around the origin dot to distinguish them from completions.
- **Tooltip on hover**: player name, event type, outcome (if any), and elapsed seconds within
  the possession.

## Event type color encoding

| Category   | Types                                                    | Color                |
|------------|----------------------------------------------------------|----------------------|
| Movement   | Pass, Carry, Dribble                                     | `#9F1239` red        |
| Defensive  | Pressure, Duel, Interception, Block, Ball Recovery, Clearance | `#1E3A5F` navy |
| Terminal   | Shot, Foul Won, Foul Committed                           | `#525252` gray       |
| Other      | everything else                                          | `#E5E5E5` light gray |

Override the color function via `config.colorScale` to use a custom scheme.

**Ball Receipt\***: excluded by default — they cluster on top of Pass end-points with no
additional spatial information. Set `includeBallReceipt: true` to include them.

## JSON contract

Reads from `src/footballd3/sample_data/possession_{match_id}_{possession}.json`
(or any object with an `events` array in this shape):

```json
{
  "match_id": 3943043,
  "possession": 60,
  "team": "Spain",
  "events": [
    {
      "event_id":   "uuid-string",
      "event_type": "Pass",
      "seconds":    0.0,
      "x":          37.8,
      "y":          15.5,
      "end_x":      56.6,
      "end_y":      24.7,
      "player":     "Marc Cucurella",
      "outcome":    null
    }
  ],
  "metadata": { "match_id": 3943043, "possession": 60, "team": "Spain", ... }
}
```

`end_x`/`end_y` are non-null for Pass, Carry, and Shot events; `null` for all others.
`outcome` is non-null only for failed passes; `null` means the pass was completed.

Extracted by `src/statsbomb/extract_possession.py`.

## Usage

```js
import { createPitch }        from "../pitch/pitch.js";
import { createEventScatter } from "./eventScatter.js";

const pitch = createPitch(d3.select("#svg"), { mode: "full", pxPerYard: 7 });

fetch("../../sample_data/possession_3943043_60.json")
  .then(r => r.json())
  .then(data => {
    const { g, update } = createEventScatter(pitch, data, {
      markerRadius:       5,
      showArrows:         true,
      includeBallReceipt: false,
    });

    // Later: filter to passes only
    update({ filter: e => e.event_type === "Pass" });

    // Or replace with a different event array entirely
    update({ events: someOtherEventsArray });
  });
```

## Returns

`{ g, update }`:

- `g` — the `<g class="es">` D3 selection appended to `pitch.g`. Use to add overlays or
  apply transforms without re-rendering.
- `update({ events?, filter? })` — re-renders with a new event array (`events`) or a
  predicate function (`filter: (event) => boolean`). Designed for additive future cross-
  component selection linkage; does not require rebuilding the component.

## Notes

- Composes on `pitch.js`: call `createPitch()` first, then pass the return value here.
- Coordinates are StatsBomb-native 120×80 yards; `pitch.px()` handles all pixel mapping.
- Arrow marker IDs are prefixed `es-` to avoid collision with `progressiveMap.js` markers
  when both components share the same SVG.
- The component is general: it renders *any* events array. The possession JSON is just the
  showcase data source; the component has no notion of "possession".
