# DATA-SPEC v2 — Tactical Findings Layer

Status: accepted 2026-10-12. Thresholds are provisional (calibrated on one match). Ready for Part 0.
Module: AI Engineering Learning Vault — Module 2/3 bridge (deterministic inputs before evals)
Owner: Tyler (Plan, definitions, review) / Claude (Execute, Verify)
Related: [SPEC.md](./SPEC.md), [DATA-SPEC.md](./DATA-SPEC.md), [VERIFICATION-3943043.md](./VERIFICATION-3943043.md), [FAILURE-TAXONOMY.md](./FAILURE-TAXONOMY.md)
Intended path: `ai/match_summary/DATA-SPEC-v2.md`
Match in scope: `3943043` (Spain vs England, Euro 2024 Final) only

## Goal

Replace the raw JSON the tactics call reads today with a deterministic set of
labelled **findings** computed in Python. Each finding carries a **claim**: the
exact clause the prose may use to state it. The model selects findings, orders
them and joins their claims. It never interprets coordinates or counts, and it
never writes a factual clause itself.

The tactics section states **what happened, in order**. It does not explain why
(see "After this spec").

## Why

`generate_tactics_section` sends three raw extractor files and a list of
prohibitions. Every defect logged so far is an interpretation error, not an
invented number:

| # | Defect | Run | Root cause |
|---|---|---|---|
| D1 | Off-ball centroid labelled "on-ball" | Both | No field semantics in the prompt |
| D2 | "England more central than Spain", backwards | Module 1 | Model did the comparison itself |
| D3 | Stones named as a hull vertex | Module 1 | Model read hull geometry |
| D4 | Walker "high and central" at y=69 | Module 1 | No thresholds for wide/central |
| D5 | Edge counts summed for Spain, single-direction for England | Module 1 | Model did arithmetic |
| D6 | "Shape held until 89' when Nacho, Merino and Oyarzabal came on" (they came on at 82', 88', 67') | Committed | `formation` periods are Tactical-Shift based and do not line up with substitutions |
| D7 | Spain's "back three" in a 4-2-3-1 | Committed | Unsupported shape label |
| D8 | Claims about the 88'–FT window (1 pass) | Module 1 | No minimum sample |

D1–D5 and D8 are from `VERIFICATION-3943043.md`. D6 and D7 were found on
2026-10-07 reading the committed `match_summary.md`; they are not in that file yet.
All eight are classified, with the gate that now catches each one, in
`FAILURE-TAXONOMY.md`.

## Seam rules

1. Python computes every label, comparison, sum, change and claim string. The model computes nothing and states no fact in its own words.
2. The tactics call receives findings only. No raw extractor JSON, no coordinates outside a finding's `evidence`.
3. Findings read **extractor JSON** in `data/euro-2024/{match_id}/`, not raw StatsBomb events. If a finding needs something the JSON lacks, the extractor changes first (Part 0).
4. Every threshold, display format and claim template is a named constant in one file, and every finding records the constant and the definitions version that produced it.
5. A finding with too little data is not emitted. There is no "low confidence" finding.

## Two things the data check turned up (read before the definitions)

Both were checked on 2026-10-07 against the raw StatsBomb event and 360 files
for this match, not just the committed JSON.

### A. `off_ball` in `team_shape_*.json` mixes two coordinate frames

- StatsBomb coordinates already have each team attacking left to right in both
  halves. Mean shot x is 104–108 and mean goalkeeper event x is 9–16 for both
  teams in both periods. So `_attack_direction_by_period` always returns
  "right" and never flips. The module docstring ("raw StatsBomb events use the
  physical pitch coordinate system") is wrong, but on-ball output is unaffected.
- A 360 freeze frame is in the frame of the **event's actor**. When the
  opponent acts, our players' dots are in the opponent's frame, where high x
  means near our own goal. The extractor does not mirror them.
- `extract_team_shape_off_ball` pools dots from opponent-actor events (about
  85% of dots) with dots from our own defensive events such as Pressure (about
  15%), which are in our frame. The published centroid is an average of two
  mirrored frames.

| | Published `off_ball.centroid.x` | Opponent-actor dots | Own-actor dots | Corrected, own attack-right frame |
|---|---|---|---|---|
| Spain | 62.21 | 64.67 | 49.98 | 54.44 (55.05 excluding keeper) |
| England | 69.84 | 74.22 | 40.88 | 45.14 (45.98 excluding keeper) |

Reproducing the extractor's filter gives 62.21 and 69.84 exactly, so the
replication is faithful. Corrected, England's out-of-possession positions sit
about 9 yards **deeper** than Spain's. The committed prose says England's shape
"centred further upfield (69.8, 39.2)", which is wrong in label (D1) and in
direction. `ellipse`, `thirds_spine`, `depth_line` and `density_grid` are
built from the same pooled cloud and are affected too. Not checked: whether
the team-shape view on tylermartins.com renders this grid.

### B. A mean position hides flank switching

On-ball `nodes` carry only a mean x and y. Nico Williams' first-half open-play
touches: 23 left wing, 15 left half-space, 4 centre, 3 right half-space, 9
right wing. His mean y is 29–30, which would label a left winger as playing
between the left half-space and the centre. Zone labels therefore need the
touch distribution, not the mean.

These counts are from raw events with an open-play, in-possession filter. The
extractor's own filter gives slightly different totals (51 events for Williams
against 54 here), so Part 3's fixture values for `player_zone` are set after
Part 0 regenerates the JSON, not from this document.

## Scope

Five categories, all from files that already exist for this match.

| Category | Findings | Source file |
|---|---|---|
| Context | `final_score`, `goal`, `game_state` | `match_stats.json`, `shots.json` |
| Structure | `formation`, `formation_change`, `substitution`, `role_change` | `formation_*.json`, `substitutes.json` |
| Shape in possession | `player_zone`, `team_height`, `team_width` | `team_shape_*.json` → `on_ball` |
| Shape out of possession | `block_height` | `team_shape_*.json` → `off_ball` (after Part 0) |
| Passing structure | `hub`, `no_hub`, `top_pair`, `concentration` | `pass_network_*.json` |

Plus two cross-cutting types computed from the above: `comparison` (team vs
team) and `change` (window vs previous window).

Notes:

- **Context is included.** The section narrates the match in order, so it gets the score and goals as findings.
- **Side bias moves to the progression category (Part 6).** `pass_network` has only a mean position per passer, so a per-lane pass share from it would be a proxy.
- **Hull vertices are not a finding.** The hull stays a rendering artefact for D3. `player_zone` covers what the prose was trying to say.
- **No compactness finding out of possession.** The pooled cloud spans every ball position in the match, so its spread measures where the ball was, not how tight the team was.

## Coordinate and display conventions (constants)

- Pitch 120 × 80 yards, analysed team attacks toward x = 120. y = 0 is the team's left touchline (Left Back template y = 12).
- **Lanes (y):** `left_wing` 0–18, `left_half_space` 18–30, `centre` 30–50, `right_half_space` 50–62, `right_wing` 62–80. Edges are the penalty-area and six-yard-box lines. `LANE_DISPLAY` maps each to prose ("left wing", "left half-space", "centre", ...).
- **Bands (x):** `own_third` 0–40, `own_half` 40–60, `opposition_half` 60–80, `final_third` 80–120. `BAND_DISPLAY` maps each to prose.
- **Minutes.** StatsBomb `minute` is elapsed minutes and keeps counting through stoppage time. `display_minute(minute, period)` returns a string:
  - period 1, minute ≥ 45 → `45+{minute − 44}'` (minute 45 → `45+1'`)
  - period 2, minute ≥ 90 → `90+{minute − 89}'` (minute 90 → `90+1'`)
  - otherwise → `{minute + 1}'` (goals at minutes 46, 72, 85 → `47'`, `73'`, `86'`)
  - period > 2 → raise. Extra time is out of scope.

  Every minute-bearing finding carries `minute`, `period` and `display_minute` in `evidence`. Prose and claims use `display_minute` only.
- **Window text.** Boundaries go through `display_minute`. The first boundary of a match reads "kick-off" and the last reads "full time" (e.g. "kick-off to 46'", "68' to full time").
- **Number formats.** `DISPLAY_FORMATS`: percentages to one decimal with a `%` sign, yards to one decimal followed by "yards", counts as integers.

## Finding schema

One JSON object per finding. Field order as listed.

| Field | Type | Notes |
|---|---|---|
| `id` | str | Stable and readable: `{category}.{type}.{team_code}.{window}[.{subject}]`, e.g. `pass.hub.ESP.w0.laporte` |
| `category` | str | `context`, `structure`, `in_possession`, `out_of_possession`, `passing` |
| `type` | str | One of the finding names above, or `comparison` / `change` |
| `team` | str \| null | Null for match-level findings |
| `window` | obj \| null | `{index, from_minute, to_minute, source, text}`. `source` names which windowing the file uses; `text` follows "Window text" |
| `game_states` | list[str] | Every state overlapping the window: `level`, `leading`, `trailing`, from the team's side |
| `subject` | obj \| null | `{player, display_name}` or `{pair: [..]}` |
| `label` | str \| null | The only thing the vocabulary keys on. Null for value-only findings |
| `value` | number \| str \| obj | The headline quantity |
| `claim` | str \| null | The clause that states this finding in prose, rendered from `CLAIM_TEMPLATES`. No terminal punctuation. Null for value-only findings, which cannot be cited alone |
| `evidence` | obj | Every number behind the finding, with the source path for each |
| `threshold` | obj \| null | `{constant, value}` that produced the label |
| `notability` | float | See "Notability" |
| `definitions_version` | str | From `tactical_definitions.py` |

Output file: `data/euro-2024/{match_id}/tactical_findings.json`, shape
`{"findings": [...], "suppressed": [...], "metadata": {...}}`. `suppressed`
lists every finding that was not emitted, with the rule that stopped it, so a
missing finding is explainable.

## Definitions and thresholds

Observed values are from the committed JSON for match 3943043. All thresholds
are provisional until calibrated on more matches (decision 11).

### Context

- **`final_score`**: `match_stats.home.score`, `match_stats.away.score`. → Spain 2, England 1.
- **`goal`**: one per `shots.json` entry with `is_goal`. → Williams 46, Palmer 72, Oyarzabal 85 (display 47', 73', 86').
- **`game_state`**: segments between goals. → 0–46 level, 46–72 Spain leading, 72–85 level, 85–FT Spain leading.

### Structure

- **`formation`**: one per `formation.periods[]`: formation string, from and to minute.
- **`formation_change`**: consecutive periods with different formation strings. → England 89: 4-2-3-1 → 4-1-2-1-2. Spain: none.
- **`substitution`**: one per entry in `substitutes.json` (never from `formation` periods, which caused D6). Fields: minute, period, second, player on, player off, position on entry.
- **`role_change`**: same `player_id` in consecutive formation periods with a different `position` string. → England 69: Bellingham Left Wing → Right Defensive Midfield, Foden Center Attacking Midfield → Left Wing. England 89: Rice, Saka, Bellingham, Watkins. Spain 89: Olmo Center Attacking Midfield → Right Wing.

No thresholds. These are copied facts.

### Shape in possession

Windows are the `on_ball.periods[]` (lineup periods).

- **`player_zone`**: label is `{lane}` and `{band}` for one player in one window.
  - Needs `lane_counts` and `band_counts` per node (Part 0).
  - Lane label = modal lane if its share ≥ `MODAL_SHARE` (0.50), else `mixed` with the top two lanes in `evidence`. Same rule for band.
  - Suppressed if `event_count` < `MIN_NODE_EVENTS` (10).
  - → Yamal H1: `right_wing` (32 of 44 touches). Williams H1: `mixed` (left wing 23, left half-space 15, right wing 9 of 54).
- **`team_height`**: event-weighted mean x of eligible outfield nodes. Label `own_half` or `opposition_half` against the halfway line (60).
  - → Spain 0–45: 65.9, `opposition_half`. England 0–60: 59.5, `own_half`.
- **`team_width`**: max y minus min y across eligible outfield nodes. Value only, no label, no claim.
  - → Spain 60.8, England 59.8.
- Both team-level findings are suppressed unless at least `MIN_ELIGIBLE_OUTFIELD` (8) outfield nodes pass `MIN_NODE_EVENTS`.

Consequence on this match: only the first window of each team emits team-level
findings. After the first substitution the windows hold 0–4 eligible players.
That is correct behaviour, and it is a limit of windowing by substitution.

### Shape out of possession

- **`block_height`**: mean x of the team's 360 dots while the opponent has the ball, open play, keeper excluded, **in the team's own attack-right frame**. Value only, no absolute label, no claim.
  - → Spain 55.05, England 45.98 (computed from raw files; the committed JSON cannot produce this until Part 0).
  - Whole match only. The extractor does not window off-ball data.
  - `evidence` carries the extractor's `camera_caveat`.

### Passing structure

Windows are `pass_network.windows[]`. All findings in a window are suppressed
if the window's completed passes < `MIN_WINDOW_PASSES` (40).

- **Involvement share** (used below) = (passes made + passes received) ÷ (2 × window passes), from `edges`.
- **`hub`**: involvement share ≥ `HUB_SHARE` (0.15).
  - → Spain 0–45: Le Normand 16.5%, Laporte 16.4%. Spain 67–82: Le Normand 17.0%, Laporte 15.4%. Spain 45–67: none (Fabián Ruiz 14.3%). England 0–60: none (Stones 12.8%, Walker 12.2%, Rice 12.0%).
- **`no_hub`**: emitted when a window has no hub, so "evenly spread" is a grounded statement. Carries the most involved player and share in `evidence`. → England 0–60, Spain 45–67.
- **`top_pair`**: top 3 pairs by **bidirectional** total, each ≥ `MIN_PAIR_COUNT` (8).
  - → Spain 0–45: Laporte–Le Normand 31, Carvajal–Le Normand 23, then Laporte–Cucurella and Laporte–Rodri tied on 16. England 0–60: Stones–Pickford 13, Rice–Bellingham 11, Stones–Walker 10.
  - Ties at the cut are all emitted.
- **`concentration`**: involvement share of the top 3 players. Value only, no claim.
  - → Spain 0–45: 44.8%. England 0–60: 37.0%.

Consequence on this match: England's 60–69 (28 passes), 69–89 (38) and 89–FT
(4) windows are suppressed, as are Spain's 82–88 (30) and 88–FT (1). The
"Palmer became the central link after 69'" claim in the current prose would no
longer be available. That claim rests on a 5-pass pair in a 38-pass window.

### Cross-cutting

- **`comparison`**: same finding type, both teams. Emitted only when the gap ≥ the type's minimum.
  - `block_height`: `COMPARE_MIN_YARDS` (5). → England deeper by 9.1.
  - `team_height`: `COMPARE_MIN_YARDS` (5), first windows only. Both windows appear in the claim, because they differ in length (0–45 vs 0–60). → Spain higher by 6.4.
  - `team_width`: `COMPARE_MIN_YARDS` (5). → gap 1.0, not emitted.
  - `concentration`: `COMPARE_MIN_POINTS` (5). → Spain more concentrated by 7.8 points.
  - Label is the direction: `higher` / `deeper`, `wider` / `narrower`, `more_concentrated` / `more_distributed`. The claim always names the team the label describes first, so direction is fixed by the template.
- **`change`**: same team, same finding type, consecutive **emitted** windows.
  - Hub change: a player's involvement share moves by ≥ `CHANGE_MIN_SHARE` (0.04) **and** crosses `HUB_SHARE`. → none on this match (Laporte 16.4% → 12.6% is a 3.8-point move).
  - `formation_change` and `role_change` are already change findings and are not duplicated.

### Rule for which findings get an absolute label

A label needs an anchor on the pitch (halfway line, penalty-area lines). Where
there is no anchor, the finding is value-only (null `claim`) and reaches the
prose only through a `comparison`. `block_height`, `team_width` and
`concentration` get absolute labels only after the thresholds are calibrated on
more matches.

## Claims

Every finding with a non-null `claim` gets it from `CLAIM_TEMPLATES` in
`tactical_definitions.py`. Templates use the display conventions above. The
wording below is the contract; the integration test (Part 3) asserts the
rendered strings for this match, and Tyler hand-checks them once.

| Type / label | Template |
|---|---|
| `final_score` | `{winner} beat {loser} {w}–{l}` (draw: `{home} and {away} drew {h}–{a}`) |
| `goal` | `{player} scored for {team} ({display_minute})` → "Nico Williams scored for Spain (47')" |
| `game_state` | `{team} led {score} from {from} to {to}` / `the score was level at {score} from {from} to {to}` |
| `formation` | `{team} played a {formation} from {from} to {to}` |
| `formation_change` | `{team} changed from a {old} to a {new} ({display_minute})` |
| `substitution` | `{on} replaced {off} for {team} ({display_minute})` |
| `role_change` | `{player} moved from {old_position} to {new_position} ({display_minute})` |
| `player_zone` lane | `{player} took {n} of {total} touches on the {lane} ({window})` |
| `player_zone` `mixed` | `{player} split touches between the {lane1} ({n1}) and the {lane2} ({n2}) ({window})` |
| `team_height` | `{team}'s average position in possession was in {their own half \| the opposition half} ({window})` |
| `hub` | `{player} was a hub for {team}, involved in {share} of passes ({window})` |
| `no_hub` | `{team}'s passing had no single hub; the most involved player, {player}, had {share} ({window})` |
| `top_pair` | `{a} and {b} combined {n} times ({window})` |
| `comparison` `block_height` | `{deeper}'s average out-of-possession position was {gap} deeper than {other}'s` |
| `comparison` `team_height` | `{higher}'s average position in possession was {gap} higher than {other}'s ({higher} {window_a}, {other} {window_b})` |
| `comparison` `concentration` | `{team}'s passing was more concentrated than {other}'s: the top three players had {a} of involvement against {b} ({window})` |
| `change` hub | `{player}'s passing involvement {rose \| fell} from {a} to {b} ({window_1} to {window_2})` |

Rules:

- Claims have no terminal punctuation and start with a name, a team, or "the".
- Formation strings are copied literally; no "back three/four/five" in any template.
- Player names use `display_name`. Team names are the full team name.
- No template contains a causal word or a word from the "Banned everywhere" list.

The vocabulary table below is the design reference for templates. With
claims in place it constrains Python, not the model.

## Notability

One number per finding so selection can be checked in code.

| Type | Score |
|---|---|
| `formation_change` | 3.0 |
| `goal` | 3.0 |
| `role_change` | 2.0 |
| `substitution` | 1.0 |
| `final_score`, `formation`, `game_state` | 1.0 |
| `hub` | share ÷ `HUB_SHARE` |
| `top_pair` | pair total ÷ window passes ÷ 0.05 |
| `comparison` | gap ÷ the type's minimum gap |
| `change` | delta ÷ the type's minimum delta |
| `player_zone` | 1.0, or 1.5 when the lane differs from the declared position's side |
| `no_hub`, `team_height`, `team_width`, `concentration`, `block_height` | 1.0 |

## Vocabulary (template reference)

| Finding / label | Permitted | Never |
|---|---|---|
| `hub` | "hub", "ran through", "most involved" | "playmaker", "dictated", "controlled" |
| `no_hub` | "evenly spread", "no single hub" | "disjointed", "lacked a focal point" |
| `top_pair` | "combined", "exchanged", with the bidirectional count | a single-direction count |
| `player_zone` lane | the lane name, "wide", "inside" | "inverted", "false 9", any role label |
| `player_zone` `mixed` | "split between", "moved between" | "roamed", "free role" |
| `team_height` | "in the opposition half", "in their own half" | "dominated territory", "pinned back" |
| `block_height` comparison | "deeper", "higher" | "low block", "high press", "parked the bus" |
| `concentration` comparison | "more concentrated", "more evenly shared" | "one-dimensional" |
| `formation`, `formation_change` | the literal formation string | "back three/four/five" unless it is the first number of the string |
| `role_change` | the literal position strings, "moved to" | why the manager did it |

**Banned everywhere** (`BANNED_TERMS`): intent, fatigue, morale, "wanted to", "looked to", "tried to", and the causal words in the linking rule.

## Linking rule

The model writes only the words between claims. Those words come from `CONNECTIVES`:

- **Joining:** "and", "while", "but", "also", "in contrast".
- **Sequence:** "then", "after", "before", "following", "meanwhile". Allowed only when the sentence cites at least one minute-bearing finding (`goal`, `substitution`, `formation_change`, `role_change`, `game_state`, `change`).
- **Causal words are banned** (`CAUSAL_TERMS`): "because", "forced", "allowed", "led to", "as a result", "which meant", "so", "therefore", "due to", "thanks to".

Joining two claims states both and claims no relationship between them.

## Build

Each part is its own PR. PRs, not pushes. CLAUDE.md updates go in a separate one-line commit.

### Part 0 — Extractor fixes (`libs/statsbomb/extract_team_shape.py`)

1. Off-ball: mirror dots from opponent-actor frames (x → 120 − x, y → 80 − y) before pooling. Leave own-actor dots as they are.
2. Off-ball: exclude dots with `keeper == true`.
3. On-ball: add `lane_counts` (5 keys) and `band_counts` (4 keys) to every node.
4. Correct the coordinate-normalisation docstring and `coordinate_note`.
5. Unit test with synthetic frames: an opponent-actor dot at x = 100 lands at x = 20; an own-actor dot at x = 30 stays at 30.
6. Re-run `scripts/extract_euro2024.py` for 3943043 and commit the regenerated `team_shape_*.json`.

Acceptance: regenerated centroid x is 55.05 ± 0.1 for Spain and 45.98 ± 0.1 for England.

### Part 1 — Definitions (`libs/statsbomb/tactical_definitions.py`)

`DEFINITIONS_VERSION = "0.1.0"`, lane and band edges, `LANE_DISPLAY`,
`BAND_DISPLAY`, `DISPLAY_FORMATS`, `display_minute()`, `CLAIM_TEMPLATES`,
`CONNECTIVES`, `CAUSAL_TERMS`, `BANNED_TERMS`, and every threshold named in this
spec. Nothing else defines thresholds, templates or term lists.

Unit tests for `display_minute`: (0, 1) → `1'`; (44, 1) → `45'`; (45, 1) → `45+1'`; (47, 1) → `45+3'`; (45, 2) → `46'`; (89, 2) → `90'`; (90, 2) → `90+1'`; (95, 3) raises.

### Part 2 — Findings (`libs/statsbomb/derive_tactical_findings.py`)

- Public API: `derive_tactical_findings(match_id, data_dir) -> dict`, `main()`.
- `derive_` prefix because it reads extractor JSON, not StatsBomb. Exported from `libs/statsbomb/__init__.py`.
- Join key across files is the full `player` string (`pass_network` nodes have no `player_id`).
- Renders `claim` for every non-value-only finding from `CLAIM_TEMPLATES`.
- Wired into `scripts/extract_euro2024.py` after the extractors it depends on.

### Part 3 — Tests

- `tests/unit/test_derive_tactical_findings.py`: synthetic inputs for every threshold edge (share exactly 0.15, a window of exactly 40 passes, a tie at the pair cut, a `mixed` lane), plus one rendered claim per template.
- `tests/integration/test_tactical_findings_3943043.py`: asserts every "→" value in this spec and every rendered claim for this match. Tyler hand-checks those values and claims once against the JSON; after that they are the fixture.
- The integration test's module docstring states that its values are **regression fixtures**: they prove the code matches this spec, not that the thresholds are right for football.

### Part 4 — Switch the tactics call (`ai/match_summary/generate_match_summary.py`)

1. `generate_tactics_section` reads `tactical_findings.json` and sends findings with a non-null `claim` only. Remove `TACTICS_SOURCE_KEYS`.
2. Output becomes structured (`client.messages.parse`): `sentences: [{text, finding_ids}]`. `tactics.prose` is the sentences joined; `tactics.claims` is the list. The claim map is now an output, not a hand-built table.
3. System prompt: describe **what happened in the match, in order**, using only the supplied findings; pick the most notable; every sentence cites at least one finding ID and contains each cited finding's `claim` word for word; words between claims come only from `CONNECTIVES`, under the linking rule.
4. Remove the instruction that asks for "how the outcome happened". Causal explanation is out of scope for this spec.
5. New `check_grounding(sentences, findings) -> report`, run after generation. Per sentence:
   1. it cites at least one finding ID, and every ID exists and has a non-null `claim`;
   2. every cited claim appears in the text word for word (the first character compared case-insensitively, so a claim can open a sentence or follow a connective);
   3. **leftover check:** remove the cited claims from the text. What remains may contain only `CONNECTIVES`, punctuation and whitespace: no digits, no player or team names, no other words;
   4. a sequence connective appears only if a minute-bearing finding is cited;
   5. no `CAUSAL_TERMS` or `BANNED_TERMS` anywhere in the full text.

   The report records, per sentence, each check's result and the leftover text, so a failure shows exactly what the model added.
6. `tests/unit/test_check_grounding.py` validates the gate itself against hand-written sentences built from this match's findings.
   - **Must fail:**
     - a reversed comparison ("Spain's average out-of-possession position was 9.1 yards deeper than England's");
     - swapped hub numbers (Laporte with Le Normand's share, both hubs cited);
     - a reversed role change (from and to positions swapped);
     - a causal word between two valid claims ("because");
     - a wrong minute (Palmer at 72');
     - a player name in the leftover text;
     - a digit in the leftover text;
     - a sequence word with no minute-bearing finding cited;
     - a cited ID whose claim is absent from the text;
     - an unknown ID.
   - **Must pass:**
     - a claim opening a sentence;
     - a claim after a connective;
     - two claims joined by "and";
     - two claims joined by "while";
     - "after" with a `substitution` cited.

   Acceptance: every must-fail sentence fails and every must-pass sentence passes.
7. Write `output/{match_id}/grounding_report.json` on every run, pass or fail. A failing run is written with `"publishable": false` and `main()` exits non-zero.

### Part 5 — Re-run the baseline

- Baseline (Module 1 run): 15 claim rows. 8 grounded, 4 hard-defect rows (D1–D4), 3 minor (D5 twice, D8). The v1 file's summary line says "11 of 15 fully grounded", which does not match its own table (8 ✅ rows). Use the table.
- Committed run: D1 persists, plus D6 and D7.
- Generate three times (effort settings are not deterministic).
- Pass:
  - `check_grounding` passes on all three;
  - none of D1–D8 appears in any of the three;
  - Tyler's manual read of one run finds zero hard defects.
- Write `VERIFICATION-3943043-v2.md` from `grounding_report.json` by script, with the before/after defect table. Append the D6/D7 note to the v1 file.
- Update `FAILURE-TAXONOMY.md` with anything new the three runs or the manual read turn up, including failures that pass `check_grounding` (those are the Module 3 judge's job).

### Part 6 — New categories, one PR each

**Starts only after the Module 3 judge exists**, so each category's before/after
measures whether the summary got better, not just that nothing broke.

Order: **chance creation** first (it is the raw material for explaining how
goals happened), then progression (side bias lands here), pressing,
transitions, set pieces. Each PR follows the same steps:

1. Definitions, thresholds and claim templates added to this spec, accepted by Tyler.
2. Extractor built or extended, with unit tests against a hand-checked sample (the bar in DATA-SPEC.md).
3. Findings, claim templates and vocabulary rows added.
4. Integration test values and claims for 3943043.
5. Part 5 re-run plus the Module 3 judge, so each category has its own before/after on both facts and quality.

## Conventions

- Python: snake_case, flat `libs/statsbomb/` package, one module per concept, module docstring with Public API and JSON output shape, as in the existing extractors.
- `libs/` never imports from `ai/`.
- Env vars for keys, never literals.
- Docs and test gates (`scripts/check_docs.sh`, `scripts/check_tests.sh`) must pass.

## Out of scope

- Any match other than 3943043. Expansion comes after the eval modules.
- Threshold calibration across matches. Every threshold here is provisional.
- Judges, salience scoring, voice. Those are the eval modules. `check_grounding` is a generation gate, not the eval.
- **Causal explanation ("why").** See "After this spec".
- Extra time (`display_minute` raises on period > 2).
- The outcome section. It is unchanged.
- Syncing `libs/footballd3/sample_data/` or `tylermartins.com` copies of `team_shape_*.json` after Part 0. Known gap, tracked separately.
- Re-windowing on-ball shape by fixed time or by game state.
- Absolute labels for `block_height`, `team_width`, `concentration`.

## What "correct" means

- **Findings:** each value equals an independent recomputation from the source JSON, each label follows from the value and the named constant, and each claim renders from its template. `assert`-able.
- **Prose:** `check_grounding` passes, and `check_grounding` itself passes its must-fail / must-pass suite. Also `assert`-able.
- **The model's job in v1:** choose findings and their order. That is all it controls.
- **Not covered here:** whether the definitions match football (Tyler's review of this document), and whether the model chose the right findings and the result reads well (the Module 3 judge).

## Trade-offs (what I chose not to build)

- **Stiff prose, on purpose.** Word-for-word claims and a connective whitelist make the section read as a sequence of stated facts. That is the strict first version: it makes every factual error a code failure. Exit: in Module 4, the model writes freely and outputs the facts each sentence asserts; code checks those facts against the findings, and a narrow judge (validated against human labels in Module 3) checks that each sentence says what its facts say. The validated judge earns the model freedom to paraphrase.
- **No "why".** A causal claim must be grounded like any other claim, and inferring causes from findings is how D2 happened. Deferred to "After this spec".
- **Fewer findings on this match.** Suppression rules remove the short windows and the Palmer link. Correct but thin.

## After this spec

- **Module 3:** `FAILURE-TAXONOMY.md` is the error-analysis input. The Module 3 eval is a judge on selection and readability, validated against human labels, run alongside `check_grounding`.
- **Module 4:** relax word-for-word claims (see "Trade-offs").
- **Why, step 1 (Part 6):** explanation findings computed in Python, starting with chance creation (e.g. which lane each goal's possession came down). Causal words become allowed only in a sentence that cites an explanation finding. Needs its own definitions, templates and linking-rule update.
- **Why, step 2 (Module 6):** the model proposes an explanation, a tool computes the evidence, and the claim appears only if the evidence supports it. Add this to the Module 6 task in CURRICULUM.md as a dated entry.

## Decisions

| # | Decision | Accepted | Effect on this match if changed |
|---|---|---|---|
| 1 | `HUB_SHARE` | 0.15 (provisional) | At 0.12: Stones (12.8%) and Walker (12.2%) become hubs for England; Rice (11.96%) and Carvajal (11.9%) just miss |
| 2 | `MIN_WINDOW_PASSES` | 40 (provisional) | At 30: Spain 82–88 and England 69–89 emit, which brings back the Palmer link |
| 3 | `MIN_NODE_EVENTS` | 10 (provisional) | At 8: 3 more Spain players in 45–67, still below `MIN_ELIGIBLE_OUTFIELD` |
| 4 | `MODAL_SHARE` | 0.50 (provisional) | At 0.40: Williams H1 becomes `left_wing` (43%) |
| 5 | `MIN_PAIR_COUNT` | 8 (provisional) | Lower adds pairs in the short windows only if decision 2 also changes |
| 6 | `COMPARE_MIN_YARDS` / `COMPARE_MIN_POINTS` | 5 / 5 (provisional) | All three emitted comparisons clear 5 comfortably |
| 7 | Minute convention | `display_minute(minute, period)` with stoppage time | Without it, prose says Oyarzabal scored in the 85th, and first-half stoppage reads as 46'+ |
| 8 | Keeper excluded from `block_height` | Yes | Included: 54.44 and 45.14 |
| 9 | Hull vertices dropped as a finding | Yes | |
| 10 | Module name and location | `libs/statsbomb/derive_tactical_findings.py` | |
| 11 | Match-set size for the later expansion | Open: five were proposed, "the other 9" was mentioned | |
| 12 | Facts reach prose only as Python-rendered claims, word for word | Yes (v1; relaxed in Module 4) | Free-written facts reopen direction flips (D2) |
| 13 | `check_grounding` is a leftover check against a connective whitelist | Yes | |
| 14 | Tactics section scope | What happened, in order. No causal claims | |
| 15 | Part 6 timing and order | After the Module 3 judge; chance creation first | |

## Decision log

- **2026-10-07:** v2 drafted from the D1–D8 defect review and the raw-data check (A, B).
- **2026-10-12:** review changes accepted.
  - Added the `claim` field and `CLAIM_TEMPLATES`.
  - Replaced the number, name and vocabulary checks with the leftover check.
  - Added the must-fail / must-pass suite for `check_grounding`.
  - Made the minute rule stoppage-aware.
  - Scoped the section to "what happened, in order" and moved "why" to Part 6 and Module 6.
  - Marked thresholds provisional and labelled integration values as regression fixtures.
  - Moved the defect table into `FAILURE-TAXONOMY.md`.
  - Moved Part 6 after the Module 3 judge, with chance creation first.

## Ships

This spec and `FAILURE-TAXONOMY.md` as one PR. Then Parts 0–5 merged as six
PRs, with `tactical_findings.json`, `grounding_report.json` and
`VERIFICATION-3943043-v2.md` committed for match 3943043. Part 6 follows the
Module 3 judge, one PR per category.
