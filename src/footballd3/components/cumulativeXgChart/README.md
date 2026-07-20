# cumulativeXgChart.js

Cumulative xG "race chart" built from raw shot events. Renders a step-line per team:
each team's running total of expected goals (xG) across match time, rising only at the
instant of a shot and flat otherwise. Actual goals are overlaid as "G" chips directly on
the scoring team's line so viewers can compare expected scoring against what actually
happened.

Produced by: `src/statsbomb/extract_cumulative_xg.py`
Consumes: shot records from `extract_shots(match_id)` (in-process — no intermediate file)
Produces: `src/footballd3/sample_data/cumulative_xg_{match_id}.json`

---

## ⚠ Important caveats — read before interpreting

**(a) xG is provider-specific, not universally calibrated.**
The values here come from StatsBomb's own xG model (`shot_statsbomb_xg`). Different
providers (Opta, other in-house models) fit their own models on their own shot corpora —
absolute xG values, and therefore this chart's totals, should not be compared directly
against a chart built from a different provider's data on the same match.

**(b) xG measures shot quality, not finishing quality.**
Cumulative xG is a running sum of "how likely was a shot like this to score, given
historical shots from similar positions and situations" — it says nothing about whether
the actual shot-taker finished well or poorly. *A team well ahead on this chart can still
lose the match*, and a team behind on it can still win.

**(c) Cumulative xG is not a score prediction.**
This chart is a running sum of independent shot-quality estimates, not a simulation of
match outcomes. Do not read the end-of-line totals as "the score this match should have
been."

**(d) Own goals show as goal markers but add nothing to either line.**
StatsBomb assigns no xG value to own goals, so they never appear in the shot-derived
`points[]` series and contribute zero to either team's cumulative total. They still
appear as "G" chip markers (pulled independently from the full match event stream), but
— matching `extract_momentum.py`'s existing convention — the chip is attributed to the
shooting team's own line, not the beneficiary's. If an own goal occurs in a match, look
twice at which line its chip sits on.

---

## Construction

```
shots_{match_id} (via extract_shots, in-process)
  → preserve original StatsBomb chronological order (no re-sort by minute alone)
  → running per-team sum of shot xg, one point per shot
  → anchor at kickoff (0, 0) and full time (final_minute, final_total) per team
  → emit as a step function (curveStepAfter), not smoothed
```

**Why a step function, not a smoothed curve (like momentumChart's)?** xG only actually
changes at the instant of a shot. A smoothed interpolation between shots would visually
imply continuous accrual that never happened — the step function is the honest shape.

**Why anchored at raw shot events, not a per-minute grid (like momentumChart's)?**
Momentum aggregates a dense, continuous xT signal that exists every minute regardless of
events. A team's xG is naturally zero except at the sparse instants a shot occurs —
forcing it onto a per-minute grid would just re-express the same step function with
wasted flat rows.

**Why is `final_minute` taken from the full event stream, not the last shot?** The last
shot of a match is frequently several minutes before the actual final whistle (stoppage
time, late defensive play with no more shots). Anchoring the line's end on the last shot
instead of the true match-ending minute would visibly truncate the chart before full time.

---

## Consumed JSON contract

Only the following fields are read, in-process, from `extract_shots(match_id)`'s
DataFrame (no on-disk `shots_{match_id}.json` dependency required):

```
minute, team, xg, display_name, outcome, is_goal
```

Unused fields present in `extract_shots()`'s output (ignored by this transform):
`x`, `y`, `event_id`.

---

## Produced JSON contract

`src/footballd3/sample_data/cumulative_xg_{match_id}.json`

```json
{
  "home_team": "Spain",
  "away_team": "England",
  "points": [
    { "minute": 11, "team": "Spain", "display_name": "Fabián Ruiz", "xg": 0.057442, "cumulative_xg": 0.057442, "outcome": "Saved", "is_goal": false },
    { "minute": 46, "team": "Spain", "display_name": "Nico Williams", "xg": 0.0812, "cumulative_xg": 0.301, "outcome": "Goal", "is_goal": true },
    { "minute": 72, "team": "England", "display_name": "Cole Palmer", "xg": 0.0491, "cumulative_xg": 0.734, "outcome": "Goal", "is_goal": true }
  ],
  "final_minute": 94,
  "final_home_xg": 1.734,
  "final_away_xg": 0.981,
  "goals": [
    { "minute": 46, "team": "Spain", "player": "Nico Williams", "is_own_goal": false },
    { "minute": 72, "team": "England", "player": "Cole Palmer", "is_own_goal": false },
    { "minute": 85, "team": "Spain", "player": "Mikel Oyarzabal", "is_own_goal": false }
  ],
  "metadata": {
    "match_id": 3943043,
    "competition": "UEFA Euro",
    "season": "2024",
    "match_label": "Spain vs England"
  }
}
```

---

## Usage

```js
import { createCumulativeXgChart } from "./cumulativeXgChart.js";

fetch("../../sample_data/cumulative_xg_3943043.json")
  .then(r => r.json())
  .then(data => {
    const { svg, g, timeScale, xgScale, update } = createCumulativeXgChart(
      d3.select("#cumulative-xg-container"),
      data,
      {
        width: 900,
        height: 240,
        showGoals: true,
        showTotals: true,
        orientation: "horizontal",  // or "vertical"
      }
    );

    // Toggle goal markers:
    document.getElementById("cxg-goals").addEventListener("change", function () {
      update({ showGoals: this.checked });
    });

    // Toggle orientation:
    document.getElementById("cxg-orientation").addEventListener("change", function () {
      update({ orientation: this.value });
    });
  });
```

---

## Orientations

### Horizontal (default)

Time flows left → right. Cumulative xG grows upward (zero at the bottom). End-of-line
totals sit at the right edge.

```
xG
 ^                                          England 0.98
 |                                  ┌───────
 |                        ┌─────────┘
 |              ┌─────────┘
 |      ┌───────┘                            Spain 1.73
 |──────┘                          ┌──────────
 |                        ┌────────┘
─┼──────────────────────────────────────────→ minutes
```

### Vertical

Time flows top → bottom. Cumulative xG grows rightward (zero at the left). End-of-line
totals sit near the bottom edge. Useful when composing next to a vertical pitch map or
in a match-report layout where time runs down the page. Passing `orientation: "vertical"`
swaps the SVG dimensions automatically (width and height are exchanged).

```
0            xG →
│
├── early
│  ┐
│  └┐
│   └──┐
│      └── goal
│
├── late
│         Spain 1.73  England 0.98
```

---

## Returns

`{ svg, g, timeScale, xgScale, update }`:

- `svg` — the created SVG selection.
- `g` — the main `<g>` group (use for custom overlays).
- `timeScale` — `d3.scaleLinear` mapping match minutes → pixels (X in horizontal, Y in vertical).
- `xgScale` — `d3.scaleLinear` mapping cumulative xG values → pixels (Y in horizontal, X in vertical).
- `update({ data?, orientation?, showGoals?, showTotals? })` — re-renders with updated
  options. Any omitted key retains its current value. `orientation` change resizes the SVG.

---

## Visual encoding

| Element | Meaning |
|---------|---------|
| Navy step-line | Home team's running cumulative xG |
| Rose step-line | Away team's running cumulative xG |
| Step (flat then vertical rise) | xG only changes at a shot instant |
| "G" chip on a line | An actual goal, placed at that line's cumulative value when it happened |
| End-of-line label | Each team's final cumulative xG total |
| Dashed divider at 45' | Half-time divider |
| Crosshair + tooltip | Nearest-shot details on hover: minute, team, player, outcome, xG, both teams' running totals |

---

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `width` | `760` | SVG width in pixels |
| `height` | `220` | SVG height in pixels |
| `padding` | `{top:20,right:88,bottom:40,left:48}` | Inner padding (wide right margin fits end-of-line labels) |
| `homeColor` | `"#1E3A5F"` | Home team line and label color |
| `awayColor` | `"#9F1239"` | Away team line and label color |
| `showGoals` | `true` | Render actual-goal "G" chip markers |
| `showTotals` | `true` | Render end-of-line cumulative total labels |
| `orientation` | `"horizontal"` | `"horizontal"` or `"vertical"` — controls which axis carries time |
