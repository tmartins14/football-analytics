# DATA-SPEC — Match Summary "How" Data Model

Status: draft, pending push
Module: AI Engineering Learning Vault — Module 1 (Foundations / Defining Correct)
Owner: Tyler (Plan) / Claude (Execute, Verify)
Related: [SPEC.md](./SPEC.md)

## Goal

Define the complete StatsBomb data model — existing and new — that grounds the
"how" (tactics) paragraph of the match summary, for the one match this
vertical slice covers.

## Scope

Six requirement categories, each judged against a strict bar: StatsBomb data
must give 100% coverage of the requirement, not a sample or proxy of it.

| Category | Source | Status |
|---|---|---|
| Shape & structure (formation, shifts, in/out-possession shape, subs) | `extract_formation`, `extract_team_shape`, `extract_substitutes` | Exists |
| Progression style (direct vs. patient, which channels) | `extract_progressive_map`, `extract_pass_network` | Exists |
| Pressing & defensive organization (PPDA, press intensity, defensive line height) | new: pressing extractor built on `Pressure` events + defensive-action coordinates | New build |
| Chance creation pattern (buildup chain to shot, key-pass linkage, xT) | `extract_xt`, `extract_momentum` (existing) + new: full possession-chain-to-shot reconstruction | Exists + new build |
| Transition behavior (counterattack speed/directness, defensive transition) | new: turnover-to-outcome sequence extractor built on dispossession/recovery/interception events | New build |
| Set-piece attacking patterns (routines, delivery outcomes) | new: extractor built on `play_pattern` origin tagging | New build |

Four new extraction modules required — this is real new-build scope, not a
data-availability question.

## Out of scope

Zero StatsBomb coverage, excluded per the 100%-coverage rule:

- Physical/tracking metrics (distance, sprints) — no tracking data in
  StatsBomb events.
- Defensive set-piece marking scheme (man vs. zonal) — not a labeled field
  anywhere in the schema.
- Explicit tactical role labels ("false 9," "inverted fullback") — not a
  StatsBomb tag; stays an LLM inference on top of complete positional data,
  not a data requirement.

## What "correct" means

A different problem than SPEC.md's. This is data-pipeline correctness, not
subjective judgment. Each new extractor's output must be exactly verifiable
against the raw event log:

- PPDA matches an independent manual recount over a sample window.
- Buildup chains terminate at the correct shot every time.
- Transition windows are bounded by the correct turnover event.
- Set-piece tagging matches `play_pattern` exactly.

This is `assert`-able and unit-testable — genuinely easier to verify than the
generation layer in SPEC.md.

## Pass/fail signal

Unit tests per new extractor against a hand-checked sample from one match,
before anything feeds the summary generator.

## Ships

This DATA-SPEC, plus three new extractor modules (pressing, transitions,
set-pieces) and the buildup-chain extension to the existing shot/xT pipeline,
each with passing unit tests.
