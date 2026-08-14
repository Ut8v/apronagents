"""Durable state in SQLite.

The store subscribes to the bus and records two things: an append-only event
journal, and a per-issue projection of current state. A late-joining dashboard
catches up from here instead of asking any organ directly.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from apron.bus.events import (
    ChangesRequested,
    Event,
    IssueClaimed,
    IssueQueued,
    IssueState,
    MergeConflictDetected,
    MergeStarted,
    MergeSucceeded,
    ReviewApproved,
    ReviewOpened,
    TestsFailed,
    WorkStarted,
    event_from_dict,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   TEXT NOT NULL UNIQUE,
    kind       TEXT NOT NULL,
    timestamp  REAL NOT NULL,
    payload    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS issues (
    issue_id    TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    depends_on  TEXT NOT NULL,
    state       TEXT NOT NULL,
    worker_id   TEXT,
    branch      TEXT,
    updated_at  REAL NOT NULL
);
"""


@dataclass(frozen=True)
class IssueSnapshot:
    """The current state of one issue, as projected from the journal."""

    issue_id: str
    task_id: str
    title: str
    description: str
    depends_on: tuple[str, ...]
    state: IssueState
    worker_id: str | None
    branch: str | None
    updated_at: float


class StateStore:
    """Append-only journal plus a current-state projection, both in SQLite."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    # --- recording -----------------------------------------------------------

    def record(self, event: Event) -> None:
        """Journal ``event`` and update the issue projection. Idempotent per event id."""
        with self._lock, self._conn:
            inserted = self._conn.execute(
                "INSERT OR IGNORE INTO events (event_id, kind, timestamp, payload)"
                " VALUES (?, ?, ?, ?)",
                (event.event_id, event.kind, event.timestamp, json.dumps(event.to_dict())),
            )
            if inserted.rowcount:
                self._project(event)

    def _project(self, event: Event) -> None:
        if isinstance(event, IssueQueued):
            self._conn.execute(
                "INSERT OR REPLACE INTO issues"
                " (issue_id, task_id, title, description, depends_on, state,"
                "  worker_id, branch, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?)",
                (
                    event.issue_id,
                    event.task_id,
                    event.title,
                    event.description,
                    json.dumps(list(event.depends_on)),
                    IssueState.QUEUED,
                    event.timestamp,
                ),
            )
        elif isinstance(event, IssueClaimed):
            self._transition(event, IssueState.CLAIMED, worker_id=event.worker_id)
        elif isinstance(event, WorkStarted):
            self._transition(
                event, IssueState.IN_PROGRESS,
                worker_id=event.worker_id, branch=event.branch,
            )
        elif isinstance(event, ReviewOpened):
            self._transition(event, IssueState.IN_REVIEW)
        elif isinstance(event, (ChangesRequested, MergeConflictDetected)):
            # A conflict takes the same edge as a rejected review: back to the
            # worker to rework (rebase) before another merge attempt.
            self._transition(event, IssueState.CHANGES_REQUESTED)
        elif isinstance(event, ReviewApproved):
            self._transition(event, IssueState.APPROVED)
        elif isinstance(event, MergeStarted):
            self._transition(event, IssueState.MERGING)
        elif isinstance(event, TestsFailed):
            self._transition(event, IssueState.TEST_FAILED)
        elif isinstance(event, MergeSucceeded):
            self._transition(event, IssueState.MERGED)

    def _transition(self, event: Event, state: IssueState, **columns: str) -> None:
        issue_id: str = getattr(event, "issue_id")
        assignments = "".join(f"{name} = ?, " for name in columns)
        self._conn.execute(
            f"UPDATE issues SET {assignments}state = ?, updated_at = ?"
            " WHERE issue_id = ?",
            (*columns.values(), state, event.timestamp, issue_id),
        )

    # --- reading -------------------------------------------------------------

    def events_since(self, seq: int = 0) -> list[tuple[int, Event]]:
        """Return ``(seq, event)`` pairs after ``seq``, in journal order."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, payload FROM events WHERE seq > ? ORDER BY seq", (seq,)
            ).fetchall()
        return [(row["seq"], event_from_dict(json.loads(row["payload"]))) for row in rows]

    def issues(self) -> list[IssueSnapshot]:
        """Every known issue, oldest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM issues ORDER BY rowid"
            ).fetchall()
        return [self._snapshot(row) for row in rows]

    def issue(self, issue_id: str) -> IssueSnapshot | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM issues WHERE issue_id = ?", (issue_id,)
            ).fetchone()
        return self._snapshot(row) if row else None

    @staticmethod
    def _snapshot(row: sqlite3.Row) -> IssueSnapshot:
        return IssueSnapshot(
            issue_id=row["issue_id"],
            task_id=row["task_id"],
            title=row["title"],
            description=row["description"],
            depends_on=tuple(json.loads(row["depends_on"])),
            state=IssueState(row["state"]),
            worker_id=row["worker_id"],
            branch=row["branch"],
            updated_at=row["updated_at"],
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
