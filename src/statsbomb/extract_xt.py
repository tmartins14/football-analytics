"""Extract Expected Threat (xT) values for all open-play ball-progression actions in a match.

Applies Karun Singh's published open xT grid (open_xt_12x8_v1, karun.in) to StatsBomb
events. Credited actions are completed open-play passes and completed carries — set pieces
excluded, shots excluded (they are the terminal reward the grid is built from, not a
credited move). xT delta = grid_value(end_zone) - grid_value(start_zone). Negative
deltas (ball moved away from goal) are preserved; consumers filter as needed.

Grid provenance: Karun Singh's open_xt_12x8_v1 (8 rows x 12 cols, 96 cells), trained on
his own match corpus — NOT StatsBomb data and NOT Euro 2024. Values are transferred, not
fitted to this dataset; they are directionally meaningful but not calibrated to Euro 2024.
Karun's original blog post (karun.in/blog/expected-threat) describes a 16x12 grid;
open_xt_12x8_v1 is the only published standalone JSON he has released.

Public API:
    resolve_euro_2024_match() -> tuple[int, str, str, str]
    build_grid_json() -> dict
    extract_xt(match_id, competition, season, match_label) -> dict
    main()

JSON outputs (both written to src/footballd3/sample_data/):
    xt_grid.json                         — grid surface for D3 rendering
    xt_actions_{match_id}.json           — per-action xT deltas for the match

xt_grid.json shape:
    {
        "rows": 8, "cols": 12,
        "values": [[...], ...],
        "source": "Karun Singh open_xt_12x8_v1",
        "source_url": "https://karun.in/blog/data/open_xt_12x8_v1.json",
        "pitch_dims": {"width_yards": 120, "height_yards": 80},
        "cell_dims": {"width_yards": 10.0, "height_yards": 10.0}
    }

xt_actions_{match_id}.json shape:
    {
        "actions": [
            {
                "event_id": str, "team": str, "display_name": str,
                "minute": int, "second": int,
                "x0": float, "y0": float, "x1": float, "y1": float,
                "start_zone": [row, col], "end_zone": [row, col],
                "xt_delta": float, "action_type": "Pass" | "Carry"
            }
        ],
        "metadata": {
            "match_id": int, "competition": str, "season": str,
            "match_label": str, "grid_source": str,
            "grid_dims": [8, 12], "n_actions": int
        }
    }
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

# Karun Singh's published open xT grid (open_xt_12x8_v1).
# Source: https://karun.in/blog/data/open_xt_12x8_v1.json  (verified 2026-07-03)
# Layout: XT_GRID[row][col] — row indexes Y-zone (0 = y~0 touchline, 7 = y~80 touchline),
#         col indexes X-zone (0 = defensive end, 11 = attacking end, x -> 120).
# Values are probability of possession leading to a goal from that zone.
XT_GRID: list[list[float]] = [
    [0.00638303, 0.00779616, 0.00844854, 0.00977659, 0.01126267, 0.01248344, 0.01473596, 0.01745060, 0.02122129, 0.02756312, 0.03485072, 0.03792590],
    [0.00750072, 0.00878589, 0.00942382, 0.01059490, 0.01214719, 0.01384540, 0.01611813, 0.01870347, 0.02401521, 0.02953272, 0.04066992, 0.04647721],
    [0.00887990, 0.00977745, 0.01001304, 0.01110462, 0.01269174, 0.01429128, 0.01685596, 0.01935132, 0.02412240, 0.02855202, 0.05491138, 0.06442595],
    [0.00941056, 0.01082722, 0.01016549, 0.01132376, 0.01262646, 0.01484598, 0.01689528, 0.01997070, 0.02385149, 0.03511326, 0.10805102, 0.25745362],
    [0.00941056, 0.01082722, 0.01016549, 0.01132376, 0.01262646, 0.01484598, 0.01689528, 0.01997070, 0.02385149, 0.03511326, 0.10805102, 0.25745362],
    [0.00887990, 0.00977745, 0.01001304, 0.01110462, 0.01269174, 0.01429128, 0.01685596, 0.01935132, 0.02412240, 0.02855202, 0.05491138, 0.06442595],
    [0.00750072, 0.00878589, 0.00942382, 0.01059490, 0.01214719, 0.01384540, 0.01611813, 0.01870347, 0.02401521, 0.02953272, 0.04066992, 0.04647721],
    [0.00638303, 0.00779616, 0.00844854, 0.00977659, 0.01126267, 0.01248344, 0.01473596, 0.01745060, 0.02122129, 0.02756312, 0.03485072, 0.03792590],
]

_GRID_ROWS: int = 8
_GRID_COLS: int = 12
_PITCH_WIDTH: float = 120.0   # StatsBomb x-range in yards
_PITCH_HEIGHT: float = 80.0   # StatsBomb y-range in yards

# Set-piece play patterns to exclude from credited actions, matching the convention
# established in extract_progressive_map.py.
SET_PIECE_PLAY_PATTERNS: frozenset[str] = frozenset({
    "From Corner",
    "From Free Kick",
    "From Goal Kick",
    "From Kick Off",
    "From Throw In",
})


def resolve_euro_2024_match() -> tuple[int, str, str, str]:
    """Resolve a UEFA Euro 2024 Final match ID and metadata from the StatsBomb API.

    Locates the Final-stage match (Spain vs England) via live API calls to
    sb.competitions() and sb.matches() — no hardcoded IDs.

    Returns:
        tuple[int, str, str, str]: (match_id, competition_name, season_name, match_label)
            where match_label is "Home vs Away".

    Raises:
        ValueError: If UEFA Euro 2024 is not found in sb.competitions(), or if the Final
            cannot be isolated to a single row in sb.matches().
    """
    comps = sb.competitions()
    euro = comps[
        comps["competition_name"].str.contains("UEFA Euro", case=False)
        & (comps["season_name"] == "2024")
    ]
    if euro.empty:
        raise ValueError("Could not find UEFA Euro 2024 in sb.competitions()")

    competition_id = int(euro["competition_id"].iloc[0])
    season_id = int(euro["season_id"].iloc[0])
    competition_name = str(euro["competition_name"].iloc[0])
    season_name = str(euro["season_name"].iloc[0])

    matches = sb.matches(competition_id=competition_id, season_id=season_id)

    if "competition_stage" in matches.columns:
        final_rows = matches[
            matches["competition_stage"].astype(str).str.strip() == "Final"
        ]
    else:
        final_rows = matches.sort_values("match_date").iloc[[-1]]

    if final_rows.empty or len(final_rows) > 1:
        raise ValueError(
            f"Could not isolate Euro 2024 Final unambiguously. "
            f"Candidates:\n{final_rows[['match_id', 'match_date', 'home_team', 'away_team']]}"
        )

    row = final_rows.iloc[0]
    match_id = int(row["match_id"])
    match_label = f"{row['home_team']} vs {row['away_team']}"
    return match_id, competition_name, season_name, match_label


def _build_nickname_lookup(match_id: int) -> dict[int, str]:
    """Build a player_id -> display_name mapping from sb.lineups() for all teams in a match.

    display_name coalesces player_nickname (when non-empty) with player_name.
    Join by integer player_id, never by name string.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict[int, str]: Maps integer player_id to resolved display name.
    """
    lineups = sb.lineups(match_id=match_id)
    lookup: dict[int, str] = {}
    for team_df in lineups.values():
        for _, row in team_df.iterrows():
            nick = row.get("player_nickname")
            name = row["player_name"]
            display_name = nick if (pd.notna(nick) and nick) else name
            lookup[int(row["player_id"])] = display_name
    return lookup


def _map_to_zone(x: float, y: float) -> tuple[int, int]:
    """Map a StatsBomb (x, y) coordinate to an xT grid cell (row, col).

    Mapping is purely proportional: x / 120 gives the fractional position along the
    pitch length; y / 80 gives the fractional position along the width. This is
    independent of physical pitch dimensions — the 12x8 zone grid divides the pitch
    into equal proportional bands regardless of coordinate units.

    Boundary rule: exact upper-bound values (x=120.0, y=80.0) are clamped to the last
    valid cell index (col=11, row=7) rather than falling out of bounds.

    StatsBomb normalizes all events so the attacking team always has x -> 120. No
    coordinate flip is needed for either team — the lookup is direct for both.

    Args:
        x (float): StatsBomb x-coordinate in [0, 120].
        y (float): StatsBomb y-coordinate in [0, 80].

    Returns:
        tuple[int, int]: (row, col) — row in [0, 7] indexes the Y-zone,
            col in [0, 11] indexes the X-zone (0=defensive end, 11=attacking end).
    """
    col = min(int(x / _PITCH_WIDTH * _GRID_COLS), _GRID_COLS - 1)
    row = min(int(y / _PITCH_HEIGHT * _GRID_ROWS), _GRID_ROWS - 1)
    return row, col


def build_grid_json() -> dict:
    """Build the xt_grid.json payload from the embedded XT_GRID constant.

    The payload carries full provenance metadata so D3 consumers and downstream
    analysts know the grid's origin and coordinate mapping without consulting the
    source code.

    Returns:
        dict: JSON contract with keys: rows, cols, values (the 8x12 grid),
            source, source_url, pitch_dims, cell_dims.
    """
    return {
        "rows": _GRID_ROWS,
        "cols": _GRID_COLS,
        "values": XT_GRID,
        "source": "Karun Singh open_xt_12x8_v1",
        "source_url": "https://karun.in/blog/data/open_xt_12x8_v1.json",
        "pitch_dims": {"width_yards": 120, "height_yards": 80},
        "cell_dims": {"width_yards": 10.0, "height_yards": 10.0},
    }


def extract_xt(
    match_id: int,
    competition: str,
    season: str,
    match_label: str,
) -> dict:
    """Extract xT deltas for all credited open-play ball-progression actions in a match.

    Credited actions:
    - Completed open-play passes: type == "Pass", pass_outcome is NaN (null = complete
      in StatsBomb encoding), play_pattern not in SET_PIECE_PLAY_PATTERNS.
    - Open-play carries: type == "Carry", play_pattern not in SET_PIECE_PLAY_PATTERNS.
      Carries are always completed — StatsBomb has no incomplete-carry event.

    Excluded: shots (terminal reward, not a credited move), incomplete passes,
    set-piece phases (play_pattern filter), events missing start/end location.
    Both teams' events are included in a single output file.

    xT delta = XT_GRID[end_row][end_col] - XT_GRID[start_row][start_col].
    Negative deltas (ball moved away from goal) are included; consumers may filter.

    Args:
        match_id (int): StatsBomb match ID.
        competition (str): Competition name for metadata.
        season (str): Season name for metadata.
        match_label (str): "Home vs Away" label for metadata.

    Returns:
        dict: JSON contract with keys: actions (list), metadata (dict).
            Each action: event_id, team, display_name, minute, second,
            x0, y0, x1, y1, start_zone, end_zone, xt_delta, action_type.
    """
    nicknames = _build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)

    open_play = events[~events["play_pattern"].isin(SET_PIECE_PLAY_PATTERNS)]

    actions: list[dict] = []

    # ── Completed open-play passes ─────────────────────────────────────────────
    passes = open_play[open_play["type"] == "Pass"]
    for _, row in passes.iterrows():
        # pass_outcome is NaN for completed passes; any non-null string is a failure.
        if not bool(pd.isna(row.get("pass_outcome"))):
            continue

        loc = row.get("location")
        end = row.get("pass_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue

        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])
        start_zone = list(_map_to_zone(x0, y0))
        end_zone = list(_map_to_zone(x1, y1))
        xt_delta = round(
            XT_GRID[end_zone[0]][end_zone[1]] - XT_GRID[start_zone[0]][start_zone[1]], 8
        )

        pid = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid)
            else str(row.get("player", ""))
        )

        actions.append({
            "event_id":     str(row["id"]),
            "team":         str(row["team"]),
            "display_name": display_name,
            "minute":       int(row["minute"]),
            "second":       int(row["second"]),
            "x0": x0, "y0": y0,
            "x1": x1, "y1": y1,
            "start_zone":   start_zone,
            "end_zone":     end_zone,
            "xt_delta":     xt_delta,
            "action_type":  "Pass",
        })

    # ── Open-play carries (always completed in StatsBomb) ──────────────────────
    carries = open_play[open_play["type"] == "Carry"]
    for _, row in carries.iterrows():
        loc = row.get("location")
        end = row.get("carry_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue

        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])
        start_zone = list(_map_to_zone(x0, y0))
        end_zone = list(_map_to_zone(x1, y1))
        xt_delta = round(
            XT_GRID[end_zone[0]][end_zone[1]] - XT_GRID[start_zone[0]][start_zone[1]], 8
        )

        pid = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid)
            else str(row.get("player", ""))
        )

        actions.append({
            "event_id":     str(row["id"]),
            "team":         str(row["team"]),
            "display_name": display_name,
            "minute":       int(row["minute"]),
            "second":       int(row["second"]),
            "x0": x0, "y0": y0,
            "x1": x1, "y1": y1,
            "start_zone":   start_zone,
            "end_zone":     end_zone,
            "xt_delta":     xt_delta,
            "action_type":  "Carry",
        })

    return {
        "actions": actions,
        "metadata": {
            "match_id":    match_id,
            "competition": competition,
            "season":      season,
            "match_label": match_label,
            "grid_source": "Karun Singh open_xt_12x8_v1",
            "grid_dims":   [_GRID_ROWS, _GRID_COLS],
            "n_actions":   len(actions),
        },
    }


def main() -> None:
    """Resolve the Euro 2024 Final, compute xT for all actions, and write both JSON files.

    Writes:
        src/footballd3/sample_data/xt_grid.json
        src/footballd3/sample_data/xt_actions_{match_id}.json
    """
    match_id, competition, season, match_label = resolve_euro_2024_match()
    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    grid_data = build_grid_json()
    grid_path = out_dir / "xt_grid.json"
    with open(grid_path, "w") as f:
        json.dump(grid_data, f, indent=2)
    print(f"Wrote grid ({grid_data['rows']}x{grid_data['cols']}) -> {grid_path}")

    actions_data = extract_xt(match_id, competition, season, match_label)
    actions_path = out_dir / f"xt_actions_{match_id}.json"
    with open(actions_path, "w") as f:
        json.dump(actions_data, f, indent=2)

    n = actions_data["metadata"]["n_actions"]
    n_pass = sum(1 for a in actions_data["actions"] if a["action_type"] == "Pass")
    n_carry = sum(1 for a in actions_data["actions"] if a["action_type"] == "Carry")
    n_pos = sum(1 for a in actions_data["actions"] if a["xt_delta"] > 0)
    print(f"Wrote {n} actions ({n_pass} passes, {n_carry} carries, {n_pos} positive xT) -> {actions_path}")


if __name__ == "__main__":
    main()
