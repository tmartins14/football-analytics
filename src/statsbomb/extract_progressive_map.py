"""Extract all open-play passes and carries for a team, flagging each as progressive or not.

All open-play passes (completed and incomplete) and carries are emitted. Each
action carries a `progressive` boolean: True when the action moved the ball at
least 25% of the remaining distance toward the goal centre (StatsBomb's own
definition). Set-piece phases are excluded via the play_pattern field. Carries
are always completed — StatsBomb logs carry failures as separate events
(dispossessions, failed take-ons), not as incomplete carries.

Public API:
    resolve_euro_2024_final() -> int
    extract_progressive_map(match_id, team, threshold=0.25) -> dict
    main()

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

# StatsBomb 120×80 yard coordinate system — goal centre used for progression math.
GOAL_CENTER_X: float = 120.0
GOAL_CENTER_Y: float = 40.0

# StatsBomb's 25%-of-remaining-distance-to-goal-centre threshold.
# Exposed as a named constant so callers can override without magic numbers.
PROGRESSIVE_THRESHOLD: float = 0.25

# Play patterns that identify set-piece phases, applied to both passes and carries.
SET_PIECE_PLAY_PATTERNS: frozenset[str] = frozenset({
    "From Corner",
    "From Free Kick",
    "From Goal Kick",
    "From Kick Off",
    "From Throw In",
})


def resolve_euro_2024_final() -> int:
    """Resolve the UEFA Euro 2024 Final match ID from the StatsBomb open data API.

    Duplicated from extract_shots and extract_pass_network. This is the third
    script that needs it; extract to a shared utility module when convenient.

    Returns:
        int: The StatsBomb match_id for the Euro 2024 Final.

    Raises:
        ValueError: If the competition/season can't be found, or if the Final
            can't be isolated to a single match.
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

    return int(final_rows["match_id"].iloc[0])


def _build_nickname_lookup(match_id: int) -> dict[int, str]:
    """Build a player_id -> display_name mapping from sb.lineups() for all teams in a match.

    display_name coalesces player_nickname (when non-empty) with player_name.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict[int, str]: Maps player_id to resolved display name.
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
    Goal centre is (120, 40) in StatsBomb 120×80 yards. A threshold of 0.25 means
    the action must cover at least 25% of the remaining distance.

    Args:
        x0 (float): Start x-coordinate.
        y0 (float): Start y-coordinate.
        x1 (float): End x-coordinate.
        y1 (float): End y-coordinate.
        threshold (float): Fraction of remaining distance that must be covered.
            Default 0.25 (StatsBomb's own progressive definition).

    Returns:
        bool: True when the action qualifies as progressive.
    """
    d_start = _dist_to_goal(x0, y0)
    if d_start == 0:
        return False
    return _dist_to_goal(x1, y1) <= (1.0 - threshold) * d_start


def _fetch_match_info(match_id: int) -> tuple[str, str]:
    """Return (competition_display, match_label) for a Euro 2024 match.

    Makes two API calls (competitions + matches). Returns empty strings when
    the match cannot be found.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        tuple[str, str]: (competition display string, "Home vs Away" label).
    """
    comps = sb.competitions()
    euro = comps[
        comps["competition_name"].str.contains("UEFA Euro", case=False)
        & (comps["season_name"] == "2024")
    ]
    if euro.empty:
        return ("", "")
    competition_id = int(euro["competition_id"].iloc[0])
    season_id = int(euro["season_id"].iloc[0])
    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    match_rows = matches[matches["match_id"] == match_id]
    if match_rows.empty:
        return ("", "")
    row = match_rows.iloc[0]
    competition = f"{euro['competition_name'].iloc[0]} {euro['season_name'].iloc[0]}"
    label = f"{row['home_team']} vs {row['away_team']}"
    return competition, label


def extract_progressive_map(
    match_id: int,
    team: str,
    threshold: float = PROGRESSIVE_THRESHOLD,
) -> dict:
    """Extract all open-play passes and carries for one team, flagging each as progressive.

    Emits every open-play pass (completed and incomplete) and carry. Each action
    carries a `progressive` boolean computed from the 25%-of-remaining-distance-to-
    goal-centre rule (StatsBomb's own definition, threshold configurable). Set-piece
    phases are excluded via the play_pattern field — both the delivery and any
    follow-up actions in the same phase are dropped. Carries are always completed:
    StatsBomb logs carry failures as separate dispossession or failed take-on events,
    not as incomplete carries.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name as it appears in StatsBomb data (e.g. "Spain").
        threshold (float): Fraction of remaining distance to goal that an action
            must cover to be classified as progressive. Default 0.25.

    Returns:
        dict: JSON contract with keys: team, actions, params, metadata.
            actions is a list of dicts: action_type, display_name, x0, y0,
            x1, y1, completed, progressive, distance_gained (yards), minute.
    """
    nicknames = _build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)

    # Restrict to team's open-play events (exclude all set-piece play patterns).
    team_events = events[
        (events["team"] == team)
        & (~events["play_pattern"].isin(SET_PIECE_PLAY_PATTERNS))
    ]

    actions: list[dict] = []

    # ── Passes (completed + incomplete — all emitted, progressive flagged) ────
    passes = team_events[team_events["type"] == "Pass"]
    for _, row in passes.iterrows():
        loc = row.get("location")
        end = row.get("pass_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue

        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])

        pid = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid)
            else str(row.get("player", ""))
        )
        # pass_outcome is NaN for completed passes; any non-null value is a failure.
        completed = bool(pd.isna(row.get("pass_outcome")))

        actions.append({
            "action_type":    "pass",
            "display_name":   display_name,
            "x0": x0, "y0": y0,
            "x1": x1, "y1": y1,
            "completed":      completed,
            "progressive":    _is_progressive(x0, y0, x1, y1, threshold),
            "distance_gained": round(_dist_to_goal(x0, y0) - _dist_to_goal(x1, y1), 2),
            "minute":         int(row["minute"]),
        })

    # ── Carries (completed-only — all emitted, progressive flagged) ───────────
    carries = team_events[team_events["type"] == "Carry"]
    for _, row in carries.iterrows():
        loc = row.get("location")
        end = row.get("carry_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue

        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])

        pid = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid)
            else str(row.get("player", ""))
        )

        actions.append({
            "action_type":    "carry",
            "display_name":   display_name,
            "x0": x0, "y0": y0,
            "x1": x1, "y1": y1,
            "completed":      True,  # carries are always completed in StatsBomb
            "progressive":    _is_progressive(x0, y0, x1, y1, threshold),
            "distance_gained": round(_dist_to_goal(x0, y0) - _dist_to_goal(x1, y1), 2),
            "minute":         int(row["minute"]),
        })

    competition, match_label = _fetch_match_info(match_id)

    return {
        "team": team,
        "actions": actions,
        "params": {
            "progressive_threshold": threshold,
        },
        "metadata": {
            "match_id":         match_id,
            "team":             team,
            "competition":      competition,
            "match_label":      match_label,
            "set_piece_filter": "play_pattern",
        },
    }


def main() -> None:
    """Resolve the Euro 2024 Final, extract all open-play actions, and write JSON.

    Extracts Spain and England. Output paths:
        src/footballd3/sample_data/progressive_map_{match_id}_{team_slug}.json
    """
    match_id = resolve_euro_2024_final()
    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    for team in ("Spain", "England"):
        data = extract_progressive_map(match_id, team)
        team_slug = team.lower().replace(" ", "_")
        out_path = out_dir / f"progressive_map_{match_id}_{team_slug}.json"

        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)

        n_total      = len(data["actions"])
        n_prog       = sum(1 for a in data["actions"] if a["progressive"])
        n_passes     = sum(1 for a in data["actions"] if a["action_type"] == "pass")
        n_carries    = sum(1 for a in data["actions"] if a["action_type"] == "carry")
        n_prog_pass  = sum(1 for a in data["actions"] if a["action_type"] == "pass"  and a["progressive"])
        n_prog_carry = sum(1 for a in data["actions"] if a["action_type"] == "carry" and a["progressive"])
        print(f"[{team}] {n_total} actions ({n_passes} passes, {n_carries} carries) → {out_path}")
        print(f"  progressive: {n_prog} ({n_prog_pass} passes, {n_prog_carry} carries)")


if __name__ == "__main__":
    main()
