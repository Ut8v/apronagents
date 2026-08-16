"""Backend that drives a model directly through the Anthropic API: the
:class:`ApiRunner` implements issues inside the worker's sandbox clone
through three file tools, and the :class:`ApiPlanner` splits tasks using
structured outputs.

Committing and pushing stay the worker's job. Every path the model supplies
is resolved and confined to the clone directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from anthropic import AsyncAnthropic

from apron.agents.definition import AgentDefinition
from apron.orchestrator.planner import PlannedIssue, issues_from_payload
from apron.workers.runner import OnProgress, WorkResult

DEFAULT_MODEL = "claude-opus-5"
MAX_TURNS = 40
_MAX_TOKENS = 16000
_LISTING_LIMIT = 200
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}

TOOLS = [
    {
        "name": "list_files",
        "description": (
            "List every file in the project working tree, as relative paths. "
            "Call this first to see the project layout."
        ),
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "name": "read_file",
        "description": "Read one file from the project. Returns its full text content.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path of the file to read"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "write_file",
        "description": (
            "Create or overwrite one file in the project with the given "
            "content. Parent directories are created as needed. Call this "
            "for every file your implementation touches."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path of the file to write"},
                "content": {"type": "string", "description": "The complete new file content"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
]


class ApiRunner:
    """Executes an agent definition against a working directory via the API."""

    def __init__(
        self,
        client: AsyncAnthropic | None = None,
        session_context: str | None = None,
    ) -> None:
        self.client = client or AsyncAnthropic()
        self.session_context = session_context

    async def run_issue(
        self,
        definition: AgentDefinition,
        issue: PlannedIssue,
        workdir: Path,
        on_progress: OnProgress | None = None,
    ) -> WorkResult:
        model = definition.model or DEFAULT_MODEL
        messages: list[dict] = [
            {
                "role": "user",
                "content": (
                    f"Implement this issue in the project at your working tree.\n\n"
                    f"Title: {issue.title}\n"
                    f"Description: {issue.description}\n\n"
                    "Use the tools to inspect the project and write your "
                    "changes. When the issue is fully implemented, stop and "
                    "reply with a one-paragraph summary of what you changed."
                    + (
                        "\n\nBackground from the user's recent interactive "
                        "Claude session (already agreed; do not re-litigate):\n"
                        + self.session_context
                        if self.session_context
                        else ""
                    )
                ),
            }
        ]

        for _ in range(MAX_TURNS):
            async with self.client.messages.stream(
                model=model,
                max_tokens=_MAX_TOKENS,
                system=definition.prompt,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                response = await stream.get_final_message()

            if response.stop_reason == "refusal":
                return WorkResult(summary="the agent declined this issue")
            if response.stop_reason != "tool_use":
                summary = next(
                    (b.text for b in response.content if b.type == "text"), ""
                )
                return WorkResult(summary=summary.strip())

            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type == "text" and on_progress and block.text.strip():
                    await on_progress(block.text.strip().split("\n")[0][:120])
                if block.type != "tool_use":
                    continue
                if on_progress is not None:
                    hint = block.input.get("path", "")
                    await on_progress(f"{block.name} {hint}".strip()[:120])
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": _run_tool(workdir, block.name, block.input),
                    }
                )
            messages.append({"role": "user", "content": results})

        return WorkResult(summary=f"stopped after {MAX_TURNS} turns")


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "title", "description", "depends_on"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["issues"],
    "additionalProperties": False,
}


class ApiPlanner:
    """Splits a task into issues by driving the orchestrator agent definition
    through the API with structured outputs."""

    def __init__(
        self,
        definition_resolver: Callable[[], AgentDefinition],
        working_dir: Path,
        client: AsyncAnthropic | None = None,
        session_context: str | None = None,
    ) -> None:
        self.client = client or AsyncAnthropic()
        self._resolve_definition = definition_resolver
        self.working_dir = working_dir
        self.session_context = session_context

    async def plan(self, task_id: str, prompt: str) -> list[PlannedIssue]:
        definition = self._resolve_definition()
        response = await self.client.messages.create(
            model=definition.model or DEFAULT_MODEL,
            max_tokens=_MAX_TOKENS,
            system=definition.prompt,
            output_config={"format": {"type": "json_schema", "schema": PLAN_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Task: {prompt}\n\n"
                        f"Project files:\n{_list_files(self.working_dir)}\n\n"
                        + (
                            "Background from the user's recent interactive "
                            f"Claude session:\n{self.session_context}\n\n"
                            if self.session_context
                            else ""
                        )
                        + "Split this task into issues. Refer to files by "
                        "paths relative to the project root."
                    ),
                }
            ],
        )
        text = next(b.text for b in response.content if b.type == "text")
        return issues_from_payload(json.loads(text))


def _run_tool(workdir: Path, name: str, tool_input: dict) -> str:
    try:
        if name == "list_files":
            return _list_files(workdir)
        if name == "read_file":
            return _resolve(workdir, tool_input["path"]).read_text()
        if name == "write_file":
            target = _resolve(workdir, tool_input["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(tool_input["content"])
            return f"wrote {tool_input['path']}"
        return f"Error: unknown tool {name!r}"
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        return f"Error: {error}"


def _resolve(workdir: Path, relative: str) -> Path:
    """Confine a model-supplied path to the clone; reject any escape."""
    resolved = (workdir / relative).resolve()
    if not resolved.is_relative_to(workdir.resolve()):
        raise ValueError(f"path {relative!r} escapes the working tree")
    if ".git" in resolved.relative_to(workdir.resolve()).parts:
        raise ValueError("the .git directory is off limits")
    return resolved


def _list_files(workdir: Path) -> str:
    paths = sorted(
        str(path.relative_to(workdir))
        for path in workdir.rglob("*")
        if path.is_file() and not _SKIP_DIRS.intersection(path.relative_to(workdir).parts)
    )
    listing = paths[:_LISTING_LIMIT]
    if len(paths) > _LISTING_LIMIT:
        listing.append(f"... and {len(paths) - _LISTING_LIMIT} more files")
    return "\n".join(listing) or "(empty project)"
