"""Transform xt_actions_{match_id}.json into a per-minute match momentum curve.

This is a windowing layer on top of the xT layer — it does NOT recompute xT. It
reads the already-computed per-action xT deltas (from extract_xt.py) and aggregates
them into a match momentum narrative: home attacking threat minus away attacking
threat per minute, smoothed with an exponential decay window.

CONSTRUCTION (Opta/Bundesliga-style):
1. Per minute, per team: raw_threat = max(0, max(xt_delta)) — peak danger per minute.
2. Apply exponential decay window (default: 3 min, alpha=0.6). Weights normalized.
3. Momentum = home_smoothed_threat - away_smoothed_threat.
4. A secondary series at double the window (default: 6 min) is emitted alongside.

CAVEATS:
(a) ATTACKING-THREAT momentum only. Does not capture defensive resistance or off-ball
    pressure. Measures threat GENERATED, not "who is on top."
(b) The window length is a CONFIG PARAMETER that shapes the curve.
(c) xT provenance: Karun Singh's open_xt_12x8_v1 — NOT fitted to Euro 2024.

extract_xt.py must be run before extract_momentum.py to produce xt_actions_{match_id}.json.

Public API:
    extract_momentum(match_id, window_minutes, decay_alpha, aggregation) -> pd.DataFrame
    main()

DataFrame columns: minute, home_threat, away_threat, momentum
    (primary window only; secondary series available via df.attrs["secondary_minutes"])

JSON output shape (momentum_{match_id}.json):
    {
        "home_team": str, "away_team": str,
        "minutes":           [{"minute", "home_threat", "away_threat", "momentum"}],
        "secondary_minutes": [...],
        "goals":     [{"minute", "team", "player", "is_own_goal"}],
        "red_cards": [{"minute", "team", "player"}],
        "params": {"window_minutes", "weighting", "decay_alpha", "aggregation",
                   "secondary_window_minutes"},
        "metadata": {"match_id", "competition", "season", "match_label", "grid_source"}
    }
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import build_nickname_lookup, fetch_match_info, resolve_match

_SAMPLE_DATA_DIR = Path(__file__).parents[2] / "libs" / "footballd3" / "sample_data"

_WINDOW_MINUTES:              int   = 3
_DECAY_ALPHA:                 float = 0.6
_SECONDARY_WINDOW_MULTIPLIER: int   = 2


def _resolve_teams(match_id: int) -> tuple[str, str]:
    """Look up the home and away team names for a match from the StatsBomb API.

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
    # Extract competition_name and season_name from the display string.
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


def _extract_goals_from_events(
    events: pd.DataFrame, nicknames: dict[int, str]
) -> list[dict]:
    """Extract all goals from a match events DataFrame.

    Captures both regular goals (shot_outcome == "Goal") and own goals
    (shot_outcome contains "Own Goal"). Sorted by minute ascending.

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


def _extract_red_cards_from_events(
    events: pd.DataFrame, nicknames: dict[int, str]
) -> list[dict]:
    """Extract all red card events from a match.

    StatsBomb encodes red cards via Bad Behaviour events (bad_behaviour_card column)
    and Foul Committed events (foul_committed_card column). Either column may be absent.

    Args:
        events (pd.DataFrame): Full match events from sb.events().
        nicknames (dict[int, str]): player_id -> display_name mapping.

    Returns:
        list[dict]: One entry per red card: minute, team, player (display_name).
    """
    red_rows: list[pd.Series] = []

    if "bad_behaviour_card" in events.columns:
        bb = events[events["type"] == "Bad Behaviour"]
        bb_reds = bb[bb["bad_behaviour_card"].fillna("").str.contains("Red", case=False)]
        red_rows.extend(row for _, row in bb_reds.iterrows())

    if "foul_committed_card" in events.columns:
        fc = events[events["type"] == "Foul Committed"]
        fc_reds = fc[fc["foul_committed_card"].fillna("").str.contains("Red|Second", case=False)]
        red_rows.extend(row for _, row in fc_reds.iterrows())

    result: list[dict] = []
    for row in red_rows:
        pid = row.get("player_id")
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

    For each minute 0..max_minute, raw_threat = max(0, max(xt_delta)) over all
    that team's actions in that minute. Negative deltas are clipped to 0.

    Args:
        actions (list[dict]): xt_actions records; only team, minute, xt_delta are read.
        home_team (str): Home team name.
        away_team (str): Away team name.
        max_minute (int): Upper bound; series length = max_minute + 1.

    Returns:
        tuple[list[float], list[float]]: (home_raw, away_raw), each length max_minute + 1.
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
    Early minutes use a partial window with re-normalized weights.

    Args:
        raw (list[float]): Per-minute values; raw[0] unused sentinel.
        window (int): Number of minutes in the smoothing window.
        alpha (float): Exponential decay factor in (0, 1).

    Returns:
        list[float]: Smoothed series of the same length as raw.
    """
    weights = [alpha ** i for i in range(window)]
    smoothed = [0.0] * len(raw)
    for t in range(1, len(raw)):
        available = min(t, window)
        w_slice = weights[:available]
        total_w = sum(w_slice)
        smoothed[t] = sum(w_slice[i] * raw[t - i] for i in range(available)) / total_w
    return smoothed


def extract_momentum(
    match_id: int,
    window_minutes: int       = _WINDOW_MINUTES,
    decay_alpha:    float     = _DECAY_ALPHA,
    aggregation:    str       = "max",
    data_dir:       Path | None = None,
) -> pd.DataFrame:
    """Compute a per-minute momentum curve from a pre-extracted xt_actions file.

    Reads xt_actions.json (or xt_actions_{match_id}.json for legacy paths) from
    data_dir — does NOT recompute xT. Run extract_xt.py first to produce this file.

    Applies MAX aggregation (peak danger per minute, negatives clipped to 0) and
    an exponential decay window. Returns the primary series as a DataFrame;
    the secondary series (window × 2) and match events are stored in df.attrs.

    Args:
        match_id (int): StatsBomb match ID.
        window_minutes (int): Primary smoothing window in minutes. Default: 3.
        decay_alpha (float): Exponential decay factor in (0, 1). Default: 0.6.
        aggregation (str): Aggregation label stored in params metadata. Default: "max".
        data_dir (Path | None): Directory containing xt_actions.json; defaults to
            the legacy _SAMPLE_DATA_DIR (libs/footballd3/sample_data/).

    Returns:
        pd.DataFrame: One row per minute (1..max_minute) with columns:
            minute (int), home_threat (float), away_threat (float), momentum (float).
        Also sets on df.attrs:
            home_team, away_team (str),
            secondary_minutes (list[dict]): Same shape, secondary window.
            goals (list[dict]): [{minute, team, player, is_own_goal}].
            red_cards (list[dict]): [{minute, team, player}].
            params (dict): Window and decay parameters used.
            grid_source (str): xT grid provenance string.
            competition, season, match_label (str).

    Raises:
        FileNotFoundError: If xt_actions file does not exist.
        ValueError: If the actions list is empty.
    """
    _dir = data_dir if data_dir is not None else _SAMPLE_DATA_DIR
    # New layout uses xt_actions.json (match_id in dir path); legacy uses xt_actions_{id}.json.
    actions_path = _dir / "xt_actions.json"
    if not actions_path.exists():
        actions_path = _dir / f"xt_actions_{match_id}.json"
    if not actions_path.exists():
        raise FileNotFoundError(
            f"xt_actions file not found in {_dir} — run extract_xt.py first."
        )

    with open(actions_path) as f:
        xt_data = json.load(f)

    actions: list[dict] = xt_data["actions"]
    grid_source: str = xt_data["metadata"].get("grid_source", "Karun Singh open_xt_12x8_v1")

    if not actions:
        raise ValueError(f"No actions found in xt_actions_{match_id}.json")

    home_team, away_team = _resolve_teams(match_id)
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)
    competition, season, match_label = fetch_match_info(match_id)

    max_minute = max(int(a["minute"]) for a in actions)
    home_raw, away_raw = _compute_raw_threats(actions, home_team, away_team, max_minute)

    home_sm = _apply_exp_window(home_raw, window_minutes, decay_alpha)
    away_sm = _apply_exp_window(away_raw, window_minutes, decay_alpha)
    minutes_records = [
        {
            "minute":      m,
            "home_threat": round(home_sm[m], 6),
            "away_threat": round(away_sm[m], 6),
            "momentum":    round(home_sm[m] - away_sm[m], 6),
        }
        for m in range(1, max_minute + 1)
    ]

    secondary_window = window_minutes * _SECONDARY_WINDOW_MULTIPLIER
    home_sm2 = _apply_exp_window(home_raw, secondary_window, decay_alpha)
    away_sm2 = _apply_exp_window(away_raw, secondary_window, decay_alpha)
    secondary_minutes = [
        {
            "minute":      m,
            "home_threat": round(home_sm2[m], 6),
            "away_threat": round(away_sm2[m], 6),
            "momentum":    round(home_sm2[m] - away_sm2[m], 6),
        }
        for m in range(1, max_minute + 1)
    ]

    df = pd.DataFrame(minutes_records)
    df.attrs["home_team"]         = home_team
    df.attrs["away_team"]         = away_team
    df.attrs["secondary_minutes"] = secondary_minutes
    df.attrs["goals"]             = _extract_goals_from_events(events, nicknames)
    df.attrs["red_cards"]         = _extract_red_cards_from_events(events, nicknames)
    df.attrs["grid_source"]       = grid_source
    df.attrs["competition"]       = competition
    df.attrs["season"]            = season
    df.attrs["match_label"]       = match_label
    df.attrs["params"] = {
        "window_minutes":           window_minutes,
        "weighting":                "exponential",
        "decay_alpha":              decay_alpha,
        "aggregation":              aggregation,
        "secondary_window_minutes": secondary_window,
    }
    return df


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Compute momentum for a match and write the JSON contract.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.
            Also used as data_dir for locating xt_actions.json.

    Writes:
        {out_dir}/momentum.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    df = extract_momentum(match_id, data_dir=out_dir)

    payload = {
        "home_team":         df.attrs["home_team"],
        "away_team":         df.attrs["away_team"],
        "minutes":           df.to_dict(orient="records"),
        "secondary_minutes": df.attrs["secondary_minutes"],
        "goals":             df.attrs["goals"],
        "red_cards":         df.attrs["red_cards"],
        "params":            df.attrs["params"],
        "metadata": {
            "match_id":    match_id,
            "competition": df.attrs["competition"],
            "season":      df.attrs["season"],
            "match_label": df.attrs["match_label"],
            "grid_source": df.attrs["grid_source"],
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "momentum.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    home = df.attrs["home_team"]
    away = df.attrs["away_team"]
    params = df.attrs["params"]
    print(f"Momentum: {home} vs {away}")
    print(f"  Minutes:    {len(df)}")
    print(f"  Goals:      {len(df.attrs['goals'])}   Red cards: {len(df.attrs['red_cards'])}")
    print(
        f"  Window:     {params['window_minutes']} min "
        f"(α={params['decay_alpha']}, secondary: {params['secondary_window_minutes']} min)"
    )
    print(f"  → {out_path}")


if __name__ == "__main__":
    main()
