"""Batch extractor for all UEFA Euro 2024 matches.

Fetches the full match list from the StatsBomb open data API and extracts
the following files into data/euro-2024/{match_id}/ for each match:

    shots.json
    match_stats.json
    momentum.json          (requires xt_actions.json — xt runs first)
    goal_animation.json
    xt_actions.json
    pass_network_{team}.json   (both teams)
    formation_{team_slug}.json (both teams)
    team_shape_{team_slug}.json (both teams)
    freeze_frames_goals.json
    convex_hull_goals.json

The shared xt_grid.json is written to data/ once (first match only).

Run from the repo root:
    uv run python scripts/extract_euro2024.py

The script is idempotent: a match directory whose match_stats.json already
exists is skipped unless --force is passed.

Usage:
    uv run python scripts/extract_euro2024.py [--force] [--match-id ID]
"""

import argparse
import sys
import traceback
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parents[1] / "libs"))

from statsbombpy import sb

from statsbomb.extract_shots import main as shots_main
from statsbomb.extract_match_stats import main as match_stats_main
from statsbomb.extract_xt import main as xt_main
from statsbomb.extract_momentum import main as momentum_main
from statsbomb.extract_goal_animation import main as goal_anim_main
from statsbomb.extract_pass_network import main as pass_network_main
from statsbomb.extract_formation import main as formation_main
from statsbomb.extract_team_shape import main as team_shape_main
from statsbomb.extract_freeze_frame import main as freeze_frame_main
from statsbomb.extract_convex_hull import main as convex_hull_main

COMPETITION_ID = 55   # UEFA Euro
SEASON_ID = 282       # 2024
DATA_ROOT = Path(__file__).parents[1] / "data" / "euro-2024"


def _extract_match(match_id: int, home_team: str, away_team: str, force: bool) -> None:
    """Run all extractors for a single match.

    Args:
        match_id (int): StatsBomb match ID.
        home_team (str): Home team name from StatsBomb metadata.
        away_team (str): Away team name from StatsBomb metadata.
        force (bool): Re-extract even if output already exists.
    """
    out_dir = DATA_ROOT / str(match_id)
    teams = [home_team, away_team]

    if not force and (out_dir / "match_stats.json").exists():
        print(f"  [skip] {match_id} already extracted")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[{match_id}] {home_team} vs {away_team}")

    # xt must run before momentum (momentum reads xt_actions.json).
    steps = [
        ("shots",          lambda: shots_main(match_id, out_dir)),
        ("xt",             lambda: xt_main(match_id, out_dir)),
        ("momentum",       lambda: momentum_main(match_id, out_dir)),
        ("goal_animation", lambda: goal_anim_main(match_id, out_dir)),
        ("match_stats",    lambda: match_stats_main(match_id, out_dir)),
        ("pass_network",   lambda: pass_network_main(match_id, out_dir, teams)),
        ("formation",      lambda: formation_main(match_id, out_dir, teams)),
        ("team_shape",     lambda: team_shape_main(match_id, out_dir, teams)),
        ("freeze_frames",  lambda: freeze_frame_main(match_id, out_dir)),
        ("convex_hull",    lambda: convex_hull_main(match_id, out_dir)),
    ]

    for name, fn in steps:
        try:
            print(f"  {name}…", end=" ", flush=True)
            fn()
            print("ok")
        except Exception:
            print("FAILED")
            traceback.print_exc()


def main() -> None:
    """Parse CLI args and run batch extraction for all Euro 2024 matches.

    Exits with code 1 if any match extraction raises an unhandled error.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true",
        help="Re-extract matches that already have output files."
    )
    parser.add_argument(
        "--match-id", type=int, default=None,
        help="Extract only this match ID instead of the full tournament."
    )
    args = parser.parse_args()

    matches = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)
    if args.match_id is not None:
        matches = matches[matches["match_id"] == args.match_id]
        if matches.empty:
            print(f"Match ID {args.match_id} not found in Euro 2024.", file=sys.stderr)
            sys.exit(1)

    print(f"Euro 2024 — {len(matches)} match(es) to process")
    print(f"Output root: {DATA_ROOT}\n")

    for _, row in matches.iterrows():
        _extract_match(
            match_id=int(row["match_id"]),
            home_team=str(row["home_team"]),
            away_team=str(row["away_team"]),
            force=args.force,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
