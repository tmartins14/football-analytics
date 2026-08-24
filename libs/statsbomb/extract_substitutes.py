"""Determine the eligible player roster for a match and extract substitutes.

The eligible roster (get_eligible_players) is the shared ground truth for "which
players actually played, and what is their stable identity" — consumed both here
and by extract_player_events.py. It is sourced from sb.lineups()'s per-player
positions array (present only for players who took the field) rather than from
extract_formation.py's Tactical-Shift-triggered formation periods, because not
every substitution triggers a Tactical Shift event: relying on formation periods
would silently drop any substitute whose entry wasn't accompanied by a reshuffle.

Goalkeepers are excluded entirely (any player with a "Goalkeeper" position entry).
player_id (StatsBomb's stable numeric ID) is used as the identity/join key
throughout — not display_name, which is fragile (accented characters, theoretical
name collisions).

Public API:
    get_eligible_players(match_id) -> pd.DataFrame
    extract_substitutes(match_id) -> pd.DataFrame
    main()

DataFrame columns (get_eligible_players): player_id, player, display_name, team,
    jersey_number, position, is_starter, on_minute, on_second, replaced_player

DataFrame columns (extract_substitutes): same, filtered to is_starter == False

JSON output shape (substitutes_{match_id}.json):
    {
        "teams": {
            "<team name>": [
                { "player_id", "player", "display_name", "jersey_number",
                  "position", "on_minute", "on_second", "replaced_player" }
            ]
        },
        "metadata": {"match_id", "competition", "season", "match_label"}
    }
Written to: libs/footballd3/sample_data/substitutes_{match_id}.json
"""

import json
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import clean_nan, fetch_match_info, resolve_match


def get_eligible_players(match_id: int) -> pd.DataFrame:
    """Build the roster of non-goalkeeper players who actually played in a match.

    Sourced from sb.lineups(): a player has played if their positions list is
    non-empty. Excluded entirely if any position entry's position label is
    "Goalkeeper" (safe under the common case of no keeper/outfield swaps).
    is_starter is True when the player's first position entry has
    start_reason == "Starting XI"; substitutes get on_minute/on_second/
    replaced_player cross-referenced from the match's Substitution events
    (matched by the incoming player's full name), which is more directly
    readable than parsing the lineups positions[0]["from"] "MM:SS" string.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pd.DataFrame: One row per eligible (non-GK, played) player with columns:
            player_id (int): StatsBomb's stable numeric player ID.
            player (str): Full player name.
            display_name (str): Resolved display name (nickname or full name).
            team (str): Team name.
            jersey_number (int): Jersey number.
            position (str): StatsBomb position label at first appearance.
            is_starter (bool): True if the player started the match.
            on_minute (int | None): Substitution-on minute; None for starters.
            on_second (int | None): Substitution-on second; None for starters.
            replaced_player (str | None): Full name of the player replaced;
                None for starters.
    """
    lineups = sb.lineups(match_id=match_id)
    events = sb.events(match_id=match_id)
    subs = events[events["type"] == "Substitution"]

    records: list[dict] = []
    for team, team_df in lineups.items():
        for _, row in team_df.iterrows():
            positions = row.get("positions") or []
            if not positions:
                continue  # never took the field

            if any(p.get("position") == "Goalkeeper" for p in positions):
                continue  # goalkeepers excluded entirely

            player_name = row["player_name"]
            nick = row.get("player_nickname")
            display_name = nick if (pd.notna(nick) and nick) else player_name

            first = positions[0]
            is_starter = first.get("start_reason") == "Starting XI"

            on_minute = on_second = None
            replaced_player = None
            if not is_starter:
                sub_rows = subs[subs["substitution_replacement"] == player_name]
                if not sub_rows.empty:
                    sub_row = sub_rows.iloc[0]
                    on_minute = int(sub_row["minute"])
                    on_second = int(sub_row["second"])
                    replaced_player = str(sub_row["player"])

            records.append({
                "player_id":       int(row["player_id"]),
                "player":          player_name,
                "display_name":    display_name,
                "team":            team,
                "jersey_number":   int(row["jersey_number"]),
                "position":        first.get("position"),
                "is_starter":      is_starter,
                "on_minute":       on_minute,
                "on_second":       on_second,
                "replaced_player": replaced_player,
            })

    return pd.DataFrame(records)


def extract_substitutes(match_id: int) -> pd.DataFrame:
    """Extract the non-goalkeeper substitutes who entered a match.

    Starters are already fully covered by extract_formation.py's Starting XI
    period, so this is scoped to substitutes only.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        pd.DataFrame: get_eligible_players(match_id) filtered to is_starter == False.
    """
    df = get_eligible_players(match_id)
    return df[~df["is_starter"]].reset_index(drop=True)


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Extract substitutes for a match and write JSON, grouped by team.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output: {out_dir}/substitutes.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    competition, season, match_label = fetch_match_info(match_id)
    df = extract_substitutes(match_id)

    teams: dict[str, list[dict]] = {}
    for team, group in df.groupby("team"):
        records = group.drop(columns=["team", "is_starter"]).to_dict(orient="records")
        # Every field can carry a pandas-coerced NaN in place of a per-row None
        # (get_eligible_players' columns mix real values with None across rows —
        # e.g. a substitute with no matching Substitution event leaves
        # on_minute/on_second/replaced_player all None — and pandas' NaN
        # coercion applies even to object/string columns, not just numeric
        # ones). clean_nan() restores real None so json.dump never emits a
        # literal NaN token. on_minute/on_second additionally need int() to
        # undo the float64 widening NaN-coercion causes on those two columns.
        cleaned = []
        for record in records:
            record = {k: clean_nan(v) for k, v in record.items()}
            for key in ("on_minute", "on_second"):
                if record[key] is not None:
                    record[key] = int(record[key])
            cleaned.append(record)
        teams[team] = cleaned

    payload = {
        "teams": teams,
        "metadata": {
            "match_id":    match_id,
            "competition": competition,
            "season":      season,
            "match_label": match_label,
        },
    }

    out_path = out_dir / "substitutes.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    for team, players in teams.items():
        names = [p["display_name"] for p in players]
        print(f"[{team}] {len(players)} substitutes: {names}")
    print(f"Wrote → {out_path}")


if __name__ == "__main__":
    main()
