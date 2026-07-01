# shotMap

Overlays shot events from the StatsBomb JSON contract onto a half-pitch. Each
shot is a circle — area encodes xG, color encodes outcome. Hovering a circle
shows a tooltip with player display name, outcome, match minute, and xG.

Internally calls `createPitch` in `mode: "half"`. All StatsBomb shots have
x > 60 (the library normalises attacks left→right); the component mirrors them
onto the half-pitch automatically via `mirroredX = 120 − shot.x`.

## JSON contract (input)

One object per shot. Produced by `src/statsbomb/extract_shots.py`.

```json
[
  {
    "x": 108.0,
    "y": 38.5,
    "xg": 0.28,
    "outcome": "Goal",
    "is_goal": true,
    "team": "Spain",
    "display_name": "Mikel Oyarzabal",
    "minute": 86
  }
]
```

Coordinates are StatsBomb-native (120×80 yards, origin top-left). Do not
transform them before passing — the component handles pixel mapping.

## Usage

```js
import { createShotMap } from "./shotMap.js";

const shots = await fetch("../../sample_data/shots_3943043.json").then(r => r.json());

// Render all shots
createShotMap(d3.select("#svg"), shots);

// Per-team vertical panels (conventional shot map layout)
const teams = [...new Set(shots.map(s => s.team))].sort();
createShotMap(d3.select("#svg-a"), shots.filter(s => s.team === teams[0]), { orientation: "vertical", pxPerYard: 7 });
createShotMap(d3.select("#svg-b"), shots.filter(s => s.team === teams[1]), { orientation: "vertical", pxPerYard: 7 });
```

## Config options

`mode` is always `"half"` and is not configurable. Other pitch options pass through:

| Option | Type | Default | Description |
|---|---|---|---|
| `pxPerYard` | number | `8` | Scale factor passed to `createPitch` |
| `orientation` | `"horizontal"` \| `"vertical"` | `"horizontal"` | `"vertical"` is the conventional shot map orientation (goal at top) |
| `theme` | string \| object | `"whiteboard"` | Passed to `createPitch` — see pitch README |

## Return shape

`{ g, px }` — the same shape `createPitch` returns, so the caller can append
additional elements to `g` or reuse `px` for further coordinate mapping.

## Visual encoding

| Property | Encoding |
|---|---|
| xG | Circle radius via `d3.scaleSqrt`, domain `[0, 0.5]`, range `[3, 14]` px |
| Goal (`is_goal: true`) | Fill `#9F1239` at 0.9 opacity |
| Non-goal | Fill `#1E3A5F` at 0.45 opacity |
| All circles | `#FAF7F0` stroke, 1 px |

## Hover tooltip

Displayed on `mouseover`, follows cursor on `mousemove`, hidden on `mouseout`.
Shows player display name, outcome, minute, and xG formatted to two decimal places.
The tooltip element is a module-level singleton appended to `document.body`
(`position: fixed`, `pointer-events: none`) — both panels on a page share it
without conflict.
