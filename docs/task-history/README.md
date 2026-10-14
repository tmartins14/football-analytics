# Task index

One row per task doc in this folder, oldest first. Every doc follows
`TEMPLATE.md`'s format — frontmatter (`status`, `started`/`completed`,
`area`, `related_prs`, `related_docs`, `tags`) then the same section order.
Reading just this table and picking the right row should usually be enough
to find what you need without opening every doc.

| Task | Status | Dates | Area | Doc |
|---|---|---|---|---|
| Curriculum bootstrap and early analyses | superseded | 2026-04 → 2026-05 | `literature_notes/`, `analyses/` | [2026-04-curriculum-and-early-analyses.md](2026-04-curriculum-and-early-analyses.md) |
| Build the footballd3 and statsbomb libraries | done | 2026-06 → 2026-07 | `libs/` | [2026-06-footballd3-statsbomb-libraries.md](2026-06-footballd3-statsbomb-libraries.md) |
| Player Match Analysis extractors, components, and the test gate | done | 2026-08-05 → 2026-08-10 | `libs/statsbomb`, `libs/footballd3` | [2026-08-player-match-analysis.md](2026-08-player-match-analysis.md) |
| Restructure into libs/ + apps/, then consolidate ai/match_summary | done | 2026-08-23 → 2026-09-14 | `libs/`, `ai/` | [2026-08-libs-apps-and-ai-directory-restructure.md](2026-08-libs-apps-and-ai-directory-restructure.md) |
| Module 1: auto-written match summary, first vertical slice | done | 2026-08-25 → 2026-08-31 | `ai/match_summary` | [2026-08-match-summary-module1.md](2026-08-match-summary-module1.md) |
| matchSummary footballd3 component, added then reverted | superseded | 2026-08-31 | `libs/footballd3` | [2026-08-dashboard-component-reverted.md](2026-08-dashboard-component-reverted.md) |
| Spec Kit scaffolding, SPEC_TEMPLATE.md, and docs/ARCHITECTURE.md's move | done | 2026-09-12 | `docs/`, `.specify/` | [2026-09-spec-kit-scaffolding.md](2026-09-spec-kit-scaffolding.md) |
| Module 2: sampling decision and the model/effort comparison harness | done | 2026-09-15 → 2026-09-22 | `ai/match_summary` | [2026-09-module2-sampling-and-comparison.md](2026-09-module2-sampling-and-comparison.md) |
| DATA-SPEC-v2: the tactical findings layer | in-progress | 2026-10-12 → ongoing | `libs/statsbomb`, `ai/match_summary` | [2026-10-data-spec-v2-tactical-findings.md](2026-10-data-spec-v2-tactical-findings.md) |

## For an agent landing here cold

1. Scan the table above for the row closest to your question.
2. Read that doc's **Summary** and **Outcome** first — most questions stop
   there.
3. Follow **Where to look for more** only if you need the authoritative
   source (the actual spec, code, or PR) rather than a summary of it.
4. The sibling repo (`tylermartins.com`) has its own `docs/task-history/`
   with the same template — some tasks here are cross-referenced from
   there and back (e.g. this repo's DATA-SPEC-v2 doc and that repo's
   AI-section doc describe two sides of the same feature).

See `../README.md` for how this folder relates to `docs/ARCHITECTURE.md`,
`tooling.md`, and `testing.md`.
