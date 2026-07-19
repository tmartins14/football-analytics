"""Extract convex-hull geometry for both teams at each goal instant.

For each goal with a matching 360 freeze frame, splits visible players into
offense and defense, excludes goalkeepers, and computes a scipy convex hull over
each team's outfield players. Returns a tidy DataFrame; main() reassembles the
nested JSON contract for the D3 convexHull component.

TEAMMATE-BOOLEAN NOTE: The `teammate` field in a 360 freeze frame is relative to
the ACTOR, not to a fixed team. teammate=True means "same team as the actor".
Offense/defense is resolved by comparing the actor's team to possession_team.

Public API:
    extract_convex_hull(match_id) -> pd.DataFrame
    find_goal_events(match_id) -> pd.DataFrame
    split_teams(frame_players, actor_team, possession_team) -> tuple[list, list]
    compute_hull(players, include_keeper) -> dict | None
    main()

DataFrame columns: goal_event_id, minute, possession_team_name, actor_team_name,
    side, team_name, hull_vertices, area, player_count

JSON output shape:
    {
      "hulls": [
        {
          "sides": [
            {
              "side": "offense" | "defense",
              "team_name": str,
              "hull_vertices": [[x, y], ...],
              "area": float,
              "player_count": int
            }
          ],
          "metadata": {
            "match_id": int,
            "event_id": str,
            "minute": int,
            "possession_team_name": str,
            "actor_team_name": str,
            "include_keeper": bool
          }
        }
      ],
      "match_metadata": {"match_id": int, "competition": str, "match_label": str}
    }
Written to: src/footballd3/sample_data/convex_hull_{match_id}_goals.json
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull, QhullError
from statsbombpy import sb

from .utils import fetch_match_info, load_360_frames, resolve_match


def find_goal_events(match_id: int) -> pd.DataFrame:
    """Return all goal shot events for a match, sorted by minute.

    Loads the full event stream via sb.events() and filters to shots whose
    outcome is "Goal". The returned DataFrame includes team and possession_team
    columns needed by split_teams() to resolve offense/defense labeling.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pd.DataFrame: Rows for each goal, sorted ascending by minute.
            Always contains columns: id, type, team, possession_team,
            shot_outcome, minute. Returns an empty DataFrame if no goals exist.
    """
    events = sb.events(match_id=match_id)
    goals = events[
        (events["type"] == "Shot") & (events["shot_outcome"] == "Goal")
    ].sort_values("minute")
    return goals


def split_teams(
    frame_players: list,
    actor_team: str,
    possession_team: str,
) -> tuple[list, list]:
    """Split 360 frame players into offense and defense teams.

    The `teammate` flag in StatsBomb 360 data is relative to the ACTOR. teammate=True
    means "same team as the actor"; teammate=False means "opponent of the actor".
    Offense/defense is resolved by comparing the actor's team to possession_team:

        if actor_team == possession_team:
            offense = teammates (actor's side)
            defense = opponents
        else:
            offense = opponents
            defense = teammates

    Args:
        frame_players (list[dict]): Raw freeze_frame list from the 360 data.
        actor_team (str): Team name of the event's actor (from events["team"]).
        possession_team (str): Team in possession at the moment of the event.

    Returns:
        tuple[list[dict], list[dict]]: (offense_players, defense_players).

    Raises:
        ValueError: If actor_team or possession_team is empty/None.
    """
    if not actor_team or not possession_team:
        raise ValueError(
            f"actor_team and possession_team must not be empty; "
            f"got {actor_team!r}, {possession_team!r}"
        )

    actor_side = [p for p in frame_players if p.get("teammate", False)]
    opponent_side = [p for p in frame_players if not p.get("teammate", False)]

    if actor_team == possession_team:
        return actor_side, opponent_side
    else:
        return opponent_side, actor_side


def compute_hull(players: list, include_keeper: bool = False) -> dict | None:
    """Compute the convex hull over a team's visible players.

    Excludes goalkeepers by default — a deep keeper far from the group balloons
    the hull into unoccupied dead space. Uses scipy.spatial.ConvexHull.

    Args:
        players (list[dict]): Raw 360 player dicts, each with location ([x, y])
            and keeper (bool) fields.
        include_keeper (bool): If True, includes the goalkeeper. Default False.

    Returns:
        dict | None: Hull result with keys hull_vertices ([[x, y], ...]), area (float),
            player_count (int). Returns None when fewer than 3 players are visible
            (degenerate or all collinear).
    """
    if not include_keeper:
        players = [p for p in players if not p.get("keeper", False)]

    if len(players) < 3:
        return None

    points = np.array([[p["location"][0], p["location"][1]] for p in players])

    try:
        hull = ConvexHull(points)
    except QhullError:
        return None

    vertices = points[hull.vertices].tolist()
    area = float(round(hull.volume, 2))  # hull.volume == area in 2-D

    return {
        "hull_vertices": vertices,
        "area":          area,
        "player_count":  len(players),
    }


def extract_convex_hull(match_id: int) -> pd.DataFrame:
    """Extract convex hull sides for all goal freeze frames as a tidy DataFrame.

    For each goal event that has a matching 360 frame, computes a convex hull
    for the offense and defense teams separately (keepers excluded). Returns one
    row per hull side (offense/defense) per goal.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pd.DataFrame: One row per hull side per goal with columns:
            goal_event_id (str): StatsBomb UUID of the goal event.
            minute (int): Match minute of the goal.
            possession_team_name (str): Team in possession at the goal moment.
            actor_team_name (str): Team of the shooter.
            side (str): "offense" or "defense".
            team_name (str): Team name for this side.
            hull_vertices (list): Ordered [[x, y], ...] hull vertices in 120×80 yards.
            area (float): Hull area in square yards.
            player_count (int): Number of outfield players used to compute the hull.
        Returns an empty DataFrame when no goals have matching 360 frames or all
        hulls are degenerate.
    """
    goals = find_goal_events(match_id)
    if goals.empty:
        return pd.DataFrame()

    frame_lookup = load_360_frames(match_id)

    all_teams = list(goals["team"].unique()) + list(
        goals.get("possession_team", goals["team"]).unique()
    )
    unique_teams = list(dict.fromkeys(t for t in all_teams if t and pd.notna(t)))

    records = []
    for _, row in goals.iterrows():
        event_id = str(row["id"])
        if event_id not in frame_lookup:
            continue

        frame_players = frame_lookup[event_id]["freeze_frame"]
        actor_team = str(row["team"])
        possession_team = str(row.get("possession_team", actor_team))
        defense_team = next((t for t in unique_teams if t != possession_team), "opponent")

        offense_players, defense_players = split_teams(frame_players, actor_team, possession_team)

        for side_label, team_name, players in [
            ("offense", possession_team, offense_players),
            ("defense", defense_team, defense_players),
        ]:
            hull = compute_hull(players, include_keeper=False)
            if hull is None:
                continue
            records.append({
                "goal_event_id":      event_id,
                "minute":             int(row["minute"]),
                "possession_team_name": possession_team,
                "actor_team_name":    actor_team,
                "side":               side_label,
                "team_name":          team_name,
                "hull_vertices":      hull["hull_vertices"],
                "area":               hull["area"],
                "player_count":       hull["player_count"],
            })
    return pd.DataFrame(records)


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Compute goal convex hulls for a match and write JSON.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output: {out_dir}/convex_hull_goals.json
    """
    if match_id is None:
        print("Resolving Euro 2024 Final…")
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    print(f"  match_id = {match_id}")

    df = extract_convex_hull(match_id)
    if df.empty:
        raise RuntimeError("No hull entries produced — check 360 frame coverage.")

    competition, _, match_label = fetch_match_info(match_id)

    # Re-group by goal to reconstruct the nested JSON contract.
    hull_entries = []
    for event_id, group in df.groupby("goal_event_id", sort=False):
        row0 = group.iloc[0]
        sides = []
        for _, side_row in group.iterrows():
            sides.append({
                "side":         side_row["side"],
                "team_name":    side_row["team_name"],
                "hull_vertices": side_row["hull_vertices"],
                "area":         side_row["area"],
                "player_count": int(side_row["player_count"]),
            })
        hull_entries.append({
            "sides": sides,
            "metadata": {
                "match_id":            match_id,
                "event_id":            str(event_id),
                "minute":              int(row0["minute"]),
                "possession_team_name": str(row0["possession_team_name"]),
                "actor_team_name":     str(row0["actor_team_name"]),
                "include_keeper":      False,
            },
        })
        offense_area = next((s["area"] for s in sides if s["side"] == "offense"), None)
        defense_area = next((s["area"] for s in sides if s["side"] == "defense"), None)
        print(
            f"  Goal {int(row0['minute'])}': "
            f"offense={offense_area} yd², defense={defense_area} yd²"
        )

    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "convex_hull_goals.json"

    payload = {
        "hulls": hull_entries,
        "match_metadata": {
            "match_id":    match_id,
            "competition": competition,
            "match_label": match_label,
        },
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {len(hull_entries)} hull entries → {out_path}")


if __name__ == "__main__":
    main()
