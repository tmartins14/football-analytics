# comparisonBars

Generic mirrored opposed-bar chart. Two named sides (left vs right) are rendered as a
stacked list of rows, each with its own scale type and number format.

This component contains **no domain knowledge**. "Left" and "right" are opaque identity
objects. Row labels, values, and scale semantics come entirely from the caller.
It can be used for any A-vs-B comparison — football matches, player seasons,
country statistics, product metrics, etc.

## JSON contract

**Input data object:**

```json
{
  "left":  { "label": "Bayern",   "color": "#DC052D" },
  "right": { "label": "Dortmund", "color": "#FDE100" },
  "rows": [
    {
      "label":      "Wins",
      "leftValue":  22,
      "rightValue": 18,
      "scaleType":  "sum",
      "format":     "int"
    },
    {
      "label":      "Win Rate",
      "leftValue":  63.2,
      "rightValue": 52.9,
      "scaleType":  "fixed100",
      "format":     "pct"
    },
    {
      "label":      "Goals / 90",
      "leftValue":  2.4,
      "rightValue": 1.9,
      "scaleType":  "max",
      "format":     "float1",
      "maxValue":   4.0
    }
  ]
}
```

### Row fields

| Field        | Type                              | Required            | Description |
|--------------|-----------------------------------|---------------------|-------------|
| `label`      | `string`                          | Yes                 | Row label centered between bars |
| `leftValue`  | `number`                          | Yes                 | Left-side numeric value |
| `rightValue` | `number`                          | Yes                 | Right-side numeric value |
| `scaleType`  | `"sum" \| "fixed100" \| "max"`    | Yes                 | Bar scale method (see below) |
| `format`     | `"int" \| "pct" \| "float1"`      | Yes                 | Value display format |
| `maxValue`   | `number`                          | When `scaleType === "max"` | External reference maximum |

### scaleType semantics

| Value      | Formula                                        | Use when |
|------------|------------------------------------------------|----------|
| `"sum"`    | `barW = value / (left + right) × maxBarW`     | Values represent a share of a combined total (e.g. shots, fouls, corners) |
| `"fixed100"` | `barW = value / 100 × maxBarW`             | Values are already percentages that sum to 100 (e.g. possession, pass accuracy) |
| `"max"`    | `barW = value / maxValue × maxBarW`           | Both sides should be compared to a fixed external reference (e.g. season high, league max) |

**WARNING:** Using the wrong `scaleType` misrepresents the visual gap.
- A `"sum"` row where one side is 0 will show a full bar for the other side — correctly
  showing 100% share of the combined total. If that's misleading for your data, use `"max"`.
- A `"fixed100"` row where values don't sum to 100 will produce bars that don't fill the
  zone correctly — the caller is responsible for ensuring the sum.

### format values

| Value      | Example output |
|------------|---------------|
| `"int"`    | `16`          |
| `"pct"`    | `51.7%`       |
| `"float1"` | `1.8`         |

### Empty/zero state

Rows where both values are 0 render normally with zero-width bars. Value labels show
`"0"` (or `"0.0%"` / `"0.0"` depending on format). The row label and separator remain
visible, keeping the layout stable across datasets.

## Usage

```javascript
import { createComparisonBars } from "./components/comparisonBars/comparisonBars.js";

// Non-football example: two seasons compared
const data = {
  left:  { label: "2022–23", color: "#1E3A5F" },
  right: { label: "2023–24", color: "#9F1239" },
  rows: [
    { label: "Wins",          leftValue: 28, rightValue: 30, scaleType: "sum",      format: "int"    },
    { label: "Clean Sheets",  leftValue: 14, rightValue: 11, scaleType: "sum",      format: "int"    },
    { label: "Win Rate",      leftValue: 73.7, rightValue: 78.9, scaleType: "fixed100", format: "pct" },
    { label: "Goals / Match", leftValue: 2.3, rightValue: 2.7, scaleType: "max",    format: "float1", maxValue: 4.0 },
  ],
};

const { svg, update } = createComparisonBars(d3.select("#container"), data);

// Swap to different data later (e.g. on filter change):
update(newData);
```

## Config options

| Option         | Type     | Default | Description |
|----------------|----------|---------|-------------|
| `width`        | `number` | `480`   | Total SVG width in pixels |
| `rowHeight`    | `number` | `40`    | Height per data row in pixels |
| `barHeight`    | `number` | `14`    | Bar rectangle height in pixels |
| `labelWidth`   | `number` | `130`   | Center label zone width in pixels |
| `headerHeight` | `number` | `32`    | Height of the side-label header row |
| `paddingY`     | `number` | `10`    | Vertical padding above and below the row stack |

## Return shape

| Key      | Type              | Description |
|----------|-------------------|-------------|
| `svg`    | `d3.Selection`    | The appended `<svg>` element |
| `update` | `(newData) → void` | Replace data and redraw rows. Adjusts SVG height for new row count. Does not redraw the header. |

## Layout

```
[SIDE LABEL LEFT ]              [ LABEL  ]              [SIDE LABEL RIGHT]
─────────────────────────────────────────────────────────────────────────
       val [===left bar===]     Shots     [===right bar===] val
       val [=left bar=]         Corners   [======right bar======] val
       val []                   Red Cards [] val
─────────────────────────────────────────────────────────────────────────
```

Value text sits just inside the bar zone at the axis edge (fixed position). Bars grow
outward from there toward the SVG edges. The center label zone width is configurable.

## Notes

- `d3` must be loaded globally before this module is imported.
- No pitch dependency — this component is standalone and pitch-agnostic.
- If `scaleType === "max"` and `maxValue` is absent or zero, `createComparisonBars`
  throws with a message naming the offending row.
