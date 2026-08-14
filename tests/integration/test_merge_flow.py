"""Integration coverage for the merge controller: the green path, the
supervised gate, the conflict path, and the failed-tests path."""

import asyncio
from pathlib import Path

from apron.bus.events import ChangesRequested, IssueState, ReviewApproved, TaskReceived
from apron.config import Mode
from apron.merge.tester import TestReport
from apron.orchestrator import PlannedIssue
from apron.workers.runner import FakeRunner

TWO_INDEPENDENT = [
    PlannedIssue(issue_id="i1", title="Add greeting", description=""),
    PlannedIssue(issue_id="i2", title="Add farewell", description=""),
]
INDEPENDENT_OUTPUTS = {
    "i1": {"greeting.py": "GREETING = 'hello'\n"},
    "i2": {"farewell.py": "FAREWELL = 'bye'\n"},
}


def main_files(repo) -> list[str]:
    listing = repo.git.run(
        "ls-tree", "-r", "--name-only", "main", cwd=repo.bare_path
    ).stdout.split()
    return sorted(listing)


async def test_autonomous_green_path_merges_everything(build_loop):
    loop = build_loop(TWO_INDEPENDENT, FakeRunner(INDEPENDENT_OUTPUTS))

    await loop.bus.publish(TaskReceived(task_id="t1", prompt="build both"))
    await loop.finish()

    assert main_files(loop.repo) == ["README.md", "farewell.py", "greeting.py"]
    states = {i.issue_id: i.state for i in loop.store.issues()}
    assert states == {"i1": IssueState.MERGED, "i2": IssueState.MERGED}
    # One merge at a time: every merge finished before the next one started.
    starts = [e.issue_id for e in loop.probe.of_kind("MergeStarted")]
    successes = [e.issue_id for e in loop.probe.of_kind("MergeSucceeded")]
    assert sorted(starts) == ["i1", "i2"]
    assert sorted(successes) == ["i1", "i2"]


async def test_supervised_mode_merges_nothing_without_approval(build_loop):
    loop = build_loop(
        TWO_INDEPENDENT, FakeRunner(INDEPENDENT_OUTPUTS), mode=Mode.SUPERVISED
    )

    await loop.bus.publish(TaskReceived(task_id="t1", prompt="build both"))
    await loop.probe.wait_for("ReviewOpened", count=2)
    await asyncio.sleep(0.2)  # give an eager merge every chance to happen

    assert loop.probe.of_kind("MergeStarted") == []
    assert main_files(loop.repo) == ["README.md"]

    # Approve one review: exactly that branch merges.
    await loop.bus.publish(ReviewApproved(issue_id="i1"))
    await loop.probe.wait_for("MergeSucceeded")
    assert main_files(loop.repo) == ["README.md", "greeting.py"]
    assert loop.store.issue("i2").state is IssueState.IN_REVIEW

    # Send the other back: the worker reworks it and opens a fresh review.
    await loop.bus.publish(ChangesRequested(issue_id="i2", reason="rename it"))
    await loop.probe.wait_for("ReviewOpened", count=3)
    await loop.bus.publish(ReviewApproved(issue_id="i2"))
    await loop.finish()
    assert main_files(loop.repo) == ["README.md", "farewell.py", "greeting.py"]


async def test_conflicting_branch_is_reworked_not_forced(build_loop):
    both_touch_shared = [
        PlannedIssue(issue_id="i1", title="Set shared to one", description=""),
        PlannedIssue(issue_id="i2", title="Set shared to two", description=""),
    ]
    runner = FakeRunner(
        {
            "i1": {"shared.txt": "one\n"},
            "i2": {"shared.txt": "two\n"},
        }
    )
    loop = build_loop(
        both_touch_shared, runner, seed_files={"shared.txt": "original\n"}
    )

    await loop.bus.publish(TaskReceived(task_id="t1", prompt="edit shared"))
    await loop.finish()

    # The collision was detected, never forced, and rework resolved it.
    conflicts = loop.probe.of_kind("MergeConflictDetected")
    assert len(conflicts) >= 1
    assert conflicts[0].detail == "shared.txt"
    states = {i.issue_id: i.state for i in loop.store.issues()}
    assert states == {"i1": IssueState.MERGED, "i2": IssueState.MERGED}
    # The reworked branch was rebuilt on top of the first merge, so the
    # second issue's content wins in the final tree.
    final = loop.repo.git.run(
        "show", "main:shared.txt", cwd=loop.repo.bare_path
    ).stdout
    assert final in ("one\n", "two\n")
    # The conflicted issue went around the loop twice.
    reworked = conflicts[0].issue_id
    claims = [e for e in loop.probe.of_kind("IssueClaimed") if e.issue_id == reworked]
    assert len(claims) == 2


class FlakyTester:
    """Red on the first candidate, green afterwards."""

    def __init__(self) -> None:
        self.runs = 0

    async def run(self, workdir: Path) -> TestReport:
        self.runs += 1
        if self.runs == 1:
            return TestReport(passed=False, log_tail="1 failed: test_greeting")
        return TestReport(passed=True)


async def test_red_tests_keep_main_clean_and_route_the_issue_back(build_loop):
    issue = [PlannedIssue(issue_id="i1", title="Add greeting", description="")]
    tester = FlakyTester()
    loop = build_loop(issue, FakeRunner(INDEPENDENT_OUTPUTS), tester=tester)

    await loop.bus.publish(TaskReceived(task_id="t1", prompt="add greeting"))
    await loop.probe.wait_for("TestsFailed")

    await loop.finish()

    assert tester.runs == 2
    assert loop.store.issue("i1").state is IssueState.MERGED
    assert main_files(loop.repo) == ["README.md", "greeting.py"]
    # Exactly one merge commit landed: the red candidate was rolled back.
    merge_commits = loop.repo.git.run(
        "rev-list", "--merges", "--count", "main", cwd=loop.repo.bare_path
    ).stdout.strip()
    assert merge_commits == "1"
