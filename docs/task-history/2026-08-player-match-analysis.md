---
title: Player Match Analysis extractors, components, and the test gate
status: done
started: 2026-08-05
completed: 2026-08-10
repo: football-analytics
area: libs/statsbomb, libs/footballd3
related_prs: [1, 2, 3]
related_docs: [docs/testing.md]
tags: [player-match-analysis, testing, statsbomb, footballd3]
---

# Player Match Analysis extractors, components, and the test gate

## Summary

Built the player-level match-analysis extractors and footballd3 components
(heatmaps, action feed, highlight reel, lineup selector, timeline) and, in
the same branch, the repo's first automated test suite — pytest for
`statsbomb`, vitest for `footballd3`. `docs/testing.md`'s regression tests
are literally the bugs found while building this.

## Context

Before this, verification was manual: run an extractor, eyeball the JSON,
count a roster by hand. That caught real bugs but nothing was repeatable —
the next change could silently reintroduce any of them. This task is where
that manual verification became a gate.

## What was done

### 2026-08-05 — extractors, components, and the first test suite (PR #1)

Added the player-match-analysis data extractors and footballd3 components,
then — same day — the pytest/vitest test suite covering them. Four
specific bugs this first pass found and turned into permanent regression
tests (per `docs/testing.md`): a fabricated `"Tackle"` top-level event type
that doesn't exist in StatsBomb data (`Tackle` is a `duel_type` qualifier
on `Duel`), 4 of 7 substitutions silently missing because the roster was
sourced from Tactical-Shift-based formation periods instead of
`sb.lineups()`, `on_minute`/`on_second` floats instead of ints, and a `None`
field silently becoming an invalid JSON `NaN` token.

### 2026-08-06 → 2026-08-09 — wiring the page, review-fix passes (PR #2)

A dense run of fix commits against real review feedback, phases D through
G: SSR crash, heatmap orientation, goal-mouth indexing and aspect ratio,
highlight-reel rebuild, lineup-selector rebuild, action-feed scroll/
indentation and shape-coded event types, event-hover tooltip bug, and
several rounds of visual-polish fixes (selection ring, bench overlap,
scaling shot markers with frame size).

### 2026-08-10 — publish and type declarations (PR #3)

Bumped footballd3 to 0.1.2 for publish and added type declarations for the
nine footballd3 components this task had left untyped.

## Key decisions

- **Roster source of truth is `sb.lineups()`, not formation periods.**
  Tactical-Shift-triggered formation periods don't line up with every
  substitution, so a roster built from them silently drops any substitute
  whose entry wasn't accompanied by a reshuffle. This is the same failure
  mode DATA-SPEC-v2 later classified as defect D6 in a different extractor
  (`formation` periods vs. `substitutes` timing) — same root cause,
  independently rediscovered.
- **Unit tests mock `sb.lineups()`/`sb.events()` with synthetic data**
  instead of hitting the network, so edge cases (empty positions, a
  goalkeeper/outfield swap, a substitute with no matching event row) can be
  constructed exactly, deterministically. The real-data confirmation of
  the same logic lives in `tests/integration/` instead. This unit/
  integration split is still the convention for every extractor's tests.

## Outcome

Shipped and merged (PRs #1–#3). Two small trailing commits on the
`player-match-analysis` branch after PR #3 (hardcoded light-theme color
fixes, dated 2026-08-15 and 2026-08-18) were never merged anywhere —
worth checking whether they're still wanted before that branch is deleted.

## Where to look for more

- `docs/testing.md` — the gate this task established, with the exact
  regression-test list and why each exists.
- `tests/unit/test_extract_substitutes.py`,
  `tests/integration/test_roster_matches_known_match.py` — the roster bug's
  tests specifically.
- `git log --oneline 51f8e54..a537f25` — the exact commit range (PRs #1–#3).
