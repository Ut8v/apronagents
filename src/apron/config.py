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
    open_browser: bool = True
    user_dir: Path = field(default_factory=lambda: Path.home())

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
    open_browser: bool | None = None,
) -> Settings:
    """Build settings from explicit arguments, then environment, then defaults.

    Environment variables (``APRON_MODE``, ``APRON_PORT``, ``APRON_WORKERS``)
    fill in anything the caller left unset.
    """
    env = os.environ
    resolved_mode = mode or env.get("APRON_MODE", Mode.SUPERVISED)
    return Settings(
        working_dir=(working_dir or Path.cwd()).resolve(),
        mode=Mode(resolved_mode),
        worker_count=worker_count or int(env.get("APRON_WORKERS", DEFAULT_WORKER_COUNT)),
        port=port or int(env.get("APRON_PORT", DEFAULT_PORT)),
        open_browser=True if open_browser is None else open_browser,
    )
