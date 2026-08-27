"""Event types and schema: the shared vocabulary of the whole tool.

Every coordination message between organs is one of the frozen dataclasses
defined here. Events are past-tense facts describing what happened, never
instructions about what to do next. If two components need to agree on a
message shape, it is defined here once.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class IssueState(StrEnum):
    """The states an issue moves through, mirroring the lifecycle diagram."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    MERGING = "merging"
    TEST_FAILED = "test_failed"
    MERGED = "merged"


def _new_event_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True, kw_only=True)
class Event:
    """Base class for everything that travels on the bus."""

    event_id: str = field(default_factory=_new_event_id)
    timestamp: float = field(default_factory=time.time)

    @property
    def kind(self) -> str:
        return type(self).__name__

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["kind"] = self.kind
        return payload


_EVENT_TYPES: dict[str, type[Event]] = {}


def _register(cls: type[Event]) -> type[Event]:
    _EVENT_TYPES[cls.__name__] = cls
    return cls


def event_from_dict(payload: dict) -> Event:
    """Rehydrate an event from its ``to_dict`` form (e.g. out of the store)."""
    data = dict(payload)
    kind = data.pop("kind")
    try:
        cls = _EVENT_TYPES[kind]
    except KeyError:
        raise ValueError(f"unknown event kind: {kind!r}") from None
    # JSON has no tuples; restore list-valued fields to the declared tuples.
    data = {k: tuple(v) if isinstance(v, list) else v for k, v in data.items()}
    return cls(**data)


# --- task planning -----------------------------------------------------------


@_register
@dataclass(frozen=True, kw_only=True)
class TaskReceived(Event):
    task_id: str
    prompt: str


@_register
@dataclass(frozen=True, kw_only=True)
class PlanningProgress(Event):
    """The planner did something observable while splitting the task (read a
    file, said what it is thinking). Pure telemetry, so the dispatch terminal
    has something to show between hitting enter and the first issue."""

    task_id: str
    note: str


@_register
@dataclass(frozen=True, kw_only=True)
class PlanProposed(Event):
    """The planner produced a split that now waits at the plan gate.
    ``issues`` is a tuple of ``{"id", "title", "description", "depends_on"}``
    dicts — the human may edit them before approving."""

    task_id: str
    issues: tuple = ()


@_register
@dataclass(frozen=True, kw_only=True)
class PlanApproved(Event):
    """The human cleared the plan (possibly edited) for dispatch. Same
    issue shape as :class:`PlanProposed`."""

    task_id: str
    issues: tuple = ()


@_register
@dataclass(frozen=True, kw_only=True)
class TaskPlanned(Event):
    task_id: str
    issue_ids: tuple[str, ...]


# --- issue lifecycle ---------------------------------------------------------


@_register
@dataclass(frozen=True, kw_only=True)
class IssueQueued(Event):
    issue_id: str
    task_id: str
    title: str
    description: str
    depends_on: tuple[str, ...] = ()


@_register
@dataclass(frozen=True, kw_only=True)
class IssueClaimed(Event):
    issue_id: str
    worker_id: str


@_register
@dataclass(frozen=True, kw_only=True)
class WorkStarted(Event):
    issue_id: str
    worker_id: str
    branch: str


@_register
@dataclass(frozen=True, kw_only=True)
class ProgressReported(Event):
    """A worker's agent did something observable (read a file, made an edit,
    said what it is about to do). Pure telemetry for the dashboard."""

    issue_id: str
    worker_id: str
    note: str


@_register
@dataclass(frozen=True, kw_only=True)
class ReviewOpened(Event):
    issue_id: str
    worker_id: str
    branch: str
    summary: str = ""


@_register
@dataclass(frozen=True, kw_only=True)
class ChangesRequested(Event):
    """The reviewer sent the work back. ``annotations`` pins feedback to
    specific diff lines: a tuple of ``{"path", "line", "note"}`` dicts."""

    issue_id: str
    reason: str = ""
    annotations: tuple = ()


@_register
@dataclass(frozen=True, kw_only=True)
class ReviewApproved(Event):
    issue_id: str


# --- merging -----------------------------------------------------------------


@_register
@dataclass(frozen=True, kw_only=True)
class MergeStarted(Event):
    issue_id: str
    branch: str


@_register
@dataclass(frozen=True, kw_only=True)
class TestsPassed(Event):
    issue_id: str


@_register
@dataclass(frozen=True, kw_only=True)
class TestsFailed(Event):
    issue_id: str
    log_tail: str = ""


@_register
@dataclass(frozen=True, kw_only=True)
class MergeConflictDetected(Event):
    issue_id: str
    branch: str
    detail: str = ""


@_register
@dataclass(frozen=True, kw_only=True)
class MergeSucceeded(Event):
    issue_id: str
    branch: str


# --- completion --------------------------------------------------------------


@_register
@dataclass(frozen=True, kw_only=True)
class TaskCompleted(Event):
    task_id: str


@_register
@dataclass(frozen=True, kw_only=True)
class HandoffCompleted(Event):
    task_id: str
    target_dir: str
    files: tuple[str, ...] = ()


# --- workers and agents ------------------------------------------------------


@_register
@dataclass(frozen=True, kw_only=True)
class WorkerStarted(Event):
    worker_id: str
    agent_name: str


@_register
@dataclass(frozen=True, kw_only=True)
class WorkerStopped(Event):
    worker_id: str
    reason: str = ""


@_register
@dataclass(frozen=True, kw_only=True)
class AgentDefinitionsReloaded(Event):
    names: tuple[str, ...]
