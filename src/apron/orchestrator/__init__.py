"""Orchestrator organ: turns a task into independent issues, tracks their
dependencies, and assigns ready issues to free workers.

The :class:`Orchestrator` facade is thin glue between the bus and the three
jobs in this package; the planning, dependency, and assignment logic each
live in their own module. Its behavior is an agent definition resolved
through discovery (``role: orchestrator``), never hardcoded.
"""

from __future__ import annotations

import asyncio
import logging

from apron.agents.definition import AgentDefinition
from apron.bus.bus import EventBus
from apron.bus.events import (
    ChangesRequested,
    IssueQueued,
    MergeConflictDetected,
    MergeSucceeded,
    PlanningProgress,
    TaskCompleted,
    TaskPlanned,
    TaskReceived,
    TestsFailed,
)
from apron.orchestrator.assigner import Assigner
from apron.orchestrator.issue_graph import IssueGraph
from apron.orchestrator.planner import PlannedIssue, Planner, StaticPlanner

log = logging.getLogger(__name__)

__all__ = [
    "Assigner",
    "IssueGraph",
    "Orchestrator",
    "PlannedIssue",
    "Planner",
    "StaticPlanner",
]


class Orchestrator:
    """Listens for tasks, plans them, queues issues, and drives assignment."""

    def __init__(
        self,
        definition: AgentDefinition,
        planner: Planner,
        graph: IssueGraph,
        assigner: Assigner,
        bus: EventBus,
    ) -> None:
        self.definition = definition
        self.planner = planner
        self.graph = graph
        self.assigner = assigner
        self.bus = bus
        self._work_tasks: set[asyncio.Task] = set()
        self._task_id: str | None = None
        bus.subscribe(self._on_task_received, TaskReceived)
        bus.subscribe(self._on_merge_succeeded, MergeSucceeded)
        bus.subscribe(
            self._on_sent_back, (ChangesRequested, MergeConflictDetected, TestsFailed)
        )

    async def _on_task_received(self, event: TaskReceived) -> None:
        # Planning can take a model many seconds; run it as a background
        # task so publishing TaskReceived (and the HTTP request behind it)
        # returns immediately instead of hanging until the plan is ready.
        self._task_id = event.task_id
        task = asyncio.ensure_future(self._plan(event))
        self._work_tasks.add(task)
        task.add_done_callback(self._work_tasks.discard)

    async def _plan(self, event: TaskReceived) -> None:
        async def note(text: str) -> None:
            await self.bus.publish(
                PlanningProgress(task_id=event.task_id, note=text)
            )

        # Say something before the model starts thinking, so the dispatch
        # terminal never sits silent while the plan is being written.
        await note("splitting the task into issues…")
        try:
            issues = await self.planner.plan(
                event.task_id, event.prompt, on_progress=note
            )
        except Exception:
            log.exception("planning failed for task %s", event.task_id)
            await note("planning failed — check the apron terminal for details")
            return
        for issue in issues:
            self.graph.add(issue)
            await self.bus.publish(
                IssueQueued(
                    issue_id=issue.issue_id,
                    task_id=event.task_id,
                    title=issue.title,
                    description=issue.description,
                    depends_on=issue.depends_on,
                )
            )
        await self.bus.publish(
            TaskPlanned(
                task_id=event.task_id,
                issue_ids=tuple(issue.issue_id for issue in issues),
            )
        )
        self.dispatch()

    async def _on_merge_succeeded(self, event: MergeSucceeded) -> None:
        self.graph.mark_merged(event.issue_id)
        if self.graph.all_merged() and self._task_id is not None:
            await self.bus.publish(TaskCompleted(task_id=self._task_id))
        self.dispatch()

    async def _on_sent_back(
        self, event: ChangesRequested | MergeConflictDetected | TestsFailed
    ) -> None:
        """A review rejection, conflict, or red test run: rework the issue."""
        if event.issue_id in self.graph:
            self.graph.release(event.issue_id)
            self.dispatch()

    def dispatch(self) -> None:
        """Hand out whatever is ready; keep the running tasks alive."""
        for task in self.assigner.dispatch():
            self._work_tasks.add(task)
            task.add_done_callback(self._work_tasks.discard)

    async def wait_for_workers(self) -> None:
        """Wait until every in-flight worker task settles (tests, shutdown)."""
        while self._work_tasks:
            await asyncio.gather(*list(self._work_tasks))
