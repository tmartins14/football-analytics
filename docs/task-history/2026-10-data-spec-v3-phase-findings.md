---
title: "DATA-SPEC-v3: phase findings and player contribution"
status: in-progress
started: 2026-10-16
completed: ongoing
repo: football-analytics
area: ai/match_summary
related_prs: [22, 23, 24, 25, 26]
related_docs: [ai/match_summary/DATA-SPEC-v3.md, ai/match_summary/DATA-SPEC-v2.md, ai/match_summary/FAILURE-TAXONOMY.md, ai/match_summary/AUDIT-v3.md]
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

### 2026-10-16 — Part 0 (data audit)

`AUDIT-v3.md` added, answering all eight of v3's Part 0 questions read-only
against this repo's code and committed match data (no raw-events network
call made). Confirmed: `obv_*` fields are categorically absent from open
data (paid-tier only); `progressive_map` already exists in
`extract_progressive_map.py` with a definition that conflicts with v3's own
drafted fallback; only 44 of 51 Euro 2024 matches are extracted locally (one
empty) and nothing is cached raw, so reference-data building depends on live
network fetches; `socceraction` isn't installed or declared anywhere in this
project; successful-Tackle/Interception outcome values are two
non-overlapping strings each, not one clean value, and Ball Recovery has no
outcome field at all; minutes-played is computable from existing
`substitutes.json` plus `extract_formation.py`'s match-end minute but isn't
stored anywhere yet. Four items flagged to Tyler as open questions rather
than resolved in the audit doc itself (see `AUDIT-v3.md`'s closing summary).

### 2026-10-16 — Tyler's audit decisions, and the socceraction dependency

Tyler resolved all four open questions from `AUDIT-v3.md`: use
`extract_progressive_map.py`'s existing definition for Q3 (drop v3's drafted
fallback); backfill the missing Euro 2024 matches before Part 2 rather than
relying on live fetches alone; add `socceraction` now rather than deferring
to Part 3; both `"Won"` and `"Success In Play"` count as a successful
Tackle/Interception for Q5.

Added `socceraction` as a dependency. Installing it surfaced a real,
unrelated-to-this-repo version conflict: `pandera` 0.17.2 (socceraction's
own transitive dependency, via its Opta loader) declares no upper bound on
`multimethod`, and `multimethod>=2.0` removed the `overload` API pandera
needs — so `uv`'s resolver silently picked an incompatible combination that
fails at import time, not at resolve time. Fixed by pinning
`multimethod<2.0` directly in `pyproject.toml`. Confirmed
`socceraction.data.statsbomb.StatsBombLoader(getter="local", root=...)`
exists for loading a local StatsBomb JSON tree without the network-backed
`statsbombpy` API path (settling audit item 8's open half). Full test suite
(223 tests, unit + integration) still passes after the dependency bump and
the `numpy`/`pandas`/`scipy` downgrades socceraction's own constraints
pulled in.

### 2026-10-16 — Part 1 (tier 1 extractors)

Four new `libs/statsbomb/` modules, one per Q1-Q6 group, each emitting raw
values only (no suppression thresholds, no modal-share/tercile labeling, no
claim rendering — that split stays `derive_tactical_findings.py`'s job in
Part 4, same as the existing v2 extractors): `extract_chance_creation.py`
(Q1 shot zone/source mix, Q2 per-player xA/key-pass creators),
`extract_progression.py` (Q3 side bias, pass/carry mode mix, per-player
volume — reusing `extract_progressive_map`'s existing 25%-closer-to-goal
rule outright, per Tyler's audit decision, not the spec's originally-drafted
fallback), `extract_pressing.py` (Q4 PPDA/high-pressure counts, Q6 per-player
pressure received — one combined file, since both need cross-team
bookkeeping), and `extract_defending.py` (Q5 defensive action height, high
turnovers, ball-winning zone by band; `block_height` itself needed no new
work — it's already v2's `team_shape` centroid, only the tercile label is
new and that's Part 4's). Added a small `side_group()` coordinate helper to
`utils.py` (v3's left/centre/right team-level grouping, built on the
existing `lane_for_y`).

Every non-trivial value was independently hand-recomputed against raw
`sb.events()` with ad hoc pandas filters written separately from the
extractor code (the bar DATA-SPEC.md sets) — PPDA for both teams, Spain's
win-zone and defensive-action-height totals, both teams' shot/npxG counts —
and Spain's and England's progressive-action totals were additionally
cross-checked against the pre-existing `extract_progressive_map` extractor's
own count, a second independent source agreeing exactly. Wired into
`libs/statsbomb/__init__.py` and `scripts/extract_euro2024.py`'s batch
pipeline (ran end-to-end for match 3943043, output committed).

### 2026-10-17 — backfill the 7 missing Euro 2024 matches

Ran the batch pipeline (now including the four Part 1 extractors) for the
7 Euro 2024 matches that had never been extracted
(3930158, 3930161, 3930164, 3930165, 3930168, 3930175, 3930183) and for
3930167, whose directory existed but was empty (a previously-failed/aborted
run). `data/euro-2024/` now has all 51 matches complete.

Backfilling 3930167 surfaced a real pre-existing bug, unrelated to v3:
`extract_pass_network.py`'s window-building loop skips a substitution
window when it's zero-length (two subs land on the same minute), but kept
using the raw loop position as that window's `index` rather than its
position among *emitted* windows — so `index` could skip a value. 3930167 has
exactly this (two Albania subs both at 84'), which made
`derive_tactical_findings.py`'s `is_last = index == len(windows) - 1` check
false for the actual last window, and it then crashed calling
`display_minute` on a `None` period instead of rendering "full time". Fixed
by renumbering `index` to the emitted-window position; added a regression
unit test (`tests/unit/test_extract_pass_network.py`) reproducing the
same-minute double-substitution case. This bug likely affects other
already-extracted matches with simultaneous substitutions too (not
re-audited here — flagged, not fixed, since it's out of this task's scope
and didn't crash for any of the 43 already-committed matches).

A second, separate issue surfaced for match 3930158 (Germany 5-0 Scotland):
`extract_team_shape.py`'s own sanity check, `_assert_attacks_right`, raised
for Scotland — "`_attack_direction_by_period` returned non-'right' for
period(s) {1: 'left'}". Investigated rather than silenced: Scotland took
**zero shots** in period 1 (unsurprising in a 5-0 game), which forces the
function's documented fallback — mean x of all in-possession located events
— and that fallback came out to 45.78 (of 120), under the same x>60
threshold the primary shot-based check uses. That threshold is calibrated
for shot locations, which genuinely cluster near goal; general in-possession
build-up play does not, so the fallback looks structurally prone to a false
"left" reading for any team with zero shots in a period, independent of
their real attack direction — this reads as a weak fallback heuristic, not
evidence of an actual StatsBomb coordinate-frame flip for this match.
Checked all 51 matches for the same symptom (missing one team's
`team_shape_*.json` file): 3930158 is the only one affected. Left
`extract_team_shape.py` untouched and did not relax or bypass its own
assertion — that's exactly the kind of check this repo's conventions say an
agent shouldn't quietly work around, and the fallback's calibration is
Tyler's call, not mine. 3930158 is committed with everything else that
succeeded for it (shots, momentum, formation, chance_creation, progression,
pressing, defending, etc.) but **without** `team_shape_scotland.json` or
`tactical_findings.json` (which needs both teams' team_shape) — flagged
for Tyler, not silently patched over.

Full test suite (297 tests) and the docs gate both pass after the backfill.

## Outcome

Parts 0 and 1 complete, all four audit questions resolved, `socceraction`
added, and all 51 Euro 2024 matches now extracted locally. Part 2 (reference
data: `reference_distributions.json`, `xt_grid_v1.json`, built from the four
Part 1 extractors run across all 51 matches) is next.

## Where to look for more

- `ai/match_summary/DATA-SPEC-v3.md` — the authoritative spec (do not edit
  this as an agent — see this repo's `CLAUDE.md`).
- `ai/match_summary/AUDIT-v3.md` — the Part 0 audit and its open questions.
- `ai/match_summary/DATA-SPEC-v2.md` — the superseded Part 6 and everything
  v3 still inherits (seam rules, finding schema, `check_grounding`, etc).
- `ai/match_summary/FAILURE-TAXONOMY.md` — D10/D11, the failures this spec
  closes.
