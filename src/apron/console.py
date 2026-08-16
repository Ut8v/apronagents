"""Renders bus events as terminal output.

The terminal that dispatched a run should narrate it the same way the
dashboard does. ``apron start`` attaches a :class:`ConsoleReporter` to the
bus, so planning, live worker activity, reviews, merges, and the handoff
all stream into the terminal — a third renderer over the same events.
"""

from __future__ import annotations

import sys
from typing import TextIO

from apron.bus.bus import EventBus, Subscription
from apron.bus.events import (
    ChangesRequested,
    Event,
    HandoffCompleted,
    MergeConflictDetected,
    MergeStarted,
    MergeSucceeded,
    PlanningProgress,
    ProgressReported,
    ReviewOpened,
    TaskCompleted,
    TaskPlanned,
    TaskReceived,
    TestsFailed,
    WorkStarted,
)

_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


class ConsoleReporter:
    """Prints one human-readable line per noteworthy bus event."""

    def __init__(
        self,
        dashboard_url: str = "",
        out: TextIO | None = None,
        color: bool | None = None,
    ) -> None:
        self.dashboard_url = dashboard_url
        self._out = out or sys.stdout
        self._color = self._out.isatty() if color is None else color

    def attach(self, bus: EventBus) -> Subscription:
        return bus.subscribe(self._on_event)

    def _on_event(self, event: Event) -> None:
        line = self.render(event)
        if line is not None:
            print(line, file=self._out, flush=True)

    def _dim(self, text: str) -> str:
        return f"{_DIM}{text}{_RESET}" if self._color else text

    def _bold(self, text: str) -> str:
        return f"{_BOLD}{text}{_RESET}" if self._color else text

    def render(self, event: Event) -> str | None:
        if isinstance(event, TaskReceived):
            return self._bold(f"◆ task {event.task_id}: {event.prompt[:100]}")
        if isinstance(event, PlanningProgress):
            return self._dim(f"  ▸ planner · {event.note}")
        if isinstance(event, TaskPlanned):
            issues = ", ".join(event.issue_ids)
            return self._bold(f"◆ planned {len(event.issue_ids)} issue(s): {issues}")
        if isinstance(event, WorkStarted):
            return f"▶ {event.worker_id} started {event.issue_id} ({event.branch})"
        if isinstance(event, ProgressReported):
            return self._dim(f"  ▸ {event.worker_id} · {event.note}")
        if isinstance(event, ReviewOpened):
            where = f" — approve at {self.dashboard_url}" if self.dashboard_url else ""
            return self._bold(f"● review open: {event.issue_id} by {event.worker_id}{where}")
        if isinstance(event, ChangesRequested):
            reason = f": {event.reason}" if event.reason else ""
            return f"↩ sent back {event.issue_id}{reason}"
        if isinstance(event, MergeStarted):
            return self._dim(f"  ⇅ merging {event.branch}")
        if isinstance(event, TestsFailed):
            return f"✗ tests failed on {event.issue_id} — routed back to a worker"
        if isinstance(event, MergeConflictDetected):
            detail = f" ({event.detail})" if event.detail else ""
            return f"✗ merge conflict on {event.branch}{detail} — routed back for a rebase"
        if isinstance(event, MergeSucceeded):
            return f"✓ merged {event.issue_id}"
        if isinstance(event, TaskCompleted):
            return self._bold("◆ all issues merged")
        if isinstance(event, HandoffCompleted):
            return self._bold(f"⇥ handoff complete → {event.target_dir}")
        return None
