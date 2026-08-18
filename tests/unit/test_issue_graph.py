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


def test_revise_folds_feedback_into_the_description_without_stacking():
    from apron.orchestrator.issue_graph import IssueGraph
    from apron.orchestrator.planner import PlannedIssue

    graph = IssueGraph()
    graph.add(PlannedIssue("i1", "Add parser", "Parse the config file."))

    graph.revise("i1", "Feedback: handle empty files.")
    [issue] = graph.ready()
    assert issue.description == "Parse the config file.\n\nFeedback: handle empty files."

    # A second send-back replaces the old feedback instead of stacking it.
    graph.revise("i1", "Feedback: the parser crashes on comments.")
    [issue] = graph.ready()
    assert "empty files" not in issue.description
    assert issue.description.startswith("Parse the config file.")
    assert issue.description.endswith("the parser crashes on comments.")

    graph.revise("i1", "")
    [issue] = graph.ready()
    assert issue.description == "Parse the config file."
