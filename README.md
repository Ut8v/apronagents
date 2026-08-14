# Apron Agents

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

## Quick start

```sh
./run start
```

This sets up the environment with [uv](https://docs.astral.sh/uv/), boots the
orchestrator, workers, merge controller, and dashboard server, and opens the
dashboard in your browser.

Once the environment exists you can also launch directly:

```sh
apron start
```

## Status

Early development. The event bus and state store are in place; the sandbox git
layer, agents, merge controller, and dashboard are being built out.

## License

MIT
