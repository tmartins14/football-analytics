"""Extract the timestamped on-ball event stream for every eligible player in a match.

Eligible players are every non-goalkeeper player who actually played (starter or
substitute), sourced from extract_substitutes.get_eligible_players — see that
module for why the roster can't be derived from formation periods alone.

Credited event types: Pass, Carry, Pressure, Duel, Interception, Dribble,
Dispossessed, Miscontrol, Ball Recovery, Clearance, Block, Shot. "Tackle" is
deliberately absent — it is not a StatsBomb `type`, it is a `duel_type` qualifier
on Duel events, exposed via the duel_type field instead.

Per-event fields: minute/second (match-cumulative, do not reset at half-time),
type, location, end_location (Pass/Carry/Shot only), outcome (semantics vary by
type — see _event_outcome), under_pressure, possession, possession_team,
duel_type (Duel only), is_progressive/distance_gained (Pass/Carry only, via the
imported progressive-map helpers), xt_delta (Pass/Carry only, via the imported xT
grid), pressure_regain (Pressure only, via _pressure_regain).

One JSON file is written per eligible player — not one combined file — because
consumers only ever need one player's data at a time (fetched on selection rather
than loaded and filtered client-side). Whole-match-by-default: main()/
extract_player_events() process every eligible player unless a single player_id is
passed, which restricts output to that one player for fast iteration during
development (re-running the full ~27-player roster on every change is wasteful
when tuning one player's logic).

Public API:
    extract_player_events(match_id, player_id=None) -> pd.DataFrame
    main()

DataFrame columns: player_id, event_id, minute, second, type, location,
    end_location, outcome, under_pressure, possession, possession_team,
    duel_type, is_progressive, xt_delta, distance_gained, pressure_regain

JSON output shape (one file per player):
    {
        "events": [
            { "event_id", "minute", "second", "type", "location", "end_location",
              "outcome", "under_pressure", "possession", "possession_team",
              "duel_type", "is_progressive", "xt_delta", "distance_gained",
              "pressure_regain" }
        ],
        "metadata": {"match_id", "player_id", "display_name", "team",
                     "competition", "season", "match_label", "n_events",
                     "xt_grid_source", "progressive_threshold",
                     "pressure_regain_window_seconds"}
    }
Written to: src/footballd3/sample_data/player_events/{match_id}/{player_id}.json
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .extract_progressive_map import PROGRESSIVE_THRESHOLD, _dist_to_goal, _is_progressive
from .extract_substitutes import get_eligible_players
from .extract_xt import XT_GRID, _map_to_zone
from .utils import clean_nan, end_location, fetch_match_info, pass_outcome, resolve_match

ALLOWED_TYPES: frozenset[str] = frozenset({
    "Pass", "Carry", "Pressure", "Duel", "Interception", "Dribble",
    "Dispossessed", "Miscontrol", "Ball Recovery", "Clearance", "Block", "Shot",
})

PRESSURE_REGAIN_WINDOW_SECONDS: int = 5


def _event_outcome(row: pd.Series) -> str | None:
    """Resolve a human-readable outcome string for one event, or None.

    Semantics vary by event type. Pass uses utils.pass_outcome (None means
    completed). Duel/Interception/Dribble/Shot use their own StatsBomb outcome
    columns. Ball Recovery has no outcome column — StatsBomb flags a failed
    recovery via a separate boolean, mapped here to "Failure". Carry, Clearance,
    Block, Pressure, Dispossessed, and Miscontrol have no StatsBomb outcome field
    at all — the event's mere existence is its own outcome.

    Args:
        row (pd.Series): A single StatsBomb events row.

    Returns:
        str | None: Outcome string, or None when not applicable/completed.
    """
    event_type = str(row.get("type", ""))
    if event_type == "Pass":
        return pass_outcome(row)
    if event_type == "Duel":
        v = row.get("duel_outcome")
        return str(v) if pd.notna(v) else None
    if event_type == "Interception":
        v = row.get("interception_outcome")
        return str(v) if pd.notna(v) else None
    if event_type == "Dribble":
        v = row.get("dribble_outcome")
        return str(v) if pd.notna(v) else None
    if event_type == "Shot":
        v = row.get("shot_outcome")
        return str(v) if pd.notna(v) else None
    if event_type == "Ball Recovery":
        failure = row.get("ball_recovery_recovery_failure")
        return "Failure" if pd.notna(failure) and bool(failure) else None
    return None


def _pressure_regain(
    row: pd.Series,
    all_events: pd.DataFrame,
    window_seconds: int = PRESSURE_REGAIN_WINDOW_SECONDS,
) -> bool:
    """True when possession flips to the presser's team within window_seconds.

    Looks across ALL match events (not just credited event types), since a
    possession change is visible via any event's possession_team field. Elapsed
    time uses minute*60+second (StatsBomb-cumulative, does not reset at
    half-time — unlike the raw timestamp string) and is bounded to the same
    period so the window can never spuriously span the half-time gap.

    Args:
        row (pd.Series): A single Pressure event row.
        all_events (pd.DataFrame): Full match event DataFrame (unfiltered by
            type or player), for possession-change visibility.
        window_seconds (int): Seconds after the pressure event to check for a
            possession flip. Defaults to 5.

    Returns:
        bool: True if possession changed to the pressing player's team within
            the window.
    """
    pressing_team = str(row["team"])
    starting_possession_team = str(row["possession_team"])
    t0 = int(row["minute"]) * 60 + int(row["second"])

    same_period = all_events[all_events["period"] == row["period"]]
    elapsed = same_period["minute"] * 60 + same_period["second"]
    window = same_period[(elapsed >= t0) & (elapsed <= t0 + window_seconds)]

    flipped_to_presser = (window["possession_team"] == pressing_team) & (
        window["possession_team"] != starting_possession_team
    )
    return bool(flipped_to_presser.any())


def extract_player_events(match_id: int, player_id: int | None = None) -> pd.DataFrame:
    """Extract the credited event stream for eligible players in a match.

    Args:
        match_id (int): StatsBomb match ID.
        player_id (int | None): When given, restricts extraction to this one
            eligible player (fast-iteration path). When None (default), extracts
            every eligible (non-GK, played) player in the match.

    Returns:
        pd.DataFrame: One row per credited event with columns: player_id,
            event_id, minute, second, type, location, end_location, outcome,
            under_pressure, possession, possession_team, duel_type,
            is_progressive, xt_delta, distance_gained, pressure_regain.

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

    all_events = sb.events(match_id=match_id)
    target = all_events[
        all_events["player_id"].isin(eligible_ids) & all_events["type"].isin(ALLOWED_TYPES)
    ]

    records: list[dict] = []
    for _, row in target.iterrows():
        loc = row.get("location")
        if not isinstance(loc, list):
            continue

        event_type = str(row["type"])
        end_x, end_y = end_location(row)
        end_loc = [end_x, end_y] if end_x is not None else None

        is_progressive = xt_delta = distance_gained = None
        if event_type in ("Pass", "Carry") and end_loc is not None:
            x0, y0 = float(loc[0]), float(loc[1])
            x1, y1 = end_x, end_y
            is_progressive = _is_progressive(x0, y0, x1, y1)
            distance_gained = round(_dist_to_goal(x0, y0) - _dist_to_goal(x1, y1), 2)
            start_row, start_col = _map_to_zone(x0, y0)
            end_row, end_col = _map_to_zone(x1, y1)
            xt_delta = round(XT_GRID[end_row][end_col] - XT_GRID[start_row][start_col], 8)

        pressure_regain = None
        if event_type == "Pressure":
            pressure_regain = _pressure_regain(row, all_events)

        duel_type = None
        if event_type == "Duel":
            v = row.get("duel_type")
            duel_type = str(v) if pd.notna(v) else None

        under_pressure = row.get("under_pressure")
        under_pressure = bool(under_pressure) if pd.notna(under_pressure) else False

        records.append({
            "player_id":       int(row["player_id"]),
            "event_id":        str(row["id"]),
            "minute":          int(row["minute"]),
            "second":          int(row["second"]),
            "type":            event_type,
            "location":        [float(loc[0]), float(loc[1])],
            "end_location":    end_loc,
            "outcome":         _event_outcome(row),
            "under_pressure":  under_pressure,
            "possession":      int(row["possession"]),
            "possession_team": str(row["possession_team"]),
            "duel_type":       duel_type,
            "is_progressive":  is_progressive,
            "xt_delta":        xt_delta,
            "distance_gained": distance_gained,
            "pressure_regain": pressure_regain,
        })

    return pd.DataFrame(records)


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    player_id: int | None = None,
) -> None:
    """Extract player events for a match and write one JSON file per player.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Per-match output directory; defaults to
            data/euro-2024/{match_id}/. Files are written under a
            player_events/ subdirectory of this path.
        player_id (int | None): When given, writes only this one player's file
            (fast-iteration path). When None (default), writes every eligible
            player's file.

    Output: {out_dir}/player_events/{player_id}.json, one per eligible player.
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    events_dir = out_dir / "player_events"
    events_dir.mkdir(parents=True, exist_ok=True)

    competition, season, match_label = fetch_match_info(match_id)
    eligible = get_eligible_players(match_id)
    roster = eligible.set_index("player_id")[["display_name", "team"]].to_dict(orient="index")

    df = extract_player_events(match_id, player_id=player_id)

    for pid, group in df.groupby("player_id"):
        pid = int(pid)
        meta = roster[pid]
        events = group.drop(columns=["player_id"]).to_dict(orient="records")
        events = [{k: clean_nan(v) for k, v in event.items()} for event in events]

        payload = {
            "events": events,
            "metadata": {
                "match_id":                       match_id,
                "player_id":                       pid,
                "display_name":                    meta["display_name"],
                "team":                             meta["team"],
                "competition":                      competition,
                "season":                           season,
                "match_label":                      match_label,
                "n_events":                         len(events),
                "xt_grid_source":                   "Karun Singh open_xt_12x8_v1",
                "progressive_threshold":            PROGRESSIVE_THRESHOLD,
                "pressure_regain_window_seconds":   PRESSURE_REGAIN_WINDOW_SECONDS,
            },
        }

        out_path = events_dir / f"{pid}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"[{meta['display_name']}] {len(events)} events → {out_path}")


if __name__ == "__main__":
    main()
