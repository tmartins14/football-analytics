# pitch

Renders a StatsBomb-native 120×80 pitch into a D3 SVG selection. Returns the
pitch group element and a coordinate helper (`px`) that downstream components
use to place data elements in StatsBomb space without doing any pixel math
themselves.

## Usage

```js
import { createPitch } from "./pitch.js";

const { g, px } = createPitch(d3.select("svg"), {
  mode: "half",
  orientation: "vertical",
  pxPerYard: 7,
});

// Place a circle at StatsBomb coordinates (100, 40)
const [cx, cy] = px(100, 40);
g.append("circle").attr("cx", cx).attr("cy", cy).attr("r", 5);
```

## Config options

| Option | Type | Default | Description |
|---|---|---|---|
| `mode` | `"full"` \| `"half"` | `"full"` | Full 120×80 pitch or attacking half (60×80) |
| `orientation` | `"horizontal"` \| `"vertical"` | `"horizontal"` | Long axis direction |
| `pxPerYard` | number | `8` | Scale factor; pitch elements stay the same visual size, canvas flexes |
| `padding` | number | `24` | Canvas padding in pixels on all sides |
| `showGoals` | boolean | `true` | Render goal boxes |
| `theme` | string \| object | `"whiteboard"` | `"whiteboard"`, `"green"`, or a custom token object |

## Return shape

| Key | Type | Description |
|---|---|---|
| `svg` | D3 selection | The `<svg>` element (modified in place) |
| `g` | D3 selection | `<g class="pitch">` — append data elements here |
| `xScale` | d3.scaleLinear | Maps StatsBomb X → screen X |
| `yScale` | d3.scaleLinear | Maps StatsBomb Y → screen Y |
| `px` | function | Coordinate helper — see below |
| `width` | number | Total SVG width in pixels |
| `height` | number | Total SVG height in pixels |
| `config` | object | Echo of `{ mode, orientation, padding, pxPerYard }` |

## `px(sbX, sbY)` helper

Converts StatsBomb coordinates to screen pixels, accounting for orientation.

```js
const [screenX, screenY] = px(sbX, sbY);
```

- In `"horizontal"` mode: `[xScale(sbX), yScale(sbY)]`
- In `"vertical"` mode: `[xScale(sbY), yScale(sbX)]` — axes swap so the pitch
  rotates 90°; callers pass native StatsBomb coordinates either way.

## Themes

| Theme | Background | Lines | Use when |
|---|---|---|---|
| `"whiteboard"` | `#FAF7F0` | `#1E4D2B` | Default; signature look |
| `"green"` | `#1E4D2B` | `#FAF7F0` | Broadcast-style; use sparingly |

Custom themes pass a token object directly:

```js
createPitch(selection, {
  theme: { background: "#111", lines: "#eee", lineWeight: 1.0 },
});
```
