"""Extract a time-windowed ball-path event sequence around any match event.

Provides a general-purpose play animation extractor and a goal-specific wrapper.
The clip window is period-isolated: events are filtered to the same period as the
anchor event, preventing the window from straddling a halftime boundary.

Public API:
    extract_play_animation(match_id, anchor_event_id, window_seconds) -> pd.DataFrame
    extract_goal_animation(match_id, window_seconds) -> pd.DataFrame
    main()

DataFrame columns (both functions): goal_event_id, goal_minute, goal_scorer,
    goal_team, event_id, t_seconds, team, event_type, ball_x, ball_y,
    ball_end_x, ball_end_y, actor, outcome
    (goal_* columns are None/NaN for extract_play_animation clips)

JSON output shape (per clip):
    {
        "window": {"anchor_event_id", "start_event_id", "end_event_id", "period",
                   "window_seconds", "t_span_seconds"},
        "frames": [{"event_id", "t_seconds", "team", "event_type", "ball_x", "ball_y",
                    "ball_end_x", "ball_end_y", "actor", "outcome"}],
        "context": {"goal": {"event_id", "minute", "second", "scorer", "team"}} | {},
        "metadata": {"match_id", "competition", "match_label"}
    }

Top-level file (goal_animation_{match_id}.json):
    {
        "goals":          list[clip_dict],
        "match_metadata": {"match_id", "competition", "match_label"}
    }

DISCLAIMER: ball paths are straight event-to-event segments — not real trajectories.
StatsBomb open data contains no continuous tracking.

Written to: libs/footballd3/sample_data/goal_animation_{match_id}.json
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

# Period start offsets in absolute match seconds.
# StatsBomb timestamps reset to 00:00:00 at the start of each period.
PERIOD_OFFSETS: dict[int, float] = {
    1: 0.0,
    2: 45 * 60.0,
    3: 90 * 60.0,
    4: 105 * 60.0,
    5: 120 * 60.0,
}

DEFAULT_WINDOW_SECONDS: float = 10.0

# Event types included in the clip window.
# Ball Receipt* excluded: clusters on Pass end-points with no independent location.
_INCLUDED_TYPES = frozenset({
    "Pass", "Carry", "Shot",
    "Pressure", "Duel", "Interception", "Ball Recovery",
})


def _absolute_seconds(period: int, timestamp: str) -> float:
    """Compute absolute match seconds from a StatsBomb period and timestamp.

    Args:
        period (int): StatsBomb period number (1–5).
        timestamp (str): Timestamp string in "HH:MM:SS.mmm" format.

    Returns:
        float: Absolute match seconds from kick-off.
    """
    return PERIOD_OFFSETS[period] + parse_timestamp(timestamp)


def _find_snap_start(
    events_df: pd.DataFrame,
    anchor_abs_seconds: float,
    window_seconds: float,
) -> float:
    """Find the snap-start time for a clip.

    Returns the absolute time of the nearest event at-or-before
    (anchor_abs_seconds - window_seconds), so the clip always opens on a real
    ball position rather than a gap.

    Args:
        events_df (pd.DataFrame): Events with an 'abs_seconds' column, pre-filtered
            to the anchor event's period.
        anchor_abs_seconds (float): Absolute match time of the anchor event.
        window_seconds (float): Nominal clip duration in seconds.

    Returns:
        float: Absolute match time of the snapped clip start.
    """
    window_start = anchor_abs_seconds - window_seconds
    candidates = events_df[events_df["abs_seconds"] <= window_start]
    if candidates.empty:
        return float(events_df["abs_seconds"].min())
    return float(candidates["abs_seconds"].max())


def _build_play_clip(
    events_df: pd.DataFrame,
    nicknames: dict[int, str],
    anchor_event_id: str,
    window_seconds: float,
    metadata: dict,
) -> dict:
    """Build a single play animation clip dict around any anchor event.

    Shared engine called by both extract_play_animation and extract_goal_animation.
    The clip is period-isolated (no halftime bleed). Snap-start aligns the clip
    to a real ball position.

    Args:
        events_df (pd.DataFrame): All match events with an 'abs_seconds' column.
        nicknames (dict[int, str]): player_id -> display_name mapping.
        anchor_event_id (str): StatsBomb UUID of the anchor event.
        window_seconds (float): Requested clip duration in seconds before the anchor.
        metadata (dict): {"match_id", "competition", "match_label"} to embed.

    Returns:
        dict: Clip dict with keys: window, frames, context (empty {}), metadata.

    Raises:
        ValueError: If anchor_event_id is not found in events_df.
    """
    anchor_rows = events_df[events_df["id"] == anchor_event_id]
    if anchor_rows.empty:
        raise ValueError(f"Anchor event {anchor_event_id!r} not found in events DataFrame")
    anchor_row = anchor_rows.iloc[0]

    anchor_period = int(anchor_row["period"])
    anchor_abs = float(anchor_row["abs_seconds"])

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

        pid = row.get("player_id")
        actor = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid) else str(row.get("player", ""))
        )
        ex, ey = end_location(row)

        frames.append({
            "event_id":   str(row["id"]),
            "t_seconds":  round(float(row["abs_seconds"]) - snap_start, 3),
            "team":       str(row.get("team", "")),
            "event_type": str(row["type"]),
            "ball_x":     float(loc[0]),
            "ball_y":     float(loc[1]),
            "ball_end_x": ex,
            "ball_end_y": ey,
            "actor":      actor,
            "outcome":    pass_outcome(row),
        })

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
) -> pd.DataFrame:
    """Extract a time-windowed ball-path clip anchored to any match event as a DataFrame.

    The clip window is period-isolated so it cannot straddle a halftime or extra-time
    boundary. Start timing snaps to the nearest real event. Both teams' events are
    included; each row carries a "team" column.

    Args:
        match_id (int): StatsBomb match ID.
        anchor_event_id (str): UUID of the event that closes the clip.
        window_seconds (float): Requested clip duration in seconds before the anchor.
            Default is DEFAULT_WINDOW_SECONDS (10.0).

    Returns:
        pd.DataFrame: One row per frame event with columns:
            goal_event_id (str): Equal to anchor_event_id for all rows.
            goal_minute, goal_scorer, goal_team: None (not a goal clip).
            event_id (str), t_seconds (float), team (str), event_type (str),
            ball_x, ball_y (float), ball_end_x, ball_end_y (float | None),
            actor (str), outcome (str | None).
        Also sets df.attrs["clip"] with the full clip dict for JSON reconstruction.

    Raises:
        ValueError: If anchor_event_id is not found in the match's events.
    """
    nicknames = build_nickname_lookup(match_id)
    all_events = sb.events(match_id=match_id)
    all_events["abs_seconds"] = all_events.apply(
        lambda r: _absolute_seconds(int(r["period"]), str(r["timestamp"])), axis=1
    )
    competition, _, match_label = fetch_match_info(match_id)
    metadata = {"match_id": match_id, "competition": competition, "match_label": match_label}
    clip = _build_play_clip(all_events, nicknames, anchor_event_id, window_seconds, metadata)

    records = [
        {
            "goal_event_id": anchor_event_id,
            "goal_minute":   None,
            "goal_scorer":   None,
            "goal_team":     None,
            **frame,
        }
        for frame in clip["frames"]
    ]
    df = pd.DataFrame(records)
    df.attrs["clip"] = clip
    return df


def extract_goal_animation(
    match_id: int,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> pd.DataFrame:
    """Extract ball-path clips for all goals in a match as a tidy DataFrame.

    For each goal (Shot where shot_outcome == "Goal"), builds a clip of the
    preceding window_seconds and returns all frames as rows. Goal metadata
    (scorer, minute) is carried on every row within that goal so the DataFrame
    can be grouped by goal_event_id for analysis or JSON reconstruction.

    The window is time-based (not possession-based), so transition goals keep
    the opponent's final action in frame. Ball Receipt* events are excluded.

    Args:
        match_id (int): StatsBomb match ID.
        window_seconds (float): Clip duration in seconds before each goal. Default 10.0.

    Returns:
        pd.DataFrame: One row per frame event per goal with columns:
            goal_event_id (str): StatsBomb UUID of the goal shot event.
            goal_minute (int): Match minute of the goal.
            goal_scorer (str): Resolved display_name of the scorer.
            goal_team (str): Team name of the scorer.
            event_id (str), t_seconds (float), team (str), event_type (str),
            ball_x, ball_y (float), ball_end_x, ball_end_y (float | None),
            actor (str), outcome (str | None).
        Also sets df.attrs["clips"] (list[dict]) for full JSON reconstruction.

    Raises:
        ValueError: If no goals are found in the match.
    """
    nicknames = build_nickname_lookup(match_id)
    all_events = sb.events(match_id=match_id)
    all_events["abs_seconds"] = all_events.apply(
        lambda r: _absolute_seconds(int(r["period"]), str(r["timestamp"])), axis=1
    )

    goals = all_events[
        (all_events["type"] == "Shot")
        & (all_events["shot_outcome"].astype(str) == "Goal")
    ].copy()

    if goals.empty:
        raise ValueError(f"No goals found in match {match_id}")

    competition, _, match_label = fetch_match_info(match_id)
    metadata = {"match_id": match_id, "competition": competition, "match_label": match_label}

    all_records: list[dict] = []
    clips: list[dict] = []

    for _, goal_row in goals.sort_values("abs_seconds").iterrows():
        goal_event_id = str(goal_row["id"])
        clip = _build_play_clip(all_events, nicknames, goal_event_id, window_seconds, metadata)

        scorer_pid = goal_row.get("player_id")
        scorer = (
            nicknames.get(int(scorer_pid), str(goal_row.get("player", "")))
            if pd.notna(scorer_pid) else str(goal_row.get("player", ""))
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

        for frame in clip["frames"]:
            all_records.append({
                "goal_event_id": goal_event_id,
                "goal_minute":   int(goal_row["minute"]),
                "goal_scorer":   scorer,
                "goal_team":     str(goal_row.get("team", "")),
                **frame,
            })

    df = pd.DataFrame(all_records)
    df.attrs["clips"] = clips
    df.attrs["competition"] = competition
    df.attrs["match_label"] = match_label
    return df


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Extract goal animation clips for a match and write JSON.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output path: {out_dir}/goal_animation.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    print(f"Resolved match_id: {match_id}")

    df = extract_goal_animation(match_id)
    clips = df.attrs["clips"]
    competition = df.attrs["competition"]
    match_label = df.attrs["match_label"]

    output = {
        "goals": clips,
        "match_metadata": {
            "match_id":    match_id,
            "competition": competition,
            "match_label": match_label,
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "goal_animation.json"

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
