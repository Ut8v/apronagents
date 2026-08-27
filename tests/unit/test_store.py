"""Tests for the SQLite state store: journal, projection, and catch-up."""

from apron.bus.events import (
    ChangesRequested,
    IssueClaimed,
    IssueQueued,
    IssueState,
    MergeConflictDetected,
    MergeStarted,
    MergeSucceeded,
    ReviewApproved,
    ReviewOpened,
    TestsFailed,
    WorkStarted,
)
from apron.bus.store import StateStore


def make_queued(issue_id="i1", depends_on=()):
    return IssueQueued(
        issue_id=issue_id,
        task_id="t1",
        title=f"Issue {issue_id}",
        description="do the thing",
        depends_on=depends_on,
    )


def test_queued_issue_appears_in_projection():
    store = StateStore()
    store.record(make_queued(depends_on=("i0",)))

    issue = store.issue("i1")
    assert issue is not None
    assert issue.state is IssueState.QUEUED
    assert issue.title == "Issue i1"
    assert issue.depends_on == ("i0",)
    assert issue.worker_id is None
    assert issue.branch is None


def test_full_lifecycle_reaches_merged():
    store = StateStore()
    store.record(make_queued())
    store.record(IssueClaimed(issue_id="i1", worker_id="w1"))
    store.record(WorkStarted(issue_id="i1", worker_id="w1", branch="issue/i1"))
    store.record(ReviewOpened(issue_id="i1", worker_id="w1", branch="issue/i1"))
    store.record(ReviewApproved(issue_id="i1"))
    store.record(MergeStarted(issue_id="i1", branch="issue/i1"))
    store.record(MergeSucceeded(issue_id="i1", branch="issue/i1"))

    issue = store.issue("i1")
    assert issue.state is IssueState.MERGED
    assert issue.worker_id == "w1"
    assert issue.branch == "issue/i1"


def test_send_back_paths_return_issue_to_changes_requested():
    store = StateStore()
    store.record(make_queued())
    store.record(ReviewOpened(issue_id="i1", worker_id="w1", branch="issue/i1"))
    store.record(ChangesRequested(issue_id="i1", reason="too broad"))
    assert store.issue("i1").state is IssueState.CHANGES_REQUESTED

    store.record(MergeConflictDetected(issue_id="i1", branch="issue/i1"))
    assert store.issue("i1").state is IssueState.CHANGES_REQUESTED


def test_failed_tests_are_visible():
    store = StateStore()
    store.record(make_queued())
    store.record(MergeStarted(issue_id="i1", branch="issue/i1"))
    store.record(TestsFailed(issue_id="i1", log_tail="1 failed"))
    assert store.issue("i1").state is IssueState.TEST_FAILED


def test_merged_is_terminal_even_for_stray_late_events():
    store = StateStore()
    store.record(make_queued())
    store.record(MergeStarted(issue_id="i1", branch="issue/i1"))
    store.record(MergeSucceeded(issue_id="i1", branch="issue/i1"))

    # A duplicate approval or send-back arriving after the merge must not
    # walk the projection backwards.
    store.record(ReviewApproved(issue_id="i1"))
    assert store.issue("i1").state is IssueState.MERGED
    store.record(ChangesRequested(issue_id="i1", reason="too late"))
    assert store.issue("i1").state is IssueState.MERGED


def test_events_since_returns_journal_in_order():
    store = StateStore()
    first = make_queued("i1")
    second = IssueClaimed(issue_id="i1", worker_id="w1")
    store.record(first)
    store.record(second)

    entries = store.events_since()
    assert [event for _, event in entries] == [first, second]

    last_seq = entries[0][0]
    assert [event for _, event in store.events_since(last_seq)] == [second]


def test_recording_the_same_event_twice_is_idempotent():
    store = StateStore()
    event = make_queued()
    store.record(event)
    store.record(event)
    assert len(store.events_since()) == 1
    assert len(store.issues()) == 1


def test_state_survives_reopening_the_database(tmp_path):
    db_path = tmp_path / "state.sqlite"
    store = StateStore(db_path)
    store.record(make_queued())
    store.record(IssueClaimed(issue_id="i1", worker_id="w1"))
    store.close()

    reopened = StateStore(db_path)
    assert reopened.issue("i1").state is IssueState.CLAIMED
    assert len(reopened.events_since()) == 2
    reopened.close()


def test_progress_updates_last_activity_but_never_a_merged_issue():
    from apron.bus.events import ProgressReported

    store = StateStore()
    store.record(make_queued())
    store.record(
        ProgressReported(issue_id="i1", worker_id="w1", note="Edit tz.py")
    )
    assert store.issue("i1").last_activity == "Edit tz.py"

    store.record(MergeStarted(issue_id="i1", branch="issue/i1"))
    store.record(MergeSucceeded(issue_id="i1", branch="issue/i1"))
    store.record(
        ProgressReported(issue_id="i1", worker_id="w1", note="stray late note")
    )
    assert store.issue("i1").last_activity == "Edit tz.py"


def test_planning_tracks_notes_for_the_current_unplanned_task():
    from apron.bus.events import PlanningProgress, TaskPlanned, TaskReceived

    store = StateStore()
    assert store.planning() == {"active": False, "notes": []}

    store.record(TaskReceived(task_id="t1", prompt="add dark mode"))
    store.record(PlanningProgress(task_id="t1", note="reading the project…"))
    store.record(PlanningProgress(task_id="t1", note="splitting into issues…"))
    assert store.planning() == {
        "active": True,
        "notes": ["reading the project…", "splitting into issues…"],
    }

    store.record(TaskPlanned(task_id="t1", issue_ids=("a",)))
    assert store.planning() == {"active": False, "notes": []}


def test_pending_plan_tracks_the_gate():
    from apron.bus.events import PlanApproved, PlanProposed, TaskReceived

    store = StateStore()
    assert store.pending_plan() is None

    store.record(TaskReceived(task_id="t1", prompt="p"))
    store.record(
        PlanProposed(
            task_id="t1",
            issues=({"id": "a", "title": "A", "description": "", "depends_on": []},),
        )
    )
    plan = store.pending_plan()
    assert plan is not None and plan["task_id"] == "t1"
    assert plan["issues"][0]["id"] == "a"
    # A proposal also ends the "planner is thinking" phase.
    assert store.planning() == {"active": False, "notes": []}

    store.record(PlanApproved(task_id="t1", issues=()))
    assert store.pending_plan() is None


def _record_full_run(store, task_id="t1", issue_id="i1"):
    from apron.bus.events import (
        HandoffCompleted,
        MergeSucceeded,
        TaskReceived,
    )

    store.record(TaskReceived(task_id=task_id, prompt=f"do {task_id}"))
    store.record(
        IssueQueued(issue_id=issue_id, task_id=task_id, title="T", description="")
    )
    store.record(IssueClaimed(issue_id=issue_id, worker_id="w1"))
    store.record(WorkStarted(issue_id=issue_id, worker_id="w1", branch=f"issue/{issue_id}"))
    store.record(ReviewOpened(issue_id=issue_id, worker_id="w1", branch=f"issue/{issue_id}"))
    store.record(ReviewApproved(issue_id=issue_id))
    store.record(MergeStarted(issue_id=issue_id, branch=f"issue/{issue_id}"))
    store.record(MergeSucceeded(issue_id=issue_id, branch=f"issue/{issue_id}"))
    store.record(
        HandoffCompleted(task_id=task_id, target_dir="/p", files=("a.py", "b.md"))
    )


def test_runs_summarize_each_task_newest_first():
    from apron.bus.events import TaskReceived

    store = StateStore()
    _record_full_run(store, task_id="t1", issue_id="i1")
    store.record(TaskReceived(task_id="t2", prompt="do t2"))

    runs = store.runs()
    assert [r["task_id"] for r in runs] == ["t2", "t1"]
    assert runs[0]["status"] == "in flight" and runs[0]["finished_at"] is None
    done = runs[1]
    assert done["status"] == "completed"
    assert (done["issues"], done["merged"], done["files"]) == (1, 1, 2)
    assert done["finished_at"] is not None


def test_task_events_collect_a_runs_full_story():
    store = StateStore()
    _record_full_run(store, task_id="t1", issue_id="i1")
    _record_full_run(store, task_id="t2", issue_id="i2")  # unrelated run

    kinds = [e.kind for e in store.task_events("t1")]
    assert kinds == [
        "TaskReceived", "IssueQueued", "IssueClaimed", "WorkStarted",
        "ReviewOpened", "ReviewApproved", "MergeStarted", "MergeSucceeded",
        "HandoffCompleted",
    ]
    assert all(
        getattr(e, "issue_id", "i1") == "i1" for e in store.task_events("t1")
    )
