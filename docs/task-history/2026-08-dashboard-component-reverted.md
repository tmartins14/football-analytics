---
title: matchSummary footballd3 component, added then reverted
status: superseded
started: 2026-08-31
completed: 2026-08-31
repo: football-analytics
area: libs/footballd3
related_prs: [6, 7]
related_docs: []
tags: [footballd3, revert]
---

# matchSummary footballd3 component, added then reverted

## Summary

A `matchSummary` footballd3 component was added on top of
Module 1's `generate_match_summary.py` output (PR #6), then reverted the
same day (PR #7). Both merged to `main`; net effect is no change to the
component library.

## Context

Module 1's match summary existed only as generated JSON/Markdown at this
point (see `2026-08-match-summary-module1.md`) — this was an attempt to
surface it as a visual component like the rest of the gallery.

## What was done

PR #6 (`7486f8a`, branch `feature/match-summary-dashboard-doc`) added the
component. PR #7 (`c97d49d`, `revert/matchsummary-footballd3-component`)
reverted PR #6's merge commit directly, same day. The commit messages
don't record *why* it was reverted.

## Outcome

Superseded — `tylermartins.com` later rebuilt the equivalent as native
React instead of a footballd3 component (see that repo's
`docs/task-history/2026-09-ai-section.md`), which is the version actually in use
today.

## Where to look for more

- `git show 7486f8a`, `git show c97d49d` — the add and the revert.
