"""Extract all open-play passes and carries for a team, flagging each as progressive.

All open-play passes (completed and incomplete) and carries are emitted. Each
action carries a `progressive` boolean: True when the action moved the ball at
least 25% of the remaining distance toward the goal centre (StatsBomb's own
definition). Set-piece phases are excluded via the play_pattern field.

Public API:
    extract_progressive_map(match_id, team, threshold) -> pd.DataFrame
    main()

DataFrame columns: event_id, action_type, display_name, x0, y0, x1, y1,
    completed, progressive, distance_gained, minute

JSON output shape:
    {
        "team": str,
        "actions": [
            {
                "action_type": "pass" | "carry",
                "display_name": str,
                "x0": float, "y0": float,
                "x1": float, "y1": float,
                "completed": bool,
                "progressive": bool,
                "distance_gained": float,
                "minute": int
            }
        ],
        "params": {"progressive_threshold": float},
        "metadata": {
            "match_id": int,
            "team": str,
            "competition": str,
            "match_label": str,
            "set_piece_filter": "play_pattern"
        }
    }
Written to: src/footballd3/sample_data/progressive_map_{match_id}_{team_slug}.json
"""

import json
import math
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import (
    SET_PIECE_PLAY_PATTERNS,
    build_nickname_lookup,
    fetch_match_info,
    resolve_match,
)

# StatsBomb 120×80 yard coordinate system — goal centre used for progression math.
GOAL_CENTER_X: float = 120.0
GOAL_CENTER_Y: float = 40.0

# StatsBomb's 25%-of-remaining-distance-to-goal-centre threshold.
PROGRESSIVE_THRESHOLD: float = 0.25


def _dist_to_goal(x: float, y: float) -> float:
    """Euclidean distance from (x, y) to the goal centre at (120, 40) in StatsBomb yards.

    Args:
        x (float): StatsBomb x-coordinate (0–120).
        y (float): StatsBomb y-coordinate (0–80).

    Returns:
        float: Distance in yards.
    """
    return math.sqrt((GOAL_CENTER_X - x) ** 2 + (GOAL_CENTER_Y - y) ** 2)


def _is_progressive(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    threshold: float = PROGRESSIVE_THRESHOLD,
) -> bool:
    """Return True when the action moves the ball at least `threshold` of the remaining distance to goal.

    Progressive = end-point distance to goal ≤ (1 - threshold) × start-point distance to goal.

    Args:
        x0 (float): Start x-coordinate.
        y0 (float): Start y-coordinate.
        x1 (float): End x-coordinate.
        y1 (float): End y-coordinate.
        threshold (float): Fraction of remaining distance that must be covered. Default 0.25.

    Returns:
        bool: True when the action qualifies as progressive.
    """
    d_start = _dist_to_goal(x0, y0)
    if d_start == 0:
        return False
    return _dist_to_goal(x1, y1) <= (1.0 - threshold) * d_start


def extract_progressive_map(
    match_id: int,
    team: str,
    threshold: float = PROGRESSIVE_THRESHOLD,
) -> pd.DataFrame:
    """Extract all open-play passes and carries for one team as a tidy DataFrame.

    Emits every open-play pass (completed and incomplete) and carry. Each action
    carries a `progressive` boolean computed from the 25%-of-remaining-distance-to-
    goal-centre rule. Set-piece phases are excluded via the play_pattern field.
    Carries are always completed — StatsBomb logs carry failures as separate events.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name as it appears in StatsBomb data (e.g. "Spain").
        threshold (float): Fraction of remaining distance that defines progressive.
            Default 0.25 (StatsBomb's own definition).

    Returns:
        pd.DataFrame: One row per pass or carry with columns:
            event_id (str): StatsBomb event UUID.
            action_type (str): "pass" or "carry".
            display_name (str): Resolved player display name.
            x0, y0, x1, y1 (float): Start and end coordinates in 120×80 yards.
            completed (bool): True for completed passes; always True for carries.
            progressive (bool): True when the 25% threshold is met.
            distance_gained (float): Yards gained toward goal (negative = away).
            minute (int): Match minute.
    """
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)

    team_events = events[
        (events["team"] == team)
        & (~events["play_pattern"].isin(SET_PIECE_PLAY_PATTERNS))
    ]

    records: list[dict] = []

    for _, row in team_events[team_events["type"] == "Pass"].iterrows():
        loc = row.get("location")
        end = row.get("pass_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue

        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])
        pid = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid) else str(row.get("player", ""))
        )
        completed = bool(pd.isna(row.get("pass_outcome")))

        records.append({
            "event_id":        str(row["id"]),
            "action_type":     "pass",
            "display_name":    display_name,
            "x0": x0, "y0": y0,
            "x1": x1, "y1": y1,
            "completed":       completed,
            "progressive":     _is_progressive(x0, y0, x1, y1, threshold),
            "distance_gained": round(_dist_to_goal(x0, y0) - _dist_to_goal(x1, y1), 2),
            "minute":          int(row["minute"]),
        })

    for _, row in team_events[team_events["type"] == "Carry"].iterrows():
        loc = row.get("location")
        end = row.get("carry_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue

        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])
        pid = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid) else str(row.get("player", ""))
        )

        records.append({
            "event_id":        str(row["id"]),
            "action_type":     "carry",
            "display_name":    display_name,
            "x0": x0, "y0": y0,
            "x1": x1, "y1": y1,
            "completed":       True,  # carries are always completed in StatsBomb
            "progressive":     _is_progressive(x0, y0, x1, y1, threshold),
            "distance_gained": round(_dist_to_goal(x0, y0) - _dist_to_goal(x1, y1), 2),
            "minute":          int(row["minute"]),
        })

    return pd.DataFrame(records)


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    teams: list[str] | None = None,
) -> None:
    """Extract progressive pass/carry map for a match and write JSON.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.
        teams (list[str] | None): Teams to extract; defaults to both teams in the match.

    Output paths: {out_dir}/progressive_map_{team_slug}.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    competition, _, match_label = fetch_match_info(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    if teams is None:
        _comps = sb.competitions()
        _euro = _comps[
            _comps["competition_name"].str.contains("UEFA Euro", case=False)
            & (_comps["season_name"] == "2024")
        ]
        _matches = sb.matches(
            competition_id=int(_euro["competition_id"].iloc[0]),
            season_id=int(_euro["season_id"].iloc[0]),
        )
        _row = _matches[_matches["match_id"] == match_id].iloc[0]
        teams = [str(_row["home_team"]), str(_row["away_team"])]

    for team in teams:
        df = extract_progressive_map(match_id, team)

        actions = df.drop(columns=["event_id"]).to_dict(orient="records")
        payload = {
            "team": team,
            "actions": actions,
            "params": {"progressive_threshold": PROGRESSIVE_THRESHOLD},
            "metadata": {
                "match_id":         match_id,
                "team":             team,
                "competition":      competition,
                "match_label":      match_label,
                "set_piece_filter": "play_pattern",
            },
        }

        team_slug = team.lower().replace(" ", "_")
        out_path = out_dir / f"progressive_map_{team_slug}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)

        n_prog  = int(df["progressive"].sum())
        n_pass  = int((df["action_type"] == "pass").sum())
        n_carry = int((df["action_type"] == "carry").sum())
        n_prog_pass  = int(((df["action_type"] == "pass")  & df["progressive"]).sum())
        n_prog_carry = int(((df["action_type"] == "carry") & df["progressive"]).sum())
        print(f"[{team}] {len(df)} actions ({n_pass} passes, {n_carry} carries) → {out_path}")
        print(f"  progressive: {n_prog} ({n_prog_pass} passes, {n_prog_carry} carries)")


if __name__ == "__main__":
    main()
