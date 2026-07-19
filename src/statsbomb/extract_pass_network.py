"""Extract a substitution-windowed pass network for one team as a tidy DataFrame.

Each window covers the time between two lineup changes. Nodes are average player
positions (from pass origins); edges are directed pass counts (both directions
emitted separately). Only completed passes are included.

Public API:
    extract_pass_network(match_id, team) -> pd.DataFrame
    main()

DataFrame columns: window_index, window_label, from_player, from_x, from_y,
    to_player, count

JSON output shape:
    {
      "windows": [
        {
          "index": 0,
          "label": "0'–63' (Starting XI)",
          "nodes": [{"player", "display_name", "x", "y", "passes"}],
          "edges": [{"from", "to", "count"}]
        }
      ],
      "substitutions": [{"minute", "player_off", "player_on"}],
      "metadata": {"match_id", "team", "filter", "competition", "match_label"}
    }
Written to: src/footballd3/sample_data/pass_network_{match_id}_{team}.json
"""

import json
import math
from pathlib import Path

import pandas as pd
from statsbombpy import sb

from .utils import build_nickname_lookup, fetch_match_info, resolve_match


def _build_windows(
    events: pd.DataFrame,
    team: str,
    nicknames: dict,
) -> tuple[list[dict], list[dict]]:
    """Split completed pass events into substitution-bounded windows.

    For each window, computes average pass-origin positions per player (nodes)
    and directed pass counts per ordered player pair (edges). Both directions
    of a pair are emitted as separate edge records.

    Args:
        events (pd.DataFrame): Full match event DataFrame from sb.events().
        team (str): Team name to filter on, exactly as returned by StatsBomb.
        nicknames (dict[int, str]): player_id -> display_name from sb.lineups().

    Returns:
        tuple[list[dict], list[dict]]: (windows, substitutions).
            windows: list of dicts with keys index, label, nodes, edges.
                Each node has keys: player, display_name, x, y, passes.
            substitutions: list of {minute, player_off, player_on} dicts.
    """
    sub_mask = (events["type"] == "Substitution") & (events["team"] == team)
    sub_rows = events[sub_mask].sort_values("minute")

    substitutions = []
    for _, row in sub_rows.iterrows():
        substitutions.append({
            "minute":     int(row["minute"]),
            "player_off": str(row["player"]),
            "player_on":  str(row.get("substitution_replacement", "")),
        })

    sub_minutes = [s["minute"] for s in substitutions]
    starts = [0] + sub_minutes
    ends = sub_minutes + [None]

    pass_mask = (
        (events["type"] == "Pass")
        & (events["team"] == team)
        & (events["pass_outcome"].isna())
    )
    passes = events[pass_mask].copy()

    windows = []
    for i, (start, end) in enumerate(zip(starts, ends)):
        w = passes[passes["minute"] >= start]
        if end is not None:
            w = w[w["minute"] < end]
        if w.empty:
            continue

        nodes = []
        for player, group in w.groupby("player"):
            locs = [loc for loc in group["location"] if isinstance(loc, list)]
            if not locs:
                continue
            avg_x = round(sum(loc[0] for loc in locs) / len(locs), 2)
            avg_y = round(sum(loc[1] for loc in locs) / len(locs), 2)
            pid_val = group["player_id"].iloc[0]
            display_name = (
                nicknames.get(int(pid_val), str(player)) if pid_val == pid_val else str(player)
            )
            nodes.append({
                "player":       str(player),
                "display_name": display_name,
                "x":            avg_x,
                "y":            avg_y,
                "passes":       int(len(group)),
            })

        edge_counts: dict[tuple[str, str], int] = {}
        for _, row in w.iterrows():
            recipient = row.get("pass_recipient")
            if recipient is None or (isinstance(recipient, float) and math.isnan(recipient)):
                continue
            key = (str(row["player"]), str(recipient))
            edge_counts[key] = edge_counts.get(key, 0) + 1

        edges = [
            {"from": k[0], "to": k[1], "count": v}
            for k, v in sorted(edge_counts.items(), key=lambda x: -x[1])
        ]

        end_str = f"{end}'" if end is not None else "FT"
        label = f"0'–{end_str} (Starting XI)" if i == 0 else f"{start}'–{end_str}"
        windows.append({"index": i, "label": label, "nodes": nodes, "edges": edges})

    return windows, substitutions


def extract_pass_network(match_id: int, team: str) -> pd.DataFrame:
    """Extract a substitution-windowed pass network as a tidy edges DataFrame.

    Computes directed pass counts per ordered player pair per substitution
    window. The from_player's average pass-origin position (from_x, from_y) is
    included so spatial analysis is possible without a second call. Only
    completed passes (pass_outcome is NaN) are included.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name exactly as returned by StatsBomb (e.g. "Spain").

    Returns:
        pd.DataFrame: One row per directed pass pair per window with columns:
            window_index (int): Window index (0 = Starting XI).
            window_label (str): Human-readable window label (e.g. "0'–63' (Starting XI)").
            from_player (str): Display name of the passer.
            from_x, from_y (float): Average pass-origin position for from_player in
                this window, in StatsBomb 120×80 yards.
            to_player (str): Display name of the recipient.
            count (int): Number of completed passes from from_player to to_player.
        Returns an empty DataFrame when no completed passes exist.
    """
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)
    windows, _ = _build_windows(events, team, nicknames)

    records = []
    for window in windows:
        node_pos = {n["player"]: (n["x"], n["y"]) for n in window["nodes"]}
        for edge in window["edges"]:
            pos = node_pos.get(edge["from"], (None, None))
            records.append({
                "window_index": window["index"],
                "window_label": window["label"],
                "from_player":  edge["from"],
                "from_x":       pos[0],
                "from_y":       pos[1],
                "to_player":    edge["to"],
                "count":        edge["count"],
            })
    return pd.DataFrame(records)


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    teams: list[str] | None = None,
) -> None:
    """Extract pass networks for a match and write JSON.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.
        teams (list[str] | None): Teams to extract; defaults to both teams in the match.

    Output: {out_dir}/pass_network_{team}.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)

    competition, _, match_label = fetch_match_info(match_id)

    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)

    out_dir.mkdir(parents=True, exist_ok=True)

    if teams is None:
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

    for team in teams:
        windows, substitutions = _build_windows(events, team, nicknames)

        payload = {
            "windows": windows,
            "substitutions": substitutions,
            "metadata": {
                "match_id":    match_id,
                "team":        team,
                "filter":      "completed passes, per substitution window",
                "competition": competition,
                "match_label": match_label,
            },
        }

        out_path = out_dir / f"pass_network_{team}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)

        n_nodes = len(windows[0]["nodes"]) if windows else 0
        print(f"[{team}] {len(windows)} windows · {n_nodes} players in window 0 → {out_path}")


if __name__ == "__main__":
    main()
