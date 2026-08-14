"""Sequences merges into sandbox main, one branch at a time.

Supervised and autonomous mode share one machinery: a review must be
approved before its branch may merge. The only difference is who publishes
``ReviewApproved`` — a human through the dashboard, or this controller
itself the moment a review opens.

Dependency order is upheld upstream: the orchestrator never assigns an
issue before its prerequisites are merged, so branches arrive here already
in a mergeable order."""

from __future__ import annotations

import asyncio
import logging

from apron.bus.bus import EventBus
from apron.bus.events import (
    ChangesRequested,
    MergeConflictDetected,
    MergeStarted,
    MergeSucceeded,
    ReviewApproved,
    ReviewOpened,
    TestsFailed,
    TestsPassed,
)
from apron.config import Mode
from apron.merge.conflict import abort_merge, conflicted_files
from apron.merge.tester import Tester
from apron.sandbox.clone import WorkerClone
from apron.sandbox.repo import SandboxRepo

log = logging.getLogger(__name__)


class MergeController:
    """Owns sandbox main: merges approved branches serially, testing each."""

    def __init__(
        self,
        repo: SandboxRepo,
        tester: Tester,
        bus: EventBus,
        mode: Mode = Mode.SUPERVISED,
    ) -> None:
        self.repo = repo
        self.tester = tester
        self.bus = bus
        self.mode = mode
        self._open_reviews: dict[str, str] = {}  # issue_id -> branch
        self._queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self._runner_task: asyncio.Task | None = None
        self._clone: WorkerClone | None = None
        bus.subscribe(self._on_review_opened, ReviewOpened)
        bus.subscribe(self._on_review_approved, ReviewApproved)
        bus.subscribe(self._on_changes_requested, ChangesRequested)

    # --- gate ---------------------------------------------------------------

    async def _on_review_opened(self, event: ReviewOpened) -> None:
        self._open_reviews[event.issue_id] = event.branch
        if self.mode is Mode.AUTONOMOUS:
            await self.bus.publish(ReviewApproved(issue_id=event.issue_id))

    async def _on_review_approved(self, event: ReviewApproved) -> None:
        branch = self._open_reviews.pop(event.issue_id, None)
        if branch is None:
            log.warning("approval for unknown review %s ignored", event.issue_id)
            return
        self._queue.put_nowait((event.issue_id, branch))

    async def _on_changes_requested(self, event: ChangesRequested) -> None:
        # The review is dead; the worker will open a fresh one after rework.
        self._open_reviews.pop(event.issue_id, None)

    # --- merge loop ---------------------------------------------------------

    def start(self) -> None:
        """Begin consuming the merge queue, one branch at a time."""
        if self._runner_task is None:
            self._runner_task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._runner_task is not None:
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
            self._runner_task = None

    async def _run(self) -> None:
        while True:
            issue_id, branch = await self._queue.get()
            try:
                await self._merge_one(issue_id, branch)
            except Exception:
                log.exception("merge of %s failed unexpectedly", branch)
            finally:
                self._queue.task_done()

    async def _merge_one(self, issue_id: str, branch: str) -> None:
        await self.bus.publish(MergeStarted(issue_id=issue_id, branch=branch))
        clone = self._ensure_clone()
        clone.update_main()

        merge = clone.run(
            "merge", "--no-ff", f"origin/{branch}", "-m", f"Merge {branch}",
            check=False,
        )
        if merge.returncode != 0:
            collided = conflicted_files(clone)
            abort_merge(clone)
            await self.bus.publish(
                MergeConflictDetected(
                    issue_id=issue_id, branch=branch, detail=", ".join(collided)
                )
            )
            return

        report = await self.tester.run(clone.path)
        if not report.passed:
            # Undo the candidate so main stays green, then route back.
            clone.run("reset", "--hard", "origin/main")
            await self.bus.publish(
                TestsFailed(issue_id=issue_id, log_tail=report.log_tail)
            )
            return

        await self.bus.publish(TestsPassed(issue_id=issue_id))
        clone.push_branch("main")
        await self.bus.publish(MergeSucceeded(issue_id=issue_id, branch=branch))

    def _ensure_clone(self) -> WorkerClone:
        if self._clone is None:
            self._clone = WorkerClone.create(self.repo, "merge-controller")
        return self._clone
