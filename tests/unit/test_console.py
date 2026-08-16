"""Tests for the terminal renderer of bus events."""

import io

from apron.bus.bus import EventBus
from apron.bus.events import (
    HandoffCompleted,
    IssueQueued,
    MergeConflictDetected,
    MergeSucceeded,
    ProgressReported,
    ReviewOpened,
    TaskPlanned,
    TaskReceived,
    TestsFailed,
    WorkStarted,
)
from apron.cli import state_changes
from apron.console import ConsoleReporter


def reporter_and_output():
    out = io.StringIO()
    return ConsoleReporter(dashboard_url="http://x:1", out=out, color=False), out


async def test_narrates_the_lifecycle_and_skips_noise():
    reporter, out = reporter_and_output()
    bus = EventBus()
    reporter.attach(bus)

    await bus.publish(TaskReceived(task_id="t1", prompt="add dark mode"))
    await bus.publish(TaskPlanned(task_id="t1", issue_ids=("a", "b")))
    await bus.publish(IssueQueued(issue_id="a", task_id="t1", title="A", description=""))
    await bus.publish(WorkStarted(issue_id="a", worker_id="w1", branch="issue/a"))
    await bus.publish(ProgressReported(issue_id="a", worker_id="w1", note="Edit cli.py"))
    await bus.publish(ReviewOpened(issue_id="a", worker_id="w1", branch="issue/a"))
    await bus.publish(MergeSucceeded(issue_id="a", branch="issue/a"))
    await bus.publish(HandoffCompleted(task_id="t1", target_dir="/proj"))

    lines = out.getvalue().splitlines()
    assert lines == [
        "◆ task t1: add dark mode",
        "◆ planned 2 issue(s): a, b",
        "▶ w1 started a (issue/a)",
        "  ▸ w1 · Edit cli.py",
        "● review open: a by w1 — approve at http://x:1",
        "✓ merged a",
        "⇥ handoff complete → /proj",
    ]  # IssueQueued deliberately silent — TaskPlanned already covers it


def test_failures_are_loud():
    reporter, _ = reporter_and_output()
    assert "tests failed" in reporter.render(TestsFailed(issue_id="a"))
    conflict = reporter.render(
        MergeConflictDetected(issue_id="a", branch="issue/a", detail="cli.py")
    )
    assert "conflict" in conflict and "cli.py" in conflict


def test_follow_diffs_snapshots_into_lines():
    issue = {
        "issue_id": "a", "state": "in_progress",
        "worker_id": "w1", "last_activity": "Read cli.py",
    }
    lines, seen = state_changes({}, [issue])
    assert lines == ["a: in_progress"]  # first sighting: the state

    lines, seen = state_changes(seen, [dict(issue, last_activity="Edit cli.py")])
    assert lines == ["  ▸ w1 · Edit cli.py"]  # same state: the activity

    lines, seen = state_changes(seen, [dict(issue, state="in_review")])
    assert lines == ["a: in_review"]

    lines, _ = state_changes(seen, [dict(issue, state="in_review")])
    assert lines == []  # no change, no output
