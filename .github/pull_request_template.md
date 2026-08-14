## What this changes

<!-- One or two sentences: what does this PR do, and why? -->

## How it was verified

<!-- Tests added/updated, manual runs, screenshots for dashboard changes -->

## Checklist

- [ ] `uv run pytest` passes locally
- [ ] New behavior is covered by tests
- [ ] No raw git or subprocess calls outside the audited modules
      (`sandbox/git_ops.py`, `merge/tester.py`, `workers/cli_runner.py`)
- [ ] Dashboard changes: `npx tsc --noEmit` and `npm run build` pass
