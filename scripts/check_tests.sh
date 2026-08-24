#!/usr/bin/env bash
# check_tests.sh — test gate for football-analytics.
#
# Fails (exit 2, with reasons on stderr) if any test fails; passes (exit 0)
# when the whole suite is green. Mirrors check_docs.sh's structure exactly —
# same variable-block-at-top layout, same exit-code convention. See
# docs/testing.md for what's tested and why (unit vs integration split,
# session-scoped fixtures, the specific regression tests tied to real bugs
# found while building this). One script, three callers:
#   - Claude Code Stop hook  (blocks the turn from finishing on failing tests)
#   - git pre-commit         (blocks the commit)
#   - CI                     (blocks the merge)
#
# Install the tools once:
#   Python:  uv add --dev pytest
#   JS:      npm i -D vitest jsdom

set -uo pipefail

PY_RUNNER="uv run"   # how to invoke Python tools (uv, per stack)

fail=0
err() { printf '%s\n' "$*" >&2; }

# 1. Python tests (pytest) — unit + integration (tests/ dir, per pyproject.toml).
if command -v "${PY_RUNNER%% *}" >/dev/null 2>&1; then
  if ! $PY_RUNNER pytest -q; then
    err "✗ Python tests failed  (detail: ${PY_RUNNER} pytest -v)"
    fail=1
  fi
else
  err "✗ '${PY_RUNNER%% *}' not found — cannot run pytest"
  fail=1
fi

# 2. JS/D3 tests (vitest) — co-located *.test.js under libs/footballd3/components/.
if command -v npx >/dev/null 2>&1; then
  if ! npx vitest run 1>&2; then
    err "✗ JS/D3 tests failed  (detail: npx vitest run --reporter=verbose)"
    fail=1
  fi
else
  err "✗ 'npx' not found — cannot run vitest"
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  err ""
  err "Test gate failed — fix the failing tests above before finishing."
  exit 2
fi

echo "✓ Test gate passed."
exit 0
