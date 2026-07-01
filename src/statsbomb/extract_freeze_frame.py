"""Extract 360 freeze-frame snapshots for all goals from StatsBomb open data.

Loads 360 frames for the UEFA Euro 2024 Final, finds each goal event that has a
matching freeze frame, transforms each to a flat JSON contract, and writes them
to a single file as an ordered goals array.

Public API:
    resolve_euro_2024_final() -> int
    load_frames(match_id) -> dict
    find_goal_frames(events, frame_lookup) -> list
    transform_frame(event_row, frame_data, match_id) -> dict
    main()

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
import urllib.request
from pathlib import Path

import pandas as pd
from statsbombpy import sb


def resolve_euro_2024_final() -> int:
    """Resolve the UEFA Euro 2024 Final match ID from the StatsBomb open data API.

    Duplicated from extract_shots.resolve_euro_2024_final. Once a third script
    needs the same resolution, extract to a shared utility module.

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
        # statsbombpy may expose the event UUID under 'id' or 'event_uuid'
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


def find_goal_frames(events, frame_lookup: dict) -> list:
    """Find all goal events that have a matching 360 freeze frame, sorted by minute.

    Filters events to shots with outcome "Goal" whose event UUID appears in
    frame_lookup. Goals without a matching 360 frame are silently skipped (the
    broadcast FOV occasionally excludes the moment of a distant goal).

    Args:
        events (pandas.DataFrame): Full match event DataFrame from sb.events().
        frame_lookup (dict[str, dict]): Event UUID -> frame data, from load_frames().

    Returns:
        list[tuple[pandas.Series, dict]]: Each entry is (event_row, frame_data)
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


def transform_frame(event_row, frame_data: dict, match_id: int, display_name: str) -> dict:
    """Transform a StatsBomb event row and 360 frame into the freeze-frame JSON contract.

    Ball position is taken from the event's location field (where the action
    occurred). Player positions come from the 360 freeze-frame array. Coordinates
    are StatsBomb-native 120×80 yards and passed through untouched — the pitch
    component owns pixel mapping.

    Args:
        event_row (pandas.Series): One row from sb.events(), must have fields:
            id (str), location (list[float, float]), player (str), team (str),
            type (str), minute (int).
        frame_data (dict): Frame entry from load_frames(), with visible_area and
            freeze_frame keys.
        match_id (int): StatsBomb match ID, embedded in metadata for context.
        display_name (str): Pre-resolved player display name (nickname or full name).

    Returns:
        dict: One freeze-frame snapshot with keys:
            ball (dict): {x (float), y (float)} — ball position at the moment of the event.
            frame (list[dict]): [{x, y, teammate, actor, keeper}] — one entry per
                player visible in the broadcast field of view.
            visible_area (list): Flat coordinate polygon [x1, y1, ...] in StatsBomb space.
            metadata (dict): Context fields; not rendered by the D3 component but consumed
                by the index.html goal-navigation label (display_name, minute, team).
    """
    loc = event_row["location"]
    players = [
        {
            "x": float(p["location"][0]),
            "y": float(p["location"][1]),
            "teammate": bool(p.get("teammate", False)),
            "actor": bool(p.get("actor", False)),
            "keeper": bool(p.get("keeper", False)),
        }
        for p in frame_data["freeze_frame"]
    ]

    return {
        "ball": {"x": float(loc[0]), "y": float(loc[1])},
        "frame": players,
        "visible_area": frame_data["visible_area"],
        "metadata": {
            "match_id": match_id,
            "event_id": str(event_row["id"]),
            "display_name": display_name,
            "team": str(event_row["team"]),
            "action_type": str(event_row["type"]),
            "minute": int(event_row["minute"]),
            "competition": "UEFA Euro 2024",
            "match_label": "Spain vs England",
        },
    }


def main() -> None:
    """Resolve the Euro 2024 Final, extract goal freeze frames, and write JSON.

    Output: src/footballd3/sample_data/freeze_frames_{match_id}_goals.json
    """
    print("Resolving Euro 2024 Final…")
    match_id = resolve_euro_2024_final()
    print(f"  match_id = {match_id}")

    print("Loading events…")
    events = sb.events(match_id=match_id)

    print("Loading 360 frames…")
    frame_lookup = load_frames(match_id)
    print(f"  {len(frame_lookup)} frames loaded")

    print("Building player nickname lookup…")
    lineups = sb.lineups(match_id=match_id)
    nicknames: dict[int, str] = {}
    for team_df in lineups.values():
        for _, row in team_df.iterrows():
            nick = row.get("player_nickname")
            name = row["player_name"]
            nicknames[int(row["player_id"])] = nick if (pd.notna(nick) and nick) else name

    print("Finding goals with freeze frames…")
    goal_frames = find_goal_frames(events, frame_lookup)
    if not goal_frames:
        raise RuntimeError("No goal events with matching 360 frames found.")

    snapshots = []
    for row, frame in goal_frames:
        pid = row.get("player_id")
        display_name = nicknames.get(int(pid), str(row["player"])) if pid == pid else str(row["player"])
        snapshots.append(transform_frame(row, frame, match_id, display_name))

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"freeze_frames_{match_id}_goals.json"

    payload = {
        "goals": snapshots,
        "match_metadata": {
            "match_id": match_id,
            "competition": "UEFA Euro 2024",
            "match_label": "Spain vs England",
        },
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    for i, (snap, (row, _)) in enumerate(zip(snapshots, goal_frames), 1):
        print(f"  Goal {i}: {snap['metadata']['display_name']} ({int(row['minute'])}')")
    print(f"Wrote {len(snapshots)} goal snapshots → {out_path}")


if __name__ == "__main__":
    main()
