# Contributing to Apron Agents

Thanks for wanting to help. This document covers the workflow and the few
rules that keep the project safe and readable.

## Getting set up

You need Python 3.11+, [uv](https://docs.astral.sh/uv/), git, and (for
dashboard work) Node 20+.

```sh
git clone https://github.com/Ut8v/apronagents.git
cd apronagents
uv sync                # python env + dependencies
uv run pytest          # the whole suite should pass before you start
```

For the dashboard:

```sh
cd src/dashboard
npm ci
npm run dev            # Vite dev server, proxied to a locally running apron
```

To try the whole tool without any model account:

```sh
uv run apron start --runner demo
```

## Making changes

- Branch from `main`; open a pull request when ready. CI runs the Python
  suite on 3.11–3.13, typechecks and builds the dashboard, and verifies the
  wheel installs.
- Keep pull requests small and focused, and commit in small, coherent steps —
  the same spirit as the tool itself.
- Add or update tests with your change. `tests/unit/` mirrors the package
  layout; `tests/integration/` runs full loops against throwaway sandboxes.

## The invariants

A few properties of this codebase are load-bearing and tested. Changes that
weaken them will not be merged:

1. **The sandbox never touches a real remote.** All raw git goes through
   `src/apron/sandbox/git_ops.py` — the one audited path — and the tests in
   `tests/unit/test_git_ops.py` enforce its rules. Do not add git calls
   anywhere else.
2. **Subprocesses are confined.** Only `git_ops.py` (git), `merge/tester.py`
   (the project's test command), and `workers/cli_runner.py` (the user's
   agent CLI) may spawn processes. A test enforces this list.
3. **`.claude/` is read-only.** Apron discovers Claude Code agent definitions
   but never writes to them; edits go to the `.apron/` overlay.
4. **The dashboard renders bus state only.** New UI state must come from
   events and the store, not from component-local sources of truth.

## Code conventions

- One responsibility per module; soft cap ~300 lines per file, hard cap 500.
  Functions aim for under ~50 lines. Frontend components: one per file,
  under ~200 lines.
- Events are past-tense facts (`ReviewOpened`, `MergeSucceeded`) and are
  defined once in `src/apron/bus/events.py`.
- Files are named for what they do (`assigner.py`, `conflict.py`), not vague
  labels (`utils.py`, `helpers.py`).
- Organs coordinate through the bus, not by importing each other's internals.

## Reporting bugs and proposing features

Open a GitHub issue. For bugs, include the command you ran, the runner in
use (`claude-code`, `codex`, `api`, `demo`), and the relevant log output.
For features, a short problem statement beats a solution spec.
