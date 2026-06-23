"""Extract shot events from StatsBomb open data and write a flat JSON contract.

Public API:
    resolve_euro_2024_final() -> int
    extract_shots(match_id) -> list[dict]
    main()

JSON output shape: { x, y, xg, outcome, is_goal, team, player, minute }
Written to: src/footballd3/sample_data/shots_{match_id}.json
"""

import json
import math
from pathlib import Path

from statsbombpy import sb


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

    # StatsBomb uses a 'match_week' or 'competition_stage' column; try stage first.
    if "competition_stage" in matches.columns:
        final_rows = matches[
            matches["competition_stage"].astype(str).str.strip() == "Final"
        ]
    else:
        final_rows = matches.sort_values("match_date").iloc[[-1]]

    if final_rows.empty or len(final_rows) > 1:
        raise ValueError(
            f"Could not isolate Euro 2024 Final unambiguously. "
            f"Candidates:\n{final_rows[['match_id', 'match_date', 'home_team', 'away_team']]}"
        )

    return int(final_rows["match_id"].iloc[0])


def extract_shots(match_id: int) -> list[dict]:
    """Extract shot events for one match and return flat records for the JSON contract.

    Calls sb.events(), filters to type == "Shot", and maps each row to the
    minimal fields the shot map renderer needs. Drops shots where xG is NaN
    (own goals have no StatsBomb xG value).

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        list[dict]: One dict per shot with keys:
            x, y (float): StatsBomb-native coordinates (origin top-left, 120×80).
            xg (float): StatsBomb xG from shot_statsbomb_xg.
            outcome (str): Shot outcome label (e.g. "Goal", "Blocked", "Saved").
            is_goal (bool): True when outcome == "Goal".
            team (str): Team name.
            player (str): Player name.
            minute (int): Match minute.
    """
    events = sb.events(match_id=match_id)
    shots = events[events["type"] == "Shot"].copy()

    records = []
    for _, row in shots.iterrows():
        xg = row.get("shot_statsbomb_xg")
        if xg is None or (isinstance(xg, float) and math.isnan(xg)):
            continue
        loc = row["location"]
        records.append(
            {
                "x": loc[0],
                "y": loc[1],
                "xg": float(xg),
                "outcome": row["shot_outcome"],
                "is_goal": row["shot_outcome"] == "Goal",
                "team": row["team"],
                "player": row["player"],
                "minute": int(row["minute"]),
            }
        )
    return records


def main() -> None:
    """Resolve the Euro 2024 Final, extract its shots, and write the JSON contract.

    Output path: src/footballd3/sample_data/shots_{match_id}.json
    """
    match_id = resolve_euro_2024_final()
    shots = extract_shots(match_id)

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"shots_{match_id}.json"

    with open(out_path, "w") as f:
        json.dump(shots, f, indent=2)

    print(f"Wrote {len(shots)} shots → {out_path}")


if __name__ == "__main__":
    main()
