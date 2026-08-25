# statsbomb

Python package for extracting StatsBomb open data and writing flat JSON files
that the footballd3 component library consumes. All IDs are resolved live via
the StatsBomb API — never hardcoded.

Each extract function accepts a `match_id` and returns a tidy `pd.DataFrame`.
`main()` in each module resolves the Euro 2024 Final, calls the extract function,
and writes the JSON contract to `libs/footballd3/sample_data/`.

## Quick start

```python
from statsbomb import extract_shots, extract_progressive_map

# Euro 2024 Final
df = extract_shots(3869685)
print(df.head())

# Any match — resolve the ID first
from statsbomb.utils import resolve_match
match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
df = extract_progressive_map(match_id, team="Spain")
```

---

## `utils.py` — shared helpers

All duplicated helpers live here. Import directly when needed for analysis.

```python
from statsbomb.utils import resolve_match, fetch_match_info, build_nickname_lookup
```

| Symbol | Signature | Purpose |
|---|---|---|
| `SET_PIECE_PLAY_PATTERNS` | `frozenset[str]` | Set-piece play-pattern labels used to exclude set pieces. |
| `resolve_match` | `(competition_name, season_name, home_team=None, away_team=None) -> int` | Generic match resolver via `sb.competitions()` / `sb.matches()`. Falls back to Final stage or last-by-date. |
| `fetch_match_info` | `(match_id) -> tuple[str, str, str]` | Returns `(competition_display, season, "Home vs Away")`. Scans all competitions. |
| `build_nickname_lookup` | `(match_id) -> dict[int, str]` | `player_id → display_name` coalescing nickname/full name. |
| `load_360_frames` | `(match_id) -> dict` | Loads 360 freeze frames keyed by event UUID. Includes `visible_area`. Falls back to GitHub raw JSON on `statsbombpy` v1.18 bug. |
| `open_play_mask` | `(events) -> pd.Series[bool]` | Boolean mask excluding set-piece play patterns. |
| `parse_timestamp` | `(ts: str) -> float` | `"HH:MM:SS.mmm"` → float seconds within period. |
| `end_location` | `(row) -> tuple[float\|None, float\|None]` | End coordinates for Pass/Carry/Shot; `None` for other types. |
| `pass_outcome` | `(row) -> str\|None` | Pass failure string; `None` for completions and non-Pass types. |

---

## Modules

---

### `extract_shots.py`

```python
extract_shots(match_id: int) -> pd.DataFrame
```

Filters events to `type == "Shot"`. Drops shots where `xg` is NaN (own goals
carry no StatsBomb xG value).

**DataFrame columns:** `event_id, x, y, xg, outcome, is_goal, team, display_name, minute`

**Output:** `libs/footballd3/sample_data/shots_{match_id}.json`

```json
[
  { "x": 108.0, "y": 38.5, "xg": 0.28, "outcome": "Goal",
    "is_goal": true, "team": "Spain", "player": "Mikel Oyarzabal", "minute": 86 }
]
```

```bash
uv run python libs/statsbomb/extract_shots.py
```

---

### `extract_freeze_frame.py`

```python
extract_freeze_frame(match_id: int) -> pd.DataFrame
```

Loads 360 freeze frames for all goal events in a match. Each row is one
player dot at one goal instant.

**DataFrame columns:** `goal_event_id, goal_minute, scorer, scorer_team, ball_x, ball_y, player_x, player_y, teammate, actor, keeper`

**Output:** `libs/footballd3/sample_data/freeze_frames_{match_id}_goals.json`

```json
{
  "goals": [
    {
      "ball": { "x": 111.0, "y": 36.8 },
      "frame": [{ "x": 108.5, "y": 37.2, "teammate": true, "actor": false, "keeper": false }],
      "visible_area": [0.0, 80.0, 120.0, 80.0, 120.0, 0.0, 0.0, 0.0],
      "metadata": { "match_id": 3943043, "event_id": "uuid", "display_name": "Mikel Oyarzabal",
                    "team": "Spain", "minute": 86 }
    }
  ],
  "match_metadata": { "match_id": 3943043, "competition": "UEFA Euro 2024", "match_label": "Spain vs England" }
}
```

```bash
uv run python libs/statsbomb/extract_freeze_frame.py
```

---

### `extract_convex_hull.py`

```python
extract_convex_hull(match_id: int) -> pd.DataFrame
```

Reads 360 frames for each goal and computes convex hull geometry for both
teams at each goal instant. `teammate` booleans are actor-relative; the
extractor performs the possession-team comparison to label offense/defense.

**DataFrame columns:** `goal_event_id, minute, possession_team_name, actor_team_name, side, team_name, hull_vertices, area, player_count`

**Output:** `libs/footballd3/sample_data/convex_hull_{match_id}_goals.json`

```json
{
  "hulls": [
    {
      "sides": [
        { "side": "offense", "team_name": "Spain",
          "hull_vertices": [[108.5, 36.2], [111.0, 38.0]],
          "area": 142.3, "player_count": 8 }
      ],
      "metadata": { "match_id": 3943043, "event_id": "uuid", "minute": 86,
                    "possession_team_name": "Spain", "include_keeper": false }
    }
  ],
  "match_metadata": { "match_id": 3943043, "competition": "UEFA Euro 2024", "match_label": "Spain vs England" }
}
```

```bash
uv run python libs/statsbomb/extract_convex_hull.py
```

---

### `extract_progressive_map.py`

```python
extract_progressive_map(match_id: int, team: str, threshold: float = 0.25) -> pd.DataFrame
```

Extracts all open-play passes and carries for a team, flagging each action as
progressive (25%-of-remaining-distance-to-goal-centre rule). Set pieces excluded
via `play_pattern`. Passes include completed and incomplete; carries always completed.

**DataFrame columns:** `event_id, action_type, display_name, x0, y0, x1, y1, completed, progressive, distance_gained, minute`

**Output:** `libs/footballd3/sample_data/progressive_map_{match_id}_{team_slug}.json`

```json
{
  "team": "Spain",
  "actions": [
    { "action_type": "pass", "display_name": "Pedri",
      "x0": 45.2, "y0": 32.1, "x1": 67.8, "y1": 29.4,
      "completed": true, "progressive": true, "distance_gained": 18.4, "minute": 23 }
  ],
  "params": { "progressive_threshold": 0.25 },
  "metadata": { "match_id": 3943043, "team": "Spain" }
}
```

```bash
uv run python libs/statsbomb/extract_progressive_map.py
```

---

### `extract_possession.py`

```python
extract_possession(match_id: int, possession_id: int) -> pd.DataFrame
```

Extracts all events for a single possession. `main()` auto-selects the richest
Spain possession (most distinct event types) as the showcase.

**DataFrame columns:** `event_id, event_type, seconds, x, y, end_x, end_y, player, outcome`
**df.attrs:** `possession_team`

**Output:** `libs/footballd3/sample_data/possession_{match_id}_{possession_id}.json`

```json
{
  "match_id": 3943043, "possession": 60, "team": "Spain",
  "events": [
    { "event_id": "uuid", "event_type": "Pass", "seconds": 0.0,
      "x": 37.8, "y": 15.5, "end_x": 56.6, "end_y": 24.7,
      "player": "Marc Cucurella", "outcome": null }
  ],
  "metadata": { "match_id": 3943043, "possession": 60 }
}
```

`end_x`/`end_y` non-null for Pass/Carry/Shot; `null` for all other types.
`outcome` non-null only for failed passes; `null` = completed.

```bash
uv run python libs/statsbomb/extract_possession.py
```

---

### `extract_heatmap.py`

```python
extract_heatmap(match_id: int, player_name: str | None = None) -> pd.DataFrame
```

Extracts all on-ball events for a player. `main()` defaults to Pedri.
On-ball = every event where the player is the actor and a location is present.

**DataFrame columns:** `event_id, x, y, event_type, minute, display_name, team`
**df.attrs:** `display_name, team`

**Output:** `libs/footballd3/sample_data/heatmap_{match_id}_{player_slug}.json`

```json
{
  "grid": { "cols": 60, "rows": 40, "values": [[0.0012, ...], ...] },
  "metadata": { "match_id": 3943043, "display_name": "Pedri", "team": "Spain",
                "event_count": 89, "bandwidth_yards": 6.0 }
}
```

```bash
uv run python libs/statsbomb/extract_heatmap.py
```

---

### `extract_pass_network.py`

```python
extract_pass_network(match_id: int, team: str) -> pd.DataFrame
```

Splits completed passes into substitution windows; computes per-window average-position
nodes and directed-pair edge counts.

**DataFrame columns:** `window_index, window_label, from_player, from_x, from_y, to_player, count`

**Output:** `libs/footballd3/sample_data/pass_network_{match_id}_{team_slug}.json`

```json
{
  "windows": [
    {
      "index": 0, "label": "0'–45' (Starting XI)",
      "nodes": [{ "player": "Rodri", "x": 60.2, "y": 40.1, "passes": 72 }],
      "edges": [{ "from": "Rodri", "to": "Pedri", "count": 14 }]
    }
  ],
  "substitutions": [{ "minute": 45, "player_off": "Rodri", "player_on": "Zubimendi" }],
  "metadata": { "match_id": 3943043, "team": "Spain" }
}
```

```bash
uv run python libs/statsbomb/extract_pass_network.py
```

---

### `extract_formation.py`

```python
extract_formation(match_id: int, team: str) -> pd.DataFrame
```

Reads the Starting XI event and every Tactical Shift to produce an ordered
sequence of formation periods with canonical template coordinates.
Template coordinates are formation-slot positions, NOT measured from play.

**DataFrame columns:** `formation, from_minute, to_minute, player, display_name, jersey_number, position, template_x, template_y`

**Output:** `libs/footballd3/sample_data/formation_{match_id}_{team_slug}.json`

```json
{
  "periods": [
    {
      "formation": "4-3-3", "from_minute": 0, "to_minute": 55,
      "players": [
        { "player": "Unai Simón", "display_name": "Unai Simón",
          "jersey_number": 23, "position": "Goalkeeper",
          "template_x": 5.0, "template_y": 40.0 }
      ]
    }
  ],
  "metadata": { "match_id": 3943043, "team": "Spain" }
}
```

```bash
uv run python libs/statsbomb/extract_formation.py
```

---

### `extract_team_shape.py`

```python
extract_team_shape_on_ball(match_id: int, team: str) -> pd.DataFrame
```

Per-player mean position from open-play in-possession events, split by
substitution period. Coordinates normalized so the team always attacks right.

**DataFrame columns:** `period_from_minute, period_to_minute, player_id, player, display_name, x, y, event_count`
**df.attrs:** `periods_meta` (per-period hull + players_in/out), `competition`, `match_label`

```python
extract_team_shape_off_ball(
    match_id: int, team: str,
    bandwidth_yards: float = 8.0,
    depth_percentile: int = 70,
    cols: int = 24,
    rows: int = 16,
) -> dict
```

Aggregate off-ball shape from 360 frames while the team is out of possession.
Returns a density grid, centroid, thirds-spine, covariance ellipse, and depth line.
Uses teammate-boolean inversion: when the actor is an opponent, `teammate=True` marks
opponents and `teammate=False` marks the analyzed team.

**Output:** `libs/footballd3/sample_data/team_shape_{match_id}_{team_slug}.json`

```json
{
  "on_ball": {
    "periods": [
      {
        "from_minute": 0, "to_minute": 45,
        "players_in": ["Pedri"], "players_out": [],
        "nodes": [{ "player_id": 6731, "display_name": "Pedri", "x": 74.3, "y": 42.1, "event_count": 58 }],
        "hull": [[65.0, 20.0], [80.0, 60.0]]
      }
    ]
  },
  "off_ball": {
    "density_grid": { "cols": 24, "rows": 16, "values": [[0.0003, ...], ...] },
    "centroid": { "x": 48.2, "y": 41.0 },
    "thirds_spine": [{ "third": "defensive", "x": 20.0, "y": 41.0 }],
    "ellipse": { "cx": 48.2, "cy": 41.0, "rx": 18.4, "ry": 9.1, "angle_deg": 12.5 },
    "depth_line": { "x": 60.0, "percentile": 70 }
  },
  "metadata": { "match_id": 3943043, "team": "Spain" }
}
```

```bash
uv run python libs/statsbomb/extract_team_shape.py
```

---

### `extract_xt.py`

```python
extract_xt(match_id: int) -> pd.DataFrame
build_grid_json() -> dict
```

Applies Karun Singh's `open_xt_12x8_v1` to all credited open-play ball-progression
actions. Credited: completed open-play passes and carries. Excluded: shots, incomplete
passes, set-piece phases. Both teams included.

**DataFrame columns:** `event_id, team, display_name, minute, second, x0, y0, x1, y1, start_zone, end_zone, xt_delta, action_type`

**Grid provenance:** `open_xt_12x8_v1`, trained on Karun Singh's own corpus — not
StatsBomb data, not calibrated to Euro 2024.

**Output:** `xt_grid.json` + `xt_actions_{match_id}.json`

```bash
uv run python libs/statsbomb/extract_xt.py
```

---

### `extract_momentum.py`

```python
extract_momentum(
    match_id: int,
    window_minutes: int = 3,
    decay_alpha: float = 0.6,
    aggregation: str = "max",
) -> pd.DataFrame
```

Thin windowing layer on `xt_actions_{match_id}.json` — does NOT recompute xT.
Aggregates deltas into a per-minute momentum curve: `raw_threat = max(0, max(xt_delta))`;
apply exponential decay window; `momentum = home_smoothed − away_smoothed`.
Secondary series at 2× the window is emitted alongside.

**Dependency:** run `extract_xt.py` first.

**DataFrame columns:** `minute, home_threat, away_threat, momentum`
**df.attrs:** `home_team, away_team, secondary_minutes, goals, red_cards, params, competition, season, match_label, grid_source`

**Output:** `libs/footballd3/sample_data/momentum_{match_id}.json`

```bash
uv run python libs/statsbomb/extract_momentum.py
```

---

### `extract_goal_animation.py`

```python
extract_goal_animation(match_id: int, window_seconds: float = 10.0) -> pd.DataFrame
extract_play_animation(match_id: int, anchor_event_id: str, window_seconds: float = 10.0) -> pd.DataFrame
```

`extract_goal_animation` finds all goals and builds a clip of the preceding
`window_seconds` for each. `extract_play_animation` is the general engine for
any anchor event. Both return flat DataFrames; `extract_goal_animation` stores
the full clip dicts in `df.attrs["clips"]` for JSON reconstruction.

Clip window is period-isolated. Start timing snaps to the nearest real event.
Ball Receipt* excluded. Point events (Pressure, Duel, etc.) set `ball_end_x/y = null`.

**DataFrame columns:** `goal_event_id, goal_minute, goal_scorer, goal_team, event_id, t_seconds, team, event_type, ball_x, ball_y, ball_end_x, ball_end_y, actor, outcome`

**Output:** `libs/footballd3/sample_data/goal_animation_{match_id}.json`

```json
{
  "goals": [
    {
      "window": { "anchor_event_id": "uuid", "period": 2, "window_seconds": 10.0, "t_span_seconds": 10.686 },
      "frames": [
        { "event_id": "uuid", "t_seconds": 0.0, "team": "Spain", "event_type": "Carry",
          "ball_x": 25.1, "ball_y": 50.6, "ball_end_x": 27.0, "ball_end_y": 43.8,
          "actor": "Aymeric Laporte", "outcome": null }
      ],
      "context": { "goal": { "minute": 86, "scorer": "Mikel Oyarzabal", "team": "Spain" } },
      "metadata": { "match_id": 3943043 }
    }
  ],
  "match_metadata": { "match_id": 3943043 }
}
```

```bash
uv run python libs/statsbomb/extract_goal_animation.py
```

---

### `extract_match_stats.py`

```python
extract_match_stats(match_id: int) -> pd.DataFrame
load_team_colors(out_dir: Path) -> dict
```

Computes match-level statistics for both teams. Possession = share of
`possession_team`-tagged events. Yellow/red cards from `foul_committed_card`
and `bad_behaviour_card` columns.

**DataFrame columns:** `label, home_value, away_value, scale_type, format, tier`
**df.attrs:** `home_team, away_team, home_score, away_score, competition, match_label`

**Output:** `libs/footballd3/sample_data/match_stats_{match_id}.json`

```json
{
  "home": { "team": "Spain", "color": "#9F1239", "score": 2 },
  "away": { "team": "England", "color": "#1E3A5F", "score": 1 },
  "rows": [
    { "label": "Shots", "home_value": 12, "away_value": 9,
      "scale_type": "sum", "format": "int", "tier": "basic" }
  ],
  "metadata": { "match_id": 3943043 }
}
```

```bash
uv run python libs/statsbomb/extract_match_stats.py
```

---

## Running all extractors

```bash
uv run python libs/statsbomb/extract_shots.py
uv run python libs/statsbomb/extract_freeze_frame.py
uv run python libs/statsbomb/extract_convex_hull.py
uv run python libs/statsbomb/extract_progressive_map.py
uv run python libs/statsbomb/extract_possession.py
uv run python libs/statsbomb/extract_heatmap.py
uv run python libs/statsbomb/extract_pass_network.py
uv run python libs/statsbomb/extract_formation.py
uv run python libs/statsbomb/extract_team_shape.py
uv run python libs/statsbomb/extract_xt.py       # must run before extract_momentum
uv run python libs/statsbomb/extract_momentum.py
uv run python libs/statsbomb/extract_goal_animation.py
uv run python libs/statsbomb/extract_match_stats.py
```

## Dependencies

Managed by `uv` via `pyproject.toml`:

```bash
uv sync
```

Core: `statsbombpy`, `pandas`, `numpy`, `scipy`.
