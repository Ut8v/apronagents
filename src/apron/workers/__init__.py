"""Worker organ: claims one issue at a time, loads its agent definition,
branches in the sandbox, runs the agent through a pluggable runner backend,
commits, and opens a review. Workers never merge their own work."""

from apron.workers.runner import AgentRunner, FakeRunner, WorkResult
from apron.workers.worker import Worker

__all__ = ["AgentRunner", "FakeRunner", "WorkResult", "Worker"]
