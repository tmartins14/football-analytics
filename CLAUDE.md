# Football Analytics

@docs/ARCHITECTURE.md

This repo has several distinct work areas. Full detail on how they connect
lives in `docs/ARCHITECTURE.md` — this table is just for finding the
right folder.

| Task type | Where |
|---|---|
| StatsBomb Python extraction (`extract_*` functions) | `libs/statsbomb/` |
| D3/JS visualization components | `libs/footballd3/` |
| AI-engineering features | `ai/` |
| New deployable apps (non-AI) | `apps/` (empty scaffold) |
| Legacy match-analysis dashboard | `pages/match-analysis/` |
| Sequenced practice questions / mini-project notebooks | `analyses/practice_questions/`, `analyses/corners_euro_2024/`, `analyses/world_cup_2026/` |
| Exploratory StatsBomb notebooks (not the library) | `analyses/statsbomb/` |
| Ad hoc / throwaway notebook work | `analyses/sandbox/` |
| Committed Euro 2024 extractor output | `data/euro-2024/` |
| Data extraction scripts, docs/test gate scripts | `scripts/` |
| Written research, literature notes, match writeups | `research/`, `literature_notes/`, `match_reactions/` |
| Set-piece analytics scaffold (not built out) | `set_piece_analytics/` |
| Superseded precursor notebooks | `scratch/` |
| pytest suite (`libs/statsbomb` only) | `tests/` |
| Docs/testing gate rationale | `docs/tooling.md`, `docs/testing.md` |
| A written spec, before execution (not every task gets one) | `docs/specs/` |
| Record of what was done, after the fact (every task gets one) | `docs/task-history/` |
| Obsidian vault / personal notes | `football-analytics-notes/` |

Not sure which folder owns something? Check `docs/ARCHITECTURE.md` first —
it covers naming collisions (e.g. two things named `statsbomb`) and known
gaps between folders.

## Task documentation

Every task done in this repo gets a task doc in `docs/task-history/`,
following `docs/task-history/TEMPLATE.md` — written as part of finishing
the task, not as an afterthought. If Tyler provides a written spec for the
task, it goes in `docs/specs/` first; not every task starts with one, but
every task ends with a `docs/task-history/` entry regardless. See
`docs/README.md` for the full split.
