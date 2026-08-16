<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/svg/mark-reverse.svg">
    <img src="assets/brand/svg/mark.svg" alt="Apron Agents" width="88" height="88">
  </picture>
</p>

# Apron Agents

<p>
  <a href="https://pypi.org/project/apronagents/"><img src="https://img.shields.io/pypi/v/apronagents" alt="PyPI"></a>
  <a href="https://pypi.org/project/apronagents/"><img src="https://img.shields.io/pypi/pyversions/apronagents" alt="Python versions"></a>
  <a href="https://github.com/Ut8v/apronagents/actions/workflows/ci.yml"><img src="https://github.com/Ut8v/apronagents/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license"></a>
</p>

A local, one-command tool that breaks a coding task into small independent issues,
hands them to worker agents that each work in an isolated sandbox, and merges their
work one chunk at a time behind a human review gate.

The name comes from the airport apron: the staging area where aircraft are prepped
and checked before they ever reach the runway. Apron Agents does the same with code
before it reaches your real remote.

## How it works

- An **orchestrator** agent splits your task into small, file-independent issues.
- **Worker** agents each claim an issue and work in an isolated clone of a
  disposable, fully local sandbox repository (a bare repo in a temp dir acting as a
  "fake GitHub"). Your real remote is never touched.
- A **merge controller** merges one branch at a time, running tests on every
  candidate merge.
- A **dashboard** gives you a live view of every agent plus a chunk-by-chunk
  review-and-merge control surface. In supervised mode, nothing merges without
  your approval; in autonomous mode, green tests are enough.
- When everything is merged and green, the final result is copied into your
  working directory and the tool stops. You test locally and run any real git
  operations yourself.

## Install

```sh
pip install apronagents
```

Then, from the project directory you want the agents to work on:

```sh
apron start
```

This boots the orchestrator, workers, merge controller, and dashboard server,
and opens the dashboard in your browser. Enter a task, review the diffs, and
approve merges chunk by chunk; when everything is green the result lands in
your working directory and the tool stops.

No account? Try the whole flow with fake agents:

```sh
apron start --runner demo
```

Common flags:

```sh
apron start [--mode supervised|autonomous] [--runner ...] [--test-command 'pytest -q']
apron task "add dark mode"   # dispatch to a running apron from your terminal
```

## Quick start from a clone

For hacking on Apron itself:

```sh
git clone https://github.com/Ut8v/apronagents && cd apronagents
./run start
```

This sets up the environment with [uv](https://docs.astral.sh/uv/) and
launches everything the same way.

## Agent backends

Workers run on whatever you already use — pick with `--runner` or let
auto-detection choose:

| Runner | Powered by | Needs |
|---|---|---|
| `claude-code` | The `claude` CLI, headless | Any Claude plan (Pro/Max) or API login — whatever Claude Code already uses |
| `codex` | The `codex` CLI, headless | A ChatGPT plan or OpenAI key — whatever Codex already uses |
| `api` | The Anthropic API directly | `ANTHROPIC_API_KEY` or an `ant auth login` profile |
| `demo` | Fake in-process agents | Nothing — try the whole flow with no account |

Any other headless agent CLI can be plugged in as a `CliProfile`
(`src/apron/workers/cli_runner.py`).

## Customizing agents

Agent behavior lives in editable markdown definitions, not code. Apron ships
defaults, discovers your existing `.claude/agents/` definitions read-only,
and writes any edits you make in the dashboard to a `.apron/` overlay that
hot-reloads on the next issue.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — setup, workflow, and the invariants
every change must respect. CI runs the test suite (Python 3.11–3.13), the
dashboard typecheck/build, and a wheel install smoke test on every push and
pull request.

## License

[MIT](LICENSE)
