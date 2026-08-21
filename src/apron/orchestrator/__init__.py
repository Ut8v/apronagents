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
from typing import Callable

from apron.agents.definition import AgentDefinition
from apron.bus.bus import EventBus
from apron.bus.events import (
    ChangesRequested,
    IssueQueued,
    MergeConflictDetected,
    MergeSucceeded,
    PlanApproved,
    PlanningProgress,
    PlanProposed,
    TaskCompleted,
    TaskPlanned,
    TaskReceived,
    TestsFailed,
)
from apron.config import Mode
from apron.orchestrator.assigner import Assigner
from apron.orchestrator.issue_graph import IssueGraph
from apron.orchestrator.planner import (
    PlanError,
    PlannedIssue,
    Planner,
    StaticPlanner,
    issues_from_payload,
)

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
        mode_provider: Callable[[], Mode] | None = None,
    ) -> None:
        self.definition = definition
        self.planner = planner
        self.graph = graph
        self.assigner = assigner
        self.bus = bus
        # With a provider wired, supervised runs hold every plan at the plan
        # gate for human review before any issue is queued. Without one
        # (tests, embedded use) plans dispatch immediately, as before.
        self._mode_provider = mode_provider
        self._pending_plans: dict[str, list[PlannedIssue]] = {}
        self._work_tasks: set[asyncio.Task] = set()
        self._task_id: str | None = None
        bus.subscribe(self._on_task_received, TaskReceived)
        bus.subscribe(self._on_plan_approved, PlanApproved)
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
        if self._gate_active():
            # Supervised: the plan waits for the human, exactly like a merge.
            self._pending_plans[event.task_id] = issues
            await self.bus.publish(
                PlanProposed(
                    task_id=event.task_id,
                    issues=tuple(
                        {
                            "id": i.issue_id,
                            "title": i.title,
                            "description": i.description,
                            "depends_on": list(i.depends_on),
                        }
                        for i in issues
                    ),
                )
            )
            return
        await self._queue_issues(event.task_id, issues)

    def _gate_active(self) -> bool:
        return (
            self._mode_provider is not None
            and self._mode_provider() is Mode.SUPERVISED
        )

    async def _on_plan_approved(self, event: PlanApproved) -> None:
        """The human cleared a (possibly edited) plan: queue it for real."""
        if event.task_id not in self._pending_plans:
            return
        try:
            issues = issues_from_payload({"issues": list(event.issues)})
        except PlanError as error:
            log.error("approved plan for %s rejected: %s", event.task_id, error)
            return
        del self._pending_plans[event.task_id]
        await self._queue_issues(event.task_id, issues)

    async def _queue_issues(
        self, task_id: str, issues: list[PlannedIssue]
    ) -> None:
        for issue in issues:
            self.graph.add(issue)
            await self.bus.publish(
                IssueQueued(
                    issue_id=issue.issue_id,
                    task_id=task_id,
                    title=issue.title,
                    description=issue.description,
                    depends_on=issue.depends_on,
                )
            )
        await self.bus.publish(
            TaskPlanned(
                task_id=task_id,
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
        """A review rejection, conflict, or red test run: rework the issue,
        with the feedback folded into its description so the next worker
        actually knows what went wrong."""
        if event.issue_id in self.graph:
            self.graph.revise(event.issue_id, _feedback_text(event))
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


def _feedback_text(
    event: ChangesRequested | MergeConflictDetected | TestsFailed,
) -> str:
    """Render a send-back event as rework instructions for the next pass."""
    if isinstance(event, ChangesRequested):
        lines = ["Feedback from the reviewer on your previous attempt:"]
        if event.reason:
            lines.append(f"- {event.reason}")
        for a in event.annotations:
            lines.append(f"- {a['path']} line {a['line']}: {a['note']}")
        if len(lines) == 1:
            lines.append("- The reviewer sent this back; rework it carefully.")
        lines.append("Address every point above.")
        return "\n".join(lines)
    if isinstance(event, TestsFailed):
        text = "Your previous attempt failed the test suite."
        if event.log_tail:
            text += f" Failing output:\n{event.log_tail}"
        return text
    detail = f" ({event.detail})" if event.detail else ""
    return (
        f"Your previous branch conflicted with main{detail}. "
        "Redo the issue on top of the current main."
    )
