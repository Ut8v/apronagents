"""Runner backend that drives the ``claude`` CLI running a chosen agent
definition inside the sandbox.

A worker becomes a headless Claude Code session using whatever login and
plan the user already has — no API key required — wrapped in Apron's
sandbox, merge control, and dashboard. The generic CLI mechanics live in
:mod:`apron.workers.cli_runner`; this module pins the Claude Code profile.
"""

from __future__ import annotations

from apron.workers.cli_runner import CLAUDE_CODE_PROFILE, CliAgentRunner


class ClaudeCodeRunner(CliAgentRunner):
    """A worker backend that is a headless Claude Code session."""

    def __init__(self, timeout: float = 3600.0) -> None:
        super().__init__(CLAUDE_CODE_PROFILE, timeout=timeout)
