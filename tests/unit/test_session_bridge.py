"""Tests for the session bridge: interactive-session context flowing into
dispatch, and the run log flowing back out."""

import stat
from dataclasses import replace
from pathlib import Path

from apron.agents.definition import AgentDefinition, AgentRole
from apron.orchestrator.planner import PlannedIssue
from apron.sandbox.handoff import RunLogIssue, write_run_log
from apron.workers.cli_runner import (
    CLAUDE_CODE_PROFILE,
    CliAgentRunner,
    summarize_recent_session,
)

DEFINITION = AgentDefinition(
    name="worker-default", description="", role=AgentRole.WORKER,
    prompt="You are a careful worker.",
)
ISSUE = PlannedIssue("i1", "Add greeting", "Create greeting.txt")


def fake_cli(tmp_path: Path, script_body: str, name: str = "fake-claude") -> Path:
    path = tmp_path / name
    path.write_text("#!/bin/sh\n" + script_body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


# --- half 1: session context in ---------------------------------------------


async def test_summarize_returns_the_sessions_summary(tmp_path: Path):
    exe = fake_cli(tmp_path, 'echo "We agreed to use token buckets."\n')
    summary = await summarize_recent_session(tmp_path, executable=str(exe))
    assert summary == "We agreed to use token buckets."


async def test_summarize_handles_no_cli_no_session_and_nothing(tmp_path: Path):
    assert await summarize_recent_session(tmp_path, executable="not-a-real-cli") is None
    failing = fake_cli(tmp_path, "exit 1\n", name="failing")
    assert await summarize_recent_session(tmp_path, executable=str(failing)) is None
    nothing = fake_cli(tmp_path, 'echo "NOTHING"\n', name="nothing")
    assert await summarize_recent_session(tmp_path, executable=str(nothing)) is None


async def test_workers_receive_the_session_context(tmp_path: Path):
    workdir = tmp_path / "clone"
    workdir.mkdir()
    exe = fake_cli(tmp_path, 'printf "%s\\n" "$@" > args.txt\necho done\n')
    runner = CliAgentRunner(
        replace(CLAUDE_CODE_PROFILE, executable=str(exe)),
        session_context="We agreed to use token buckets.",
    )
    await runner.run_issue(DEFINITION, ISSUE, workdir)
    args = (workdir / "args.txt").read_text()
    assert "We agreed to use token buckets." in args
    assert "do not re-litigate" in args


# --- half 2: run log out ------------------------------------------------------


def test_run_log_records_the_whole_story(tmp_path: Path):
    path = write_run_log(
        tmp_path,
        task_prompt="Add a --utc flag",
        issues=[
            RunLogIssue("cli-utc-flag", "Add the flag", "Added --utc to cli.py."),
            RunLogIssue("docs", "Document it"),
        ],
        files=["cli.py", "README.md"],
    )
    assert path == tmp_path / ".apron" / "last-run.md"
    text = path.read_text()
    assert "Add a --utc flag" in text
    assert "**cli-utc-flag** — Add the flag" in text
    assert "Added --utc to cli.py." in text
    assert "- `cli.py`" in text
    assert "interactive Claude" in text  # the catch-up note for the next session
