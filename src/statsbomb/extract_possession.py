"""Extract all events for a single possession, emitting the shared possession contract.

The possession contract is consumed by both eventScatter.js (spatial rendering) and
timelineStrip.js (temporal rendering). Both components read the same file; only the
fields they care about differ.

Public API:
    resolve_euro_2024_final() -> int
    extract_possession(match_id, possession_id) -> dict
    main()

JSON output shape:
    {
        "match_id":   int,
        "possession": int,
        "team":       str,
        "events": [
            {
                "event_id":   str,         # StatsBomb UUID
                "event_type": str,         # StatsBomb type string ("Pass", "Carry", ...)
                "seconds":    float,       # elapsed seconds within possession from first event
                "x":          float,       # StatsBomb 120x80 origin coordinate
                "y":          float,
                "end_x":      float|null,  # Pass / Carry / Shot only; null for point events
                "end_y":      float|null,
                "player":     str,         # resolved display_name (nickname coalesce)
                "outcome":    str|null     # Pass: null=complete, str=failure reason; else null
            }
        ],
        "metadata": {
            "match_id":    int,
            "possession":  int,
            "team":        str,
            "competition": str,
            "match_label": str
        }
    }

Written to: src/footballd3/sample_data/possession_{match_id}_{possession_id}.json
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from statsbombpy import sb


def resolve_euro_2024_final() -> int:
    """Resolve the UEFA Euro 2024 Final match ID from the StatsBomb open data API.

    Duplicated from extract_shots, extract_pass_network, and extract_progressive_map.
    Shared utility extraction is deferred until a fourth caller appears.

    Returns:
        int: The StatsBomb match_id for the Euro 2024 Final.

    Raises:
        ValueError: If the competition/season cannot be found, or if the Final
            cannot be isolated to a single match.
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


def _parse_timestamp(ts: str) -> float:
    """Parse a StatsBomb timestamp string to total elapsed seconds.

    StatsBomb timestamps are formatted as "HH:MM:SS.mmm" within a period.

    Args:
        ts (str): Timestamp string in "HH:MM:SS.mmm" format.

    Returns:
        float: Total seconds represented by the timestamp.
    """
    t = datetime.strptime(ts, "%H:%M:%S.%f")
    return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000


def _end_location(row: pd.Series) -> tuple[float | None, float | None]:
    """Extract the end location for an event, returning (end_x, end_y) or (None, None).

    Only Pass, Carry, and Shot events carry end-location data in StatsBomb.

    Args:
        row (pd.Series): A single StatsBomb events row.

    Returns:
        tuple[float | None, float | None]: (end_x, end_y) or (None, None).
    """
    event_type = row.get("type", "")
    field_map = {
        "Pass":  "pass_end_location",
        "Carry": "carry_end_location",
        "Shot":  "shot_end_location",
    }
    field = field_map.get(event_type)
    if field:
        loc = row.get(field)
        if isinstance(loc, list) and len(loc) >= 2:
            return float(loc[0]), float(loc[1])
    return None, None


def _outcome(row: pd.Series) -> str | None:
    """Extract a human-readable outcome string for an event, or None.

    For Pass events: None means the pass was completed (StatsBomb represents
    completion as a null pass_outcome). For all other event types, returns None.

    Args:
        row (pd.Series): A single StatsBomb events row.

    Returns:
        str | None: Outcome string for Pass failures; None for completions and
            all non-Pass events.
    """
    if row.get("type") == "Pass":
        outcome = row.get("pass_outcome")
        if pd.notna(outcome) and outcome:
            return str(outcome)
        return None
    return None


def extract_possession(match_id: int, possession_id: int) -> dict:
    """Extract all events for a single possession and return the possession contract.

    Filters all match events to those sharing the given possession number, then
    builds the flat contract consumed by eventScatter.js and timelineStrip.js.
    Events are sorted by their StatsBomb index (chronological order within possession).
    Elapsed seconds are computed relative to the first event in the possession.

    Args:
        match_id (int): StatsBomb match ID.
        possession_id (int): StatsBomb possession number.

    Returns:
        dict: Possession contract. See module docstring for the full shape.

    Raises:
        ValueError: If no events are found for the given possession_id.
    """
    nicknames = _build_nickname_lookup(match_id)
    all_events = sb.events(match_id=match_id)

    poss_events = all_events[all_events["possession"] == possession_id].sort_values("index")

    if poss_events.empty:
        raise ValueError(f"No events found for possession {possession_id} in match {match_id}")

    # Elapsed seconds: delta from the first event's timestamp in this possession.
    first_ts = _parse_timestamp(str(poss_events.iloc[0]["timestamp"]))
    team = str(poss_events.iloc[0].get("possession_team", ""))

    events_out: list[dict] = []
    for _, row in poss_events.iterrows():
        loc = row.get("location")
        if not isinstance(loc, list) or len(loc) < 2:
            continue  # skip events with no spatial location (rare but possible)

        pid = row.get("player_id")
        player = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid)
            else str(row.get("player", ""))
        )

        end_x, end_y = _end_location(row)
        elapsed = round(_parse_timestamp(str(row["timestamp"])) - first_ts, 3)

        events_out.append({
            "event_id":   str(row["id"]),
            "event_type": str(row["type"]),
            "seconds":    elapsed,
            "x":          float(loc[0]),
            "y":          float(loc[1]),
            "end_x":      end_x,
            "end_y":      end_y,
            "player":     player,
            "outcome":    _outcome(row),
        })

    competition, match_label = _fetch_match_info(match_id)

    return {
        "match_id":   match_id,
        "possession": possession_id,
        "team":       team,
        "events":     events_out,
        "metadata": {
            "match_id":    match_id,
            "possession":  possession_id,
            "team":        team,
            "competition": competition,
            "match_label": match_label,
        },
    }


def _fetch_match_info(match_id: int) -> tuple[str, str]:
    """Return (competition_display, match_label) for a Euro 2024 match.

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


def _pick_showcase_possession(match_id: int, team: str) -> int:
    """Pick the possession with the most diverse event types for a given team.

    Scores possessions by the number of distinct event types they contain — more
    types means a richer demo for the scatter and timeline components.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name as it appears in StatsBomb data.

    Returns:
        int: The possession_id with the highest event-type diversity for that team.

    Raises:
        ValueError: If no possessions are found for the given team.
    """
    all_events = sb.events(match_id=match_id)
    team_poss = all_events[all_events["possession_team"] == team]

    if team_poss.empty:
        raise ValueError(f"No possessions found for team '{team}' in match {match_id}")

    # Score each possession by distinct event types (variety > raw count).
    scored = (
        team_poss.groupby("possession")["type"]
        .nunique()
        .sort_values(ascending=False)
    )
    return int(scored.index[0])


def main() -> None:
    """Resolve the Euro 2024 Final, pick the richest Spain possession, and write JSON.

    Output path:
        src/footballd3/sample_data/possession_{match_id}_{possession_id}.json
    """
    match_id = resolve_euro_2024_final()
    team = "Spain"

    print(f"Resolved match_id: {match_id}")
    possession_id = _pick_showcase_possession(match_id, team)
    print(f"Selected possession {possession_id} for {team} (most diverse event types)")

    data = extract_possession(match_id, possession_id)

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"possession_{match_id}_{possession_id}.json"

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    n_events = len(data["events"])
    types = {e["event_type"] for e in data["events"]}
    max_sec = max(e["seconds"] for e in data["events"]) if data["events"] else 0
    print(f"[{team}] possession {possession_id}: {n_events} events, {len(types)} types, {max_sec:.1f}s")
    print(f"  types: {sorted(types)}")
    print(f"  written to: {out_path}")


if __name__ == "__main__":
    main()
