"""The Phase 3 end-to-end loop: a task is split into two independent issues,
two workers (fake runners, real sandbox git) branch and commit in isolation,
and both open reviews — everything coordinated through the bus."""

import pytest

from apron.agents.definition import AgentRole, AgentSource
from apron.agents.discovery import discover_agents, resolve_for_role
from apron.bus.bus import EventBus
from apron.bus.events import IssueState, ReviewOpened, TaskReceived
from apron.bus.store import StateStore
from apron.orchestrator import Assigner, IssueGraph, Orchestrator, PlannedIssue, StaticPlanner
from apron.sandbox.repo import SandboxRepo
from apron.workers.runner import FakeRunner
from apron.workers.worker import Worker

ISSUES = [
    PlannedIssue(issue_id="i1", title="Add greeting module", description="Create greeting.py"),
    PlannedIssue(issue_id="i2", title="Add farewell module", description="Create farewell.py"),
]

OUTPUTS = {
    "i1": {"greeting.py": "def greet():\n    return 'hello'\n"},
    "i2": {"farewell.py": "def bye():\n    return 'bye'\n"},
}


@pytest.fixture
def repo(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("demo project\n")
    with SandboxRepo.create(seed_dir=project) as sandbox_repo:
        yield sandbox_repo


async def test_task_flows_from_plan_to_two_open_reviews(tmp_path, repo):
    bus = EventBus()
    store = StateStore()
    bus.subscribe(store.record)

    # Both organs load their behavior through the discovery layer.
    agents = discover_agents(
        user_apron_dir=tmp_path / "none",
        claude_user_dir=tmp_path / "none",
        claude_project_dir=tmp_path / "none",
        project_apron_dir=tmp_path / "none",
    )
    orchestrator_def = resolve_for_role(agents, AgentRole.ORCHESTRATOR)
    worker_def = resolve_for_role(agents, AgentRole.WORKER)
    assert orchestrator_def.source is AgentSource.SHIPPED
    assert worker_def.source is AgentSource.SHIPPED

    runner = FakeRunner(OUTPUTS)
    workers = [
        Worker(f"worker-{n}", worker_def, repo, runner, bus) for n in (1, 2)
    ]
    graph = IssueGraph()
    orchestrator = Orchestrator(
        definition=orchestrator_def,
        planner=StaticPlanner(ISSUES),
        graph=graph,
        assigner=Assigner(graph, workers),
        bus=bus,
    )

    reviews: list[ReviewOpened] = []
    bus.subscribe(reviews.append, ReviewOpened)

    await bus.publish(TaskReceived(task_id="t1", prompt="add greeting and farewell"))
    await orchestrator.wait_for_workers()

    # Two reviews opened, one per issue, by two different workers.
    assert {r.issue_id for r in reviews} == {"i1", "i2"}
    assert {r.worker_id for r in reviews} == {"worker-1", "worker-2"}
    assert runner.calls == [("worker-default", "i1"), ("worker-default", "i2")]

    # Each worker pushed its own branch to the bare repo; main is untouched.
    assert sorted(repo.branches()) == ["issue/i1", "issue/i2", "main"]
    main_tree = repo.git.run(
        "ls-tree", "-r", "--name-only", "main", cwd=repo.bare_path
    ).stdout.split()
    assert main_tree == ["README.md"]
    branch_file = repo.git.run(
        "show", "issue/i1:greeting.py", cwd=repo.bare_path
    ).stdout
    assert "hello" in branch_file

    # The store projected the whole journey; a late dashboard could catch up.
    states = {i.issue_id: i.state for i in store.issues()}
    assert states == {"i1": IssueState.IN_REVIEW, "i2": IssueState.IN_REVIEW}
    kinds = [event.kind for _, event in store.events_since()]
    assert kinds.count("IssueQueued") == 2
    assert kinds.count("ReviewOpened") == 2
    assert "TaskPlanned" in kinds
