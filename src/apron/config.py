"""Settings, paths, defaults, and the supervised/autonomous mode toggle."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Mode(StrEnum):
    """Whether merges wait for a human click or proceed on green tests."""

    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4650
DEFAULT_WORKER_COUNT = 3


@dataclass(frozen=True)
class Settings:
    """Everything configurable about one Apron run.

    ``working_dir`` is the user's real project directory: the place agents
    read the task's context from and the target of the final handoff. The
    sandbox itself lives in a separate temp dir owned by the sandbox layer.
    """

    working_dir: Path
    mode: Mode = Mode.SUPERVISED
    worker_count: int = DEFAULT_WORKER_COUNT
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    # None means an in-memory store (fine for one run; the sandbox is
    # disposable anyway). Set a path to keep state across a crash.
    db_path: Path | None = None
    # Shell command the merge controller runs against every candidate merge;
    # None accepts every candidate (the review gate still applies).
    test_command: str | None = None
    # Which execution backend powers the agents:
    #   auto        - claude CLI if installed, else codex CLI, else the API
    #                 if credentials resolve, else the demo loop
    #   claude-code - the `claude` CLI (any Claude plan, no API key needed)
    #   codex       - the `codex` CLI (ChatGPT plan or OpenAI key)
    #   api         - the Anthropic API directly
    #   demo        - fake agents, for trying the tool without any account
    runner: str = "auto"
    # Before planning, ask the project's most recent interactive Claude
    # session to summarize itself and inject that into planner and worker
    # prompts. Opt-in: it reads (a summary of) your session transcript.
    with_session_context: bool = False
    open_browser: bool = True
    user_dir: Path = field(default_factory=lambda: Path.home())

    @property
    def dashboard_url(self) -> str:
        """The URL shown to humans (and opened in the browser). The server
        still binds to ``host`` as-is; this only prettifies loopback."""
        shown = "localhost" if self.host in ("127.0.0.1", "0.0.0.0") else self.host
        return f"http://{shown}:{self.port}"

    @property
    def project_apron_dir(self) -> Path:
        """Project-level overlay: ``.apron/`` in the working dir. Writable."""
        return self.working_dir / ".apron"

    @property
    def user_apron_dir(self) -> Path:
        """User-level overlay: ``~/.apron/``. Writable."""
        return self.user_dir / ".apron"

    @property
    def project_claude_dir(self) -> Path:
        """Project-level Claude Code config: ``.claude/``. Read-only, always."""
        return self.working_dir / ".claude"

    @property
    def user_claude_dir(self) -> Path:
        """User-level Claude Code config: ``~/.claude/``. Read-only, always."""
        return self.user_dir / ".claude"


def load_settings(
    working_dir: Path | None = None,
    mode: str | None = None,
    port: int | None = None,
    worker_count: int | None = None,
    test_command: str | None = None,
    runner: str | None = None,
    with_session_context: bool | None = None,
    open_browser: bool | None = None,
) -> Settings:
    """Build settings from explicit arguments, then environment, then defaults.

    Environment variables (``APRON_MODE``, ``APRON_PORT``, ``APRON_WORKERS``,
    ``APRON_TEST_COMMAND``, ``APRON_RUNNER``) fill in anything the caller
    left unset.
    """
    env = os.environ
    resolved_mode = mode or env.get("APRON_MODE", Mode.SUPERVISED)
    return Settings(
        working_dir=(working_dir or Path.cwd()).resolve(),
        mode=Mode(resolved_mode),
        worker_count=worker_count or int(env.get("APRON_WORKERS", DEFAULT_WORKER_COUNT)),
        port=port or int(env.get("APRON_PORT", DEFAULT_PORT)),
        test_command=test_command or env.get("APRON_TEST_COMMAND"),
        runner=runner or env.get("APRON_RUNNER", "auto"),
        with_session_context=(
            env.get("APRON_SESSION_CONTEXT", "") == "1"
            if with_session_context is None
            else with_session_context
        ),
        open_browser=True if open_browser is None else open_browser,
    )
