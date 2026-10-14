# specs/

This is where a **written spec goes before it's built** — the input to a
task, not a record of one. Drop a filled-in spec here, then hand it to an
agent to plan from and execute. If you're looking for a record of what's
already been done, that's `../task-history/` instead.

This repo already has two spec formats, depending on the shape of the
task:

- **`SPEC_TEMPLATE.md`** (repo root) — a lightweight "interview pattern"
  template for a single, well-scoped task: paste it into a fresh chat,
  get interviewed one question at a time, read and fix the result
  yourself, then hand the *finished* spec to a new session to execute.
- **`.specify/`** (Spec Kit) — for a feature described from scratch with
  no context yet; drives the `speckit-*` skills (`speckit-specify`,
  `speckit-plan`, `speckit-tasks`, etc.).

`ai/<project>/`'s own specs (`SPEC.md`, `DATA-SPEC.md`, and friends —
currently `ai/match_summary/`) still live inside the project itself, not
here, per `docs/ARCHITECTURE.md` — an AI-engineering project is
self-contained (code, spec, and output together), so its spec travels
with it rather than sitting in this folder.

This folder is empty right now — nothing of this shape has been dropped
in yet. That's expected, not a gap to fill.
