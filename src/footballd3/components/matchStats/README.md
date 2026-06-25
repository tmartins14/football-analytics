# matchStats

Football match statistics breakdown. Renders a score headline and a mirrored bar chart
of per-team stats (shots, possession, xG, cards, etc.) by composing the generic
`comparisonBars` component.

All football logic lives here. `comparisonBars` receives only generic left/right/rows
data and knows nothing about teams, scores, or cards.

## JSON contract

**File:** `sample_data/match_stats_{match_id}.json`
**Produced by:** `src/statsbomb/extract_match_stats.py`

```json
{
  "home": { "team": "Spain",   "color": "#9F1239", "score": 2 },
  "away": { "team": "England", "color": "#1E3A5F", "score": 1 },
  "rows": [
    { "label": "Shots",           "home_value": 16,   "away_value": 9,    "scale_type": "sum",      "format": "int",    "tier": "basic"    },
    { "label": "Shots on Target", "home_value": 6,    "away_value": 3,    "scale_type": "sum",      "format": "int",    "tier": "basic"    },
    { "label": "Possession",      "home_value": 51.7, "away_value": 48.3, "scale_type": "fixed100", "format": "pct",    "tier": "basic"    },
    { "label": "Corners",         "home_value": 10,   "away_value": 2,    "scale_type": "sum",      "format": "int",    "tier": "basic"    },
    { "label": "Fouls",           "home_value": 12,   "away_value": 7,    "scale_type": "sum",      "format": "int",    "tier": "basic"    },
    { "label": "Yellow Cards",    "home_value": 1,    "away_value": 3,    "scale_type": "sum",      "format": "int",    "tier": "basic"    },
    { "label": "Red Cards",       "home_value": 0,    "away_value": 0,    "scale_type": "sum",      "format": "int",    "tier": "basic"    },
    { "label": "xG",              "home_value": 1.79, "away_value": 0.73, "scale_type": "sum",      "format": "float1", "tier": "advanced" }
  ],
  "metadata": {
    "match_id": 3943043,
    "competition": "UEFA Euro 2024",
    "match_label": "Spain vs England"
  }
}
```

### Row fields

| Field        | Type                           | Required                | Description |
|--------------|--------------------------------|-------------------------|-------------|
| `label`      | `string`                       | Yes                     | Stat label displayed between bars |
| `home_value` | `number`                       | Yes                     | Home team value |
| `away_value` | `number`                       | Yes                     | Away team value |
| `scale_type` | `"sum"\|"fixed100"\|"max"`     | Yes                     | Bar scale method (passed through to comparisonBars) |
| `format`     | `"int"\|"pct"\|"float1"`       | Yes                     | Value display format |
| `tier`       | `"basic"\|"advanced"`          | Yes                     | Row visibility tier |
| `max_value`  | `number`                       | When `scale_type="max"` | External reference maximum |

**Extensibility:** Adding a new stat is a new row object in `rows`. No envelope change
is required. Tag it `"tier": "advanced"` to keep the default view clean.

## Possession method

Possession % is computed as the **share of distinct StatsBomb possession sequences**
owned by each team. StatsBomb assigns every event a `possession` (integer sequence ID)
and `possession_team` field; deduplicating on `(possession, possession_team)` and
counting per team mirrors StatsBomb's own possession model.

This means each possession sequence counts once regardless of duration. A 1-pass move
and a 20-pass move both count as one sequence. The values always sum to 100%.

## xG source

xG values (`"label": "xG"`) are StatsBomb's own `shot_statsbomb_xg` field, summed per
team over all shots with a non-null xG. This is not a custom model.

## team_colors.json

Team colors are loaded from `sample_data/team_colors.json` during extraction. Format:

```json
{
  "Spain":   "#9F1239",
  "England": "#1E3A5F"
}
```

Key is the exact team name string as returned by StatsBomb. Missing teams fall back to
project defaults (`#9F1239` home / `#1E3A5F` away).

## Card icons

Yellow and red card rows receive small colored SVG rectangles (8×11 px) next to the
numeric value for each side that has at least one card. These icons are rendered inside
`matchStats` — `comparisonBars` is never told about card semantics.

Zero-value card rows (e.g. "Red Cards: 0 vs 0") render normally as bar rows with
zero-width bars and "0" labels. No icon is shown for the zero side.

## Usage

```javascript
import { createMatchStats } from "./components/matchStats/matchStats.js";

fetch("sample_data/match_stats_3943043.json")
  .then(r => r.json())
  .then(data => {
    const { root, update } = createMatchStats(d3.select("#container"), data, {
      tier:           "basic",  // "basic" or "all"
      showTierToggle: true,
      width:          480,
    });

    // Swap to another match later:
    // update(otherMatchData);
  });
```

## Config options

| Option           | Type               | Default   | Description |
|------------------|--------------------|-----------|-------------|
| `tier`           | `"basic"\|"all"`   | `"basic"` | Initial row filter — "basic" hides advanced rows |
| `showTierToggle` | `boolean`          | `true`    | Show the basic/all toggle buttons |
| `width`          | `number`           | `480`     | Total width in pixels (passed to comparisonBars) |
| `rowHeight`      | `number`           | `40`      | Height per stat row in pixels |
| `barHeight`      | `number`           | `14`      | Bar rectangle height in pixels |
| `labelWidth`     | `number`           | `130`     | Center label zone width in pixels |
| `headerHeight`   | `number`           | `32`      | comparisonBars side-label header height |
| `paddingY`       | `number`           | `10`      | Vertical padding around rows |

## Return shape

| Key      | Type               | Description |
|----------|--------------------|-------------|
| `root`   | `d3.Selection`     | The `.ms-root` div element |
| `update` | `(newData, newConfig?) → void` | Replace data and re-render. Preserves tier unless `newConfig.tier` is supplied. |

## Extraction

```bash
uv run src/statsbomb/extract_match_stats.py
# Writes: src/footballd3/sample_data/match_stats_3943043.json
```

Stats extracted from `sb.events()`:

| Stat            | StatsBomb source |
|-----------------|-----------------|
| Score           | `type=Shot, shot_outcome=Goal` per team |
| Shots           | `type=Shot` count per team |
| Shots on Target | `shot_outcome in {Saved, Goal}` |
| Possession %    | Possession sequence count method |
| Corners         | `type=Pass, pass_type=Corner` |
| Fouls           | `type=Foul Committed` |
| Yellow Cards    | `foul_committed_card=Yellow Card` + `bad_behaviour_card` when present |
| Red Cards       | `foul_committed_card in {Red Card, Second Yellow}` + `bad_behaviour_card` |
| xG              | `sum(shot_statsbomb_xg)` per team, tier="advanced" |
