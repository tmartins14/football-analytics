"""Transform shots_{match_id} data into a per-team cumulative xG race series.

This is a running-total layer on top of the shots layer — it does NOT recompute
xG or re-filter events. It reads extract_shots.py's already-filtered shot records
and aggregates them into a step function per team: each shot bumps that team's
running total by its xg value at that shot's minute.

CONSTRUCTION:
1. Reuse extract_shots(match_id) for shot-level records (xg, minute, team,
   outcome, display_name, is_goal). Own goals are already excluded upstream
   (no StatsBomb xG value for them).
2. Preserve extract_shots()'s existing chronological row order — same-minute
   shots are NOT re-sorted by any secondary key, since that order already
   reflects StatsBomb's true event sequence.
3. Walk the shots in order, maintaining a running total per team; emit one
   point per shot with that team's cumulative_xg after this shot.
4. final_minute = max(minute) across the FULL match event stream (sb.events()),
   not the last shot's minute — the last shot is frequently several minutes
   before the actual final whistle (e.g. stoppage time).
5. goals[] (for the goal-marker overlay) is pulled independently from the full
   event stream, own goals included, since own goals never appear in the
   shots-derived points[] series.

CAVEATS:
(a) xG models are provider-specific and not universally calibrated. StatsBomb's
    shot_statsbomb_xg is StatsBomb's own model; absolute values should not be
    compared to Opta/other providers' xG on the same shots.
(b) xG measures shot quality (likelihood a shot like this scores, given
    historical shots from similar positions/situations), not finishing
    quality. A team leading heavily on cumulative xG can still lose.
(c) Cumulative xG is NOT a prediction of the final score — it is a running
    sum of independent shot-quality estimates, not a simulation.
(d) Own goals contribute ZERO to either team's cumulative_xg (StatsBomb
    assigns no xG to them) but DO appear as goal markers, attributed to the
    shooting team's own line — a goal chip can therefore appear "on" a curve
    at a point where that curve did not visibly rise.

extract_shots.py must be importable to produce the underlying shot records
(no on-disk intermediate file is required, unlike the xT -> momentum chain).

Public API:
    extract_cumulative_xg(match_id) -> pd.DataFrame
    main()

DataFrame columns: minute, team, display_name, xg, cumulative_xg, outcome, is_goal

JSON output shape (cumulative_xg_{match_id}.json):
    {
        "home_team": str, "away_team": str,
        "points": [{"minute", "team", "display_name", "xg", "cumulative_xg", "outcome", "is_goal"}],
        "final_minute": int,
        "final_home_xg": float, "final_away_xg": float,
        "goals": [{"minute", "team", "player", "is_own_goal"}],
        "metadata": {"match_id", "competition", "season", "match_label"}
    }
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .extract_shots import extract_shots
from .utils import build_nickname_lookup, fetch_match_info, resolve_match


def _resolve_teams(match_id: int) -> tuple[str, str]:
    """Look up the home and away team names for a match from the StatsBomb API.

    Duplicated locally from the equivalent private helper in extract_momentum.py —
    no shared utility for this exists yet in utils.py (per the "extract, don't
    speculate" convention, it should only be pulled out once this pattern repeats
    a third time).

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        tuple[str, str]: (home_team, away_team).

    Raises:
        ValueError: If the match cannot be located via fetch_match_info.
    """
    competition, season, _ = fetch_match_info(match_id)
    if not competition:
        raise ValueError(f"match_id {match_id} not found in sb.competitions()")

    comps = sb.competitions()
    for _, comp_row in comps.iterrows():
        if str(comp_row["season_name"]) == season:
            try:
                matches = sb.matches(
                    competition_id=int(comp_row["competition_id"]),
                    season_id=int(comp_row["season_id"]),
                )
            except Exception:  # noqa: BLE001
                continue
            match_rows = matches[matches["match_id"] == match_id]
            if not match_rows.empty:
                row = match_rows.iloc[0]
                return str(row["home_team"]), str(row["away_team"])
    raise ValueError(f"match_id {match_id} not found after season scan")


def _final_minute(events: pd.DataFrame) -> int:
    """Return the true match-ending minute from the full event stream.

    Uses max(events["minute"]) rather than the last shot's minute so the
    cumulative-xG line always extends to full time (including stoppage), even
    when the final shot of the match happened several minutes before the
    actual final whistle (StatsBomb's "Half End" event carries this).

    Args:
        events (pd.DataFrame): Full match events from sb.events().

    Returns:
        int: The maximum minute value across all events in the match.
    """
    return int(events["minute"].max())


def _extract_goals_from_events(
    events: pd.DataFrame, nicknames: dict[int, str]
) -> list[dict]:
    """Extract all goals (including own goals) for the goal-marker overlay.

    Duplicated locally from the equivalent private helper in extract_momentum.py
    (same shape: minute, team, player, is_own_goal) — own goals carry no
    StatsBomb xG and are therefore absent from extract_shots()'s output, but
    they must still appear as actual-goal markers for viewers to compare
    expected vs. real scoring.

    Args:
        events (pd.DataFrame): Full match events from sb.events().
        nicknames (dict[int, str]): player_id -> display_name mapping.

    Returns:
        list[dict]: One entry per goal, sorted by minute ascending.
    """
    shots = events[events["type"] == "Shot"]
    goal_mask = shots["shot_outcome"].fillna("").str.contains("Goal", case=False)
    goals_df = shots[goal_mask]

    result: list[dict] = []
    for _, row in goals_df.iterrows():
        pid = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid) else str(row.get("player", ""))
        )
        is_own_goal = "own" in str(row.get("shot_outcome", "")).lower()
        result.append({
            "minute":      int(row["minute"]),
            "team":        str(row["team"]),
            "player":      display_name,
            "is_own_goal": is_own_goal,
        })
    return sorted(result, key=lambda g: g["minute"])


def _compute_cumulative_points(
    shots: pd.DataFrame, home_team: str, away_team: str
) -> list[dict]:
    """Compute a chronologically-ordered, per-team running total of xG.

    Assumes `shots` is already in true chronological order (the row order
    extract_shots() returns, itself inherited from StatsBomb's event `index`
    via sb.events()) — same-minute shots are NOT re-sorted by any other key,
    which would silently scramble StatsBomb's own tie-break.

    Args:
        shots (pd.DataFrame): Output of extract_shots(match_id).
        home_team (str): Home team name.
        away_team (str): Away team name.

    Returns:
        list[dict]: One row per shot: minute, team, display_name, xg,
            cumulative_xg (running total for that shot's team, rounded to
            6 decimals), outcome, is_goal.
    """
    totals: dict[str, float] = {home_team: 0.0, away_team: 0.0}
    points: list[dict] = []
    for _, row in shots.iterrows():
        team = row["team"]
        totals[team] = totals.get(team, 0.0) + float(row["xg"])
        points.append({
            "minute":        int(row["minute"]),
            "team":          team,
            "display_name":  row["display_name"],
            "xg":            float(row["xg"]),
            "cumulative_xg": round(totals[team], 6),
            "outcome":       row["outcome"],
            "is_goal":       bool(row["is_goal"]),
        })
    return points


def extract_cumulative_xg(match_id: int) -> pd.DataFrame:
    """Compute a running per-team cumulative xG series from match shots.

    Reuses extract_shots(match_id) for the shot-level series — does NOT
    re-query sb.events() and re-filter type == "Shot". Separately queries
    sb.events() once for the match-ending minute and the goal-marker overlay
    (own goals included), since neither is present in extract_shots()'s
    xG-filtered output.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pd.DataFrame: One row per shot (see _compute_cumulative_points).
        Also sets on df.attrs:
            home_team, away_team (str).
            final_minute (int): True match-ending minute (see _final_minute).
            final_home_xg, final_away_xg (float): Rounded final totals.
            goals (list[dict]): See _extract_goals_from_events.
            competition, season, match_label (str).

    Raises:
        ValueError: If extract_shots(match_id) returns no shots.
    """
    shots = extract_shots(match_id)
    if shots.empty:
        raise ValueError(f"extract_shots(match_id={match_id}) returned no shots")

    home_team, away_team = _resolve_teams(match_id)
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)
    competition, season, match_label = fetch_match_info(match_id)

    points = _compute_cumulative_points(shots, home_team, away_team)
    df = pd.DataFrame(points)

    home_rows = df[df["team"] == home_team]
    away_rows = df[df["team"] == away_team]
    final_home_xg = float(home_rows["cumulative_xg"].max()) if not home_rows.empty else 0.0
    final_away_xg = float(away_rows["cumulative_xg"].max()) if not away_rows.empty else 0.0

    df.attrs["home_team"]     = home_team
    df.attrs["away_team"]     = away_team
    df.attrs["final_minute"]  = _final_minute(events)
    df.attrs["final_home_xg"] = round(final_home_xg, 6)
    df.attrs["final_away_xg"] = round(final_away_xg, 6)
    df.attrs["goals"]         = _extract_goals_from_events(events, nicknames)
    df.attrs["competition"]   = competition
    df.attrs["season"]        = season
    df.attrs["match_label"]   = match_label
    return df


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Compute cumulative xG for a match and write the JSON contract.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Writes:
        {out_dir}/cumulative_xg.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    df = extract_cumulative_xg(match_id)

    payload = {
        "home_team":     df.attrs["home_team"],
        "away_team":     df.attrs["away_team"],
        "points":        df.to_dict(orient="records"),
        "final_minute":  df.attrs["final_minute"],
        "final_home_xg": df.attrs["final_home_xg"],
        "final_away_xg": df.attrs["final_away_xg"],
        "goals":         df.attrs["goals"],
        "metadata": {
            "match_id":    match_id,
            "competition": df.attrs["competition"],
            "season":      df.attrs["season"],
            "match_label": df.attrs["match_label"],
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cumulative_xg.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    home = df.attrs["home_team"]
    away = df.attrs["away_team"]
    print(f"Cumulative xG: {home} vs {away}")
    print(f"  Shots:     {len(df)}   Goals: {len(df.attrs['goals'])}")
    print(f"  Final:     {home} {df.attrs['final_home_xg']:.2f}  —  {away} {df.attrs['final_away_xg']:.2f}")
    print(f"  Full time: minute {df.attrs['final_minute']}")
    print(f"  → {out_path}")


if __name__ == "__main__":
    main()
