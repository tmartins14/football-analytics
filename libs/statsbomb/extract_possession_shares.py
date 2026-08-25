"""Extract cumulative team-possession share at each minute bucket, match-level.

Feeds playerStatCards' (footballd3) client-side PAdj defensive actions
calculation — the one metric of the six stat cards that can't live on a
single player's own event record (extract_player_events.py already carries
everything xA and xGChain need), since it requires whole-match opponent-
possession context. One small file per MATCH, not per player — every
player's stat card reads the same file.

Possession share is approximated by each team's fraction of DISTINCT
possession ids among events with minute <= that bucket's cutoff — StatsBomb's
open data carries no possession-duration field, so this is a possession-COUNT
proxy, not a time-weighted "68% possession" broadcast-graphic figure.
Recorded explicitly in metadata as possession_share_method (same method and
same caveat a prior extract_player_match_summary.py used for its single
match-total possession split, now bucketed by minute instead).

Public API:
    extract_possession_shares(match_id) -> list[dict]
    main()

JSON output shape:
    {
        "buckets": [
            { "upto_minute": 5, "team_possession_pct": {"Spain": 52.1, "England": 47.9} },
            ...
        ],
        "metadata": {"match_id", "teams", "competition", "season", "match_label",
                     "bucket_size_minutes", "possession_share_method"}
    }
Written to: libs/footballd3/sample_data/possession_shares_{match_id}.json
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import fetch_match_info, resolve_match

BUCKET_SIZE_MINUTES: int = 5


def _bucket_minutes(max_minute: int, bucket_size: int = BUCKET_SIZE_MINUTES) -> list[int]:
    """Cumulative bucket cutoffs from bucket_size up to max_minute.

    Always ends exactly at max_minute even when it isn't a multiple of
    bucket_size, so the match's final minute is never excluded from the last
    bucket. Unlike extract_player_heatmap_buckets.py's per-player version,
    there is no "stop at last credited event" truncation here — this is
    match-wide, so buckets run all the way to the match's own final minute.

    Args:
        max_minute (int): The match's last event minute.
        bucket_size (int): Minutes per bucket. Defaults to 5.

    Returns:
        list[int]: Ascending bucket cutoff minutes, e.g. [5, 10, ..., 94].
    """
    if max_minute < bucket_size:
        return [max_minute] if max_minute > 0 else []

    buckets = list(range(bucket_size, max_minute + 1, bucket_size))
    if buckets[-1] != max_minute:
        buckets.append(max_minute)
    return buckets


def _possession_shares_at(
    events: pd.DataFrame,
    upto_minute: int,
    teams: list[str],
) -> dict[str, float]:
    """Each team's possession share (0-100) among events with minute <= upto_minute.

    Counts each `possession` id once (by its possession_team), not weighted
    by elapsed time — see module docstring.

    Args:
        events (pd.DataFrame): Full match event DataFrame.
        upto_minute (int): Cumulative cutoff minute.
        teams (list[str]): The match's team names (ensures both keys are
            always present, even if one team somehow has zero possessions
            in an early bucket).

    Returns:
        dict[str, float]: team name -> possession percentage, summing to 100
            (or all zeros if no possessions exist yet at this cutoff).
    """
    cutoff = events[events["minute"] <= upto_minute]
    by_team = cutoff.drop_duplicates("possession")["possession_team"].value_counts()
    total = int(by_team.sum())
    return {
        team: round(100 * int(by_team.get(team, 0)) / total, 2) if total else 0.0
        for team in teams
    }


def extract_possession_shares(match_id: int) -> list[dict]:
    """Compute cumulative team-possession share at each 5-minute bucket.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        list[dict]: Ascending `{ "upto_minute": int, "team_possession_pct":
            {team: float} }` entries, one per bucket.
    """
    events = sb.events(match_id=match_id)
    teams = sorted(events["possession_team"].dropna().unique().tolist())
    max_minute = int(events["minute"].max())

    return [
        {
            "upto_minute": upto,
            "team_possession_pct": _possession_shares_at(events, upto, teams),
        }
        for upto in _bucket_minutes(max_minute)
    ]


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Extract possession shares for a match and write one JSON file.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to
            data/euro-2024/{match_id}/.

    Output: {out_dir}/possession_shares_{match_id}.json.
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    competition, season, match_label = fetch_match_info(match_id)
    buckets = extract_possession_shares(match_id)
    teams = sorted(buckets[0]["team_possession_pct"].keys()) if buckets else []

    payload = {
        "buckets": buckets,
        "metadata": {
            "match_id":                match_id,
            "teams":                   teams,
            "competition":             competition,
            "season":                  season,
            "match_label":             match_label,
            "bucket_size_minutes":     BUCKET_SIZE_MINUTES,
            "possession_share_method": "distinct_possession_id_count",
        },
    }

    out_path = out_dir / f"possession_shares_{match_id}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[{match_label}] {len(buckets)} buckets → {out_path}")


if __name__ == "__main__":
    main()
