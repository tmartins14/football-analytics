---
title: Curriculum bootstrap and early analyses
status: superseded
started: 2026-04-12
completed: 2026-05-29
repo: football-analytics
area: literature_notes, analyses
related_prs: []
related_docs: []
tags: [bootstrap, curriculum, literature-review, practice-questions]
---

# Curriculum bootstrap and early analyses

## Summary

The repo's first six weeks: standing up the initial commit, drafting a
football-analytics curriculum/syllabus, working through a literature-review
pass on core analytics concepts, then a short run of practice-question
notebooks. Entirely pre-dates the `libs/`/`ai/`/`apps/` structure and the
PR workflow — everything here landed as direct commits to `main`.

## Context

Starting point for the whole project: before any shared library code
existed, the work was literature review (reading and reacting to published
analytics methods) and small one-off analysis notebooks, to build
footballing/analytics domain knowledge before building reusable tooling.

## What was done

- Initial commit, a "Phase 1" syllabus, and the first curriculum
  architecture pass (`curriculum architecture built`, 2026-04-17).
- A literature-review series, one topic per notes file: defensive structure
  and pressing, positional play, build-up play and possession metrics,
  counter-attacking, xG, VAEP, xT, xT vs. VAEP, EPV, PSxG, Wide Open Spaces,
  OBSO, Brefeld et al., SkillCorner progressive passing (2026-04-17 →
  2026-05-11).
- A notes-folder restructuring pass (2026-05-12).
- First practice-question notebooks: pressing effectiveness (Q1), xG vs.
  actual conversion rate by shot location (Q3) (2026-05-19 → 2026-05-20).
- Euro 2024 corners data exploration and World Cup 2026 bracket code
  (2026-05-26 → 2026-05-29).

## Outcome

Superseded by everything that followed: the curriculum itself moved out of
this repo entirely (it now lives at `../_contexts/CURRICULUM.md`, a
sibling folder to both `football-analytics` and `tylermartins.com`, mapped
to Chip Huyen's *AI Engineering* chapters), and the practice-question
pattern continued at much greater scale under `analyses/practice_questions/`
(25 sequenced questions by the time of later work, not individually
recorded here). The literature notes under `literature_notes/` are still
in the repo and still useful background reading; they just predate any of
the code conventions later docs in this folder describe.

## Where to look for more

- `literature_notes/`, `research/`, `match_reactions/` — the content
  itself.
- `../../../_contexts/CURRICULUM.md` (outside this repo) — where the
  curriculum structure these notes were building toward now lives.
- `git log --oneline 74da62e..73e2fc6` for the exact commit range.
