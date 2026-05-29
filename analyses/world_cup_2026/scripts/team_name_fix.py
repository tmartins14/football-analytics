import pandas as pd
wc = pd.read_csv('data/raw/WorldCupMatches.csv', encoding='utf-8', on_bad_lines='skip')
names = set(wc['Home Team Name'].dropna().str.strip().unique()) | set(wc['Away Team Name'].dropna().str.strip().unique())
ivory = [n for n in names if 'voire' in n.lower()]
print(repr(ivory[0]))