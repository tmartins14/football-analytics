<!--
TEMPLATE.md — the task-doc template for docs/specs/.

Mirrored byte-for-byte in tylermartins.com's docs/specs/TEMPLATE.md. If you
change this file, change that one the same way in the same commit (same
convention this project already uses for DESIGN.md <-> ~/dev/context/style.md).

This is a template, not a doc itself — delete this comment block and
everything below the --- / frontmatter when you copy it to start a real one.
Fill every frontmatter field; omit a body section only where its own
instruction says you can.
-->

---
title: <Short task name — matches the h1 below>
status: done | in-progress | planned | superseded
started: YYYY-MM-DD
completed: YYYY-MM-DD | ongoing
repo: football-analytics | tylermartins.com
area: <primary path this touched, e.g. libs/statsbomb, ai/match_summary, app/football>
related_prs: [12, 13]
related_docs: [path/to/doc.md relative to this repo's root, or ../../other-repo/docs/specs/foo.md]
tags: [short, lowercase, tags]
---

# <Title>

## Summary

One paragraph, written so an agent reading only this section already has
the gist: what this task was, why it happened, and what the outcome is.
No detail that isn't repeated or expanded below.

## Context

What problem or need prompted this. What was true before it. Why now.

## What was done

The actual work. For a single-session task, plain prose or a list is fine.
For multi-part or multi-session work, use dated subheadings so the doc
reads as a timeline, not a wall of text:

### YYYY-MM-DD — <phase or part name>

...

### YYYY-MM-DD — <next phase>

...

## Key decisions

Choices made and why — especially ones not obvious from reading the code
or the PR diff alone (a tradeoff rejected, a constraint that shaped the
approach, something the obvious reading of the code wouldn't tell you).
Omit this section entirely if there's nothing worth recording here that
isn't already in "What was done."

## Outcome

Current state: what shipped, what's still open, known issues or follow-ups
flagged for later. If `status` above is `in-progress` or `planned`, say so
here too and what the next step is.

## Where to look for more

Links to the authoritative source — PRs, the actual spec/code files, a
related task doc in this folder or the sibling repo's `docs/specs/`. This
doc summarizes; it never duplicates detail that already lives somewhere
else and could drift out of sync with it.
