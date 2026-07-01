"""Extract convex-hull geometry for both teams at each goal instant.

For each goal in the UEFA Euro 2024 Final, reads the matching 360 freeze frame,
splits visible players into the two teams (offense = possession team; defense =
other team), filters out goalkeepers, and computes a scipy convex hull over each
team's outfield players. Writes hull vertices, area, and player counts to JSON
so the D3 convexHull component can render territory polygons without touching
the StatsBomb schema.

Coordinates are StatsBomb-native 120×80 yards throughout. The D3 component owns
pixel mapping via pitch.px().

TEAMMATE-BOOLEAN NOTE: The `teammate` field in a 360 freeze frame is relative to
the ACTOR (the player who performed the event), not to a fixed team. `teammate=True`
means "same team as the actor"; `teammate=False` means "opponent of the actor".
To label these as offense/defense we compare the actor's team to the event's
possession_team: if they match, teammates=offense; otherwise teammates=defense.
For goal shots the actor is always the shooter and therefore always on the
possession team, so the branch is predictable — but the code still performs the
comparison explicitly so it is correct for any event type.

Public API:
    resolve_euro_2024_final() -> int
    load_frames(match_id) -> dict
    find_goal_events(match_id) -> pandas.DataFrame
    split_teams(frame_players, actor_team, possession_team) -> tuple[list, list]
    compute_hull(players, include_keeper) -> dict | None
    main()

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
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull, QhullError
from statsbombpy import sb


def resolve_euro_2024_final() -> int:
    """Resolve the UEFA Euro 2024 Final match ID from the StatsBomb open data API.

    Searches sb.competitions() for UEFA Euro 2024, then sb.matches() for the
    Final stage. Raises ValueError if the competition or stage cannot be
    unambiguously identified.

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


def load_frames(match_id: int) -> dict:
    """Load 360 freeze-frame data for a match, keyed by event UUID.

    Tries sb.frames() first; falls back to reading raw JSON from the StatsBomb
    open-data GitHub repository if sb.frames() raises (a known bug in
    statsbombpy <= 1.18 causes InvalidIndexError for some Euro 2024 match IDs).

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict[str, dict]: Maps event UUID (str) to a frame data dict with keys:
            visible_area (list): Flat polygon coordinate array [x1, y1, ...].
            freeze_frame (list[dict]): Player entries from the 360 data, each
                containing location, teammate, actor, and keeper fields.

    Raises:
        urllib.error.HTTPError: If sb.frames() fails and the GitHub fallback
            also fails.
    """
    try:
        frames_df = sb.frames(match_id=match_id)
        uuid_col = "id" if "id" in frames_df.columns else "event_uuid"
        return {
            str(row[uuid_col]): {
                "visible_area": row["visible_area"],
                "freeze_frame": row["freeze_frame"],
            }
            for _, row in frames_df.iterrows()
        }
    except Exception:  # noqa: BLE001 — catches pandas InvalidIndexError on sb <= 1.18
        print("  sb.frames() raised; using GitHub raw JSON fallback.")

    url = (
        f"https://raw.githubusercontent.com/statsbomb/open-data/master"
        f"/data/three-sixty/{match_id}.json"
    )
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        raw = json.loads(resp.read())

    return {
        entry["event_uuid"]: {
            "visible_area": entry["visible_area"],
            "freeze_frame": entry["freeze_frame"],
        }
        for entry in raw
    }


def find_goal_events(match_id: int) -> pd.DataFrame:
    """Return all goal shot events for a match, sorted by minute.

    Loads the full event stream via sb.events() and filters to shots whose
    outcome is "Goal". The returned DataFrame includes team and possession_team
    columns needed by split_teams() to resolve offense/defense labeling.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pandas.DataFrame: Rows for each goal, sorted ascending by minute.
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

    The `teammate` flag in StatsBomb 360 data is relative to the ACTOR (the
    player who performed the event), not to any fixed team. `teammate=True`
    means "same team as the actor"; `teammate=False` means "opponent of the
    actor". We resolve which is offense vs defense by comparing the actor's
    team to the event's possession_team:

        if actor_team == possession_team:
            offense = teammates (actor's side)
            defense = opponents
        else:
            offense = opponents
            defense = teammates (actor is defending team's player)

    Each entry in frame_players is a raw 360 dict with at minimum the keys
    `teammate` (bool), `actor` (bool), `keeper` (bool), and `location` ([x, y]).

    Args:
        frame_players (list[dict]): Raw freeze_frame list from the 360 data.
        actor_team (str): Team name of the event's actor (from events["team"]).
        possession_team (str): Team in possession at the moment of the event
            (from events["possession_team"]).

    Returns:
        tuple[list[dict], list[dict]]: (offense_players, defense_players).
            Each list contains raw 360 player dicts for that side.

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

    Excludes goalkeepers by default — a deep keeper far from the group
    balloons the hull into unoccupied dead space. The keeper marker still
    appears on the underlying freeze frame; this exclusion is geometry-only.

    Uses scipy.spatial.ConvexHull (v1 implementation). A concave/alpha-shape
    variant may be added in future to avoid enclosing unoccupied space when
    players are spread across the pitch.

    Args:
        players (list[dict]): Raw 360 player dicts, each with at minimum
            `location` ([x, y]) and `keeper` (bool) fields.
        include_keeper (bool): If True, includes the goalkeeper in hull
            computation. Default False.

    Returns:
        dict | None: Hull result with keys:
            hull_vertices (list[list[float]]): Ordered convex-hull vertices in
                StatsBomb 120×80 coordinates [[x, y], ...].
            area (float): Hull area in square yards (scipy hull.volume in 2-D
                equals the enclosed area).
            player_count (int): Number of players used to compute the hull
                (after keeper filtering).
        Returns None when fewer than 3 players are visible (degenerate hull —
        collinear or only one or two on-screen players).
    """
    if not include_keeper:
        players = [p for p in players if not p.get("keeper", False)]

    if len(players) < 3:
        return None

    points = np.array([[p["location"][0], p["location"][1]] for p in players])

    try:
        hull = ConvexHull(points)
    except QhullError:
        # All points are collinear — hull is degenerate
        return None

    vertices = points[hull.vertices].tolist()
    area = float(round(hull.volume, 2))  # hull.volume == area in 2-D

    return {
        "hull_vertices": vertices,
        "area": area,
        "player_count": len(players),
    }


def main() -> None:
    """Resolve the Euro 2024 Final, compute goal convex hulls, and write JSON.

    Output: src/footballd3/sample_data/convex_hull_{match_id}_goals.json
    """
    print("Resolving Euro 2024 Final…")
    match_id = resolve_euro_2024_final()
    print(f"  match_id = {match_id}")

    print("Loading goal events…")
    goals = find_goal_events(match_id)
    if goals.empty:
        raise RuntimeError("No goal events found for this match.")

    # Derive the two team names from events so we can look up the defense team
    # without an additional API call.
    all_teams = list(goals["team"].unique()) + list(goals.get("possession_team", goals["team"]).unique())
    unique_teams = list(dict.fromkeys(t for t in all_teams if t and pd.notna(t)))

    print(f"  {len(goals)} goal(s) found for teams: {unique_teams}")

    print("Loading 360 frames…")
    frame_lookup = load_frames(match_id)
    print(f"  {len(frame_lookup)} frames loaded")

    match_label = "Spain vs England"
    competition = "UEFA Euro 2024"

    hull_entries = []
    for _, row in goals.iterrows():
        event_id = str(row["id"])
        if event_id not in frame_lookup:
            print(f"  ⚠ Goal at {int(row['minute'])}' has no matching 360 frame — skipping")
            continue

        frame_data = frame_lookup[event_id]
        frame_players = frame_data["freeze_frame"]

        actor_team = str(row["team"])
        possession_team = str(row.get("possession_team", actor_team))

        # Identify the defense team as whichever known team is not the possession team.
        # Falls back to "opponent" if team list is incomplete (shouldn't happen in practice).
        defense_team = next(
            (t for t in unique_teams if t != possession_team),
            "opponent",
        )

        offense_players, defense_players = split_teams(
            frame_players, actor_team, possession_team
        )

        sides = []
        for side_label, team_name, players in [
            ("offense", possession_team, offense_players),
            ("defense", defense_team, defense_players),
        ]:
            hull = compute_hull(players, include_keeper=False)
            if hull is None:
                print(
                    f"  ⚠ {side_label} hull at {int(row['minute'])}' skipped "
                    f"(<3 outfield players visible)"
                )
                continue
            sides.append({"side": side_label, "team_name": team_name, **hull})

        hull_entries.append({
            "sides": sides,
            "metadata": {
                "match_id": match_id,
                "event_id": event_id,
                "minute": int(row["minute"]),
                "possession_team_name": possession_team,
                "actor_team_name": actor_team,
                "include_keeper": False,
            },
        })

        offense_area = next((s["area"] for s in sides if s["side"] == "offense"), None)
        defense_area = next((s["area"] for s in sides if s["side"] == "defense"), None)
        print(
            f"  Goal {int(row['minute'])}': "
            f"offense={offense_area} yd², defense={defense_area} yd²"
        )

    if not hull_entries:
        raise RuntimeError("No hull entries produced — check 360 frame coverage.")

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"convex_hull_{match_id}_goals.json"

    payload = {
        "hulls": hull_entries,
        "match_metadata": {
            "match_id": match_id,
            "competition": competition,
            "match_label": match_label,
        },
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {len(hull_entries)} hull entries → {out_path}")


if __name__ == "__main__":
    main()
