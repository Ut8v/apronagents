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
