"""A small harness wiring the full loop for integration tests: real bus,
store, sandbox git, workers, orchestrator, and merge controller — with the
planner and runner supplied per test."""

import asyncio
from dataclasses import dataclass, field

import pytest

from apron.agents.definition import AgentRole
from apron.agents.discovery import discover_agents, resolve_for_role
from apron.bus.bus import EventBus
from apron.bus.events import Event
from apron.bus.store import StateStore
from apron.config import Mode
from apron.merge.controller import MergeController
from apron.merge.tester import CommandTester, Tester
from apron.orchestrator import Assigner, IssueGraph, Orchestrator, StaticPlanner
from apron.sandbox.repo import SandboxRepo
from apron.workers.runner import AgentRunner
from apron.workers.worker import Worker

DEFAULT_TIMEOUT = 15.0


class EventProbe:
    """Records every event and lets a test await specific kinds."""

    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        bus.subscribe(self.events.append)

    def of_kind(self, kind: str) -> list[Event]:
        return [e for e in self.events if e.kind == kind]

    async def wait_for(self, kind: str, count: int = 1) -> list[Event]:
        async def _poll() -> list[Event]:
            while len(self.of_kind(kind)) < count:
                await asyncio.sleep(0.01)
            return self.of_kind(kind)

        return await asyncio.wait_for(_poll(), DEFAULT_TIMEOUT)


@dataclass
class Loop:
    bus: EventBus
    store: StateStore
    repo: SandboxRepo
    orchestrator: Orchestrator
    controller: MergeController
    probe: EventProbe
    workers: list[Worker] = field(default_factory=list)

    async def finish(self) -> None:
        """Wait for the task to complete, then quiesce everything."""
        await self.probe.wait_for("TaskCompleted")
        await self.orchestrator.wait_for_workers()
        await self.controller.stop()


@pytest.fixture
def build_loop(tmp_path):
    """Factory: assemble the whole loop around a seeded sandbox."""
    loops: list[Loop] = []

    def _build(
        issues,
        runner: AgentRunner,
        tester: Tester | None = None,
        mode: Mode = Mode.AUTONOMOUS,
        worker_count: int = 2,
        seed_files: dict[str, str] | None = None,
    ) -> Loop:
        project = tmp_path / "project"
        project.mkdir(exist_ok=True)
        for name, content in (seed_files or {"README.md": "demo\n"}).items():
            (project / name).write_text(content)
        repo = SandboxRepo.create(seed_dir=project)

        bus = EventBus()
        store = StateStore()
        bus.subscribe(store.record)
        probe = EventProbe(bus)

        missing = tmp_path / "no-agents"
        agents = discover_agents(
            user_apron_dir=missing,
            claude_user_dir=missing,
            claude_project_dir=missing,
            project_apron_dir=missing,
        )
        worker_def = resolve_for_role(agents, AgentRole.WORKER)
        workers = [
            Worker(f"worker-{n}", worker_def, repo, runner, bus)
            for n in range(1, worker_count + 1)
        ]
        graph = IssueGraph()
        orchestrator = Orchestrator(
            definition=resolve_for_role(agents, AgentRole.ORCHESTRATOR),
            planner=StaticPlanner(issues),
            graph=graph,
            assigner=Assigner(graph, workers),
            bus=bus,
        )
        controller = MergeController(repo, tester or CommandTester(None), bus, mode)
        controller.start()
        loop = Loop(bus, store, repo, orchestrator, controller, probe, workers)
        loops.append(loop)
        return loop

    yield _build

    for loop in loops:
        loop.repo.destroy()
