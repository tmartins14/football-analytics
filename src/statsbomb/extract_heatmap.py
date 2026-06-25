"""Extract on-ball events for one player and compute a KDE density surface.

Public API:
    resolve_euro_2024_final() -> int
    extract_player_events(match_id, player_name=None) -> tuple[str, str, list[dict]]
    compute_kde_grid(events, bandwidth_yards, cols, rows) -> dict
    main()

JSON output shape:
    {
        "grid": {"cols": 60, "rows": 40, "values": [[...], ...]},
        "metadata": {
            "match_id", "player", "team", "competition", "match_label",
            "event_count", "method", "bandwidth_yards",
            "grid_cols", "grid_rows", "pitch_width_yards", "pitch_height_yards"
        }
    }

Written to: src/footballd3/sample_data/heatmap_{match_id}_{player_slug}.json

On-ball events: every event where the named player is the actor AND a location
field is present. This captures passes, shots, carries, pressures, duels,
ball-receipts, and so on — any moment the player actively participated in play.
This is NOT player movement or off-ball positioning.
"""

import json
import re
from pathlib import Path

import numpy as np
from scipy.stats import gaussian_kde
from statsbombpy import sb

SB_PITCH_WIDTH = 120
SB_PITCH_HEIGHT = 80


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
            f"Candidates:\n{final_rows[['match_id', 'match_date', 'home_team', 'away_team']]}"
        )

    return int(final_rows["match_id"].iloc[0])


def extract_player_events(
    match_id: int,
    player_name: str | None = None,
) -> tuple[str, str, list[dict]]:
    """Extract on-ball events for one player from a single match.

    An on-ball event is any StatsBomb event where the player is the actor and
    a location field is present (i.e., the event has a spatial coordinate).
    This includes passes, shots, carries, pressures, duels, ball receipts, etc.
    It is NOT off-ball positioning — individual player positions between events
    are not available in StatsBomb open data.

    Args:
        match_id (int): StatsBomb match ID.
        player_name (str | None): Full player name as it appears in StatsBomb
            data. When None, picks the player with the highest on-ball event
            count in the match — maximises visual interest for a demo.

    Returns:
        tuple[str, str, list[dict]]: (player_name, team, events) where each
            event dict has keys:
                x (float): StatsBomb-native x coordinate (0–120).
                y (float): StatsBomb-native y coordinate (0–80).
                type (str): StatsBomb event type label.
                minute (int): Match minute.

    Raises:
        ValueError: If the requested player has no on-ball events in this match.
    """
    events = sb.events(match_id=match_id)

    # Keep only events that have a spatial location.
    located = events[events["location"].notna()].copy()

    if player_name is None:
        # Pick the player with the most on-ball events. Excludes NaN player
        # rows (e.g., referee-assigned events) by dropping them first.
        by_player = (
            located.dropna(subset=["player"])
            .groupby(["player", "team"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        if by_player.empty:
            raise ValueError(f"No located events found for match {match_id}")
        top = by_player.iloc[0]
        player_name = top["player"]
        team = top["team"]
    else:
        player_rows = located[located["player"] == player_name]
        if player_rows.empty:
            raise ValueError(
                f"Player '{player_name}' has no on-ball events with location "
                f"in match {match_id}"
            )
        team = str(player_rows["team"].iloc[0])

    player_events = located[located["player"] == player_name]

    records = []
    for _, row in player_events.iterrows():
        loc = row["location"]
        records.append(
            {
                "x": float(loc[0]),
                "y": float(loc[1]),
                "type": str(row["type"]),
                "minute": int(row["minute"]),
            }
        )

    return player_name, team, records


def compute_kde_grid(
    events: list[dict],
    bandwidth_yards: float = 5.0,
    cols: int = 60,
    rows: int = 40,
) -> dict:
    """Compute a KDE density surface over the StatsBomb 120×80 pitch.

    Uses a Gaussian kernel evaluated at the centre of each grid cell.
    The bandwidth is specified in StatsBomb yards (the native coordinate unit
    for the 120×80 pitch). Density values are normalised to [0, 1] relative to
    the grid maximum so the renderer always maps over a simple [0, 1] domain.

    Grid layout: col 0 covers x ∈ [0, 120/cols), row 0 covers y ∈ [0, 80/rows).
    Cell centres are at x = (col + 0.5) * (120/cols), y = (row + 0.5) * (80/rows).

    The bandwidth is passed to scipy.stats.gaussian_kde as a scalar factor
    applied to the data's standard deviation (bw_method = bandwidth / std).
    To use yards directly, we compute the per-axis scaling explicitly.

    Args:
        events (list[dict]): On-ball event records, each with "x" and "y" keys
            in StatsBomb native coordinates (yards, 0–120 and 0–80).
        bandwidth_yards (float): Gaussian kernel bandwidth in yards. This is
            the primary smoothing parameter; larger values produce broader,
            smoother surfaces. Default 5.0 yards. Must be explicit — never
            a buried default.
        cols (int): Grid columns (x-axis divisions over 120 yards). Default 60.
        rows (int): Grid rows (y-axis divisions over 80 yards). Default 40.

    Returns:
        dict: {
            "cols": int,
            "rows": int,
            "values": list[list[float]]  # [rows][cols], normalised to [0, 1]
        }

    Raises:
        ValueError: If fewer than 2 events are provided (KDE needs at least 2
            non-identical points to estimate a density).
    """
    if len(events) < 2:
        raise ValueError(
            f"KDE requires at least 2 events; got {len(events)}. "
            "The player may have been substituted very early."
        )

    xs = np.array([e["x"] for e in events], dtype=float)
    ys = np.array([e["y"] for e in events], dtype=float)

    # scipy gaussian_kde uses Scott's rule by default; we override bw_method
    # with an explicit factor. The factor is bandwidth / std so the effective
    # smoothing distance is bandwidth_yards regardless of data spread.
    # Separate factors for x and y because the pitch is not square (120 vs 80),
    # but a scalar is sufficient here since both axes share the same yard unit.
    data = np.vstack([xs, ys])
    x_std = xs.std() or 1.0
    y_std = ys.std() or 1.0

    # Build a 2-component KDE with per-axis bandwidth scaling.
    # scipy doesn't natively support anisotropic bandwidth, so we scale the
    # data to unit-bandwidth space, fit the KDE, then evaluate on the scaled grid.
    x_scale = bandwidth_yards / x_std
    y_scale = bandwidth_yards / y_std
    scaled_data = np.vstack([xs / x_std, ys / y_std])
    kde = gaussian_kde(scaled_data, bw_method=1.0)

    # Build grid of cell centres in StatsBomb yards, then scale for evaluation.
    cell_w = SB_PITCH_WIDTH / cols
    cell_h = SB_PITCH_HEIGHT / rows
    cx = np.linspace(cell_w / 2, SB_PITCH_WIDTH - cell_w / 2, cols)
    cy = np.linspace(cell_h / 2, SB_PITCH_HEIGHT - cell_h / 2, rows)
    grid_x, grid_y = np.meshgrid(cx, cy)  # both shape (rows, cols)

    eval_points = np.vstack([
        grid_x.ravel() / x_std,
        grid_y.ravel() / y_std,
    ])
    density = kde(eval_points).reshape(rows, cols)

    # Normalise to [0, 1].
    d_max = density.max()
    if d_max > 0:
        density = density / d_max

    values = [[round(float(v), 4) for v in row] for row in density]
    return {"cols": cols, "rows": rows, "values": values}


def main() -> None:
    """Resolve Euro 2024 Final, pick top-event-count player, compute KDE, write JSON.

    Output path: src/footballd3/sample_data/heatmap_{match_id}_{player_slug}.json

    The player slug is the player's name lowercased with spaces replaced by
    underscores and non-alphanumeric characters removed.
    """
    bandwidth_yards = 5.0
    cols = 60
    rows = 40

    match_id = resolve_euro_2024_final()
    print(f"Match ID: {match_id}")

    player_name, team, events = extract_player_events(match_id)
    print(f"Player: {player_name} ({team}) — {len(events)} on-ball events")

    grid = compute_kde_grid(events, bandwidth_yards=bandwidth_yards, cols=cols, rows=rows)

    # Resolve match metadata for the contract.
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
    match_label = f"{match_row['home_team']} vs {match_row['away_team']}"

    output = {
        "grid": grid,
        "metadata": {
            "match_id": match_id,
            "player": player_name,
            "team": team,
            "competition": competition,
            "match_label": match_label,
            "event_count": len(events),
            "method": "kde",
            "bandwidth_yards": bandwidth_yards,
            "grid_cols": cols,
            "grid_rows": rows,
            "pitch_width_yards": SB_PITCH_WIDTH,
            "pitch_height_yards": SB_PITCH_HEIGHT,
        },
    }

    player_slug = re.sub(r"[^a-z0-9]+", "_", player_name.lower()).strip("_")
    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"heatmap_{match_id}_{player_slug}.json"

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote → {out_path}")


if __name__ == "__main__":
    main()
