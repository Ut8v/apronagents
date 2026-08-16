"""Abstract AgentRunner interface: the backend-agnostic contract every
execution backend implements.

A runner is given an agent definition, one issue, and the worker's clone
directory; it makes the changes on disk and reports back. Committing and
pushing stay the worker's job, so every backend gets the same git behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Mapping, Protocol

from apron.agents.definition import AgentDefinition
from apron.orchestrator.planner import PlannedIssue

# Called with a short human-readable note whenever the agent does something
# observable ("Edit tz.py", "Running the tests..."). Backends that can't
# stream simply never call it.
OnProgress = Callable[[str], Awaitable[None]]


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
        on_progress: OnProgress | None = None,
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
        on_progress: OnProgress | None = None,
    ) -> WorkResult:
        self.calls.append((definition.name, issue.issue_id))
        files = self._outputs.get(issue.issue_id, {})
        for relative, content in files.items():
            path = workdir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            if on_progress is not None:
                await on_progress(f"wrote {relative}")
        return WorkResult(summary=f"{issue.title}: wrote {len(files)} file(s)")
