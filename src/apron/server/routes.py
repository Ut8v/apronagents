"""REST routes: submit a task, list state, get a diff, approve, send back,
read and edit agents, and toggle the mode.

Every write goes through the bus or the overlay; the routes hold no state of
their own."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apron.agents.definition import AgentDefinition, AgentRole, DefinitionError
from apron.agents.discovery import discover_agents, discover_from_settings
from apron.agents.overlay import save_override
from apron.bus.bus import EventBus
from apron.bus.events import (
    AgentDefinitionsReloaded,
    ChangesRequested,
    ReviewApproved,
    TaskReceived,
)
from apron.bus.store import StateStore
from apron.config import Mode, Settings
from apron.merge.controller import MergeController
from apron.sandbox.repo import SandboxRepo
from apron.workers.worker import Worker


@dataclass
class ServerContext:
    """Everything the server reads from or writes through."""

    settings: Settings
    bus: EventBus
    store: StateStore
    repo: SandboxRepo
    workers: Sequence[Worker]
    controller: MergeController


class TaskIn(BaseModel):
    prompt: str


class SendBackIn(BaseModel):
    reason: str = ""


class ModeIn(BaseModel):
    mode: Mode


class AgentIn(BaseModel):
    description: str = ""
    role: AgentRole = AgentRole.WORKER
    model: str | None = None
    tools: list[str] = []
    prompt: str


def state_payload(ctx: ServerContext) -> dict:
    """The whole dashboard state, projected from the store and worker pool."""
    return {
        "mode": ctx.controller.mode.value,
        "planning": ctx.store.planning(),
        "issues": [
            {
                "issue_id": i.issue_id,
                "task_id": i.task_id,
                "title": i.title,
                "description": i.description,
                "depends_on": list(i.depends_on),
                "state": i.state.value,
                "worker_id": i.worker_id,
                "branch": i.branch,
                "last_activity": i.last_activity,
                "updated_at": i.updated_at,
            }
            for i in ctx.store.issues()
        ],
        "workers": [
            {
                "id": w.worker_id,
                "agent_name": w.definition.name,
                "agent_source": w.definition.source.value if w.definition.source else None,
                "idle": w.idle,
            }
            for w in ctx.workers
        ],
    }


def _agent_payload(definition: AgentDefinition, overridden: bool) -> dict:
    return {
        "name": definition.name,
        "description": definition.description,
        "role": definition.role.value,
        "model": definition.model,
        "tools": list(definition.tools),
        "prompt": definition.prompt,
        "source": definition.source.value if definition.source else None,
        "overridden": overridden,
    }


def build_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter()

    @router.get("/state")
    async def get_state() -> dict:
        return state_payload(ctx)

    @router.post("/task")
    async def submit_task(body: TaskIn) -> dict:
        task_id = uuid.uuid4().hex[:8]
        await ctx.bus.publish(TaskReceived(task_id=task_id, prompt=body.prompt))
        return {"task_id": task_id}

    @router.get("/workspace")
    async def workspace() -> dict:
        """The project tree with change markers: what merged work has
        changed since the seed, and which files each in-flight issue
        branch is touching right now."""
        git, bare = ctx.repo.git, ctx.repo.bare_path
        root = git.run(
            "rev-list", "--max-parents=0", "main", cwd=bare
        ).stdout.split()[0]
        merged: dict[str, str] = {}
        for line in git.run(
            "diff", "--name-status", f"{root}..main", cwd=bare
        ).stdout.splitlines():
            if line:
                merged[line.split("\t")[-1]] = line.split("\t")[0][0]
        editing: dict[str, list[str]] = {}
        for branch in ctx.repo.branches():
            if branch == "main":
                continue
            issue_id = branch.removeprefix("issue/")
            diff = git.run(
                "diff", "--name-status", f"main...{branch}", cwd=bare, check=False
            )
            for line in diff.stdout.splitlines():
                if line:
                    editing.setdefault(line.split("\t")[-1], []).append(issue_id)
        tracked = git.run(
            "ls-tree", "-r", "--name-only", "main", cwd=bare
        ).stdout.splitlines()
        paths = sorted(set(tracked) | set(merged) | set(editing))
        return {
            "files": [
                {"path": p, "merged": merged.get(p), "editing": editing.get(p, [])}
                for p in paths
            ]
        }

    @router.get("/issues/{issue_id}/diff")
    async def get_diff(issue_id: str) -> dict:
        issue = ctx.store.issue(issue_id)
        if issue is None:
            raise HTTPException(404, f"unknown issue {issue_id!r}")
        if issue.branch is None:
            raise HTTPException(409, f"issue {issue_id!r} has no branch yet")
        base = ctx.repo.git
        files = base.run(
            "diff", "--name-status", f"main...{issue.branch}", cwd=ctx.repo.bare_path
        ).stdout
        patch = base.run(
            "diff", f"main...{issue.branch}", cwd=ctx.repo.bare_path
        ).stdout
        return {
            "issue_id": issue_id,
            "branch": issue.branch,
            "files": [
                {"status": line.split("\t")[0], "path": line.split("\t")[-1]}
                for line in files.splitlines()
                if line
            ],
            "diff": patch,
        }

    @router.post("/issues/{issue_id}/approve")
    async def approve(issue_id: str) -> dict:
        _require_issue(ctx, issue_id)
        await ctx.bus.publish(ReviewApproved(issue_id=issue_id))
        return {"ok": True}

    @router.post("/issues/{issue_id}/send-back")
    async def send_back(issue_id: str, body: SendBackIn) -> dict:
        _require_issue(ctx, issue_id)
        await ctx.bus.publish(
            ChangesRequested(issue_id=issue_id, reason=body.reason)
        )
        return {"ok": True}

    @router.get("/agents")
    async def list_agents() -> list[dict]:
        resolved = discover_from_settings(ctx.settings)
        base = _without_project_layer(ctx.settings)
        return [
            _agent_payload(d, overridden=name in base and d.source != base[name].source)
            for name, d in sorted(resolved.items())
        ]

    @router.put("/agents/{name}")
    async def save_agent(name: str, body: AgentIn) -> dict:
        if not body.prompt.strip():
            raise HTTPException(422, "prompt must not be empty")
        definition = AgentDefinition(
            name=name,
            description=body.description,
            role=body.role,
            prompt=body.prompt.strip(),
            model=body.model,
            tools=tuple(body.tools),
        )
        try:
            save_override(ctx.settings.project_apron_dir, definition)
        except DefinitionError as error:
            raise HTTPException(422, str(error)) from error
        await ctx.bus.publish(AgentDefinitionsReloaded(names=(name,)))
        saved = discover_from_settings(ctx.settings)[name]
        return _agent_payload(saved, overridden=name in _without_project_layer(ctx.settings))

    @router.post("/mode")
    async def set_mode(body: ModeIn) -> dict:
        ctx.controller.mode = body.mode
        return {"mode": ctx.controller.mode.value}

    return router


def _require_issue(ctx: ServerContext, issue_id: str) -> None:
    if ctx.store.issue(issue_id) is None:
        raise HTTPException(404, f"unknown issue {issue_id!r}")


def _without_project_layer(settings: Settings) -> dict[str, AgentDefinition]:
    """What resolution would give without ``.apron/agents/`` — used to tell
    an override apart from an agent that only exists in the overlay."""
    missing = settings.project_apron_dir / "agents-disabled"
    return discover_agents(
        user_apron_dir=settings.user_apron_dir / "agents",
        claude_user_dir=settings.user_claude_dir / "agents",
        claude_project_dir=settings.project_claude_dir / "agents",
        project_apron_dir=missing,
    )
