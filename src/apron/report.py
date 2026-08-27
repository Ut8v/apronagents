"""Renders one run's journaled events as a shareable markdown report.

Like the console reporter and the dashboard, this is a renderer over the
bus vocabulary — the journal stays the single source of truth, and the
report is just the story it already tells: the task, the plan, what every
issue went through, and what crossed the bridge at handoff.
"""

from __future__ import annotations

import time
from typing import Sequence

from apron.bus.events import (
    ChangesRequested,
    Event,
    HandoffCompleted,
    IssueClaimed,
    IssueQueued,
    MergeConflictDetected,
    MergeSucceeded,
    PlanProposed,
    ReviewApproved,
    ReviewOpened,
    TaskReceived,
    TestsFailed,
)

_SUMMARY_EXCERPT = 120


def _clock(timestamp: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(timestamp))


def _day(timestamp: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def _duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def run_report(events: Sequence[Event]) -> str:
    """One run's events (as returned by ``StateStore.task_events``) as
    markdown. Raises ValueError when the slice holds no run at all."""
    received = next((e for e in events if isinstance(e, TaskReceived)), None)
    if received is None:
        raise ValueError("no run in this event slice")
    handoff = next((e for e in events if isinstance(e, HandoffCompleted)), None)

    lines = [f"# Apron run {received.task_id}", ""]
    lines.append(f"**Task:** {received.prompt.strip()}")
    status = "completed ✓" if handoff else "not completed"
    when = f"**Started:** {_day(received.timestamp)}"
    if handoff:
        when += (
            f" · **Finished:** {_clock(handoff.timestamp)}"
            f" ({_duration(handoff.timestamp - received.timestamp)})"
        )
    lines += [when + f" · **Status:** {status}", ""]

    queued = [e for e in events if isinstance(e, IssueQueued)]
    if queued:
        lines.append("## Plan")
        if any(isinstance(e, PlanProposed) for e in events):
            lines.append("_Held at the plan gate and human-approved before dispatch._")
        for n, issue in enumerate(queued, start=1):
            needs = (
                f" _(needs {', '.join(issue.depends_on)})_" if issue.depends_on else ""
            )
            lines.append(f"{n}. **{issue.issue_id}** — {issue.title}{needs}")
        lines.append("")

    for issue in queued:
        lines += _issue_section(issue, events)

    if handoff:
        lines.append("## Handoff")
        lines.append(
            f"{len(handoff.files)} file(s) copied into `{handoff.target_dir}` — "
            "the run's only bridge to reality. The real remote was never touched."
        )
        lines += [f"- `{name}`" for name in handoff.files]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _issue_section(issue: IssueQueued, events: Sequence[Event]) -> list[str]:
    mine = [e for e in events if getattr(e, "issue_id", None) == issue.issue_id]
    merged = any(isinstance(e, MergeSucceeded) for e in mine)
    mark = "merged ✓" if merged else "not merged"
    lines = [f"## {issue.issue_id} — {mark}"]
    for event in mine:
        stamp = _clock(event.timestamp)
        if isinstance(event, IssueClaimed):
            lines.append(f"- {stamp} claimed by {event.worker_id}")
        elif isinstance(event, ReviewOpened):
            summary = event.summary.strip().split("\n")[0][:_SUMMARY_EXCERPT]
            note = f": “{summary}”" if summary else ""
            lines.append(f"- {stamp} review opened{note}")
        elif isinstance(event, ChangesRequested):
            reason = event.reason.strip() or "sent back"
            notes = (
                f" (+{len(event.annotations)} line note(s))"
                if event.annotations
                else ""
            )
            lines.append(f"- {stamp} sent back: {reason}{notes}")
            for a in event.annotations:
                lines.append(f"    - `{a['path']}:{a['line']}` — {a['note']}")
        elif isinstance(event, TestsFailed):
            lines.append(f"- {stamp} tests failed — routed back for rework")
        elif isinstance(event, MergeConflictDetected):
            lines.append(f"- {stamp} merge conflict — routed back for a rebase")
        elif isinstance(event, ReviewApproved):
            lines.append(f"- {stamp} approved by the reviewer")
        elif isinstance(event, MergeSucceeded):
            lines.append(f"- {stamp} merged into sandbox main")
    lines.append("")
    return lines
