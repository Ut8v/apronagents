"""Process supervisor: boots the organs, wires them to the shared bus, and
shuts them down cleanly.

One launch is one run: seed the sandbox from the working directory, boot the
orchestrator, workers, merge controller, and server, then wait. When the
task completes, the merged result is handed off into the working directory —
the single bridge to reality — and the tool stops.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import webbrowser

import uvicorn

from apron.agents.definition import AgentDefinition, AgentRole
from apron.agents.discovery import discover_from_settings, resolve_for_role
from apron.agents.watch import AgentWatcher
from apron.bus.bus import EventBus
from apron.bus.events import AgentDefinitionsReloaded, HandoffCompleted, TaskCompleted
from apron.bus.store import StateStore
from apron.config import Settings
from apron.merge.controller import MergeController
from apron.merge.tester import CommandTester
from apron.orchestrator import Assigner, IssueGraph, Orchestrator, PlannedIssue, Planner, StaticPlanner
from apron.sandbox.handoff import handoff
from apron.sandbox.repo import SandboxRepo
from apron.server.app import build_app
from apron.server.routes import ServerContext
from apron.workers.api_runner import ApiPlanner, ApiRunner
from apron.workers.cli_runner import CLAUDE_CODE_PROFILE, CODEX_PROFILE, CliAgentRunner, CliPlanner
from apron.workers.runner import AgentRunner, FakeRunner
from apron.workers.worker import Worker

log = logging.getLogger(__name__)

_DEMO_ISSUES = [
    PlannedIssue("demo-greeting", "Add a demo greeting", "Write apron-demo/greeting.txt"),
    PlannedIssue("demo-farewell", "Add a demo farewell", "Write apron-demo/farewell.txt"),
]
_DEMO_OUTPUTS = {
    "demo-greeting": {"apron-demo/greeting.txt": "Hello from an Apron demo worker.\n"},
    "demo-farewell": {"apron-demo/farewell.txt": "Goodbye from an Apron demo worker.\n"},
}


class Launcher:
    """Owns the process tree for one Apron run."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bus = EventBus()
        self.store = StateStore(settings.db_path or ":memory:")
        self._store_subscription = self.bus.subscribe(self.store.record)
        self.repo: SandboxRepo | None = None
        self.workers: list[Worker] = []
        self.controller: MergeController | None = None
        self._watcher: AgentWatcher | None = None
        self._server: uvicorn.Server | None = None
        self._tasks: list[asyncio.Task] = []
        self._done = asyncio.Event()
        self.handed_off_files: list[str] = []

    # --- boot ----------------------------------------------------------------

    async def start(self) -> None:
        settings = self.settings
        self.repo = SandboxRepo.create(seed_dir=settings.working_dir)
        runner, planner = self._build_backend()

        worker_def = self._resolve(AgentRole.WORKER)
        self.workers = [
            Worker(
                f"worker-{n}",
                worker_def,
                self.repo,
                runner,
                self.bus,
                definition_resolver=lambda: self._resolve(AgentRole.WORKER),
            )
            for n in range(1, settings.worker_count + 1)
        ]
        graph = IssueGraph()
        self.orchestrator = Orchestrator(
            definition=self._resolve(AgentRole.ORCHESTRATOR),
            planner=planner,
            graph=graph,
            assigner=Assigner(graph, self.workers),
            bus=self.bus,
        )
        self.controller = MergeController(
            self.repo, CommandTester(settings.test_command), self.bus, settings.mode
        )
        self.controller.start()
        self.bus.subscribe(self._on_task_completed, TaskCompleted)

        self._watcher = AgentWatcher(
            self._agent_directories(), self._on_agents_changed
        )
        self._tasks.append(asyncio.create_task(self._watcher.run()))
        await self._start_server()
        log.info(
            "apron ready: mode=%s, runner=%s, %d workers, dashboard on http://%s:%d",
            settings.mode, self._backend_name, len(self.workers),
            settings.host, settings.port,
        )
        if settings.open_browser:
            webbrowser.open(f"http://{settings.host}:{settings.port}")

    def _build_backend(self) -> tuple[AgentRunner, Planner]:
        choice = self.settings.runner
        if choice == "auto":
            choice = self._detect_backend()
        self._backend_name = choice

        if choice == "claude-code":
            runner = CliAgentRunner(CLAUDE_CODE_PROFILE)
        elif choice == "codex":
            runner = CliAgentRunner(CODEX_PROFILE)
        elif choice == "api":
            runner = ApiRunner()
            return runner, ApiPlanner(
                lambda: self._resolve(AgentRole.ORCHESTRATOR),
                self.settings.working_dir,
                client=runner.client,
            )
        elif choice == "demo":
            log.warning(
                "no agent backend found: running the DEMO loop (fake agents). "
                "Install the claude or codex CLI, or set ANTHROPIC_API_KEY, "
                "for real agents."
            )
            return FakeRunner(_DEMO_OUTPUTS), StaticPlanner(_DEMO_ISSUES)
        else:
            raise ValueError(f"unknown runner {choice!r}")

        return runner, CliPlanner(
            runner,
            lambda: self._resolve(AgentRole.ORCHESTRATOR),
            self.settings.working_dir,
        )

    def _detect_backend(self) -> str:
        if shutil.which(CLAUDE_CODE_PROFILE.executable):
            return "claude-code"
        if shutil.which(CODEX_PROFILE.executable):
            return "codex"
        try:
            # Resolves ANTHROPIC_API_KEY, auth tokens, or an `ant` profile;
            # raises when no credential source exists.
            ApiRunner()
            return "api"
        except Exception:
            return "demo"

    async def _start_server(self) -> None:
        ctx = ServerContext(
            self.settings, self.bus, self.store, self.repo, self.workers, self.controller
        )
        config = uvicorn.Config(
            build_app(ctx),
            host=self.settings.host,
            port=self.settings.port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)
        self._tasks.append(asyncio.create_task(self._server.serve()))
        while not self._server.started and not self._tasks[-1].done():
            await asyncio.sleep(0.05)
        if self._tasks[-1].done():
            self._tasks[-1].result()  # surface the startup error

    # --- agents hot reload ---------------------------------------------------

    def _resolve(self, role: AgentRole) -> AgentDefinition:
        return resolve_for_role(discover_from_settings(self.settings), role)

    def _agent_directories(self) -> list:
        s = self.settings
        return [
            s.user_apron_dir / "agents",
            s.user_claude_dir / "agents",
            s.project_claude_dir / "agents",
            s.project_apron_dir / "agents",
        ]

    async def _on_agents_changed(self) -> None:
        names = tuple(sorted(discover_from_settings(self.settings)))
        await self.bus.publish(AgentDefinitionsReloaded(names=names))

    # --- completion and shutdown --------------------------------------------

    async def _on_task_completed(self, event: TaskCompleted) -> None:
        self.handed_off_files = handoff(self.repo, self.settings.working_dir)
        await self.bus.publish(
            HandoffCompleted(
                task_id=event.task_id, target_dir=str(self.settings.working_dir)
            )
        )
        log.info(
            "task complete: %d file(s) copied into %s",
            len(self.handed_off_files), self.settings.working_dir,
        )
        self._done.set()

    async def wait(self) -> None:
        """Block until the task is handed off (or forever, if none arrives)."""
        await self._done.wait()

    async def stop(self) -> None:
        if self._watcher:
            self._watcher.stop()
        if self._server:
            self._server.should_exit = True
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if self.controller:
            await self.controller.stop()
        if self.repo:
            self.repo.destroy()
        self._store_subscription.unsubscribe()
        self.store.close()
        log.info("apron stopped")


def launch(settings: Settings) -> None:
    """Run one full Apron session, blocking until it finishes."""

    async def _run() -> None:
        launcher = Launcher(settings)
        try:
            await launcher.start()
            await launcher.wait()
            # Give the dashboard a moment to render the completion.
            await asyncio.sleep(1.0)
        finally:
            await launcher.stop()
        if launcher.handed_off_files:
            print(f"\nDone. {len(launcher.handed_off_files)} file(s) now in "
                  f"{settings.working_dir}:")
            for name in launcher.handed_off_files:
                print(f"  {name}")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\napron: interrupted, sandbox cleaned up")
