"""Sandbox git layer: a disposable bare repo in a temp dir acting as a fully
local "fake GitHub", plus per-worker clones and the final handoff.

Nothing in this package ever touches a real remote.
"""

from apron.sandbox.clone import WorkerClone
from apron.sandbox.git_ops import GitError, GitOps, GitResult, RemoteAccessViolation
from apron.sandbox.handoff import handoff
from apron.sandbox.repo import SandboxRepo

__all__ = [
    "GitError",
    "GitOps",
    "GitResult",
    "RemoteAccessViolation",
    "SandboxRepo",
    "WorkerClone",
    "handoff",
]
