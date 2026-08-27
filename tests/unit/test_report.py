"""Tests for the markdown run report."""

import pytest

from apron.bus.events import (
    ChangesRequested,
    HandoffCompleted,
    IssueClaimed,
    IssueQueued,
    MergeSucceeded,
    PlanProposed,
    ReviewApproved,
    ReviewOpened,
    TaskReceived,
)
from apron.report import run_report


def test_report_tells_the_whole_story():
    events = [
        TaskReceived(task_id="t1", prompt="Add rate limiting", timestamp=100.0),
        PlanProposed(task_id="t1", issues=()),
        IssueQueued(issue_id="core", task_id="t1", title="Limiter core", description=""),
        IssueQueued(
            issue_id="wiring", task_id="t1", title="Wire it in",
            description="", depends_on=("core",),
        ),
        IssueClaimed(issue_id="core", worker_id="worker-1"),
        ReviewOpened(
            issue_id="core", worker_id="worker-1", branch="issue/core",
            summary="Added a token bucket.",
        ),
        ChangesRequested(
            issue_id="core", reason="handle bursts",
            annotations=({"path": "limiter.py", "line": 9, "note": "guard zero"},),
        ),
        ReviewOpened(issue_id="core", worker_id="worker-1", branch="issue/core"),
        ReviewApproved(issue_id="core"),
        MergeSucceeded(issue_id="core", branch="issue/core"),
        HandoffCompleted(
            task_id="t1", target_dir="/proj", files=("limiter.py",), timestamp=400.0,
        ),
    ]
    report = run_report(events)

    assert "# Apron run t1" in report
    assert "**Task:** Add rate limiting" in report
    assert "(5m 0s)" in report and "completed ✓" in report
    assert "_Held at the plan gate and human-approved before dispatch._" in report
    assert "**wiring** — Wire it in _(needs core)_" in report
    assert "## core — merged ✓" in report
    assert "claimed by worker-1" in report
    assert "“Added a token bucket.”" in report
    assert "sent back: handle bursts (+1 line note(s))" in report
    assert "`limiter.py:9` — guard zero" in report
    assert "## wiring — not merged" in report
    assert "1 file(s) copied into `/proj`" in report
    assert "The real remote was never touched." in report


def test_report_requires_a_run():
    with pytest.raises(ValueError):
        run_report([ReviewApproved(issue_id="x")])
