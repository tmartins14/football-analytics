# SPEC — Auto-Written Match Summary

Status: draft, pending review
Module: AI Engineering Learning Vault — Module 1 (Foundations / Defining Correct)
Owner: Tyler (Plan) / Claude (Execute, Verify)

## Goal

Generate a two-part auto-written summary of a completed match from its StatsBomb
data — a structured outcome section (headline, key stats, standout performers)
and a free-prose section explaining how the outcome happened (tactics,
formations, shape).

## Scope

- New module under `src/statsbomb/` (name TBD, e.g. `generate_match_summary.py`)
  that calls a model to produce both sections for a given `match_id`.
- Exact StatsBomb data feeding each section (team-level stats, player-level
  events, formation, shape, etc.) is **out of scope for this SPEC**. It gets
  its own data-scope spec, starting from the full StatsBomb schema and
  building down to what this feature actually needs.
- Thin vertical slice for this module: one match, generation only — no
  dashboard rendering yet.

## Out of scope

- Rendering to tylermartins.com or any frontend component.
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

## Ships

This SPEC, plus a thin vertical slice (even a stubbed generation call) for
one match, merged.