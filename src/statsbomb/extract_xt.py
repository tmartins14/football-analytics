"""Extract Expected Threat (xT) values for all open-play ball-progression actions in a match.

Applies Karun Singh's published open xT grid (open_xt_12x8_v1) to StatsBomb events.
Credited actions are completed open-play passes and completed carries — set pieces
excluded, shots excluded (they are the terminal reward, not a credited move).
xT delta = grid_value(end_zone) - grid_value(start_zone). Negative deltas are preserved.

Grid provenance: Karun Singh's open_xt_12x8_v1 (8 rows x 12 cols), trained on his own
match corpus — NOT StatsBomb data and NOT Euro 2024. Values are directionally meaningful
but not calibrated to this dataset.

Public API:
    extract_xt(match_id) -> pd.DataFrame
    build_grid_json() -> dict
    main()

DataFrame columns: event_id, team, display_name, minute, second,
    x0, y0, x1, y1, start_zone, end_zone, xt_delta, action_type

JSON outputs (both written to src/footballd3/sample_data/):
    xt_grid.json              — grid surface for D3 rendering
    xt_actions_{match_id}.json — per-action xT deltas for the match
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import (
    SET_PIECE_PLAY_PATTERNS,
    build_nickname_lookup,
    fetch_match_info,
    resolve_match,
)

# Karun Singh's published open xT grid (open_xt_12x8_v1).
# Source: https://karun.in/blog/data/open_xt_12x8_v1.json  (verified 2026-07-03)
# Layout: XT_GRID[row][col] — row indexes Y-zone (0=y~0 touchline, 7=y~80 touchline),
#         col indexes X-zone (0=defensive end, 11=attacking end, x->120).
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

_GRID_ROWS: int   = 8
_GRID_COLS: int   = 12
_PITCH_WIDTH: float  = 120.0
_PITCH_HEIGHT: float = 80.0


def _map_to_zone(x: float, y: float) -> tuple[int, int]:
    """Map a StatsBomb (x, y) coordinate to an xT grid cell (row, col).

    Boundary rule: exact upper-bound values (x=120, y=80) are clamped to the last
    valid cell index. StatsBomb normalizes all events so the attacking team always
    has x -> 120, so no coordinate flip is needed.

    Args:
        x (float): StatsBomb x-coordinate in [0, 120].
        y (float): StatsBomb y-coordinate in [0, 80].

    Returns:
        tuple[int, int]: (row, col) — row in [0, 7] indexes Y-zone,
            col in [0, 11] indexes X-zone (0=defensive end, 11=attacking end).
    """
    col = min(int(x / _PITCH_WIDTH * _GRID_COLS), _GRID_COLS - 1)
    row = min(int(y / _PITCH_HEIGHT * _GRID_ROWS), _GRID_ROWS - 1)
    return row, col


def build_grid_json() -> dict:
    """Build the xt_grid.json payload from the embedded XT_GRID constant.

    Carries full provenance metadata so D3 consumers and downstream analysts know
    the grid's origin and coordinate mapping without consulting the source code.

    Returns:
        dict: JSON contract with keys: rows, cols, values (8×12 grid),
            source, source_url, pitch_dims, cell_dims.
    """
    return {
        "rows": _GRID_ROWS,
        "cols": _GRID_COLS,
        "values": XT_GRID,
        "source": "Karun Singh open_xt_12x8_v1",
        "source_url": "https://karun.in/blog/data/open_xt_12x8_v1.json",
        "pitch_dims": {"width_yards": 120, "height_yards": 80},
        "cell_dims":  {"width_yards": 10.0, "height_yards": 10.0},
    }


def extract_xt(match_id: int) -> pd.DataFrame:
    """Extract xT deltas for all credited open-play ball-progression actions as a DataFrame.

    Credited actions:
    - Completed open-play passes: type == "Pass", pass_outcome is NaN, not a set piece.
    - Open-play carries: type == "Carry", not a set piece. (Carries are always completed.)

    Excluded: shots, incomplete passes, set-piece phases, events missing locations.
    Both teams' events are included.

    xT delta = XT_GRID[end_row][end_col] - XT_GRID[start_row][start_col].
    Negative deltas (ball moved away from goal) are included; filter as needed.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pd.DataFrame: One row per credited action with columns:
            event_id (str): StatsBomb event UUID.
            team (str): Team name.
            display_name (str): Resolved player display name.
            minute, second (int): Match time.
            x0, y0, x1, y1 (float): Start and end coordinates in 120×80 yards.
            start_zone, end_zone (list[int]): [row, col] in the 8×12 xT grid.
            xt_delta (float): xT change from start_zone to end_zone.
            action_type (str): "Pass" or "Carry".
    """
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)
    open_play = events[~events["play_pattern"].isin(SET_PIECE_PLAY_PATTERNS)]

    records: list[dict] = []

    for _, row in open_play[open_play["type"] == "Pass"].iterrows():
        if not bool(pd.isna(row.get("pass_outcome"))):
            continue
        loc = row.get("location")
        end = row.get("pass_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue

        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])
        start_zone = list(_map_to_zone(x0, y0))
        end_zone   = list(_map_to_zone(x1, y1))
        xt_delta = round(
            XT_GRID[end_zone[0]][end_zone[1]] - XT_GRID[start_zone[0]][start_zone[1]], 8
        )
        pid = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid) else str(row.get("player", ""))
        )
        records.append({
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

    for _, row in open_play[open_play["type"] == "Carry"].iterrows():
        loc = row.get("location")
        end = row.get("carry_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue

        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])
        start_zone = list(_map_to_zone(x0, y0))
        end_zone   = list(_map_to_zone(x1, y1))
        xt_delta = round(
            XT_GRID[end_zone[0]][end_zone[1]] - XT_GRID[start_zone[0]][start_zone[1]], 8
        )
        pid = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid) else str(row.get("player", ""))
        )
        records.append({
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

    return pd.DataFrame(records)


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Compute xT for all match actions and write JSON files.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Per-match output directory; defaults to
            data/euro-2024/{match_id}/. The shared xt_grid.json is written one
            level above (data/).

    Writes:
        {out_dir.parent}/xt_grid.json  (shared across all matches)
        {out_dir}/xt_actions.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    competition, season, match_label = fetch_match_info(match_id)

    out_dir.mkdir(parents=True, exist_ok=True)

    grid_data = build_grid_json()
    # xt_grid.json is shared across all matches — write to the competition parent dir.
    grid_path = out_dir.parent.parent / "xt_grid.json"
    with open(grid_path, "w") as f:
        json.dump(grid_data, f, indent=2)
    print(f"Wrote grid ({grid_data['rows']}x{grid_data['cols']}) → {grid_path}")

    df = extract_xt(match_id)

    # Convert list columns to JSON-serialisable lists for the file contract.
    actions = df.to_dict(orient="records")
    payload = {
        "actions": actions,
        "metadata": {
            "match_id":    match_id,
            "competition": competition,
            "season":      season,
            "match_label": match_label,
            "grid_source": "Karun Singh open_xt_12x8_v1",
            "grid_dims":   [_GRID_ROWS, _GRID_COLS],
            "n_actions":   len(df),
        },
    }
    actions_path = out_dir / "xt_actions.json"
    with open(actions_path, "w") as f:
        json.dump(payload, f, indent=2)

    n_pass  = int((df["action_type"] == "Pass").sum())
    n_carry = int((df["action_type"] == "Carry").sum())
    n_pos   = int((df["xt_delta"] > 0).sum())
    print(f"Wrote {len(df)} actions ({n_pass} passes, {n_carry} carries, {n_pos} positive xT) → {actions_path}")


if __name__ == "__main__":
    main()
