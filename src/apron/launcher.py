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
import webbrowser

import uvicorn

from apron.agents.definition import AgentDefinition, AgentRole
from apron.agents.discovery import discover_from_settings, resolve_for_role
from apron.agents.watch import AgentWatcher
import uuid

from apron.bus.bus import EventBus
from apron.bus.events import (
    AgentDefinitionsReloaded,
    HandoffCompleted,
    ReviewOpened,
    TaskCompleted,
    TaskReceived,
)
from apron.bus.store import StateStore
from apron.config import Settings
from apron.console import ConsoleReporter
from apron.merge.controller import MergeController
from apron.merge.tester import CommandTester
from apron.orchestrator import Assigner, IssueGraph, Orchestrator
from apron.sandbox.handoff import RunLogIssue, handoff, write_run_log
from apron.sandbox.repo import SandboxRepo
from apron.server.app import build_app
from apron.server.routes import ServerContext
from apron.workers.backends import build_backend
from apron.workers.cli_runner import summarize_recent_session
from apron.workers.worker import Worker

log = logging.getLogger(__name__)



class Launcher:
    """Owns the process tree for one Apron run."""

    def __init__(self, settings: Settings, initial_task: str | None = None) -> None:
        self.settings = settings
        self._initial_task = initial_task
        self.bus = EventBus()
        if settings.db_path is not None:
            settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.store = StateStore(settings.db_path or ":memory:")
        self._store_subscription = self.bus.subscribe(self.store.record)
        self.repo: SandboxRepo | None = None
        self.workers: list[Worker] = []
        self.controller: MergeController | None = None
        self._watcher: AgentWatcher | None = None
        self._watcher_task: asyncio.Task | None = None
        self._server: uvicorn.Server | None = None
        self._server_task: asyncio.Task | None = None
        self._done = asyncio.Event()
        self.handed_off_files: list[str] = []

    # --- boot ----------------------------------------------------------------

    async def start(self) -> None:
        settings = self.settings
        self._session_context: str | None = None
        if settings.with_session_context:
            log.info("gathering context from your recent interactive session...")
            self._session_context = await summarize_recent_session(
                settings.working_dir
            )
            if self._session_context:
                log.info(
                    "session context attached (%d chars)", len(self._session_context)
                )
            else:
                log.warning(
                    "no session context found (no claude CLI, or no recent "
                    "session for this directory) — continuing without it"
                )
        self.repo = SandboxRepo.create(seed_dir=settings.working_dir)
        runner, planner, self._backend_name = build_backend(
            settings.runner,
            settings.working_dir,
            lambda: self._resolve(AgentRole.ORCHESTRATOR),
            session_context=self._session_context,
        )

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
        self.controller = MergeController(
            self.repo, CommandTester(settings.test_command), self.bus, settings.mode
        )
        graph = IssueGraph()
        self.orchestrator = Orchestrator(
            definition=self._resolve(AgentRole.ORCHESTRATOR),
            planner=planner,
            graph=graph,
            assigner=Assigner(graph, self.workers),
            bus=self.bus,
            # Supervised runs hold plans at the plan gate; reads the live
            # mode so the dashboard toggle applies to in-flight planning.
            mode_provider=lambda: self.controller.mode,
        )
        self.controller.start()
        self.bus.subscribe(self._on_task_completed, TaskCompleted)

        self._watcher = AgentWatcher(
            self._agent_directories(), self._on_agents_changed
        )
        self._watcher_task = asyncio.create_task(self._watcher.run())
        await self._start_server()
        log.info(
            "apron ready: mode=%s, runner=%s, %d workers, dashboard on %s",
            settings.mode, self._backend_name, len(self.workers),
            settings.dashboard_url,
        )
        if settings.open_browser:
            webbrowser.open(settings.dashboard_url)
        if self._initial_task:
            task_id = uuid.uuid4().hex[:8]
            await self.bus.publish(
                TaskReceived(task_id=task_id, prompt=self._initial_task)
            )
            log.info("task %s dispatched from the command line", task_id)

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
        self._server_task = asyncio.create_task(self._server.serve())
        while not self._server.started and not self._server_task.done():
            await asyncio.sleep(0.05)
        if self._server_task.done():
            self._server_task.result()  # surface the startup error

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
        log_path = write_run_log(
            self.settings.working_dir,
            task_prompt=self._task_prompt(event.task_id),
            issues=self._run_log_issues(),
            files=self.handed_off_files,
        )
        log.info("run log written to %s", log_path)
        await self.bus.publish(
            HandoffCompleted(
                task_id=event.task_id,
                target_dir=str(self.settings.working_dir),
                files=tuple(self.handed_off_files),
            )
        )
        log.info(
            "task complete: %d file(s) copied into %s",
            len(self.handed_off_files), self.settings.working_dir,
        )
        self._done.set()

    def _task_prompt(self, task_id: str) -> str:
        for _, event in self.store.events_since():
            if isinstance(event, TaskReceived) and event.task_id == task_id:
                return event.prompt
        return ""

    def _run_log_issues(self) -> list[RunLogIssue]:
        summaries: dict[str, str] = {}
        for _, event in self.store.events_since():
            if isinstance(event, ReviewOpened):
                summaries[event.issue_id] = event.summary
        return [
            RunLogIssue(
                issue_id=issue.issue_id,
                title=issue.title,
                summary=summaries.get(issue.issue_id, ""),
            )
            for issue in self.store.issues()
        ]

    async def wait(self) -> None:
        """Block until the task is handed off (or forever, if none arrives)."""
        await self._done.wait()

    async def stop(self) -> None:
        if self._watcher_task:
            self._watcher.stop()
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
        if self._server_task:
            # Ask uvicorn to exit and let its lifespan finish; cancelling the
            # task instead interrupts the shutdown mid-await and uvicorn logs
            # a CancelledError traceback.
            self._server.should_exit = True
            try:
                await asyncio.wait_for(self._server_task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._server_task.cancel()
        if self.controller:
            await self.controller.stop()
        if self.repo:
            self.repo.destroy()
        self._store_subscription.unsubscribe()
        self.store.close()
        log.info("apron stopped")


def launch(settings: Settings, initial_task: str | None = None) -> None:
    """Run one full Apron session, blocking until it finishes."""

    async def _run() -> None:
        launcher = Launcher(settings, initial_task=initial_task)
        # The terminal that dispatched the run narrates it, like the dashboard.
        reporter = ConsoleReporter(dashboard_url=settings.dashboard_url)
        reporter.attach(launcher.bus)
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
