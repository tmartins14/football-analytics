"""
derive_group_standings.py
-------------------------
Derives group standings for every World Cup group stage from 1930–2022.

For each team in each group, calculates:
  - Points (W=3, D=1, L=0; pre-1994 tournaments use W=2, D=1, L=0)
  - Goals for, goals against, goal difference
  - Group rank (by points, then goal diff, then goals for)

Note on 1950: The tournament had no knockout stage — a 'final round'
group of 4 replaced the semi-finals and final. The Fjelstul database
flags these as group_stage=1 with group_name='not applicable'. These
matches are included in the standings as a single group labelled
'Final Round'.

Run from the piece root:
    python scripts/derive_group_standings.py

Output:
    data/processed/group_standings.csv
"""

import pandas as pd
from pathlib import Path

PROCESSED = Path("data/processed")

# ---------------------------------------------------------------------------
# Points system changed in 1994 (3 points for a win, previously 2)
# ---------------------------------------------------------------------------
def points_for_win(year: int) -> int:
    return 3 if year >= 1994 else 2

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
print("Loading data...")
wc = pd.read_csv(PROCESSED / "wc_matches_clean.csv")
gs = wc[wc["group_stage"] == 1].copy()

# Normalise 1950 final round group name
gs["group_name"] = gs["group_name"].replace("not applicable", "Final Round")

# Extract year
gs["year"] = gs["tournament_id"].str.extract(r"(\d{4})").astype(int)

print(f"  Group stage matches: {len(gs)}")
print(f"  Tournaments: {sorted(gs['year'].unique())}")

# ---------------------------------------------------------------------------
# Derive standings
# For each match, record the result from both the home and away perspective,
# then aggregate per team per group per tournament.
# ---------------------------------------------------------------------------
records = []

for _, match in gs.iterrows():
    year          = match["year"]
    tournament_id = match["tournament_id"]
    group         = match["group_name"]
    home          = match["home_team_name"]
    away          = match["away_team_name"]
    home_goals    = match["home_team_score"]
    away_goals    = match["away_team_score"]
    win_pts       = points_for_win(year)

    if pd.isna(home_goals) or pd.isna(away_goals):
        continue

    home_goals = int(home_goals)
    away_goals = int(away_goals)

    if home_goals > away_goals:
        home_pts, away_pts = win_pts, 0
        home_w, away_w    = 1, 0
        home_d, away_d    = 0, 0
        home_l, away_l    = 0, 1
    elif home_goals < away_goals:
        home_pts, away_pts = 0, win_pts
        home_w, away_w    = 0, 1
        home_d, away_d    = 0, 0
        home_l, away_l    = 1, 0
    else:
        home_pts, away_pts = 1, 1
        home_w, away_w    = 0, 0
        home_d, away_d    = 1, 1
        home_l, away_l    = 0, 0

    records.append({
        "tournament_id": tournament_id,
        "year":          year,
        "group_name":    group,
        "team":          home,
        "played":        1,
        "won":           home_w,
        "drawn":         home_d,
        "lost":          home_l,
        "goals_for":     home_goals,
        "goals_against": away_goals,
        "points":        home_pts,
    })
    records.append({
        "tournament_id": tournament_id,
        "year":          year,
        "group_name":    group,
        "team":          away,
        "played":        1,
        "won":           away_w,
        "drawn":         away_d,
        "lost":          away_l,
        "goals_for":     away_goals,
        "goals_against": home_goals,
        "points":        away_pts,
    })

df = pd.DataFrame(records)

# ---------------------------------------------------------------------------
# Aggregate per team per group per tournament
# ---------------------------------------------------------------------------
standings = (
    df.groupby(["tournament_id", "year", "group_name", "team"])
    .agg(
        played        = ("played",        "sum"),
        won           = ("won",           "sum"),
        drawn         = ("drawn",         "sum"),
        lost          = ("lost",          "sum"),
        goals_for     = ("goals_for",     "sum"),
        goals_against = ("goals_against", "sum"),
        points        = ("points",        "sum"),
    )
    .reset_index()
)

standings["goal_diff"] = standings["goals_for"] - standings["goals_against"]

# ---------------------------------------------------------------------------
# Rank within each group
# Tiebreakers: points → goal_diff → goals_for
# ---------------------------------------------------------------------------
standings["group_rank"] = (
    standings
    .groupby(["tournament_id", "group_name"])[["points", "goal_diff", "goals_for"]]
    .rank(method="min", ascending=False)
    .max(axis=1)  # take the worst (highest) rank across tiebreakers — proper tiebreak below
)

# Proper multi-key rank
standings["group_rank"] = standings.groupby(
    ["tournament_id", "group_name"]
).apply(
    lambda g: g.sort_values(
        ["points", "goal_diff", "goals_for"], ascending=False
    ).assign(group_rank=range(1, len(g) + 1))["group_rank"]
).reset_index(level=[0, 1], drop=True)

standings = standings.sort_values(
    ["year", "group_name", "group_rank"]
).reset_index(drop=True)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
standings.to_csv(PROCESSED / "group_standings.csv", index=False)
print(f"\nWritten: data/processed/group_standings.csv  ({len(standings)} rows)")

# ---------------------------------------------------------------------------
# Sanity check — print 2022 standings
# ---------------------------------------------------------------------------
print("\n=== 2022 Group Standings (sample) ===")
s22 = standings[standings["year"] == 2022]
for group in sorted(s22["group_name"].unique())[:3]:
    print(f"\n{group}")
    print(
        s22[s22["group_name"] == group][
            ["group_rank", "team", "played", "won", "drawn",
             "lost", "goals_for", "goals_against", "goal_diff", "points"]
        ].to_string(index=False)
    )

print("\nDone.")