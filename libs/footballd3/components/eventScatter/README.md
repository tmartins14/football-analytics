# eventScatter.js

General-purpose event scatter overlay for a StatsBomb 120×80 pitch. Renders any flat
events array as shape-coded markers on the pitch; events with end coordinates (Pass, Carry,
Shot) also draw an arrow from origin to destination.

This component is not possession-specific. A possession is one filtered event set; you can
pass match-level events, player-filtered events, or any other subset.

## What it shows

- **Shaped marker at (x, y)**: every event's origin position. Shape encodes the event's
  layer category, fill vs. hollow encodes whether it succeeded — see "Shape + outcome
  encoding" below.
- **Arrow to (end_x, end_y)**: drawn for events that carry a destination (Pass, Carry, Shot).
- **Tooltip on hover**: player name (if given — omit `player` when every event
  already belongs to one known player, e.g. a single-player whole-match view;
  the line is skipped rather than showing "undefined"), event type, outcome
  (if any), and a timestamp — `{minute}'` if `minute` is present (a
  whole-match/single-player view), else `+X.Xs` elapsed within the possession
  (the possession-scoped shape below).

## Shape + outcome encoding

Shape and color no longer both encode category — shape does, and every marker/arrow
renders in one ink color (`config.markerColor`, themable). This mirrors
`actionFeed.js`'s own row glyphs exactly (both import the same `CATEGORY_SHAPE` map)
so the Territory pitch and the Action Feed speak one consistent visual language:

| Category           | Shape (`CATEGORY_SHAPE`) |
|---------------------|--------------------------|
| `shot`              | circle                   |
| `progressive_pass`  | triangle                 |
| `key_pass`          | diamond                  |
| `pressure`          | square                   |
| `duel`              | cross                    |
| `turnover`          | star                     |
| `other`             | wye                      |

Category is derived locally (`_classify`, mirroring `actionFeed.js`'s `classifyLayer`,
adapted to this component's `event_type` field name) rather than imported directly — this
component's general possession contract doesn't carry `is_progressive`/`key_pass` at all,
so importing the player-events-specific classifier as-is would silently misclassify events
for that consumer. A caller with those fields (e.g. `TerritoryPanel.tsx`) can pass them
through per-event for classification that agrees exactly with the Action Feed's.

Fill vs. hollow (`_isSuccessful`, same adaptation) encodes outcome: filled means the event
succeeded, hollow means it didn't. Shot succeeds iff `outcome === "Goal"`; Duel succeeds
unless `outcome` names a loss; Pass/Carry succeed when `outcome` is `null`; everything else
has no real success/fail concept and defaults to filled.

**Ball Receipt\***: excluded by default — they cluster on top of Pass end-points with no
additional spatial information. Set `includeBallReceipt: true` to include them.

## JSON contract

Reads from `libs/footballd3/sample_data/possession_{match_id}_{possession}.json`
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

`player` and `seconds` are only needed for this possession-scoped shape (see
tooltip behavior above). A whole-match/single-player consumer — e.g.
`TerritoryPanel.tsx` on the Player Match Analysis page — passes `minute`
instead of `seconds`, and omits `player` entirely.
`outcome` is non-null only for failed passes; `null` means the pass was completed.

Extracted by `libs/statsbomb/extract_possession.py`.

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
