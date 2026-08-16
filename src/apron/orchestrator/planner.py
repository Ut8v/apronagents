"""Turns a task into a list of issues that are as file-independent as
possible. Most merge conflicts are prevented here, before they can happen.

Planning is a pluggable protocol: the deterministic :class:`StaticPlanner`
serves tests and the demo loop, while the model-backed planners live with
their execution backends (``workers/api_runner.py`` and
``workers/claude_code_runner.py``). This module also owns the shared plan
vocabulary and the normalization from a model's raw plan payload.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol, Sequence

# Called with a short human-readable note each time the planner does
# something observable; the orchestrator turns these into bus events.
OnPlanProgress = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class PlannedIssue:
    """One small, independently workable chunk of the task."""

    issue_id: str
    title: str
    description: str
    depends_on: tuple[str, ...] = ()


class Planner(Protocol):
    """Anything that can split a task into planned issues."""

    async def plan(
        self,
        task_id: str,
        prompt: str,
        on_progress: OnPlanProgress | None = None,
    ) -> list[PlannedIssue]: ...


class StaticPlanner:
    """Returns a fixed plan regardless of the prompt.

    Used by tests and the demo loop to exercise the machinery with a known
    split. ``narration`` lines are reported at ``pace`` intervals so the
    demo also exercises the live planning feed.
    """

    def __init__(
        self,
        issues: Sequence[PlannedIssue],
        narration: Sequence[str] = (),
        pace: float = 0.0,
    ) -> None:
        self._issues = list(issues)
        self._narration = list(narration)
        self._pace = pace

    async def plan(
        self,
        task_id: str,
        prompt: str,
        on_progress: OnPlanProgress | None = None,
    ) -> list[PlannedIssue]:
        for note in self._narration:
            if on_progress is not None:
                await on_progress(note)
            if self._pace:
                await asyncio.sleep(self._pace)
        return list(self._issues)


class PlanError(ValueError):
    """A model produced a plan that cannot be used."""


def issues_from_payload(payload: dict) -> list[PlannedIssue]:
    """Normalize a model's ``{"issues": [...]}`` payload into planned issues.

    Ids are slugified and deduplicated; dependency references to unknown ids
    are an error, since silently dropping an edge would let an issue start
    before its prerequisite is merged.
    """
    raw_issues = payload.get("issues")
    if not isinstance(raw_issues, list) or not raw_issues:
        raise PlanError("plan has no issues")

    issues: list[PlannedIssue] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_issues, start=1):
        title = str(raw.get("title", "")).strip()
        if not title:
            raise PlanError(f"issue {index} has no title")
        issue_id = _slug(str(raw.get("id", "")) or title)
        while issue_id in seen:
            issue_id = f"{issue_id}-{index}"
        seen.add(issue_id)
        issues.append(
            PlannedIssue(
                issue_id=issue_id,
                title=title,
                description=str(raw.get("description", "")).strip(),
                depends_on=tuple(_slug(str(dep)) for dep in raw.get("depends_on", [])),
            )
        )

    known = {issue.issue_id for issue in issues}
    for issue in issues:
        for dep in issue.depends_on:
            if dep not in known:
                raise PlanError(
                    f"issue {issue.issue_id!r} depends on unknown issue {dep!r}"
                )
    return issues


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "issue"
