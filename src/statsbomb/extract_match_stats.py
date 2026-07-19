"""Extract match-level statistics from StatsBomb open data and return a tidy DataFrame.

Computes basic and advanced stats for both teams in one match. main() wraps the
DataFrame in the home/away/metadata envelope consumed by the matchStats D3 component.

Possession is computed as the share of all StatsBomb events attributed to each team
via the possession_team column. Yellow/red cards are sourced from foul_committed_card
and bad_behaviour_card columns.

Public API:
    extract_match_stats(match_id) -> pd.DataFrame
    load_team_colors(out_dir) -> dict
    main()

DataFrame columns: label, home_value, away_value, scale_type, format, tier

JSON output shape:
    {
      "home": { "team": str, "color": str, "score": int },
      "away": { "team": str, "color": str, "score": int },
      "rows": [
        {
          "label": str,
          "home_value": float,
          "away_value": float,
          "scale_type": "sum" | "fixed100" | "max",
          "format": "int" | "pct" | "float1",
          "tier": "basic" | "advanced"
        }
      ],
      "metadata": { "match_id": int, "competition": str, "match_label": str }
    }
Written to: src/footballd3/sample_data/match_stats_{match_id}.json
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import fetch_match_info, resolve_match

_DEFAULT_HOME_COLOR = "#9F1239"
_DEFAULT_AWAY_COLOR = "#1E3A5F"


def load_team_colors(out_dir: Path) -> dict:
    """Load team colors from team_colors.json in the sample_data directory.

    Args:
        out_dir (Path): Directory containing team_colors.json.

    Returns:
        dict: Mapping of team name (str) → hex color (str). Empty dict if file absent.
    """
    colors_path = out_dir / "team_colors.json"
    if not colors_path.exists():
        return {}
    with open(colors_path) as f:
        return json.load(f)


def _count_cards(events: pd.DataFrame, team: str, card_values: set) -> int:
    """Count disciplinary cards of specified types for a team.

    Checks both foul_committed_card (card given on a foul) and bad_behaviour_card
    (card given without a foul) when the column exists.

    Args:
        events (pd.DataFrame): Full match events DataFrame.
        team (str): Team name to filter by.
        card_values (set[str]): Card label values to count, e.g. {"Yellow Card"}.

    Returns:
        int: Total card count for the team.
    """
    team_events = events[events["team"] == team]
    count = 0
    if "foul_committed_card" in team_events.columns:
        count += int(team_events["foul_committed_card"].isin(card_values).sum())
    if "bad_behaviour_card" in team_events.columns:
        count += int(team_events["bad_behaviour_card"].isin(card_values).sum())
    return count


def extract_match_stats(match_id: int) -> pd.DataFrame:
    """Extract basic and advanced match statistics for both teams as a tidy DataFrame.

    Resolves home/away from sb.matches(), pulls all events, and computes stats
    using only StatsBomb data. Returns one row per stat with home/away values;
    main() wraps this in the full JSON contract (with home/away metadata).

    xG is the sum of shot_statsbomb_xg per team. Possession is the event share
    per possession_team. Corners are passes where pass_type == "Corner".

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pd.DataFrame: One row per stat with columns:
            label (str): Display label (e.g. "Shots", "xG").
            home_value (float): Stat value for the home team.
            away_value (float): Stat value for the away team.
            scale_type (str): "sum", "fixed100", or "max".
            format (str): "int", "pct", or "float1".
            tier (str): "basic" or "advanced".
        Also sets df.attrs["home_team"], df.attrs["away_team"],
            df.attrs["home_score"], df.attrs["away_score"].
    """
    competition, _, match_label = fetch_match_info(match_id)

    comps = sb.competitions()
    euro = comps[
        comps["competition_name"].str.contains("UEFA Euro", case=False)
        & (comps["season_name"] == "2024")
    ]
    competition_id = int(euro["competition_id"].iloc[0])
    season_id = int(euro["season_id"].iloc[0])
    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    match_row = matches[matches["match_id"] == match_id].iloc[0]

    home_team = str(match_row["home_team"])
    away_team = str(match_row["away_team"])

    events = sb.events(match_id=match_id)

    goals = events[(events["type"] == "Shot") & (events["shot_outcome"] == "Goal")]
    home_score = int((goals["team"] == home_team).sum())
    away_score = int((goals["team"] == away_team).sum())

    shots = events[events["type"] == "Shot"]
    home_shots = int((shots["team"] == home_team).sum())
    away_shots = int((shots["team"] == away_team).sum())

    on_target = shots[shots["shot_outcome"].isin({"Saved", "Goal"})]
    home_sot = int((on_target["team"] == home_team).sum())
    away_sot = int((on_target["team"] == away_team).sum())

    poss_counts = events["possession_team"].value_counts()
    total_events = poss_counts.sum()
    home_poss = round(float(poss_counts.get(home_team, 0)) / total_events * 100, 1)
    away_poss = round(100.0 - home_poss, 1)

    passes = events[events["type"] == "Pass"]
    corners = passes[passes["pass_type"] == "Corner"]
    home_corners = int((corners["team"] == home_team).sum())
    away_corners = int((corners["team"] == away_team).sum())

    fouls = events[events["type"] == "Foul Committed"]
    home_fouls = int((fouls["team"] == home_team).sum())
    away_fouls = int((fouls["team"] == away_team).sum())

    yellow_vals = {"Yellow Card"}
    home_yellows = _count_cards(events, home_team, yellow_vals)
    away_yellows = _count_cards(events, away_team, yellow_vals)

    red_vals = {"Red Card", "Second Yellow"}
    home_reds = _count_cards(events, home_team, red_vals)
    away_reds = _count_cards(events, away_team, red_vals)

    shots_with_xg = shots[shots["shot_statsbomb_xg"].notna()].copy()
    shots_with_xg["shot_statsbomb_xg"] = pd.to_numeric(
        shots_with_xg["shot_statsbomb_xg"], errors="coerce"
    )
    shots_with_xg = shots_with_xg[shots_with_xg["shot_statsbomb_xg"].notna()]
    home_xg = round(float(shots_with_xg[shots_with_xg["team"] == home_team]["shot_statsbomb_xg"].sum()), 2)
    away_xg = round(float(shots_with_xg[shots_with_xg["team"] == away_team]["shot_statsbomb_xg"].sum()), 2)

    rows = [
        {"label": "Shots",           "home_value": home_shots,   "away_value": away_shots,   "scale_type": "sum",      "format": "int",    "tier": "basic"},
        {"label": "Shots on Target", "home_value": home_sot,     "away_value": away_sot,     "scale_type": "sum",      "format": "int",    "tier": "basic"},
        {"label": "Possession",      "home_value": home_poss,    "away_value": away_poss,    "scale_type": "fixed100", "format": "pct",    "tier": "basic"},
        {"label": "Corners",         "home_value": home_corners, "away_value": away_corners, "scale_type": "sum",      "format": "int",    "tier": "basic"},
        {"label": "Fouls",           "home_value": home_fouls,   "away_value": away_fouls,   "scale_type": "sum",      "format": "int",    "tier": "basic"},
        {"label": "Yellow Cards",    "home_value": home_yellows, "away_value": away_yellows, "scale_type": "sum",      "format": "int",    "tier": "basic"},
        {"label": "Red Cards",       "home_value": home_reds,    "away_value": away_reds,    "scale_type": "sum",      "format": "int",    "tier": "basic"},
        {"label": "xG",              "home_value": home_xg,      "away_value": away_xg,      "scale_type": "sum",      "format": "float1", "tier": "advanced"},
    ]

    df = pd.DataFrame(rows)
    df.attrs["home_team"]  = home_team
    df.attrs["away_team"]  = away_team
    df.attrs["home_score"] = home_score
    df.attrs["away_score"] = away_score
    df.attrs["competition"] = competition
    df.attrs["match_label"] = match_label
    return df


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Extract match stats for a match and write the JSON contract.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output path: {out_dir}/match_stats.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    df = extract_match_stats(match_id)

    out_dir.mkdir(parents=True, exist_ok=True)
    # Look for team_colors.json in the shared data/ root (two levels up from match dir),
    # falling back to the match dir itself for backward compatibility.
    shared_dir = out_dir.parents[1]
    team_colors = load_team_colors(shared_dir) or load_team_colors(out_dir)

    home_team  = df.attrs["home_team"]
    away_team  = df.attrs["away_team"]
    competition = df.attrs["competition"]
    match_label = df.attrs["match_label"]

    payload = {
        "home": {
            "team":  home_team,
            "color": team_colors.get(home_team, _DEFAULT_HOME_COLOR),
            "score": df.attrs["home_score"],
        },
        "away": {
            "team":  away_team,
            "color": team_colors.get(away_team, _DEFAULT_AWAY_COLOR),
            "score": df.attrs["away_score"],
        },
        "rows": df.to_dict(orient="records"),
        "metadata": {
            "match_id":    match_id,
            "competition": competition,
            "match_label": match_label,
        },
    }

    out_path = out_dir / "match_stats.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(
        f"Wrote match stats → {out_path}\n"
        f"  {home_team} {df.attrs['home_score']}–{df.attrs['away_score']} {away_team}"
    )


if __name__ == "__main__":
    main()
