# SPEC — Auto-Written Match Summary

Status: living — Module 1 shipped (PR #5); Module 2 (Foundation Models) in progress
Owner: Tyler (Plan) / Claude (Execute, Verify)

## Goal

Generate a two-part auto-written summary of a completed match from its StatsBomb
data — a structured outcome section (headline, key stats, standout performers)
and a free-prose section explaining how the outcome happened (tactics,
formations, shape).

## Scope

- New module under `ai/match_summary/` (name TBD, e.g. `generate_match_summary.py`)
  that calls a model to produce both sections for a given `match_id`.
- Exact StatsBomb data feeding each section (team-level stats, player-level
  events, formation, shape, etc.) is **out of scope for this SPEC**. It gets
  its own data-scope spec, starting from the full StatsBomb schema and
  building down to what this feature actually needs.
- Thin vertical slice for Module 1: one match, generation only — no
  dashboard rendering yet. (Module 2 adds static rendering to the site — see below.)

## Out of scope

- Live / on-request inference on the site — Module 10. (Static rendering of a
  committed summary JSON is brought into scope by Module 2 — see the Module 2
  section and the 2026-09-21 decision.)
- The exact data-scope decision — separate spec (see Scope above).
- Automated eval — Module 3.
- RAG / agent / cross-match Q&A — Module 6.

## What "correct" means

Three separate dimensions, because the two sections fail in different ways —
a single pass/fail check can't cover all three.

1. **Structured outcome section — factual grounding.** Every stat, performer,
   and number cited must trace exactly to source data. No invented values, no
   misattributed stat lines. This is `assert`-able now.
2. **Structured outcome section — selection judgment.** Which stats count as
   "key" and who counts as a "performer" is an editorial call, not a fact.
   Correct means the selection is defensible against some rule (top scorer,
   highest xG chance, most saves — not arbitrary), not that it matches one
   right answer. This needs real eval design — deferred to Module 3, not
   solved here.
3. **Free-prose tactics section — grounding, not exactness.** Every tactical
   claim (formation, shape, role) must be traceable to the underlying data,
   once the data spec picks a source. Wrong looks like a hallucinated
   formation or shift, not "the tone was off." Writing quality itself (both
   sections) is subjective and also deferred to Module 3.

## Pass/fail signal for this module

Manual read-through: read the generated summary next to the source JSON and
check nothing is invented. No automated eval yet — that's explicitly Module
3's job, not this one.

## Ships (Module 1)

This SPEC, plus a thin vertical slice (even a stubbed generation call) for
one match, merged.

---

## Module 2 — Model & Effort Selection & Site Hookup

Status: draft, pending review
Depends on: Task 1 (see the 2026-09-15 decision — sampling removed, `effort` wired
per section, reproducibility metadata). This task cannot run until Task 1 is merged.

### Goal

Decide, from measured evidence rather than guesses, which model and effort level
generate each section — balancing cost, latency, and quality — then ship the chosen
configuration wired to the tylermartins.com match-summary page.

### Scope — 5 runs on match 3943043 (Spain vs England)

Two sweeps, deduplicated. Each run = one outcome call + one tactics call.

| # | Model      | Effort | Sweep          |
|---|------------|--------|----------------|
| 1 | Haiku 4.5  | none¹  | model          |
| 2 | Sonnet 5   | medium | model + effort |
| 3 | Opus 5     | medium | model          |
| 4 | Sonnet 5   | low    | effort         |
| 5 | Sonnet 5   | high   | effort         |

¹ Haiku 4.5 predates the 5-family `effort` control. Confirm in CC whether it accepts
`effort`; if not, run with none and note the asymmetry. Model sweep is held at
effort=medium so it isn't confounded; run 2 is shared across both sweeps — hence 5, not 6.

### What "correct" means for this task

Two notions, kept distinct:

1. **Experiment correctness (measurement integrity).** Cost and token figures come
   from the API `usage` field on each response — never estimated after the fact. Every
   cell recorded; rate table applied uniformly; the config that produced each output
   captured. A cell whose `usage` wasn't logged is a failed cell, not a data point.
2. **Output correctness.** The manual read from the "What correct means" section above:
   outcome factual-grounding (pass/fail), MOTM present in `standout_performers`
   (hit/miss), tactics grounding (pass/fail). Automated scoring is Module 3, not here.

### Measured per run

`input_tokens`, `output_tokens` (incl. thinking), `total_tokens`; USD input/output/total
cost via the rate table; wall-clock latency (informs routing; latency optimization is
Module 9); the three output-correctness reads above.

### Rate table (standard, first-party, global — as of 2026-09-21; re-check before trusting)

| Model     | Input $/MTok | Output $/MTok |
|-----------|--------------|---------------|
| Haiku 4.5 | 1            | 5             |
| Sonnet 5  | 2            | 10            |
| Opus 5    | 5            | 25            |

### Steps

1. **Pre-estimate (in `/plan`, before any spend).** From the measured payload
   (~164k input tok on 5-family, ~124k on Haiku 4.5) × the rate table, estimate each
   run and the experiment total as a spend gate. Effort-high output/thinking tokens are
   unknown until run — give a range. Do not make live calls until the estimate is reviewed.
2. **Run the 5 cells.** Read the existing extractor JSON for 3943043; per cell, generate
   both sections, capture full `usage` + latency + raw outputs.
3. **Assemble the results table.** Compute cost from `usage` × rate table.
4. **Make the routing decision** — per-section model + effort — from the table; record
   it in the Decision log.
5. **Apply + ship.** Set the generator to the chosen per-section routing, regenerate
   3943043's `match_summary.json`, and wire it to the tylermartins.com match-summary page
   via the static-JSON pattern — the page reads the committed JSON; no live inference.

### Results table (one row per cell)

`model | effort | input_tok | output_tok | total_tok | input_$ | output_$ | total_$ | latency_s | outcome_grounding | motm | tactics_grounding`

### Acceptance criteria

- All 5 cells run; real `usage` recorded per call; per-cell and total cost from `usage` × rates.
- No non-default temperature/top_p/top_k sent (no 400 on any cell).
- `effort` sent only to models that support it; Haiku handled per its footnote.
- Results table fully populated, committed as JSON (record) and Markdown (PR).
- Chosen routing recorded in the Decision log with the numbers that justify it.
- Site: the match-summary page renders the committed `match_summary.json` (static),
  with the known Module 1 defects still visible where shown.

### Deliverables

- Comparison script under `ai/match_summary/` (reads extractor JSON, runs the 5 cells,
  writes results from `usage` — no estimated token counts in the output).
- `comparison-3943043.json` + a Markdown results table.
- Generator on the chosen per-section routing.
- tylermartins.com match-summary page rendering the committed summary JSON.

### Ships (Module 2)

Task 1 merged, then: the comparison script + committed results, the generator on its
chosen routing, and the site page rendering the committed JSON — merged. "Chose not to
build": the full model×effort grid, and pinning an older model to keep temperature (both
rejected — see the 2026-09-15 and 2026-09-21 decisions).

---

## Decision log

### 2026-09-15 — Module 2 (Task 1) — Sampling controls unavailable on Claude 5-family
Claude 5-family models (incl. claude-sonnet-5) reject non-default temperature/
top_p/top_k with a 400 (verified live + migration guide). Superseded the
2026-09-14 temperature decision.
- Send NO sampling parameters.
- Control output via prompting + structured output (grounding), not sampling.
- Tune the `effort` parameter per section instead: lower for outcome
  extraction, higher for tactics reasoning. (Confirm exact effort values in CC.)

Acceptance criteria:
- No non-default temperature/top_p/top_k sent (no 400).
- outcome parses against OutcomeSection; every key_stats[].value traces to a source_field.
- tactics section makes no claim about goals/cards/shots/events.
- Summary metadata records `model`, `effort`, and a prompt version/hash, so every
  generated output is traceable to the config that produced it (prerequisite for the
  Module 2 comparison and Module 3 eval).

### 2026-09-21 — Module 2 (Task 2) — Model & effort routing (PENDING results)
Per-section model + effort to be chosen from the comparison results table (see the
Module 2 section). Not decided in advance — it is an output of the measured runs.

### 2026-09-21 — Frontend static render brought into scope (revises Module 1 out-of-scope)
Module 1 placed "rendering to tylermartins.com / any frontend" out of scope. Module 2
reverses that for the ship: the site renders the committed `match_summary.json` via the
static-JSON pattern (no live inference). Live / on-request inference stays out of scope —
Module 10.