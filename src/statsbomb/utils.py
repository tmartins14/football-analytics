"""Shared utilities for the statsbomb extraction package.

Centralises the functions and constants that were duplicated across every
extract_*.py module. All exports are public (no leading underscore) so callers
can cherry-pick helpers without importing an entire extractor.

Public API:
    SET_PIECE_PLAY_PATTERNS (frozenset[str]): Play-pattern labels identifying set-piece phases.
    resolve_match(competition_name, season_name, home_team, away_team) -> int
    fetch_match_info(match_id) -> tuple[str, str, str]
    build_nickname_lookup(match_id) -> dict[int, str]
    load_360_frames(match_id) -> dict
    open_play_mask(events) -> pd.Series
    parse_timestamp(ts) -> float
    end_location(row) -> tuple[float | None, float | None]
    pass_outcome(row) -> str | None
"""

import json
from datetime import datetime

import requests

import pandas as pd
from statsbombpy import sb


SET_PIECE_PLAY_PATTERNS: frozenset[str] = frozenset({
    "From Corner",
    "From Free Kick",
    "From Goal Kick",
    "From Kick Off",
    "From Throw In",
})


def resolve_match(
    competition_name: str,
    season_name: str,
    home_team: str | None = None,
    away_team: str | None = None,
) -> int:
    """Resolve a StatsBomb match ID from competition, season, and optionally team names.

    Searches sb.competitions() for a row matching competition_name (case-insensitive
    substring) and season_name (exact). If home_team and away_team are both given, the
    match is located by team names. Otherwise falls back to the Final competition_stage
    (for cup competitions) or the last match by date.

    Args:
        competition_name (str): Substring to match against competition_name, e.g. "UEFA Euro".
        season_name (str): Exact season_name, e.g. "2024".
        home_team (str | None): Home team name for an exact match lookup.
        away_team (str | None): Away team name for an exact match lookup.

    Returns:
        int: StatsBomb match_id.

    Raises:
        ValueError: If the competition/season is not found, or if the match cannot
            be isolated to a single row.
    """
    comps = sb.competitions()
    comp_rows = comps[
        comps["competition_name"].str.contains(competition_name, case=False, na=False)
        & (comps["season_name"] == season_name)
    ]
    if comp_rows.empty:
        raise ValueError(
            f"No competition matching '{competition_name}' / season '{season_name}' "
            "found in sb.competitions()"
        )

    competition_id = int(comp_rows["competition_id"].iloc[0])
    season_id = int(comp_rows["season_id"].iloc[0])
    matches = sb.matches(competition_id=competition_id, season_id=season_id)

    if home_team and away_team:
        match_rows = matches[
            (matches["home_team"].astype(str) == home_team)
            & (matches["away_team"].astype(str) == away_team)
        ]
        if match_rows.empty or len(match_rows) > 1:
            raise ValueError(
                f"Could not isolate '{home_team} vs {away_team}' unambiguously. "
                f"Candidates:\n{match_rows[['match_id','match_date','home_team','away_team']]}"
            )
        return int(match_rows["match_id"].iloc[0])

    # Fallback: prefer the Final stage (cup competitions), then last by date.
    if "competition_stage" in matches.columns:
        final_rows = matches[
            matches["competition_stage"].astype(str).str.strip() == "Final"
        ]
        if len(final_rows) == 1:
            return int(final_rows["match_id"].iloc[0])

    last_row = matches.sort_values("match_date").iloc[[-1]]
    return int(last_row["match_id"].iloc[0])


def fetch_match_info(match_id: int) -> tuple[str, str, str]:
    """Return (competition, season, match_label) for any StatsBomb match.

    Scans all competition/season combinations in sb.competitions() to locate the
    match_id. Short-circuits as soon as the match is found. Returns empty strings
    when the match cannot be located. This scan is acceptable for StatsBomb open
    data (finite competition set) but will be slower on large private datasets.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        tuple[str, str, str]: (competition display string, season name, "Home vs Away" label).
            All three are empty strings when the match_id is not found.
    """
    comps = sb.competitions()
    for _, comp_row in comps.iterrows():
        try:
            matches = sb.matches(
                competition_id=int(comp_row["competition_id"]),
                season_id=int(comp_row["season_id"]),
            )
        except Exception:  # noqa: BLE001 — some competition/seasons return errors
            continue
        rows = matches[matches["match_id"] == match_id]
        if not rows.empty:
            row = rows.iloc[0]
            competition = f"{comp_row['competition_name']} {comp_row['season_name']}"
            season = str(comp_row["season_name"])
            label = f"{row['home_team']} vs {row['away_team']}"
            return competition, season, label
    return ("", "", "")


def build_nickname_lookup(match_id: int) -> dict[int, str]:
    """Build a player_id -> display_name mapping from sb.lineups() for all teams in a match.

    display_name coalesces player_nickname (when non-empty and non-null) with
    player_name. Join by integer player_id, never by name string.

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


def load_360_frames(match_id: int) -> dict:
    """Load 360 freeze-frame data for a match, keyed by event UUID.

    Tries sb.frames() first; falls back to reading raw JSON from the StatsBomb
    open-data GitHub repository if sb.frames() raises. This handles the known
    InvalidIndexError bug in statsbombpy <= 1.18 for some Euro 2024 match IDs.

    Each returned entry always contains "freeze_frame". It also contains
    "visible_area" when available (present in the GitHub fallback path and in
    sb.frames() when the column exists).

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict[str, dict]: Maps event UUID (str) to a frame data dict with keys:
            freeze_frame (list[dict]): Player entries, each with location,
                teammate, actor, and keeper fields.
            visible_area (list, optional): Flat polygon coordinate array [x1, y1, ...].
                Present when available; consumers should use .get("visible_area").

    Raises:
        requests.HTTPError: If sb.frames() fails and the GitHub fallback also fails.
    """
    try:
        frames_df = sb.frames(match_id=match_id)
        uuid_col = "id" if "id" in frames_df.columns else "event_uuid"
        result: dict[str, dict] = {}
        for _, row in frames_df.iterrows():
            entry: dict = {"freeze_frame": row["freeze_frame"]}
            if "visible_area" in frames_df.columns:
                entry["visible_area"] = row["visible_area"]
            result[str(row[uuid_col])] = entry
        return result
    except Exception:  # noqa: BLE001 — catches pandas InvalidIndexError on sb <= 1.18
        print("  sb.frames() raised; using GitHub raw JSON fallback.")

    url = (
        f"https://raw.githubusercontent.com/statsbomb/open-data/master"
        f"/data/three-sixty/{match_id}.json"
    )
    raw = requests.get(url).json()

    return {
        entry["event_uuid"]: {
            "visible_area": entry["visible_area"],
            "freeze_frame": entry["freeze_frame"],
        }
        for entry in raw
    }


def open_play_mask(events: pd.DataFrame) -> "pd.Series[bool]":
    """Return a boolean mask selecting open-play events, excluding set-piece phases.

    Filters out corners, free kicks, goal kicks, kick-offs, and throw-ins via the
    play_pattern column. Transitions (From Counter) are included. The play_pattern
    column is coerced to string to handle version differences in statsbombpy output.

    Args:
        events (pd.DataFrame): Full match event DataFrame from sb.events().

    Returns:
        pd.Series[bool]: True for open-play events. Returns all-True when the
            play_pattern column is absent.
    """
    if "play_pattern" not in events.columns:
        return pd.Series([True] * len(events), index=events.index)
    return ~events["play_pattern"].astype(str).isin(SET_PIECE_PLAY_PATTERNS)


def parse_timestamp(ts: str) -> float:
    """Parse a StatsBomb timestamp string to total elapsed seconds within the period.

    StatsBomb timestamps are formatted as "HH:MM:SS.mmm" and reset to 00:00:00
    at the start of each period. Use absolute_seconds() for cross-period time.

    Args:
        ts (str): Timestamp string in "HH:MM:SS.mmm" format.

    Returns:
        float: Total seconds represented by the timestamp within the period.
    """
    t = datetime.strptime(ts, "%H:%M:%S.%f")
    return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000


def end_location(row: pd.Series) -> tuple[float | None, float | None]:
    """Extract the end location for an event, returning (end_x, end_y) or (None, None).

    Only Pass, Carry, and Shot events carry end-location data in StatsBomb. All other
    event types return (None, None).

    Args:
        row (pd.Series): A single StatsBomb events row.

    Returns:
        tuple[float | None, float | None]: (end_x, end_y) or (None, None).
    """
    field_map = {
        "Pass":  "pass_end_location",
        "Carry": "carry_end_location",
        "Shot":  "shot_end_location",
    }
    field = field_map.get(str(row.get("type", "")))
    if field:
        loc = row.get(field)
        if isinstance(loc, list) and len(loc) >= 2:
            return float(loc[0]), float(loc[1])
    return None, None


def pass_outcome(row: pd.Series) -> str | None:
    """Extract a human-readable outcome string for a Pass event, or None.

    For Pass events: None means the pass was completed (StatsBomb represents
    completion as a null pass_outcome). Returns None for all non-Pass event types.

    Args:
        row (pd.Series): A single StatsBomb events row.

    Returns:
        str | None: Outcome string for Pass failures; None for completions and
            all non-Pass events.
    """
    if str(row.get("type", "")) == "Pass":
        outcome = row.get("pass_outcome")
        if pd.notna(outcome) and outcome:
            return str(outcome)
        return None
    return None
