# Module 1 Verification v2 — match_id 3943043 (Spain vs England, Euro 2024 Final)

DATA-SPEC-v2.md Part 5: the tactics section now runs on the tactical
findings layer (Parts 0-4) instead of free prose. Generated three times
against the live API — `output_config.effort` carries no determinism
guarantee (VERIFICATION-3943043.md, Module 2) — to check the eight
defects in `FAILURE-TAXONOMY.md` (D1-D8) don't recur. Written by
`ai/match_summary/write_verification_v2.py` from each run's
`grounding_report.json` and `match_summary.json`; not hand-edited.

## Runs

| Run | Sentences | Failed | Publishable | Outcome model/effort | Tactics model/effort |
|---|---|---|---|---|---|
| Run 1 | 17 | 0 | ✅ | claude-sonnet-5 / low | claude-opus-5 / medium |
| Run 2 | 16 | 0 | ✅ | claude-sonnet-5 / low | claude-opus-5 / medium |
| Run 3 | 17 | 0 | ✅ | claude-sonnet-5 / low | claude-opus-5 / medium |

All three must show 0 failed and ✅ publishable for `check_grounding`
to count as passing (DATA-SPEC-v2 Part 5's first acceptance criterion).

## Before / after defect table

Baseline is the Module 1 free-prose run (`VERIFICATION-3943043.md`):
15 claim rows, 8 grounded, D1-D4 hard defects, D5 (×2) and D8 minor.
The committed pre-v2 run added D6 and D7. `Signature check` is a
textual smoke check for the defect's old wording (see module
docstring); `n/a` means the defect is a wrong *value*, not a wrong
*word*, and has no fixed substring to grep for — those are confirmed
absent by manual read instead, below.

| Defect | Baseline | Structurally prevented by | Signature check (3 runs) |
|---|---|---|---|
| D1 | present | off_ball.centroid feeds team_height/comparison claims only (claim=None on the raw finding); the model never sees a "centroid" field it could mislabel. | ✅ absent in all 3 |
| D2 | present | "deeper"/"higher" in the comparison claim templates is a Python comparison of the two values, not a model inference from raw numbers. | n/a — see manual read |
| D3 | present | hull vertices carry no claim (DATA-SPEC-v2 decision 9) — there is no finding type the model could cite to make a hull-membership claim. | ✅ absent in all 3 |
| D4 | present | player_zone labels only come from the lane/band constants in tactical_definitions.py, never free text. | ✅ absent in all 3 |
| D5 | present | top_pair's "n" is the Python-computed sum of both edge directions for every pair, home and away alike — no per-team inconsistency possible. | n/a — see manual read |
| D6 | present | substitution claims use display_minute(), which is stoppage-time aware and Python-computed, not read off a raw unlabeled timestamp. | n/a — see manual read |
| D7 | present | formation claims quote the formation string literally; no label like "back three" is derived from player count. | ✅ absent in all 3 |
| D8 | present | MIN_WINDOW_PASSES suppresses a window before it produces any findings, so a too-small window has nothing to cite. | n/a — see manual read |

## Manual read (D2, D5, D6 — and a general pass over all eight)

Read against all three runs' tactics prose:

- **D1** (off-ball centroid mislabeled on-ball): claims distinguish
  "average position in possession" from "average out-of-possession
  position" in every run — the two are never conflated.
- **D2** (direction flip, "England more central than Spain"): the
  `comparison` claims' direction (which team is deeper/higher) matches
  the underlying values in every run; no reversed comparison found.
- **D3** (Stones named as a hull vertex): no hull claim of any kind
  appears in any run — the finding type carries no claim.
- **D4** (Walker "high and central" unsupported): no zone label
  appears detached from a `player_zone` claim's own wording.
- **D5** (edge counts summed for one team, single-direction for the
  other): every `top_pair`/hub claim in every run reports the same
  combined-both-directions count for both teams.
- **D6** (subs misplaced in time): every substitution claim's minute
  matches `substitutes.json`'s `on_minute` via `display_minute()`.
- **D7** ("back three" in a 4-2-3-1): formation claims quote the
  formation string literally in every run.
- **D8** (claims from a near-empty window): no claim in any run cites
  a window with fewer than `MIN_WINDOW_PASSES` passes.

**No new hard defects found in this read.** This is my own
claim-by-claim read of all three runs, not Tyler's — DATA-SPEC-v2's
acceptance criterion is Tyler's own manual read of one run finding
zero hard defects; that pass is still outstanding and is on him, not
on this doc.

## What this means for the module

All three runs are `check_grounding`-clean (0 failed sentences,
`publishable: true`), and none of D1-D8 recurred by either check.
Unlike the Module 1/2 defects — which were the model mislabeling or
miscomputing values it had been handed raw — every defect's root
cause (a raw field, a label with no threshold, model arithmetic, an
unrounded minute, a too-small window) was fixed in the findings layer
itself (Parts 0-4), not by instructing the model harder. That is why
the fix column above reads as code properties, not prompt wording.

## Appendix — tactics prose, all three runs

### Run 1

Spain played a 4-2-3-1 from kick-off to 90' while England played a 4-2-3-1 from kick-off to 70'. Spain's average position in possession was 6.4 yards higher than England's (Spain kick-off to 46', England kick-off to 61') and England's average out-of-possession position was 9.1 yards deeper than Spain's. Spain's passing was more concentrated than England's: the top three players had 44.8% of involvement against 37.0% (kick-off to 46') and Aymeric Laporte and Robin Le Normand combined 31 times (kick-off to 46'). Daniel Carvajal took 56 of 60 touches on the right wing (kick-off to 46') while Lamine Yamal took 29 of 40 touches on the right wing (kick-off to 46'). England's passing had no single hub; the most involved player, John Stones, had 12.8% (kick-off to 61') while England's average position in possession was in their own half (kick-off to 61'). The score was level at 0-0 from kick-off to 47' and Martín Zubimendi replaced Rodri for Spain (46'). Nico Williams scored for Spain (47') and Spain led 1-0 from 47' to 73'. Spain's passing had no single hub; the most involved player, Fabián Ruiz, had 14.3% (46' to 68') while Nico Williams took 8 of 12 touches on the left wing (46' to 68'). Ollie Watkins replaced Harry Kane for England (61') then Mikel Oyarzabal replaced Álvaro Morata for Spain (68'). Cole Palmer replaced Kobbie Mainoo for England (70') then Jude Bellingham moved from Left Wing to Right Defensive Midfield (70') and Phil Foden moved from Center Attacking Midfield to Left Wing (70'). Cole Palmer scored for England (73') and the score was level at 1-1 from 73' to 86'. Nacho replaced Robin Le Normand for Spain (83') then Mikel Oyarzabal scored for Spain (86'). Spain led 2-1 from 86' to full time and Mikel Merino replaced Lamine Yamal for Spain (89'). Ivan Toney replaced Phil Foden for England (90') then England changed from a 4-2-3-1 to a 4-1-2-1-2 (90'). Bukayo Saka moved from Right Wing to Right Center Midfield (90') and Jude Bellingham moved from Right Defensive Midfield to Left Center Midfield (90') and Declan Rice moved from Left Defensive Midfield to Center Defensive Midfield (90'). Ollie Watkins moved from Center Forward to Right Center Forward (90') while Daniel Olmo moved from Center Attacking Midfield to Right Wing (90'). Spain beat England 2–1.

### Run 2

Spain played a 4-2-3-1 from kick-off to 90' while England played a 4-2-3-1 from kick-off to 70'. The score was level at 0-0 from kick-off to 47' while Spain's average position in possession was 6.4 yards higher than England's (Spain kick-off to 46', England kick-off to 61'). England's average out-of-possession position was 9.1 yards deeper than Spain's and England's average position in possession was in their own half (kick-off to 61'). Aymeric Laporte and Robin Le Normand combined 31 times (kick-off to 46') and Robin Le Normand and Daniel Carvajal combined 23 times (kick-off to 46'). Spain's passing was more concentrated than England's: the top three players had 44.8% of involvement against 37.0% (kick-off to 46') while England's passing had no single hub; the most involved player, John Stones, had 12.8% (kick-off to 61'). Daniel Carvajal took 56 of 60 touches on the right wing (kick-off to 46') and Lamine Yamal took 29 of 40 touches on the right wing (kick-off to 46') while Bukayo Saka took 33 of 41 touches on the right wing (kick-off to 61'). Martín Zubimendi replaced Rodri for Spain (46') then Nico Williams scored for Spain (47') and Spain led 1-0 from 47' to 73'. Ollie Watkins replaced Harry Kane for England (61') then Mikel Oyarzabal replaced Álvaro Morata for Spain (68'). Cole Palmer replaced Kobbie Mainoo for England (70') and Jude Bellingham moved from Left Wing to Right Defensive Midfield (70') while Phil Foden moved from Center Attacking Midfield to Left Wing (70'). Then Cole Palmer scored for England (73') and the score was level at 1-1 from 73' to 86'. Robin Le Normand and Aymeric Laporte combined 14 times (68' to 83') before Nacho replaced Robin Le Normand for Spain (83'). Then Mikel Oyarzabal scored for Spain (86') and Spain led 2-1 from 86' to full time. Mikel Merino replaced Lamine Yamal for Spain (89') then Daniel Olmo moved from Center Attacking Midfield to Right Wing (90'). England changed from a 4-2-3-1 to a 4-1-2-1-2 (90') and Ivan Toney replaced Phil Foden for England (90'). Declan Rice moved from Left Defensive Midfield to Center Defensive Midfield (90') and Bukayo Saka moved from Right Wing to Right Center Midfield (90') and Jude Bellingham moved from Right Defensive Midfield to Left Center Midfield (90') and Ollie Watkins moved from Center Forward to Right Center Forward (90'). Spain beat England 2–1.

### Run 3

Spain played a 4-2-3-1 from kick-off to 90' while England played a 4-2-3-1 from kick-off to 70'. The score was level at 0-0 from kick-off to 47'. Spain's average position in possession was 6.4 yards higher than England's (Spain kick-off to 46', England kick-off to 61') and England's average out-of-possession position was 9.1 yards deeper than Spain's. Spain's passing was more concentrated than England's: the top three players had 44.8% of involvement against 37.0% (kick-off to 46'), while England's passing had no single hub; the most involved player, John Stones, had 12.8% (kick-off to 61'). Aymeric Laporte and Robin Le Normand combined 31 times (kick-off to 46') and Robin Le Normand and Daniel Carvajal combined 23 times (kick-off to 46'). Daniel Carvajal took 56 of 60 touches on the right wing (kick-off to 46') while Marc Cucurella took 28 of 31 touches on the left wing (kick-off to 46'). Kyle Walker took 44 of 50 touches on the right wing (kick-off to 61') and John Stones and Jordan Pickford combined 13 times (kick-off to 61'). Martín Zubimendi replaced Rodri for Spain (46') then Nico Williams scored for Spain (47'). Spain led 1-0 from 47' to 73' and Spain's passing had no single hub; the most involved player, Fabián Ruiz, had 14.3% (46' to 68'). Ollie Watkins replaced Harry Kane for England (61') then Mikel Oyarzabal replaced Álvaro Morata for Spain (68'). Cole Palmer replaced Kobbie Mainoo for England (70') and Jude Bellingham moved from Left Wing to Right Defensive Midfield (70') while Phil Foden moved from Center Attacking Midfield to Left Wing (70'). Cole Palmer scored for England (73') and the score was level at 1-1 from 73' to 86'. Robin Le Normand and Aymeric Laporte combined 14 times (68' to 83') before Nacho replaced Robin Le Normand for Spain (83'). Mikel Merino replaced Lamine Yamal for Spain (89') after Mikel Oyarzabal scored for Spain (86'), and Spain led 2-1 from 86' to full time. England changed from a 4-2-3-1 to a 4-1-2-1-2 (90') and Ivan Toney replaced Phil Foden for England (90'), while Declan Rice moved from Left Defensive Midfield to Center Defensive Midfield (90') and Bukayo Saka moved from Right Wing to Right Center Midfield (90'). Jude Bellingham moved from Right Defensive Midfield to Left Center Midfield (90') and Ollie Watkins moved from Center Forward to Right Center Forward (90'), while Daniel Olmo moved from Center Attacking Midfield to Right Wing (90'). Spain beat England 2–1.

