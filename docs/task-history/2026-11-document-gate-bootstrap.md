---
title: Document CHECK_TESTS_UNIT_ONLY and the gate bootstrap
status: done
started: 2026-11-06
completed: 2026-11-06
repo: football-analytics
area: docs/testing.md
related_prs: []
related_docs: [docs/testing.md, scripts/check_tests.sh, scripts/check_docs.sh]
tags: [docs, gates, testing]
---

# Document CHECK_TESTS_UNIT_ONLY and the gate bootstrap

## Summary

Added a "Running the gates" section to `docs/testing.md` covering the
`CHECK_TESTS_UNIT_ONLY=1` switch and the `npm ci` / `npx --no-install`
bootstrap in both gate scripts. Docs only; no script, settings or workflow was
touched. Requested in issue #33.

## Context

`scripts/check_tests.sh` gained `CHECK_TESTS_UNIT_ONLY` and both gate scripts
gained an `npm ci` bootstrap, but `docs/testing.md` did not mention either.

## What was done

- New "Running the gates" section in `docs/testing.md`, before "Extending the gate":
  - `CHECK_TESTS_UNIT_ONLY=1` skips `integration`-marked tests (live StatsBomb
    API); set by the Stop hook; CI runs the full suite.
  - `npm ci` when `node_modules` is missing, and `npx --no-install` so nothing
    unpinned is downloaded.

## Outcome

Done. Section matches the current behavior of the scripts as read.

## Where to look for more

- `docs/testing.md`
- `scripts/check_tests.sh`, `scripts/check_docs.sh`
- Issue #33
