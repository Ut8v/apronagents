"""Tests for plan payload normalization."""

import pytest

from apron.orchestrator.planner import PlanError, issues_from_payload


def test_normalizes_ids_and_dependencies():
    issues = issues_from_payload(
        {
            "issues": [
                {"id": "Add Auth!", "title": "Add auth", "description": "d"},
                {"title": "Wire UI", "description": "d", "depends_on": ["Add Auth!"]},
            ]
        }
    )
    assert [i.issue_id for i in issues] == ["add-auth", "wire-ui"]
    assert issues[1].depends_on == ("add-auth",)


def test_duplicate_ids_are_disambiguated():
    issues = issues_from_payload(
        {
            "issues": [
                {"id": "same", "title": "A", "description": ""},
                {"id": "same", "title": "B", "description": ""},
            ]
        }
    )
    assert len({i.issue_id for i in issues}) == 2


def test_empty_and_invalid_plans_are_rejected():
    with pytest.raises(PlanError, match="no issues"):
        issues_from_payload({"issues": []})
    with pytest.raises(PlanError, match="no title"):
        issues_from_payload({"issues": [{"description": "d"}]})
    with pytest.raises(PlanError, match="unknown issue"):
        issues_from_payload(
            {"issues": [{"title": "A", "description": "", "depends_on": ["ghost"]}]}
        )


async def test_static_planner_narrates_before_returning():
    from apron.orchestrator.planner import PlannedIssue, StaticPlanner

    planner = StaticPlanner(
        [PlannedIssue("i1", "One", "")],
        narration=("reading the project…", "splitting…"),
    )
    notes: list[str] = []

    async def on_progress(note: str) -> None:
        notes.append(note)

    issues = await planner.plan("t1", "do the thing", on_progress=on_progress)
    assert [i.issue_id for i in issues] == ["i1"]
    assert notes == ["reading the project…", "splitting…"]
