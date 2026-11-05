"""Extract chance-creation measures for one team: shot zone/source mix,
shot-assist origin, and per-player creative threat (DATA-SPEC-v3 Q1/Q2).

Non-penalty shots only (`shot_type != "Penalty"`); xG is `shot_statsbomb_xg`.
This module emits raw, per-match values only, each traceable to a specific
raw-event filter — no suppression thresholds (`MIN_TEAM_SHOTS`, `MIN_XA`,
`MIN_KEY_PASSES`), no modal-share labeling, and no claim rendering. Those are
`derive_tactical_findings.py`'s job (DATA-SPEC-v3 Part 4), same split as the
existing v2 extractors (e.g. `extract_team_shape.py` emits raw positions;
labeling happens downstream).

Public API:
    extract_chance_creation(match_id, team) -> dict
    main()

JSON output shape:
    {
        "team": str,
        "shots": {
            "non_penalty_count": int,
            "total_npxg": float,
            "by_zone": {
                "six_yard_box": {"npxg": float, "count": int},
                "box_central":  {"npxg": float, "count": int},
                "box_wide":     {"npxg": float, "count": int},
                "outside_box":  {"npxg": float, "count": int}
            },
            "by_source": {
                "open_play":  {"npxg": float, "count": int},
                "counter":    {"npxg": float, "count": int},
                "set_piece":  {"npxg": float, "count": int},
                "other":      {"npxg": float, "count": int}
            }
        },
        "shot_assists": {
            "total_count": int,
            "by_side_and_type": {
                "left":   {"cross": int, "cut_back": int, "through_ball": int, "other": int},
                "centre": {"cross": int, "cut_back": int, "through_ball": int, "other": int},
                "right":  {"cross": int, "cut_back": int, "through_ball": int, "other": int}
            }
        },
        "creators": [
            {
                "player_id": int,
                "display_name": str,
                "xa": float,
                "key_passes": int,
                "passes_into_box": int
            }
        ],
        "metadata": {
            "match_id": int,
            "team": str,
            "competition": str,
            "match_label": str,
            "zone_filter": "statsbomb_120x80_own_attack_right_frame",
            "source_grouping": {
                "open_play": ["Regular Play"],
                "counter": ["From Counter"],
                "set_piece": ["From Corner", "From Free Kick", "From Throw In"],
                "other": "every other play_pattern (From Goal Kick, From Kick Off, From Keeper, Other)"
            }
        }
    }
Written to: data/euro-2024/{match_id}/chance_creation_{team_slug}.json
"""

import json
import re
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import build_nickname_lookup, fetch_match_info, resolve_match, side_group

SOURCE_GROUPS: dict[str, frozenset[str]] = {
    "open_play": frozenset({"Regular Play"}),
    "counter": frozenset({"From Counter"}),
    "set_piece": frozenset({"From Corner", "From Free Kick", "From Throw In"}),
}


def _shot_zone(x: float, y: float) -> str:
    """Classify a shot location into one of four zones.

    `six_yard_box` (x >= 114, 30 <= y <= 50) is a subset of the box (x >= 102,
    18 <= y <= 62); `box_central` is the rest of the box with 30 <= y <= 50;
    `box_wide` is the remainder of the box; everything else is `outside_box`.

    Args:
        x (float): StatsBomb x-coordinate (0-120), actor's own attack-right frame.
        y (float): StatsBomb y-coordinate (0-80).

    Returns:
        str: One of "six_yard_box", "box_central", "box_wide", "outside_box".
    """
    in_box = x >= 102 and 18 <= y <= 62
    in_six_yard = x >= 114 and 30 <= y <= 50
    if in_six_yard:
        return "six_yard_box"
    if not in_box:
        return "outside_box"
    if 30 <= y <= 50:
        return "box_central"
    return "box_wide"


def _source_group(play_pattern: str) -> str:
    """Map a raw play_pattern value to its Q1 source group, or "other".

    Args:
        play_pattern (str): StatsBomb play_pattern value.

    Returns:
        str: "open_play", "counter", "set_piece", or "other" — "other" covers
            play_pattern values v3 does not name (From Goal Kick, From Kick
            Off, From Keeper, Other), kept distinct rather than dropped so
            `total_npxg` always equals the sum across `by_source`.
    """
    for group, patterns in SOURCE_GROUPS.items():
        if play_pattern in patterns:
            return group
    return "other"


def _assist_type(row: pd.Series) -> str:
    """Classify an assisting pass's type: cross, cut_back, through_ball, or other.

    Checked in that priority order (first match wins) — a pass can in
    principle carry more than one StatsBomb flag.

    Args:
        row (pd.Series): A single StatsBomb Pass event row.

    Returns:
        str: "cross", "cut_back", "through_ball", or "other".
    """
    if pd.notna(row.get("pass_cross")) and bool(row["pass_cross"]):
        return "cross"
    if pd.notna(row.get("pass_cut_back")) and bool(row["pass_cut_back"]):
        return "cut_back"
    if str(row.get("pass_technique", "")) == "Through Ball":
        return "through_ball"
    return "other"


def extract_chance_creation(match_id: int, team: str) -> dict:
    """Compute raw chance-creation values for one team in one match.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name as it appears in StatsBomb data (e.g. "Spain").

    Returns:
        dict: Matches this module's documented JSON output shape, minus
            "metadata" (added by `main`).
    """
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)

    shots = events[
        (events["team"] == team)
        & (events["type"] == "Shot")
        & (events["shot_type"] != "Penalty")
    ]

    by_zone: dict[str, dict] = {
        z: {"npxg": 0.0, "count": 0}
        for z in ("six_yard_box", "box_central", "box_wide", "outside_box")
    }
    by_source: dict[str, dict] = {
        s: {"npxg": 0.0, "count": 0}
        for s in ("open_play", "counter", "set_piece", "other")
    }
    total_npxg = 0.0

    for _, row in shots.iterrows():
        loc = row.get("location")
        if not isinstance(loc, list):
            continue
        xg = float(row["shot_statsbomb_xg"])
        total_npxg += xg

        zone = _shot_zone(float(loc[0]), float(loc[1]))
        by_zone[zone]["npxg"] += xg
        by_zone[zone]["count"] += 1

        source = _source_group(str(row["play_pattern"]))
        by_source[source]["npxg"] += xg
        by_source[source]["count"] += 1

    for d in by_zone.values():
        d["npxg"] = round(d["npxg"], 6)
    for d in by_source.values():
        d["npxg"] = round(d["npxg"], 6)

    # Shot assists: shots in `shots` whose assisting Pass is a shot/goal assist.
    # `shot_key_pass_id` can be entirely absent (not just NaN) when zero shots
    # in the match were key-pass-assisted — same sparse-column behavior as
    # pass_shot_assist/pass_goal_assist above.
    assist_pass_ids = {
        str(v) for v in shots.get("shot_key_pass_id", pd.Series(dtype=object)).dropna().tolist()
    }
    by_side_and_type: dict[str, dict] = {
        side: {"cross": 0, "cut_back": 0, "through_ball": 0, "other": 0}
        for side in ("left", "centre", "right")
    }
    total_assists = 0
    if assist_pass_ids:
        assisting_passes = events[events["id"].isin(assist_pass_ids)]
        for _, prow in assisting_passes.iterrows():
            ploc = prow.get("location")
            if not isinstance(ploc, list):
                continue
            side = side_group(float(ploc[1]))
            atype = _assist_type(prow)
            by_side_and_type[side][atype] += 1
            total_assists += 1

    # Creators (Q2): xA, key passes, passes into the box, per player.
    team_passes = events[(events["team"] == team) & (events["type"] == "Pass")]
    # `pass_shot_assist`/`pass_goal_assist` are entirely absent from the
    # DataFrame (not just NaN) when zero events in the whole match set
    # them — statsbombpy's flattening only creates a column when at least
    # one event carries it. `.get()` with a same-index False default
    # covers that case; `.fillna(False)` alone (bracket indexing) still
    # raises a KeyError when the column doesn't exist at all.
    false_series = pd.Series(False, index=team_passes.index)
    key_pass_mask = (
        team_passes.get("pass_shot_assist", false_series).fillna(False).astype(bool)
        | team_passes.get("pass_goal_assist", false_series).fillna(False).astype(bool)
    )
    key_passes = team_passes[key_pass_mask]

    npxg_by_shot_id = shots.set_index("id")["shot_statsbomb_xg"]

    creators: dict[int, dict] = {}
    for _, prow in key_passes.iterrows():
        pid = prow.get("player_id")
        if pd.isna(pid):
            continue
        pid = int(pid)
        assisted_shot_id = prow.get("pass_assisted_shot_id")
        xa = 0.0
        if pd.notna(assisted_shot_id) and str(assisted_shot_id) in npxg_by_shot_id.index:
            xa = float(npxg_by_shot_id.loc[str(assisted_shot_id)])

        entry = creators.setdefault(pid, {
            "player_id": pid,
            "display_name": nicknames.get(pid, str(prow.get("player", ""))),
            "xa": 0.0,
            "key_passes": 0,
            "passes_into_box": 0,
        })
        entry["xa"] += xa
        entry["key_passes"] += 1

    for _, prow in team_passes.iterrows():
        pid = prow.get("player_id")
        if pd.isna(pid) or int(pid) not in creators:
            continue
        completed = pd.isna(prow.get("pass_outcome"))
        is_open_play = str(prow.get("play_pattern", "")) in ("Regular Play", "From Counter")
        end = prow.get("pass_end_location")
        if completed and is_open_play and isinstance(end, list):
            ex, ey = float(end[0]), float(end[1])
            if ex >= 102 and 18 <= ey <= 62:
                creators[int(pid)]["passes_into_box"] += 1

    for entry in creators.values():
        entry["xa"] = round(entry["xa"], 6)

    return {
        "team": team,
        "shots": {
            "non_penalty_count": int(len(shots)),
            "total_npxg": round(total_npxg, 6),
            "by_zone": by_zone,
            "by_source": by_source,
        },
        "shot_assists": {
            "total_count": total_assists,
            "by_side_and_type": by_side_and_type,
        },
        "creators": sorted(
            creators.values(), key=lambda c: (-c["xa"], c["display_name"])
        ),
    }


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    teams: list[str] | None = None,
) -> None:
    """Extract chance-creation measures for a match and write JSON per team.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.
        teams (list[str] | None): Teams to extract; defaults to both teams in the match.

    Output paths: {out_dir}/chance_creation_{team_slug}.json
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
        payload = extract_chance_creation(match_id, team)
        payload["metadata"] = {
            "match_id": match_id,
            "team": team,
            "competition": competition,
            "match_label": match_label,
            "zone_filter": "statsbomb_120x80_own_attack_right_frame",
            "source_grouping": {
                "open_play": ["Regular Play"],
                "counter": ["From Counter"],
                "set_piece": ["From Corner", "From Free Kick", "From Throw In"],
                "other": "every other play_pattern (From Goal Kick, From Kick Off, From Keeper, Other)",
            },
        }

        team_slug = re.sub(r"[^a-z0-9]+", "_", team.lower()).strip("_")
        out_path = out_dir / f"chance_creation_{team_slug}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(
            f"[{team}] {payload['shots']['non_penalty_count']} non-penalty shots, "
            f"{payload['shots']['total_npxg']} npxG, "
            f"{len(payload['creators'])} creator(s) → {out_path}"
        )


if __name__ == "__main__":
    main()
