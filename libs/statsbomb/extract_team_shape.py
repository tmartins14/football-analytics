"""Extract empirical team shape from StatsBomb events and 360 freeze-frame data.

Produces two separate measurements, intentionally using different methods:

ON-BALL (in-possession): event-based, identified by player. Mean position per
named player from that team's open-play events where possession_team == team.
Returns a tidy DataFrame with one row per player per lineup period.

OFF-BALL (out-of-possession): frame-based, anonymous. Pools 360 frame dots for
the analyzed team while the opponent has the ball (open play only). Returns an
aggregate dict: density grid, centroid, thirds-spine, covariance ellipse, and
a percentile-depth line. No player identities are assigned to the cloud.

OPEN-PLAY FILTER: play_pattern not in (From Corner, From Free Kick, From Goal
    Kick, From Kick Off, From Throw In). Transitions included.

COORDINATE FRAME: StatsBomb event and 360 freeze-frame coordinates are
    already consistently attack-right for both teams across both halves —
    mean shot x and mean goalkeeper event x cluster at the same end of the
    pitch in both periods (see DATA-SPEC-v2 §A). No period-based flip is
    applied. `_attack_direction_by_period` is kept only as a sanity check
    (`_assert_attacks_right`): if it ever detects "left" for this match, that
    assumption has broken and the output should not be trusted.

TEAMMATE-BOOLEAN INVERSION: in a 360 frame, `teammate` is relative to the
    actor (the player who performed the event), not the analyzed team. For
    out-of-possession frames the actor belongs to the opponent, so teammate=True
    marks OPPONENT players and teammate=False marks OUR players.

OPPONENT-ACTOR MIRRORING: a 360 freeze frame is in the frame of the event's
    actor. When the actor is the opponent, our players' dots arrive in the
    opponent's frame, where high x means near our own goal — pooling them
    with our own-actor dots unmirrored would average two different frames
    (DATA-SPEC-v2 §A). Off-ball dots from opponent-actor frames are mirrored
    (x → 120-x, y → 80-y) before pooling; own-actor dots are used as-is.
    Keeper dots are excluded from the off-ball pool entirely.

Public API:
    extract_team_shape_on_ball(match_id, team) -> pd.DataFrame
    extract_team_shape_off_ball(match_id, team, bandwidth_yards, depth_percentile, cols, rows) -> dict
    main()

DataFrame columns (extract_team_shape_on_ball):
    period_from_minute, period_to_minute, player_id, player, display_name, x, y, event_count

JSON output shape (team_shape_{match_id}_{team_slug}.json):
    {
      "on_ball": {
        "periods": [
          {
            "from_minute": int,
            "to_minute": int,
            "players_in": [str],
            "players_out": [str],
            "nodes": [{"player_id": int, "player": str, "display_name": str,
                       "x": float, "y": float, "event_count": int,
                       "lane_counts": {str: int}, "band_counts": {str: int}}],
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

Written to: data/euro-2024/{match_id}/team_shape_{team_slug}.json
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from scipy.stats import gaussian_kde
from statsbombpy import sb

from .tactical_definitions import BAND_EDGES, LANE_EDGES, band_for_x, lane_for_y
from .utils import (
    SET_PIECE_PLAY_PATTERNS,
    build_nickname_lookup,
    fetch_match_info,
    load_360_frames,
    open_play_mask,
    resolve_match,
)

SB_PITCH_WIDTH  = 120
SB_PITCH_HEIGHT = 80


def _attack_direction_by_period(events: pd.DataFrame, team: str) -> dict[int, str]:
    """Determine which direction the team attacks in each match period.

    Uses shot locations as the primary indicator: shots always happen in the
    attacking third, so mean shot x > 60 → team attacks right in that period.
    Falls back to mean x of in-possession located events when a period has no
    shots (e.g. goalless half with no attempts). Using all events (including
    defensive events) is unreliable when one team defends deeply.

    Args:
        events (pd.DataFrame): Full match event DataFrame from sb.events().
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


def _assert_attacks_right(attack_dir_by_period: dict[int, str], match_id: int, team: str) -> None:
    """Raise if any period's detected attack direction is not "right".

    StatsBomb event and 360 coordinates are already consistently in each
    team's own attack-right frame across both halves (see DATA-SPEC-v2 §A),
    so this extractor applies no period-based flip. This is a sanity check on
    that assumption, not a normalization step — a "left" result means the
    assumption has broken for this match and the output should not be
    trusted until that's investigated.

    Args:
        attack_dir_by_period (dict[int, str]): Period → "right"/"left", from
            `_attack_direction_by_period`.
        match_id (int): StatsBomb match ID, for the error message.
        team (str): Team name, for the error message.

    Raises:
        ValueError: If any period's direction is not "right".
    """
    bad = {period: direction for period, direction in attack_dir_by_period.items() if direction != "right"}
    if bad:
        raise ValueError(
            f"match {match_id}, team '{team}': _attack_direction_by_period returned "
            f"non-'right' for period(s) {bad} — the assumption that StatsBomb "
            "coordinates are already attack-right has broken for this match; "
            "investigate before trusting team_shape output."
        )


def _mirror_xy(x: float, y: float) -> tuple[float, float]:
    """Point-reflect a StatsBomb coordinate: x → 120-x, y → 80-y.

    Used to remap a 360 freeze-frame dot that arrived in an opponent actor's
    frame into the analysed team's own attack-right frame (DATA-SPEC-v2 §A).
    Not a period-based normalization — see the module docstring.

    Args:
        x (float): StatsBomb x coordinate (0–120).
        y (float): StatsBomb y coordinate (0–80).

    Returns:
        tuple[float, float]: The mirrored (x, y).
    """
    return SB_PITCH_WIDTH - x, SB_PITCH_HEIGHT - y


def _off_ball_dot_xy(dot: dict, actor_is_opponent: bool) -> tuple[float, float] | None:
    """Decide whether one 360 freeze-frame dot belongs in the off-ball pool.

    Excludes the goalkeeper and the opposing side's dots (teammate-boolean
    inversion applies — see the module docstring). Mirrors opponent-actor
    dots into the analysed team's own attack-right frame; own-actor dots are
    used as-is.

    Args:
        dot (dict): One `freeze_frame` entry: `location`, `teammate`,
            `actor`, `keeper`.
        actor_is_opponent (bool): Whether the event's actor belongs to the
            opposing team (so `teammate` is relative to them, not us).

    Returns:
        tuple[float, float] | None: The (x, y) to pool, or None if this dot
            is excluded (not our player, or the goalkeeper).
    """
    if dot.get("keeper", False):
        return None
    is_our_dot = (not dot["teammate"]) if actor_is_opponent else dot["teammate"]
    if not is_our_dot:
        return None
    raw_x = float(dot["location"][0])
    raw_y = float(dot["location"][1])
    if actor_is_opponent:
        return _mirror_xy(raw_x, raw_y)
    return raw_x, raw_y


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
        xs (np.ndarray): x coordinates of source dots (StatsBomb yards, 0–120).
        ys (np.ndarray): y coordinates of source dots (StatsBomb yards, 0–80).
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
        xs (np.ndarray): x coordinates in StatsBomb yards.
        ys (np.ndarray): y coordinates in StatsBomb yards.

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
        xs (np.ndarray): x coordinates in normalised StatsBomb yards.
        ys (np.ndarray): y coordinates.

    Returns:
        list[dict]: Up to 3 entries in order (defensive, middle, attacking),
            each with keys "third" (str), "x" (float), "y" (float).
            Thirds with no dots are omitted.
    """
    spine = []
    thresholds = [
        ("defensive", xs < 40),
        ("middle",    (xs >= 40) & (xs < 80)),
        ("attacking", xs >= 80),
    ]
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


def _build_lineup_periods(events: pd.DataFrame, team: str) -> list[dict]:
    """Build lineup windows for a team, separated by substitution events.

    Reads the Starting XI event to establish the opening roster, then reads
    Substitution events in chronological order and groups simultaneous subs
    (same minute) to avoid zero-width windows. Each returned entry covers the
    time between two lineup changes and carries the exact set of 11 players on
    the pitch during that window.

    Args:
        events (pd.DataFrame): Full match event DataFrame from sb.events().
        team (str): Team name to analyze.

    Returns:
        list[dict]: Ordered list of windows, each with:
            from_minute (int): First minute of the window (inclusive).
            to_minute   (int): First minute after the window (exclusive).
            players     (set[str]): Player names on the pitch in this window.
            players_in  (list[str]): Who joined at from_minute (all 11 for window 0).
            players_out (list[str]): Who left at from_minute (empty for window 0).

    Raises:
        ValueError: If no Starting XI event is found for the given team.
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


def _on_ball_periods(
    events: pd.DataFrame,
    team: str,
    nicknames: dict[int, str],
) -> list[dict]:
    """Compute on-ball player mean positions for each lineup period.

    Shared logic called by extract_team_shape_on_ball. Filters to open-play
    in-possession events for the team and computes, per player per lineup
    window: the mean (x, y), a per-touch lane/band bucket tally, and a convex
    hull of the window's nodes. Coordinates are used as-is — see the module
    docstring's COORDINATE FRAME note; the caller is responsible for calling
    `_assert_attacks_right` first.

    Args:
        events (pd.DataFrame): Full match event DataFrame.
        team (str): Team name to analyze.
        nicknames (dict[int, str]): player_id → display_name.

    Returns:
        list[dict]: One entry per lineup window with keys:
            from_minute, to_minute (int),
            players_in, players_out (list[str]),
            nodes (list[dict]): player_id, player, display_name, x, y,
                event_count, lane_counts (dict[str, int]), band_counts (dict[str, int]),
            hull  (list[[float, float]]).
    """
    lineup_periods = _build_lineup_periods(events, team)

    op_mask   = open_play_mask(events)
    is_actor  = events["team"] == team
    in_poss   = events["possession_team"] == team
    has_loc   = events["location"].notna()
    has_player = events["player"].notna()

    base_subset = events[op_mask & is_actor & in_poss & has_loc & has_player].copy()

    result_periods: list[dict] = []

    for lp in lineup_periods:
        from_min = lp["from_minute"]
        to_min   = lp["to_minute"]
        squad    = lp["players"]

        in_window = (base_subset["minute"] >= from_min) & (base_subset["minute"] < to_min)
        is_squad  = base_subset["player"].isin(squad)
        subset    = base_subset[in_window & is_squad]

        player_records: dict[str, dict] = {}

        for _, row in subset.iterrows():
            pid = str(row["player"])
            raw_x, raw_y = float(row["location"][0]), float(row["location"][1])

            if pid not in player_records:
                pid_val = row.get("player_id")
                int_pid = int(pid_val) if pid_val == pid_val else None
                player_name = str(row["player"])
                display_name = nicknames.get(int_pid, player_name) if int_pid is not None else player_name
                player_records[pid] = {
                    "player_id":    int_pid,
                    "player":       player_name,
                    "display_name": display_name,
                    "xs": [],
                    "ys": [],
                    "lane_counts": {label: 0 for label, _, _ in LANE_EDGES},
                    "band_counts": {label: 0 for label, _, _ in BAND_EDGES},
                }
            player_records[pid]["xs"].append(raw_x)
            player_records[pid]["ys"].append(raw_y)
            player_records[pid]["lane_counts"][lane_for_y(raw_y)] += 1
            player_records[pid]["band_counts"][band_for_x(raw_x)] += 1

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
                "lane_counts":  rec["lane_counts"],
                "band_counts":  rec["band_counts"],
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

    return result_periods


def extract_team_shape_on_ball(match_id: int, team: str) -> pd.DataFrame:
    """Extract empirical on-ball team shape as a tidy DataFrame.

    Builds lineup windows from Starting XI + Substitution events. For each
    window, filters to open-play in-possession events where the player is on
    the pitch and computes the mean (x, y) and lane/band touch counts per
    player. Returns one row per player per lineup period.

    Coordinates are used as-is — StatsBomb event coordinates are already
    consistently attack-right for both teams (see the module docstring's
    COORDINATE FRAME note). `_attack_direction_by_period` is used only as a
    sanity check that this still holds for this match.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name exactly as it appears in StatsBomb data (e.g. "Spain").

    Returns:
        pd.DataFrame: One row per player per lineup period with columns:
            period_from_minute (int): Period start minute (inclusive).
            period_to_minute (int): Period end minute (exclusive).
            player_id (int | None): StatsBomb player ID.
            player (str): Full player name.
            display_name (str): Resolved display name (nickname or full name).
            x, y (float): Mean position in StatsBomb 120×80 yards.
            event_count (int): Number of open-play in-possession events.
            lane_counts (dict[str, int]): Touch count per lane (5 keys).
            band_counts (dict[str, int]): Touch count per band (4 keys).
        Also sets df.attrs:
            periods_meta (list[dict]): Per-period hull + players_in/out for JSON reconstruction.
            competition, match_label (str).

    Raises:
        ValueError: If no Starting XI event is found for the given team, or
            if `_attack_direction_by_period` detects a direction other than
            "right" for any period (see `_assert_attacks_right`).
    """
    nicknames = build_nickname_lookup(match_id)
    events = sb.events(match_id=match_id)
    competition, _, match_label = fetch_match_info(match_id)

    attack_dir = _attack_direction_by_period(events, team)
    _assert_attacks_right(attack_dir, match_id, team)
    periods = _on_ball_periods(events, team, nicknames)

    records: list[dict] = []
    periods_meta: list[dict] = []

    for p in periods:
        for node in p["nodes"]:
            records.append({
                "period_from_minute": p["from_minute"],
                "period_to_minute":   p["to_minute"],
                "player_id":          node["player_id"],
                "player":             node["player"],
                "display_name":       node["display_name"],
                "x":                  node["x"],
                "y":                  node["y"],
                "event_count":        node["event_count"],
                "lane_counts":        node["lane_counts"],
                "band_counts":        node["band_counts"],
            })
        periods_meta.append({
            "from_minute": p["from_minute"],
            "to_minute":   p["to_minute"],
            "players_in":  p["players_in"],
            "players_out": p["players_out"],
            "hull":        p["hull"],
        })

    df = pd.DataFrame(records)
    df.attrs["periods_meta"]  = periods_meta
    df.attrs["competition"]   = competition
    df.attrs["match_label"]   = match_label
    return df


def extract_team_shape_off_ball(
    match_id: int,
    team: str,
    bandwidth_yards: float = 8.0,
    depth_percentile: int = 70,
    cols: int = 24,
    rows: int = 16,
) -> dict:
    """Extract empirical off-ball team shape from 360 freeze frames.

    Collects every 360 frame dot belonging to the analyzed team while the team
    is OUT of possession (open-play events only). Applies teammate-boolean
    inversion: when the actor is an opponent, teammate=True marks opponents and
    teammate=False marks the analyzed team. Excludes the goalkeeper, and
    mirrors dots from opponent-actor frames into the team's own attack-right
    frame before pooling (see `_off_ball_dot_xy` and the module docstring's
    OPPONENT-ACTOR MIRRORING note).

    Computes: density grid (Gaussian KDE), centroid, thirds-spine, covariance
    ellipse, and a percentile depth line.

    Args:
        match_id (int): StatsBomb match ID.
        team (str): Team name exactly as it appears in StatsBomb data.
        bandwidth_yards (float): Gaussian KDE bandwidth in yards. Default: 8.0.
        depth_percentile (int): Percentile (0–100) for the depth line x value. Default: 70.
        cols (int): KDE grid columns. Default: 24.
        rows (int): KDE grid rows. Default: 16.

    Returns:
        dict: {
            "density_grid": {"cols", "rows", "values"},
            "centroid":     {"x", "y"},
            "thirds_spine": [{"third", "x", "y"}],
            "ellipse":      {"cx", "cy", "rx", "ry", "angle_deg"},
            "depth_line":   {"x", "percentile"}
        }

    Raises:
        ValueError: If fewer than 2 frame dots are found for the team, or if
            `_attack_direction_by_period` detects a direction other than
            "right" for any period (see `_assert_attacks_right`).
    """
    events = sb.events(match_id=match_id)
    frame_lookup = load_360_frames(match_id)
    attack_dir = _attack_direction_by_period(events, team)
    _assert_attacks_right(attack_dir, match_id, team)

    op_mask    = open_play_mask(events)
    out_of_poss = events["possession_team"] != team
    subset = events[op_mask & out_of_poss].copy()

    all_xs: list[float] = []
    all_ys: list[float] = []

    for _, row in subset.iterrows():
        event_uuid = str(row["id"])
        if event_uuid not in frame_lookup:
            continue

        frame_data  = frame_lookup[event_uuid]
        actor_team  = str(row["team"])

        # Teammate-boolean inversion: actor is opponent when actor_team != team.
        # When actor is opponent: teammate=True → opponent, teammate=False → our team.
        actor_is_opponent = (actor_team != team)

        for dot in frame_data["freeze_frame"]:
            xy = _off_ball_dot_xy(dot, actor_is_opponent)
            if xy is None:
                continue
            all_xs.append(xy[0])
            all_ys.append(xy[1])

    xs = np.array(all_xs)
    ys = np.array(all_ys)

    density_grid = _compute_kde_grid(xs, ys, bandwidth_yards, cols, rows)
    centroid     = {"x": round(float(xs.mean()), 2), "y": round(float(ys.mean()), 2)}
    thirds_spine = _compute_thirds_spine(xs, ys)
    ellipse      = _compute_ellipse(xs, ys)
    depth_x      = float(np.percentile(xs, depth_percentile))
    depth_line   = {"x": round(depth_x, 2), "percentile": depth_percentile}

    return {
        "density_grid": density_grid,
        "centroid":     centroid,
        "thirds_spine": thirds_spine,
        "ellipse":      ellipse,
        "depth_line":   depth_line,
    }


def main(
    match_id: int | None = None,
    out_dir: Path | None = None,
    teams: list[str] | None = None,
) -> None:
    """Extract on-ball and off-ball team shape for a match and write JSON.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.
        teams (list[str] | None): Teams to extract; defaults to both teams in the match.

    Output: {out_dir}/team_shape_{team_slug}.json
    """
    bandwidth_yards  = 8.0
    depth_percentile = 70
    cols = 24
    rows = 16

    if match_id is None:
        print("Resolving Euro 2024 Final…")
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    print(f"  match_id = {match_id}")

    competition, _, match_label = fetch_match_info(match_id)

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

    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    for team in teams:
        print(f"\nProcessing {team}…")

        print("  Extracting on-ball shape…")
        on_df = extract_team_shape_on_ball(match_id, team)
        periods_meta = on_df.attrs["periods_meta"]
        print(f"  → {len(periods_meta)} lineup period(s)")

        # Reconstruct nested on_ball dict from the tidy DataFrame + attrs.
        on_ball_periods: list[dict] = []
        for pm in periods_meta:
            group = on_df[
                (on_df["period_from_minute"] == pm["from_minute"])
                & (on_df["period_to_minute"] == pm["to_minute"])
            ]
            nodes = group.drop(columns=["period_from_minute", "period_to_minute"]).to_dict(
                orient="records"
            )
            on_ball_periods.append({
                "from_minute": pm["from_minute"],
                "to_minute":   pm["to_minute"],
                "players_in":  pm["players_in"],
                "players_out": pm["players_out"],
                "nodes":       nodes,
                "hull":        pm["hull"],
            })
            print(f"    {pm['from_minute']}'–{pm['to_minute']}': {len(nodes)} players")

        print("  Extracting off-ball shape…")
        off_ball = extract_team_shape_off_ball(
            match_id, team,
            bandwidth_yards=bandwidth_yards,
            depth_percentile=depth_percentile,
            cols=cols,
            rows=rows,
        )

        on_event_count = int(on_df["event_count"].sum())

        payload = {
            "on_ball":  {"periods": on_ball_periods},
            "off_ball": off_ball,
            "metadata": {
                "match_id":                  match_id,
                "team":                      team,
                "competition":               competition,
                "match_label":               match_label,
                "on_ball_event_count":       on_event_count,
                "on_ball_period_count":      len(on_ball_periods),
                "off_ball_bandwidth_yards":  bandwidth_yards,
                "off_ball_depth_percentile": depth_percentile,
                "off_ball_grid_cols":        cols,
                "off_ball_grid_rows":        rows,
                "phase_filter":              "open_play_only",
                "coordinate_system":         "statsbomb_120x80_normalised_attack_right",
                "coordinate_note": (
                    "StatsBomb event and 360 freeze-frame coordinates are already "
                    "in each team's own attack-right frame across both halves; no "
                    "period-based flip is applied. Off-ball 360 dots from "
                    "opponent-actor frames are mirrored (x→120-x, y→80-y) into "
                    "the analysed team's frame before pooling; own-actor dots are "
                    "used as-is, and the goalkeeper is excluded."
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
        out_path = out_dir / f"team_shape_{team_slug}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"  Wrote → {out_path}")


if __name__ == "__main__":
    main()
