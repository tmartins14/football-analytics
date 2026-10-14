---
title: Restructure into libs/ + apps/, then consolidate ai/match_summary
status: done
started: 2026-08-23
completed: 2026-09-14
repo: football-analytics
area: libs/, ai/
related_prs: [4, 9]
related_docs: [docs/ARCHITECTURE.md]
tags: [restructure, architecture, libs, apps, ai-directory]
---

# Restructure into libs/ + apps/, then consolidate ai/match_summary

## Summary

Two related restructuring passes, three weeks apart: first moving
`statsbomb`/`footballd3` from `src/` into `libs/` and reserving `apps/` for
future non-AI deployables (with the first version of what's now
`docs/ARCHITECTURE.md`), then pulling the match-summary project's code,
specs, and generated output together into one self-contained `ai/match_summary/`
directory instead of splitting them across `libs/statsbomb/`,
`docs/specs/match-summary/`, and `data/euro-2024/`. Together, these two
commits are why the repo looks the way `docs/ARCHITECTURE.md` describes it.

## Context

By mid-August the repo had grown organically (`src/`, ad hoc spec
locations) without anyone having had to navigate it by name before. The
first pass gave the top-level layout real categories. The second pass
responded to a concrete problem the first `ai/`-style project
(match-summary) had already hit: its code, its spec, and its output were
in three different places, which made the project hard to review or reason
about as a whole.

## What was done

### 2026-08-23 — libs/ + apps/ (PR #4, branch `restructure-libs-apps`)

Moved `statsbomb` and `footballd3` from `src/` into `libs/`, added an empty
`apps/` directory reserved for future non-AI deployable consumers, and
wrote `docs/ARCHITECTURE.md`'s first version (committed at the time as
`.claude/ARCHITECTURE.md` — see the Spec Kit scaffolding task for when it
moved to `docs/`). Also fixed a stale `src/statsbomb` path left behind in
the match-summary SPEC by the move.

### 2026-09-14 — ai/ directory consolidation (PR #9, branch
`chore/create-ai-directory`)

One commit, `de01e5e`: *"Consolidates generate_match_summary (code,
specs, and generated output) from `libs/statsbomb/`,
`docs/specs/match-summary/`, and `data/euro-2024/` into a single
self-contained `ai/match_summary/` project."* This is also the commit that
emptied `docs/specs/` — `SPEC.md`, `DATA-SPEC.md`, and
`VERIFICATION-3943043.md` were deleted from `docs/specs/match-summary/`
and re-added under `ai/match_summary/` in the same commit, establishing
the convention `docs/ARCHITECTURE.md` still states today: AI-project specs
live inside `ai/<project>/`, not `docs/specs/`. (`docs/specs/` sat empty
from this point until this documentation task repurposed it for task
records like this one.)

## Key decisions

- **AI-engineering projects are self-contained.** Code, spec, and output
  co-located under `ai/<project>/`, rather than split by *kind* of
  artifact across `libs/`, `docs/specs/`, and `data/`. This is still the
  rule: `docs/ARCHITECTURE.md`'s `ai/` section states it directly, and
  every DATA-SPEC-v2 PR since has followed it (`ai/match_summary/` holds
  the spec, the findings code lives in `libs/statsbomb/` because it's a
  reusable library module, not because the self-containment rule was
  dropped — see `2026-10-data-spec-v2-tactical-findings.md`).
- **`apps/` is reserved, not retrofitted.** The legacy
  `pages/match-analysis/` dashboard predates this convention and was
  explicitly left where it is rather than folded into the new `apps/`
  structure.

## Outcome

Done; both changes are merged and current. `docs/ARCHITECTURE.md` is the
living reference for the structure these two commits established — this
doc exists so the *reasoning* behind that structure has a home too.

## Where to look for more

- `docs/ARCHITECTURE.md` — the structure itself, as it stands today.
- `git show de01e5e --stat` — the exact file moves for the `ai/`
  consolidation.
