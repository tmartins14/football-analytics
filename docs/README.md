# docs/

Two kinds of document live here, for two different questions:

- **Reference docs** (this folder — `ARCHITECTURE.md`, `tooling.md`,
  `testing.md`): *how the repo works right now.* Living documents, kept
  current, not task-specific. Each carries a short "Task history" line
  pointing at the `specs/` doc(s) that explain *why* it's organized that
  way — the reference doc itself stays focused on the current state.
- **Task docs** (`specs/`): *what was done, when, and why.* One doc per
  body of work, following `specs/TEMPLATE.md`. Append-only in spirit — a
  finished task's doc doesn't get rewritten later, a new one gets added
  (or, for an ongoing multi-session task, dated subheadings get appended
  to the existing one; see `specs/2026-10-data-spec-v2-tactical-findings.md`
  for an example).

## Where to start

- **Human, wants the lay of the land:** `specs/README.md`'s index table,
  then the doc(s) for whatever you're curious about.
- **Agent, asked a question about this repo's history:** same — start at
  `specs/README.md`, not by grepping git log. Read a task doc's Summary
  and Outcome first; follow its "Where to look for more" links only if you
  need the authoritative source.
- **Either, wants to know how something works today** (not how it got
  that way): `ARCHITECTURE.md` (repo layout), `tooling.md` (the docs
  gate), `testing.md` (the test gate).

## What's *not* here

`ai/<project>/`'s own specs (`SPEC.md`, `DATA-SPEC.md`, `VERIFICATION-*.md`
— currently just `ai/match_summary/`) stay where they are. They're the
authoritative, living source for that project, managed by Tyler — not
something an agent edits (see this repo's `CLAUDE.md`) — and `specs/`
summarizes them rather than duplicating them. If you're looking for the
exact current acceptance values, decision log, or claim templates for
`ai/match_summary/`, go there directly; the matching doc in `specs/` will
point you to it rather than restate it.
