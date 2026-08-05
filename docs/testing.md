# Testing — the test gate

This document explains the test suite in this repo: what it covers, why it's
structured the way it is, and how to maintain it. Companion to `docs/tooling.md`
(the documentation gate) — read that first if you haven't; this one assumes the
same "request vs. gate" framing and doesn't re-explain it.

## Why this exists

The player-analysis extractors (`extract_substitutes.py`, `extract_player_events.py`)
and the footballd3 components they feed were built through a session of manual,
ad-hoc verification — run the extractor, eyeball the JSON, count a roster by hand.
That caught real bugs (a fabricated `"Tackle"` event type; 4 of 7 substitutions
silently missing from Tactical-Shift-based formation periods; `on_minute` floats
instead of ints; a `None` field silently becoming an invalid JSON `NaN` token) but
none of it was repeatable — the next change could reintroduce any of them without
anyone noticing. This test suite turns that one-time manual verification into a
gate: `scripts/check_tests.sh`, wired into the same Stop hook / pre-commit / future-CI
enforcement points as the docs gate.

## What's tested — and what isn't (yet)

This first pass covers the code built in the player-analysis session (both
`statsbomb` extractors touched or added, and the 5 footballd3 components
touched or added) — not the other ~9 existing extractors or ~14 existing
components. That's a deliberate scope decision, not an oversight: this
establishes the pattern and the infrastructure, and covers the highest-risk new
code now. Extending coverage to the rest of both libraries is incremental
follow-up work, not a blocker for this gate existing. `check_tests.sh` gates on
"the tests that exist pass," not on a coverage percentage — see "Extending the
gate" below for why that's deliberate too.

## Python: `tests/` — unit vs. integration

```
tests/
  conftest.py        # session-scoped match_id / raw_events / raw_lineups fixtures
  unit/               # pure functions, synthetic data, zero network calls
  integration/        # real network, live match 3943043, @pytest.mark.integration
```

**Why a mirrored `tests/` tree, not co-located `test_*.py` next to each module?**
This repo's Python package (`src/statsbomb/`) is flat — one module per extractor,
no per-module subfolders — so there's no natural "component folder" to co-locate
into the way footballd3 has. A top-level `tests/` tree is the standard pytest
convention for a flat package, and it's also excluded from `interrogate`'s
docstring gate (`PY_PKG="src"` in `check_docs.sh` doesn't walk `tests/`), which is
correct — test files document intent through their assertions and names, not
module docstrings.

**Why session-scoped fixtures.** `sb.events(match_id=3943043)` takes ~11s on a
cold call — a real network hit against StatsBomb's public open-data GitHub raw
JSON. `statsbombpy` already wraps calls in `requests_cache`
(`install_cache(mkdtemp(), backend="sqlite", expire_after=600)`, in
`statsbombpy/api_client.py`) — but the cache directory is a fresh `mkdtemp()` per
Python process, so it only speeds up repeated identical calls *within* one
`pytest` run, not across separate `uv run` invocations. `tests/conftest.py`'s
`raw_events`/`raw_lineups` fixtures are `scope="session"` so the one-time network
cost is paid once per test run, shared by every test that needs match data,
rather than once per test.

**Why unit tests mock `sb.lineups()`/`sb.events()` instead of using the session
fixtures.** The tricky logic worth testing thoroughly (`get_eligible_players`'s
goalkeeper-exclusion and starter/substitute detection; `_pressure_regain`'s
half-time-boundary handling) needs to exercise specific edge cases — an empty
`positions` list, a player with both a Center Back and a Goalkeeper position
entry, a substitute with no matching `Substitution` event row — that may or may
not exist in the one real match this repo's sample data targets. Synthetic data
via `monkeypatch` lets each test construct exactly the case it needs, deterministically,
with no network call at all. The **real**-data version of this coverage (confirming
the function's actual output against the actual Euro 2024 Final roster) lives in
`tests/integration/`.

**Why some private (`_`-prefixed) helpers are imported directly into tests.**
Python doesn't enforce privacy, and the extractors themselves already import
across modules this way (`extract_player_events.py` imports `_map_to_zone` from
`extract_xt.py`, `_is_progressive`/`_dist_to_goal` from `extract_progressive_map.py`).
Tests follow the same established pattern rather than only testing through public
entry points.

## JS: co-located `*.test.js` under `src/footballd3/components/`

```
src/footballd3/components/formation/
  formation.js
  formation.d.ts
  formation.test.js   <- new
  README.md
```

**Why co-located, the opposite choice from Python.** `src/footballd3/components/`
is already organized one-folder-per-component (the same folder `check_docs.sh`'s
README-presence check walks). A test file is one more file in that same folder,
matching the existing convention, rather than a parallel mirror tree the way
Python's flat package needed.

**Tooling: vitest + jsdom.** `vitest.config.js` (repo root, alongside
`eslint.config.js`) points at `src/footballd3/components/**/*.test.js` with
`environment: "jsdom"`. `vitest`/`jsdom` are devDependencies of the **root**
`package.json` (not `src/footballd3/package.json`) — matching where
`eslint`/`eslint-plugin-jsdoc` already live, deliberately keeping the *published*
npm package's own `package.json` free of dev-only tooling.

**jsdom limitation, verified empirically (not assumed) while writing these
tests:** jsdom implements no real layout — every element's
`getBoundingClientRect()` returns all zeros, and there's no real SVG coordinate
transform (`getScreenCTM`) to invert. `d3.pointer(event, node)` does **not**
throw in jsdom (confirmed by direct probe) — it just returns `[event.clientX,
event.clientY]` more or less verbatim, ignoring any `transform="translate(...)"`
a parent `<g>` applies. That means a simulated click's *exact resulting pixel
position* can't be predicted the way it could in a real browser. Tests for
pointer-position-dependent behavior (`scrubber.js`'s click-to-seek) assert *that*
the callback fires, not an exact resulting minute. Tests that don't depend on
real layout — attribute values, element counts, filter correctness,
programmatic `seek()`/keyboard-driven interaction — are unaffected and get
precise assertions (confirmed: `scrubber.test.js`'s `ArrowRight`/`ArrowLeft`
keyboard tests assert exact resulting minutes, since keyboard nudges don't
depend on pointer coordinates at all).

## Regression tests tied to specific bugs found while building this

Worth knowing *why* these exist, not just that they do — a future reader
shouldn't have to reconstruct the reasoning:

- **`tests/integration/test_roster_matches_known_match.py`** — asserts the
  exact substitute roster (3 England, 4 Spain, named). Direct regression test
  for the bug that motivated `extract_substitutes.py` to exist at all: 4 of the
  match's 7 substitutions never triggered a `Tactical Shift` event, so a roster
  sourced from `extract_formation.py`'s formation periods would silently drop
  them.
- **`tests/unit/test_extract_substitutes.py::test_substitute_without_a_tactical_shift_is_still_included`**
  — the synthetic version of the same case: a substitute with **no** Tactical
  Shift event anywhere in the synthetic table must still be found, proving
  `get_eligible_players` never depends on one existing.
- **`tests/unit/test_extract_substitutes.py::TestMainWritesCleanJson`** — a bug
  this test suite *found*, not one carried over from manual testing: pandas
  silently converts a per-row `None` to a float `NaN` even in an **object/string**
  column (`replaced_player`), not just numeric ones (`on_minute`/`on_second`,
  the case already known about). `extract_substitutes.py`'s `main()` originally
  only cleaned the two numeric fields; a substitute with no matching
  `Substitution` event would have produced a literal invalid `NaN` token for
  `replaced_player` in the JSON output. Fixed by moving the NaN-cleaning helper
  to `statsbomb.utils.clean_nan()` (shared with `extract_player_events.py`,
  which had its own equivalent, now deduplicated) and applying it to every
  field, not just the two known-risky ones.
- **`tests/integration/test_player_events_contract.py::test_palmer_file_is_strict_json_with_no_nan_tokens`**
  — re-verifies the NaN-token issue against real data using a **strict** JSON
  parse (`parse_constant` raises on `NaN`/`Infinity`/`-Infinity`). Python's own
  `json.loads` accepts those as a non-standard extension by default and would
  **not** catch this bug on its own — the strict parse simulates what
  `JSON.parse` in the eventual tylermartins.com consumer actually does.
- **`tests/integration/test_player_events_contract.py::test_no_fabricated_tackle_type`**
  — regression test for an earlier draft that included `"Tackle"` as a
  top-level event `type`. It isn't one — `Tackle` is a `duel_type` qualifier on
  `Duel` events.
- **`tests/unit/test_extract_player_events.py::TestPressureRegain::test_half_time_boundary_regression`**
  — StatsBomb's per-period clock restarts near 45' for the second half rather
  than continuing from where the first half ended, so a period-1 event and a
  period-2 event can have near-identical `minute*60+second` values despite the
  halftime break between them in real time. `_pressure_regain`'s window is
  bounded to `row["period"]` specifically to prevent this pair from being
  compared as if temporally adjacent.

## Running it and reading the output

```bash
# Python — fast, no network:
uv run pytest tests/unit -v

# Python — full suite including live-network integration tests:
uv run pytest -v

# JS:
npx vitest run

# The combined gate, exactly as the Stop hook / pre-commit runs it:
bash scripts/check_tests.sh; echo "exit: $?"
```

- Exit 0 → everything passes.
- Exit 2 → something failed; reasons are printed above the summary line.

## Extending the gate

- **Not built now:** a required test-coverage percentage. `check_tests.sh` gates
  on "the existing tests pass," matching `docs/tooling.md`'s own explicit
  "defer until there's real signal" stance on gate scope-creep — a coverage
  threshold frozen now, before most of the codebase has any tests at all, would
  either be trivially low (meaningless) or force a large test-writing push
  disconnected from any actual change.
- **Not built now:** CI. Same reason `check_docs.sh` hasn't wired one up yet —
  "add when the repo actually has merges to gate."
- **Reasonable to add, once real signal exists:** unit tests for the remaining
  extractors/components, following the exact pattern established here
  (synthetic data + `monkeypatch` for Python, co-located `*.test.js` + jsdom for
  JS) rather than inventing a new one.
