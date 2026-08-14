"""Tests for the event vocabulary and its serialization round-trip."""

from apron.bus.events import (
    IssueQueued,
    MergeSucceeded,
    TaskPlanned,
    event_from_dict,
)


def test_to_dict_includes_kind_and_identity():
    event = IssueQueued(issue_id="i1", task_id="t1", title="Add parser", description="...")
    payload = event.to_dict()
    assert payload["kind"] == "IssueQueued"
    assert payload["issue_id"] == "i1"
    assert payload["event_id"] == event.event_id
    assert payload["timestamp"] == event.timestamp


def test_round_trip_restores_the_same_event():
    event = MergeSucceeded(issue_id="i1", branch="issue/i1")
    assert event_from_dict(event.to_dict()) == event


def test_round_trip_restores_tuple_fields_from_json_lists():
    event = TaskPlanned(task_id="t1", issue_ids=("i1", "i2"))
    payload = event.to_dict()
    payload["issue_ids"] = list(payload["issue_ids"])  # what JSON would give back
    restored = event_from_dict(payload)
    assert restored == event
    assert restored.issue_ids == ("i1", "i2")


def test_unknown_kind_is_rejected():
    try:
        event_from_dict({"kind": "NoSuchEvent"})
    except ValueError as error:
        assert "NoSuchEvent" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_events_are_immutable():
    event = IssueQueued(issue_id="i1", task_id="t1", title="x", description="y")
    try:
        event.issue_id = "i2"  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("expected frozen dataclass to reject assignment")
