"""Extract all events for a single possession as a tidy DataFrame.

The possession contract is consumed by both eventScatter.js (spatial rendering)
and timelineStrip.js (temporal rendering).

Public API:
    extract_possession(match_id, possession_id) -> pd.DataFrame
    main()

DataFrame columns: event_id, event_type, seconds, x, y, end_x, end_y, player, outcome

JSON output shape:
    {
        "match_id":   int,
        "possession": int,
        "team":       str,
        "events": [
            {
                "event_id":   str,
                "event_type": str,
                "seconds":    float,
                "x":          float,
                "y":          float,
                "end_x":      float|null,
                "end_y":      float|null,
                "player":     str,
                "outcome":    str|null
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
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import (
    build_nickname_lookup,
    end_location,
    fetch_match_info,
    parse_timestamp,
    pass_outcome,
    resolve_match,
)


def extract_possession(match_id: int, possession_id: int) -> pd.DataFrame:
    """Extract all events for a single possession as a tidy DataFrame.

    Filters all match events to those sharing the given possession number, then
    builds the flat records consumed by eventScatter.js and timelineStrip.js.
    Events are sorted by their StatsBomb index (chronological order within
    possession). Elapsed seconds are computed relative to the first event.

    Args:
        match_id (int): StatsBomb match ID.
        possession_id (int): StatsBomb possession number.

    Returns:
        pd.DataFrame: One row per event with columns:
            event_id (str): StatsBomb event UUID.
            event_type (str): StatsBomb type string ("Pass", "Carry", ...).
            seconds (float): Elapsed seconds within possession from the first event.
            x, y (float): StatsBomb 120×80 event origin coordinates.
            end_x, end_y (float | None): End coordinates for Pass/Carry/Shot; None otherwise.
            player (str): Resolved display_name of the actor.
            outcome (str | None): Pass outcome string; None for completions and
                all non-Pass events.
        Also sets df.attrs["possession_team"] (str) for the team that held possession.

    Raises:
        ValueError: If no events are found for the given possession_id.
    """
    nicknames = build_nickname_lookup(match_id)
    all_events = sb.events(match_id=match_id)

    poss_events = all_events[all_events["possession"] == possession_id].sort_values("index")
    if poss_events.empty:
        raise ValueError(f"No events found for possession {possession_id} in match {match_id}")

    first_ts = parse_timestamp(str(poss_events.iloc[0]["timestamp"]))
    possession_team = str(poss_events.iloc[0].get("possession_team", ""))

    records = []
    for _, row in poss_events.iterrows():
        loc = row.get("location")
        if not isinstance(loc, list) or len(loc) < 2:
            continue

        pid = row.get("player_id")
        player = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid) else str(row.get("player", ""))
        )

        ex, ey = end_location(row)
        elapsed = round(parse_timestamp(str(row["timestamp"])) - first_ts, 3)

        records.append({
            "event_id":   str(row["id"]),
            "event_type": str(row["type"]),
            "seconds":    elapsed,
            "x":          float(loc[0]),
            "y":          float(loc[1]),
            "end_x":      ex,
            "end_y":      ey,
            "player":     player,
            "outcome":    pass_outcome(row),
        })

    df = pd.DataFrame(records)
    df.attrs["possession_team"] = possession_team
    return df


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
    scored = (
        team_poss.groupby("possession")["type"]
        .nunique()
        .sort_values(ascending=False)
    )
    return int(scored.index[0])


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Pick the richest possession for a match and write JSON.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output path: {out_dir}/possession_{possession_id}.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    team = "Spain"

    print(f"Resolved match_id: {match_id}")
    possession_id = _pick_showcase_possession(match_id, team)
    print(f"Selected possession {possession_id} for {team} (most diverse event types)")

    df = extract_possession(match_id, possession_id)
    competition, _, match_label = fetch_match_info(match_id)
    possession_team = df.attrs.get("possession_team", team)

    payload = {
        "match_id":   match_id,
        "possession": possession_id,
        "team":       possession_team,
        "events":     df.to_dict(orient="records"),
        "metadata": {
            "match_id":    match_id,
            "possession":  possession_id,
            "team":        possession_team,
            "competition": competition,
            "match_label": match_label,
        },
    }

    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"possession_{possession_id}.json"

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    types = set(df["event_type"])
    max_sec = df["seconds"].max() if not df.empty else 0
    print(f"[{team}] possession {possession_id}: {len(df)} events, {len(types)} types, {max_sec:.1f}s")
    print(f"  types: {sorted(types)}")
    print(f"  written to: {out_path}")


if __name__ == "__main__":
    main()
