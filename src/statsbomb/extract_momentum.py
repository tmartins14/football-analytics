"""Transform xt_actions_{match_id}.json into a per-minute match momentum curve.

This is a thin windowing layer on top of the xT layer — it does NOT recompute xT.
It reads the already-computed per-action xT deltas (from extract_xt.py) and aggregates
them into a match momentum narrative: home attacking threat minus away attacking threat
per minute, smoothed with a recency-weighted exponential decay window.

CONSTRUCTION (Opta/Bundesliga-style):
1. Per minute, per team: raw_threat = max(0, max(xt_delta)) over that team's actions
   in that minute. MAX aggregation captures peak danger per minute — not possession
   volume. Negative deltas (ball moved away from goal) are clipped to zero, so a team
   that only moved the ball backward in a given minute contributes 0, not negative.
2. Apply exponential decay window (default: window=3 min, alpha=0.6) across the
   raw-threat series for each team. The current minute is weighted 1.0; each prior
   minute is weighted alpha^i. Weights are normalized so the smoothed value stays on
   the same scale as the raw values.
3. Momentum per minute = home_smoothed_threat - away_smoothed_threat.
   Values > 0 indicate home team generating more attacking threat; < 0 indicate away.
4. A secondary series at double the window length (default: 6 min) is emitted alongside
   the primary so D3 can overlay both curves and show window-dependence.

CAVEATS (propagated verbatim to the README):
(a) This is ATTACKING-THREAT momentum built from xT. It sees the team on the ball and
    does NOT capture defensive resistance or off-ball pressure. A team absorbing
    sustained pressure reads as "no momentum" even when executing well. This measures
    threat GENERATED, not "who is on top."
(b) The window length is a CONFIG PARAMETER that shapes the curve. A short window
    produces a jumpy chart; a long window produces a smooth narrative arc. The story
    is window-dependent, not a fact.
(c) xT provenance: Karun Singh's open_xt_12x8_v1 grid, trained on his own match
    corpus — NOT fitted to Euro 2024. Values are directionally meaningful but not
    calibrated to this dataset.

Public API:
    extract_momentum(match_id, competition, season, match_label, ...) -> dict
    main()

Output written to src/footballd3/sample_data/momentum_{match_id}.json.

momentum_{match_id}.json shape:
    {
        "home_team": str,
        "away_team": str,
        "minutes": [
            {"minute": int, "home_threat": float, "away_threat": float, "momentum": float}
        ],
        "secondary_minutes": [...],  # same shape, secondary window length
        "goals": [
            {"minute": int, "team": str, "player": str, "is_own_goal": bool}
        ],
        "red_cards": [
            {"minute": int, "team": str, "player": str}
        ],
        "params": {
            "window_minutes": int, "weighting": "exponential",
            "decay_alpha": float, "aggregation": "max",
            "secondary_window_minutes": int
        },
        "metadata": {
            "match_id": int, "competition": str, "season": str,
            "match_label": str, "grid_source": str
        }
    }

Consumed fields from xt_actions: team, minute, xt_delta.
Unused fields present in xt_actions but not read here:
    display_name, second, x0, y0, x1, y1, start_zone, end_zone, action_type.
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from extract_xt import resolve_euro_2024_match

_SAMPLE_DATA_DIR = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"

_WINDOW_MINUTES:              int   = 3
_DECAY_ALPHA:                 float = 0.6
_SECONDARY_WINDOW_MULTIPLIER: int   = 2


def _resolve_teams(match_id: int, competition_name: str, season_name: str) -> tuple[str, str]:
    """Look up the home and away team names for a match from the StatsBomb API.

    Args:
        match_id (int): StatsBomb match ID.
        competition_name (str): Competition name (substring match, case-insensitive).
        season_name (str): Season name for exact filtering.

    Returns:
        tuple[str, str]: (home_team, away_team) as reported by StatsBomb.

    Raises:
        ValueError: If the competition or the match cannot be located via the API.
    """
    comps = sb.competitions()
    comp_rows = comps[
        comps["competition_name"].str.contains(competition_name, case=False)
        & (comps["season_name"] == season_name)
    ]
    if comp_rows.empty:
        raise ValueError(
            f"Competition matching '{competition_name}' / season '{season_name}' "
            "not found in sb.competitions()"
        )

    competition_id = int(comp_rows["competition_id"].iloc[0])
    season_id      = int(comp_rows["season_id"].iloc[0])
    matches        = sb.matches(competition_id=competition_id, season_id=season_id)
    match_row      = matches[matches["match_id"] == match_id]

    if match_row.empty:
        raise ValueError(
            f"match_id {match_id} not found in {competition_name} {season_name} matches"
        )

    row = match_row.iloc[0]
    return str(row["home_team"]), str(row["away_team"])


def _build_nickname_lookup(match_id: int) -> dict[int, str]:
    """Build a player_id -> display_name mapping from sb.lineups() for all teams.

    display_name coalesces player_nickname (when non-empty) with player_name.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict[int, str]: Maps integer player_id to resolved display name.
    """
    lineups = sb.lineups(match_id=match_id)
    lookup: dict[int, str] = {}
    for team_df in lineups.values():
        for _, row in team_df.iterrows():
            nick = row.get("player_nickname")
            name = row["player_name"]
            display = nick if (pd.notna(nick) and nick) else name
            lookup[int(row["player_id"])] = display
    return lookup


def _extract_goals_from_events(
    events: pd.DataFrame, nicknames: dict[int, str]
) -> list[dict]:
    """Extract all goals from a match events DataFrame.

    Captures both regular goals (shot_outcome == "Goal") and own goals (shot_outcome
    contains "Own Goal"). Sorted by minute ascending.

    Args:
        events (pd.DataFrame): Full match events from sb.events().
        nicknames (dict[int, str]): player_id -> display_name mapping.

    Returns:
        list[dict]: One entry per goal: minute, team, player (display_name), is_own_goal.
    """
    shots = events[events["type"] == "Shot"]
    goal_mask = shots["shot_outcome"].fillna("").str.contains("Goal", case=False)
    goals_df = shots[goal_mask]

    result: list[dict] = []
    for _, row in goals_df.iterrows():
        pid          = row.get("player_id")
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


def _extract_red_cards_from_events(
    events: pd.DataFrame, nicknames: dict[int, str]
) -> list[dict]:
    """Extract all red card events (direct red, second yellow, or violent conduct) from a match.

    StatsBomb encodes red cards via two routes:
    - "Bad Behaviour" events (bad_behaviour_card column): direct reds for violent/abusive conduct.
    - "Foul Committed" events (foul_committed_card column): red or second yellow from a foul.

    Either column may be absent from the DataFrame when no such events occur in the match.

    Args:
        events (pd.DataFrame): Full match events from sb.events().
        nicknames (dict[int, str]): player_id -> display_name mapping.

    Returns:
        list[dict]: One entry per red card: minute, team, player (display_name).
    """
    red_rows: list[pd.Series] = []

    # Direct reds via Bad Behaviour events (column absent when no such events exist).
    if "bad_behaviour_card" in events.columns:
        bb = events[events["type"] == "Bad Behaviour"]
        bb_reds = bb[bb["bad_behaviour_card"].fillna("").str.contains("Red", case=False)]
        red_rows.extend(row for _, row in bb_reds.iterrows())

    # Red or second-yellow via Foul Committed events.
    if "foul_committed_card" in events.columns:
        fc = events[events["type"] == "Foul Committed"]
        fc_reds = fc[fc["foul_committed_card"].fillna("").str.contains("Red|Second", case=False)]
        red_rows.extend(row for _, row in fc_reds.iterrows())

    result: list[dict] = []
    for row in red_rows:
        pid          = row.get("player_id")
        display_name = (
            nicknames.get(int(pid), str(row.get("player", "")))
            if pd.notna(pid) else str(row.get("player", ""))
        )
        result.append({
            "minute": int(row["minute"]),
            "team":   str(row["team"]),
            "player": display_name,
        })

    return sorted(result, key=lambda r: r["minute"])


def _compute_raw_threats(
    actions: list[dict],
    home_team: str,
    away_team: str,
    max_minute: int,
) -> tuple[list[float], list[float]]:
    """Compute per-minute raw threat for each team using MAX aggregation.

    For each minute 0..max_minute, raw_threat = max(0, max(xt_delta)) over all that
    team's actions in that minute. A minute with no actions yields 0. Negative deltas
    (ball moved away from goal) are clipped so that "no forward threat" maps to 0.

    Args:
        actions (list[dict]): xt_actions records; only team, minute, xt_delta are read.
        home_team (str): Home team name.
        away_team (str): Away team name.
        max_minute (int): Upper bound; series length = max_minute + 1.

    Returns:
        tuple[list[float], list[float]]: (home_raw, away_raw), both of length
            max_minute + 1. Index i = minute i (index 0 is a zero sentinel).
    """
    home_max: dict[int, float] = {}
    away_max: dict[int, float] = {}

    for action in actions:
        m     = int(action["minute"])
        delta = float(action["xt_delta"])
        if action["team"] == home_team:
            home_max[m] = max(home_max.get(m, float("-inf")), delta)
        elif action["team"] == away_team:
            away_max[m] = max(away_max.get(m, float("-inf")), delta)

    home_raw = [0.0] * (max_minute + 1)
    away_raw = [0.0] * (max_minute + 1)
    for m in range(1, max_minute + 1):
        home_raw[m] = max(0.0, home_max.get(m, 0.0))
        away_raw[m] = max(0.0, away_max.get(m, 0.0))

    return home_raw, away_raw


def _apply_exp_window(raw: list[float], window: int, alpha: float) -> list[float]:
    """Apply an exponential decay rolling window to a per-minute series.

    smoothed[t] = sum(alpha^i * raw[t-i] for i in 0..w-1) / sum(alpha^i for i in 0..w-1)

    Early minutes use a partial window (only available history); weights are
    re-normalized so early-match values stay on the same scale as late-match values.
    Index 0 is always 0 (unused sentinel, consistent with per-minute indexing).

    Args:
        raw (list[float]): Per-minute values; raw[0] unused, raw[i] = minute i.
        window (int): Number of minutes to include in the smoothing window.
        alpha (float): Exponential decay factor in (0, 1). Smaller = stronger recency
            bias (earlier minutes contribute less). Default 0.6 gives weights
            [1.0, 0.6, 0.36] (normalized ~[51%, 31%, 18%]) for a 3-minute window.

    Returns:
        list[float]: Smoothed series of the same length as raw.
    """
    weights = [alpha ** i for i in range(window)]
    smoothed = [0.0] * len(raw)
    for t in range(1, len(raw)):
        available = min(t, window)
        w_slice   = weights[:available]
        total_w   = sum(w_slice)
        smoothed[t] = sum(w_slice[i] * raw[t - i] for i in range(available)) / total_w
    return smoothed


def _build_minute_series(
    home_smooth: list[float],
    away_smooth: list[float],
    max_minute: int,
) -> list[dict]:
    """Zip smoothed home and away threats into the output minute records.

    Args:
        home_smooth (list[float]): Smoothed home threat, indexed by minute.
        away_smooth (list[float]): Smoothed away threat, indexed by minute.
        max_minute (int): Last minute to include.

    Returns:
        list[dict]: One record per minute from 1..max_minute with
            minute, home_threat, away_threat, momentum keys.
    """
    return [
        {
            "minute":      m,
            "home_threat": round(home_smooth[m], 6),
            "away_threat": round(away_smooth[m], 6),
            "momentum":    round(home_smooth[m] - away_smooth[m], 6),
        }
        for m in range(1, max_minute + 1)
    ]


def extract_momentum(
    match_id: int,
    competition: str,
    season: str,
    match_label: str,
    window_minutes: int   = _WINDOW_MINUTES,
    decay_alpha:    float = _DECAY_ALPHA,
    aggregation:    str   = "max",
) -> dict:
    """Compute a per-minute momentum curve from a pre-extracted xt_actions file.

    Reads xt_actions_{match_id}.json from sample_data — does NOT recompute xT values.
    Applies MAX aggregation (peak danger per minute, negatives clipped to 0) and an
    exponential decay window. Emits both a primary series (window_minutes) and a
    secondary series (window_minutes × 2) for D3 overlay comparison.

    Consumed fields from xt_actions: team, minute, xt_delta.
    Unused fields present in xt_actions (but not read here):
        display_name, second, x0, y0, x1, y1, start_zone, end_zone, action_type.

    Args:
        match_id (int): StatsBomb match ID. Locates xt_actions_{match_id}.json.
        competition (str): Competition name; forwarded to metadata and team lookup.
        season (str): Season name; forwarded to metadata and team lookup.
        match_label (str): "Home vs Away" string; forwarded to metadata.
        window_minutes (int): Primary smoothing window in minutes. Default: 3.
            Short windows (2-3 min) are reactive; long windows (6+ min) are smooth.
        decay_alpha (float): Exponential decay factor in (0, 1). Default: 0.6.
            At 0.6 with a 3-minute window: weights ≈ [51%, 31%, 18%] (current, -1, -2).
        aggregation (str): Aggregation method label stored in params. Currently only
            "max" is implemented; included for downstream provenance.

    Returns:
        dict: Full momentum JSON contract (see module docstring for schema).

    Raises:
        FileNotFoundError: If xt_actions_{match_id}.json does not exist.
        ValueError: If the actions list is empty, or home/away cannot be resolved.
    """
    actions_path = _SAMPLE_DATA_DIR / f"xt_actions_{match_id}.json"
    if not actions_path.exists():
        raise FileNotFoundError(
            f"xt_actions_{match_id}.json not found in sample_data — "
            "run extract_xt.py first."
        )

    with open(actions_path) as f:
        xt_data = json.load(f)

    actions: list[dict] = xt_data["actions"]
    grid_source: str    = xt_data["metadata"].get("grid_source", "Karun Singh open_xt_12x8_v1")

    if not actions:
        raise ValueError(f"No actions found in xt_actions_{match_id}.json")

    home_team, away_team = _resolve_teams(match_id, competition, season)
    nicknames            = _build_nickname_lookup(match_id)
    events               = sb.events(match_id=match_id)

    max_minute = max(int(a["minute"]) for a in actions)
    home_raw, away_raw = _compute_raw_threats(actions, home_team, away_team, max_minute)

    # Primary window.
    home_sm = _apply_exp_window(home_raw, window_minutes, decay_alpha)
    away_sm = _apply_exp_window(away_raw, window_minutes, decay_alpha)
    minutes = _build_minute_series(home_sm, away_sm, max_minute)

    # Secondary window (double the primary for overlay comparison).
    secondary_window = window_minutes * _SECONDARY_WINDOW_MULTIPLIER
    home_sm2 = _apply_exp_window(home_raw, secondary_window, decay_alpha)
    away_sm2 = _apply_exp_window(away_raw, secondary_window, decay_alpha)
    secondary_minutes = _build_minute_series(home_sm2, away_sm2, max_minute)

    goals     = _extract_goals_from_events(events, nicknames)
    red_cards = _extract_red_cards_from_events(events, nicknames)

    return {
        "home_team":         home_team,
        "away_team":         away_team,
        "minutes":           minutes,
        "secondary_minutes": secondary_minutes,
        "goals":             goals,
        "red_cards":         red_cards,
        "params": {
            "window_minutes":           window_minutes,
            "weighting":                "exponential",
            "decay_alpha":              decay_alpha,
            "aggregation":              aggregation,
            "secondary_window_minutes": secondary_window,
        },
        "metadata": {
            "match_id":    match_id,
            "competition": competition,
            "season":      season,
            "match_label": match_label,
            "grid_source": grid_source,
        },
    }


def main() -> None:
    """Resolve the Euro 2024 Final, compute momentum, and write the JSON contract.

    Writes:
        src/footballd3/sample_data/momentum_{match_id}.json
    """
    match_id, competition, season, match_label = resolve_euro_2024_match()

    data = extract_momentum(match_id, competition, season, match_label)

    _SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _SAMPLE_DATA_DIR / f"momentum_{match_id}.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    n_minutes = len(data["minutes"])
    n_goals   = len(data["goals"])
    n_reds    = len(data["red_cards"])
    home      = data["home_team"]
    away      = data["away_team"]
    params    = data["params"]

    print(f"Momentum: {home} vs {away}")
    print(f"  Minutes:    {n_minutes}")
    print(f"  Goals:      {n_goals}   Red cards: {n_reds}")
    print(f"  Window:     {params['window_minutes']} min "
          f"(α={params['decay_alpha']}, secondary: {params['secondary_window_minutes']} min)")
    print(f"  → {out_path}")


if __name__ == "__main__":
    main()
