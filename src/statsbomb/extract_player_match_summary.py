"""Extract the six-metric stat-card summary for every eligible player in a match.

Feeds playerStatCards (footballd3). Three metrics are simple aggregations over
extract_player_events.py's own output — reused here via extract_player_events()
rather than re-derived, so "progressive", "pressure regain", and shot-xG logic
stay defined in exactly one place:
    - progressive_passes: count of the player's Pass events with is_progressive.
    - pressure_regains: count of the player's Pressure events with pressure_regain.
    - duels_won_pct: % of the player's Duel events with a winning outcome
      ("Won" or "Success In Play" — StatsBomb's two non-losing duel_outcome
      values; "Lost Out"/"Lost In Play" are losses).

Three need server-side derivation over the FULL match event stream (not just
this player's credited events), because they aggregate across other players'
events within a possession/match:
    - xg: sum of the player's own Shot events' shot_statsbomb_xg.
    - xa: sum of shot_statsbomb_xg for every shot whose pass_assisted_shot_id
      traces back to one of the player's passes — StatsBomb's own assist→shot
      link, not a possession-proximity guess.
    - xg_chain: sum of shot_statsbomb_xg across every possession (StatsBomb's
      `possession` id) the player touched the ball in, counted once per
      possession regardless of how many times they touched it.
    - padj_defensive_actions: raw defensive-action count (Pressure, Duel,
      Interception, Block, Ball Recovery, Clearance — the same "Defensive"
      category eventScatter.js already color-codes together), scaled by
      opponent possession share relative to a 50% baseline: a player whose
      team dominated the ball (so the opponent had fewer possessions to
      defend against) gets their raw count scaled up, and vice versa. Team
      possession share is approximated as each team's fraction of the
      match's distinct possession ids — StatsBomb's open data has no
      possession-duration field, so this is a possession-COUNT proxy, not a
      time-weighted one; recorded explicitly in metadata as
      possession_share_method so consumers can judge it themselves.

Public API:
    extract_player_match_summary(match_id, player_id=None) -> dict[int, dict]
    main()

JSON output shape (one file per player):
    {
        "progressive_passes", "pressure_regains", "duels_won_pct",
        "xg", "xa", "xg_chain", "padj_defensive_actions",
        "metadata": {"match_id", "player_id", "display_name", "team",
                     "competition", "season", "match_label",
                     "team_possession_pct", "opponent_possession_pct",
                     "possession_share_method",
                     "defensive_action_types"}
    }
Written to: src/footballd3/sample_data/player_match_summary/{match_id}/{player_id}.json
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .extract_player_events import extract_player_events
from .extract_substitutes import get_eligible_players
from .utils import clean_nan, fetch_match_info, resolve_match

DEFENSIVE_ACTION_TYPES: frozenset[str] = frozenset({
    "Pressure", "Duel", "Interception", "Block", "Ball Recovery", "Clearance",
})
WON_DUEL_OUTCOMES: frozenset[str] = frozenset({"Won", "Success In Play"})
POSSESSION_BASELINE_PCT: float = 50.0


def _progressive_passes(events: pd.DataFrame) -> int:
    """Count of Pass events flagged is_progressive.

    Args:
        events (pd.DataFrame): One player's rows from extract_player_events().

    Returns:
        int: Progressive pass count.
    """
    is_progressive = events.loc[events["type"] == "Pass", "is_progressive"].fillna(False)
    return int(is_progressive.sum())


def _pressure_regains(events: pd.DataFrame) -> int:
    """Count of Pressure events flagged pressure_regain.

    Args:
        events (pd.DataFrame): One player's rows from extract_player_events().

    Returns:
        int: Pressure-regain count.
    """
    pressure_regain = events.loc[events["type"] == "Pressure", "pressure_regain"].fillna(False)
    return int(pressure_regain.sum())


def _duels_won_pct(events: pd.DataFrame) -> float | None:
    """% of Duel events with a winning outcome, or None when the player had no duels.

    Args:
        events (pd.DataFrame): One player's rows from extract_player_events().

    Returns:
        float | None: Rounded percentage (0-100), or None with zero duels.
    """
    duels = events[events["type"] == "Duel"]
    if duels.empty:
        return None
    won = int(duels["outcome"].isin(WON_DUEL_OUTCOMES).sum())
    return round(100 * won / len(duels), 1)


def _xg(events: pd.DataFrame) -> float:
    """Sum of the player's own shot_xg across their Shot events.

    Args:
        events (pd.DataFrame): One player's rows from extract_player_events().

    Returns:
        float: Total xG, 0.0 if the player took no shots.
    """
    shots = events[events["type"] == "Shot"]
    return round(float(shots["shot_xg"].fillna(0.0).sum()), 6)


def _xa(match_events: pd.DataFrame, player_id: int) -> float:
    """Sum of shot_statsbomb_xg for every shot this player's passes assisted.

    Joins via pass_assisted_shot_id (StatsBomb's own pass->shot link) rather
    than possession proximity, so a possession with multiple shots attributes
    xA to the correct one.

    Args:
        match_events (pd.DataFrame): Full raw match event DataFrame (all players).
        player_id (int): The passer's StatsBomb player ID.

    Returns:
        float: Total xA, 0.0 if none of the player's passes assisted a shot.
    """
    assisting_passes = match_events[
        (match_events["player_id"] == player_id)
        & match_events["pass_assisted_shot_id"].notna()
    ]
    if assisting_passes.empty:
        return 0.0

    shots = match_events[match_events["type"] == "Shot"].set_index("id")
    total = 0.0
    for shot_id in assisting_passes["pass_assisted_shot_id"]:
        if shot_id in shots.index:
            xg = shots.loc[shot_id, "shot_statsbomb_xg"]
            total += float(xg) if pd.notna(xg) else 0.0
    return round(total, 6)


def _xg_chain(match_events: pd.DataFrame, player_id: int) -> float:
    """Sum of shot xG across every possession this player touched the ball in.

    Each possession is counted once regardless of how many times the player
    touched it. A possession's xG is the sum of shot_statsbomb_xg for every
    Shot event within it (usually zero or one shot, occasionally more on a
    rebound).

    Args:
        match_events (pd.DataFrame): Full raw match event DataFrame (all players).
        player_id (int): StatsBomb player ID.

    Returns:
        float: Total xG chain value, 0.0 if the player touched no
            possession that produced a shot.
    """
    shots = match_events[match_events["type"] == "Shot"]
    xg_by_possession = shots.groupby("possession")["shot_statsbomb_xg"].sum()

    touched_possessions = set(
        match_events.loc[match_events["player_id"] == player_id, "possession"].unique()
    )
    total = sum(
        float(xg_by_possession.get(poss, 0.0)) for poss in touched_possessions
    )
    return round(total, 6)


def _possession_shares(match_events: pd.DataFrame, team: str) -> tuple[float, float]:
    """Team/opponent possession share, approximated by distinct-possession-id count.

    StatsBomb open data carries no possession-duration field, so this counts
    each `possession` id once (by its possession_team) rather than weighting
    by elapsed time. A team with many short possessions and an opponent with
    few long ones will look more even here than a time-weighted split would.

    Args:
        match_events (pd.DataFrame): Full raw match event DataFrame.
        team (str): The player's team name.

    Returns:
        tuple[float, float]: (team_possession_pct, opponent_possession_pct),
            each 0-100, summing to 100.
    """
    by_possession_team = (
        match_events.drop_duplicates("possession")["possession_team"].value_counts()
    )
    total = int(by_possession_team.sum())
    team_count = int(by_possession_team.get(team, 0))
    team_pct = round(100 * team_count / total, 2) if total else 0.0
    return team_pct, round(100 - team_pct, 2)


def _padj_defensive_actions(events: pd.DataFrame, opponent_possession_pct: float) -> float:
    """Possession-adjusted defensive-action count.

    raw_count / (opponent_possession_pct / 50) — a player facing a
    below-50%-possession opponent (i.e. their own team dominated the ball,
    so there were fewer defensive opportunities) gets their raw count scaled
    up, and vice versa. opponent_possession_pct is clamped to a 1% floor to
    avoid a divide-by-near-zero blowup in extreme matches.

    Args:
        events (pd.DataFrame): One player's rows from extract_player_events().
        opponent_possession_pct (float): The opposing team's possession share (0-100).

    Returns:
        float: Possession-adjusted defensive-action count, rounded to 2 places.
    """
    raw_count = int(events["type"].isin(DEFENSIVE_ACTION_TYPES).sum())
    floor_pct = max(opponent_possession_pct, 1.0)
    return round(raw_count / (floor_pct / POSSESSION_BASELINE_PCT), 2)


def extract_player_match_summary(
    match_id: int,
    player_id: int | None = None,
) -> dict[int, dict]:
    """Compute the six-metric stat-card summary for eligible players.

    Args:
        match_id (int): StatsBomb match ID.
        player_id (int | None): When given, restricts extraction to this one
            eligible player (fast-iteration path). When None (default), extracts
            every eligible (non-GK, played) player in the match.

    Returns:
        dict[int, dict]: Maps player_id to
            {"progressive_passes", "pressure_regains", "duels_won_pct", "xg",
             "xa", "xg_chain", "padj_defensive_actions",
             "team_possession_pct", "opponent_possession_pct"}.

    Raises:
        ValueError: If player_id is given but is not an eligible player in
            this match.
    """
    eligible = get_eligible_players(match_id)
    eligible_ids = set(eligible["player_id"])
    team_by_player = eligible.set_index("player_id")["team"].to_dict()

    if player_id is not None:
        if player_id not in eligible_ids:
            raise ValueError(
                f"player_id {player_id} is not an eligible (non-GK, played) "
                f"player in match {match_id}"
            )
        eligible_ids = {player_id}

    match_events = sb.events(match_id=match_id)

    result: dict[int, dict] = {}
    for pid in eligible_ids:
        player_events = extract_player_events(match_id, player_id=pid)
        team = team_by_player[pid]
        team_pct, opponent_pct = _possession_shares(match_events, team)

        result[pid] = {
            "progressive_passes":      _progressive_passes(player_events),
            "pressure_regains":        _pressure_regains(player_events),
            "duels_won_pct":           _duels_won_pct(player_events),
            "xg":                      _xg(player_events),
            "xa":                      _xa(match_events, pid),
            "xg_chain":                _xg_chain(match_events, pid),
            "padj_defensive_actions":  _padj_defensive_actions(player_events, opponent_pct),
            "team_possession_pct":     team_pct,
            "opponent_possession_pct": opponent_pct,
        }

    return result


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    player_id: int | None = None,
) -> None:
    """Extract player match summaries and write one JSON file per player.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Per-match output directory; defaults to
            data/euro-2024/{match_id}/. Files are written under a
            player_match_summary/ subdirectory of this path.
        player_id (int | None): When given, writes only this one player's file
            (fast-iteration path). When None (default), writes every eligible
            player's file.

    Output: {out_dir}/player_match_summary/{player_id}.json, one per eligible player.
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    summary_dir = out_dir / "player_match_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    competition, season, match_label = fetch_match_info(match_id)
    eligible = get_eligible_players(match_id)
    roster = eligible.set_index("player_id")[["display_name", "team"]].to_dict(orient="index")

    by_player = extract_player_match_summary(match_id, player_id=player_id)

    for pid, metrics in by_player.items():
        meta = roster[pid]
        metrics = {k: clean_nan(v) for k, v in metrics.items()}

        payload = {
            **metrics,
            "metadata": {
                "match_id":                match_id,
                "player_id":               pid,
                "display_name":            meta["display_name"],
                "team":                    meta["team"],
                "competition":             competition,
                "season":                  season,
                "match_label":             match_label,
                "possession_share_method": "distinct_possession_id_count",
                "defensive_action_types":  sorted(DEFENSIVE_ACTION_TYPES),
            },
        }

        out_path = summary_dir / f"{pid}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"[{meta['display_name']}] xg={metrics['xg']} xa={metrics['xa']} → {out_path}")


if __name__ == "__main__":
    main()
