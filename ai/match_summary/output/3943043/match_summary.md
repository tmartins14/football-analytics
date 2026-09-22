# Spain 2–1 England — UEFA Euro 2024 Final

> **Draft — generated output, not yet reviewed for publish**

Spain outclassed England 2-1, dominating possession and chances despite a nervy finish sealed by substitute Mikel Oyarzabal.

## Match stats

| Stat | Spain | England | Source |
|---|---|---|---|
| Shots | 16 | 9 | `match_stats.rows[0]` |
| Possession | 62.2% | 37.8% | `match_stats.rows[2]` |
| Expected Goals | 1.79 | 0.73 | `match_stats.rows[7]` |
| Passes | 592 | 323 | `match_stats.rows[8]` |
| Pass Accuracy | 87.5% | 78.6% | `match_stats.rows[9]` |
| Corners | 10 | 2 | `match_stats.rows[3]` |

## Standout performers

- **Mikel Oyarzabal** (Spain) — Came on as a 67th-minute substitute for Morata and was involved in Spain's attacking play late in the match, contributing to the winning effort.
  `substitutes.teams.Spain[2]`
- **Aymeric Laporte** (Spain) — High passing volume from center-back including multiple progressive passes, a key build-up figure across all four on-ball periods recorded.
  `pass_network.home.windows[0].nodes[0]`
- **Jude Bellingham** (England) — Led England's progressive passing and carrying involvement, including a 21.5-yard progressive pass and multiple progressive carries.
  `progressive_map.away.actions`
- **Bukayo Saka** (England) — Recorded a 38.6-yard progressive carry and several progressive passes, England's most dangerous outlet on the right.
  `progressive_map.away.actions`
- **Daniel Carvajal** (Spain) — Second-highest pass count among Spain starters (36 in the first window) and a constant outlet down the right flank.
  `pass_network.home.windows[0].nodes[1]`

## Tactical report

Both sides lined up in a 4-2-3-1, with Spain's declared shape holding until the 89th minute, when Nacho, Mikel Merino and Mikel Oyarzabal came on for Robin Le Normand, Rodri (via Zubimendi at half-time) and Morata respectively, keeping the same broad structure through to full time. England mirrored that setup for an hour before Ollie Watkins replaced Harry Kane, Cole Palmer came on for Kobbie Mainoo at 69', and Jude Bellingham dropped into the right-sided base-midfield slot alongside Declan Rice — a rearrangement that culminated in a late switch to a 4-1-2-1-2 after 89 minutes, with Rice as the deepest midfielder behind Palmer, Saka and Bellingham, and Ivan Toney and Watkins paired up front alongside Toney's introduction for Foden.

In possession, Spain's on-ball centroid[^1] (62.2, 41.4) sat further forward and more central than England's underlying off-ball density would suggest was comfortable, with Robin Le Normand and Aymeric Laporte the busiest first-half nodes (75 and 70 involvements) both operating from deep, central positions to progress play, while Rodri linked between them and the advanced trio. Their attacking hull in the first 45 stretched from the byline out to Nico Williams and Lamine Yamal high and wide, indicating a team happy to commit both wide forwards high and let the back three carry the ball forward underneath them. England's on-ball shape by contrast centred further upfield (69.8, 39.2) with Declan Rice (45 events) and Kyle Walker (50) forming the busiest circulation points, and John Stones stepping into a more advanced, central passing role alongside Rice and Mainoo — reflecting a back-to-front build via the center-backs and Walker rather than a single deep pivot.

Passing-network hubs reinforce this: Spain's first-half network shows Le Normand and Laporte as by far the highest-volume nodes (48 passes each) exchanging heavily with each other and Carvajal, with Rodri as a clear tertiary connector into Fabián Ruiz and the front line — a hub structure that persisted with Zubimendi and later Nacho stepping into similar deep-central roles after changes. England's network was more evenly spread across Rice (23), Stones (24) and Walker (24), with Stones-Pickford, Walker-Stones and Rice-Bellingham as the heaviest single connections, before the ball progressively found Bellingham and, after the 69th-minute change, Cole Palmer as the central attacking link — Palmer immediately becoming a frequent outlet for Bellingham, Walker and Saka in the final third once introduced.

[^1]: **Known issue, reproduced in this run:** both bolded "on-ball centroid" claims above are actually the source data's `off_ball.centroid` field — `team_shape_*.json` has no on-ball aggregate. Documented in `VERIFICATION-3943043.md` as a Module 1 defect (mislabel, not fabrication); still present at `TACTICS_EFFORT="high"`. Prompt fix is deferred to Module 3 per SPEC.md.

---

**Model:** claude-sonnet-5 · **Outcome effort:** low · **Tactics effort:** high · **Match ID:** 3943043
**Generated via:** `ai/match_summary/generate_match_summary.py` · `main()`
**Written to:** `ai/match_summary/output/3943043/match_summary.json`
