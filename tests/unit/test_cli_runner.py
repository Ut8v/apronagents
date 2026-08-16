"""Tests for the CLI agent backend, using a fake agent executable."""

import json
import stat
from dataclasses import replace
from pathlib import Path

import pytest

from apron.agents.definition import AgentDefinition, AgentRole
from apron.orchestrator.planner import PlanError, PlannedIssue
from apron.workers.cli_runner import (
    CLAUDE_CODE_PROFILE,
    CODEX_PROFILE,
    CliAgentRunner,
    CliPlanner,
    _extract_json,
)

DEFINITION = AgentDefinition(
    name="worker-default",
    description="",
    role=AgentRole.WORKER,
    prompt="You are a careful worker.",
    model="claude-opus-5",
)

ISSUE = PlannedIssue("i1", "Add greeting", "Create greeting.txt")


def fake_cli(tmp_path: Path, script_body: str) -> Path:
    """A stand-in agent executable; records its argv and cwd."""
    path = tmp_path / "fake-agent"
    path.write_text("#!/bin/sh\n" + script_body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def claude_like(tmp_path: Path, script_body: str) -> CliAgentRunner:
    executable = fake_cli(tmp_path, script_body)
    return CliAgentRunner(replace(CLAUDE_CODE_PROFILE, executable=str(executable)))


async def test_runs_the_cli_in_the_clone_and_returns_its_summary(tmp_path: Path):
    workdir = tmp_path / "clone"
    workdir.mkdir()
    runner = claude_like(
        tmp_path,
        'printf "%s\\n" "$@" > args.txt\n'
        'echo "made it" > greeting.txt\n'
        'echo "I created greeting.txt"\n',
    )

    result = await runner.run_issue(DEFINITION, ISSUE, workdir)

    assert result.summary == "I created greeting.txt"
    # The CLI ran inside the clone: its files landed there.
    assert (workdir / "greeting.txt").read_text() == "made it\n"
    args = (workdir / "args.txt").read_text()
    assert "Add greeting" in args
    assert "You are a careful worker." in args  # system prompt passed through
    assert "--model\nclaude-opus-5" in args
    assert "Bash" in args  # workers may run tests; planning stays read-only


async def test_model_flag_is_skipped_for_foreign_models(tmp_path: Path):
    workdir = tmp_path / "clone"
    workdir.mkdir()
    runner = claude_like(tmp_path, 'printf "%s\\n" "$@" > args.txt\necho ok\n')
    definition = replace(DEFINITION, model="gpt-5.2-codex")

    await runner.run_issue(definition, ISSUE, workdir)
    assert "--model" not in (workdir / "args.txt").read_text()


async def test_codex_profile_reads_the_output_file(tmp_path: Path):
    workdir = tmp_path / "clone"
    workdir.mkdir()
    executable = fake_cli(
        tmp_path,
        # $5 is the {output} path in the codex work template.
        'echo "codex summary" > "$5"\necho "verbose progress logs"\n',
    )
    runner = CliAgentRunner(replace(CODEX_PROFILE, executable=str(executable)))

    result = await runner.run_issue(DEFINITION, ISSUE, workdir)
    assert result.summary == "codex summary"  # not the stdout noise


async def test_cli_failures_raise_with_stderr(tmp_path: Path):
    workdir = tmp_path / "clone"
    workdir.mkdir()
    runner = claude_like(tmp_path, 'echo "no credits" >&2\nexit 3\n')

    with pytest.raises(RuntimeError, match="no credits"):
        await runner.run_issue(DEFINITION, ISSUE, workdir)


async def test_hung_clis_time_out(tmp_path: Path):
    workdir = tmp_path / "clone"
    workdir.mkdir()
    executable = fake_cli(tmp_path, "sleep 5\n")
    runner = CliAgentRunner(
        replace(CLAUDE_CODE_PROFILE, executable=str(executable)), timeout=0.2
    )
    with pytest.raises(RuntimeError, match="timed out"):
        await runner.run_issue(DEFINITION, ISSUE, workdir)


async def test_planner_parses_the_json_plan(tmp_path: Path):
    plan = {
        "issues": [
            {"id": "one", "title": "One", "description": "d", "depends_on": []},
            {"id": "two", "title": "Two", "description": "d", "depends_on": ["one"]},
        ]
    }
    runner = claude_like(
        tmp_path, f"echo 'Here is the plan:\\n{json.dumps(plan)}'\n"
    )
    planner = CliPlanner(runner, lambda: DEFINITION, tmp_path)

    issues = await planner.plan("t1", "do the thing")
    assert [i.issue_id for i in issues] == ["one", "two"]
    assert issues[1].depends_on == ("one",)


def test_extract_json_tolerates_fences_and_rejects_prose():
    assert _extract_json('```json\n{"issues": []}\n```') == {"issues": []}
    with pytest.raises(PlanError, match="no JSON object"):
        _extract_json("I could not produce a plan.")


async def test_streaming_reports_notes_and_reads_the_result(tmp_path: Path):
    workdir = tmp_path / "clone"
    workdir.mkdir()
    lines = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Let me look at the project first."}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "tz.py"}}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "cli.py"}}]}},
        {"type": "result", "result": "Added the flag to cli.py."},
    ]
    script = "\n".join(f"echo '{json.dumps(l)}'" for l in lines) + "\n"
    runner = claude_like(tmp_path, script)

    notes = []

    async def on_progress(note):
        notes.append(note)

    result = await runner.run_issue(DEFINITION, ISSUE, workdir, on_progress=on_progress)

    assert result.summary == "Added the flag to cli.py."
    assert notes == [
        "Let me look at the project first.",
        "Read tz.py",
        "Edit cli.py",
    ]


async def test_without_a_callback_streaming_args_are_not_used(tmp_path: Path):
    workdir = tmp_path / "clone"
    workdir.mkdir()
    runner = claude_like(tmp_path, 'printf "%s\\n" "$@" > args.txt\necho done\n')
    await runner.run_issue(DEFINITION, ISSUE, workdir)
    assert "stream-json" not in (workdir / "args.txt").read_text()
