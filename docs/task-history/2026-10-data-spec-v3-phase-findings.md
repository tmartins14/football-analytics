---
title: "DATA-SPEC-v3: phase findings and player contribution"
status: in-progress
started: 2026-10-16
completed: ongoing
repo: football-analytics
area: ai/match_summary
related_prs: []
related_docs: [ai/match_summary/DATA-SPEC-v3.md, ai/match_summary/DATA-SPEC-v2.md, ai/match_summary/FAILURE-TAXONOMY.md]
tags: [ai-engineering, data-spec-v3, tactical-findings, player-contribution, statsbomb, llm]
---

# DATA-SPEC-v3: phase findings and player contribution

## Summary

Extends the tactical findings layer built under DATA-SPEC-v2 with phase-based
questions analysts actually ask (chance creation, progression, pressing,
defending) and a deterministic player contribution rating, closing failure
classes D10 (no team attacking/defensive approach) and D11 (model-chosen key
performers) from `FAILURE-TAXONOMY.md`. Supersedes DATA-SPEC-v2's Part 6
("new categories, one PR each"), which is now a pointer to this document.

## Context

DATA-SPEC-v2 shipped a deterministic findings layer for structure and
possession-shape claims (Parts 0-5), but deferred new finding categories
(chance creation, progression, pressing, transitions, set pieces) to its own
Part 6, gated on a Module 3 judge that didn't exist yet. DATA-SPEC-v3
replaces that gate: rather than waiting on the judge, it adds a code-checked
coverage contract (`check_coverage`) so each required question is answered
per team without needing subjective quality judging first, plus a new
Player Contribution rating (Q7) to replace model-chosen "key performers."

## What was done

### 2026-10-16 — spec accepted, docs-only PR

`DATA-SPEC-v3.md` added (authored by Tyler), and DATA-SPEC-v2's Part 6
section replaced with a one-line pointer to it — the new spec fully owns the
"new finding categories" scope v2's Part 6 used to describe.

## Outcome

Docs landed; Part 0 (data audit) is next, not yet started as of this PR.

## Where to look for more

- `ai/match_summary/DATA-SPEC-v3.md` — the authoritative spec (do not edit
  this as an agent — see this repo's `CLAUDE.md`).
- `ai/match_summary/DATA-SPEC-v2.md` — the superseded Part 6 and everything
  v3 still inherits (seam rules, finding schema, `check_grounding`, etc).
- `ai/match_summary/FAILURE-TAXONOMY.md` — D10/D11, the failures this spec
  closes.
