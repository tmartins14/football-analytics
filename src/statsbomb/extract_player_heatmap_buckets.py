"""Extract minute-bucketed cumulative on-ball density (KDE) grids per player.

heatmap.js (see extract_heatmap.py) is a static, full-match KDE grid with no
minute concept. The Player Match Analysis dashboard's Territory panel needs the
density layer to reveal progressively as its master scrubber moves, which a
single full-match grid can't do. This extractor precomputes a KDE grid at each
5-minute cumulative cutoff instead — the panel picks the nearest bucket
<= scrubbedMinute and swaps it into heatmap.js via its existing update(newData)
method, so heatmap.js itself needs no code change.

"Cumulative" means each bucket's grid is built from every located on-ball event
from kickoff through that bucket's minute (not a trailing window) — the same
semantics as convexHull.js's points-mode territory build-up and
cumulativeXtChart.js's running total, so all three panels reveal in lockstep
off the same "minute <= scrubbedMinute" rule.

Bucket generation stops at a player's own last on-ball event minute (e.g. a
substitution or red card) rather than continuing to the match's final minute —
their density grid is frozen from that point on, and the panel's "nearest
bucket <= scrubbedMinute" lookup naturally holds the last emitted bucket for
every later scrub position, so no trailing filler buckets are needed. Leading
buckets with fewer than 2 events (compute_kde_grid's minimum) are omitted
entirely, not zero-filled — a player who hasn't touched the ball yet has no
density surface to show, the panel should render nothing until the first
bucket appears in the list.

Public API:
    extract_player_heatmap_buckets(match_id, player_id=None) -> dict[int, list[dict]]
    main()

JSON output shape (one file per player):
    {
        "buckets": [
            { "upto_minute": 5, "event_count": 3, "grid": {"cols", "rows", "values"} },
            ...
        ],
        "metadata": {"match_id", "player_id", "display_name", "team",
                     "competition", "season", "match_label",
                     "bucket_size_minutes", "bandwidth_yards",
                     "grid_cols", "grid_rows",
                     "pitch_width_yards", "pitch_height_yards"}
    }
Written to: src/footballd3/sample_data/heatmap_buckets/{match_id}/{player_id}.json
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .extract_heatmap import SB_PITCH_HEIGHT, SB_PITCH_WIDTH, compute_kde_grid
from .extract_substitutes import get_eligible_players
from .utils import clean_nan, fetch_match_info, resolve_match

BUCKET_SIZE_MINUTES: int = 5
BANDWIDTH_YARDS: float = 5.0
GRID_COLS: int = 60
GRID_ROWS: int = 40
MIN_EVENTS_FOR_KDE: int = 2


def _bucket_minutes(max_event_minute: int, bucket_size: int = BUCKET_SIZE_MINUTES) -> list[int]:
    """Cumulative bucket cutoffs from bucket_size up to max_event_minute.

    Always ends exactly at max_event_minute even when it isn't a multiple of
    bucket_size, so the player's final on-ball event is never excluded from
    their last bucket.

    Args:
        max_event_minute (int): The player's last located on-ball event minute.
        bucket_size (int): Minutes per bucket. Defaults to 5.

    Returns:
        list[int]: Ascending bucket cutoff minutes, e.g. [5, 10, ..., 70] or
            [5, 10, 13] when max_event_minute isn't a multiple of bucket_size.
            Empty when max_event_minute < bucket_size.
    """
    if max_event_minute < bucket_size:
        return [max_event_minute] if max_event_minute > 0 else []

    buckets = list(range(bucket_size, max_event_minute + 1, bucket_size))
    if buckets[-1] != max_event_minute:
        buckets.append(max_event_minute)
    return buckets


def extract_player_heatmap_buckets(
    match_id: int,
    player_id: int | None = None,
) -> dict[int, list[dict]]:
    """Compute cumulative minute-bucketed KDE grids for eligible players.

    Args:
        match_id (int): StatsBomb match ID.
        player_id (int | None): When given, restricts extraction to this one
            eligible player (fast-iteration path). When None (default), extracts
            every eligible (non-GK, played) player in the match.

    Returns:
        dict[int, list[dict]]: Maps player_id to its ascending bucket list,
            each entry `{"upto_minute", "event_count", "grid"}`. A player with
            fewer than MIN_EVENTS_FOR_KDE located events maps to an empty list.

    Raises:
        ValueError: If player_id is given but is not an eligible player in
            this match.
    """
    eligible = get_eligible_players(match_id)
    eligible_ids = set(eligible["player_id"])

    if player_id is not None:
        if player_id not in eligible_ids:
            raise ValueError(
                f"player_id {player_id} is not an eligible (non-GK, played) "
                f"player in match {match_id}"
            )
        eligible_ids = {player_id}

    events = sb.events(match_id=match_id)
    located = events[events["location"].notna() & events["player_id"].isin(eligible_ids)]

    result: dict[int, list[dict]] = {}
    for pid, group in located.groupby("player_id"):
        pid = int(pid)
        group = group.sort_values(["minute", "second"])
        points = [
            {"x": float(loc[0]), "y": float(loc[1]), "minute": int(minute)}
            for loc, minute in zip(group["location"], group["minute"], strict=True)
        ]

        max_minute = points[-1]["minute"] if points else 0
        buckets: list[dict] = []
        for upto in _bucket_minutes(max_minute):
            cumulative = [p for p in points if p["minute"] <= upto]
            if len(cumulative) < MIN_EVENTS_FOR_KDE:
                continue
            grid = compute_kde_grid(
                cumulative, bandwidth_yards=BANDWIDTH_YARDS, cols=GRID_COLS, rows=GRID_ROWS
            )
            buckets.append({
                "upto_minute": upto,
                "event_count": len(cumulative),
                "grid": grid,
            })
        result[pid] = buckets

    for pid in eligible_ids:
        result.setdefault(pid, [])

    return result


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    player_id: int | None = None,
) -> None:
    """Extract minute-bucketed heatmaps for a match and write one JSON file per player.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Per-match output directory; defaults to
            data/euro-2024/{match_id}/. Files are written under a
            heatmap_buckets/ subdirectory of this path.
        player_id (int | None): When given, writes only this one player's file
            (fast-iteration path). When None (default), writes every eligible
            player's file.

    Output: {out_dir}/heatmap_buckets/{player_id}.json, one per eligible player.
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    buckets_dir = out_dir / "heatmap_buckets"
    buckets_dir.mkdir(parents=True, exist_ok=True)

    competition, season, match_label = fetch_match_info(match_id)
    eligible = get_eligible_players(match_id)
    roster = eligible.set_index("player_id")[["display_name", "team"]].to_dict(orient="index")

    by_player = extract_player_heatmap_buckets(match_id, player_id=player_id)

    for pid, buckets in by_player.items():
        meta = roster[pid]
        buckets = [{k: clean_nan(v) for k, v in bucket.items()} for bucket in buckets]

        payload = {
            "buckets": buckets,
            "metadata": {
                "match_id":            match_id,
                "player_id":           pid,
                "display_name":        meta["display_name"],
                "team":                meta["team"],
                "competition":         competition,
                "season":              season,
                "match_label":         match_label,
                "bucket_size_minutes": BUCKET_SIZE_MINUTES,
                "bandwidth_yards":     BANDWIDTH_YARDS,
                "grid_cols":           GRID_COLS,
                "grid_rows":           GRID_ROWS,
                "pitch_width_yards":   SB_PITCH_WIDTH,
                "pitch_height_yards":  SB_PITCH_HEIGHT,
            },
        }

        out_path = buckets_dir / f"{pid}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"[{meta['display_name']}] {len(buckets)} buckets → {out_path}")


if __name__ == "__main__":
    main()
