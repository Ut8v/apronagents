"""Matches ready issues to free workers.

The assigner speaks to workers through a small structural protocol rather
than importing the workers package: organs stay decoupled, and tests can
stand in trivial fakes.
"""

from __future__ import annotations

import asyncio
from typing import Protocol, Sequence

from apron.orchestrator.issue_graph import IssueGraph
from apron.orchestrator.planner import PlannedIssue


class AssignableWorker(Protocol):
    """What the assigner needs from a worker, nothing more."""

    @property
    def idle(self) -> bool: ...

    def reserve(self) -> None: ...

    async def work_on(self, issue: PlannedIssue) -> None: ...


class Assigner:
    """Hands each ready issue to a free worker."""

    def __init__(self, graph: IssueGraph, workers: Sequence[AssignableWorker]) -> None:
        self.graph = graph
        self.workers = list(workers)

    def dispatch(self) -> list[asyncio.Task]:
        """Assign every ready issue a free worker can take.

        Workers are reserved synchronously so a second dispatch cannot
        double-book them; the work itself runs as returned tasks.
        """
        tasks: list[asyncio.Task] = []
        for issue in self.graph.ready():
            worker = next((w for w in self.workers if w.idle), None)
            if worker is None:
                break
            worker.reserve()
            self.graph.mark_active(issue.issue_id)
            tasks.append(asyncio.create_task(worker.work_on(issue)))
        return tasks
