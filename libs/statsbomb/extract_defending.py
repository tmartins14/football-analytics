"""Extract defending measures for one team: defensive action height, high
turnovers, and ball-winning zone (DATA-SPEC-v3 Q5 — minus `block_height`,
which needs no new extractor work: it is already v2's `off_ball.centroid.x`
in `team_shape_{team_slug}.json`; v3 only adds a tercile label to it in Part
4 once reference data exists).

A "successful" Duel of type Tackle (used by both `defensive_action_height`
and `win_zone`) is `outcome` in {"Won", "Success In Play"} — confirmed in
`AUDIT-v3.md` to be the only two non-overlapping success values StatsBomb
uses for this match; Tyler's decision from that audit's open question was
that both count.

Raw values only — no tercile labeling (needs `reference_distributions.json`,
built in Part 2), no `MODAL_SHARE` labeling, no claim rendering. Those are
`derive_tactical_findings.py`'s job (DATA-SPEC-v3 Part 4).

Public API:
    extract_defending(match_id, team) -> dict
    main()

JSON output shape:
    {
        "team": str,
        "defensive_action_height": {"mean_x": float | null, "n_actions": int},
        "high_turnovers": {"count": int, "ended_in_shot": int},
        "win_zone": {
            "own_third": int, "own_half": int,
            "opposition_half": int, "final_third": int
        },
        "metadata": {
            "match_id": int,
            "team": str,
            "competition": str,
            "match_label": str,
            "successful_tackle_outcomes": ["Won", "Success In Play"],
            "high_turnover_x": float
        }
    }
Written to: data/euro-2024/{match_id}/defending_{team_slug}.json
"""

import json
import re
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .tactical_definitions import band_for_x
from .utils import fetch_match_info, resolve_match

SUCCESSFUL_TACKLE_OUTCOMES: frozenset[str] = frozenset({"Won", "Success In Play"})
HIGH_TURNOVER_X: float = 76.0
OPEN_PLAY_PATTERNS: frozenset[str] = frozenset({"Regular Play", "From Counter"})


def _is_successful_tackle(row: pd.Series) -> bool:
    """True when a Duel event is a successful Tackle.

    Args:
        row (pd.Series): A single StatsBomb events row.

    Returns:
        bool: True when type is Duel, duel_type is Tackle, and outcome is
            "Won" or "Success In Play".
    """
    if row.get("type") != "Duel" or row.get("duel_type") != "Tackle":
        return False
    return str(row.get("duel_outcome", "")) in SUCCESSFUL_TACKLE_OUTCOMES


def _defensive_action_height(events: pd.DataFrame, team: str) -> dict:
    """Mean x-coordinate of Ball Recovery, Interception, successful Duel
    (Tackle), Block, and Clearance events for one team.

    Args:
        events (pd.DataFrame): Full match event DataFrame.
        team (str): Team name.

    Returns:
        dict: {"mean_x": float | None, "n_actions": int}.
    """
    team_events = events[events["team"] == team]
    recov = team_events[team_events["type"].isin(["Ball Recovery", "Interception", "Block", "Clearance"])]
    tackles = team_events[team_events.apply(_is_successful_tackle, axis=1)]
    combined = pd.concat([recov, tackles])

    xs = [float(loc[0]) for loc in combined["location"] if isinstance(loc, list)]
    mean_x = round(sum(xs) / len(xs), 2) if xs else None
    return {"mean_x": mean_x, "n_actions": len(xs)}


def _high_turnovers(events: pd.DataFrame, team: str) -> dict:
    """Count open-play possessions this team won at x >= HIGH_TURNOVER_X,
    and how many of those possessions produced a shot.

    "First event by the possession team" is the earliest event, within a
    possession id this team owns (possession_team == team), whose own actor
    is also this team — skipping any stray opponent event still tagged
    under that possession id.

    Args:
        events (pd.DataFrame): Full match event DataFrame.
        team (str): Team name.

    Returns:
        dict: {"count": int, "ended_in_shot": int}.
    """
    owned = events[(events["possession_team"] == team) & (events["team"] == team)]
    first_by_possession = owned.sort_index().groupby("possession").first()

    shot_possessions = set(
        events[(events["team"] == team) & (events["type"] == "Shot")]["possession"]
    )

    count = 0
    ended_in_shot = 0
    for possession_id, row in first_by_possession.iterrows():
        loc = row.get("location")
        if not isinstance(loc, list):
            continue
        if row.get("play_pattern") not in OPEN_PLAY_PATTERNS:
            continue
        if float(loc[0]) < HIGH_TURNOVER_X:
            continue
        count += 1
        if possession_id in shot_possessions:
            ended_in_shot += 1

    return {"count": count, "ended_in_shot": ended_in_shot}


def _win_zone(events: pd.DataFrame, team: str) -> dict:
    """Ball-winning action counts by band: Ball Recovery, Interception,
    successful Duel (Tackle).

    Args:
        events (pd.DataFrame): Full match event DataFrame.
        team (str): Team name.

    Returns:
        dict: {"own_third": int, "own_half": int, "opposition_half": int, "final_third": int}.
    """
    team_events = events[events["team"] == team]
    recov = team_events[team_events["type"].isin(["Ball Recovery", "Interception"])]
    tackles = team_events[team_events.apply(_is_successful_tackle, axis=1)]
    combined = pd.concat([recov, tackles])

    bands = {"own_third": 0, "own_half": 0, "opposition_half": 0, "final_third": 0}
    for loc in combined["location"]:
        if isinstance(loc, list):
            bands[band_for_x(float(loc[0]))] += 1
    return bands


def extract_defending(match_id: int, team: str) -> dict:
    """Compute raw defending values for one team in one match.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name as it appears in StatsBomb data (e.g. "Spain").

    Returns:
        dict: Matches this module's documented JSON output shape, minus
            "metadata" (added by `main`).
    """
    events = sb.events(match_id=match_id)
    return {
        "team": team,
        "defensive_action_height": _defensive_action_height(events, team),
        "high_turnovers": _high_turnovers(events, team),
        "win_zone": _win_zone(events, team),
    }


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    teams: list[str] | None = None,
) -> None:
    """Extract defending measures for a match and write JSON per team.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.
        teams (list[str] | None): Teams to extract; defaults to both teams in the match.

    Output paths: {out_dir}/defending_{team_slug}.json
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
        payload = extract_defending(match_id, team)
        payload["metadata"] = {
            "match_id": match_id,
            "team": team,
            "competition": competition,
            "match_label": match_label,
            "successful_tackle_outcomes": sorted(SUCCESSFUL_TACKLE_OUTCOMES),
            "high_turnover_x": HIGH_TURNOVER_X,
        }

        team_slug = re.sub(r"[^a-z0-9]+", "_", team.lower()).strip("_")
        out_path = out_dir / f"defending_{team_slug}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(
            f"[{team}] defensive height {payload['defensive_action_height']['mean_x']}, "
            f"high turnovers {payload['high_turnovers']['count']} → {out_path}"
        )


if __name__ == "__main__":
    main()
