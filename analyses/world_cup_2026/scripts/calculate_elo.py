"""
calculate_elo.py
----------------
Calculates historical Elo ratings for all national teams using the full
international match history in results_clean.csv.

Follows the eloratings.net methodology:
  - All teams initialised at 1500
  - K-factor varies by match type
  - K adjusted upward for goal margin
  - Shootout results treated as draws for Elo purposes
  - Home advantage: +100 points added to home team's effective rating
    when match is not on neutral ground

Run from the piece root:
    python scripts/calculate_elo.py

Outputs:
    data/processed/elo_ratings.csv      — one row per match per team,
                                          with pre-match Elo for both sides
    data/processed/elo_at_wc_entry.csv  — each team's Elo at the start of
                                          each World Cup they appeared in
"""

import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RAW = Path("data/raw")
PROCESSED = Path("data/processed")
PROCESSED.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# K-factor map
#
# Based on eloratings.net methodology. Tournaments not explicitly listed
# default to K=30 (competitive non-major tournament) or K=20 (friendly).
# The is_friendly() function handles the friendly/competitive split.
# ---------------------------------------------------------------------------
K_BASE = {
    "FIFA World Cup":                      60,
    "FIFA World Cup qualification":        40,
    "Confederations Cup":                  50,
    "Copa América":                        50,
    "African Cup of Nations":              50,
    "AFC Asian Cup":                       50,
    "UEFA Euro":                           50,
    "UEFA Euro qualification":             40,
    "Copa América qualification":          40,
    "African Cup of Nations qualification":40,
    "AFC Asian Cup qualification":         40,
    "Gold Cup":                            40,
    "Gold Cup qualification":              40,
    "CONCACAF Nations League":             40,
    "UEFA Nations League":                 40,
    "Friendly":                            20,
}

FRIENDLY_KEYWORDS = {"friendly", "invitational", "four nations", "tournament",
                     "cup of champions", "kirin", "algarve", "cyprus",
                     "dubai", "china cup", "four-nation"}

def get_k_base(tournament: str) -> int:
    """Return base K-factor for a given tournament name."""
    if tournament in K_BASE:
        return K_BASE[tournament]
    t_lower = tournament.lower()
    if any(kw in t_lower for kw in FRIENDLY_KEYWORDS):
        return 20
    if "qualification" in t_lower or "qualifier" in t_lower:
        return 40
    return 30  # competitive non-major default

def k_goal_adjustment(goal_diff: int) -> float:
    """
    Multiply K by this factor based on absolute goal difference.
    eloratings.net formula:
      1 goal diff  → ×1.0
      2 goal diff  → ×1.5
      3 goal diff  → ×1.75
      4+ goal diff → ×1.75 + (n - 3) / 8
    """
    n = abs(goal_diff)
    if n <= 1:
        return 1.0
    elif n == 2:
        return 1.5
    elif n == 3:
        return 1.75
    else:
        return 1.75 + (n - 3) / 8

# ---------------------------------------------------------------------------
# Elo expected outcome
# ---------------------------------------------------------------------------
HOME_ADVANTAGE = 100  # Elo points added to home team when not neutral

def expected_score(rating_a: float, rating_b: float) -> float:
    """Expected score for team A against team B (0 to 1)."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print("Loading data...")
results = pd.read_csv(PROCESSED / "results_clean.csv", parse_dates=["date"])
shootouts = pd.read_csv(RAW / "shootouts.csv", parse_dates=["date"])

# Sort chronologically — critical for Elo to accumulate correctly
results = results.sort_values("date").reset_index(drop=True)

print(f"  Matches to process: {len(results):,}")
print(f"  Date range: {results['date'].min().date()} → {results['date'].max().date()}")

# ---------------------------------------------------------------------------
# Build shootout lookup
# Shootout matches are treated as draws for Elo purposes.
# Key: (date, home_team, away_team) → True if match went to shootout
# ---------------------------------------------------------------------------
shootout_keys = set()
for _, row in shootouts.iterrows():
    shootout_keys.add((row["date"], row["home_team"], row["away_team"]))
    # Also add reversed (some datasets flip home/away in shootouts)
    shootout_keys.add((row["date"], row["away_team"], row["home_team"]))

print(f"  Shootout matches: {len(shootouts):,}")

# ---------------------------------------------------------------------------
# Elo calculation
# ---------------------------------------------------------------------------
print("\nCalculating Elo ratings...")

ratings = {}   # team → current Elo rating
records = []   # one row per match, storing pre-match Elo for both teams

for idx, match in results.iterrows():
    home = match["home_team"]
    away = match["away_team"]
    home_score = match["home_score"]
    away_score = match["away_score"]
    tournament = match["tournament"]
    neutral = match["neutral"]
    date = match["date"]

    # Initialise teams if first appearance
    if home not in ratings:
        ratings[home] = 1500
    if away not in ratings:
        ratings[away] = 1500

    home_elo = ratings[home]
    away_elo = ratings[away]

    # Apply home advantage to effective ratings
    if neutral:
        home_elo_eff = home_elo
        away_elo_eff = away_elo
    else:
        home_elo_eff = home_elo + HOME_ADVANTAGE
        away_elo_eff = away_elo

    # Expected scores
    home_exp = expected_score(home_elo_eff, away_elo_eff)
    away_exp = 1 - home_exp

    # Actual scores — shootouts treated as draws
    is_shootout = (date, home, away) in shootout_keys
    if is_shootout:
        home_actual = 0.5
        away_actual = 0.5
    elif home_score > away_score:
        home_actual = 1.0
        away_actual = 0.0
    elif home_score < away_score:
        home_actual = 0.0
        away_actual = 1.0
    else:
        home_actual = 0.5
        away_actual = 0.5

    # K-factor
    k_base = get_k_base(tournament)
    goal_diff = abs(home_score - away_score)
    k = k_base * k_goal_adjustment(goal_diff)

    # Rating updates
    home_new = home_elo + k * (home_actual - home_exp)
    away_new = away_elo + k * (away_actual - away_exp)

    # Store pre-match record
    records.append({
        "date":            date,
        "tournament":      tournament,
        "neutral":         neutral,
        "home_team":       home,
        "away_team":       away,
        "home_score":      home_score,
        "away_score":      away_score,
        "is_shootout":     is_shootout,
        "home_elo_pre":    round(home_elo, 2),
        "away_elo_pre":    round(away_elo, 2),
        "home_elo_post":   round(home_new, 2),
        "away_elo_post":   round(away_new, 2),
        "elo_diff":        round(home_elo - away_elo, 2),
        "k_factor":        round(k, 2),
    })

    # Update ratings
    ratings[home] = home_new
    ratings[away] = away_new

print(f"  Done. {len(records):,} match records processed.")

# ---------------------------------------------------------------------------
# Save elo_ratings.csv
# ---------------------------------------------------------------------------
elo_df = pd.DataFrame(records)
elo_df.to_csv(PROCESSED / "elo_ratings.csv", index=False)
print(f"\nWritten: data/processed/elo_ratings.csv  ({len(elo_df):,} rows)")

# ---------------------------------------------------------------------------
# Build elo_at_wc_entry.csv
#
# For each team in each World Cup, find their Elo rating on the date of
# their first group stage match. We use wc_matches_clean.csv to identify
# which teams appeared in each tournament and their first match date.
# ---------------------------------------------------------------------------
print("\nBuilding WC entry Elo table...")

wc = pd.read_csv(PROCESSED / "wc_matches_clean.csv", parse_dates=["match_date"])

# Keep group stage only
wc_groups = wc[wc["group_stage"] == 1].copy()

# Get each team's first match date per tournament
home = wc_groups[["tournament_id", "match_date", "home_team_name"]].rename(
    columns={"home_team_name": "team"}
)
away = wc_groups[["tournament_id", "match_date", "away_team_name"]].rename(
    columns={"away_team_name": "team"}
)
appearances = pd.concat([home, away]).drop_duplicates()
first_match = (
    appearances.groupby(["tournament_id", "team"])["match_date"]
    .min()
    .reset_index()
    .rename(columns={"match_date": "first_match_date"})
)

# For each appearance, find pre-match Elo from elo_ratings.csv
# Strategy: look up the home_elo_pre or away_elo_pre on that exact date
elo_lookup = []
for _, row in first_match.iterrows():
    team = row["team"]
    date = row["first_match_date"]
    tournament_id = row["tournament_id"]

    # Find the match record for this team on this date
    match_as_home = elo_df[
        (elo_df["date"] == date) & (elo_df["home_team"] == team)
    ]
    match_as_away = elo_df[
        (elo_df["date"] == date) & (elo_df["away_team"] == team)
    ]

    if not match_as_home.empty:
        elo = match_as_home.iloc[0]["home_elo_pre"]
    elif not match_as_away.empty:
        elo = match_as_away.iloc[0]["away_elo_pre"]
    else:
        elo = None  # team not in results_clean (East Germany, Serbia & Montenegro)

    elo_lookup.append({
        "tournament_id":   tournament_id,
        "team":            team,
        "first_match_date": date,
        "elo_at_entry":    elo,
    })

elo_wc = pd.DataFrame(elo_lookup)

# Extract year from tournament_id for convenience
elo_wc["year"] = elo_wc["tournament_id"].str.extract(r"(\d{4})").astype(int)

missing = elo_wc["elo_at_entry"].isna().sum()
# Known exclusions — teams in wc_matches_clean.csv with no results_clean.csv
# match on their WC entry date:
#   East Germany          — 1974, dissolved, no results data
#   Yugoslavia            — 1998, banned 1992-1994, results data ends 1992
#   Serbia and Montenegro — 2006, not in results as combined entity
# These carry null Elo and are excluded from Elo-based analysis.
print(f"  Teams with no Elo rating (known exclusions): {missing}")
print(elo_wc[elo_wc["elo_at_entry"].isna()][["tournament_id", "team"]].to_string(index=False))

elo_wc.to_csv(PROCESSED / "elo_at_wc_entry.csv", index=False)
print(f"\nWritten: data/processed/elo_at_wc_entry.csv  ({len(elo_wc):,} rows)")
print("\nDone.")