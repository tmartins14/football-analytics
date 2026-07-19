"""Extract 360 freeze-frame snapshots for all goals from StatsBomb open data.

Loads 360 frames, finds each goal event that has a matching freeze frame,
and returns a tidy DataFrame of player positions. main() reassembles the
nested JSON contract consumed by the freezeFrame D3 component.

Public API:
    extract_freeze_frame(match_id) -> pd.DataFrame
    find_goal_frames(events, frame_lookup) -> list
    transform_frame(event_row, frame_data, match_id, display_name) -> dict
    main()

DataFrame columns: goal_event_id, goal_minute, scorer, scorer_team,
    ball_x, ball_y, player_x, player_y, teammate, actor, keeper

JSON output shape:
    {
      "goals": [
        {
          "ball": {"x": float, "y": float},
          "frame": [{"x": float, "y": float, "teammate": bool, "actor": bool, "keeper": bool}],
          "visible_area": [float, ...],
          "metadata": {"match_id": int, "event_id": str, "display_name": str, "team": str,
                       "action_type": str, "minute": int, "competition": str, "match_label": str}
        }
      ],
      "match_metadata": {"match_id": int, "competition": str, "match_label": str}
    }
Written to: src/footballd3/sample_data/freeze_frames_{match_id}_goals.json
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import build_nickname_lookup, fetch_match_info, load_360_frames, resolve_match


def find_goal_frames(events: pd.DataFrame, frame_lookup: dict) -> list:
    """Find all goal events that have a matching 360 freeze frame, sorted by minute.

    Filters events to shots with outcome "Goal" whose event UUID appears in
    frame_lookup. Goals without a matching 360 frame are silently skipped.

    Args:
        events (pd.DataFrame): Full match event DataFrame from sb.events().
        frame_lookup (dict[str, dict]): Event UUID -> frame data, from load_360_frames().

    Returns:
        list[tuple[pd.Series, dict]]: Each entry is (event_row, frame_data)
            sorted ascending by minute. Empty if no goals have matching frames.
    """
    goals = events[
        (events["type"] == "Shot") & (events["shot_outcome"] == "Goal")
    ].sort_values("minute")

    result = []
    for _, row in goals.iterrows():
        event_id = str(row["id"])
        if event_id in frame_lookup:
            result.append((row, frame_lookup[event_id]))
    return result


def transform_frame(
    event_row: pd.Series,
    frame_data: dict,
    match_id: int,
    display_name: str,
    competition: str = "",
    match_label: str = "",
) -> dict:
    """Transform a StatsBomb event row and 360 frame into the freeze-frame JSON contract.

    Ball position comes from the event location (where the action occurred).
    Player positions come from the 360 freeze-frame array. Coordinates are
    StatsBomb-native 120×80 yards and passed through untouched.

    Args:
        event_row (pd.Series): One row from sb.events() with fields: id, location,
            player, team, type, minute.
        frame_data (dict): Frame entry from load_360_frames(), with visible_area and
            freeze_frame keys.
        match_id (int): StatsBomb match ID, embedded in metadata.
        display_name (str): Pre-resolved player display name (nickname or full name).
        competition (str): Competition display string for metadata.
        match_label (str): "Home vs Away" label for metadata.

    Returns:
        dict: One freeze-frame snapshot conforming to the goals[] contract shape.
    """
    loc = event_row["location"]
    players = [
        {
            "x": float(p["location"][0]),
            "y": float(p["location"][1]),
            "teammate": bool(p.get("teammate", False)),
            "actor":    bool(p.get("actor", False)),
            "keeper":   bool(p.get("keeper", False)),
        }
        for p in frame_data["freeze_frame"]
    ]

    return {
        "ball":   {"x": float(loc[0]), "y": float(loc[1])},
        "frame":  players,
        "visible_area": frame_data.get("visible_area", []),
        "metadata": {
            "match_id":    match_id,
            "event_id":    str(event_row["id"]),
            "display_name": display_name,
            "team":        str(event_row["team"]),
            "action_type": str(event_row["type"]),
            "minute":      int(event_row["minute"]),
            "competition": competition,
            "match_label": match_label,
        },
    }


def extract_freeze_frame(match_id: int) -> pd.DataFrame:
    """Extract goal freeze-frame player positions for a match as a tidy DataFrame.

    For each goal event that has a matching 360 frame, emits one row per player
    visible in the broadcast field of view. Goal-level metadata (scorer, minute,
    ball position) is repeated on every row within that goal so the DataFrame can
    be filtered and grouped by goal_event_id for analysis.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pd.DataFrame: One row per player per goal freeze frame with columns:
            goal_event_id (str): StatsBomb UUID of the goal shot event.
            goal_minute (int): Match minute of the goal.
            scorer (str): Resolved display_name of the scorer.
            scorer_team (str): Team name of the scorer.
            ball_x, ball_y (float): Ball position in StatsBomb 120×80 coords.
            player_x, player_y (float): Player position in StatsBomb 120×80 coords.
            teammate (bool): True when player is on the same team as the actor.
            actor (bool): True when player is the actor (the scorer).
            keeper (bool): True when player is a goalkeeper.
        Returns an empty DataFrame when no goals have matching 360 frames.
    """
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)
    frame_lookup = load_360_frames(match_id)
    goal_frames = find_goal_frames(events, frame_lookup)

    records = []
    for event_row, frame_data in goal_frames:
        pid = event_row.get("player_id")
        scorer = (
            nicknames.get(int(pid), str(event_row["player"]))
            if pid == pid else str(event_row["player"])
        )
        loc = event_row["location"]
        for p in frame_data["freeze_frame"]:
            records.append({
                "goal_event_id": str(event_row["id"]),
                "goal_minute":   int(event_row["minute"]),
                "scorer":        scorer,
                "scorer_team":   str(event_row["team"]),
                "ball_x":        float(loc[0]),
                "ball_y":        float(loc[1]),
                "player_x":      float(p["location"][0]),
                "player_y":      float(p["location"][1]),
                "teammate":      bool(p.get("teammate", False)),
                "actor":         bool(p.get("actor", False)),
                "keeper":        bool(p.get("keeper", False)),
            })
    return pd.DataFrame(records)


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Extract goal freeze frames for a match and write JSON.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output: {out_dir}/freeze_frames_goals.json
    """
    if match_id is None:
        print("Resolving Euro 2024 Final…")
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    print(f"  match_id = {match_id}")

    print("Loading events…")
    events = sb.events(match_id=match_id)

    print("Loading 360 frames…")
    frame_lookup = load_360_frames(match_id)
    print(f"  {len(frame_lookup)} frames loaded")

    nicknames = build_nickname_lookup(match_id)
    competition, _, match_label = fetch_match_info(match_id)

    print("Finding goals with freeze frames…")
    goal_frames = find_goal_frames(events, frame_lookup)
    if not goal_frames:
        raise RuntimeError("No goal events with matching 360 frames found.")

    snapshots = []
    for row, frame in goal_frames:
        pid = row.get("player_id")
        display_name = nicknames.get(int(pid), str(row["player"])) if pid == pid else str(row["player"])
        snapshots.append(transform_frame(row, frame, match_id, display_name, competition, match_label))

    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "freeze_frames_goals.json"

    payload = {
        "goals": snapshots,
        "match_metadata": {
            "match_id":    match_id,
            "competition": competition,
            "match_label": match_label,
        },
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    for i, (snap, (row, _)) in enumerate(zip(snapshots, goal_frames), 1):
        print(f"  Goal {i}: {snap['metadata']['display_name']} ({int(row['minute'])}')")
    print(f"Wrote {len(snapshots)} goal snapshots → {out_path}")


if __name__ == "__main__":
    main()
