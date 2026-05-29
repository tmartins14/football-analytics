"""
calculate_cis.py
----------------
Calculates the Competitive Intensity Score (CIS) for every World Cup
group stage match from 1930 to 2022.

CIS measures how competitive a match was, accounting for both the
scoreline and the pre-match Elo gap between the two sides. A high CIS
means a close match between evenly rated teams. A low CIS means a
dominant result between unevenly rated teams.

Formula:
    CIS = (1 - scoreline_component) * elo_weight

Where:
    scoreline_component = |goal_diff| / MAX_GOAL_DIFF (capped at 1.0)
    elo_weight          = normalised inverse of pre-match Elo gap,
                          scaled to [ELO_WEIGHT_MIN, ELO_WEIGHT_MAX]

A CIS of 1.0 = maximum intensity (0-0 or 1-0 between equal teams)
A CIS of 0.0 = minimum intensity (large scoreline, large Elo gap)

Run from the piece root:
    python scripts/calculate_cis.py

Outputs:
    data/processed/cis_by_match.csv  — one row per group stage match
                                       with CIS and component values
    data/processed/cis_by_tournament.csv — mean CIS per tournament
                                           for trend analysis
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROCESSED = Path("data/processed")

# ---------------------------------------------------------------------------
# CIS parameters
#
# MAX_GOAL_DIFF: scorelines at or above this are treated as maximum
# blowouts. Set to the 95th percentile of historical group stage goal
# differentials (derived from the data: 4 goals).
#
# ELO_WEIGHT range: scales how much the Elo gap modifies the CIS.
# A match between equals (0 Elo gap) gets weight ELO_WEIGHT_MAX.
# A match with a very large gap gets weight ELO_WEIGHT_MIN.
# This means a 2-0 between equals scores higher than a 2-0 between
# a strong favourite and a heavy underdog.
#
# ELO_GAP_CAP: Elo gaps beyond this are all treated as maximum mismatch.
# Set to the 95th percentile of observed group stage Elo gaps.
# ---------------------------------------------------------------------------
MAX_GOAL_DIFF   = 4      # 95th percentile of historical group stage goal diffs
ELO_WEIGHT_MIN  = 0.5    # weight applied to maximum Elo mismatch matches
ELO_WEIGHT_MAX  = 1.0    # weight applied to perfectly even matches
ELO_GAP_CAP     = None   # derived from data below (95th percentile)

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
print("Loading data...")
wc  = pd.read_csv(PROCESSED / "wc_matches_clean.csv", parse_dates=["match_date"])
elo = pd.read_csv(PROCESSED / "elo_at_wc_entry.csv")

# Group stage only
gs = wc[wc["group_stage"] == 1].copy()
print(f"  Group stage matches: {len(gs)}")

# ---------------------------------------------------------------------------
# Merge Elo ratings onto matches
# ---------------------------------------------------------------------------
elo_home = elo[["tournament_id", "team", "elo_at_entry"]].rename(
    columns={"team": "home_team_name", "elo_at_entry": "home_elo"}
)
elo_away = elo[["tournament_id", "team", "elo_at_entry"]].rename(
    columns={"team": "away_team_name", "elo_at_entry": "away_elo"}
)

gs = gs.merge(elo_home, on=["tournament_id", "home_team_name"], how="left")
gs = gs.merge(elo_away, on=["tournament_id", "away_team_name"], how="left")

has_elo = gs[["home_elo", "away_elo"]].notna().all(axis=1)
print(f"  Matches with full Elo data: {has_elo.sum()} / {len(gs)}")
print(f"  Matches excluded (known exclusions — no Elo): {(~has_elo).sum()}")

# ---------------------------------------------------------------------------
# Derive ELO_GAP_CAP from data (95th percentile of observed Elo gaps)
# ---------------------------------------------------------------------------
gs["elo_gap"] = (gs["home_elo"] - gs["away_elo"]).abs()
ELO_GAP_CAP = float(np.percentile(gs["elo_gap"].dropna(), 95))
print(f"\nDerived parameters:")
print(f"  MAX_GOAL_DIFF : {MAX_GOAL_DIFF} (95th percentile of goal differentials)")
print(f"  ELO_GAP_CAP   : {ELO_GAP_CAP:.1f} (95th percentile of group stage Elo gaps)")

# ---------------------------------------------------------------------------
# Calculate CIS
# ---------------------------------------------------------------------------
gs["goal_diff"] = (gs["home_team_score"] - gs["away_team_score"]).abs()

# Scoreline component: 0 = draw, 1 = maximum blowout
gs["scoreline_component"] = (gs["goal_diff"] / MAX_GOAL_DIFF).clip(upper=1.0)

# Elo weight: 1.0 = perfectly even, ELO_WEIGHT_MIN = maximum mismatch
# Normalise gap to [0, 1] then invert and rescale to [ELO_WEIGHT_MIN, ELO_WEIGHT_MAX]
gs["elo_gap_norm"] = (gs["elo_gap"] / ELO_GAP_CAP).clip(upper=1.0)
gs["elo_weight"] = ELO_WEIGHT_MAX - gs["elo_gap_norm"] * (ELO_WEIGHT_MAX - ELO_WEIGHT_MIN)

# CIS: high = competitive, low = mismatch
gs["cis"] = (1 - gs["scoreline_component"]) * gs["elo_weight"]

# Round for readability
for col in ["home_elo", "away_elo", "elo_gap", "elo_gap_norm",
            "elo_weight", "scoreline_component", "cis"]:
    gs[col] = gs[col].round(4)

# Derive year from tournament_id
gs["year"] = gs["tournament_id"].str.extract(r"(\d{4})").astype(int)

# ---------------------------------------------------------------------------
# Select output columns
# ---------------------------------------------------------------------------
cis_output = gs[[
    "tournament_id",
    "tournament_name",
    "year",
    "match_id",
    "match_date",
    "group_name",
    "home_team_name",
    "away_team_name",
    "home_team_score",
    "away_team_score",
    "goal_diff",
    "home_elo",
    "away_elo",
    "elo_gap",
    "scoreline_component",
    "elo_weight",
    "cis",
]].copy()

# ---------------------------------------------------------------------------
# Save cis_by_match.csv
# ---------------------------------------------------------------------------
cis_output.to_csv(PROCESSED / "cis_by_match.csv", index=False)
print(f"\nWritten: data/processed/cis_by_match.csv  ({len(cis_output)} rows)")

# ---------------------------------------------------------------------------
# Build cis_by_tournament.csv
# Excludes matches with missing Elo (known exclusions)
# ---------------------------------------------------------------------------
cis_valid = cis_output.dropna(subset=["cis"])

tournament_stats = (
    cis_valid.groupby(["tournament_id", "year"])
    .agg(
        matches          = ("cis", "count"),
        mean_cis         = ("cis", "mean"),
        median_cis       = ("cis", "median"),
        std_cis          = ("cis", "std"),
        mean_goal_diff   = ("goal_diff", "mean"),
        mean_elo_gap     = ("elo_gap", "mean"),
        draw_rate        = ("goal_diff", lambda x: (x == 0).mean()),
    )
    .reset_index()
    .sort_values("year")
)

for col in ["mean_cis", "median_cis", "std_cis", "mean_goal_diff",
            "mean_elo_gap", "draw_rate"]:
    tournament_stats[col] = tournament_stats[col].round(4)

tournament_stats.to_csv(PROCESSED / "cis_by_tournament.csv", index=False)
print(f"Written: data/processed/cis_by_tournament.csv  ({len(tournament_stats)} rows)")

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print("\n=== CIS summary by tournament ===")
print(tournament_stats[["year", "matches", "mean_cis", "mean_goal_diff",
                          "mean_elo_gap", "draw_rate"]].to_string(index=False))

print("\n=== Top 10 most competitive group stage matches ===")
print(cis_valid.nlargest(10, "cis")[
    ["year", "home_team_name", "away_team_name",
     "home_team_score", "away_team_score", "elo_gap", "cis"]
].to_string(index=False))

print("\n=== Top 10 least competitive group stage matches ===")
print(cis_valid.nsmallest(10, "cis")[
    ["year", "home_team_name", "away_team_name",
     "home_team_score", "away_team_score", "elo_gap", "cis"]
].to_string(index=False))

print("\nDone.")