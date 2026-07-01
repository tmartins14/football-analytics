# progressiveMap

Renders all of a team's open-play passes and carries as arrows over a pitch. Progressive
actions (those that moved the ball at least 25% closer to the opponent's goal centre) are
highlighted with bold colour-coded arrows. Non-progressive actions appear as thin muted
lines in the background, providing movement context. A `progressiveOnly` toggle hides the
background layer when you want to focus solely on progression.

Passes show both **attempts** (completed and incomplete). Carries show **completed carries only** — see the asymmetry note below.

## Progression definition

**Progressive = StatsBomb's 25%-of-remaining-distance-to-goal-centre rule, set pieces excluded (play_pattern filter), threshold configurable.**

Formally:

```
goal_centre = (120, 40)   # StatsBomb 120×80 yards
dist_start  = distance from start point to goal_centre
dist_end    = distance from end point   to goal_centre

progressive = dist_end ≤ (1 - threshold) × dist_start
            = dist_end ≤ 0.75 × dist_start   [threshold = 0.25, default]
```

Set-piece phases are excluded by filtering on `play_pattern`: actions in "From Corner", "From Free Kick", "From Goal Kick", "From Kick Off", or "From Throw In" are dropped. This excludes both the set-piece delivery and any follow-up actions in the same phase.

**Definition comparability note:** The 25%-of-remaining-distance rule matches StatsBomb's own definition. Other providers use different thresholds or entirely different methods — FBref / Opta use fixed-yardage cutoffs (≥10 yards in own half, ≥30 yards in middle third, or a cross into the penalty area); Wyscout uses zone-based criteria. The progressive count is definition-dependent and is **not comparable across sources.**

## Pass / carry asymmetry

**Passes show attempts (completed + incomplete).** StatsBomb logs both completed and incomplete passes, so the map can distinguish intent (progressive pass attempted) from execution (progressive pass completed).

**Carries show completed carries only.** StatsBomb logs carry failures as separate dispossession or failed take-on events — not as incomplete carries. There is no "attempted carry" vs "completed carry" distinction in the data. A split would fabricate a metric. Carries are completed-only, full stop.

This asymmetry is intentional. Do not resolve it into symmetry by pulling dispossessions as "failed carries."

## Visual encoding

| Element | Style | Meaning |
|---------|-------|---------|
| Red solid arrow | `#9F1239`, opacity 0.75, 1.5px | Completed progressive pass |
| Red dashed arrow | `#9F1239`, opacity 0.28, dashed (5,3) | Incomplete progressive pass attempt |
| Navy thick arrow | `#1E3A5F`, opacity 0.75, 2.5px | Progressive carry (completed) |
| Faded red arrow | `#9F1239`, opacity 0.18, 1.5px | Non-progressive pass (context) |
| Faded navy arrow | `#1E3A5F`, opacity 0.18, 2.5px | Non-progressive carry (context) |

Color encodes action **type** consistently for all actions — red for passes, navy for carries.
Progressive actions are bold with arrowheads; non-progressive are thin and faded.
Within progressive passes, solid vs dashed encodes completion.

Color encodes completion (red = successful progressive action); stroke weight and color together identify carries.

## JSON contract

**Input:** `sample_data/progressive_map_{match_id}_{team_slug}.json`

```json
{
  "team": "Spain",
  "actions": [
    {
      "action_type":    "pass",
      "display_name":   "Fabián Ruiz",
      "x0": 45.2, "y0": 32.1,
      "x1": 89.4, "y1": 28.7,
      "completed":      true,
      "progressive":    true,
      "distance_gained": 28.3,
      "minute":         23
    },
    {
      "action_type":    "carry",
      "display_name":   "Rodri",
      "x0": 55.0, "y0": 40.1,
      "x1": 78.2, "y1": 38.3,
      "completed":      true,
      "progressive":    true,
      "distance_gained": 22.1,
      "minute":         67
    }
  ],
  "params": {
    "progressive_threshold": 0.25
  },
  "metadata": {
    "match_id":         3943043,
    "team":             "Spain",
    "competition":      "UEFA Euro 2024",
    "match_label":      "Spain vs England",
    "set_piece_filter": "play_pattern"
  }
}
```

Field notes:
- `progressive: true` when `dist_end ≤ 0.75 × dist_start` (relative to goal centre (120, 40)).
- `carry` actions always have `completed: true` — reflects the StatsBomb schema, not a simplification.
- `display_name` is the nickname-coalesced label resolved in Python. Components render it verbatim.
- `distance_gained` is in StatsBomb yards. Positive = moved toward goal, negative = moved away.
  For non-progressive actions, the value represents the actual distance change (useful as context).
- `params.progressive_threshold` records the threshold used, enabling reproducibility checks.
- Coordinates are StatsBomb-native 120×80 yards. `pitch.px()` converts to screen pixels.

## Usage

```javascript
import { createProgressiveMap } from "./components/progressiveMap/progressiveMap.js";

// 1. Create the pitch (full pitch, horizontal, whiteboard).
const pitch = createPitch(d3.select("#my-svg"), { pxPerYard: 7 });

// 2. Load progressive map data and overlay arrows.
fetch("sample_data/progressive_map_3943043_spain.json")
  .then(r => r.json())
  .then(data => {
    const { update } = createProgressiveMap(pitch, data, {
      toggle:         "both",   // "passes" | "carries" | "both"
      player:         null,     // null = all players; "Rodri" = one player
      progressiveOnly: false,   // false = all actions (default); true = progressive only
    });

    // Show only progressive actions:
    update({ progressiveOnly: true });

    // Filter to a single player (all actions):
    update({ progressiveOnly: false, player: "Rodri" });

    // Back to all players, both types, all actions:
    update({ toggle: "both", player: null, progressiveOnly: false });
  });
```

## Extraction

```bash
cd /path/to/football-analytics
uv run python src/statsbomb/extract_progressive_map.py
```

Resolves the UEFA Euro 2024 Final match ID live via `sb.competitions()` → `sb.matches()`,
extracts Spain and England, and writes:
- `src/footballd3/sample_data/progressive_map_{match_id}_spain.json`
- `src/footballd3/sample_data/progressive_map_{match_id}_england.json`
