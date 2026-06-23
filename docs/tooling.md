# Tooling — the documentation gate

This document explains the documentation enforcement setup in this repo: what it is,
why it exists, how it works, and how to maintain it. If you're changing the repo
layout or wondering why a check is failing, start here.

## The core idea: request vs. gate

There are two ways to make something reliably happen in a codebase:

- A **request** — written instructions you hope are followed. With a human or an AI,
  this is probabilistic: it works most of the time and fails silently the rest.
- A **gate** — a program that inspects the code and refuses to let it through unless
  a condition holds. This is deterministic: it doesn't depend on anyone remembering.

This setup uses both, deliberately layered. `CLAUDE.md` is the request layer (makes
correct docs more likely up front). `check_docs.sh` is the gate (guarantees they
exist before code lands). The request makes the gate trip less often; the gate is
what actually holds the line.

The one thing no gate can do: verify *quality*. It checks that a docstring, JSDoc
block, or README **exists** and is structurally complete — not that it's accurate or
useful. Accuracy is on the author and code review. A green gate means "documented,"
not "documented well."

## What "documented" means here

- **Python:** every module has a header docstring; every public function and class has
  a docstring. `__init__.py` package-marker files are exempt by policy (see below).
- **JS / D3:** every exported function or component has a JSDoc block with a
  description, `@param` for each parameter, and `@returns`.
- **Each component directory** under `src/footballd3/components/` has a `README.md`.

## The moving parts

| File | Role |
|------|------|
| `CLAUDE.md` | Request layer. Read by Claude Code each session: conventions, layout, and the definition of "documented." Guarantees nothing on its own. |
| `scripts/check_docs.sh` | The gate. Orchestrates the three checks and returns one verdict via exit code. |
| `.claude/settings.json` | Wires the gate into Claude Code as a **Stop hook** so a turn can't finish on missing docs. |
| `pyproject.toml` `[tool.interrogate]` | Python docstring policy (thresholds and exemptions). |
| `eslint.config.js` | JS JSDoc rules. |
| `package.json` | Declares `"type": "module"` so the ESM eslint config loads; holds the JS dev dependencies. |

## The three checks inside `check_docs.sh`

The script itself checks nothing — it runs three real tools and collects their results.

1. **interrogate (Python).** Walks `src/`, counts every module/function/class that
   should have a docstring vs. how many do, and fails below the configured threshold
   (100%). Policy lives in `pyproject.toml`.
2. **eslint + eslint-plugin-jsdoc (JS).** eslint is a linter; the plugin teaches it
   JSDoc rules; `eslint.config.js` switches those rules on for `src/footballd3/**`.
   Note: the plugin is inert until a rule references it — installing it does nothing
   on its own.
3. **README presence.** A shell loop asserting each component directory contains a
   `README.md`. Checks existence only, not content.

At the end it exits **0** if everything passed or **2** if anything failed (reasons on
stderr). Exit codes are how a program reports success/failure to its caller: 0 is
success by universal convention; we use 2 because that's the value Claude Code's hook
system treats as "block and keep working."

## Where it's enforced

The same one script is the single definition of "documented," called from three places:

- **Claude Code Stop hook** (`.claude/settings.json`) — blocks a turn from finishing
  with undocumented code. In-session enforcement.
- **git pre-commit** — blocks the commit. This is the real guarantee: it catches code
  regardless of who or what wrote it.
- **CI** — blocks the merge. (Add when the repo actually has merges to gate; premature
  before then.)

## The toolchain underneath

- **uv** — Python package manager. Installs `interrogate` (`uv add --dev interrogate`).
- **Node** — runtime that lets JavaScript run outside a browser. Ships with **npm**,
  the JS package manager.
- **npm** — installs `eslint` and `eslint-plugin-jsdoc` (`npm i -D eslint eslint-plugin-jsdoc`).

"Command not found" after installing usually means the tool isn't on your shell's
PATH yet — reopen the terminal or restart the editor before assuming it failed.

## Layout assumptions (update these if you move things)

`check_docs.sh` runs from the repo root, so its paths are relative to root. The
variables at the top of the script:

```
PY_PKG="src"                              # Python package to check
JS_DIR="src/footballd3"                   # JS components directory
COMPONENT_DIRS=( "src/footballd3/components/"* )   # dirs that must each have a README
```

If you relocate the Python source or the D3 library, update these — and the
`files` glob in `eslint.config.js` (`src/footballd3/**/*.js`). A future cleanup worth
doing is moving the JS library out of `src/` (which is the Python root) to its own
top-level directory, so the two languages stop bleeding into each other.

## Configuration policy — one place, not two

interrogate's rules live in `pyproject.toml` under `[tool.interrogate]`, which the tool
reads automatically on every run. Keep them there, **not** duplicated as flags in the
script. The reason: command-line flags apply only to the exact command they're typed
on. If the policy lives only in the script, a bare `uv run interrogate src` typed by
hand uses different rules than the gate — which causes confusing "it fails by hand but
passes in the script" drift. Config in `pyproject.toml` makes every invocation behave
identically.

Current Python policy:

```toml
[tool.interrogate]
fail-under = 100
ignore-private = true
ignore-magic = true
ignore-nested-functions = true
ignore-init-method = true     # skips class __init__ constructor methods
ignore-init-module = true     # skips __init__.py package-marker files
```

Note `ignore-init-method` (constructor methods) and `ignore-init-module` (`__init__.py`
files) are different settings. `__init__.py` files are exempt on purpose: requiring a
docstring on every package-marker file is stricter than most projects bother with and
tends to produce filler that passes the tool while informing no one.

## Running it and reading the output

```bash
bash scripts/check_docs.sh; echo "exit: $?"
```

- Exit 0 → everything documented.
- Exit 2 → something isn't; the reasons are printed above the summary line.

For a detailed per-file Python view that matches the gate's rules (because the policy
is in `pyproject.toml`, no flags needed):

```bash
uv run interrogate -vv src
```

In interrogate's report, **MISSED** means "this object has no docstring" — not "the
tool failed to find it." The object was found; it just isn't documented.

## Gotchas and failure modes (learned the hard way)

- **Silent skip on a wrong `JS_DIR`.** The eslint block only runs `if [ -d "$JS_DIR" ]`.
  A wrong path means eslint never runs and the JS side reports clean while checking
  nothing — a green check that verifies nothing, the worst kind. If the JS half looks
  suspiciously fine, confirm the path first.
- **Blank line above a JSDoc block.** eslint only associates a JSDoc block that sits
  *immediately* above the declaration. One blank line between them and it reads as
  missing. Linters are literal; "close enough" fails.
- **`/**` vs `/*`.** Only a block opening with `/**` (two asterisks) counts as JSDoc.
- **"Document it" vs. "delete it."** A tool flagging a missing docstring has no
  judgment about whether the file should exist. The stray `src/footballd3/__init__.py`
  (a Python marker inside a JS library) was flagged as undocumented; the right fix was
  deleting it, not documenting it. You supply the judgment.
- **`"type": "module"`.** The ESM `eslint.config.js` only loads if `package.json`
  declares this. Otherwise rename the config to `eslint.config.mjs`.

## Extending the gate

If you add checks, keep the ceiling in mind: structure is gateable, quality isn't.

- **Reasonable to add:** a non-empty / no-placeholder check on READMEs (raises the
  floor from "file exists" to "someone wrote something"), once it's worth the few lines.
- **Defer until there's real signal:** a required-sections validator (grep for
  `## Purpose` etc.). Write a few real component READMEs first and gate the sections
  that genuinely recur — don't freeze a schema from a guess. `pitch` takes a config
  object, not JSON, so a hard-required "JSON contract" heading fits `shotMap` but not
  every component.
- **Don't build:** a check that the contract described in a README matches the JSON the
  code emits. It sounds ideal but is brittle, fights every legitimate change, and
  becomes its own maintenance burden. That alignment is what review is for.