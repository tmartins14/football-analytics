"""
normalize_team_names.py
-----------------------
Normalises team names across world_cup_matches.csv and results.csv so both
datasets use a single consistent name per footballing entity.

Principle: results.csv is the Elo source, so its names are canonical.
All world_cup_matches.csv names are mapped to match results.csv exactly.

Run from the piece root:
    python scripts/normalize_team_names.py

Outputs:
    data/processed/wc_matches_clean.csv  — world_cup_matches.csv, men's
                                           tournaments only, normalised names
    data/processed/results_clean.csv     — results.csv with normalised names
    data/processed/name_audit.txt        — audit log of all substitutions made
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
# Men's tournament IDs (excludes women's tournaments in the Fjelstul dataset)
# ---------------------------------------------------------------------------
MENS_TOURNAMENT_IDS = {
    "WC-1930", "WC-1934", "WC-1938", "WC-1950", "WC-1954", "WC-1958",
    "WC-1962", "WC-1966", "WC-1970", "WC-1974", "WC-1978", "WC-1982",
    "WC-1986", "WC-1990", "WC-1994", "WC-1998", "WC-2002", "WC-2006",
    "WC-2010", "WC-2014", "WC-2018", "WC-2022",
}

# ---------------------------------------------------------------------------
# Normalisation map for world_cup_matches.csv
#
# Keys   = names as they appear in world_cup_matches.csv (Fjelstul database)
# Values = canonical names as used in results.csv
#
# Germany note: 'West Germany' maps to 'Germany' — the Elo lineage of the
# modern German national team runs through West Germany.
# 'East Germany' has no successor in results.csv and is kept as-is.
#
# Known exclusions (retained as-is, no Elo rating will be assigned):
#   'East Germany'         — 1974 tournament, 6 matches
#   'Serbia and Montenegro'— 2006 tournament, 3 matches
# ---------------------------------------------------------------------------
WC_TO_CANONICAL = {
    "West Germany":          "Germany",
    "Soviet Union":          "Russia",
    "Zaire":                 "DR Congo",
    "Dutch East Indies":     "Indonesia",
    "China":                 "China PR",
}

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
print("Loading raw data...")
wc = pd.read_csv(RAW / "world_cup_matches.csv")
results = pd.read_csv(RAW / "results.csv")

# ---------------------------------------------------------------------------
# Step 1: Filter world_cup_matches.csv to men's tournaments only
# ---------------------------------------------------------------------------
total_before = len(wc)
wc = wc[wc["tournament_id"].isin(MENS_TOURNAMENT_IDS)].copy()
print(f"Filtered to men's tournaments: {total_before} → {len(wc)} rows")

# ---------------------------------------------------------------------------
# Step 2: Strip whitespace
# ---------------------------------------------------------------------------
wc["home_team_name"] = wc["home_team_name"].str.strip()
wc["away_team_name"] = wc["away_team_name"].str.strip()
results["home_team"] = results["home_team"].str.strip()
results["away_team"] = results["away_team"].str.strip()

# ---------------------------------------------------------------------------
# Step 3: Apply normalisation map to world_cup_matches.csv
# ---------------------------------------------------------------------------
audit_lines = ["=== world_cup_matches.csv name substitutions ===\n"]
substitution_counts = {}

for col in ["home_team_name", "away_team_name"]:
    for original, canonical in WC_TO_CANONICAL.items():
        mask = wc[col] == original
        count = mask.sum()
        if count > 0:
            wc.loc[mask, col] = canonical
            key = f"{original} → {canonical}"
            substitution_counts[key] = substitution_counts.get(key, 0) + count

for sub, count in sorted(substitution_counts.items()):
    line = f"  {sub}  ({count} rows)"
    print(line)
    audit_lines.append(line + "\n")

# ---------------------------------------------------------------------------
# Step 4: Cross-check — find any WC team names still missing from results.csv
# ---------------------------------------------------------------------------
teams_wc = (
    set(wc["home_team_name"].dropna().unique())
    | set(wc["away_team_name"].dropna().unique())
)
teams_res = (
    set(results["home_team"].dropna().unique())
    | set(results["away_team"].dropna().unique())
)

still_missing = sorted(teams_wc - teams_res)
audit_lines.append("\n=== WC teams unmatched in results.csv after normalisation ===\n")

if still_missing:
    print("\n⚠️  Teams still unmatched after normalisation:")
    for t in still_missing:
        print(f"  {repr(t)}")
        audit_lines.append(f"  {repr(t)}\n")
else:
    msg = "  All WC teams successfully matched. ✓"
    print(f"\n{msg}")
    audit_lines.append(msg + "\n")

# ---------------------------------------------------------------------------
# Step 5: Document known exclusions
# ---------------------------------------------------------------------------
audit_lines.append("""
=== Known exclusions (not errors) ===

  'East Germany' — appeared at the 1974 World Cup. Has no successor entity
  in results.csv. Retained as-is. Will receive no Elo rating. Affects 6 matches.

  'Serbia and Montenegro' — appeared at the 2006 World Cup. results.csv only
  carries the successor states individually (Serbia, Montenegro). Retained
  as-is. Will receive no Elo rating. Affects 3 matches.
""")

# ---------------------------------------------------------------------------
# Step 6: Save outputs
# ---------------------------------------------------------------------------
wc.to_csv(PROCESSED / "wc_matches_clean.csv", index=False)
results.to_csv(PROCESSED / "results_clean.csv", index=False)

audit_path = PROCESSED / "name_audit.txt"
with open(audit_path, "w") as f:
    f.writelines(audit_lines)

print(f"\nOutputs written to {PROCESSED}/")
print("  wc_matches_clean.csv")
print("  results_clean.csv")
print("  name_audit.txt")