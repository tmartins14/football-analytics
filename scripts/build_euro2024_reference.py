"""Build DATA-SPEC-v3's Euro 2024 reference data (Part 2).

Writes two files to data/euro-2024/reference/:

    reference_distributions.json  - tercile cut points for ppda, block_height
        and defensive_action_height, computed across all 51 Euro 2024
        matches' already-committed extractor output (see
        libs/statsbomb/reference_distributions.py).
    xt_grid_v1.json                - a 16x12 expected-threat grid fitted with
        socceraction.xthreat on SPADL actions converted from every Euro 2024
        match's raw events. This step hits the network (fetches all 51
        matches' events via socceraction's StatsBombLoader) and can take
        several minutes.

Run from the repo root:
    uv run python scripts/build_euro2024_reference.py [--skip-xt] [--skip-reference]
"""

import argparse
import json
import sys
import traceback
from datetime import date
from pathlib import Path

import pandas as pd
from statsbombpy import sb

sys.path.insert(0, str(Path(__file__).parents[1] / "libs"))

from statsbomb.reference_distributions import main as build_reference_distributions_main

COMPETITION_ID = 55
SEASON_ID = 282
XT_GRID_L = 16
XT_GRID_W = 12
OUT_DIR = Path(__file__).parents[1] / "data" / "euro-2024" / "reference"


def _undo_away_team_flip(actions: pd.DataFrame, home_team_id: int) -> pd.DataFrame:
    """Undo `convert_to_actions`'s home/away coordinate flip for StatsBomb data.

    `socceraction.spadl.statsbomb.convert_to_actions` unconditionally flips
    the away team's x/y so "home always attacks right" — correct for a
    provider whose raw coordinates are physically pitch-fixed, but StatsBomb's
    own events (confirmed empirically: both teams' shots cluster at the same
    end in both periods, via `loader.events()`, before any SPADL conversion)
    are already per-team-attack-right normalized. Applying `convert_to_actions`
    as-is therefore double-flips every away-team action in the match, putting
    their legitimate near-goal actions near the *other* goal instead — verified
    directly on match 3943043: England (away) shots averaged `start_x=13.75`
    (reads as deep in their own box) before this fix, `91.25` after, matching
    Spain's (home) `92.94`. Re-applies the exact same flip to away-team rows,
    which cancels out and restores the original per-team-normalized frame
    `convert_to_actions` needs as an *input*, not what it should apply again.

    Args:
        actions (pd.DataFrame): Output of `convert_to_actions`, for one match.
        home_team_id (int): The same `home_team_id` passed to `convert_to_actions`.

    Returns:
        pd.DataFrame: `actions` with the away team's coordinates restored.
    """
    import socceraction.spadl.config as spadlconfig

    away_idx = (actions["team_id"] != home_team_id).values
    fixed = actions.copy()
    for col in ("start_x", "end_x"):
        fixed.loc[away_idx, col] = spadlconfig.field_length - fixed.loc[away_idx, col]
    for col in ("start_y", "end_y"):
        fixed.loc[away_idx, col] = spadlconfig.field_width - fixed.loc[away_idx, col]
    return fixed


def _fit_xt_grid() -> None:
    """Fit socceraction's ExpectedThreat model on all Euro 2024 matches and write JSON.

    Fetches each match's events via `socceraction.data.statsbomb.StatsBombLoader`
    (not `statsbombpy`'s `sb.events()` — that DataFrame's flattened schema
    isn't compatible with `socceraction.spadl.statsbomb.convert_to_actions`,
    which needs the loader's own nested-`extra` schema). A single match whose
    conversion raises is logged and skipped rather than aborting the whole fit.
    See `_undo_away_team_flip` for why its output needs a correction before
    use — `convert_to_actions` assumes a coordinate convention StatsBomb's
    own data doesn't use.

    Output: data/euro-2024/reference/xt_grid_v1.json
    """
    import socceraction.spadl.statsbomb as sbspadl
    import socceraction.xthreat as xt
    from socceraction.data.statsbomb import StatsBombLoader

    loader = StatsBombLoader(getter="remote")
    games = loader.games(COMPETITION_ID, SEASON_ID)

    all_actions = []
    skipped: list[dict] = []
    for _, row in games.iterrows():
        game_id = int(row["game_id"])
        home_team_id = int(row["home_team_id"])
        try:
            events = loader.events(game_id)
            actions = sbspadl.convert_to_actions(events, home_team_id=home_team_id)
            actions = _undo_away_team_flip(actions, home_team_id)
            actions["game_id"] = game_id
            all_actions.append(actions)
            print(f"  [{game_id}] {len(actions)} SPADL actions")
        except Exception as exc:
            print(f"  [{game_id}] SKIPPED: {exc}")
            skipped.append({"match_id": game_id, "reason": str(exc)})
            traceback.print_exc()

    actions_df = pd.concat(all_actions, ignore_index=True)
    match_count = len(all_actions)
    print(f"Fitting ExpectedThreat({XT_GRID_L}x{XT_GRID_W}) on {len(actions_df)} actions "
          f"from {match_count} matches ({len(skipped)} skipped)…")

    model = xt.ExpectedThreat(l=XT_GRID_L, w=XT_GRID_W)
    model.fit(actions_df)

    payload = {
        "grid": {
            "l": XT_GRID_L,
            "w": XT_GRID_W,
            "xT": model.xT.tolist(),
        },
        "metadata": {
            "match_count": match_count,
            "skipped_matches": skipped,
            "fit_date": date.today().isoformat(),
            "source": "socceraction.xthreat.ExpectedThreat",
            "competition": "UEFA Euro 2024",
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "xt_grid_v1.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote xT grid ({match_count} matches, {len(skipped)} skipped) → {out_path}")


def main() -> None:
    """Parse CLI args and build reference_distributions.json and/or xt_grid_v1.json.

    Raises:
        SystemExit: Propagated if either build step raises unhandled.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-xt", action="store_true", help="Skip the xT grid fit.")
    parser.add_argument("--skip-reference", action="store_true", help="Skip the tercile reference build.")
    args = parser.parse_args()

    if not args.skip_reference:
        print("Building reference_distributions.json…")
        build_reference_distributions_main()

    if not args.skip_xt:
        print("\nFitting xt_grid_v1.json…")
        _fit_xt_grid()


if __name__ == "__main__":
    main()
