# momentumBarChart.js

2-minute-binned attacking-momentum bar chart. Renders a diverging bar per 2-minute
window: bars rise above a center baseline when the home team generated more
attacking threat (xT) across that window, and fall below when the away team did.

Produced from: `momentum_{match_id}.json` (same contract `momentumChart.js` reads —
no separate extraction step or new sample-data file needed).

---

## Why a separate component from momentumChart.js

`momentumChart.js` draws a smoothed, continuous area/line — appropriate for reading
momentum as an overall trend across the match. This component draws discrete
per-window bars — appropriate for a compact panel where individual 2-minute swings
matter more than the overall shape. Different visual semantics get a dedicated
component rather than a render-mode flag on one component, the same reasoning
`cumulativeXgChart.js`'s README documents for its own split from `momentumChart.js`.

## Construction

```
momentum_{match_id}.json .minutes[]  (one entry per match minute)
  → pair consecutive minutes (0-1, 2-3, 4-5, …)
  → sum each pair's momentum → one value per 2-minute window
  → render as a diverging bar off a center baseline
```

**Why sum, not average?** Momentum is a rate (xT delta per minute). Summing two
consecutive minutes gives that window's total attacking-threat swing — a bar
answers "how much threat swung this way in these two minutes," which is a more
useful read at this compact scale than a smoothed average would be.

## No internal tooltip

Unlike most footballd3 components, this one has no floating tooltip. It's built to
back a compact panel with its own inline readout row driven by the `onHover`
callback — a floating tooltip would be redundant chrome in that layout. If you need
a floating tooltip, wire one yourself from the `onHover` callback.

---

## Usage

```js
import { createMomentumBarChart } from "./momentumBarChart.js";

fetch("../../sample_data/momentum_3943043.json")
  .then((r) => r.json())
  .then((data) => {
    const { update } = createMomentumBarChart(
      d3.select("#momentum-bars-container"),
      data,
      {
        width: 316,
        height: 210,
        homeColor: "#1E3A5F",
        awayColor: "#9F1239",
        showGoals: true,
        onHover: (bin) => {
          const readout = document.getElementById("momentum-readout");
          readout.textContent = bin
            ? `${bin.start}'–${bin.end}' · ${bin.value >= 0 ? "home" : "away"} threat ${bin.value >= 0 ? "+" : ""}${bin.value.toFixed(2)}`
            : "Hover the chart";
        },
      }
    );
  });
```

---

## Returns

`{ svg, g, update }`:

- `svg` — the created SVG selection.
- `g` — the main `<g>` group (use for custom overlays).
- `update({ data?, showGoals? })` — re-renders with updated options. Any omitted key
  retains its current value.

---

## Visual encoding

**Horizontal orientation (default):**

| Element | Meaning |
|---------|---------|
| Bar above baseline, navy/home color | Home team generated more attacking threat in that 2-minute window |
| Bar below baseline, rose/away color | Away team generated more attacking threat in that 2-minute window |
| Bar height | Magnitude of that window's summed momentum, scaled to the chart's tallest bar |
| Dashed vertical + dot + minute label | An actual goal, at its real minute |

**Vertical orientation** (`orientation: "vertical"`) mirrors the same encoding with axes
swapped — time runs down the Y axis (top = minute 0), and bars diverge left (home) or
right (away) from a vertical centerline. Goal markers become dashed horizontal lines with
the dot at the left edge and the minute label at the right edge. Suited to a narrow, tall
container instead of a wide, short one.

---

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `width` | `316` | SVG width in pixels |
| `height` | `210` | SVG height in pixels |
| `orientation` | `"horizontal"` | `"horizontal"` (time on X, magnitude on Y) or `"vertical"` (time on Y, magnitude on X) |
| `homeColor` | `"#1E3A5F"` | Fill color for home-leaning bars |
| `awayColor` | `"#9F1239"` | Fill color for away-leaning bars |
| `showGoals` | `true` | Render goal event markers |
| `onHover` | `null` | `onHover(bin \| null)` — called with the hovered bin `{start, end, value}`, or `null` on mouse-leave |
