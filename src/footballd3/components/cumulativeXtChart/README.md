# cumulativeXtChart.js

Cumulative xT (Expected Threat) "running total" line for **one player**. Renders a
single step-line: the player's running total of xT generated across match time,
rising or falling only at the instant of a credited Pass or Carry and flat
otherwise. Shot events are overlaid as "S" chips at the line's value at that
minute — goals get an extra highlight ring — so viewers can see where a shot fell
relative to the buildup threat the player generated.

Consumes: `player_events/{match_id}/{player_id}.json` (from
`extract_player_events.py`) — or any object with the same `{ events: [...] }`
shape. No dedicated intermediate file of its own; the running cumulative sum is
computed here, client-side, from each event's already-computed `xt_delta`.

Clone of `cumulativeXgChart.js`, adapted for a single player instead of two teams
— see the module docstring in `cumulativeXtChart.js` for the specific structural
differences (single series, no orientation toggle, "shot" chips instead of "goal"
chips) and why the client-side cumulative sum here is bookkeeping, not a new
analytical judgment.

---

## Relationship to xtSurface.js

`xtSurface.js` renders the **static** 8×12 possession-value grid — a fixed
reference surface, mounted once, never re-filtered by a scrubber. This component
renders a **different** thing: one player's own cumulative xT contribution over
time, a per-action data plot. They're complementary, not alternatives —
`xtSurface.js` stays a background layer under the pitch; this is its own
standalone time-series chart.

---

## ⚠ Important caveats — read before interpreting

**(a) xT provenance.** The underlying grid (Karun Singh's public `open_xt_12x8_v1`)
is not fitted to StatsBomb data or to Euro 2024 specifically — see
`extract_xt.py`'s own caveat. Values are directionally meaningful, not calibrated
to this match.

**(b) Only Pass and Carry are credited.** Matches `extract_player_events.py`'s
credited-action set exactly (which itself matches `extract_xt.py`'s). Shots are
never credited toward the line — they're overlaid as markers showing *where* they
happened relative to the accumulated threat, not *contributing* to it.

**(c) A player can have net-negative cumulative xT.** Passes/carries that move the
ball away from goal (e.g. a backward safety pass under pressure) have negative
`xt_delta`. The Y axis extends below zero when this happens — don't assume the
line only goes up.

---

## JSON contract (consumed)

Same shape as every other panel reading `player_events/{match_id}/{player_id}.json`:

```json
{
  "events": [
    { "minute": 70, "second": 18, "type": "Carry", "xt_delta": 0.00125287, "outcome": null, "...": "..." },
    { "minute": 70, "second": 21, "type": "Pass",  "xt_delta": 0.01082925, "outcome": "Incomplete", "...": "..." },
    { "minute": 72, "second": 8,  "type": "Shot",  "xt_delta": null, "outcome": "Goal", "...": "..." }
  ]
}
```

Only `minute`, `second`, `type`, `xt_delta`, and (for Shot events) `outcome` are
read. Every other field on each event is ignored by this component — it's a
direct pass-through of the full player-events file, not a bespoke sub-contract.

---

## Usage

```js
import { createCumulativeXtChart } from "./cumulativeXtChart.js";

fetch("../../sample_data/player_events/3943043/39461.json")
  .then(r => r.json())
  .then(data => {
    const { svg, g, timeScale, xtScale, update } = createCumulativeXtChart(
      d3.select("#cumulative-xt-container"),
      data,
      {
        width: 760,
        height: 220,
        finalMinute: 94,     // align with a shared master scrubber's maxMinute
        showShots: true,
        showTotal: true,
      }
    );

    // Later: swap in a scrub-filtered subset of the same player's events.
    update({ data: { events: data.events.filter(e => e.minute <= scrubbedMinute) } });
  });
```

---

## Returns

`{ svg, g, timeScale, xtScale, update }`:

- `svg` — the created SVG selection.
- `g` — the main `<g>` group (use for custom overlays).
- `timeScale` — `d3.scaleLinear` mapping match minutes → pixels (X axis).
- `xtScale` — `d3.scaleLinear` mapping cumulative xT values → pixels (Y axis, inverted).
- `update({ data?, showShots?, showTotal? })` — re-renders with updated options.
  Any omitted key retains its current value.

---

## Visual encoding

| Element | Meaning |
|---------|---------|
| Red step-line | Player's running cumulative xT |
| Step (flat then vertical rise/fall) | xT only changes at a credited Pass/Carry instant |
| "S" chip on the line | A shot, placed at the line's cumulative value when it happened |
| Ring around an "S" chip | The shot was a goal |
| End-of-line label | The player's final cumulative xT total |
| Dashed divider at 45' | Half-time divider (when the chart's domain extends past it) |
| Crosshair + tooltip | Nearest-point details on hover: minute, cumulative xT |

---

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `width` | `760` | SVG width in pixels |
| `height` | `220` | SVG height in pixels |
| `padding` | `{top:20,right:60,bottom:40,left:48}` | Inner padding |
| `finalMinute` | player's own last event minute | Time axis domain end. Pass a shared scrubber's `maxMinute` to align this chart with sibling panels. |
| `lineColor` | `"#9F1239"` | Cumulative-xT line stroke color |
| `shotColor` | `"#525252"` | Shot chip fill color |
| `goalRingColor` | `"#9F1239"` | Extra ring stroke on goal chips |
| `showShots` | `true` | Render shot chip markers |
| `showTotal` | `true` | Render the end-of-line total label |
| `onHover` | `undefined` | `onHover(point \| null)` — fires alongside the built-in tooltip |
| `showTooltip` | `true` | Render the built-in floating tooltip on hover |
