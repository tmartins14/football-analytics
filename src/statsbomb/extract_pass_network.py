"""Extract pass-network data from StatsBomb open data and write a flat JSON contract.

Computes one substitution-bounded window per lineup phase. Each window contains
average player positions (nodes) and directed pass counts per ordered player pair
(edges). Only completed passes are included.

Public API:
    resolve_euro_2024_final() -> int
    extract_pass_network(match_id, team) -> dict
    main()

JSON output shape:
    {
      "windows": [
        {
          "index": 0,
          "label": "0'–63' (Starting XI)",
          "nodes": [{"player", "x", "y", "passes"}],
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


def _build_windows(
    events: pd.DataFrame, team: str
) -> tuple[list[dict], list[dict]]:
    """Split completed pass events into substitution-bounded windows.

    For each window, computes average pass-origin positions per player (nodes)
    and directed pass counts per ordered player pair (edges). Both directions
    of a pair are emitted as separate edge records.

    Args:
        events: Full match event DataFrame from sb.events().
        team: Team name to filter on, exactly as returned by StatsBomb.

    Returns:
        Tuple of (windows, substitutions):
            windows — list of dicts with keys: index, label, nodes, edges.
            substitutions — list of {minute, player_off, player_on} dicts.
    """
    # Substitution breakpoints for this team, sorted by minute
    sub_mask = (events["type"] == "Substitution") & (events["team"] == team)
    sub_rows = events[sub_mask].sort_values("minute")

    substitutions = []
    for _, row in sub_rows.iterrows():
        substitutions.append(
            {
                "minute": int(row["minute"]),
                "player_off": str(row["player"]),
                "player_on": str(row.get("substitution_replacement", "")),
            }
        )

    # Time window boundaries: [(start, end), ...]; last end is None (= full time)
    sub_minutes = [s["minute"] for s in substitutions]
    starts = [0] + sub_minutes
    ends = sub_minutes + [None]

    # Completed passes for this team: pass_outcome is NaN for completions
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

        # Nodes: average pass-origin (location) per player
        nodes = []
        for player, group in w.groupby("player"):
            locs = [loc for loc in group["location"] if isinstance(loc, list)]
            if not locs:
                continue
            avg_x = round(sum(loc[0] for loc in locs) / len(locs), 2)
            avg_y = round(sum(loc[1] for loc in locs) / len(locs), 2)
            nodes.append(
                {
                    "player": str(player),
                    "x": avg_x,
                    "y": avg_y,
                    "passes": int(len(group)),
                }
            )

        # Edges: one ordered-pair record per direction (A→B and B→A separate).
        # StatsBomb flattens pass.recipient.name as "pass_recipient" (not _name).
        edge_counts: dict[tuple[str, str], int] = {}
        for _, row in w.iterrows():
            recipient = row.get("pass_recipient")
            if recipient is None or (
                isinstance(recipient, float) and math.isnan(recipient)
            ):
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


def extract_pass_network(match_id: int, team: str) -> dict:
    """Extract a substitution-windowed pass network for one team from a StatsBomb match.

    Pulls all events once, computes substitution breakpoints, then for each window
    computes average player positions (nodes) and directed pass counts per ordered
    player pair (edges). Only completed passes are included — StatsBomb marks
    completions with a null pass_outcome.

    Coordinates are StatsBomb-native (120×80 yards, origin top-left) and passed
    through untouched. The pitch component owns pixel mapping.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name exactly as returned by StatsBomb (e.g. "Spain").

    Returns:
        dict: Pass network with keys:
            windows (list[dict]): One entry per substitution window, each with
                index, label, nodes [{player, x, y, passes}], and
                edges [{from, to, count}] (ordered pairs, both directions separate).
            substitutions (list[dict]): [{minute, player_off, player_on}].
            metadata (dict): match_id, team, filter description.
    """
    events = sb.events(match_id=match_id)
    windows, substitutions = _build_windows(events, team)

    return {
        "windows": windows,
        "substitutions": substitutions,
        "metadata": {
            "match_id": match_id,
            "team": team,
            "filter": "completed passes, per substitution window",
        },
    }


def main() -> None:
    """Resolve the Euro 2024 Final, extract pass networks for both teams, and write JSON.

    Output: src/footballd3/sample_data/pass_network_{match_id}_{team}.json
    """
    match_id = resolve_euro_2024_final()

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    for team in ["Spain", "England"]:
        data = extract_pass_network(match_id, team)
        data["metadata"]["competition"] = "UEFA Euro 2024"
        data["metadata"]["match_label"] = "Spain vs England"

        out_path = out_dir / f"pass_network_{match_id}_{team}.json"
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)

        n_windows = len(data["windows"])
        n_nodes = len(data["windows"][0]["nodes"]) if data["windows"] else 0
        print(f"[{team}] {n_windows} windows · {n_nodes} players in window 0 → {out_path}")


if __name__ == "__main__":
    main()
