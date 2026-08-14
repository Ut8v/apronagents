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
