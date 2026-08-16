"""Chooses and assembles the execution backend: which runner powers the
workers, and the matching planner.

Auto-detection order mirrors what a user most likely already has: the
``claude`` CLI (any Claude plan), then the ``codex`` CLI (ChatGPT plan),
then direct API credentials, and finally the no-account demo loop.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Callable

from apron.agents.definition import AgentDefinition
from apron.orchestrator.planner import PlannedIssue, Planner, StaticPlanner
from apron.workers.api_runner import ApiPlanner, ApiRunner
from apron.workers.cli_runner import (
    CLAUDE_CODE_PROFILE,
    CODEX_PROFILE,
    CliAgentRunner,
    CliPlanner,
)
from apron.workers.runner import AgentRunner, FakeRunner

log = logging.getLogger(__name__)

_DEMO_ISSUES = [
    PlannedIssue("demo-greeting", "Add a demo greeting", "Write apron-demo/greeting.txt"),
    PlannedIssue("demo-farewell", "Add a demo farewell", "Write apron-demo/farewell.txt"),
]
_DEMO_OUTPUTS = {
    "demo-greeting": {"apron-demo/greeting.txt": "Hello from an Apron demo worker.\n"},
    "demo-farewell": {"apron-demo/farewell.txt": "Goodbye from an Apron demo worker.\n"},
}


def build_backend(
    choice: str,
    working_dir: Path,
    orchestrator_resolver: Callable[[], AgentDefinition],
    session_context: str | None = None,
) -> tuple[AgentRunner, Planner, str]:
    """Return ``(runner, planner, resolved_backend_name)`` for ``choice``."""
    if choice == "auto":
        choice = detect_backend()

    if choice == "claude-code":
        runner = CliAgentRunner(CLAUDE_CODE_PROFILE, session_context=session_context)
    elif choice == "codex":
        runner = CliAgentRunner(CODEX_PROFILE, session_context=session_context)
    elif choice == "api":
        api_runner = ApiRunner(session_context=session_context)
        planner = ApiPlanner(
            orchestrator_resolver,
            working_dir,
            client=api_runner.client,
            session_context=session_context,
        )
        return api_runner, planner, choice
    elif choice == "demo":
        log.warning(
            "no agent backend found: running the DEMO loop (fake agents). "
            "Install the claude or codex CLI, or set ANTHROPIC_API_KEY, "
            "for real agents."
        )
        planner = StaticPlanner(
            _DEMO_ISSUES,
            narration=(
                "reading the project…",
                "splitting into independent issues…",
            ),
            pace=0.7,
        )
        return FakeRunner(_DEMO_OUTPUTS), planner, choice
    else:
        raise ValueError(f"unknown runner {choice!r}")

    return (
        runner,
        CliPlanner(
            runner, orchestrator_resolver, working_dir, session_context=session_context
        ),
        choice,
    )


def detect_backend() -> str:
    if shutil.which(CLAUDE_CODE_PROFILE.executable):
        return "claude-code"
    if shutil.which(CODEX_PROFILE.executable):
        return "codex"
    try:
        # Resolves ANTHROPIC_API_KEY, auth tokens, or an `ant` profile;
        # raises when no credential source exists.
        ApiRunner()
        return "api"
    except Exception:
        return "demo"
