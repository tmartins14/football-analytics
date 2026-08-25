# Architecture

How this repo is organized and how the pieces connect. Read this before
navigating by grep alone — several directories share vocabulary
(`statsbomb` the library vs. `analyses/statsbomb/` the notebooks;
`data/` vs. `libs/footballd3/sample_data/`) and picking the wrong one
silently works, it just edits the wrong copy.

## Mental model

Three kinds of thing, one repo:

1. **`libs/`** — reusable libraries. Nothing here should import from
   `apps/`, `analyses/`, or `pages/`.
2. **`apps/`** — things that consume the libs and are their own
   deployable/runnable unit. Currently empty; this is where AI-engineering
   features go.
3. **Everything else** — analysis work, content, and one legacy app that
   predates the `apps/` convention.

## Top-level map

| Path | What it is |
|---|---|
| `libs/statsbomb/` | Python data layer — StatsBomb open-data extraction. |
| `libs/footballd3/` | JS/D3 viz component library. |
| `apps/` | Home for AI features and other new consumers. Empty today. |
| `pages/match-analysis/` | Legacy static HTML/JS dashboard. Predates `apps/`; not being migrated. |
| `analyses/` | 25 sequenced practice questions + a couple of standalone mini-projects (notebook + writeup each). Consumes `libs/statsbomb`. |
| `analyses/statsbomb/` | Two **exploratory notebooks**, not the library. Name collision with `libs/statsbomb/` is intentional-ish (predates the library extraction) — don't confuse the two. |
| `data/euro-2024/{match_id}/` | Committed **extractor output** (not raw data), produced by `scripts/extract_euro2024.py`. See "Data flow" below. |
| `scripts/extract_euro2024.py` | The one script that populates `data/euro-2024/`. |
| `scripts/check_docs.sh`, `scripts/check_tests.sh` | The docs/test gates — see `docs/tooling.md` / `docs/testing.md`. |
| `research/`, `literature_notes/`, `match_reactions/` | Pure content (notes, writeups). No code. |
| `set_piece_analytics/` | Scaffold — every README in it is empty. Not built out yet. |
| `scratch/` | Early precursor notebooks, superseded by `analyses/practice_questions/`. |
| `tests/` | pytest, for `libs/statsbomb` only (mirrored `unit`/`integration` tree — see `docs/testing.md`). `libs/footballd3` tests are co-located `*.test.js` files instead. |

## `libs/statsbomb` — Python data layer

Installs and imports normally: `uv sync` then `import statsbomb`. No
`sys.path` hack needed (that used to be required before the packaging fix —
if you see one in old code/notebooks, it's stale, not the convention).

Public API is `libs/statsbomb/__init__.py` — one `extract_*` function per
concept (`extract_shots`, `extract_pass_network`, `extract_formation`, …),
re-exported at the package level. Import from there, not from the internal
`extract_*.py` modules directly, unless you need a private helper (a few
tests do this deliberately — see `docs/testing.md`).

Full per-extractor reference (inputs, output JSON shape, CLI usage): see
`libs/statsbomb/README.md`. Don't duplicate that here — it drifts.

## `libs/footballd3` — JS viz layer

Public entry points are declared in `libs/footballd3/package.json`'s
`exports` map — one subpath per component (`footballd3/pitch`,
`footballd3/shotMap`, etc.). **Import via the subpath, not a relative path
into `components/`** — that's how the published npm package and
`tylermartins.com` both consume it.

Two live consumers, two different import styles:
- `tylermartins.com` (separate repo) — `import { createPitch } from "footballd3/pitch"`, resolved via npm (local workspace symlink in dev, published package in production).
- `pages/match-analysis/dashboard.js` (this repo, legacy, no bundler) — relative imports into `components/` directly, since it's plain browser ESM with no package resolution. This is the one place that reaches past the public entry points; it's contained to that one file.

Per-component API/JSON-contract docs: see each `libs/footballd3/components/*/README.md`.

## `apps/`

Empty. Reserved for AI-engineering features and any future consumer that's
its own deployable unit rather than library code or analysis. The legacy
dashboard (`pages/match-analysis/`) is *not* being folded in here — it
stays where it is.

## Data flow — and the known seam gap

```
libs/statsbomb/extract_*.py  →  scripts/extract_euro2024.py  →  data/euro-2024/{match_id}/*.json
```

That's the one real seam: `scripts/extract_euro2024.py` is the single
producer of `data/euro-2024/`. No raw StatsBomb data is committed
(`data/raw/`, `data/processed/` are gitignored) — only derived extracts.

**Known gap, not yet fixed:** the same match's JSON (currently match
`3943043`, the Euro 2024 Final) is also hand-copied into
`libs/footballd3/sample_data/` (component demos, renamed with a
`{match_id}_` prefix) and, in the separate `tylermartins.com` repo, into
`data/football/` (same renamed filenames). There is no sync script between
any of these three. If you're building something that reads match data
(a RAG pipeline, an ingestion script), read from `data/euro-2024/` — it's
the canonical one — and don't assume the other two are current.

## Env/secrets

`.env` exists at repo root and is gitignored. No `os.getenv`/`dotenv`/
`process.env` pattern is established yet anywhere in tracked source — the
first thing that needs `ANTHROPIC_API_KEY` or similar is establishing this
convention, not following one. Per the global convention: env vars, never
literals, not even in examples.

## Gates (docs + tests)

`scripts/check_docs.sh` and `scripts/check_tests.sh` are wired into the
Claude Code Stop hook (`.claude/settings.json`), git pre-commit, and (not
yet, by design) CI. Full rationale for what's checked and why lives in
`docs/tooling.md` (docs gate) and `docs/testing.md` (test gate) — read
those before changing test/doc conventions rather than re-deriving them
here.

## Cross-repo context

This repo sits inside a local-only npm-workspace superdirectory
(`portfolio/`, not itself a git repo) alongside the separate
`tylermartins.com` repo. `tylermartins.com` depends on `libs/footballd3`
two ways: a local workspace symlink in dev, and the published npm package
in production (Vercel installs from the registry, not the symlink) — so a
`footballd3` change only reaches production after `npm publish` **and** a
version bump in `tylermartins.com`'s `package.json`. `football-analytics`
itself has no build/deploy pipeline of its own.
