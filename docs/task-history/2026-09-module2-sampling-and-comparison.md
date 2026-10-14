---
title: "Module 2: sampling decision and the model/effort comparison harness"
status: done
started: 2026-09-15
completed: 2026-09-22
repo: football-analytics
area: ai/match_summary
related_prs: [10]
related_docs: [ai/match_summary/SPEC.md, ai/match_summary/VERIFICATION-3943043.md]
tags: [ai-engineering, module-2, sampling, model-selection, llm]
---

# Module 2: sampling decision and the model/effort comparison harness

## Summary

Chip Huyen *AI Engineering* curriculum Module 2 (foundation-model
selection and sampling), done as two tasks against `ai/match_summary/`:
first discovering and documenting that Claude 5-family models reject
non-default `temperature`/`top_p`/`top_k` and routing around it with
`effort` instead, then building a measured model × effort comparison
harness (`compare_models.py`) to pick per-section routing from evidence
rather than a guess. Task 2's branch
(`feature/match-summary-model-effort`) is still open as of this doc —
its own content shipped, but the branch itself never merged (see
"Outcome").

## Context

Module 1 (see `2026-08-match-summary-module1.md`) shipped a working
generator but with no real basis for which model or effort level to use
for which section — SPEC.md needed an explicit, evidence-backed answer
before this became a "ships" item rather than a guess.

## What was done

### 2026-09-15 — Task 1: sampling decision (PR #10)

`Set explicit per-section effort on match summary generation` (`63d7950`)
then a same-day correction, `Fix Module 2 verification to match the
actually-committed output` (`b0e561b`) — an earlier spot-check had been run
against scratchpad output, not the committed one, and
`VERIFICATION-3943043.md` was corrected in place rather than silently
replaced (the append-and-supersede pattern that doc already followed).
The underlying finding, recorded in SPEC.md's decision log: Claude 5-family
models return a 400 on non-default `temperature`/`top_p`/`top_k`, so
`effort` is the sampling-adjacent knob this project actually has.

### 2026-09-21 → 2026-09-22 — Task 2: the comparison harness

Five cells (model × effort combinations) run once each on match 3943043,
cost/latency/output recorded from real API `usage`, not estimated; per-cell
errors and a "player of the match" check called out by manual read (no
eval system exists yet — that's Module 3); routing chosen from the
results (Sonnet 5 at `low` effort for the outcome section, Opus 5 at
`medium` for tactics); the match summary regenerated and re-verified on
that routing; results moved into the output folder with a site export;
per-section effort recorded in the generated output's own metadata.

## Key decisions

- **Cost and correctness are measured, not estimated.** Every cell's
  token counts come from the response's own `usage` field; a call with
  missing/incomplete usage is a *failed* data point, not an estimate
  filled in. No prompt caching, no server-side refusal fallback, no
  automatic retry — any of those would change which model actually
  answered.
- **The routing is an explicit default, not a final answer.** SPEC.md and
  the harness's own code comments both say this directly: n = 1 per cell,
  graded by manual read, "to be revisited once the eval system (Module 3)
  exists." It's the best evidence available before an eval exists, not a
  claim that it's optimal.

## Outcome

The sampling/routing decision shipped and is live: `generate_match_summary.py`
still uses the Sonnet-5-low / Opus-5-medium split this task picked.
**The branch that built the comparison harness
(`feature/match-summary-model-effort`) is still open, unmerged into
`main`**, as of the DATA-SPEC-v2 work (see
`2026-10-data-spec-v2-tactical-findings.md`) that was done from a local
checkout of this same branch. `compare_models.py` and its test file exist
only there, not on `main` — DATA-SPEC-v2 Part 4 had to route around that
when it changed the tactics call's shape (see that doc's "2026-10-14 —
Part 4" entry for exactly what broke and how it was fixed, locally, on
this branch).

## Where to look for more

- `ai/match_summary/SPEC.md`'s "Module 2" section and decision log — the
  rate table, acceptance criteria, and the sampling-controls finding.
- `ai/match_summary/output/3943043/comparison-3943043.md` — the results
  table.
- `ai/match_summary/compare_models.py` (on `feature/match-summary-model-effort`
  only, not `main`) — the harness itself.
