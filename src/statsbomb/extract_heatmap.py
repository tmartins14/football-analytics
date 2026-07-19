"""Extract on-ball events for one player and return them as a tidy DataFrame.

main() feeds the DataFrame into compute_kde_grid() and writes the heatmap
JSON contract consumed by the heatmap D3 component.

Public API:
    extract_heatmap(match_id, player_name) -> pd.DataFrame
    compute_kde_grid(events, bandwidth_yards, cols, rows) -> dict
    main()

DataFrame columns: event_id, x, y, event_type, minute, display_name, team

JSON output shape:
    {
        "grid": {"cols": 60, "rows": 40, "values": [[...], ...]},
        "metadata": {
            "match_id", "display_name", "team", "competition", "match_label",
            "event_count", "method", "bandwidth_yards",
            "grid_cols", "grid_rows", "pitch_width_yards", "pitch_height_yards"
        }
    }
Written to: src/footballd3/sample_data/heatmap_{match_id}_{player_slug}.json

On-ball events: every event where the named player is the actor AND a location
field is present — passes, shots, carries, pressures, duels, ball receipts, etc.
This is NOT off-ball positioning or movement data.
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
from statsbombpy import sb

from .utils import build_nickname_lookup, fetch_match_info, resolve_match

SB_PITCH_WIDTH  = 120
SB_PITCH_HEIGHT = 80


def extract_heatmap(
    match_id: int,
    player_name: str | None = None,
) -> pd.DataFrame:
    """Extract on-ball events for one player from a match as a tidy DataFrame.

    An on-ball event is any StatsBomb event where the player is the actor and
    a location field is present. Includes passes, shots, carries, pressures,
    duels, ball receipts, etc. This is NOT off-ball positioning data.

    When player_name is None, picks the player with the highest on-ball event
    count in the match (maximises visual interest for demos).

    Args:
        match_id (int): StatsBomb match ID.
        player_name (str | None): Full player name as it appears in StatsBomb data.
            When None, picks the top-event-count player automatically.

    Returns:
        pd.DataFrame: One row per on-ball event with columns:
            event_id (str): StatsBomb event UUID.
            x, y (float): StatsBomb-native coordinates (0–120, 0–80).
            event_type (str): StatsBomb event type label.
            minute (int): Match minute.
            display_name (str): Resolved player display name (nickname or full name).
            team (str): Player's team name.
        Also sets df.attrs["display_name"] and df.attrs["team"].

    Raises:
        ValueError: If the requested player has no on-ball events in this match,
            or if no located events exist in the match.
    """
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)
    located = events[events["location"].notna()].copy()

    if player_name is None:
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
    pid_series = player_events["player_id"].dropna()
    if not pid_series.empty:
        pid_val = pid_series.iloc[0]
        display_name = nicknames.get(int(pid_val), player_name)
    else:
        display_name = player_name

    records = []
    for _, row in player_events.iterrows():
        loc = row["location"]
        records.append({
            "event_id":    str(row["id"]),
            "x":           float(loc[0]),
            "y":           float(loc[1]),
            "event_type":  str(row["type"]),
            "minute":      int(row["minute"]),
            "display_name": display_name,
            "team":        str(team),
        })

    df = pd.DataFrame(records)
    df.attrs["display_name"] = display_name
    df.attrs["team"] = str(team)
    return df


def compute_kde_grid(
    events: list[dict],
    bandwidth_yards: float = 5.0,
    cols: int = 60,
    rows: int = 40,
) -> dict:
    """Compute a KDE density surface over the StatsBomb 120×80 pitch.

    Uses a Gaussian kernel evaluated at the centre of each grid cell. The
    bandwidth is specified in StatsBomb yards. Density values are normalised to
    [0, 1] relative to the grid maximum.

    Grid layout: col 0 covers x ∈ [0, 120/cols), row 0 covers y ∈ [0, 80/rows).
    Cell centres are at x = (col + 0.5) * (120/cols), y = (row + 0.5) * (80/rows).

    Args:
        events (list[dict]): On-ball event records, each with "x" and "y" keys
            in StatsBomb native coordinates (yards, 0–120 and 0–80).
        bandwidth_yards (float): Gaussian kernel bandwidth in yards. Default 5.0.
        cols (int): Grid columns (x-axis divisions over 120 yards). Default 60.
        rows (int): Grid rows (y-axis divisions over 80 yards). Default 40.

    Returns:
        dict: {"cols": int, "rows": int, "values": list[list[float]]}
            where values is [rows][cols] normalised to [0, 1].

    Raises:
        ValueError: If fewer than 2 events are provided (KDE requires at least
            2 non-identical points).
    """
    if len(events) < 2:
        raise ValueError(
            f"KDE requires at least 2 events; got {len(events)}. "
            "The player may have been substituted very early."
        )

    xs = np.array([e["x"] for e in events], dtype=float)
    ys = np.array([e["y"] for e in events], dtype=float)

    x_std = xs.std() or 1.0
    y_std = ys.std() or 1.0
    scaled_data = np.vstack([xs / x_std, ys / y_std])
    kde = gaussian_kde(scaled_data, bw_method=1.0)

    cell_w = SB_PITCH_WIDTH / cols
    cell_h = SB_PITCH_HEIGHT / rows
    cx = np.linspace(cell_w / 2, SB_PITCH_WIDTH - cell_w / 2, cols)
    cy = np.linspace(cell_h / 2, SB_PITCH_HEIGHT - cell_h / 2, rows)
    grid_x, grid_y = np.meshgrid(cx, cy)

    eval_points = np.vstack([grid_x.ravel() / x_std, grid_y.ravel() / y_std])
    density = kde(eval_points).reshape(rows, cols)

    d_max = density.max()
    if d_max > 0:
        density = density / d_max

    values = [[round(float(v), 4) for v in row] for row in density]
    return {"cols": cols, "rows": rows, "values": values}


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Pick top-event-count player for a match, compute KDE heatmap, and write JSON.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output path: {out_dir}/heatmap_{player_slug}.json
    """
    bandwidth_yards = 5.0
    cols = 60
    rows = 40

    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    print(f"Match ID: {match_id}")

    df = extract_heatmap(match_id)
    display_name = df.attrs["display_name"]
    team = df.attrs["team"]
    print(f"Player: {display_name} ({team}) — {len(df)} on-ball events")

    events_for_kde = df[["x", "y"]].to_dict(orient="records")
    grid = compute_kde_grid(events_for_kde, bandwidth_yards=bandwidth_yards, cols=cols, rows=rows)

    competition, _, match_label = fetch_match_info(match_id)

    output = {
        "grid": grid,
        "metadata": {
            "match_id":          match_id,
            "display_name":      display_name,
            "team":              team,
            "competition":       competition,
            "match_label":       match_label,
            "event_count":       len(df),
            "method":            "kde",
            "bandwidth_yards":   bandwidth_yards,
            "grid_cols":         cols,
            "grid_rows":         rows,
            "pitch_width_yards": SB_PITCH_WIDTH,
            "pitch_height_yards": SB_PITCH_HEIGHT,
        },
    }

    player_slug = re.sub(r"[^a-z0-9]+", "_", display_name.lower()).strip("_")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"heatmap_{player_slug}.json"

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote → {out_path}")


if __name__ == "__main__":
    main()
