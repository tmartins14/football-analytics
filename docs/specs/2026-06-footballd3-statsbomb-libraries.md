---
title: Build the footballd3 and statsbomb libraries
status: done
started: 2026-06-21
completed: 2026-07-20
repo: football-analytics
area: libs/
related_prs: []
related_docs: [docs/ARCHITECTURE.md, docs/tooling.md]
tags: [footballd3, statsbomb, libs, d3, docs-gate]
---

# Build the footballd3 and statsbomb libraries

## Summary

The first real library code in the repo: the `statsbomb` Python extraction
layer and the `footballd3` D3/JS visualization components, built together
component-by-component, plus the documentation-coverage gate that still
governs both today. All direct commits to `main` — this predates the PR
workflow and the later `libs/`/`apps/` restructure (the libraries lived
under `src/` at this point, moved to `libs/` later — see
`2026-08-libs-apps-and-ai-directory-restructure.md`).

## Context

Before this, the repo was literature notes and one-off analysis notebooks.
Nothing reusable existed for pulling StatsBomb open data or rendering it.
This is where that changed: a shared Python extraction layer and a shared
D3 component library, so later features wouldn't each reinvent data
pulling and chart rendering.

## What was done

### 2026-06-21 — starting the libraries, and the docs gate on day one

`Lot's of updates. Mainly starting footballd3 and statsbomb library.`
immediately followed, same day, by `Adding documentation checks` (`4194d41`)
— the original ancestor of today's `scripts/check_docs.sh`. The
documentation gate is as old as the libraries themselves, not something
retrofitted later.

### 2026-06-22 → 2026-07-05 — components, one at a time

Pass network (06-22), freeze frame (06-23), comparison bars and match
stats (06-25), then team shape, formation, convex hull, and progressive
pass map together (06-30), reaching "finished first round of components"
on 07-05.

### 2026-07-18 → 2026-07-20 — the legacy dashboard and first deploy

`Match Dashboard built` (07-18) — the dashboard now living at
`pages/match-analysis/`, the one place that still imports `footballd3`
components by relative path instead of through the package's public
entry points (see `docs/ARCHITECTURE.md`). Cumulative xG chart added
(07-20), then `deploying footballd3` (07-20) — footballd3's first publish,
which is what `tylermartins.com` started consuming the same week (see that
repo's `docs/specs/2026-07-component-library-gallery.md`).

## Outcome

Both libraries existed and were publishable/importable by the end of this
window. `libs/statsbomb` and `libs/footballd3` (renamed from `src/` in
August — see the restructure doc) are still the two foundational libraries
every later `ai/`-project and `tylermartins.com` feature builds on.
`scripts/check_docs.sh`'s three checks (Python docstring coverage via
`interrogate`, JS JSDoc via `eslint-plugin-jsdoc`, a README per
`footballd3` component) all trace back to the single `Adding documentation
checks` commit from day one of this task.

## Where to look for more

- `docs/ARCHITECTURE.md` — current structure of both libraries (this task
  is the reason `libs/` and its "one `extract_*` per concept" / "one
  component folder per concept" conventions exist, though the doc itself
  was written later — see the restructure doc).
- `docs/tooling.md` — the docs gate this task started.
- `libs/statsbomb/README.md`, `libs/footballd3/components/*/README.md` —
  the per-component reference docs the gate requires.
