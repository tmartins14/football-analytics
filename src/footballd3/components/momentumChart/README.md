# momentumChart.js

Match momentum chart built from per-minute xT (Expected Threat) aggregation.
Renders a filled area curve crossing a zero baseline across match minutes — home
team territory above zero, away team below. The curve is a recency-weighted rolling
window over per-action xT deltas, not a possession count or pass volume.

Produced by: `src/statsbomb/extract_momentum.py`
Consumes: `src/footballd3/sample_data/xt_actions_{match_id}.json`
Produces: `src/footballd3/sample_data/momentum_{match_id}.json`

---

## ⚠ Important caveats — read before interpreting

**(a) Attacking threat, not "who's on top".**
This chart measures threat GENERATED from open-play ball-progression actions (passes
and carries with positive xT delta). It sees the team on the ball only. A team
absorbing sustained pressure while executing a disciplined shape reads as zero or
negative momentum even if they are tactically in control. It does not capture
defensive resistance, counter-pressing effectiveness, set-piece threat, or any
off-ball activity. *Treat it as an attacking-threat narrative, not a comprehensive
dominance picture.*

**(b) The curve is window-dependent.**
Each minute's value is a recency-weighted average of the prior `window_minutes`
minutes (default: 3). A short window (2–3 min) produces a reactive, jumpy chart;
a long window (6+ min) produces a smooth narrative arc. *The same match tells a
different story at different window lengths.* When the secondary overlay is shown,
the divergence between the two curves indicates how window-sensitive the narrative is.

**(c) xT provenance: Karun Singh's open grid, not Euro 2024.**
The xT values come from Karun Singh's published open_xt_12x8_v1 grid, trained on his
own match corpus — **not** on Euro 2024 or StatsBomb data. Cell values are
directionally meaningful (higher cells are more dangerous) but are not calibrated to
this competition. Absolute magnitudes should not be compared across datasets that use
differently-fitted grids.

---

## Construction

```
xt_actions_{match_id}.json
  → bin xt_delta by team × minute (MAX aggregation)
  → clip negatives to 0 (no-forward-threat minutes = 0, not negative)
  → exponential decay window (α=0.6, window=3 min by default)
     weights ≈ [51%, 31%, 18%] for current, -1, -2 minutes
  → momentum[t] = home_smoothed[t] − away_smoothed[t]
  → emit primary (3 min) + secondary (6 min) series
```

**Why MAX (not SUM)?** MAX captures peak danger per minute — a team making one
highly dangerous ball outweighs a team making five low-value passes. SUM rewards
possession volume, turning momentum into a proxy for how many actions a team took,
which defeats the purpose of using xT in the first place.

---

## Consumed JSON contract

Only the following fields are read from `xt_actions_{match_id}.json`:

```
actions[]: { team, minute, xt_delta }
metadata:  { grid_source }
```

Unused fields present in xt_actions (ignored by this transform):
`display_name`, `second`, `x0`, `y0`, `x1`, `y1`, `start_zone`, `end_zone`, `action_type`.

---

## Produced JSON contract

`src/footballd3/sample_data/momentum_{match_id}.json`

```json
{
  "home_team": "Spain",
  "away_team": "England",
  "minutes": [
    { "minute": 1, "home_threat": 0.000353, "away_threat": 0.001221, "momentum": -0.000868 },
    { "minute": 47, "home_threat": 0.0019, "away_threat": 0.0, "momentum": 0.0019 }
  ],
  "secondary_minutes": [
    { "minute": 1, "home_threat": 0.000353, "away_threat": 0.001221, "momentum": -0.000868 }
  ],
  "goals": [
    { "minute": 46, "team": "Spain", "player": "Nico Williams", "is_own_goal": false },
    { "minute": 72, "team": "England", "player": "Cole Palmer", "is_own_goal": false },
    { "minute": 85, "team": "Spain", "player": "Mikel Oyarzabal", "is_own_goal": false }
  ],
  "red_cards": [],
  "params": {
    "window_minutes": 3,
    "weighting": "exponential",
    "decay_alpha": 0.6,
    "aggregation": "max",
    "secondary_window_minutes": 6
  },
  "metadata": {
    "match_id": 3943043,
    "competition": "UEFA Euro",
    "season": "2024",
    "match_label": "Spain vs England",
    "grid_source": "Karun Singh open_xt_12x8_v1"
  }
}
```

---

## Usage

```js
import { createMomentumChart } from "./momentumChart.js";

fetch("../../sample_data/momentum_3943043.json")
  .then(r => r.json())
  .then(data => {
    const { svg, g, timeScale, momentumScale, update } = createMomentumChart(
      d3.select("#momentum-container"),
      data,
      {
        width: 900,
        height: 240,
        showGoals: true,
        showCards: true,
        showSecondaryWindow: true,
        orientation: "horizontal",  // or "vertical"
      }
    );

    // Toggle secondary window:
    document.getElementById("mc-secondary").addEventListener("change", function () {
      update({ showSecondaryWindow: this.checked });
    });

    // Toggle orientation:
    document.getElementById("mc-orientation").addEventListener("change", function () {
      update({ orientation: this.value });
    });
  });
```

---

## Orientations

### Horizontal (default)

Time flows left → right. Home (navy) fills above the zero baseline; away (red) fills below.
Natural reading direction for match timelines.

```
momentum
   ^
   |  ████████                     ░░░░░░░░░░
   |          ████                ░░        ░░
───|──────────────────────────────────────────→ minutes
   |              ████████████████
   |
```

### Vertical

Time flows top → bottom. Home (navy) fills to the right of the zero baseline; away (red) fills to the left.
Useful when composing next to a vertical pitch map or in a match-report layout where time
runs down the page. Passing `orientation: "vertical"` swaps the SVG dimensions automatically
(width and height are exchanged).

```
  away | home
  ← E  |  S →
       |
  ─────┼──  early
  ░░░  |  ███
  ░░░  |  ████
  ─────┼──  late
       |
```

---

## Returns

`{ svg, g, timeScale, momentumScale, update }`:

- `svg` — the created SVG selection.
- `g` — the main `<g>` group (use for custom overlays).
- `timeScale` — `d3.scaleLinear` mapping match minutes → pixels (X in horizontal, Y in vertical).
- `momentumScale` — `d3.scaleLinear` mapping momentum values → pixels (Y in horizontal, X in vertical).
- `update({ data?, orientation?, showSecondaryWindow?, showGoals?, showCards? })` — re-renders
  with updated options. Any omitted key retains its current value. `orientation` change resizes the SVG.

---

## Visual encoding

| Element | Meaning |
|---------|---------|
| Fill above zero (navy) / right of zero | Home team generating attacking threat |
| Fill below zero (red) / left of zero | Away team generating attacking threat |
| Solid gray contour line | Primary window (3 min) momentum |
| Dashed semi-transparent line | Secondary window (6 min) momentum overlay |
| Dashed line + G chip | Goal event; colored by scoring team; vertical (H) or horizontal (V) |
| Dashed line + R chip | Red card event (dark red) |
| Dashed divider at 45' | Half-time divider |
| Crosshair + tooltip | Minute-by-minute values on hover; vertical (H) or horizontal (V) |

---

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `width` | `760` | SVG width in pixels |
| `height` | `220` | SVG height in pixels |
| `padding` | `{top:36,right:24,bottom:40,left:52}` | Inner padding |
| `homeColor` | `"#1E3A5F"` | Home fill and label color (above zero) |
| `awayColor` | `"#9F1239"` | Away fill and label color (below zero) |
| `showGoals` | `true` | Render goal event markers |
| `showCards` | `true` | Render red card markers |
| `showSecondaryWindow` | `true` | Overlay the 6-minute secondary window line |
| `orientation` | `"horizontal"` | `"horizontal"` or `"vertical"` — controls which axis carries time |
