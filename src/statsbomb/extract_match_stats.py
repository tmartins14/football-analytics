"""Extract match-level statistics from StatsBomb open data and write the matchStats JSON contract.

Computes basic and advanced stats for both teams in one match and emits a flat contract
consumed by the matchStats D3 component. Football logic lives entirely here; the D3
renderer (matchStats.js) and the generic bar renderer (comparisonBars.js) remain
football-agnostic at the stat-semantics level.

Possession is computed as the share of all StatsBomb events attributed to each team via
the ``possession_team`` column. Every event carries a ``possession_team`` tag indicating
which team currently holds the ball; counting events per team and expressing as a
percentage captures possession intensity and aligns with broadcast statistics.

Yellow cards are sourced from ``foul_committed_card == 'Yellow Card'``. Red cards and
second yellows from ``foul_committed_card in {'Red Card', 'Second Yellow'}``. The
``bad_behaviour_card`` column (cards issued without a foul) is also checked when present.

Public API:
    resolve_euro_2024_final() -> int
    load_team_colors(out_dir) -> dict
    extract_match_stats(match_id) -> dict
    main()

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
import math
from pathlib import Path

import pandas as pd
from statsbombpy import sb

_DEFAULT_HOME_COLOR = "#9F1239"
_DEFAULT_AWAY_COLOR = "#1E3A5F"


def resolve_euro_2024_final() -> int:
    """Resolve the UEFA Euro 2024 Final match ID from the StatsBomb open data API.

    Returns:
        int: The StatsBomb match_id for the Euro 2024 Final.

    Raises:
        ValueError: If the competition/season can't be found, or if the Final
            can't be isolated to a single match.
    """
    comps = sb.competitions()
    euro = comps[
        comps["competition_name"].str.contains("UEFA Euro", case=False)
        & (comps["season_name"] == "2024")
    ]
    if euro.empty:
        raise ValueError("Could not find UEFA Euro 2024 in sb.competitions()")

    competition_id = int(euro["competition_id"].iloc[0])
    season_id = int(euro["season_id"].iloc[0])

    matches = sb.matches(competition_id=competition_id, season_id=season_id)

    if "competition_stage" in matches.columns:
        final_rows = matches[
            matches["competition_stage"].astype(str).str.strip() == "Final"
        ]
    else:
        final_rows = matches.sort_values("match_date").iloc[[-1]]

    if final_rows.empty or len(final_rows) > 1:
        raise ValueError(
            f"Could not isolate Euro 2024 Final unambiguously. "
            f"Candidates:\n{final_rows[['match_id','match_date','home_team','away_team']]}"
        )

    return int(final_rows["match_id"].iloc[0])


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

    Checks both ``foul_committed_card`` (card given on a foul) and
    ``bad_behaviour_card`` (card given without a foul, e.g. simulation) when
    the column exists.

    Args:
        events (pd.DataFrame): Full match events DataFrame.
        team (str): Team name to filter by.
        card_values (set[str]): Card label values to count, e.g. {'Yellow Card'}.

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


def extract_match_stats(match_id: int) -> dict:
    """Extract basic and advanced match statistics for both teams.

    Resolves home/away from ``sb.matches()``, pulls all events via ``sb.events()``,
    and computes stats using only StatsBomb data — no custom models.

    xG is the sum of ``shot_statsbomb_xg`` per team (shots with NaN xG are dropped).
    Possession is the share of all events attributed to each team via ``possession_team``.
    Corners are passes where ``pass_type == 'Corner'``.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict: matchStats JSON contract with keys ``home``, ``away``, ``rows``,
            ``metadata``. Row dicts carry ``label``, ``home_value``, ``away_value``,
            ``scale_type``, ``format``, and ``tier``.
    """
    # ── Resolve teams ────────────────────────────────────────────────────────────
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
    competition = str(match_row.get("competition", "UEFA Euro 2024"))
    match_label = f"{home_team} vs {away_team}"

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    team_colors = load_team_colors(out_dir)
    home_color = team_colors.get(home_team, _DEFAULT_HOME_COLOR)
    away_color = team_colors.get(away_team, _DEFAULT_AWAY_COLOR)

    # ── Load events ──────────────────────────────────────────────────────────────
    events = sb.events(match_id=match_id)

    # ── Score ────────────────────────────────────────────────────────────────────
    goals = events[(events["type"] == "Shot") & (events["shot_outcome"] == "Goal")]
    home_score = int((goals["team"] == home_team).sum())
    away_score = int((goals["team"] == away_team).sum())

    # ── Shots ────────────────────────────────────────────────────────────────────
    shots = events[events["type"] == "Shot"]
    home_shots = int((shots["team"] == home_team).sum())
    away_shots = int((shots["team"] == away_team).sum())

    # ── Shots on target (Saved or Goal) ─────────────────────────────────────────
    on_target = shots[shots["shot_outcome"].isin({"Saved", "Goal"})]
    home_sot = int((on_target["team"] == home_team).sum())
    away_sot = int((on_target["team"] == away_team).sum())

    # ── Possession (share of events per possession_team) ─────────────────────────
    poss_counts  = events["possession_team"].value_counts()
    total_events = poss_counts.sum()
    home_poss = round(float(poss_counts.get(home_team, 0)) / total_events * 100, 1)
    away_poss = round(100.0 - home_poss, 1)

    # ── Corners ──────────────────────────────────────────────────────────────────
    passes = events[events["type"] == "Pass"]
    corners = passes[passes["pass_type"] == "Corner"]
    home_corners = int((corners["team"] == home_team).sum())
    away_corners = int((corners["team"] == away_team).sum())

    # ── Fouls ────────────────────────────────────────────────────────────────────
    fouls = events[events["type"] == "Foul Committed"]
    home_fouls = int((fouls["team"] == home_team).sum())
    away_fouls = int((fouls["team"] == away_team).sum())

    # ── Yellow cards ─────────────────────────────────────────────────────────────
    yellow_vals = {"Yellow Card"}
    home_yellows = _count_cards(events, home_team, yellow_vals)
    away_yellows = _count_cards(events, away_team, yellow_vals)

    # ── Red cards (straight red or second yellow) ────────────────────────────────
    red_vals = {"Red Card", "Second Yellow"}
    home_reds = _count_cards(events, home_team, red_vals)
    away_reds = _count_cards(events, away_team, red_vals)

    # ── xG (StatsBomb value — not a custom model) ────────────────────────────────
    shots_with_xg = shots[shots["shot_statsbomb_xg"].notna()].copy()
    shots_with_xg["shot_statsbomb_xg"] = pd.to_numeric(
        shots_with_xg["shot_statsbomb_xg"], errors="coerce"
    )
    shots_with_xg = shots_with_xg[shots_with_xg["shot_statsbomb_xg"].notna()]
    home_xg = round(float(shots_with_xg[shots_with_xg["team"] == home_team]["shot_statsbomb_xg"].sum()), 2)
    away_xg = round(float(shots_with_xg[shots_with_xg["team"] == away_team]["shot_statsbomb_xg"].sum()), 2)

    # ── Assemble rows ────────────────────────────────────────────────────────────
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

    return {
        "home": {"team": home_team, "color": home_color, "score": home_score},
        "away": {"team": away_team, "color": away_color, "score": away_score},
        "rows": rows,
        "metadata": {
            "match_id": match_id,
            "competition": competition,
            "match_label": match_label,
        },
    }


def main() -> None:
    """Resolve the Euro 2024 Final, extract match stats, and write the JSON contract.

    Output path: src/footballd3/sample_data/match_stats_{match_id}.json
    """
    match_id = resolve_euro_2024_final()
    stats = extract_match_stats(match_id)

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"match_stats_{match_id}.json"

    with open(out_path, "w") as f:
        json.dump(stats, f, indent=2)

    home = stats["home"]
    away = stats["away"]
    print(
        f"Wrote match stats → {out_path}\n"
        f"  {home['team']} {home['score']}–{away['score']} {away['team']}"
    )


if __name__ == "__main__":
    main()
