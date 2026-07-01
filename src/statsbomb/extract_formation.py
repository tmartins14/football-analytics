"""Extract declared formation and tactical-shift sequence from StatsBomb open data.

Reads the Starting XI event and every Tactical Shift for one team to produce an
ordered sequence of formation periods. Each period covers a time range and carries
the full player lineup with canonical template coordinates derived from
formation_templates.json. Template coordinates are diagram slots — the coach's
declared shape — NOT measured player positions.

Public API:
    resolve_euro_2024_final() -> int
    load_formation_templates() -> dict
    extract_formation_periods(match_id, team) -> list[dict]
    main()

JSON output shape:
    {
      "periods": [
        {
          "formation": "4-3-3",
          "from_minute": 0,
          "to_minute": 55,
          "players": [
            {
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

Written to: src/footballd3/sample_data/formation_{match_id}_{team_slug}.json
"""

import json
import re
from pathlib import Path

import pandas as pd
from statsbombpy import sb

_TEMPLATES_PATH = Path(__file__).parent / "formation_templates.json"

COORDINATE_NOTE = (
    "template_x and template_y are canonical formation-slot positions in "
    "StatsBomb 120×80 coordinate space. They are NOT measured from play — "
    "they represent the declared tactical shape derived from StatsBomb position labels."
)


def resolve_euro_2024_final() -> int:
    """Resolve the UEFA Euro 2024 Final match ID from the StatsBomb open data API.

    Duplicated from extract_shots.resolve_euro_2024_final. Once a third script
    needs the same resolution, extract to a shared utility module.

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
            f"Candidates:\n{final_rows[['match_id', 'match_date', 'home_team', 'away_team']]}"
        )

    return int(final_rows["match_id"].iloc[0])


def load_formation_templates() -> dict:
    """Load the position-label to template-coordinate mapping from formation_templates.json.

    Returns:
        dict: Maps StatsBomb position label (str) to {"x": float, "y": float}.
            Coordinates are canonical formation slots in StatsBomb 120x80 space —
            not measured positions.

    Raises:
        FileNotFoundError: If formation_templates.json is missing.
        KeyError: If a required position label is absent from the file.
    """
    with open(_TEMPLATES_PATH) as f:
        data = json.load(f)
    # Strip the metadata key; every other key is a position label.
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _format_formation(formation_int: int) -> str:
    """Convert a StatsBomb formation integer to a hyphen-separated string.

    StatsBomb encodes formations as integers without separators (e.g. 433, 4231).
    This function inserts hyphens between each digit group so the display reads
    naturally (e.g. "4-3-3", "4-2-3-1"). Single-digit groups are preserved as-is.

    Args:
        formation_int (int): StatsBomb formation integer.

    Returns:
        str: Hyphen-separated formation string (e.g. "4-3-3").
    """
    s = str(formation_int)
    return "-".join(s)


def _build_player_list(lineup: list, templates: dict, nicknames: dict) -> list[dict]:
    """Map a StatsBomb lineup array to placed player records with template coordinates.

    Each lineup entry carries player name, jersey number, and position label. The
    position label is looked up in the templates dict to assign a canonical (x, y)
    slot. Players whose position label is not in templates get coordinates (60, 40)
    — pitch centre — as a safe fallback, and a warning is printed.

    Args:
        lineup (list): StatsBomb tactics.lineup entries, each a dict with keys
            player (dict with id and name), jersey_number (int), position (dict with name).
        templates (dict): Position label -> {"x": float, "y": float}.
        nicknames (dict): player_id (int) -> display_name (str) from sb.lineups().
            Players absent from this dict, or with an empty nickname, fall back to full name.

    Returns:
        list[dict]: One record per player with keys:
            player (str), display_name (str), jersey_number (int), position (str),
            template_x (float), template_y (float).
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
            "player": player_name,
            "display_name": display_name,
            "jersey_number": jersey,
            "position": position_label,
            "template_x": float(slot["x"]),
            "template_y": float(slot["y"]),
        })

    return sorted(records, key=lambda r: r["jersey_number"])


def extract_formation_periods(match_id: int, team: str) -> list[dict]:
    """Extract the ordered formation-period sequence for one team from a match.

    Reads the Starting XI event and every Tactical Shift for the given team.
    Returns an ordered list of periods: Starting XI first, each shift next. The
    to_minute of one period equals the from_minute of the next; the last period
    runs to the final event minute in the match.

    Template coordinates in each player record are canonical formation slots in
    StatsBomb 120x80 space — the declared tactical shape, not measured positions.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name exactly as it appears in StatsBomb data (e.g. "Spain").

    Returns:
        list[dict]: Ordered formation periods, each with keys:
            formation (str): Hyphen-separated formation string (e.g. "4-3-3").
            from_minute (int): Period start minute (inclusive).
            to_minute (int): Period end minute (exclusive; last period = match end).
            players (list[dict]): Placed players; see _build_player_list return shape.
                Each player includes display_name — the StatsBomb nickname when available,
                otherwise full player name.

    Raises:
        ValueError: If no Starting XI event is found for the given team.
    """
    templates = load_formation_templates()
    events = sb.events(match_id=match_id)

    # Build player_id -> display_name lookup from the lineups endpoint.
    lineups = sb.lineups(match_id=match_id)
    team_lineup = lineups.get(team)
    if team_lineup is not None:
        nicknames = {
            int(row["player_id"]): (
                row["player_nickname"] if pd.notna(row["player_nickname"]) and row["player_nickname"]
                else row["player_name"]
            )
            for _, row in team_lineup.iterrows()
        }
    else:
        nicknames = {}

    team_events = events[events["team"] == team]

    # Starting XI — every match has exactly one per team.
    xi_rows = team_events[team_events["type"] == "Starting XI"]
    if xi_rows.empty:
        raise ValueError(f"No 'Starting XI' event found for team '{team}' in match {match_id}")

    xi_row = xi_rows.iloc[0]
    tactics = xi_row["tactics"]

    # Tactical shifts — may be zero or more.
    shift_rows = team_events[team_events["type"] == "Tactical Shift"].sort_values("minute")

    match_end = int(events["minute"].max())

    # Build the ordered sequence of (formation, lineup, minute) anchors.
    anchors = [(tactics["formation"], tactics["lineup"], 0)]
    for _, row in shift_rows.iterrows():
        t = row["tactics"]
        anchors.append((t["formation"], t["lineup"], int(row["minute"])))

    periods = []
    for i, (formation_int, lineup, from_min) in enumerate(anchors):
        to_min = anchors[i + 1][2] if i + 1 < len(anchors) else match_end
        periods.append({
            "formation": _format_formation(formation_int),
            "from_minute": from_min,
            "to_minute": to_min,
            "players": _build_player_list(lineup, templates, nicknames),
        })

    return periods


def main() -> None:
    """Resolve the Euro 2024 Final, extract formations for both teams, and write JSON.

    Output: src/footballd3/sample_data/formation_{match_id}_{team_slug}.json
    """
    match_id = resolve_euro_2024_final()
    print(f"Match ID: {match_id}")

    comps = sb.competitions()
    euro = comps[
        comps["competition_name"].str.contains("UEFA Euro", case=False)
        & (comps["season_name"] == "2024")
    ]
    competition = str(euro["competition_name"].iloc[0]) if not euro.empty else "UEFA Euro 2024"

    matches = sb.matches(
        competition_id=int(euro["competition_id"].iloc[0]),
        season_id=int(euro["season_id"].iloc[0]),
    )
    match_row = matches[matches["match_id"] == match_id].iloc[0]
    home_team = str(match_row["home_team"])
    away_team = str(match_row["away_team"])
    match_label = f"{home_team} vs {away_team}"

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    for team in [home_team, away_team]:
        print(f"\nExtracting formation for {team}…")
        periods = extract_formation_periods(match_id, team)

        for p in periods:
            print(
                f"  {p['formation']}  {p['from_minute']}'–{p['to_minute']}'  "
                f"({len(p['players'])} players)"
            )

        payload = {
            "periods": periods,
            "metadata": {
                "match_id": match_id,
                "team": team,
                "competition": competition,
                "match_label": match_label,
                "coordinate_note": COORDINATE_NOTE,
            },
        }

        team_slug = re.sub(r"[^a-z0-9]+", "_", team.lower()).strip("_")
        out_path = out_dir / f"formation_{match_id}_{team_slug}.json"

        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)

        print(f"Wrote → {out_path}")


if __name__ == "__main__":
    main()
