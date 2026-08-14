"""Tracks dependency edges between issues so nothing is assigned before its
prerequisites are merged."""

from __future__ import annotations

from apron.orchestrator.planner import PlannedIssue


class IssueGraph:
    """The orchestrator's ledger of issues: pending, active, or merged."""

    def __init__(self) -> None:
        self._issues: dict[str, PlannedIssue] = {}
        self._active: set[str] = set()
        self._merged: set[str] = set()

    def add(self, issue: PlannedIssue) -> None:
        if issue.issue_id in self._issues:
            raise ValueError(f"issue {issue.issue_id!r} already tracked")
        self._issues[issue.issue_id] = issue

    def ready(self) -> list[PlannedIssue]:
        """Issues whose prerequisites are all merged, in insertion order."""
        return [
            issue
            for issue_id, issue in self._issues.items()
            if issue_id not in self._active
            and issue_id not in self._merged
            and all(dep in self._merged for dep in issue.depends_on)
        ]

    def mark_active(self, issue_id: str) -> None:
        """An issue was handed to a worker (or re-entered rework)."""
        self._require(issue_id)
        self._active.add(issue_id)

    def release(self, issue_id: str) -> None:
        """The issue is workable again (e.g. its worker gave it back)."""
        self._require(issue_id)
        self._active.discard(issue_id)

    def mark_merged(self, issue_id: str) -> None:
        self._require(issue_id)
        self._active.discard(issue_id)
        self._merged.add(issue_id)

    def all_merged(self) -> bool:
        return set(self._issues) == self._merged

    def __contains__(self, issue_id: str) -> bool:
        return issue_id in self._issues

    def _require(self, issue_id: str) -> None:
        if issue_id not in self._issues:
            raise KeyError(f"unknown issue {issue_id!r}")
