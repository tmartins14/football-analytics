#!/usr/bin/env bash
# check_docs.sh — documentation gate for football-analytics.
#
# Fails (exit 2, with reasons on stderr) if anything is undocumented; passes
# (exit 0) when clean. One script, three callers:
#   - Claude Code Stop hook  (blocks the turn from finishing on missing docs)
#   - git pre-commit         (blocks the commit)
#   - CI                     (blocks the merge)
#
# Install the tools once:
#   Python:  uv add --dev interrogate
#   JS:      npm i -D eslint eslint-plugin-jsdoc
#            (and require jsdoc on exported functions in your eslint config)

set -uo pipefail
shopt -s nullglob

# --- set these to your ACTUAL layout ----------------------------------------
PY_PKG="src"                         # Python package to check docstring coverage on
JS_DIR="src/footballd3"                  # <-- set to your real D3 components directory
PY_RUNNER="uv run"                   # how to invoke Python tools (uv, per stack)
# Directories that must each contain a README.md. Point these at real component
# directories — not every subpackage. Adjust the globs to your structure:
COMPONENT_DIRS=( "src/footballd3/components/"* )
# ----------------------------------------------------------------------------

fail=0
err() { printf '%s\n' "$*" >&2; }

# 1. Python docstrings — modules + public functions/classes, required at 100%.
if command -v "${PY_RUNNER%% *}" >/dev/null 2>&1; then
  if ! $PY_RUNNER interrogate -q \
        --fail-under 100 \
        --ignore-private --ignore-magic \
        --ignore-nested-functions --ignore-init-method --ignore-init-module \
        "$PY_PKG"; then
    err "✗ Python docstrings below 100% in ${PY_PKG}/  (detail: ${PY_RUNNER} interrogate -v ${PY_PKG})"
    fail=1
  fi
else
  err "✗ '${PY_RUNNER%% *}' not found — cannot run interrogate"
  fail=1
fi

# 2. JS/D3 JSDoc — enforced by your eslint config + eslint-plugin-jsdoc.
if [ -d "$JS_DIR" ]; then
  if command -v npx >/dev/null 2>&1; then
    if ! npx eslint "$JS_DIR" 1>&2; then
      err "✗ JSDoc/ESLint failed in ${JS_DIR}/  (require jsdoc on exported functions)"
      fail=1
    fi
  else
    err "✗ 'npx' not found — cannot run eslint"
    fail=1
  fi
fi

# 3. Every component directory carries a README.md.
for d in "${COMPONENT_DIRS[@]}"; do
  [ -d "$d" ] || continue
  if [ ! -f "${d}/README.md" ]; then
    err "✗ Missing README.md in ${d}/"
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  err ""
  err "Documentation gate failed — add the missing docs above before finishing."
  exit 2
fi

echo "✓ Documentation gate passed."
exit 0