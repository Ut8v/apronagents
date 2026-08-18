"""Tracks dependency edges between issues so nothing is assigned before its
prerequisites are merged."""

from __future__ import annotations

from dataclasses import replace

from apron.orchestrator.planner import PlannedIssue


class IssueGraph:
    """The orchestrator's ledger of issues: pending, active, or merged."""

    def __init__(self) -> None:
        self._issues: dict[str, PlannedIssue] = {}
        self._active: set[str] = set()
        self._merged: set[str] = set()
        self._original_descriptions: dict[str, str] = {}

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

    def revise(self, issue_id: str, feedback: str) -> None:
        """Attach rework feedback to the issue for its next pass.

        The feedback is folded into the issue's description, so whichever
        worker picks it up next sees it through the normal prompt path. Each
        revision replaces the previous feedback rather than stacking — the
        original description is kept, and only the newest feedback rides
        along with it.
        """
        self._require(issue_id)
        original = self._original_descriptions.setdefault(
            issue_id, self._issues[issue_id].description
        )
        description = f"{original}\n\n{feedback}".strip() if feedback else original
        self._issues[issue_id] = replace(
            self._issues[issue_id], description=description
        )

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
