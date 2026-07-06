# statsbomb

Python package for extracting StatsBomb open data and writing flat JSON files
that the footballd3 component library consumes. All IDs are resolved live via
the StatsBomb API — never hardcoded.

## Modules

---

### `extract_shots.py`

Extracts shot events for the UEFA Euro 2024 Final and writes the shot contract
consumed by `shotMap.js`.

#### Functions

```python
resolve_euro_2024_final() -> int
```
Resolves the Euro 2024 Final match ID live. Raises `ValueError` if the Final
cannot be isolated unambiguously.

```python
extract_shots(match_id: int) -> list[dict]
```
Filters events to `type == "Shot"`, maps each row to the minimal shot contract.
Drops shots where `xg` is NaN (own goals carry no StatsBomb xG value).

```python
main() -> None
```
Orchestrates and writes `shots_{match_id}.json`.

#### Output contract

`src/footballd3/sample_data/shots_{match_id}.json` — array of shot objects:

```json
[
  { "x": 108.0, "y": 38.5, "xg": 0.28, "outcome": "Goal",
    "is_goal": true, "team": "Spain", "player": "Mikel Oyarzabal", "minute": 86 }
]
```

```bash
uv run python src/statsbomb/extract_shots.py
```

---

### `extract_pass_network.py`

Extracts a substitution-windowed pass network for one team and writes the
contract consumed by `passNetwork.js`.

Each window spans from one substitution to the next (window 0 = starting XI).
Only completed passes are included.

#### Functions

```python
resolve_euro_2024_final() -> int
```

```python
extract_pass_network(match_id: int, team: str) -> dict
```
Splits completed passes into substitution windows; computes per-window
avg-position nodes and directed-pair edge counts.

```python
main() -> None
```
Runs for both Spain and England; writes `pass_network_{match_id}_{team}.json`.

#### Output contract

`src/footballd3/sample_data/pass_network_{match_id}_{team}.json`:

```json
{
  "windows": [
    {
      "index": 0,
      "label": "0'–45' (Starting XI)",
      "nodes": [{ "player": "Rodri", "x": 60.2, "y": 40.1, "passes": 72 }],
      "edges": [{ "from": "Rodri", "to": "Pedri", "count": 14 }]
    }
  ],
  "substitutions": [{ "minute": 45, "player_off": "Rodri", "player_on": "Zubimendi" }],
  "metadata": { "match_id": 3943043, "team": "Spain", "filter": "completed passes, per substitution window" }
}
```

```bash
uv run python src/statsbomb/extract_pass_network.py
```

---

### `extract_freeze_frame.py`

Loads 360 freeze frames for all goals in a match and writes the contract
consumed by `freezeFrame.js`. Workaround for `sb.frames()` `InvalidIndexError`
on `statsbombpy` v1.18: reads frames directly from the StatsBomb open-data
GitHub raw JSON.

#### Functions

```python
resolve_euro_2024_final() -> int
load_frames(match_id: int) -> dict
find_goal_frames(events: pd.DataFrame, frame_lookup: dict) -> list
transform_frame(event_row: pd.Series, frame_data: dict, match_id: int) -> dict
main() -> None
```

#### Output contract

`src/footballd3/sample_data/freeze_frames_{match_id}_goals.json`:

```json
{
  "goals": [
    {
      "ball": { "x": 111.0, "y": 36.8 },
      "frame": [{ "x": 108.5, "y": 37.2, "teammate": true, "actor": false, "keeper": false }],
      "visible_area": [0.0, 80.0, 120.0, 80.0, 120.0, 0.0, 0.0, 0.0],
      "metadata": { "match_id": 3943043, "event_id": "uuid", "display_name": "Mikel Oyarzabal",
                    "team": "Spain", "action_type": "Shot", "minute": 86,
                    "competition": "UEFA Euro 2024", "match_label": "Spain vs England" }
    }
  ],
  "match_metadata": { "match_id": 3943043, "competition": "UEFA Euro 2024", "match_label": "Spain vs England" }
}
```

```bash
uv run python src/statsbomb/extract_freeze_frame.py
```

---

### `extract_convex_hull.py`

Reads 360 freeze frames for each goal and computes convex hull geometry for
both teams at each goal instant. Consumed by `convexHull.js`.

`teammate` booleans in 360 frames are actor-relative, not team-relative; the
extractor performs the possession-team comparison explicitly to label
offense/defense correctly for any event type.

#### Functions

```python
resolve_euro_2024_final() -> int
load_frames(match_id: int) -> dict
find_goal_events(match_id: int) -> pd.DataFrame
split_teams(frame_players, actor_team, possession_team) -> tuple[list, list]
compute_hull(players: list, include_keeper: bool) -> dict | None
main() -> None
```

#### Output contract

`src/footballd3/sample_data/convex_hull_{match_id}_goals.json`:

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
                    "possession_team_name": "Spain", "actor_team_name": "Spain",
                    "include_keeper": false }
    }
  ],
  "match_metadata": { "match_id": 3943043, "competition": "UEFA Euro 2024", "match_label": "Spain vs England" }
}
```

```bash
uv run python src/statsbomb/extract_convex_hull.py
```

---

### `extract_heatmap.py`

Extracts all on-ball events for a player and computes a KDE density surface
using a Gaussian kernel. Consumed by `heatmap.js`.

On-ball events = every event where the player is the actor and a location is
present (passes, shots, carries, pressures, duels, ball receipts, etc.). This
is NOT player movement or off-ball positioning.

#### Functions

```python
resolve_euro_2024_final() -> int
extract_player_events(match_id: int, player_name: str | None = None) -> tuple[str, str, list[dict]]
compute_kde_grid(events: list[dict], bandwidth_yards: float, cols: int, rows: int) -> dict
main() -> None
```

#### Output contract

`src/footballd3/sample_data/heatmap_{match_id}_{player_slug}.json`:

```json
{
  "grid": { "cols": 60, "rows": 40, "values": [[0.0012, ...], ...] },
  "metadata": { "match_id": 3943043, "display_name": "Pedri", "team": "Spain",
                "competition": "UEFA Euro 2024", "match_label": "Spain vs England",
                "event_count": 89, "method": "gaussian_kde",
                "bandwidth_yards": 6.0, "grid_cols": 60, "grid_rows": 40,
                "pitch_width_yards": 120, "pitch_height_yards": 80 }
}
```

```bash
uv run python src/statsbomb/extract_heatmap.py
```

---

### `extract_match_stats.py`

Computes match-level statistics for both teams and writes the contract consumed
by `matchStats.js` and `comparisonBars.js`.

Possession = share of `possession_team`-tagged events per team. Yellow/red
cards sourced from `foul_committed_card` and `bad_behaviour_card` columns.

#### Functions

```python
resolve_euro_2024_final() -> int
load_team_colors(out_dir: Path) -> dict
extract_match_stats(match_id: int) -> dict
main() -> None
```

#### Output contract

`src/footballd3/sample_data/match_stats_{match_id}.json`:

```json
{
  "home": { "team": "Spain", "color": "#9F1239", "score": 2 },
  "away": { "team": "England", "color": "#1E3A5F", "score": 1 },
  "rows": [
    { "label": "Shots", "home_value": 12, "away_value": 9,
      "scale_type": "sum", "format": "int", "tier": "basic" }
  ],
  "metadata": { "match_id": 3943043, "competition": "UEFA Euro 2024", "match_label": "Spain vs England" }
}
```

```bash
uv run python src/statsbomb/extract_match_stats.py
```

---

### `extract_formation.py`

Reads the Starting XI event and every Tactical Shift to produce an ordered
sequence of formation periods with template coordinates. Consumed by
`formation.js`.

Template coordinates are canonical formation-slot positions, NOT measured
from play. They are derived from `formation_templates.json`.

#### Functions

```python
resolve_euro_2024_final() -> int
load_formation_templates() -> dict
extract_formation_periods(match_id: int, team: str) -> list[dict]
main() -> None
```

#### Output contract

`src/footballd3/sample_data/formation_{match_id}_{team_slug}.json`:

```json
{
  "periods": [
    {
      "formation": "4-3-3",
      "from_minute": 0,
      "to_minute": 55,
      "players": [
        { "player": "Unai Simón", "display_name": "Unai Simón",
          "jersey_number": 23, "position": "Goalkeeper",
          "template_x": 5.0, "template_y": 40.0 }
      ]
    }
  ],
  "metadata": { "match_id": 3943043, "team": "Spain", "competition": "UEFA Euro 2024",
                "match_label": "Spain vs England",
                "coordinate_note": "template_x/y are canonical formation-slot positions in StatsBomb 120×80 space." }
}
```

```bash
uv run python src/statsbomb/extract_formation.py
```

---

### `extract_team_shape.py`

Produces two measurements of team shape from events and 360 frames:

- **On-ball (in-possession):** event-based; per-player mean position from
  open-play events where `possession_team == team`. Produces player nodes
  and a convex hull. Split by substitution period.
- **Off-ball (out-of-possession):** frame-based, anonymous; pools 360 frame
  dots for the team while the opponent has the ball. Produces a density grid,
  centroid, thirds-spine, covariance ellipse, and a depth percentile line.

Normalizes attack direction so the analyzed team always attacks right
(increasing x). Open-play only; set-piece phases excluded.

#### Functions

```python
resolve_euro_2024_final() -> int
load_frames(match_id: int) -> dict
extract_on_ball(events, team, attack_dir_by_period, nicknames) -> dict
extract_off_ball(events, frame_lookup, team, attack_dir_by_period,
                 bandwidth_yards, depth_percentile, cols, rows) -> dict
main() -> None
```

#### Output contract

`src/footballd3/sample_data/team_shape_{match_id}_{team_slug}.json`:

```json
{
  "on_ball": {
    "periods": [
      {
        "from_minute": 0, "to_minute": 45,
        "players_in": ["Pedri"], "players_out": [],
        "nodes": [{ "player_id": 6731, "player": "Pedri González",
                    "display_name": "Pedri", "x": 74.3, "y": 42.1, "event_count": 58 }],
        "hull": [[65.0, 20.0], [80.0, 60.0]]
      }
    ]
  },
  "off_ball": {
    "density_grid": { "cols": 24, "rows": 16, "values": [[0.0003, ...], ...] },
    "centroid": { "x": 48.2, "y": 41.0 },
    "thirds_spine": [{ "third": "def", "x": 20.0, "y": 41.0 }],
    "ellipse": { "cx": 48.2, "cy": 41.0, "rx": 18.4, "ry": 9.1, "angle_deg": 12.5 },
    "depth_percentile": [{ "x": 60.0, "y": 41.0 }]
  },
  "metadata": { "match_id": 3943043, "team": "Spain" }
}
```

```bash
uv run python src/statsbomb/extract_team_shape.py
```

---

### `extract_progressive_map.py`

Extracts all open-play passes and carries for a team, flagging each action
as progressive using StatsBomb's 25%-of-remaining-distance-to-goal-centre rule.
Consumed by `progressiveMap.js`.

Set pieces excluded via `play_pattern`. Passes include both completed and
incomplete. Carries are always completed — StatsBomb has no incomplete-carry event.

#### Functions

```python
resolve_euro_2024_final() -> int
extract_progressive_map(match_id: int, team: str, threshold: float = 0.25) -> dict
main() -> None
```

#### Output contract

`src/footballd3/sample_data/progressive_map_{match_id}_{team_slug}.json`:

```json
{
  "team": "Spain",
  "actions": [
    { "action_type": "pass", "display_name": "Pedri",
      "x0": 45.2, "y0": 32.1, "x1": 67.8, "y1": 29.4,
      "completed": true, "progressive": true, "distance_gained": 18.4, "minute": 23 }
  ],
  "params": { "progressive_threshold": 0.25 },
  "metadata": { "match_id": 3943043, "team": "Spain", "competition": "UEFA Euro 2024",
                "match_label": "Spain vs England", "set_piece_filter": "play_pattern" }
}
```

```bash
uv run python src/statsbomb/extract_progressive_map.py
```

---

### `extract_possession.py`

Extracts all events for a single possession and writes the flat contract
consumed by both `eventScatter.js` (spatial) and `timelineStrip.js` (temporal).

`main()` auto-selects the richest Spain possession (most distinct event types)
as the showcase; call `extract_possession(match_id, possession_id)` directly
for any specific possession.

#### Functions

```python
resolve_euro_2024_final() -> int
extract_possession(match_id: int, possession_id: int) -> dict
main() -> None
```

#### Output contract

`src/footballd3/sample_data/possession_{match_id}_{possession_id}.json`:

```json
{
  "match_id": 3943043,
  "possession": 60,
  "team": "Spain",
  "events": [
    { "event_id": "uuid", "event_type": "Pass", "seconds": 0.0,
      "x": 37.8, "y": 15.5, "end_x": 56.6, "end_y": 24.7,
      "player": "Marc Cucurella", "outcome": null }
  ],
  "metadata": { "match_id": 3943043, "possession": 60, "team": "Spain",
                "competition": "UEFA Euro 2024", "match_label": "Spain vs England" }
}
```

`end_x`/`end_y` non-null for Pass/Carry/Shot; `null` for all other types.
`outcome` non-null only for failed passes; `null` = completed.

```bash
uv run python src/statsbomb/extract_possession.py
```

---

### `extract_xt.py`

Applies Karun Singh's published open xT grid (`open_xt_12x8_v1`) to all
credited open-play ball-progression actions in a match. Writes both the grid
surface (for `xtSurface.js`) and per-action deltas (for `momentumChart.js`
and downstream analysis).

Credited actions: completed open-play passes and open-play carries. Excluded:
shots, incomplete passes, set-piece phases.

**Grid provenance:** `open_xt_12x8_v1`, trained on Karun Singh's own match
corpus — not StatsBomb data and not Euro 2024. Values are directionally
meaningful but not calibrated to this competition.

#### Functions

```python
resolve_euro_2024_match() -> tuple[int, str, str, str]
build_grid_json() -> dict
extract_xt(match_id: int, competition: str, season: str, match_label: str) -> dict
main() -> None
```

#### Output contracts

`src/footballd3/sample_data/xt_grid.json`:

```json
{
  "rows": 8, "cols": 12,
  "values": [[0.00638, ...], ...],
  "source": "Karun Singh open_xt_12x8_v1",
  "source_url": "https://karun.in/blog/data/open_xt_12x8_v1.json",
  "pitch_dims": { "width_yards": 120, "height_yards": 80 },
  "cell_dims": { "width_yards": 10.0, "height_yards": 10.0 }
}
```

`src/footballd3/sample_data/xt_actions_{match_id}.json`:

```json
{
  "actions": [
    { "event_id": "uuid", "team": "Spain", "display_name": "Pedri",
      "minute": 23, "second": 41,
      "x0": 45.2, "y0": 32.1, "x1": 67.8, "y1": 29.4,
      "start_zone": [3, 4], "end_zone": [3, 6], "xt_delta": 0.00324, "action_type": "Pass" }
  ],
  "metadata": { "match_id": 3943043, "competition": "UEFA Euro", "season": "2024",
                "match_label": "Spain vs England", "grid_source": "Karun Singh open_xt_12x8_v1",
                "grid_dims": [8, 12], "n_actions": 685 }
}
```

```bash
uv run python src/statsbomb/extract_xt.py
```

---

### `extract_momentum.py`

Thin windowing layer on top of `xt_actions_{match_id}.json` — does NOT
recompute xT. Aggregates per-action deltas into a per-minute match momentum
curve using MAX aggregation and an exponential decay window. Consumed by
`momentumChart.js`.

**Construction:** per minute per team `raw_threat = max(0, max(xt_delta))`;
apply exponential decay window (default α=0.6, window=3 min); emit
`momentum = home_smoothed − away_smoothed`. A secondary series at 2× the
window length is emitted alongside for D3 overlay comparison.

**Caveats:** measures attacking-threat generated (not defensive resistance
or off-ball pressure); curve shape is window-dependent; xT grid is not
calibrated to Euro 2024.

**Dependency:** run `extract_xt.py` first to produce the `xt_actions` file.

#### Functions

```python
extract_momentum(match_id: int, competition: str, season: str, match_label: str,
                 window_minutes: int = 3, decay_alpha: float = 0.6,
                 aggregation: str = "max") -> dict
main() -> None
```

#### Output contract

`src/footballd3/sample_data/momentum_{match_id}.json`:

```json
{
  "home_team": "Spain",
  "away_team": "England",
  "minutes": [{ "minute": 47, "home_threat": 0.0019, "away_threat": 0.0, "momentum": 0.0019 }],
  "secondary_minutes": [{ "minute": 47, "home_threat": 0.0016, "away_threat": 0.0, "momentum": 0.0016 }],
  "goals": [{ "minute": 86, "team": "Spain", "player": "Mikel Oyarzabal", "is_own_goal": false }],
  "red_cards": [],
  "params": { "window_minutes": 3, "weighting": "exponential", "decay_alpha": 0.6,
               "aggregation": "max", "secondary_window_minutes": 6 },
  "metadata": { "match_id": 3943043, "competition": "UEFA Euro", "season": "2024",
                "match_label": "Spain vs England", "grid_source": "Karun Singh open_xt_12x8_v1" }
}
```

```bash
uv run python src/statsbomb/extract_momentum.py
```

---

### `extract_goal_animation.py`

Extracts time-windowed ball-path event sequences for all goals in a match.
The general engine (`extract_play_animation`) works for any anchor event;
`extract_goal_animation` is a thin wrapper that finds all goals and injects
`context.goal` metadata. Consumed by `playAnimation.js`.

Clip window is period-isolated (never straddles halftime/extra-time). Start
timing snaps to the nearest real event at or before `anchor − window_seconds`.
Both teams' events are included; Ball Receipt* excluded.

**Included event types:** Pass, Carry, Shot (ball moves) + Pressure, Duel,
Interception, Ball Recovery (point events, `ball_end_x/y = null`).

```python
resolve_euro_2024_final() -> int
extract_play_animation(match_id: int, anchor_event_id: str,
                       window_seconds: float = 10.0) -> dict
extract_goal_animation(match_id: int, window_seconds: float = 10.0) -> list[dict]
main() -> None
```

#### Output contract

`src/footballd3/sample_data/goal_animation_{match_id}.json`:

```json
{
  "goals": [
    {
      "window": { "anchor_event_id": "uuid", "start_event_id": "uuid", "end_event_id": "uuid",
                  "period": 2, "window_seconds": 10.0, "t_span_seconds": 10.686 },
      "frames": [
        { "event_id": "uuid", "t_seconds": 0.0, "team": "Spain", "event_type": "Carry",
          "ball_x": 25.1, "ball_y": 50.6, "ball_end_x": 27.0, "ball_end_y": 43.8,
          "actor": "Aymeric Laporte", "outcome": null }
      ],
      "context": {
        "goal": { "event_id": "uuid", "minute": 86, "second": 56,
                  "scorer": "Mikel Oyarzabal", "team": "Spain" }
      },
      "metadata": { "match_id": 3943043, "competition": "UEFA Euro 2024", "match_label": "Spain vs England" }
    }
  ],
  "match_metadata": { "match_id": 3943043, "competition": "UEFA Euro 2024", "match_label": "Spain vs England" }
}
```

`t_seconds` is clip-relative (0.0 at first frame). `ball_end_x/y` null for
point events. `context.goal` absent for general clips from `extract_play_animation`.

```bash
uv run python src/statsbomb/extract_goal_animation.py
```

---

## Dependencies

Managed by `uv` via `pyproject.toml`. Activate the project environment before
running any extractor:

```bash
uv sync
```

Core: `statsbombpy`, `pandas`, `numpy`, `scipy`.

`extract_momentum.py` imports `resolve_euro_2024_match` from `extract_xt` — run
`extract_xt.py` first to produce the `xt_actions` file it depends on.
