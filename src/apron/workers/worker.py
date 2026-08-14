"""The worker loop: claim issue -> load agent definition -> branch -> code ->
open review. Workers never merge their own work."""

from __future__ import annotations

from apron.agents.definition import AgentDefinition
from apron.bus.bus import EventBus
from apron.bus.events import IssueClaimed, ReviewOpened, WorkerStarted, WorkStarted
from apron.orchestrator.planner import PlannedIssue
from apron.sandbox.clone import WorkerClone
from apron.sandbox.git_ops import GitError
from apron.sandbox.repo import SandboxRepo
from apron.workers.runner import AgentRunner


class Worker:
    """One agent working one issue at a time in its own sandbox clone."""

    def __init__(
        self,
        worker_id: str,
        definition: AgentDefinition,
        repo: SandboxRepo,
        runner: AgentRunner,
        bus: EventBus,
    ) -> None:
        self.worker_id = worker_id
        self.definition = definition
        self.repo = repo
        self.runner = runner
        self.bus = bus
        self._busy = False
        self._clone: WorkerClone | None = None

    @property
    def idle(self) -> bool:
        return not self._busy

    def reserve(self) -> None:
        """Claim this worker synchronously, before its work task runs."""
        if self._busy:
            raise RuntimeError(f"worker {self.worker_id} is already reserved")
        self._busy = True

    async def start(self) -> None:
        await self.bus.publish(
            WorkerStarted(worker_id=self.worker_id, agent_name=self.definition.name)
        )

    async def work_on(self, issue: PlannedIssue) -> None:
        """Work one issue on its own branch and open a review."""
        self._busy = True
        try:
            await self.bus.publish(
                IssueClaimed(issue_id=issue.issue_id, worker_id=self.worker_id)
            )
            clone = self._ensure_clone()
            branch = f"issue/{issue.issue_id}"
            self._start_branch(clone, branch)
            await self.bus.publish(
                WorkStarted(
                    issue_id=issue.issue_id, worker_id=self.worker_id, branch=branch
                )
            )

            result = await self.runner.run_issue(self.definition, issue, clone.path)
            clone.commit_all(issue.title)
            clone.push_branch(branch)
            await self.bus.publish(
                ReviewOpened(
                    issue_id=issue.issue_id,
                    worker_id=self.worker_id,
                    branch=branch,
                    summary=result.summary,
                )
            )
        finally:
            self._busy = False

    def _ensure_clone(self) -> WorkerClone:
        if self._clone is None:
            self._clone = WorkerClone.create(self.repo, self.worker_id)
        return self._clone

    def _start_branch(self, clone: WorkerClone, branch: str) -> None:
        """Branch off up-to-date main; reuse the branch on a rework pass."""
        clone.update_main()
        try:
            clone.create_branch(branch)
        except GitError:
            clone.switch(branch)
