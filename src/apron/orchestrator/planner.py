"""Turns a task into a list of issues that are as file-independent as
possible. Most merge conflicts are prevented here, before they can happen.

For now planning is a pluggable protocol with a deterministic implementation;
the agent-backed planner (driving the orchestrator agent definition through a
runner) arrives once the end-to-end loop is solid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class PlannedIssue:
    """One small, independently workable chunk of the task."""

    issue_id: str
    title: str
    description: str
    depends_on: tuple[str, ...] = ()


class Planner(Protocol):
    """Anything that can split a task into planned issues."""

    def plan(self, task_id: str, prompt: str) -> list[PlannedIssue]: ...


class StaticPlanner:
    """Returns a fixed plan regardless of the prompt.

    Used by tests and dry runs to exercise the full loop with a known split.
    """

    def __init__(self, issues: Sequence[PlannedIssue]) -> None:
        self._issues = list(issues)

    def plan(self, task_id: str, prompt: str) -> list[PlannedIssue]:
        return list(self._issues)
