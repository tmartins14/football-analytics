---
title: "DATA-SPEC-v2: the tactical findings layer"
status: in-progress
started: 2026-10-12
completed: ongoing
repo: football-analytics
area: libs/statsbomb, ai/match_summary
related_prs: [12, 13, 14, 15, 16, 17, 18]
related_docs: [ai/match_summary/DATA-SPEC-v2.md, ai/match_summary/FAILURE-TAXONOMY.md, ai/match_summary/SPEC.md, ../../../tylermartins.com/docs/specs/2026-09-ai-section.md]
tags: [ai-engineering, data-spec-v2, tactical-findings, statsbomb, llm, grounding]
---

# DATA-SPEC-v2: the tactical findings layer

## Summary

Replaces the match summary's free-prose tactics section — grounded only by
system-prompt instruction, and the source of every defect
`VERIFICATION-3943043.md` found (Module 1) — with a deterministic Python
findings layer: every label, comparison, and claim is computed in code
and handed to the model as a pre-written clause it must state word for
word. Six PRs so far (Parts 0–4 of six planned), each its own merged PR
off `main`; Part 5 (re-running the real baseline against the live API)
and Part 6 (new finding categories, gated on a Module 3 judge that doesn't
exist yet) are still ahead.

## Context

`VERIFICATION-3943043.md`'s tactics-section claim map found two hard
defects and three minor issues in the Module 1 tactics section — every one
an interpretation error (the model mislabeling a field, doing arithmetic
itself, or inferring a direction), not an invented number. DATA-SPEC-v2
reclassifies all eight observed defects (D1–D8, across the Module 1 run
and the later committed run) in `FAILURE-TAXONOMY.md` and maps each to the
cheapest gate that catches it, then builds that gate.

## What was done

### 2026-10-12 — spec accepted, Part 0 (extractor fixes)

`DATA-SPEC-v2.md` and `FAILURE-TAXONOMY.md` added as a docs-only PR (#12),
with a same-day decision-log entry recording six clarifications Tyler
made on the plan before implementation (mirror-vs-period-flip order,
creating `tactical_definitions.py` in Part 0 rather than Part 1, the
lane/band edge interval convention, fixing a stale docstring alongside the
real fix, adding a persisted acceptance test, and how to handle `--force`'s
full-pipeline blast radius).

Part 0 (PR #13) fixed `extract_team_shape.py`: 360 freeze-frame dots from
an opponent-actor frame were being pooled unmirrored with own-actor dots —
averaging two different coordinate frames into one off-ball centroid
(defect D1). Mirrored opponent-actor dots, excluded the keeper, added
`lane_counts`/`band_counts` to every on-ball node, and corrected a
docstring that had the coordinate-normalization logic backwards. Acceptance
value: regenerated centroid x = 55.05 (Spain) / 45.98 (England), ±0.1 —
confirmed against an independent recomputation from raw files, not just
the extractor's own output.

### 2026-10-13 — Part 1 (definitions) and a prerequisite fix

Part 1 (PR #14) built `libs/statsbomb/tactical_definitions.py` out into the
single source of every threshold, display format, and claim template the
spec names: `display_minute()` (stoppage-time-aware), nine named
thresholds, `CLAIM_TEMPLATES` (transcribed from the spec's own Claims
table), and the linking-rule term lists (`CONNECTIVES`, `CAUSAL_TERMS`,
`BANNED_TERMS`).

Starting Part 2 immediately surfaced a foundational gap: `display_minute()`
needs `period` to disambiguate first-half stoppage time from second-half
regular time, and *no* extractor exposed it anywhere. PR #15 added
`period` alongside every `minute` across five extractors
(`extract_shots.py`, `extract_substitutes.py`, `extract_formation.py`,
`extract_team_shape.py`, `extract_pass_network.py`) — handling the subtlety
that a single window can span both halves, so a period belongs to each
boundary, not to the window as a whole. Also found and fixed, along the
way: `extract_substitutes.py` was never wired into
`scripts/extract_euro2024.py`'s pipeline at all, so `--force` silently
never regenerated `substitutes.json`.

### 2026-10-13 — Part 2 (the findings module)

PR #16 built `libs/statsbomb/derive_tactical_findings.py`: every finding
category in the spec (context, structure, shape in/out of possession,
passing structure, plus the cross-cutting `comparison`/`change` types),
reading only already-extracted JSON, never raw StatsBomb events. Verified
ad hoc against every "→" example value named in the spec itself. Two real
bugs found and fixed in the process: a `concentration` comparison was
being suppressed on a large gap because its threshold is in percentage
points but the stored value was a raw fraction, and `top_pair`'s choice of
which player to name first was non-deterministic across repeated runs
(Python's string-hash randomization affecting a `frozenset`'s iteration
order) — fixed with an explicit secondary sort key.

### 2026-10-14 — Parts 3 and 4

Part 3 (PR #17) added the tests Part 2 deliberately didn't ship with (the
spec's own Build order keeps "findings" and "tests" as separate PRs): 22
unit tests against the private category functions with synthetic dicts
covering every named threshold edge, and 27 integration tests asserting
every "→" value and rendered claim against the real match.

Part 4 (PR #18) switched `generate_match_summary.py`'s tactics call over
to the findings layer: removed `TACTICS_SOURCE_KEYS`, added a `Sentences`
structured-output schema (`client.messages.parse`, not `.create()`), a
system prompt grounded only in findings with a non-null claim, and a new
`check_grounding()` gate verifying every sentence states its cited claims
word for word with only whitelisted connectives between them — the exact
mechanism `FAILURE-TAXONOMY.md` had already named as the gate for defect
D2 (a model-stated comparison stated backwards). No live API call was
made anywhere in building or verifying this; `check_grounding` and the
new `main()` orchestration (writing `grounding_report.json`, exiting
non-zero on failure) were both verified against mocked generation.
Discovered along the way that `compare_models.py` (the Module 2 harness —
see `2026-09-module2-sampling-and-comparison.md`) depends on exactly what
Part 4 changed and doesn't exist on `main` at all (it's unmerged on
`feature/match-summary-model-effort`), so its compatible fix stayed local
to that branch rather than going into the Part 4 PR.

## Key decisions

- **Findings are the only seam.** The model never sees raw extractor JSON
  and never computes a comparison, sum, or label itself — every fact
  reaches the prose as a Python-rendered `claim`, word for word. This is
  the single design choice the whole spec is built around (seam rules 1–2),
  directly answering how D2 ("England more central than Spain," backwards)
  happened in Module 1: the model did the comparison itself.
  Word-for-word claims are a deliberately stiff first version — Module 4
  is where the model gets to paraphrase, once a validated judge exists to
  check the paraphrase against the facts.
- **Every PR is one Part, no more.** Tests were deliberately held back to
  their own PR (Part 3) rather than shipped alongside the findings code
  (Part 2) — keeping each merged PR to exactly what its Part says, even
  when it would have been easy to bundle.
- **A planning ambiguity gets asked, not resolved.** Across all five Parts,
  real ambiguities (the period-field gap, `compare_models.py`'s
  compatibility, several finding-schema judgment calls) were surfaced to
  Tyler as explicit questions rather than silently decided — several
  times changing what got built next (the period-fields prerequisite PR
  exists entirely because of one such question).

## Outcome

Parts 0–4 shipped and merged to `main`. Still ahead: **Part 5** (generate
the real tactics section three times against the live API, confirm none
of D1–D8 recur, write `VERIFICATION-3943043-v2.md`) and **Part 6** (new
finding categories — chance creation, progression, pressing, transitions,
set pieces — gated on the Module 3 eval judge, which doesn't exist yet).
`tylermartins.com`'s AI section (see that repo's
`docs/specs/2026-09-ai-section.md`) displays this project's generated
output and will need updating once Part 5 regenerates it.

## Where to look for more

- `ai/match_summary/DATA-SPEC-v2.md` — the authoritative spec, including
  the full Decisions table and decision log (do not edit this as an agent
  — see this repo's `CLAUDE.md`).
- `ai/match_summary/FAILURE-TAXONOMY.md` — the defect classification and
  gate mapping this whole layer is built to satisfy.
- `libs/statsbomb/tactical_definitions.py`,
  `libs/statsbomb/derive_tactical_findings.py`,
  `libs/statsbomb/extract_team_shape.py` — the code.
- PRs #12–#18 on GitHub — the six merged PRs, in order.
