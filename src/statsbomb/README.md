# statsbomb

Python package for extracting StatsBomb open data and writing flat JSON files
that the footballd3 component library consumes. All IDs are resolved live via
the StatsBomb API — never hardcoded.

## Modules

### `extract_pass_network.py`

Extracts a substitution-windowed pass network for one team from the UEFA Euro 2024
Final and writes the JSON contract consumed by the `passNetwork` component.

Each window covers the period between two consecutive substitutions (window 0 =
starting XI through first sub). Only completed passes are included.

#### Functions

```python
resolve_euro_2024_final() -> int
```
Resolves the Euro 2024 Final match ID live from `sb.competitions()` and
`sb.matches()`. Returns the StatsBomb `match_id`.

---

```python
extract_pass_network(match_id: int, team: str) -> dict
```
Pulls all events for the match, splits completed passes into substitution windows,
and computes per-window avg-position nodes and directed-pair edge counts. Returns
the full multi-window pass network dict.

---

```python
main() -> None
```
Orchestrates the above functions for both Spain and England and writes JSON.

## Output contract — pass network

Written to `src/footballd3/sample_data/pass_network_{match_id}_{team}.json`:

```json
{
  "windows": [
    {
      "index": 0,
      "label": "0'–45' (Starting XI)",
      "nodes": [{ "player": "Rodri", "x": 60.2, "y": 40.1, "passes": 72 }],
      "edges": [
        { "from": "Rodri", "to": "Pedri", "count": 14 },
        { "from": "Pedri", "to": "Rodri", "count": 9  }
      ]
    }
  ],
  "substitutions": [{ "minute": 45, "player_off": "Rodri", "player_on": "Zubimendi" }],
  "metadata": { "match_id": 3943043, "team": "Spain", "filter": "completed passes, per substitution window" }
}
```

Coordinates are StatsBomb-native (120×80 yards, origin top-left). Do not
transform them — `passNetwork.js` delegates to `pitch.px()` for pixel mapping.

---

### `extract_shots.py`

Extracts shot events for the UEFA Euro 2024 Final (Spain 2–1 England) and
writes the shot JSON contract consumed by the `shotMap` component.

#### Functions

```python
resolve_euro_2024_final() -> int
```
Calls `sb.competitions()` and `sb.matches()` to locate the Euro 2024 Final.
Returns the StatsBomb `match_id`. Raises `ValueError` if the competition or
the Final cannot be isolated unambiguously.

---

```python
extract_shots(match_id: int) -> list[dict]
```
Calls `sb.events(match_id=match_id)`, filters to `type == "Shot"`, and maps
each row to the minimal fields the shot map renderer needs. Drops shots where
`xg` is NaN (own goals carry no StatsBomb xG value).

---

```python
main() -> None
```
Orchestrates the above two functions and writes the output JSON. Run directly
to regenerate the sample data file.

## Output contract

Written to `src/footballd3/sample_data/shots_{match_id}.json`. One object per shot:

```json
[
  {
    "x": 108.0,
    "y": 38.5,
    "xg": 0.28,
    "outcome": "Goal",
    "is_goal": true,
    "team": "Spain",
    "player": "Mikel Oyarzabal",
    "minute": 86
  }
]
```

Coordinates are StatsBomb-native (120×80 yards, origin top-left). Do not
transform them — `shotMap.js` handles pixel mapping.

## Running

```bash
# From project root
.venv/bin/python src/statsbomb/extract_shots.py
# → Wrote 25 shots → src/footballd3/sample_data/shots_3943043.json
```

Or run the verification notebook:

```bash
.venv/bin/jupyter lab analyses/statsbomb/extract_shots.ipynb
```

## Dependencies

Managed by `uv` via `pyproject.toml`: `statsbombpy`, `pandas`. Activate the
project environment before running:

```bash
# Install / sync dependencies
uv sync
```
