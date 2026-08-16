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
from apron.workers.runner import OnProgress, WorkResult

_SUMMARY_LIMIT = 4000
_NOTE_LIMIT = 120


@dataclass(frozen=True)
class CliProfile:
    """How to invoke one agent CLI.

    ``work_args`` and ``plan_args`` are templates; the placeholders
    ``{prompt}``, ``{system}``, and ``{output}`` are substituted per run.
    ``model_args`` is appended when the agent definition names a model the
    CLI can serve (checked against ``model_prefixes``; empty means any).
    When ``work_stream_args`` is set, issues run with it and stdout is
    parsed live per ``stream_format`` (``claude-json`` or ``lines``) so the
    dashboard can show what the agent is doing.
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
    work_stream_args: tuple[str, ...] | None = None
    stream_format: str = "lines"


CLAUDE_CODE_PROFILE = CliProfile(
    name="claude-code",
    executable="claude",
    work_args=(
        "-p", "{prompt}",
        "--append-system-prompt", "{system}",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Read,Edit,Write,Glob,Grep,Bash",
    ),
    plan_args=("-p", "{prompt}", "--append-system-prompt", "{system}"),
    model_args=("--model", "{model}"),
    model_prefixes=("claude",),
    work_stream_args=(
        "-p", "{prompt}",
        "--append-system-prompt", "{system}",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Read,Edit,Write,Glob,Grep,Bash",
        "--output-format", "stream-json", "--verbose",
    ),
    stream_format="claude-json",
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
    # codex already streams human-readable progress on stdout; the final
    # message still comes from the {output} file.
    work_stream_args=(
        "exec", "--full-auto", "--skip-git-repo-check",
        "--output-last-message", "{output}", "{prompt}",
    ),
    stream_format="lines",
)


class CliAgentRunner:
    """Runs one agent CLI per issue, in the worker's clone."""

    def __init__(
        self,
        profile: CliProfile,
        timeout: float = 3600.0,
        session_context: str | None = None,
    ) -> None:
        self.profile = profile
        self.timeout = timeout
        # A summary of the user's recent interactive session, injected into
        # every issue prompt so workers know what was already decided.
        self.session_context = session_context

    async def run_issue(
        self,
        definition: AgentDefinition,
        issue: PlannedIssue,
        workdir: Path,
        on_progress: OnProgress | None = None,
    ) -> WorkResult:
        prompt = (
            f"Implement this issue in the current project.\n\n"
            f"Title: {issue.title}\n"
            f"Description: {issue.description}\n\n"
            "Work only on files inside the current working directory, using "
            "relative paths — never absolute paths, and never files outside "
            "it. Do not run any git commands; just make the changes. When "
            "the issue is fully implemented, finish with a one-paragraph "
            "summary of what you changed."
        )
        if self.session_context:
            prompt += (
                "\n\nBackground from the user's recent interactive Claude "
                "session (already agreed; do not re-litigate):\n"
                + self.session_context
            )
        if on_progress is not None and self.profile.work_stream_args:
            summary = await self._invoke(
                self.profile.work_stream_args, definition, prompt, workdir,
                on_progress=on_progress,
            )
        else:
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
        on_progress: OnProgress | None = None,
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
                if on_progress is None:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        process.communicate(), timeout=self.timeout
                    )
                    stdout = stdout_bytes.decode(errors="replace")
                else:
                    stdout, stderr_bytes = await asyncio.wait_for(
                        self._stream(process, on_progress), timeout=self.timeout
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
                    f"{stderr_bytes.decode(errors='replace')[-1000:]}"
                )
            if profile.uses_output_file and output_file.exists():
                return output_file.read_text().strip()
            return stdout.strip()

    async def _stream(self, process, on_progress: OnProgress) -> tuple[str, bytes]:
        """Read stdout live, reporting a note per observable action; the
        returned "stdout" is the final message the stream carried."""
        final = ""
        async def drain_stderr() -> bytes:
            return await process.stderr.read()
        stderr_task = asyncio.ensure_future(drain_stderr())
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode(errors="replace").rstrip()
            if not text:
                continue
            if self.profile.stream_format == "claude-json":
                notes, result = _claude_stream_line(text)
            else:
                notes, result = [text[:_NOTE_LIMIT]], None
            if result is not None:
                final = result
            for note in notes:
                await on_progress(note)
        stderr_bytes = await stderr_task
        await process.wait()
        return final, stderr_bytes


class CliPlanner:
    """Splits a task by asking the agent CLI for a JSON plan."""

    def __init__(
        self,
        runner: CliAgentRunner,
        definition_resolver: Callable[[], AgentDefinition],
        working_dir: Path,
        session_context: str | None = None,
    ) -> None:
        self.runner = runner
        self._resolve_definition = definition_resolver
        self.working_dir = working_dir
        self.session_context = session_context

    async def plan(self, task_id: str, prompt: str) -> list[PlannedIssue]:
        context = (
            "\n\nBackground from the user's recent interactive Claude session:"
            f"\n{self.session_context}\n"
            if self.session_context
            else ""
        )
        text = await self.runner.complete(
            self._resolve_definition(),
            (
                f"Task: {prompt}{context}\n\n"
                "Split this task into issues. Refer to files by paths "
                "relative to the project root, never absolute paths. Respond "
                "with ONLY a JSON object, no prose and no code fences, "
                "shaped exactly like:\n"
                '{"issues": [{"id": "short-slug", "title": "...", '
                '"description": "...", "depends_on": []}]}'
            ),
            self.working_dir,
        )
        return issues_from_payload(_extract_json(text))


_SUMMARY_PROMPT = (
    "Summarize this session for a coding agent taking over related work: "
    "decisions made, constraints agreed on, work completed, and anything "
    "still in flight. Be concise (under 300 words). If nothing here is "
    "relevant to future coding work, reply with exactly: NOTHING"
)


async def summarize_recent_session(
    working_dir: Path, executable: str = "claude", timeout: float = 180.0
) -> str | None:
    """Ask the user's most recent interactive Claude session (for this
    project directory) to summarize itself. Returns None when there is no
    CLI, no session, or nothing relevant — callers treat that as "no
    context" and move on."""
    import shutil

    if shutil.which(executable) is None:
        return None
    process = await asyncio.create_subprocess_exec(
        executable, "-p", "--continue", _SUMMARY_PROMPT,
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return None
    if process.returncode != 0:
        return None
    summary = stdout.decode(errors="replace").strip()
    if not summary or summary == "NOTHING":
        return None
    return summary[:4000]


def _claude_stream_line(line: str) -> tuple[list[str], str | None]:
    """Turn one ``claude --output-format stream-json`` line into progress
    notes, plus the final result text when the line carries it."""
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return [], None
    if payload.get("type") == "result":
        return [], str(payload.get("result", ""))
    if payload.get("type") != "assistant":
        return [], None
    notes: list[str] = []
    for block in payload.get("message", {}).get("content", []):
        if block.get("type") == "text" and block.get("text", "").strip():
            notes.append(block["text"].strip().split("\n")[0][:_NOTE_LIMIT])
        elif block.get("type") == "tool_use":
            tool_input = block.get("input", {})
            hint = next(
                (str(tool_input[k]) for k in ("file_path", "path", "pattern", "command")
                 if k in tool_input),
                "",
            )
            notes.append(f"{block.get('name', 'tool')} {hint}".strip()[:_NOTE_LIMIT])
    return notes, None


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of a CLI reply that may add fences or prose."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise PlanError(f"no JSON object in plan reply: {text[:200]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        raise PlanError(f"invalid plan JSON: {error}") from error
