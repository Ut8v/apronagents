"""Backend that drives a headless agent CLI inside the sandbox clone.

This is how a user's existing coding-agent subscription powers Apron
workers: the ``claude`` CLI runs on whatever Claude plan they already use,
the ``codex`` CLI on their ChatGPT plan or OpenAI key, and any other agent
CLI can be plugged in as a :class:`CliProfile`. The CLI is invoked with the
worker's clone as its working directory, so its edits land exactly where a
runner's edits belong.

This module is (with ``git_ops`` and ``tester``) one of the few allowed to
spawn processes: it runs the user's chosen agent CLI, never git.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from apron.agents.definition import AgentDefinition
from apron.orchestrator.planner import PlanError, PlannedIssue, issues_from_payload
from apron.workers.runner import WorkResult

_SUMMARY_LIMIT = 4000


@dataclass(frozen=True)
class CliProfile:
    """How to invoke one agent CLI.

    ``work_args`` and ``plan_args`` are templates; the placeholders
    ``{prompt}``, ``{system}``, and ``{output}`` are substituted per run.
    ``model_args`` is appended when the agent definition names a model the
    CLI can serve (checked against ``model_prefixes``; empty means any).
    """

    name: str
    executable: str
    work_args: tuple[str, ...]
    plan_args: tuple[str, ...]
    model_args: tuple[str, ...] = ()
    model_prefixes: tuple[str, ...] = ()
    # CLIs without a system-prompt flag get it folded into the prompt text.
    fold_system_into_prompt: bool = False
    # Read the final message from the {output} file instead of stdout.
    uses_output_file: bool = False


CLAUDE_CODE_PROFILE = CliProfile(
    name="claude-code",
    executable="claude",
    work_args=(
        "-p", "{prompt}",
        "--append-system-prompt", "{system}",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Read,Edit,Write,Glob,Grep",
    ),
    plan_args=("-p", "{prompt}", "--append-system-prompt", "{system}"),
    model_args=("--model", "{model}"),
    model_prefixes=("claude",),
)

CODEX_PROFILE = CliProfile(
    name="codex",
    executable="codex",
    work_args=(
        "exec", "--full-auto", "--skip-git-repo-check",
        "--output-last-message", "{output}", "{prompt}",
    ),
    plan_args=(
        "exec", "--sandbox", "read-only", "--skip-git-repo-check",
        "--output-last-message", "{output}", "{prompt}",
    ),
    model_args=("-m", "{model}"),
    model_prefixes=("gpt", "o", "codex"),
    fold_system_into_prompt=True,
    uses_output_file=True,
)


class CliAgentRunner:
    """Runs one agent CLI per issue, in the worker's clone."""

    def __init__(self, profile: CliProfile, timeout: float = 3600.0) -> None:
        self.profile = profile
        self.timeout = timeout

    async def run_issue(
        self,
        definition: AgentDefinition,
        issue: PlannedIssue,
        workdir: Path,
    ) -> WorkResult:
        prompt = (
            f"Implement this issue in the current project.\n\n"
            f"Title: {issue.title}\n"
            f"Description: {issue.description}\n\n"
            "Do not run any git commands; just make the changes. When the "
            "issue is fully implemented, finish with a one-paragraph summary "
            "of what you changed."
        )
        summary = await self._invoke(
            self.profile.work_args, definition, prompt, workdir
        )
        return WorkResult(summary=summary[:_SUMMARY_LIMIT])

    async def complete(
        self, definition: AgentDefinition, prompt: str, workdir: Path
    ) -> str:
        """One read-only completion (used for planning)."""
        return await self._invoke(self.profile.plan_args, definition, prompt, workdir)

    async def _invoke(
        self,
        template: tuple[str, ...],
        definition: AgentDefinition,
        prompt: str,
        workdir: Path,
    ) -> str:
        profile = self.profile
        if profile.fold_system_into_prompt:
            prompt = f"Instructions:\n{definition.prompt}\n\n{prompt}"

        with tempfile.TemporaryDirectory(prefix="apron-cli-") as scratch:
            output_file = Path(scratch) / "last-message.txt"
            substitutions = {
                "prompt": prompt,
                "system": definition.prompt,
                "output": str(output_file),
            }
            command = [profile.executable]
            command += [arg.format_map(substitutions) for arg in template]
            model = definition.model
            if model and (
                not profile.model_prefixes
                or model.startswith(profile.model_prefixes)
            ):
                command += [arg.format_map({"model": model}) for arg in profile.model_args]

            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise RuntimeError(
                    f"{profile.name} timed out after {self.timeout}s"
                ) from None
            if process.returncode != 0:
                raise RuntimeError(
                    f"{profile.name} failed ({process.returncode}): "
                    f"{stderr.decode(errors='replace')[-1000:]}"
                )
            if profile.uses_output_file and output_file.exists():
                return output_file.read_text().strip()
            return stdout.decode(errors="replace").strip()


class CliPlanner:
    """Splits a task by asking the agent CLI for a JSON plan."""

    def __init__(
        self,
        runner: CliAgentRunner,
        definition_resolver: Callable[[], AgentDefinition],
        working_dir: Path,
    ) -> None:
        self.runner = runner
        self._resolve_definition = definition_resolver
        self.working_dir = working_dir

    async def plan(self, task_id: str, prompt: str) -> list[PlannedIssue]:
        text = await self.runner.complete(
            self._resolve_definition(),
            (
                f"Task: {prompt}\n\n"
                "Split this task into issues. Respond with ONLY a JSON object, "
                "no prose and no code fences, shaped exactly like:\n"
                '{"issues": [{"id": "short-slug", "title": "...", '
                '"description": "...", "depends_on": []}]}'
            ),
            self.working_dir,
        )
        return issues_from_payload(_extract_json(text))


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of a CLI reply that may add fences or prose."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise PlanError(f"no JSON object in plan reply: {text[:200]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        raise PlanError(f"invalid plan JSON: {error}") from error
