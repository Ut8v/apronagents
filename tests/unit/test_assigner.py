"""Tests for matching ready issues to free workers."""

import asyncio

from apron.orchestrator.assigner import Assigner
from apron.orchestrator.issue_graph import IssueGraph
from apron.orchestrator.planner import PlannedIssue


class RecordingWorker:
    """Minimal stand-in satisfying the AssignableWorker protocol."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.busy = False
        self.worked: list[str] = []
        self.finish = asyncio.Event()

    @property
    def idle(self) -> bool:
        return not self.busy

    def reserve(self) -> None:
        assert not self.busy
        self.busy = True

    async def work_on(self, issue: PlannedIssue) -> None:
        self.worked.append(issue.issue_id)
        await self.finish.wait()
        self.busy = False


def issue(issue_id: str, *deps: str) -> PlannedIssue:
    return PlannedIssue(
        issue_id=issue_id, title=issue_id, description="", depends_on=tuple(deps)
    )


async def test_ready_issues_go_to_free_workers():
    graph = IssueGraph()
    graph.add(issue("a"))
    graph.add(issue("b"))
    workers = [RecordingWorker("w1"), RecordingWorker("w2")]
    assigner = Assigner(graph, workers)

    tasks = assigner.dispatch()
    assert len(tasks) == 2
    assert graph.ready() == []  # both marked active

    for worker in workers:
        worker.finish.set()
    await asyncio.gather(*tasks)
    assert workers[0].worked == ["a"]
    assert workers[1].worked == ["b"]


async def test_more_issues_than_workers_leaves_the_rest_queued():
    graph = IssueGraph()
    for issue_id in ("a", "b", "c"):
        graph.add(issue(issue_id))
    worker = RecordingWorker("w1")
    assigner = Assigner(graph, [worker])

    tasks = assigner.dispatch()
    assert len(tasks) == 1
    assert assigner.dispatch() == []  # no free worker: nothing double-booked

    worker.finish.set()
    await asyncio.gather(*tasks)
    assert worker.worked == ["a"]


async def test_blocked_issues_are_not_dispatched():
    graph = IssueGraph()
    graph.add(issue("base"))
    graph.add(issue("dependent", "base"))
    worker = RecordingWorker("w1")
    worker.finish.set()
    assigner = Assigner(graph, [worker])

    await asyncio.gather(*assigner.dispatch())
    assert worker.worked == ["base"]

    graph.mark_merged("base")
    await asyncio.gather(*assigner.dispatch())
    assert worker.worked == ["base", "dependent"]
