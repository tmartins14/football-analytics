"""Extract pressing measures for both teams in one match: PPDA, high
pressures, pressure side, and per-player pressure received (DATA-SPEC-v3
Q4/Q6).

One combined file per match (not per-team) — PPDA and pressure_received both
need cross-team bookkeeping (a team's PPDA numerator is the *opponent's* pass
count; pressure_received covers every player on both sides), which is
awkward to split across two per-team files.

Raw values only — no tercile labeling (`ppda`'s Euro-2024-relative label
needs `reference_distributions.json`, built in Part 2), no
`PRESSURE_MARGIN`/`SIDE_SHARE` thresholding, no claim rendering. Those are
`derive_tactical_findings.py`'s job (DATA-SPEC-v3 Part 4).

"Open play" follows DATA-SPEC-v3's own definition exactly: `play_pattern` in
{Regular Play, From Counter}, and (for passes specifically) `pass_type` is
not one of the set-piece restart types (Corner, Free Kick, Throw-in, Goal
Kick, Kick Off) — stricter than `utils.open_play_mask`, which only excludes
by `play_pattern` and would incorrectly admit "From Keeper"/"Other" events.

Public API:
    extract_pressing(match_id) -> dict
    main()

JSON output shape:
    {
        "teams": {
            "<team name>": {
                "ppda": {
                    "opponent_passes_attempted_deep": int,
                    "defensive_actions_advanced": int,
                    "value": float | null
                },
                "pressures_high": {
                    "count": int,
                    "opponent_open_play_passes": int,
                    "per_100": float | null
                },
                "pressure_side": {"left": int, "centre": int, "right": int}
            }
        },
        "pressure_received": [
            {
                "player_id": int,
                "display_name": str,
                "team": str,
                "on_ball_events": int,
                "under_pressure_events": int,
                "share": float
            }
        ],
        "metadata": {
            "match_id": int,
            "competition": str,
            "match_label": str,
            "open_play_filter": "play_pattern + pass_type",
            "ppda_zone": "opponent's own 60% (x < 72 in the opponent's own frame)",
            "defensive_action_zone": "pressing team's own half+ (x >= 48 in its own frame)",
            "pressures_high_zone": "opponent half (x >= 60 in the pressing team's own frame)"
        }
    }
Written to: data/euro-2024/{match_id}/pressing.json
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .extract_player_events import ALLOWED_TYPES
from .extract_substitutes import get_eligible_players
from .utils import fetch_match_info, resolve_match, side_group

SET_PIECE_PASS_TYPES: frozenset[str] = frozenset({
    "Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off",
})

OPEN_PLAY_PATTERNS: frozenset[str] = frozenset({"Regular Play", "From Counter"})

PPDA_OPPONENT_X: float = 72.0   # opponent's own 60% (DATA-SPEC-v3 Decision 12).
PPDA_DEFENSIVE_X: float = 48.0  # pressing team's own half+.
PRESSURES_HIGH_X: float = 60.0  # opponent half, pressing team's own frame.


def _open_play_pass_mask(events: pd.DataFrame) -> "pd.Series[bool]":
    """Boolean mask for open-play pass attempts, per DATA-SPEC-v3's own definition.

    `play_pattern` in {Regular Play, From Counter} and `pass_type` is not a
    set-piece restart type. Stricter than `utils.open_play_mask` (which only
    excludes by `play_pattern`, admitting "From Keeper"/"Other").

    Args:
        events (pd.DataFrame): Full match event DataFrame.

    Returns:
        pd.Series[bool]: True for open-play Pass events.
    """
    is_pass = events["type"] == "Pass"
    right_pattern = events["play_pattern"].isin(OPEN_PLAY_PATTERNS)
    not_set_piece_type = ~events["pass_type"].isin(SET_PIECE_PASS_TYPES)
    return is_pass & right_pattern & not_set_piece_type


def _defensive_action_mask(events: pd.DataFrame) -> "pd.Series[bool]":
    """Boolean mask for PPDA's defensive-action set: Duel(Tackle, any outcome),
    Interception, Foul Committed.

    Args:
        events (pd.DataFrame): Full match event DataFrame.

    Returns:
        pd.Series[bool]: True for a qualifying defensive action.
    """
    is_tackle = (events["type"] == "Duel") & (events["duel_type"] == "Tackle")
    is_interception = events["type"] == "Interception"
    is_foul = events["type"] == "Foul Committed"
    return is_tackle | is_interception | is_foul


def extract_pressing(match_id: int) -> dict:
    """Compute raw pressing values for both teams in one match.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict: Matches this module's documented JSON output shape, minus
            "metadata" (added by `main`).
    """
    events = sb.events(match_id=match_id)
    teams = sorted(events["team"].dropna().unique().tolist())

    open_play_passes = events[_open_play_pass_mask(events)]
    defensive_actions = events[_defensive_action_mask(events)]
    pressures = events[events["type"] == "Pressure"]

    team_results: dict[str, dict] = {}
    for team in teams:
        opponent_passes = open_play_passes[open_play_passes["team"] != team]
        opponent_passes_deep = opponent_passes[
            opponent_passes["location"].apply(
                lambda loc: isinstance(loc, list) and float(loc[0]) < PPDA_OPPONENT_X
            )
        ]
        own_defensive = defensive_actions[defensive_actions["team"] == team]
        own_defensive_advanced = own_defensive[
            own_defensive["location"].apply(
                lambda loc: isinstance(loc, list) and float(loc[0]) >= PPDA_DEFENSIVE_X
            )
        ]

        numerator = int(len(opponent_passes_deep))
        denominator = int(len(own_defensive_advanced))
        ppda_value = round(numerator / denominator, 4) if denominator else None

        own_pressures = pressures[pressures["team"] == team]
        own_pressures_high = own_pressures[
            own_pressures["location"].apply(
                lambda loc: isinstance(loc, list) and float(loc[0]) >= PRESSURES_HIGH_X
            )
        ]
        opponent_open_play_count = int(len(opponent_passes))
        pressures_high_count = int(len(own_pressures_high))
        per_100 = (
            round(pressures_high_count / opponent_open_play_count * 100, 2)
            if opponent_open_play_count else None
        )

        pressure_side = {"left": 0, "centre": 0, "right": 0}
        for _, row in own_pressures.iterrows():
            loc = row.get("location")
            if isinstance(loc, list):
                pressure_side[side_group(float(loc[1]))] += 1

        team_results[team] = {
            "ppda": {
                "opponent_passes_attempted_deep": numerator,
                "defensive_actions_advanced": denominator,
                "value": ppda_value,
            },
            "pressures_high": {
                "count": pressures_high_count,
                "opponent_open_play_passes": opponent_open_play_count,
                "per_100": per_100,
            },
            "pressure_side": pressure_side,
        }

    # Q6 pressure_received: every eligible (non-goalkeeper) player on both teams.
    roster = get_eligible_players(match_id)
    credited = events[events["type"].isin(ALLOWED_TYPES)]

    pressure_received: list[dict] = []
    for _, prow in roster.iterrows():
        pid = int(prow["player_id"])
        player_events = credited[credited["player_id"] == pid]
        on_ball = int(len(player_events))
        under_pressure = int(
            player_events["under_pressure"].fillna(False).astype(bool).sum()
        )
        share = round(under_pressure / on_ball, 4) if on_ball else 0.0
        pressure_received.append({
            "player_id": pid,
            "display_name": str(prow["display_name"]),
            "team": str(prow["team"]),
            "on_ball_events": on_ball,
            "under_pressure_events": under_pressure,
            "share": share,
        })

    pressure_received.sort(key=lambda p: (-p["share"], p["display_name"]))

    return {"teams": team_results, "pressure_received": pressure_received}


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Extract pressing measures for a match and write one combined JSON file.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output path: {out_dir}/pressing.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    competition, _, match_label = fetch_match_info(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = extract_pressing(match_id)
    payload["metadata"] = {
        "match_id": match_id,
        "competition": competition,
        "match_label": match_label,
        "open_play_filter": "play_pattern + pass_type",
        "ppda_zone": "opponent's own 60% (x < 72 in the opponent's own frame)",
        "defensive_action_zone": "pressing team's own half+ (x >= 48 in its own frame)",
        "pressures_high_zone": "opponent half (x >= 60 in the pressing team's own frame)",
    }

    out_path = out_dir / "pressing.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    for team, result in payload["teams"].items():
        print(f"[{team}] PPDA {result['ppda']['value']}, "
              f"pressures_high/100 {result['pressures_high']['per_100']} → {out_path}")


if __name__ == "__main__":
    main()
