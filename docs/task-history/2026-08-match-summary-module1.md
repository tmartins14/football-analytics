---
title: "Module 1: auto-written match summary, first vertical slice"
status: done
started: 2026-08-25
completed: 2026-08-31
repo: football-analytics
area: ai/match_summary
related_prs: [5, 6, 7]
related_docs: [ai/match_summary/SPEC.md, ai/match_summary/DATA-SPEC.md, ai/match_summary/VERIFICATION-3943043.md]
tags: [ai-engineering, match-summary, module-1, llm]
---

# Module 1: auto-written match summary, first vertical slice

## Summary

The first AI-engineering project in the repo (Chip Huyen *AI Engineering*
curriculum, Module 1): an auto-written two-part match summary (structured
outcome section + free-prose tactics section) generated from StatsBomb
extractor JSON via the Anthropic Messages API. Established the SPEC /
DATA-SPEC / VERIFICATION pattern every later `ai/match_summary/` task
(including DATA-SPEC-v2) still follows, and the rule — still enforced by
this repo's `CLAUDE.md` — that spec files are managed by Tyler, not edited
by an agent.

## Context

Everything before this was data extraction and visualization (`libs/`).
This is the project's first attempt at having a model *write* something
from that data, and the first place "what correct means" had to be defined
for an LLM-generated artifact rather than a deterministic extractor.

## What was done

- **SPEC.md** (`6496c84`, then a path fix in `6084817`): the goal, scope,
  what "correct" means, and the pass/fail signal for an auto-written
  summary — a manual read-through against source JSON, no automated eval
  yet (that's Module 3).
- **DATA-SPEC.md** (`aca8ce6`): which of the extractors existing at the
  time cover which part of the summary, and the bar new extractors have to
  clear ("unit tests against a hand-checked sample from one match, before
  anything feeds the summary generator") — the same bar DATA-SPEC-v2 Part 6
  cites by name for its own future categories.
- **`generate_match_summary.py`** (`19fb0b3`): the vertical slice itself —
  a structured outcome section via `client.messages.parse` against a
  Pydantic schema, and a free-prose tactics section grounded in a narrower
  three-file slice (formation/team_shape/pass_network). Verified against
  match 3943043 and written up in `VERIFICATION-3943043.md`: 12/12 on the
  outcome section, 2 hard defects and 3 minor issues on the 15-claim
  tactics-section grounding table.
- A `matchSummary` footballd3 component was added on top of this
  (`7486f8a`, PR #6) then reverted the same day (PR #7) — see
  `2026-08-dashboard-component-reverted.md`.

## Key decisions

- **The tactics section's grounding is deliberately narrower than the
  outcome section's.** It receives only formation/team_shape/pass_network
  — no match_stats, no substitutes, no event or shot data — so it
  physically cannot cite a goal, card, or any match event. This
  "physically cannot" framing (narrow the inputs rather than only
  instruct against it) is the same idea DATA-SPEC-v2 later generalized into
  a full findings layer (seam rule 2: "the tactics call receives findings
  only").
- **Spec files are off-limits to the agent.** The verification work in
  this task is what established the rule (now in this repo's `CLAUDE.md`)
  that SPEC/DATA-SPEC files are Tyler's to write and edit, not the agent's
  — code, tests, and generated output are the agent's domain.

## Outcome

Shipped (PRs #5–#7, with #6 reverted). `VERIFICATION-3943043.md` recorded
two hard defects in the tactics section — an off-ball centroid mislabeled
as "on-ball," and a hull vertex misread as a named player position — both
later formally classified and fixed under DATA-SPEC-v2 (defects D1 and D3;
see `2026-10-data-spec-v2-tactical-findings.md`). This task's
`generate_match_summary.py` is still the module DATA-SPEC-v2 Part 4
rewired, not replaced.

## Where to look for more

- `ai/match_summary/SPEC.md`, `DATA-SPEC.md`, `VERIFICATION-3943043.md` —
  the authoritative specs and verification record (do not edit these as an
  agent — see this repo's `CLAUDE.md`).
- `2026-10-data-spec-v2-tactical-findings.md` — where D1/D3 and the rest of
  this task's tactics-section defects were formally fixed.
