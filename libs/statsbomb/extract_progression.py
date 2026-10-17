"""Extract progression measures for one team: side bias, pass/carry mode
mix, and per-player progressive-action volume (DATA-SPEC-v3 Q3).

Progressive action = StatsBomb's own 25%-of-remaining-distance-to-goal-centre
rule (`extract_progressive_map._is_progressive`, reused here rather than
reimplemented), applied to open-play passes (completed and incomplete) and
carries, with set-piece phases excluded via `play_pattern`. v3's own drafted
Q3 fallback (an `x >= 48` start-zone restriction plus a flat 10-yard-or-box-
entry test) is not used — per Tyler's decision from `AUDIT-v3.md`'s audit
item 4, the existing `progressive_map` extractor's definition is reused
outright, not layered with a second rule.

Raw per-team and per-player values only — no suppression thresholds
(`MIN_TEAM_PROG`, `MIN_PROG_ACTIONS`), no side-balance labeling
(`SIDE_SHARE`/`SIDE_MARGIN`), no claim rendering. That's
`derive_tactical_findings.py`'s job (DATA-SPEC-v3 Part 4).

Public API:
    extract_progression(match_id, team) -> dict
    main()

JSON output shape:
    {
        "team": str,
        "progressive_actions": {
            "total_count": int,
            "by_side": {"left": int, "centre": int, "right": int},
            "by_mode": {"pass": int, "carry": int}
        },
        "progressors": [
            {
                "player_id": int,
                "display_name": str,
                "count": int,
                "passes": int,
                "carries": int
            }
        ],
        "params": {"progressive_threshold": float},
        "metadata": {
            "match_id": int,
            "team": str,
            "competition": str,
            "match_label": str,
            "open_play_filter": "play_pattern"
        }
    }
Written to: data/euro-2024/{match_id}/progression_{team_slug}.json
"""

import json
import re
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .extract_progressive_map import PROGRESSIVE_THRESHOLD, _is_progressive
from .utils import (
    SET_PIECE_PLAY_PATTERNS,
    build_nickname_lookup,
    fetch_match_info,
    resolve_match,
    side_group,
)


def extract_progression(match_id: int, team: str) -> dict:
    """Compute raw progression values for one team in one match.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name as it appears in StatsBomb data (e.g. "Spain").

    Returns:
        dict: Matches this module's documented JSON output shape, minus
            "params"/"metadata" (added by `main`).
    """
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)

    team_events = events[
        (events["team"] == team)
        & (~events["play_pattern"].isin(SET_PIECE_PLAY_PATTERNS))
    ]

    by_side = {"left": 0, "centre": 0, "right": 0}
    by_mode = {"pass": 0, "carry": 0}
    progressors: dict[int, dict] = {}

    def _record(pid: int, display_name: str, mode: str, end_y: float) -> None:
        by_mode[mode] += 1
        by_side[side_group(end_y)] += 1
        entry = progressors.setdefault(pid, {
            "player_id": pid,
            "display_name": display_name,
            "count": 0,
            "passes": 0,
            "carries": 0,
        })
        entry["count"] += 1
        entry["passes" if mode == "pass" else "carries"] += 1

    for _, row in team_events[team_events["type"] == "Pass"].iterrows():
        loc, end = row.get("location"), row.get("pass_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue
        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])
        if not _is_progressive(x0, y0, x1, y1, PROGRESSIVE_THRESHOLD):
            continue
        pid = row.get("player_id")
        if pd.isna(pid):
            continue
        pid = int(pid)
        display_name = nicknames.get(pid, str(row.get("player", "")))
        _record(pid, display_name, "pass", y1)

    for _, row in team_events[team_events["type"] == "Carry"].iterrows():
        loc, end = row.get("location"), row.get("carry_end_location")
        if not isinstance(loc, list) or not isinstance(end, list):
            continue
        x0, y0 = float(loc[0]), float(loc[1])
        x1, y1 = float(end[0]), float(end[1])
        if not _is_progressive(x0, y0, x1, y1, PROGRESSIVE_THRESHOLD):
            continue
        pid = row.get("player_id")
        if pd.isna(pid):
            continue
        pid = int(pid)
        display_name = nicknames.get(pid, str(row.get("player", "")))
        _record(pid, display_name, "carry", y1)

    total_count = by_mode["pass"] + by_mode["carry"]

    return {
        "team": team,
        "progressive_actions": {
            "total_count": total_count,
            "by_side": by_side,
            "by_mode": by_mode,
        },
        "progressors": sorted(
            progressors.values(), key=lambda p: (-p["count"], p["display_name"])
        ),
    }


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    teams: list[str] | None = None,
) -> None:
    """Extract progression measures for a match and write JSON per team.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.
        teams (list[str] | None): Teams to extract; defaults to both teams in the match.

    Output paths: {out_dir}/progression_{team_slug}.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    competition, _, match_label = fetch_match_info(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    if teams is None:
        comps = sb.competitions()
        euro = comps[
            comps["competition_name"].str.contains("UEFA Euro", case=False)
            & (comps["season_name"] == "2024")
        ]
        matches = sb.matches(
            competition_id=int(euro["competition_id"].iloc[0]),
            season_id=int(euro["season_id"].iloc[0]),
        )
        row = matches[matches["match_id"] == match_id].iloc[0]
        teams = [str(row["home_team"]), str(row["away_team"])]

    for team in teams:
        payload = extract_progression(match_id, team)
        payload["params"] = {"progressive_threshold": PROGRESSIVE_THRESHOLD}
        payload["metadata"] = {
            "match_id": match_id,
            "team": team,
            "competition": competition,
            "match_label": match_label,
            "open_play_filter": "play_pattern",
        }

        team_slug = re.sub(r"[^a-z0-9]+", "_", team.lower()).strip("_")
        out_path = out_dir / f"progression_{team_slug}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(
            f"[{team}] {payload['progressive_actions']['total_count']} progressive actions, "
            f"{len(payload['progressors'])} progressor(s) → {out_path}"
        )


if __name__ == "__main__":
    main()
