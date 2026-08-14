"""Abstract AgentRunner interface: the backend-agnostic contract every
execution backend implements.

A runner is given an agent definition, one issue, and the worker's clone
directory; it makes the changes on disk and reports back. Committing and
pushing stay the worker's job, so every backend gets the same git behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from apron.agents.definition import AgentDefinition
from apron.orchestrator.planner import PlannedIssue


@dataclass(frozen=True)
class WorkResult:
    """What a runner reports after working an issue."""

    summary: str = ""


class AgentRunner(Protocol):
    """Anything that can execute an agent against a working directory."""

    async def run_issue(
        self,
        definition: AgentDefinition,
        issue: PlannedIssue,
        workdir: Path,
    ) -> WorkResult: ...


class FakeRunner:
    """In-memory backend for tests and dry runs.

    Instead of calling a model, it writes canned files per issue id, which
    makes the whole orchestration loop testable without any agent."""

    def __init__(self, outputs: Mapping[str, Mapping[str, str]]) -> None:
        self._outputs = outputs
        self.calls: list[tuple[str, str]] = []  # (agent name, issue id)

    async def run_issue(
        self,
        definition: AgentDefinition,
        issue: PlannedIssue,
        workdir: Path,
    ) -> WorkResult:
        self.calls.append((definition.name, issue.issue_id))
        files = self._outputs.get(issue.issue_id, {})
        for relative, content in files.items():
            path = workdir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return WorkResult(summary=f"{issue.title}: wrote {len(files)} file(s)")
