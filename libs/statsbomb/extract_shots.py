"""Extract shot events from StatsBomb open data and return a tidy DataFrame.

Public API:
    extract_shots(match_id) -> pd.DataFrame
    main()

DataFrame columns: event_id, x, y, xg, outcome, is_goal, team, display_name, minute

JSON output shape (written by main): [{ x, y, xg, outcome, is_goal, team, display_name, minute }]
Written to: libs/footballd3/sample_data/shots_{match_id}.json
"""

import json
import math
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import build_nickname_lookup, resolve_match


def extract_shots(match_id: int) -> pd.DataFrame:
    """Extract shot events for one match and return a tidy DataFrame.

    Calls sb.events(), filters to type == "Shot", and maps each row to the
    fields consumed by the shot map renderer. Drops shots where xG is NaN
    (own goals have no StatsBomb xG value). display_name is the StatsBomb
    player nickname when available, otherwise the full player name.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pd.DataFrame: One row per shot with columns:
            event_id (str): StatsBomb event UUID.
            x, y (float): StatsBomb-native coordinates (origin top-left, 120×80).
            xg (float): StatsBomb xG from shot_statsbomb_xg.
            outcome (str): Shot outcome label (e.g. "Goal", "Blocked", "Saved").
            is_goal (bool): True when outcome == "Goal".
            team (str): Team name.
            display_name (str): Player nickname or full name, resolved Python-side.
            minute (int): Match minute.
    """
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)
    shots = events[events["type"] == "Shot"].copy()

    records = []
    for _, row in shots.iterrows():
        xg = row.get("shot_statsbomb_xg")
        if xg is None or (isinstance(xg, float) and math.isnan(xg)):
            continue
        loc = row["location"]
        pid = row.get("player_id")
        display_name = nicknames.get(int(pid), str(row["player"])) if pid == pid else str(row["player"])
        records.append(
            {
                "event_id":    str(row["id"]),
                "x":           float(loc[0]),
                "y":           float(loc[1]),
                "xg":          float(xg),
                "outcome":     row["shot_outcome"],
                "is_goal":     row["shot_outcome"] == "Goal",
                "team":        row["team"],
                "display_name": display_name,
                "minute":      int(row["minute"]),
            }
        )
    return pd.DataFrame(records)


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Extract shots for a match and write the JSON contract.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output path: {out_dir}/shots.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    df = extract_shots(match_id)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "shots.json"

    # JSON contract excludes event_id (not consumed by the D3 renderer).
    records = df.drop(columns=["event_id"]).to_dict(orient="records")
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Wrote {len(df)} shots → {out_path}")


if __name__ == "__main__":
    main()
