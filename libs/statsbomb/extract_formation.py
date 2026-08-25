"""Extract declared formation and tactical-shift sequence from StatsBomb open data.

Reads the Starting XI event and every Tactical Shift for one team to produce an
ordered sequence of formation periods. Returns a tidy DataFrame; main() reassembles
the nested JSON contract consumed by the formation D3 component.

Template coordinates are canonical diagram slots derived from formation_templates.json —
the coach's declared shape — NOT measured player positions.

Public API:
    extract_formation(match_id, team) -> pd.DataFrame
    load_formation_templates() -> dict
    main()

DataFrame columns: formation, from_minute, to_minute, player_id, player,
    display_name, jersey_number, position, template_x, template_y

JSON output shape:
    {
      "periods": [
        {
          "formation": "4-3-3",
          "from_minute": 0,
          "to_minute": 55,
          "players": [
            {
              "player_id": int,
              "player": str,
              "display_name": str,
              "jersey_number": int,
              "position": str,
              "template_x": float,
              "template_y": float
            }
          ]
        }
      ],
      "metadata": {
        "match_id": int,
        "team": str,
        "competition": str,
        "match_label": str,
        "coordinate_note": str
      }
    }
Written to: libs/footballd3/sample_data/formation_{match_id}_{team_slug}.json
"""

import json
import re
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import build_nickname_lookup, fetch_match_info, resolve_match

_TEMPLATES_PATH = Path(__file__).parent / "formation_templates.json"

COORDINATE_NOTE = (
    "template_x and template_y are canonical formation-slot positions in "
    "StatsBomb 120×80 coordinate space. They are NOT measured from play — "
    "they represent the declared tactical shape derived from StatsBomb position labels."
)


def load_formation_templates() -> dict:
    """Load the position-label to template-coordinate mapping from formation_templates.json.

    Returns:
        dict: Maps StatsBomb position label (str) to {"x": float, "y": float}.
            Coordinates are canonical formation slots in StatsBomb 120×80 space.

    Raises:
        FileNotFoundError: If formation_templates.json is missing.
    """
    with open(_TEMPLATES_PATH) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _format_formation(formation_int: int) -> str:
    """Convert a StatsBomb formation integer to a hyphen-separated string (e.g. 433 → "4-3-3").

    Args:
        formation_int (int): StatsBomb formation integer.

    Returns:
        str: Hyphen-separated formation string.
    """
    return "-".join(str(formation_int))


def _build_player_list(lineup: list, templates: dict, nicknames: dict) -> list[dict]:
    """Map a StatsBomb lineup array to placed player records with template coordinates.

    Players whose position label is absent from templates get coordinates (60, 40)
    — pitch centre — as a safe fallback, and a warning is printed.

    Args:
        lineup (list): StatsBomb tactics.lineup entries, each a dict with keys
            player (dict with id and name), jersey_number (int), position (dict with name).
        templates (dict): Position label -> {"x": float, "y": float}.
        nicknames (dict[int, str]): player_id -> display_name from sb.lineups().

    Returns:
        list[dict]: One record per player with keys:
            player_id (int), player (str), display_name (str), jersey_number (int),
            position (str), template_x (float), template_y (float). Sorted by
            jersey_number.
    """
    records = []
    for entry in lineup:
        player_id = int(entry["player"]["id"])
        player_name = entry["player"]["name"]
        jersey = int(entry["jersey_number"])
        position_label = entry["position"]["name"]

        slot = templates.get(position_label)
        if slot is None:
            print(f"  WARNING: no template for position '{position_label}'; using centre (60, 40)")
            slot = {"x": 60, "y": 40}

        raw_nick = nicknames.get(player_id, "")
        display_name = raw_nick if raw_nick else player_name

        records.append({
            "player_id":     player_id,
            "player":        player_name,
            "display_name":  display_name,
            "jersey_number": jersey,
            "position":      position_label,
            "template_x":    float(slot["x"]),
            "template_y":    float(slot["y"]),
        })

    return sorted(records, key=lambda r: r["jersey_number"])


def extract_formation(match_id: int, team: str) -> pd.DataFrame:
    """Extract the ordered formation-period sequence for one team as a tidy DataFrame.

    Reads the Starting XI event and every Tactical Shift for the given team.
    Returns one row per player per formation period. The to_minute of one period
    equals the from_minute of the next; the last period runs to the final event minute.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name exactly as it appears in StatsBomb data (e.g. "Spain").

    Returns:
        pd.DataFrame: One row per player per period with columns:
            formation (str): Hyphen-separated formation string (e.g. "4-3-3").
            from_minute (int): Period start minute (inclusive).
            to_minute (int): Period end minute (exclusive; last period = match end).
            player_id (int): StatsBomb's stable numeric player ID.
            player (str): Full player name.
            display_name (str): Resolved display name (nickname or full name).
            jersey_number (int): Jersey number.
            position (str): StatsBomb position label.
            template_x, template_y (float): Canonical formation-slot coordinates.

    Raises:
        ValueError: If no Starting XI event is found for the given team.
    """
    templates = load_formation_templates()
    events = sb.events(match_id=match_id)
    nicknames = build_nickname_lookup(match_id)

    team_events = events[events["team"] == team]

    xi_rows = team_events[team_events["type"] == "Starting XI"]
    if xi_rows.empty:
        raise ValueError(f"No 'Starting XI' event found for team '{team}' in match {match_id}")

    xi_row = xi_rows.iloc[0]
    tactics = xi_row["tactics"]
    shift_rows = team_events[team_events["type"] == "Tactical Shift"].sort_values("minute")
    match_end = int(events["minute"].max())

    anchors = [(tactics["formation"], tactics["lineup"], 0)]
    for _, row in shift_rows.iterrows():
        t = row["tactics"]
        anchors.append((t["formation"], t["lineup"], int(row["minute"])))

    records = []
    for i, (formation_int, lineup, from_min) in enumerate(anchors):
        to_min = anchors[i + 1][2] if i + 1 < len(anchors) else match_end
        formation_str = _format_formation(formation_int)
        for player_rec in _build_player_list(lineup, templates, nicknames):
            records.append({
                "formation":   formation_str,
                "from_minute": from_min,
                "to_minute":   to_min,
                **player_rec,
            })

    return pd.DataFrame(records)


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    teams: list[str] | None = None,
) -> None:
    """Extract formations for both teams in a match and write JSON.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.
        teams (list[str] | None): Teams to extract; defaults to both teams in the match.

    Output: {out_dir}/formation_{team_slug}.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    print(f"Match ID: {match_id}")

    competition, _, match_label = fetch_match_info(match_id)

    if teams is None:
        # Resolve home/away from the match metadata to iterate both teams.
        comps = sb.competitions()
        euro = comps[
            comps["competition_name"].str.contains("UEFA Euro", case=False)
            & (comps["season_name"] == "2024")
        ]
        matches = sb.matches(
            competition_id=int(euro["competition_id"].iloc[0]),
            season_id=int(euro["season_id"].iloc[0]),
        )
        match_row = matches[matches["match_id"] == match_id].iloc[0]
        teams = [str(match_row["home_team"]), str(match_row["away_team"])]

    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    for team in teams:
        print(f"\nExtracting formation for {team}…")
        df = extract_formation(match_id, team)

        # Reconstruct nested periods for the JSON contract.
        periods = []
        for (formation, from_min, to_min), group in df.groupby(
            ["formation", "from_minute", "to_minute"], sort=False
        ):
            players = group.drop(columns=["formation", "from_minute", "to_minute"]).to_dict(
                orient="records"
            )
            periods.append({
                "formation":   formation,
                "from_minute": int(from_min),
                "to_minute":   int(to_min),
                "players":     players,
            })
            print(f"  {formation}  {from_min}'–{to_min}'  ({len(players)} players)")

        payload = {
            "periods": periods,
            "metadata": {
                "match_id":       match_id,
                "team":           team,
                "competition":    competition,
                "match_label":    match_label,
                "coordinate_note": COORDINATE_NOTE,
            },
        }

        team_slug = re.sub(r"[^a-z0-9]+", "_", team.lower()).strip("_")
        out_path = out_dir / f"formation_{team_slug}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"Wrote → {out_path}")


if __name__ == "__main__":
    main()
