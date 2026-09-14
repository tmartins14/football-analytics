# ai

Home for AI-engineering work — one subdirectory per project, each
self-contained: code, its own SPEC (and DATA-SPEC, VERIFICATION, etc. as
needed), and any generated output the project produces.

Like `apps/`, these consume `libs/` (`libs/statsbomb`, `libs/footballd3`) as
normal package imports — never the reverse. `libs/` must stay unaware that
`ai/` exists.

## Projects

- `match_summary/` — auto-written match summaries (structured outcome +
  free-prose tactics) generated from `libs/statsbomb` extractor output. See
  `match_summary/SPEC.md`.
