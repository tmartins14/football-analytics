---
title: Spec Kit scaffolding, SPEC_TEMPLATE.md, and docs/ARCHITECTURE.md's move
status: done
started: 2026-09-12
completed: 2026-09-12
repo: football-analytics
area: docs/, .specify/
related_prs: [8]
related_docs: [docs/ARCHITECTURE.md, SPEC_TEMPLATE.md]
tags: [spec-kit, templates, docs]
---

# Spec Kit scaffolding, SPEC_TEMPLATE.md, and docs/ARCHITECTURE.md's move

## Summary

One commit (`98e3802`, PR #8) did three things at once: added the full
GitHub Spec Kit scaffolding (`.specify/` + ten `speckit-*` skills), added a
lighter, Tyler-authored `SPEC_TEMPLATE.md` at the repo root, and moved
`docs/ARCHITECTURE.md` from `.claude/ARCHITECTURE.md` to its current
location — which is why `docs/` exists at the path this documentation
task now builds on.

## Context

By this point the repo had one fairly heavyweight spec convention already
(`ai/match_summary/SPEC.md`'s living, decision-logged style — see
`2026-08-match-summary-module1.md`) but nothing lighter for small,
single-session fixes, and the architecture doc was sitting under `.claude/`
rather than anywhere a human would think to look for it.

## What was done

Single commit, three changes:

1. **`.specify/` + Spec Kit skills.** The stock GitHub Spec Kit templates
   (`spec-template.md`, `plan-template.md`, `tasks-template.md`,
   `checklist-template.md`, `constitution-template.md`) and the ten
   `speckit-*` skills that drive them. These are generic, feature-request-
   oriented ("describe a feature in natural language, get user stories + a
   plan + tasks") — structurally unrelated to both `SPEC_TEMPLATE.md` below
   and the `ai/match_summary/` living-spec pattern. `.specify/memory/
   constitution.md` was never actually filled in (still the unedited
   placeholder template).
2. **`SPEC_TEMPLATE.md`** — a much lighter "interview pattern" template:
   paste it into a fresh chat, have the agent interview you one question
   at a time (Goal / Context / Files and interfaces / Approach / Out of
   scope / Verification), read and fix the result yourself, *then* start a
   new session and hand it the finished spec — the interview context is
   what makes the spec good and what makes execution bad, so it's
   deliberately left behind. The template's own worked example is a real
   task from the sibling repo (the `tylermartins.com` dashboard-
   responsiveness fix — see that repo's
   `docs/specs/2026-08-player-match-analysis-site.md`), left in place
   rather than blanked out.
3. **`docs/ARCHITECTURE.md`'s move.** Renamed from `.claude/ARCHITECTURE.md`
   (written during the `restructure-libs-apps` task — see
   `2026-08-libs-apps-and-ai-directory-restructure.md` — for *content*
   provenance) to `docs/ARCHITECTURE.md`. This commit is the reason the
   file lives where it does today, even though it didn't write the
   content.

## Key decisions

Three independent spec templates now coexist in this repo on purpose, each
for a different shape of task: Spec Kit (`.specify/`) for a feature
described from scratch with no context yet; `SPEC_TEMPLATE.md` for a
single scoped fix where an interview can extract the spec in one sitting;
`ai/match_summary/`'s living-spec style for an ongoing, multi-session
project that needs a running decision log. None of the three was retired
in favor of another, and this documentation task (`docs/specs/`,
`docs/specs/TEMPLATE.md`) adds a fourth, for a different job again —
recording what already happened, not planning what to build.

## Outcome

Done. All three artifacts are still in active use: Spec Kit's skills are
installed and available (constitution still unfilled), `SPEC_TEMPLATE.md`
is still the lightweight-fix template, and `docs/ARCHITECTURE.md` is still
at this path.

## Where to look for more

- `SPEC_TEMPLATE.md` — the template itself, in full, at the repo root.
- `.specify/templates/` — the Spec Kit templates.
- `docs/ARCHITECTURE.md` — the file this task relocated.
