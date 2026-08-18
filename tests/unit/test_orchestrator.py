"""Tests for the orchestrator's rework loop: send-back feedback must reach
the next worker pass through the issue description."""

import asyncio

from apron.agents.definition import AgentDefinition, AgentRole
from apron.bus.bus import EventBus
from apron.bus.events import ChangesRequested, TaskReceived, TestsFailed
from apron.orchestrator import Assigner, IssueGraph, Orchestrator
from apron.orchestrator.planner import PlannedIssue, StaticPlanner

DEFINITION = AgentDefinition(
    name="orchestrator-default",
    description="",
    role=AgentRole.ORCHESTRATOR,
    prompt="plan",
)


class RecordingWorker:
    """Stands in for a worker; records every issue it is handed."""

    def __init__(self) -> None:
        self.issues: list[PlannedIssue] = []
        self._busy = False

    @property
    def idle(self) -> bool:
        return not self._busy

    def reserve(self) -> None:
        self._busy = True

    async def work_on(self, issue: PlannedIssue) -> None:
        self.issues.append(issue)
        self._busy = False


def build(issues):
    bus = EventBus()
    graph = IssueGraph()
    worker = RecordingWorker()
    Orchestrator(
        definition=DEFINITION,
        planner=StaticPlanner(issues),
        graph=graph,
        assigner=Assigner(graph, [worker]),
        bus=bus,
    )
    return bus, worker


async def settle():
    for _ in range(10):
        await asyncio.sleep(0)


async def test_review_feedback_reaches_the_rework_pass():
    bus, worker = build([PlannedIssue("i1", "Add parser", "Parse the config.")])
    await bus.publish(TaskReceived(task_id="t1", prompt="do it"))
    await settle()
    assert worker.issues[0].description == "Parse the config."

    await bus.publish(
        ChangesRequested(
            issue_id="i1",
            reason="wrong file",
            annotations=({"path": "cli.py", "line": 14, "note": "guard None"},),
        )
    )
    await settle()

    rework = worker.issues[1].description
    assert rework.startswith("Parse the config.")
    assert "wrong file" in rework
    assert "cli.py line 14: guard None" in rework


async def test_failed_tests_feed_their_log_into_the_rework_pass():
    bus, worker = build([PlannedIssue("i1", "Add parser", "Parse the config.")])
    await bus.publish(TaskReceived(task_id="t1", prompt="do it"))
    await settle()

    await bus.publish(TestsFailed(issue_id="i1", log_tail="AssertionError: boom"))
    await settle()

    assert "failed the test suite" in worker.issues[1].description
    assert "AssertionError: boom" in worker.issues[1].description
