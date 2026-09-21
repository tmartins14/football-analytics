# Model & effort comparison — match 3943043

## Results

Cost and tokens from each response's `usage` × the rate table. Grading columns are a manual read that **calls out errors rather than gating on pass/fail**: no eval system exists yet (Module 3), so a wrong claim is recorded, not disqualifying. n = 1 per cell and `effort` output is non-deterministic, so small differences are within noise.

| # | model | effort | input_tok | output_tok | total_tok | input_$ | output_$ | total_$ | latency_s | outcome_grounding | motm | tactics_grounding |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | claude-haiku-4-5 | none | 164,148 | 1,719 | 165,867 | 0.1641 | 0.0086 | 0.1727 | 31.4 | 2 errors | hit | 7 errors |
| 2 | claude-sonnet-5 | medium | 181,961 | 1,765 | 183,726 | 0.3639 | 0.0176 | 0.3816 | 31.5 | 1 error, 2 minor | miss | 3 errors, 2 minor |
| 3 | claude-opus-5 | medium | 181,961 | 3,351 | 185,312 | 0.9098 | 0.0838 | 0.9936 | 55.3 | 0 errors, 2 minor | hit | 1 error, 1 minor |
| 4 | claude-sonnet-5 | low | 181,961 | 1,847 | 183,808 | 0.3639 | 0.0185 | 0.3824 | 30.7 | 0 errors, 1 minor | miss | 2 errors, 2 soft |
| 5 | claude-sonnet-5 | high | 181,961 | 4,964 | 186,925 | 0.3639 | 0.0496 | 0.4136 | 83.8 | 1 error, 2 soft | hit | 2 errors, 3 minor |

Total recorded spend (failed attempts included): $2.3438 (ceiling $7.00).

**MOTM (Nico Williams):** Named by Tyler as the match's man of the match. None of the six source files carries a man-of-the-match field, so the model cannot know it: a miss is not a grounding error, and the prompt must not be tuned, or outside data added, to make it hit, because that would use information the model would not have in production. Hits (cells 1, 3, 5) are picks the data it did have supports (8 progressive actions, tied for the most on Spain), though cell 1's supporting figure is wrong. Recorded as an observation only, not a selection criterion.

## Per-section breakdown

Outcome and tactics are separate calls, so routing can differ per section.

| # | section | input_tok | output_tok | total_$ | latency_s |
|---|---|---|---|---|---|
| 1 | outcome | 122,799 | 603 | 0.1258 | 15.2 |
| 1 | tactics | 41,349 | 1,116 | 0.0469 | 16.1 |
| 2 | outcome | 135,456 | 863 | 0.2795 | 15.7 |
| 2 | tactics | 46,505 | 902 | 0.1020 | 15.9 |
| 3 | outcome | 135,456 | 967 | 0.7015 | 16.4 |
| 3 | tactics | 46,505 | 2,384 | 0.2921 | 38.9 |
| 4 | outcome | 135,456 | 872 | 0.2796 | 13.6 |
| 4 | tactics | 46,505 | 975 | 0.1028 | 17.1 |
| 5 | outcome | 135,456 | 3,885 | 0.3098 | 53.9 |
| 5 | tactics | 46,505 | 1,079 | 0.1038 | 29.9 |

## Grading notes

### Cell 1 — claude-haiku-4-5, none
- Outcome: all 7 key_stats match their source fields. Performers surfaced: Rodri, Le Normand, N. Williams, Walker.
- Outcome error: Walker "40.6-yard carry in the 39th minute" does not exist. His minute-39 carries are all under 2 yards and none is progressive; his longest progressive actions are passes (41.46 at 29', incomplete).
- Outcome error: N. Williams "5 progressive passes in the 67-82 window" cites windows[2].nodes[8].passes, which is his total pass count (5). His progressive passes were at 4', 7', 13', 48' and 65'.
- Tactics: opens with a Markdown H1 header (system prompt says no headers) and cites "fatigue" (prompt forbids inferring it).
- Tactics: England's off-ball centroid "sat deeper" than Spain's, but x=69.84 vs 62.21 is further forward; the depth-line comparison is reversed the same way (Spain 82.05 "further forward" than England 86.73).
- Tactics: Foden called a left winger; he is the centre attacking midfielder until 69'. "Narrower attacking posture" and "fullbacks driving distribution" have no source.
- MOTM (Nico Williams): hit. The pick is defensible (8 progressive actions, tied for the most on Spain), but its supporting figure is one of the outcome errors above.

### Cell 2 — claude-sonnet-5, medium
- Outcome: all 7 key_stats match. Performers surfaced: Laporte, Le Normand, Palmer, Saka.
- Outcome error: Palmer "progressive pass to Bukayo Saka" is unsupported. All 6 of Palmer's recorded actions have progressive=false, and the cited field is substitutes only.
- Outcome minor: Laporte "led" progressive passing (tied with N. Williams at 8 progressive actions); Le Normand "top passer" (joint with Laporte at 48).
- Tactics error: the (62.2, 41.4) and (69.8, 39.2) centroids are labelled "on-ball" but are the off-ball centroids (the known Module 1 defect recurs).
- Tactics error: Spain "more central" than England is reversed. Pitch centre is y=40, so England (39.17) is closer than Spain (41.37).
- Tactics error: "the tournament's most frequent combination" is a claim about the whole tournament; the data covers one match.
- Tactics minor: Rodri's 29 passes called a "progressive outlet" (pass count is not progression); Spain "brief switch in the final period" (the formation label stays 4-2-3-1, only positions change).
- MOTM (Nico Williams): miss. Not a grounding error; see the MOTM note under the results table.

### Cell 3 — claude-opus-5, medium
- Outcome: all 8 key_stats are correct but oddly split ("Shots (Spain-England)" = "16.0" omits England's 9; "Spain passes at 87.5% accuracy" = "592.0", where the real 87.5 sits in the label and is not cited). Performers surfaced: Le Normand, Laporte, N. Williams, Saka, Palmer.
- Outcome verified: Laporte 35.09 carry at 42', N. Williams 30.17 at 81', Saka 38.63 at 72', Palmer on at 69:53 (on_second=53), Le Normand team-high 75 events before the break.
- Outcome minor: Palmer "four times with Bellingham in the final window" is windows[2] (69'-89'); the final window is 89'-FT.
- Tactics error: Walker "most advanced of England's back four" is contradicted; Shaw's on-ball node (x=59.38) is further forward than Walker's (55.99).
- Tactics verified: 715 vs 483 open-play events (team_shape metadata), camera caveat, both teams' thirds spines, Carvajal/Yamal/Cucurella/Saka positions, window-by-window node moves, all cited pass counts and edges, Spain's 89' Merino/Olmo positions, England's 4-1-2-1-2 at 89'.
- Tactics minor: Le Normand-Carvajal (17) called the "single strongest link"; Laporte-to-Le Normand is also 17, and Laporte-Le Normand combined is 31.
- MOTM (Nico Williams): hit. Supported by data the model had: the 30.17 carry at 81' is verified.

### Cell 4 — claude-sonnet-5, low
- Outcome: all 8 key_stats are correct (source_field uses shorthand "rows[n].home_value / away_value" rather than two full paths). Performers surfaced: Laporte, Le Normand, Saka, Palmer, Oyarzabal.
- Outcome verified: Laporte 56.14 and 30.95 both exist (the 56.14 pass was incomplete; not claimed otherwise); Saka 14 passes and the 38.63 carry at 72' (inside 69'-89'); Oyarzabal on at 67' for Morata; Palmer on at 69'.
- Outcome minor: Le Normand "top" node, joint with Laporte at 48.
- Tactics error: Spain's "build-up centroid (62, 41)" in an on-ball paragraph is the off-ball centroid (mislabel).
- Tactics error: "only in stoppage time did England shift ... after introducing Toney, Watkins and Palmer together" is wrong. Watkins came on at 60', Palmer at 69', Toney at 89'12" (not stoppage time).
- Tactics minor: "suggestive of a team pressing higher" and "Rice and Mainoo/Stones dropping deep on-ball" are not derivable from the given data.
- MOTM (Nico Williams): miss. Not a grounding error; see the MOTM note under the results table.

### Cell 5 — claude-sonnet-5, high
- Outcome: all 6 key_stats are correct. Performers surfaced: Le Normand, Laporte, N. Williams, Saka, Watkins.
- Outcome error: Le Normand "repeatedly launched long, line-breaking diagonals to switch play" is contradicted. He has 3 progressive passes, one long (55.96 at 48', y 57.8 to 56.6: a straight ball, not a switch), and the cited field is only his pass count.
- Outcome minor: Watkins as "central attacking focal point" and Saka's "counter-attacking threat" have no source. N. Williams 23 passes and Saka 14 passes verified.
- Tactics error: "Spain made three changes across the second half"; Spain made four (45', 67', 82', 88').
- Tactics error: Merino's entry "in stoppage time"; it was 88'40".
- Tactics minor: Rice (23) and Stones (24) as "top progressors" (pass counts; Walker also has 24); a stray "双" character mid-sentence; Spain's hubs shifting "leftward" is unsupported.
- Tactics verified: shape coordinates, both centroids on the attacking half, 4-1-2-1-2 at 89', Carvajal x=108 at 82'-88', pass volumes tailing off in the final windows.
- MOTM (Nico Williams): hit. Supported by data the model had: 23 passes in the opening window (verified) and 8 progressive actions.
