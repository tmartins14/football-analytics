# DATA-SPEC v3 — Phase Findings and Player Contribution

Status: draft 2026-10-15, pending Tyler's review of "Decisions to accept or change"
Module: 3 (tier 1 before Module 3 wraps; tier 2 after)
Owner: Tyler (Plan, definitions, review) / Claude (Execute, Verify)
Related: [DATA-SPEC-v2.md](./DATA-SPEC-v2.md), [FAILURE-TAXONOMY.md](./FAILURE-TAXONOMY.md)
Intended path: `ai/match_summary/DATA-SPEC-v3.md`
Match in scope for summaries: `3943043` (Spain vs England, Euro 2024 Final)

## Relationship to v2

v3 **extends** v2. Everything below inherits v2's seam rules, finding schema,
`claim` field, display conventions, suppression rule, notability, linking rule
and `check_grounding`. Where v3 says nothing, v2 governs. v3 replaces v2's
Part 6; v2's Part 6 becomes a pointer to this document.

## Goal

Close D10 (no team attacking or defensive approach) and D11 (model-chosen key
performers) from `FAILURE-TAXONOMY.md`:

1. **Phase findings:** answer the questions analysts ask about each team, by
   phase of play, from StatsBomb event and 360 data.
2. **Player contribution:** a deterministic, documented rating that picks
   standout players and gives the actions that earned it.
3. **Coverage check:** code verifies the summary answers the required
   questions.
4. **Structure:** the tactics section is organised by team and phase, not by
   minute, which removes most of D9 without waiting for Module 4.

## Seam rules (additions to v2)

6. Every measure states its StatsBomb event types, filters and coordinate frame.
7. No intent. Measures describe outcomes ("most pressured player"), never aims
   ("funnelled pressure to").
8. Reference distributions and the xT grid are versioned data files, built by
   script, and recorded in every finding that uses them.
9. Reading raw events for the other 50 Euro 2024 matches is allowed **only** to
   build the xT grid and reference distributions. No summaries, findings or
   prose for those matches.

## Coordinate frames

- Every StatsBomb event location is in the **actor's** attack-right frame (v2 §A).
- A location from team A's event, seen from team B: `(120 − x, 80 − y)`.
- Box: x ≥ 102, 18 ≤ y ≤ 62. Six-yard box: x ≥ 114, 30 ≤ y ≤ 50. Goal centre: (120, 40).
- Lanes and bands: v2 constants, half-open intervals.
- Side groups for team-level measures: `left` = left_wing + left_half_space, `centre`, `right` = right_half_space + right_wing.
- Open play: `play_pattern` in {Regular Play, From Counter} and the event is not a set-piece pass type (Corner, Free Kick, Throw-in, Goal Kick, Kick Off).

## Questions, measures and tiers

The question list is the coverage contract. **Tier 1** is built before
Module 3 wraps; **tier 2** after. Required questions (`REQUIRED_COVERAGE`) are
marked R; the summary must answer each one for each team.

| # | Phase | Question | Category | Tier | Req |
|---|---|---|---|---|---|
| Q1 | Creation | Where did their chances come from? | `chance_creation` | 1 | R |
| Q2 | Creation | Who was the creative threat? | `chance_creation` | 1 | |
| Q3 | Progression | How, through whom and down which side did they move the ball forward? | `progression` | 1 | R |
| Q4 | Pressing | How aggressively did they press? | `pressing` | 1 | R |
| Q5 | Defending | How high did they defend, and where did they win the ball? | `defending` | 1 | |
| Q6 | Pressing | Which opponents came under the most pressure? | `pressing` | 1 | |
| Q7 | Contribution | Who were the standout attacking and defensive players? | `player_contribution` | 1 | (key performers section) |
| Q8 | Tempo | Patient or direct? | `progression` | 2 | |
| Q9 | Build-up | Short or long from the back? | `build_up` | 2 | |
| Q10 | Att. transition | How quickly did they attack after winning the ball? | `transition` | 2 | |
| Q11 | Def. transition | Did they counter-press, and did it work? | `transition` | 2 | |
| Q12 | Set pieces | How dangerous were their set pieces, and how were they delivered? | `set_piece` | 2 | |

Not answerable from event data and out of scope: defensive line height,
compactness, pressing triggers, rest-defence shape.

## Tournament reference labels

Absolute labels like "high press" need an anchor. v3's anchor is **Euro 2024
itself**: for each labelled measure, compute it for every team in every match
(102 team-matches) and label this match's value by tercile.

- Labels: `top_third`, `middle_third`, `bottom_third` of Euro 2024 team-matches, with the direction stated per measure (e.g. for PPDA, low = intense).
- Stored at `data/euro-2024/reference/reference_distributions.json`: per measure, the sorted values, tercile cut points, `n`, `definitions_version`, build date.
- Claims say "relative to Euro 2024", never "high press" in the abstract.
- This also unlocks v2's deferred `block_height` label, as a tercile.

## Tier 1 definitions

All thresholds are named constants in `tactical_definitions.py` and provisional.
Values for this match are **not** pre-stated here: Tyler hand-checks them once
after build, and they become the integration fixture (as v2 did for `player_zone`).

### Q1 — Where chances came from (`chance_creation`)

Shots: open play and set piece, penalties excluded (`NON_PENALTY`). xG is `shot.statsbomb_xg`.

- **`xg_by_zone`**: team npxG split by shot zone: `six_yard_box`, `box_central` (box, 30 ≤ y ≤ 50, outside six-yard box), `box_wide`, `outside_box`. Label = modal zone by xG if its share ≥ `MODAL_SHARE`, else `mixed`.
- **`xg_by_source`**: npxG split by `play_pattern` group: `open_play`, `counter` (From Counter), `set_piece` (From Corner, From Free Kick, From Throw In). Value only.
- **`assist_origin`**: for shots with a key pass (`pass.shot_assist` or `pass.goal_assist`), the side group of the pass's start location and its type: `cross` (`pass.cross`), `cut_back` (`pass.cut_back`), `through_ball` (technique Through Ball), `other`. Label = modal side and modal type if share ≥ `MODAL_SHARE`.
- Suppress all three if team non-penalty shots < `MIN_TEAM_SHOTS` (5).
- **`comparison`** on npxG: emitted if gap ≥ `COMPARE_MIN_XG` (0.3).

### Q2 — Creative threat (`chance_creation`)

- **`top_creator`**: player with the highest xA, where xA = sum of `statsbomb_xg` of shots assisted by their key passes (penalties excluded). Emitted if xA ≥ `MIN_XA` (0.2) and key passes ≥ `MIN_KEY_PASSES` (2). Evidence: xA, key passes, passes into the box (completed passes ending in the box, open play).
- Ties at the top are all emitted.

### Q3 — Progression (`progression`)

Reuse `progressive_map`'s definition if one exists (Part 0 reports it). If not:

- **Progressive action**: completed open-play pass or carry that starts at x ≥ 48 (excludes the defending 40%) and either ends ≥ `PROG_MIN_YARDS` (10) closer to goal centre than it started, or ends in the box.
- **`progression_side`**: share of the team's progressive actions by end-location side group. Label `left` / `centre` / `right` if the top side's share ≥ `SIDE_SHARE` (0.40) and exceeds the next by ≥ `SIDE_MARGIN` (0.10), else `balanced`.
- **`progression_mode`**: share of progressive actions that are carries vs passes. Value only; reaches prose through `comparison` (gap ≥ `COMPARE_MIN_POINTS`).
- **`top_progressor`**: player with most progressive actions, if ≥ `MIN_PROG_ACTIONS` (8). Evidence: passes and carries split.
- Suppress team-level findings if progressive actions < `MIN_TEAM_PROG` (20).

### Q4 — Pressing intensity (`pressing`)

- **`ppda`**: opponent open-play passes attempted with x < 72 in the opponent's frame (that is, in the pressing team's attacking 60%), divided by the pressing team's defensive actions with x ≥ 48 in its own frame. Defensive actions: Duel of type Tackle (any outcome), Interception, Foul Committed. Lower = more intense.
  - Label: Euro 2024 tercile (`more_intense` / `typical` / `less_intense` thirds).
  - Evidence carries the numerator, denominator and the PPDA caveat: it measures pressing opportunity, not success.
- **`pressures_high`**: Pressure events with x ≥ 60 (opponent half) per 100 opponent open-play passes. Value only; reaches prose through `comparison`.
- **`comparison`** on PPDA: emitted if the two teams are in different terciles.

### Q5 — Defensive height and ball-winning (`defending`)

- **`block_height`**: v2 definition. Now labelled by Euro 2024 tercile (`higher` / `middle` / `deeper` third).
- **`defensive_action_height`**: mean x (own frame) of Ball Recovery, Interception, successful Duel (Tackle), Block, Clearance. Value only; tercile label.
- **`high_turnovers`**: open-play possessions whose first event by the possession team is at x ≥ `HIGH_TURNOVER_X` (76, about 40 m from goal). Evidence: count, and how many ended in a shot.
- **`win_zone`**: share of ball-winning actions (Ball Recovery, Interception, successful Tackle) by band. Label = modal band if share ≥ `MODAL_SHARE`.

### Q6 — Most pressured opponents (`pressing`)

- **`pressure_received`**: per opposition player, the share of their on-ball events with `under_pressure: true`, for players with ≥ `MIN_NODE_EVENTS` events. Emit the top player if their share exceeds the team median by ≥ `PRESSURE_MARGIN` (0.10).
- **`pressure_side`**: share of the team's Pressure events by side group. Same label rule as `progression_side`.
- Outcome vocabulary only: "came under pressure on X% of actions", never "targeted" or "funnelled".

## Player contribution (Q7)

### Method

Structure follows American Soccer Analysis's Goals Added (categories, defending
counted, shot valued by quality rather than outcome). Values come from
deterministic calculations:

| Category | Value | Actions |
|---|---|---|
| `shooting` | non-penalty xG (`statsbomb_xg`) | Shots |
| `passing` | xT added: `xT(end) − xT(start)` | Successful open-play passes |
| `carrying` | xT added | Successful carries / dribbles |
| `defending` | threat denied: `xT(location seen from the opponent's frame)` | Ball Recovery, Interception, successful Tackle, Block, Clearance |

- **xT grid**: fitted with `socceraction` (`socceraction.xthreat`, default 16 × 12 grid) on SPADL actions from all 51 Euro 2024 matches. Stored at `data/euro-2024/reference/xt_grid_v1.json` with grid size, match count and fit date. The grid is a constant; it is refit only by bumping its version.
- `passing` and `carrying` follow `socceraction`'s xT rating: successful moves only. Failed passes are not penalised. This is a known limitation (Decision 7).
- `defending` ("threat denied") is **this project's approximation**, not a published method. It is labelled as such in every finding's evidence.
- xA is reported as evidence and reasons, not added to the total, because assist passes already earn xT.
- Goalkeepers are excluded from both rankings (Decision 9).

### Findings

- **`attacking_contribution`**: per player, `shooting + passing + carrying`. Top `TOP_N` (3) across both teams, minimum `MIN_MINUTES` (20) played. Ties at the cut all emitted.
- **`defending_contribution`**: per player, `defending`. Same rules.
- **`top_action`**: for each emitted player, their `TOP_ACTIONS` (3) highest-valued actions: type, `display_minute`, value, start and end side group.
- Rankings are separate. There is no combined score.

### Key performers section

Rendered **in Python** from the findings above. No model call: code selects
the players and code writes the claims, so the model would add nothing.
Template per player: the contribution claim plus one `top_action` claim.

### Validation

There is no ground truth for a rating, so:

- Unit tests: xT delta on synthetic actions; the frame flip in `defending` (a recovery at our x = 20 is valued at the opponent's x = 100); minimum minutes; ties.
- Tyler reads the two top-3 lists for this match against his own view of the final and records agreement in the verification file.
- If Part 0 finds OBV fields in the open data, report the rank correlation between our attacking total and summed OBV for outfield players. Recorded as a cross-check, not asserted.

## Claims (templates)

Added to `CLAIM_TEMPLATES`. Rules from v2 apply (no terminal punctuation,
literal values, display formats). xG and xT values display to two decimals.

| Type | Template |
|---|---|
| `xg_by_zone` | `{team} took {share} of their non-penalty xG from {zone_display}` / `{team}'s non-penalty xG was split between {zone1} ({s1}) and {zone2} ({s2})` |
| `assist_origin` | `{n} of {team}'s {total} shot assists came from the {side}, {type_display}` |
| `top_creator` | `{player} created {xa} xG for {team} from {key_passes} key passes` |
| `progression_side` | `{share} of {team}'s progressive passes and carries ended on the {side}` / `{team}'s progression was balanced across the pitch ({l} left, {c} centre, {r} right)` |
| `top_progressor` | `{player} made {n} progressive actions for {team} ({passes} passes, {carries} carries)` |
| `ppda` | `{team} allowed {ppda} opponent passes per defensive action, in the {tercile_display} of Euro 2024 team performances for pressing intensity` |
| `block_height` | `{team}'s average out-of-possession position was in the {tercile_display} of Euro 2024 teams for height` |
| `high_turnovers` | `{team} won the ball within 40 m of goal {n} times, {k} of which ended in a shot` |
| `win_zone` | `{team} won the ball most often in {band_display} ({share})` |
| `pressure_received` | `{player} was under pressure on {share} of their actions, the highest for {team}` |
| `pressure_side` | `{share} of {team}'s pressures were on the {side}` |
| `attacking_contribution` | `{player} ({team}) added {total} expected goals in attack ({shooting} shooting, {passing} passing, {carrying} carrying)` |
| `defending_contribution` | `{player} ({team}) denied {total} expected threat through {n} ball-winning actions` |
| `top_action` | `{player}'s most valuable action was a {action_type} from the {start_side} at {display_minute}, worth {value}` |
| `comparison` (new types) | v2 pattern: the team the label describes first |

## Vocabulary additions

| Finding | Permitted | Never |
|---|---|---|
| `ppda`, `pressures_high` | "pressed", "pressing intensity", "more/less intense than" | "high press" without a tercile, "suffocated", "gegenpress" |
| `block_height` (tercile) | "defended higher/deeper than most Euro 2024 teams" | "low block", "parked the bus" |
| `pressure_received` | "under pressure", "pressured" | "targeted", "funnelled", "isolated" |
| `top_creator`, `xg_by_zone` | "created", "chances came from" | "dictated", "orchestrated", "pulled the strings" |
| `progression_side` | "progressed down", "on the left/right" | "overloaded", "attacked the weak side" |
| contribution | "added", "denied", "most valuable action" | "man of the match", "best player", "dominated" |

## Section structure (D9)

The tactics section becomes paragraphs, in this order:

1. `{team_a} in possession` — cites `chance_creation`, `progression`, in-possession v2 findings.
2. `{team_a} out of possession` — cites `pressing`, `defending`, `block_height`.
3. Same two for `{team_b}`.
4. `Match flow` — v2 context and structure findings (goals, substitutions, formation and role changes), in order.

Output schema: `sentences: [{paragraph, text, finding_ids}]`. `check_grounding`
adds: every cited finding's category is allowed in the sentence's paragraph
(`PARAGRAPH_CATEGORIES` constant).

## Coverage check

New `check_coverage(sentences, findings) -> report`, run after `check_grounding`:

- For each team and each R question (Q1, Q3, Q4), at least one sentence cites a finding of that question's category for that team.
- If no claim-bearing finding exists for that team and category (all suppressed), the question is reported `uncoverable` with the suppression reasons. Not a failure.
- A missed coverable question fails the run (`"publishable": false`), like a grounding failure.
- Report written into `grounding_report.json` under `coverage`.

Unit tests (must-fail / must-pass, as v2 Part 4.6): a summary missing Q4 for one team fails; a summary with Q4 suppressed for that team passes with `uncoverable`; a pressing finding cited in an in-possession paragraph fails.

## Build

Each part is its own PR. Part 0 stops for Tyler's decisions.

### Part 0 — Data audit (docs only, stop)

Write `ai/match_summary/AUDIT-v3.md` answering:

1. Do 3943043's events contain `obv_*` fields? Which event types carry them?
2. Do events carry a `counterpress` flag? On which types? (tier 2)
3. Are raw events (and 360) for all 51 Euro 2024 matches available locally? If not, how does the existing pipeline fetch them?
4. Does `progressive_map` exist, and what is its exact definition?
5. Exact outcome values used for successful Tackle, Interception and Ball Recovery in this data.
6. Presence of `pass.cross`, `pass.cut_back`, through-ball technique, `pass.shot_assist`, `pass.goal_assist`, `under_pressure`.
7. Where minutes played per player can be read from.
8. Whether `socceraction` installs and loads local StatsBomb JSON without network access.

Stop. Tyler updates this spec's decisions from the audit.

### Part 1 — Tier 1 extractors

One module per concept in `libs/statsbomb/`, each with module docstring, Public API, JSON shape and unit tests on a hand-checked sample:
`extract_chance_creation.py`, `extract_progression.py`, `extract_pressing.py`, `extract_defending.py`. Output per match in `data/euro-2024/{match_id}/`.

### Part 2 — Reference data

- `scripts/build_euro2024_reference.py`: runs the Part 1 extractors on all 51 matches, writes `reference_distributions.json` for every tercile-labelled measure.
- Fits and writes `xt_grid_v1.json`.
- Unit test: tercile labelling on a synthetic distribution, including values exactly on a cut point (lower tercile owns the cut).

### Part 3 — Player contribution

`libs/statsbomb/extract_player_contribution.py`: per-player category values and top actions for one match, reading raw events and `xt_grid_v1.json`. Unit tests per "Validation".

### Part 4 — Findings and claims

Extend `derive_tactical_findings.py` and `tactical_definitions.py` with every tier 1 finding, template and constant above. Bump `DEFINITIONS_VERSION` to `0.2.0`. Integration test values set after Tyler's hand-check.

### Part 5 — Generation, coverage and key performers

1. Tactics call: paragraph structure, `PARAGRAPH_CATEGORIES`, `check_coverage`.
2. Key performers section rendered in Python from contribution findings; the model call for that section is removed.
3. Unit tests for `check_coverage` and the paragraph rule.

### Part 6 — Re-run and record

- Generate three times; pass = `check_grounding` and `check_coverage` pass on all three.
- Tyler's manual read: does each team's approach come through? Are the standout lists defensible?
- Update `FAILURE-TAXONOMY.md`: D10 and D11 status, the D11 judge criterion replaced by the code check, and any new failures.
- `VERIFICATION-3943043-v3.md` written by script.

### Tier 2 (after Module 3)

Q8–Q12, one PR each, same pattern: definitions and templates added here and
accepted, extractor + tests, findings, Part 6 re-run.

## Out of scope

- Summaries or findings for any match other than 3943043 (other matches feed only the reference data and the xT grid).
- Tracking-only questions (line height, compactness, triggers, rest defence).
- Goalkeeper contribution.
- Per-90 normalisation (single match; raw totals with a minutes floor).
- Causal claims. v2's linking rule still applies.
- Judges (Module 3 eval) and phrasing relaxation (Module 4).

## Decisions to accept or change

| # | Decision | Proposed | Why / effect if changed |
|---|---|---|---|
| 1 | Required questions | Q1, Q3, Q4 per team | More required = more runs fail on suppression edge cases |
| 2 | Tier 1 scope before Module 3 wraps | Q1–Q7 | Tier 2 adds five more extractors |
| 3 | Label anchor | Euro 2024 terciles (102 team-matches) | Fixed thresholds would be guesses; terciles are relative only to this tournament |
| 4 | Read other 50 matches for reference data | Yes, read-only | Without it: no xT grid, no absolute labels |
| 5 | Rating structure | g+-style categories, separate attacking / defending rankings | A combined score needs invented weights |
| 6 | Passing/carrying value | xT (own, explainable); OBV only as cross-check if present | Alternative: use OBV directly if Part 0 finds it |
| 7 | Failed passes | Not penalised (socceraction xT) | Penalising needs a turnover-cost rule we'd invent |
| 8 | Defending value | Threat denied via xT grid (own approximation) | Alternative: count-based ranking (recoveries + interceptions) |
| 9 | Goalkeepers | Excluded | Saves need a post-shot model we don't have |
| 10 | `TOP_N`, `MIN_MINUTES` | 3, 20 | |
| 11 | Key performers rendered without a model | Yes | Model adds nothing when code selects and writes |
| 12 | PPDA zone | Opponent's own 60% (StatsBomb x < 72 in their frame) | Matches the published PPDA variant |
| 13 | `HIGH_TURNOVER_X` | 76 (≈ 40 m) | |
| 14 | Section structure | By team and phase, match flow last | Chronological order is what made it read as a recounting |

## Decision log

- **2026-10-15:** drafted from the D9–D11 review and research on player ratings and analyst questions.

## Ships

Part 0 audit, then Parts 1–6 merged as six PRs, with
`reference_distributions.json`, `xt_grid_v1.json`, regenerated findings,
`grounding_report.json` (with coverage) and `VERIFICATION-3943043-v3.md`
committed. Tier 2 after Module 3.
