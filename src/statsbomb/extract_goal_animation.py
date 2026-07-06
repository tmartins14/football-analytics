"""Extract a time-windowed ball-path event sequence around any match event.

Provides a general-purpose play animation extractor and a goal-specific wrapper
that locates all goals and calls the general engine for each.

The clip window is period-isolated: events are filtered to the same period as the
anchor event, preventing the window from straddling a halftime or extra-time boundary.
Start timing snaps to the nearest real event at-or-before the window start so the
clip always opens on a real ball position.

Public API:
    resolve_euro_2024_final() -> int
    extract_play_animation(match_id, anchor_event_id, window_seconds) -> dict
    extract_goal_animation(match_id, window_seconds) -> list[dict]
    main()

JSON output shape (per clip):
    {
        "window": {
            "anchor_event_id": str,      # UUID of the anchor event
            "start_event_id":  str,      # first frame's event UUID (snap start)
            "end_event_id":    str,      # last frame's event UUID (= anchor)
            "period":          int,      # period of the anchor event
            "window_seconds":  float,    # requested clip duration
            "t_span_seconds":  float     # actual clip span = last frame's t_seconds
        },
        "frames": [
            {
                "event_id":   str,       # StatsBomb UUID
                "t_seconds":  float,     # clip-relative seconds (0.0 at first frame)
                "team":       str,       # team name for this event
                "event_type": str,       # StatsBomb type string
                "ball_x":     float,     # event origin, 120x80 coords
                "ball_y":     float,
                "ball_end_x": float|null,  # Pass/Carry/Shot only; null for point events
                "ball_end_y": float|null,
                "actor":      str,       # resolved display_name
                "outcome":    str|null   # Pass: null=complete, str=failure; else null
            }
        ],
        "context": {},                   # empty for general clips; goal wrapper injects
                                         # {"goal": {"event_id","minute","second","scorer","team"}}
        "metadata": {
            "match_id":    int,
            "competition": str,
            "match_label": str
        }
    }

Top-level file structure (goal_animation_{match_id}.json):
    {
        "goals":          list[clip_dict],   # one clip per goal, in chronological order
        "match_metadata": {"match_id","competition","match_label"}
    }

DISCLAIMER: ball paths are straight event-to-event segments — not real trajectories.
Players appear only at their events (where they touched the ball); off-ball movement is
not shown. StatsBomb open data contains no continuous tracking.

Written to: src/footballd3/sample_data/goal_animation_{match_id}.json
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from statsbombpy import sb

# Period start offsets in absolute match seconds.
# StatsBomb timestamps reset to 00:00:00.000 at the start of each period.
# Events in stoppage time exceed the nominal period end (e.g., 45:03:xx in period 1)
# and are handled correctly without special-casing because timestamps keep incrementing.
PERIOD_OFFSETS: dict[int, float] = {
    1: 0.0,
    2: 45 * 60.0,
    3: 90 * 60.0,   # extra time first half
    4: 105 * 60.0,  # extra time second half
    5: 120 * 60.0,  # penalty shootout
}

DEFAULT_WINDOW_SECONDS: float = 10.0

# Event types included in the clip window.
# Pass/Carry/Shot: ball moves (ball_end_x/y present).
# Pressure/Duel/Interception/Ball Recovery: point events (ball_end_x/y = null).
# Ball Receipt* excluded: clusters on Pass end-points with no independent location.
_INCLUDED_TYPES = frozenset({
    "Pass", "Carry", "Shot",
    "Pressure", "Duel", "Interception", "Ball Recovery",
})


def resolve_euro_2024_final() -> int:
    """Resolve the UEFA Euro 2024 Final match ID from the StatsBomb open data API.

    Duplicated from extract_shots, extract_pass_network, extract_progressive_map, and
    extract_possession. Shared utility extraction is deferred until a further refactor.

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
    """Build a player_id -> display_name mapping from sb.lineups() for all teams.

    display_name coalesces player_nickname (when non-empty) with player_name.

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


def _parse_timestamp(ts: str) -> float:
    """Parse a StatsBomb timestamp string to total seconds within the period.

    StatsBomb timestamps are formatted as "HH:MM:SS.mmm" and reset to 00:00:00
    at the start of each period. Use _absolute_seconds() for cross-period time.

    Args:
        ts (str): Timestamp string in "HH:MM:SS.mmm" format.

    Returns:
        float: Total seconds represented by the timestamp within the period.
    """
    t = datetime.strptime(ts, "%H:%M:%S.%f")
    return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000


def _absolute_seconds(period: int, timestamp: str) -> float:
    """Compute absolute match seconds from a StatsBomb period and timestamp.

    This is the first extractor in this codebase to need cross-period absolute time.
    The clip window can span multiple possessions and does not reset at period boundaries.

    Args:
        period (int): StatsBomb period number (1–5). Period offsets defined in
            PERIOD_OFFSETS; unknown periods raise KeyError.
        timestamp (str): Timestamp string in "HH:MM:SS.mmm" format.

    Returns:
        float: Absolute match seconds from kick-off.
    """
    return PERIOD_OFFSETS[period] + _parse_timestamp(timestamp)


def _end_location(row: pd.Series) -> tuple[float | None, float | None]:
    """Extract the end location for an event, returning (end_x, end_y) or (None, None).

    Only Pass, Carry, and Shot events carry end-location data in StatsBomb.
    All other event types return (None, None).

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


def _outcome(row: pd.Series) -> str | None:
    """Extract a human-readable outcome string for an event, or None.

    For Pass events: None means completed (StatsBomb represents completion as null
    pass_outcome). For all other event types, returns None.

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


def _find_snap_start(
    events_df: pd.DataFrame,
    anchor_abs_seconds: float,
    window_seconds: float,
) -> float:
    """Find the snap-start time for a clip.

    Returns the absolute match time of the nearest event at-or-before
    (anchor_abs_seconds - window_seconds). This ensures the clip always opens
    on a real ball position, never in a gap.

    Args:
        events_df (pd.DataFrame): Events with an 'abs_seconds' column, pre-filtered
            to the anchor event's period.
        anchor_abs_seconds (float): Absolute match time of the anchor event.
        window_seconds (float): Nominal clip duration in seconds.

    Returns:
        float: Absolute match time of the snapped clip start. If no event exists
            before (anchor_abs_seconds - window_seconds), returns the earliest
            event's abs_seconds.
    """
    window_start = anchor_abs_seconds - window_seconds
    candidates = events_df[events_df["abs_seconds"] <= window_start]
    if candidates.empty:
        return float(events_df["abs_seconds"].min())
    return float(candidates["abs_seconds"].max())


def _build_frame(
    row: pd.Series,
    nicknames: dict[int, str],
    snap_start_abs: float,
) -> dict:
    """Build a single animation frame dict from a StatsBomb event row.

    Emits clip-relative t_seconds (0.0 at the clip's snap start). The team field
    carries which team performed the event, enabling both-team rendering.
    actor_x/actor_y are omitted — in StatsBomb events the actor is always at the
    event origin (ball_x, ball_y).

    Args:
        row (pd.Series): A single StatsBomb events row. Must have a valid
            'location' field and an 'abs_seconds' column added by the caller.
        nicknames (dict[int, str]): Player ID to display_name mapping.
        snap_start_abs (float): Absolute match seconds of the clip's snap start,
            used to compute clip-relative t_seconds.

    Returns:
        dict: Frame dict conforming to the play animation contract.
    """
    loc = row["location"]
    pid = row.get("player_id")
    player = (
        nicknames.get(int(pid), str(row.get("player", "")))
        if pd.notna(pid)
        else str(row.get("player", ""))
    )

    end_x, end_y = _end_location(row)

    return {
        "event_id":   str(row["id"]),
        "t_seconds":  round(float(row["abs_seconds"]) - snap_start_abs, 3),
        "team":       str(row.get("team", "")),
        "event_type": str(row["type"]),
        "ball_x":     float(loc[0]),
        "ball_y":     float(loc[1]),
        "ball_end_x": end_x,
        "ball_end_y": end_y,
        "actor":      player,
        "outcome":    _outcome(row),
    }


def _pick_best_goal(
    goals_df: pd.DataFrame,
    events_df: pd.DataFrame,
    window_seconds: float = 30.0,
) -> pd.Series:
    """Select the goal with the richest ball-movement build-up in the preceding window.

    Scores each goal by the number of Pass/Carry/Shot events for any team within
    window_seconds before the goal. Prefer the goal the animation will show most clearly.

    Args:
        goals_df (pd.DataFrame): Subset of events_df containing only Shot/Goal rows.
        events_df (pd.DataFrame): All match events with an 'abs_seconds' column.
        window_seconds (float): Look-back window for scoring (wider than the default
            clip window to avoid penalising goals that have action earlier).

    Returns:
        pd.Series: The row from goals_df with the highest build-up event count.
    """
    movement_types = {"Pass", "Carry", "Shot"}
    best_idx = None
    best_score = -1

    for idx, goal_row in goals_df.iterrows():
        goal_abs = goal_row["abs_seconds"]
        window_events = events_df[
            (events_df["abs_seconds"] >= goal_abs - window_seconds)
            & (events_df["abs_seconds"] <= goal_abs)
            & (events_df["type"].isin(movement_types))
        ]
        score = len(window_events)
        if score > best_score:
            best_score = score
            best_idx = idx

    return goals_df.loc[best_idx]


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


def _build_play_clip(
    events_df: pd.DataFrame,
    nicknames: dict[int, str],
    anchor_event_id: str,
    window_seconds: float,
    metadata: dict,
) -> dict:
    """Build a single play animation clip around any anchor event.

    This is the shared engine called by both extract_play_animation and
    extract_goal_animation. Receives a pre-loaded events DataFrame (with
    abs_seconds already added) and a pre-built nickname lookup.

    The clip is period-isolated: events are filtered to the anchor's period
    before the window is applied, preventing the clip from straddling a
    halftime or extra-time boundary.

    Args:
        events_df (pd.DataFrame): All match events with an 'abs_seconds' column.
        nicknames (dict[int, str]): Player ID to display_name mapping.
        anchor_event_id (str): StatsBomb UUID of the anchor event (typically the
            last event to include, e.g., a goal shot).
        window_seconds (float): Requested clip duration in seconds before the anchor.
        metadata (dict): {"match_id", "competition", "match_label"} to embed.

    Returns:
        dict: Clip dict conforming to the play animation contract. The "context"
            key is an empty dict; callers inject goal or other context after the fact.

    Raises:
        ValueError: If anchor_event_id is not found in events_df.
    """
    anchor_rows = events_df[events_df["id"] == anchor_event_id]
    if anchor_rows.empty:
        raise ValueError(f"Anchor event {anchor_event_id!r} not found in events DataFrame")
    anchor_row = anchor_rows.iloc[0]

    anchor_period = int(anchor_row["period"])
    anchor_abs = float(anchor_row["abs_seconds"])

    # Isolate events to the same period to prevent cross-period window bleed.
    period_events = events_df[events_df["period"] == anchor_period]

    snap_start = _find_snap_start(period_events, anchor_abs, window_seconds)

    clip_events = period_events[
        (period_events["abs_seconds"] >= snap_start)
        & (period_events["abs_seconds"] <= anchor_abs)
        & (period_events["type"].isin(_INCLUDED_TYPES))
    ].sort_values("index")

    frames: list[dict] = []
    for _, row in clip_events.iterrows():
        loc = row.get("location")
        if not isinstance(loc, list) or len(loc) < 2:
            continue
        frames.append(_build_frame(row, nicknames, snap_start))

    t_span = round(frames[-1]["t_seconds"], 3) if frames else 0.0

    return {
        "window": {
            "anchor_event_id": anchor_event_id,
            "start_event_id":  frames[0]["event_id"] if frames else anchor_event_id,
            "end_event_id":    frames[-1]["event_id"] if frames else anchor_event_id,
            "period":          anchor_period,
            "window_seconds":  window_seconds,
            "t_span_seconds":  t_span,
        },
        "frames":   frames,
        "context":  {},
        "metadata": metadata,
    }


def extract_play_animation(
    match_id: int,
    anchor_event_id: str,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> dict:
    """Extract a time-windowed ball-path clip anchored to any match event.

    Loads events and lineups from the StatsBomb API, then delegates to the
    shared _build_play_clip engine. The clip window is period-isolated so it
    cannot straddle a halftime or extra-time boundary. Start timing snaps to the
    nearest real event at-or-before (anchor_time - window_seconds).

    All events within the window for BOTH teams are included. Each frame carries
    a "team" field so the renderer can distinguish sides if desired.

    Args:
        match_id (int): StatsBomb match ID.
        anchor_event_id (str): UUID of the event that closes the clip (typically
            the last event to animate, e.g., a goal shot or key pass).
        window_seconds (float): Requested clip duration in seconds before the anchor.
            Default is DEFAULT_WINDOW_SECONDS (10.0). This is a configurable choice;
            see README.md for guidance on selecting a value.

    Returns:
        dict: Clip dict with keys: window, frames, context (empty {}), metadata.

    Raises:
        ValueError: If anchor_event_id is not found in the match's events.
    """
    nicknames = _build_nickname_lookup(match_id)
    all_events = sb.events(match_id=match_id)
    all_events["abs_seconds"] = all_events.apply(
        lambda r: _absolute_seconds(int(r["period"]), str(r["timestamp"])),
        axis=1,
    )
    competition, match_label = _fetch_match_info(match_id)
    metadata = {"match_id": match_id, "competition": competition, "match_label": match_label}
    return _build_play_clip(all_events, nicknames, anchor_event_id, window_seconds, metadata)


def extract_goal_animation(
    match_id: int,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> list[dict]:
    """Extract ball-path clips for all goals in a match.

    Thin wrapper around _build_play_clip: loads events and lineups once, finds
    every goal (Shot events where shot_outcome == "Goal"), calls the shared engine
    for each, and injects context.goal metadata into each clip.

    The window is time-based (not possession-based), so transition goals keep the
    opponent's final action in frame. Ball Receipt* events are excluded.

    Args:
        match_id (int): StatsBomb match ID.
        window_seconds (float): Clip duration in seconds before each goal.
            Default is DEFAULT_WINDOW_SECONDS (10.0). See README.md.

    Returns:
        list[dict]: One clip dict per goal in chronological order. Each clip
            conforms to the play animation contract with context.goal populated.

    Raises:
        ValueError: If no goals are found in the match.
    """
    nicknames = _build_nickname_lookup(match_id)
    all_events = sb.events(match_id=match_id)
    all_events["abs_seconds"] = all_events.apply(
        lambda r: _absolute_seconds(int(r["period"]), str(r["timestamp"])),
        axis=1,
    )

    goals = all_events[
        (all_events["type"] == "Shot")
        & (all_events["shot_outcome"].astype(str) == "Goal")
    ].copy()

    if goals.empty:
        raise ValueError(f"No goals found in match {match_id}")

    competition, match_label = _fetch_match_info(match_id)
    metadata = {"match_id": match_id, "competition": competition, "match_label": match_label}

    clips: list[dict] = []
    for _, goal_row in goals.sort_values("abs_seconds").iterrows():
        goal_event_id = str(goal_row["id"])

        clip = _build_play_clip(all_events, nicknames, goal_event_id, window_seconds, metadata)

        # Resolve scorer display name.
        scorer_pid = goal_row.get("player_id")
        scorer = (
            nicknames.get(int(scorer_pid), str(goal_row.get("player", "")))
            if pd.notna(scorer_pid)
            else str(goal_row.get("player", ""))
        )

        clip["context"] = {
            "goal": {
                "event_id": goal_event_id,
                "minute":   int(goal_row["minute"]),
                "second":   int(goal_row["second"]),
                "scorer":   scorer,
                "team":     str(goal_row.get("team", "")),
            }
        }
        clips.append(clip)

    return clips


def main() -> None:
    """Resolve the Euro 2024 Final, extract all goal clips, and write JSON.

    Output path:
        src/footballd3/sample_data/goal_animation_{match_id}.json

    Prints a summary per goal: scorer, minute, frame count, and clip duration.
    """
    match_id = resolve_euro_2024_final()
    print(f"Resolved match_id: {match_id}")

    clips = extract_goal_animation(match_id)

    competition, match_label = _fetch_match_info(match_id)
    output = {
        "goals": clips,
        "match_metadata": {
            "match_id":    match_id,
            "competition": competition,
            "match_label": match_label,
        },
    }

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"goal_animation_{match_id}.json"

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(clips)} goal clip(s) to {out_path}")
    for i, clip in enumerate(clips, 1):
        g = clip["context"]["goal"]
        n_frames = len(clip["frames"])
        t_span = clip["window"]["t_span_seconds"]
        types = {f["event_type"] for f in clip["frames"]}
        print(
            f"  Goal {i}: {g['scorer']} ({g['team']}) {g['minute']}' — "
            f"{n_frames} frames, {t_span:.1f}s, types={sorted(types)}"
        )


if __name__ == "__main__":
    main()
