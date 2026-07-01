# teamShape.js

Renders the **empirical** team shape on an existing pitch. Two views, toggled at runtime:

- **On-ball** (in-possession): identified, event-based. Data is split into lineup periods (one per substitution boundary). Each period shows the 11 players on the pitch at that time — named nodes at their mean position across open-play events in that window, plus a convex hull.
- **Off-ball** (out-of-possession): anonymous, frame-based. Density surface + centroid + thirds-spine + covariance ellipse + percentile-depth line.

These are **different kinds of measurement**. Do not interpret them as equivalent.

---

## Method asymmetry (required reading)

| | On-ball | Off-ball |
|---|---|---|
| Source | StatsBomb events (player-tagged) | 360 freeze-frame dots (anonymous) |
| Unit | Named players | Pooled dot cloud |
| Geometry | Mean position per player within lineup period → hull | KDE density grid + cloud statistics |
| Identity | Each node = a real player on the pitch at that time | Markers = statistics, never players |
| Periods | One set of nodes per substitution window (step via `updatePeriod`) | Single aggregate over the whole match |

The off-ball half pools thousands of frame dots. Its markers (centroid, spine, ellipse, depth line) describe the **distribution**, not individual players.

---

## Camera bias (non-optional caveat)

360 frames follow the ball. The visible subset of out-of-possession player positions is biased toward areas near the ball. The camera artifact and the real defensive shape point in the same direction — the team defends nearer the ball — so they cannot be cleanly separated. Part of any on/off difference is camera, not team shape.

---

## Coordinates

All coordinates are StatsBomb-native 120×80 yards, **normalised so the team always attacks right** (increasing x). The extractor detects each period's attack direction from shot locations and flips x → 120-x, y → 80-y when the team attacks left. This normalization is invisible to this component — it receives already-normalised data.

---

## JSON contract

File: `sample_data/team_shape_{match_id}_{team_slug}.json`

```json
{
  "on_ball": {
    "periods": [
      {
        "from_minute": 0,
        "to_minute": 69,
        "players_in": ["Declan Rice", "..."],
        "players_out": [],
        "nodes": [
          {
            "player_id": 3089,
            "player": "Declan Rice",
            "display_name": "Declan Rice",
            "x": 49.1,
            "y": 41.3,
            "event_count": 63
          }
        ],
        "hull": [[49.1, 41.3], [75.2, 68.7], ...]
      }
    ]
  },
  "off_ball": {
    "density_grid": {
      "cols": 24,
      "rows": 16,
      "values": [[0.0, 0.01, ...], ...]
    },
    "centroid": { "x": 69.84, "y": 39.17 },
    "thirds_spine": [
      { "third": "defensive", "x": 22.3, "y": 40.1 },
      { "third": "middle",    "x": 59.7, "y": 39.6 },
      { "third": "attacking", "x": 94.8, "y": 38.9 }
    ],
    "ellipse": { "cx": 69.84, "cy": 39.17, "rx": 24.1, "ry": 14.3, "angle_deg": -8.5 },
    "depth_line": { "x": 82.4, "percentile": 70 }
  },
  "metadata": {
    "match_id": 3943043,
    "team": "England",
    "competition": "UEFA Euro",
    "match_label": "Spain vs England",
    "on_ball_event_count": 642,
    "on_ball_period_count": 5,
    "off_ball_bandwidth_yards": 8.0,
    "off_ball_depth_percentile": 70,
    "off_ball_grid_cols": 24,
    "off_ball_grid_rows": 16,
    "phase_filter": "open_play_only",
    "coordinate_system": "statsbomb_120x80_normalised_attack_right",
    "coordinate_note": "...",
    "camera_caveat": "..."
  }
}
```

**Open-play filter:** set pieces excluded (corners, free kicks, goal kicks, kick-offs, throw-ins). Transitions included.

**Depth line:** 70th-percentile x of all out-of-possession dots. When x is high, the team's cloud extends far forward out of possession (pressing). When low, the team sits deep.

---

## Usage

```js
import { createPitch }     from "../pitch/pitch.js";
import { createTeamShape } from "../teamShape/teamShape.js";

// Create the pitch first — teamShape layers onto it.
const pitch = createPitch(d3.select("#ts-svg"), {
  mode:       "full",
  orientation:"horizontal",
  pxPerYard:  7,
});

const { update } = createTeamShape(pitch, data, {
  view:        "on-ball",   // initial view
  nodeColor:   "#1E3A5F",
  accentColor: "#9F1239",
  showLabels:  false,
});

// Toggle view (e.g. wired to a button).
update("off-ball");
update("on-ball");
```

## Return value

```js
{ g, px, update, updatePeriod }
```

- `g` — `pitch.g` (D3 selection of the pitch group).
- `px(sbX, sbY) => [screenX, screenY]` — coordinate conversion from createPitch().
- `update(view)` — switch between `"on-ball"` and `"off-ball"` without re-rendering the pitch.
- `updatePeriod(idx)` — jump to lineup period `idx` (0-based, clamped); redraws immediately if the current view is on-ball, otherwise stores for the next switch.

## Extraction

```sh
uv run python src/statsbomb/extract_team_shape.py
```

Reads events + 360 frames for the Euro 2024 Final. Writes one JSON per team. The 360 frames are loaded via `sb.frames()` with a GitHub raw JSON fallback for compatibility.

**Off-ball geometry params:** bandwidth 8 yards, depth-line percentile 70, grid 24×16. All recorded in `metadata`.
