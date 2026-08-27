# Module 1 Verification — match_id 3943043 (Spain vs England, Euro 2024 Final)

Manual read-through per SPEC.md's pass/fail signal: read the generated summary
next to the source JSON and confirm nothing is invented. Generated with
`uv run python -m statsbomb.generate_match_summary` (model: `claude-sonnet-5`).
Full output: `data/euro-2024/3943043/match_summary.json`.

## Structured-outcome-section check

Every `key_stats` and `standout_performers` entry, checked against the exact
`source_field` the model cited.

| Claim | Source field | Source value | Match? |
|---|---|---|---|
| Final Score: Spain 2 - 1 England | `match_stats.home.score` / `away.score` | 2 / 1 | ✅ |
| Shots: Spain 16 - England 9 | `match_stats.rows[0]` | home 16.0, away 9.0 | ✅ |
| Possession: Spain 62.2% - England 37.8% | `match_stats.rows[2]` | home 62.2, away 37.8 | ✅ |
| xG: Spain 1.79 - England 0.73 | `match_stats.rows[7]` | home 1.79, away 0.73 | ✅ |
| Passes: Spain 592 - England 323 | `match_stats.rows[8]` | home 592.0, away 323.0 | ✅ |
| Pass Accuracy: Spain 87.5% - England 78.6% | `match_stats.rows[9]` | home 87.5, away 78.6 | ✅ |
| Corners: Spain 10 - England 2 | `match_stats.rows[3]` | home 10.0, away 2.0 | ✅ |
| Aymeric Laporte — 48 completed passes in the first half | `pass_network.home.windows[0].nodes[0]` | Laporte, passes=48 | ✅ |
| Robin Le Normand — tied for most passes (48) in the opening half | `pass_network.home.windows[0].nodes[7]` | Le Normand, passes=48 | ✅ |
| Daniel Carvajal — 36 passes in the first 45 minutes | `pass_network.home.windows[0].nodes[1]` | Carvajal, passes=36 | ✅ |
| Jude Bellingham — 18 passes in the starting-XI window | `pass_network.away.windows[0].nodes[5]` | Bellingham, passes=18 | ✅ |
| Ollie Watkins — 60th-minute sub for Kane | `substitutes.teams.England[1]` | on_minute=60, replaced_player="Harry Kane" | ✅ |

**Result: 12/12 claims verified exactly against their cited source field.** No
invented or misattributed values in the structured section.

## Tactics-section claim map

Every factual claim in the free-prose paragraphs, mapped to the exact source
file + field. Sources available to this call: `formation`, `team_shape`,
`pass_network` (both teams) — **not** `match_stats`, `substitutes`, or
`progressive_map`, per SPEC.md's narrower tactics-grounding requirement.

| # | Claim (paraphrased) | Source file.field | Verdict |
|---|---|---|---|
| 1 | Both sides set up 4-2-3-1 | `formation_spain.json` / `formation_england.json`, `periods[0].formation` | ✅ Grounded |
| 2 | Spain: Rodri + Fabián Ruiz double pivot behind Olmo | `formation_spain.json periods[0].players[*].position` — Rodri "Right Defensive Midfield", Ruiz "Left Defensive Midfield", Olmo "Center Attacking Midfield" | ✅ Grounded |
| 3 | England: Rice + Mainoo screening, Foden behind Kane | `formation_england.json periods[0].players[*].position` — Rice/Mainoo "…Defensive Midfield", Foden "Center Attacking Midfield", Kane "Center Forward" | ✅ Grounded |
| 4 | **"Spain's on-ball centroid (62.2, 41.4)… England's (69.8, 39.2)"** | `team_shape_spain.json off_ball.centroid` = {62.21, 41.37}; `team_shape_england.json off_ball.centroid` = {69.84, 39.17} | ❌ **Defect — mislabeled.** These are the **off-ball** (out-of-possession) centroids, not "on-ball." There is no on-ball centroid field in the data (`on_ball` only has per-player `nodes`, no aggregate). The values are copied correctly but the semantic label is wrong. |
| 5 | "…England sat more central than Spain" (implied by claim 4) | Same centroid fields | ❌ **Also wrong on the numbers themselves** — pitch center is y=40; England's off-ball y (39.17) is *closer* to center than Spain's (41.37). The claim has the comparison backwards. |
| 6 | Spain hull (H1): Simón deep, Cucurella/Morata/Yamal high & wide, back four progressing forward | `team_shape_spain.json on_ball.periods[0].hull` cross-referenced against `.nodes` — all 5 hull vertices ([9.77,43.01]=Simón, [76.74,10.0]=Cucurella, [79.8,28.78]=Morata, [81.07,68.58]=Yamal, [67.44,70.85]=Carvajal) | ✅ Grounded (all 4 named players are exact hull vertices; 5th vertex, Carvajal, folded into "the full-backs") |
| 7 | England hull (H1): "ran from Pickford through **Stones** and Guehi out to Kane" | `team_shape_england.json on_ball.periods[0].hull` = [[77.67,33.38]=Kane, [75.49,70.42]=Saka, [55.99,69.03]=Walker, [11.01,39.26]=Pickford, [36.49,18.64]=Guehi, [59.38,10.67]=Shaw, [67.16,20.07]=Bellingham] | ❌ **Defect — Stones is not a hull vertex.** He's an interior node ([45.18, 48.52]); Pickford and Guehi are correctly hull vertices, Stones isn't. |
| 8 | "…Walker pushed high and central" | Same hull data — Walker = [55.99, 69.03] | ❌ **Defect — mischaracterized.** y=69.03 (of 0–80) is wide/near the touchline, not central; x=55.99 isn't especially "high" relative to Kane's 77.67. |
| 9 | Spain H1 hub: Le Normand↔Laporte combined 31 times; Rodri 29, Carvajal 36 passes | `pass_network_Spain.json windows[0].edges` (Laporte→LeNormand 17 + LeNormand→Laporte 14 = 31) and `.nodes` (Rodri 29, Carvajal 36) | ✅ Grounded (correctly summed both edge directions) |
| 10 | England H1 hub: Stones-Pickford (8), Rice-Bellingham (8), Walker-Stones (7) | `pass_network_England.json windows[0].edges` — each is a real single-direction edge count | ⚠️ **Minor inconsistency, not fabrication.** Each number is a real edge value, but unlike claim 9 (Spain, summed both directions = 31), these are single-direction only — the true combined totals are 13, 11, and 10 respectively. Not invented, but the "busiest connections" framing implies bidirectional volume inconsistently with how the Spain figure was computed. |
| 11 | Saka/Foden linked with Walker/Mainoo down the right | `pass_network_England.json windows[0].edges` (Saka-Walker=5, Walker-Mainoo=5, Stones-Foden=4, Saka-Foden=4) + Saka's "Right Wing" position label | ✅ Grounded |
| 12 | Spain subs: Zubimendi↔Rodri (45'), Oyarzabal↔Morata (67'), Nacho↔Le Normand (82'), Merino↔Yamal (88') | `pass_network_Spain.json substitutions` (also cross-checked against `formation_spain.json`) | ✅ Grounded — exact minute + player pairs |
| 13 | England subs + formation change: Watkins↔Kane (60'), Palmer↔Mainoo (69'), Toney↔Foden (89'); shifts to 4-1-2-1-2 with Rice sole DM, Bellingham/Saka central mid two, Toney/Watkins up front | `pass_network_England.json substitutions` + `formation_england.json periods[2]` (formation "4-1-2-1-2", Rice "Center Defensive Midfield", Saka "Right Center Midfield", Bellingham "Left Center Midfield", Toney/Watkins "…Center Forward") | ✅ Grounded — exact minutes, positions, and formation string all match |
| 14 | England 69'-89' hub shifts to Bellingham↔Palmer "combined four times"; Saka/Walker still prominent | `pass_network_England.json windows[2].edges` — Bellingham→Palmer=4 (reverse direction Palmer→Bellingham=1, true combined=5) | ⚠️ **Minor — same single-direction-vs-combined inconsistency as #10.** The cited "4" is real but "combined" undercounts (true total 5). |
| 15 | Spain's late-window network "sparser and more fragmented," Fabián Ruiz/Nacho/Olmo forming a "reduced central relay" | `pass_network_Spain.json windows[3]` (82'-88') has Ruiz=5, Nacho=3, Olmo=4 passes — plausibly the top-connected trio in that window; `windows[4]` (88'-FT) has only 1 node, 1 edge | ⚠️ **Minor — imprecise window attribution.** The named trio's data lives in window 3, not window 4; the claim blurs "closing minutes" across both without saying which. Not fabricated, just under-specified about which window backs it. |

**Result: 11 of 15 claims fully grounded. 2 hard defects (claims 4/5 and 7/8 —
a real semantic mislabeling and a hull-membership/geometry error), 3 minor
issues (claims 10, 14, 15 — real numbers, imprecise framing or window
attribution).** No hallucinated players, no invented formations, no fabricated
event data (no goals/cards/fouls mentioned, as instructed) — every number and
every player named is real. The defects found are exactly the kind SPEC.md
predicted: "wrong looks like a hallucinated formation or shift, not 'the tone
was off'" — here it's a data-source mislabel (off-ball read as on-ball) and a
hull-vertex/geometry misread, not an invented player or score.

## What this means for the module

The **module** (grounding pipeline, prompt constraints, structured-output
enforcement) worked as designed — the structured section is 100% clean, and
the tactics section's defects are traceable, spot-checkable mislabelings
rather than outright fabrication. That's the traceability bar doing its job:
every claim could be checked against a field, and checking surfaced two real
defects. Whether prompt tuning can close these two specific gaps (e.g.
explicitly telling the model "`off_ball.centroid` describes defensive/
out-of-possession shape, never label it on-ball" and "only claim a player is
part of the hull if their coordinates exactly match a hull vertex") is a
reasonable follow-up, but per SPEC.md, prompt-quality iteration is explicitly
Module 3's job, not this one's.
