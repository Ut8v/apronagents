"""Detects merge conflicts and cleans up after them.

A conflicted merge is never forced: the controller aborts it, reports which
files collided, and the issue is routed back to a worker to redo its branch
on top of the new main."""

from __future__ import annotations

from apron.sandbox.clone import WorkerClone


def conflicted_files(clone: WorkerClone) -> list[str]:
    """The files left unmerged by the in-progress merge."""
    result = clone.run("diff", "--name-only", "--diff-filter=U")
    return [line for line in result.stdout.splitlines() if line]


def abort_merge(clone: WorkerClone) -> None:
    """Back out of the conflicted merge, leaving the clone clean on main."""
    clone.run("merge", "--abort")
