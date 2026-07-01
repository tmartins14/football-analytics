"""Extract empirical team shape from StatsBomb events and 360 freeze-frame data.

Produces two separate measurements, intentionally using different methods:

ON-BALL (in-possession): event-based, identified by player. Mean position per
named player from that team's open-play events where possession_team == team.
Produces individual nodes + a convex hull of those nodes.

OFF-BALL (out-of-possession): frame-based, anonymous. Pools 360 frame dots for
the analyzed team while the opponent has the ball (open play only). Produces an
aggregate cloud: density grid, centroid, thirds-spine, covariance ellipse, and
a percentile-depth line. No player identities are assigned to the cloud.

OPEN-PLAY FILTER: play_pattern not in (From Corner, From Free Kick, From Goal
    Kick, From Kick Off, From Throw In). Transitions included.

COORDINATE NORMALIZATION: raw StatsBomb events use the physical pitch
    coordinate system without standardizing attack direction. This extractor
    normalizes so the analyzed team always attacks right (increasing x). It
    detects each period's attack direction from the team's mean event position:
    if mean x > 60 in period 1, team attacks right in H1 and normalization
    flips H2; otherwise H1 is flipped. Flip: x → 120-x, y → 80-y.

TEAMMATE-BOOLEAN INVERSION: in a 360 frame, `teammate` is relative to the
    actor (the player who performed the event), not the analyzed team. For
    out-of-possession frames the actor belongs to the opponent, so teammate=True
    marks OPPONENT players and teammate=False marks OUR players.

Public API:
    resolve_euro_2024_final() -> int
    load_frames(match_id) -> dict
    extract_on_ball(events, team, attack_dir_by_period, nicknames) -> dict
    extract_off_ball(events, frame_lookup, team, attack_dir_by_period,
                     bandwidth_yards, depth_percentile, cols, rows) -> dict
    main()

Private helpers:
    _build_lineup_periods(events, team) -> list[dict]

JSON output shape:
    {
      "on_ball": {
        "periods": [
          {
            "from_minute": int,
            "to_minute": int,
            "players_in": [str],
            "players_out": [str],
            "nodes": [{"player_id": int, "player": str, "display_name": str,
                       "x": float, "y": float, "event_count": int}],
            "hull": [[x, y], ...]
          }
        ]
      },
      "off_ball": {
        "density_grid": {"cols": int, "rows": int, "values": [[float]]},
        "centroid": {"x": float, "y": float},
        "thirds_spine": [{"third": str, "x": float, "y": float}],
        "ellipse": {"cx": float, "cy": float, "rx": float, "ry": float,
                    "angle_deg": float},
        "depth_line": {"x": float, "percentile": int}
      },
      "metadata": {...}
    }

Written to: src/footballd3/sample_data/team_shape_{match_id}_{team_slug}.json
"""

import json
import re
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from scipy.stats import gaussian_kde
from statsbombpy import sb

SB_PITCH_WIDTH = 120
SB_PITCH_HEIGHT = 80

SET_PIECE_PLAY_PATTERNS = frozenset([
    "From Corner",
    "From Free Kick",
    "From Goal Kick",
    "From Kick Off",
    "From Throw In",
])


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


def load_frames(match_id: int) -> dict:
    """Load all 360 freeze-frame data for a match, keyed by event UUID.

    Tries sb.frames() first; falls back to reading raw JSON from the StatsBomb
    open-data GitHub repository if sb.frames() raises. This handles the known
    InvalidIndexError bug in statsbombpy <= 1.18 for Euro 2024 match IDs.
    Pattern duplicated from extract_freeze_frame.py — no shared utility yet.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict[str, dict]: Maps event UUID (str) to a frame data dict with keys:
            freeze_frame (list[dict]): Player entries, each with location,
                teammate, actor, and keeper fields.

    Raises:
        urllib.error.HTTPError: If both sb.frames() and the GitHub fallback fail.
    """
    try:
        frames_df = sb.frames(match_id=match_id)
        uuid_col = "id" if "id" in frames_df.columns else "event_uuid"
        return {
            str(row[uuid_col]): {"freeze_frame": row["freeze_frame"]}
            for _, row in frames_df.iterrows()
        }
    except Exception:  # noqa: BLE001
        print("  sb.frames() raised; using GitHub raw JSON fallback.")

    url = (
        f"https://raw.githubusercontent.com/statsbomb/open-data/master"
        f"/data/three-sixty/{match_id}.json"
    )
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        raw = json.loads(resp.read())

    return {
        entry["event_uuid"]: {"freeze_frame": entry["freeze_frame"]}
        for entry in raw
    }


def _attack_direction_by_period(events, team: str) -> dict[int, str]:
    """Determine which direction the team attacks in each match period.

    Uses shot locations as the primary indicator: shots always happen in the
    attacking third, so mean shot x > 60 → team attacks right in that period.
    Falls back to mean x of in-possession located events when a period has no
    shots (e.g. goalless half with no attempts). Using all events (including
    defensive events) is unreliable when one team defends deeply.

    Args:
        events (pandas.DataFrame): Full match event DataFrame from sb.events().
        team (str): Team name to analyze.

    Returns:
        dict[int, str]: Maps period number (1, 2, ...) to "right" or "left".
    """
    shots = events[(events["team"] == team) & (events["type"] == "Shot")]
    shots_located = shots[shots["location"].notna()]

    direction_by_period: dict[int, str] = {}
    for period in sorted(int(p) for p in events["period"].unique()):
        period_shots = shots_located[shots_located["period"] == period]
        if not period_shots.empty:
            xs = [row["location"][0] for _, row in period_shots.iterrows()]
            direction_by_period[period] = "right" if np.mean(xs) > 60 else "left"
        else:
            # Fallback: mean x of in-possession events for this team in this period.
            fallback = events[
                (events["team"] == team)
                & (events["possession_team"] == team)
                & (events["period"] == period)
                & events["location"].notna()
            ]
            if not fallback.empty:
                xs = [row["location"][0] for _, row in fallback.iterrows()]
                direction_by_period[period] = "right" if np.mean(xs) > 60 else "left"
            else:
                direction_by_period[period] = "right"

    return direction_by_period


def _normalize_xy(x: float, y: float, direction: str) -> tuple[float, float]:
    """Normalize a StatsBomb coordinate so the team always attacks right.

    When direction == "left", the team attacks toward decreasing x, so we
    mirror both axes: x → 120-x, y → 80-y. This maps the defensive end to
    low x and the attacking end to high x, consistent across both halves.

    Args:
        x (float): StatsBomb x coordinate (0–120).
        y (float): StatsBomb y coordinate (0–80).
        direction (str): "right" (no change) or "left" (flip both axes).

    Returns:
        tuple[float, float]: Normalized (x, y).
    """
    if direction == "left":
        return SB_PITCH_WIDTH - x, SB_PITCH_HEIGHT - y
    return x, y


def _open_play_mask(events) -> "pandas.Series":
    """Return a boolean mask selecting open-play events.

    Excludes set pieces (corners, free kicks, goal kicks, kick-offs, throw-ins).
    Transitions (from counter) are included. The play_pattern column is coerced
    to string to handle any version differences in statsbombpy's output type.

    Args:
        events (pandas.DataFrame): Full match event DataFrame.

    Returns:
        pandas.Series[bool]: True for open-play events.
    """
    if "play_pattern" not in events.columns:
        return events.index.notna()  # keep all if column absent
    return ~events["play_pattern"].astype(str).isin(SET_PIECE_PLAY_PATTERNS)


def _compute_kde_grid(
    xs: np.ndarray,
    ys: np.ndarray,
    bandwidth_yards: float,
    cols: int,
    rows: int,
) -> dict:
    """Compute a 2D Gaussian KDE density grid over the 120×80 pitch.

    Uses the same normalised-data approach as extract_heatmap.py: scales data
    to unit bandwidth space, fits gaussian_kde with bw_method=1.0, evaluates on
    the grid of cell centres, then normalises values to [0, 1].

    Args:
        xs (numpy.ndarray): x coordinates of source dots (StatsBomb yards, 0–120).
        ys (numpy.ndarray): y coordinates of source dots (StatsBomb yards, 0–80).
        bandwidth_yards (float): Gaussian kernel bandwidth in yards.
        cols (int): Grid columns (x-axis).
        rows (int): Grid rows (y-axis).

    Returns:
        dict: {"cols": int, "rows": int, "values": list[list[float]]} where
            values is a 2D list [rows][cols] normalised to [0, 1].

    Raises:
        ValueError: If fewer than 2 points are provided.
    """
    if len(xs) < 2:
        raise ValueError(f"KDE requires at least 2 points; got {len(xs)}")

    x_std = xs.std() or 1.0
    y_std = ys.std() or 1.0

    scaled = np.vstack([xs / x_std, ys / y_std])
    kde = gaussian_kde(scaled, bw_method=1.0)

    cell_w = SB_PITCH_WIDTH / cols
    cell_h = SB_PITCH_HEIGHT / rows
    cx = np.linspace(cell_w / 2, SB_PITCH_WIDTH - cell_w / 2, cols)
    cy = np.linspace(cell_h / 2, SB_PITCH_HEIGHT - cell_h / 2, rows)
    grid_x, grid_y = np.meshgrid(cx, cy)

    eval_pts = np.vstack([grid_x.ravel() / x_std, grid_y.ravel() / y_std])
    density = kde(eval_pts).reshape(rows, cols)

    d_max = density.max()
    if d_max > 0:
        density = density / d_max

    return {
        "cols": cols,
        "rows": rows,
        "values": [[round(float(v), 4) for v in row] for row in density],
    }


def _compute_ellipse(xs: np.ndarray, ys: np.ndarray) -> dict:
    """Compute a covariance ellipse for a cloud of (x, y) points.

    Eigendecomposes the 2×2 covariance matrix. Semi-axes are 1-sigma (one
    standard deviation along each principal axis). The rotation angle is
    measured from the x-axis to the major axis, in degrees.

    Args:
        xs (numpy.ndarray): x coordinates in StatsBomb yards.
        ys (numpy.ndarray): y coordinates in StatsBomb yards.

    Returns:
        dict: {"cx", "cy", "rx", "ry", "angle_deg"} where rx >= ry.
    """
    cov = np.cov(np.vstack([xs, ys]))
    eigenvalues, eigenvectors = np.linalg.eigh(cov)

    # Sort descending by eigenvalue so rx is always the major semi-axis.
    order = eigenvalues.argsort()[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    rx = float(np.sqrt(max(eigenvalues[0], 0.0)))
    ry = float(np.sqrt(max(eigenvalues[1], 0.0)))
    angle_deg = float(np.degrees(np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0])))

    return {
        "cx":        round(float(xs.mean()), 2),
        "cy":        round(float(ys.mean()), 2),
        "rx":        round(rx, 2),
        "ry":        round(ry, 2),
        "angle_deg": round(angle_deg, 1),
    }


def _compute_thirds_spine(xs: np.ndarray, ys: np.ndarray) -> list[dict]:
    """Compute the centre of mass of dots in each pitch third.

    Thirds are defined on the normalised x-axis (team attacks right):
        defensive: x < 40
        middle:    40 <= x < 80
        attacking: x >= 80

    Args:
        xs (numpy.ndarray): x coordinates in normalised StatsBomb yards.
        ys (numpy.ndarray): y coordinates.

    Returns:
        list[dict]: Up to 3 entries in order (defensive, middle, attacking),
            each with keys "third" (str), "x" (float), "y" (float).
            Thirds with no dots are omitted.
    """
    spine = []
    thresholds = [("defensive", xs < 40), ("middle", (xs >= 40) & (xs < 80)), ("attacking", xs >= 80)]
    for label, mask in thresholds:
        if mask.sum() > 0:
            spine.append({
                "third": label,
                "x":     round(float(xs[mask].mean()), 2),
                "y":     round(float(ys[mask].mean()), 2),
            })
    return spine


def _compute_hull(nodes: list[dict]) -> list[list[float]]:
    """Compute the convex hull of player mean-position nodes.

    Uses scipy.spatial.ConvexHull. Falls back to the full node list (as
    ordered) if fewer than 3 distinct points exist.

    Args:
        nodes (list[dict]): Player node records, each with "x" and "y".

    Returns:
        list[[float, float]]: Ordered hull vertices in StatsBomb yards.
    """
    pts = np.array([[n["x"], n["y"]] for n in nodes])
    if len(pts) < 3:
        return [[round(p[0], 2), round(p[1], 2)] for p in pts]
    try:
        hull = ConvexHull(pts)
        return [[round(float(pts[i, 0]), 2), round(float(pts[i, 1]), 2)] for i in hull.vertices]
    except Exception:  # noqa: BLE001 — degenerate geometry (all collinear)
        return [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in pts]


def _build_lineup_periods(events, team: str) -> list[dict]:
    """Build lineup windows for a team, separated by substitution events.

    Reads the Starting XI event to establish the opening roster, then reads
    Substitution events in chronological order and groups simultaneous subs
    (same minute) to avoid zero-width windows. Each returned entry covers the
    time between two lineup changes and carries the exact set of 11 players on
    the pitch during that window.

    Args:
        events (pandas.DataFrame): Full match event DataFrame from sb.events().
        team (str): Team name to analyze.

    Returns:
        list[dict]: Ordered list of windows, each with:
            from_minute (int): First minute of the window (inclusive).
            to_minute   (int): First minute after the window (exclusive).
            players     (set[str]): Player names on the pitch in this window.
            players_in  (list[str]): Who joined at from_minute (all 11 for window 0).
            players_out (list[str]): Who left at from_minute (empty for window 0).
    """
    xi_rows = events[(events["team"] == team) & (events["type"] == "Starting XI")]
    if xi_rows.empty:
        raise ValueError(f"No 'Starting XI' event found for team '{team}'")
    xi_row = xi_rows.iloc[0]
    starters = [entry["player"]["name"] for entry in xi_row["tactics"]["lineup"]]

    sub_rows = events[
        (events["team"] == team) & (events["type"] == "Substitution")
    ].sort_values("minute")

    # Group simultaneous substitutions by minute to avoid zero-width windows.
    sub_groups: list[tuple[int, list]] = []
    for _, row in sub_rows.iterrows():
        minute = int(row["minute"])
        if sub_groups and sub_groups[-1][0] == minute:
            sub_groups[-1][1].append(row)
        else:
            sub_groups.append((minute, [row]))

    periods: list[dict] = []
    current: list[str] = list(starters)
    prev_minute: int = 0
    players_in: list[str] = list(starters)
    players_out: list[str] = []

    for sub_minute, rows in sub_groups:
        periods.append({
            "from_minute": prev_minute,
            "to_minute":   sub_minute,
            "players":     set(current),
            "players_in":  players_in,
            "players_out": players_out,
        })
        new_out: list[str] = []
        new_in:  list[str] = []
        for row in rows:
            player_off = str(row["player"])
            rep = row.get("substitution_replacement")
            player_on = rep["name"] if isinstance(rep, dict) else str(rep)
            current = [p for p in current if p != player_off] + [player_on]
            new_out.append(player_off)
            new_in.append(player_on)
        players_in  = new_in
        players_out = new_out
        prev_minute = sub_minute

    match_end = int(events["minute"].max()) + 1
    periods.append({
        "from_minute": prev_minute,
        "to_minute":   match_end,
        "players":     set(current),
        "players_in":  players_in,
        "players_out": players_out,
    })

    return periods


def extract_on_ball(
    events, team: str, attack_dir_by_period: dict, nicknames: dict
) -> dict:
    """Extract empirical on-ball shape from open-play events, split by lineup period.

    Builds lineup windows from Starting XI + Substitution events (one window per
    substitution boundary). For each window, filters to events where:
      - team == team (actor is on our team — required; possession_team alone
        would include opponent events during our possession phases)
      - possession_team == team
      - play pattern is open play
      - location is present
      - player is in the current lineup window
      - minute falls within [from_minute, to_minute)

    Computes mean (x, y) per player within their window, then builds a convex hull
    of those mean positions. Coordinates are normalised so the team always attacks
    right (increasing x). Players with zero events in a window are omitted; their
    absence is visible via event_count on the nodes.

    Args:
        events (pandas.DataFrame): Full match event DataFrame from sb.events().
        team (str): Team name to analyze.
        attack_dir_by_period (dict[int, str]): Period → "right"/"left" from
            _attack_direction_by_period().
        nicknames (dict[int, str]): player_id -> display_name from sb.lineups().
            Players absent from this dict fall back to full player name.

    Returns:
        dict: {
            "periods": list[dict] — one per lineup window, each with:
                from_minute (int), to_minute (int),
                players_in (list[str]), players_out (list[str]),
                nodes (list[dict]) — player_id, player, display_name, x, y, event_count,
                hull  (list[[float, float]]) — convex hull vertices.
        }
    """
    lineup_periods = _build_lineup_periods(events, team)

    open_play  = _open_play_mask(events)
    is_actor   = events["team"] == team
    in_poss    = events["possession_team"] == team
    has_loc    = events["location"].notna()
    has_player = events["player"].notna()

    base_mask = open_play & is_actor & in_poss & has_loc & has_player
    base_subset = events[base_mask].copy()

    result_periods: list[dict] = []

    for lp in lineup_periods:
        from_min  = lp["from_minute"]
        to_min    = lp["to_minute"]
        squad     = lp["players"]

        in_window = (base_subset["minute"] >= from_min) & (base_subset["minute"] < to_min)
        is_squad  = base_subset["player"].isin(squad)
        subset    = base_subset[in_window & is_squad]

        player_records: dict[str, dict] = {}

        for _, row in subset.iterrows():
            # Use player name as the stable key (player_id may be NaN for some types).
            pid = str(row["player"])
            period_half = int(row.get("period", 1))
            direction   = attack_dir_by_period.get(period_half, "right")
            raw_x, raw_y = float(row["location"][0]), float(row["location"][1])
            nx, ny = _normalize_xy(raw_x, raw_y, direction)

            if pid not in player_records:
                pid_val = row.get("player_id")
                int_pid = int(pid_val) if pid_val == pid_val else None
                player_name = str(row["player"])
                display_name = nicknames.get(int_pid, player_name) if int_pid is not None else player_name
                player_records[pid] = {
                    "player_id":    int_pid,
                    "player":       player_name,
                    "display_name": display_name,
                    "xs":           [],
                    "ys":           [],
                }
            player_records[pid]["xs"].append(nx)
            player_records[pid]["ys"].append(ny)

        nodes = []
        for rec in player_records.values():
            xs_arr = np.array(rec["xs"])
            ys_arr = np.array(rec["ys"])
            nodes.append({
                "player_id":    rec["player_id"],
                "player":       rec["player"],
                "display_name": rec["display_name"],
                "x":            round(float(xs_arr.mean()), 2),
                "y":            round(float(ys_arr.mean()), 2),
                "event_count":  len(xs_arr),
            })

        nodes.sort(key=lambda n: n["event_count"], reverse=True)
        hull = _compute_hull(nodes)

        result_periods.append({
            "from_minute": from_min,
            "to_minute":   to_min,
            "players_in":  lp["players_in"],
            "players_out": lp["players_out"],
            "nodes":       nodes,
            "hull":        hull,
        })

    return {"periods": result_periods}


def extract_off_ball(
    events,
    frame_lookup: dict,
    team: str,
    attack_dir_by_period: dict,
    bandwidth_yards: float,
    depth_percentile: int,
    cols: int,
    rows: int,
) -> dict:
    """Extract empirical off-ball shape from 360 frames for one team.

    Collects every 360 frame dot belonging to the analyzed team while the team
    is OUT of possession (open-play events only). Applies the teammate-boolean
    inversion: in each frame, teammate is relative to the ACTOR (the player
    who performed the event). When the actor is an opponent, teammate=True
    marks OPPONENTS and teammate=False marks OUR team. See module docstring.

    Coordinates are normalised so the team always attacks right. Computes:
    density grid (Gaussian KDE), centroid, thirds-spine, covariance ellipse,
    and a percentile depth line (where the team sits defensively).

    Args:
        events (pandas.DataFrame): Full match event DataFrame from sb.events().
        frame_lookup (dict[str, dict]): Event UUID → frame data from load_frames().
        team (str): Team name to analyze.
        attack_dir_by_period (dict[int, str]): Period → "right"/"left".
        bandwidth_yards (float): Gaussian KDE bandwidth in yards.
        depth_percentile (int): Percentile (0–100) for the depth line x value.
        cols (int): KDE grid columns.
        rows (int): KDE grid rows.

    Returns:
        dict: {
            "density_grid": {"cols", "rows", "values"},
            "centroid":     {"x", "y"},
            "thirds_spine": [{"third", "x", "y"}],
            "ellipse":      {"cx", "cy", "rx", "ry", "angle_deg"},
            "depth_line":   {"x", "percentile"}
        }
    """
    open_play = _open_play_mask(events)
    out_of_poss = events["possession_team"] != team

    # Only events that have a matching 360 frame.
    subset = events[open_play & out_of_poss].copy()

    all_xs: list[float] = []
    all_ys: list[float] = []

    for _, row in subset.iterrows():
        event_uuid = str(row["id"])
        if event_uuid not in frame_lookup:
            continue

        frame_data = frame_lookup[event_uuid]
        actor_team = str(row["team"])
        period = int(row.get("period", 1))
        direction = attack_dir_by_period.get(period, "right")

        # Teammate-boolean inversion: actor is opponent when actor_team != team.
        # When actor is opponent: teammate=True → opponent, teammate=False → our team.
        # When actor is our team (shouldn't happen in out-of-possession, but guard anyway):
        # teammate=True → our team.
        actor_is_opponent = (actor_team != team)

        for dot in frame_data["freeze_frame"]:
            is_our_dot = (not dot["teammate"]) if actor_is_opponent else dot["teammate"]
            if not is_our_dot:
                continue

            raw_x = float(dot["location"][0])
            raw_y = float(dot["location"][1])
            nx, ny = _normalize_xy(raw_x, raw_y, direction)
            all_xs.append(nx)
            all_ys.append(ny)

    xs = np.array(all_xs)
    ys = np.array(all_ys)

    density_grid = _compute_kde_grid(xs, ys, bandwidth_yards, cols, rows)
    centroid = {"x": round(float(xs.mean()), 2), "y": round(float(ys.mean()), 2)}
    thirds_spine = _compute_thirds_spine(xs, ys)
    ellipse = _compute_ellipse(xs, ys)
    depth_x = float(np.percentile(xs, depth_percentile))
    depth_line = {"x": round(depth_x, 2), "percentile": depth_percentile}

    return {
        "density_grid": density_grid,
        "centroid":     centroid,
        "thirds_spine": thirds_spine,
        "ellipse":      ellipse,
        "depth_line":   depth_line,
    }


def main() -> None:
    """Resolve the Euro 2024 Final, extract team shape for both teams, and write JSON.

    Output: src/footballd3/sample_data/team_shape_{match_id}_{team_slug}.json
    """
    bandwidth_yards = 8.0
    depth_percentile = 70
    cols = 24
    rows = 16

    print("Resolving Euro 2024 Final…")
    match_id = resolve_euro_2024_final()
    print(f"  match_id = {match_id}")

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

    print("Loading events…")
    events = sb.events(match_id=match_id)

    print("Loading 360 frames…")
    frame_lookup = load_frames(match_id)
    print(f"  {len(frame_lookup)} frames loaded")

    out_dir = Path(__file__).parents[2] / "src" / "footballd3" / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    lineups = sb.lineups(match_id=match_id)

    for team in [home_team, away_team]:
        print(f"\nProcessing {team}…")

        team_df = lineups.get(team)
        nicknames: dict[int, str] = {}
        if team_df is not None:
            for _, row in team_df.iterrows():
                nick = row.get("player_nickname")
                name = row["player_name"]
                nicknames[int(row["player_id"])] = nick if (pd.notna(nick) and nick) else name

        attack_dir = _attack_direction_by_period(events, team)
        print(f"  Attack direction by period: {attack_dir}")

        print("  Extracting on-ball shape…")
        on_ball = extract_on_ball(events, team, attack_dir, nicknames)
        print(f"  → {len(on_ball['periods'])} lineup periods")

        print("  Extracting off-ball shape…")
        off_ball = extract_off_ball(
            events, frame_lookup, team, attack_dir,
            bandwidth_yards=bandwidth_yards,
            depth_percentile=depth_percentile,
            cols=cols,
            rows=rows,
        )

        # Count total on-ball events across all lineup periods.
        on_event_count = sum(
            n["event_count"]
            for p in on_ball["periods"]
            for n in p["nodes"]
        )

        payload = {
            "on_ball":  on_ball,
            "off_ball": off_ball,
            "metadata": {
                "match_id":               match_id,
                "team":                   team,
                "competition":            competition,
                "match_label":            match_label,
                "on_ball_event_count":    on_event_count,
                "on_ball_period_count":   len(on_ball["periods"]),
                "off_ball_bandwidth_yards": bandwidth_yards,
                "off_ball_depth_percentile": depth_percentile,
                "off_ball_grid_cols":     cols,
                "off_ball_grid_rows":     rows,
                "phase_filter":           "open_play_only",
                "coordinate_system":      "statsbomb_120x80_normalised_attack_right",
                "coordinate_note":        (
                    "Coordinates are normalised so the team always attacks right "
                    "(increasing x). Raw StatsBomb events are flipped (x→120-x, "
                    "y→80-y) in periods where the team attacks left."
                ),
                "camera_caveat": (
                    "360 frames follow the ball; the visible subset of "
                    "out-of-possession positions is biased toward areas near the ball. "
                    "The camera artifact and the real defensive shape point the same "
                    "direction — they cannot be cleanly separated."
                ),
            },
        }

        team_slug = re.sub(r"[^a-z0-9]+", "_", team.lower()).strip("_")
        out_path = out_dir / f"team_shape_{match_id}_{team_slug}.json"

        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)

        print(f"  Wrote → {out_path}")


if __name__ == "__main__":
    main()
