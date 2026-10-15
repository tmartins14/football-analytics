# Failure Taxonomy — Match Summary (tactics section)

Intended path: `ai/match_summary/FAILURE-TAXONOMY.md`
Source: real output only. Seeded from `VERIFICATION-3943043.md` (Module 1 run) and the 2026-10-07 read of the committed `match_summary.md`.
Related: [DATA-SPEC-v2.md](./DATA-SPEC-v2.md)

The taxonomy decides what the eval measures. Each failure class is mapped to the
cheapest gate that catches it: Part 0 extractor fix → findings code →
`check_grounding` → Module 3 judge. A class with no gate yet is listed as
"none yet".

## Classes

| Class | Definition | Gate that catches it |
|---|---|---|
| Misread field | Model uses a field for something it isn't | Findings code: the model never sees raw fields |
| Bad source data | The extractor publishes a wrong value | Part 0 + unit tests |
| Direction flip | Right entities and numbers, wrong direction or roles | Claim templates + `check_grounding` (claim word for word, leftover check) |
| Model arithmetic | Model sums, compares or computes | Findings code |
| Unsupported label | A label with no threshold or no source behind it | Findings code (labels only from constants) + leftover check |
| Wrong timing | Minutes or sequence wrong | `substitution` from `substitutes.json`, `display_minute`, sequence-word rule |
| Too little data | Claims drawn from a window too small to support them | Suppression rules |
| Poor selection | True findings, but the wrong ones or in a bad order | none yet: Module 3 judge |
| Poor readability | True and well chosen, but reads badly | none yet: Module 3 judge |

## Observed failures

| # | Defect | Run | Class | Gate now |
|---|---|---|---|---|
| D1 | Off-ball centroid labelled "on-ball" | Both | Misread field + bad source data (frames pooled; see DATA-SPEC-v2 §A) | Part 0, findings code |
| D2 | "England more central than Spain", backwards | Module 1 | Direction flip | Claim templates, `check_grounding` |
| D3 | Stones named as a hull vertex | Module 1 | Misread field | Findings code (hull is not a finding) |
| D4 | Walker "high and central" at y=69 | Module 1 | Unsupported label | Findings code (`player_zone` thresholds) |
| D5 | Edge counts summed for Spain, single-direction for England | Module 1 | Model arithmetic | Findings code (`top_pair` bidirectional) |
| D6 | Subs placed at 89' (actually 82', 88', 67') | Committed | Wrong timing | `substitution` finding |
| D7 | Spain's "back three" in a 4-2-3-1 | Committed | Unsupported label | Formation strings literal in claims; leftover check |
| D8 | Claims about the 88'–FT window (1 pass) | Module 1 | Too little data | `MIN_WINDOW_PASSES` suppression |

## Known risks (not yet observed)

Listed so they are watched for, not counted as failures until a real trace shows one.

- **Swapped numbers across cited findings:** two findings in one sentence with their values exchanged (e.g. two hubs in one window). Covered by the leftover check and the `check_grounding` test suite.

## Part 5 update (2026-10-14)

Three live-API runs on the tactical-findings-layer tactics section (Parts
0-4), plus a full manual read of all three (not just one), found none of
D1-D8 and no new failure class. See `VERIFICATION-3943043-v2.md` for the
per-defect before/after table and the per-run `check_grounding` results
(0 failed sentences, `publishable: true` on all three). No new rows added
below — this is the "ran it and nothing new showed up" outcome the update
rule also expects to be recorded, not just new failures.

## Update rule

After every Part 5 run and every Part 6 category, add new failures as rows with
the run they came from. A failure that passes `check_grounding` is the most
important kind to log, because it marks the gap the Module 3 judge has to cover.
