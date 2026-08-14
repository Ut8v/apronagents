"""Tests for dependency tracking in the issue graph."""

import pytest

from apron.orchestrator.issue_graph import IssueGraph
from apron.orchestrator.planner import PlannedIssue


def issue(issue_id: str, *deps: str) -> PlannedIssue:
    return PlannedIssue(
        issue_id=issue_id, title=issue_id, description="", depends_on=tuple(deps)
    )


def test_independent_issues_are_ready_in_insertion_order():
    graph = IssueGraph()
    graph.add(issue("a"))
    graph.add(issue("b"))
    assert [i.issue_id for i in graph.ready()] == ["a", "b"]


def test_an_issue_waits_for_its_prerequisites():
    graph = IssueGraph()
    graph.add(issue("base"))
    graph.add(issue("dependent", "base"))
    assert [i.issue_id for i in graph.ready()] == ["base"]

    graph.mark_active("base")
    graph.mark_merged("base")
    assert [i.issue_id for i in graph.ready()] == ["dependent"]


def test_active_issues_leave_the_ready_pool_until_released():
    graph = IssueGraph()
    graph.add(issue("a"))
    graph.mark_active("a")
    assert graph.ready() == []
    graph.release("a")
    assert [i.issue_id for i in graph.ready()] == ["a"]


def test_all_merged_only_when_everything_is():
    graph = IssueGraph()
    graph.add(issue("a"))
    graph.add(issue("b"))
    graph.mark_merged("a")
    assert not graph.all_merged()
    graph.mark_merged("b")
    assert graph.all_merged()


def test_duplicate_and_unknown_ids_are_rejected():
    graph = IssueGraph()
    graph.add(issue("a"))
    with pytest.raises(ValueError):
        graph.add(issue("a"))
    with pytest.raises(KeyError):
        graph.mark_active("ghost")
