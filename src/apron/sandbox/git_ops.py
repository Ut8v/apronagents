"""The single audited wrapper over the git subprocess.

Every raw git invocation in Apron goes through :class:`GitOps`, which is what
makes the no-real-remote invariant auditable in one place. The wrapper is
scoped to one sandbox root directory and refuses, by construction, anything
that could reach outside it:

- every command must run with a working directory inside the sandbox root;
- URL-shaped arguments (``scheme://`` or ``user@host:``) are rejected;
- ``clone`` may only connect two paths inside the sandbox root;
- ``push``, ``fetch``, ``pull``, and ``ls-remote`` may only address the
  ``origin`` created by that clone;
- ``config``, ``remote`` mutations, ``submodule``, and command-executing
  options are rejected;
- the subprocess runs with an isolated ``HOME`` and ``GIT_ALLOW_PROTOCOL=file``
  so no user config, credential helper, or network protocol can leak in.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(Exception):
    """A git invocation failed."""


class RemoteAccessViolation(GitError):
    """An invocation would have reached outside the sandbox. Never allowed."""


_URL_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_SCP_PATTERN = re.compile(r"^[^/@]+@[^/:]+:")

# Subcommands with no legitimate use inside the sandbox.
_BLOCKED_SUBCOMMANDS = {"config", "submodule", "daemon", "credential", "instaweb"}

# Subcommands that talk to a "remote" (always our local bare repo).
_REMOTE_SUBCOMMANDS = {"push", "fetch", "pull", "ls-remote"}

# Options that would execute arbitrary commands or re-point git elsewhere.
_BLOCKED_OPTIONS = {"-c", "-C"}
_BLOCKED_OPTION_PREFIXES = (
    "--upload-pack",
    "--receive-pack",
    "--exec",
    "--config-env",
    "--git-dir",
    "--work-tree",
)

# What the audited environment allows a remote listing to do: read, only.
_ALLOWED_REMOTE_QUERIES = ("", "-v", "--verbose", "show", "get-url")


@dataclass(frozen=True)
class GitResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class GitOps:
    """Audited git runner scoped to one sandbox root."""

    def __init__(self, sandbox_root: Path) -> None:
        self.root = sandbox_root.resolve()

    def run(self, *args: str, cwd: Path, check: bool = True) -> GitResult:
        """Run one git command inside the sandbox, auditing it first."""
        arg_list = [str(a) for a in args]
        cwd = Path(cwd).resolve()
        self._audit(arg_list, cwd)

        completed = subprocess.run(
            ["git", *arg_list],
            cwd=cwd,
            env=self._environment(),
            capture_output=True,
            text=True,
        )
        result = GitResult(
            args=tuple(arg_list),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and result.returncode != 0:
            raise GitError(
                f"git {' '.join(arg_list)} failed ({result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return result

    # --- auditing ------------------------------------------------------------

    def _audit(self, args: list[str], cwd: Path) -> None:
        if not args:
            raise GitError("empty git invocation")
        if not self._inside_root(cwd):
            raise RemoteAccessViolation(
                f"git must run inside the sandbox, not {cwd}"
            )

        for arg in args:
            if _URL_PATTERN.match(arg) or _SCP_PATTERN.match(arg):
                raise RemoteAccessViolation(f"remote URL rejected: {arg!r}")
            if arg in _BLOCKED_OPTIONS or arg.startswith(_BLOCKED_OPTION_PREFIXES):
                raise RemoteAccessViolation(f"option rejected: {arg!r}")

        subcommand = args[0]
        if subcommand in _BLOCKED_SUBCOMMANDS:
            raise RemoteAccessViolation(f"subcommand rejected: {subcommand!r}")
        if subcommand == "clone":
            self._audit_clone(args, cwd)
        elif subcommand in _REMOTE_SUBCOMMANDS:
            self._audit_remote_use(args)
        elif subcommand == "remote":
            self._audit_remote_listing(args)

    def _audit_clone(self, args: list[str], cwd: Path) -> None:
        for target in self._positionals(args)[1:]:
            resolved = (cwd / Path(target).expanduser()).resolve()
            if not self._inside_root(resolved):
                raise RemoteAccessViolation(
                    f"clone may only touch the sandbox, not {resolved}"
                )

    def _audit_remote_use(self, args: list[str]) -> None:
        positionals = self._positionals(args)[1:]
        if positionals and positionals[0] != "origin":
            raise RemoteAccessViolation(
                f"only the sandbox 'origin' may be addressed, not {positionals[0]!r}"
            )

    def _audit_remote_listing(self, args: list[str]) -> None:
        rest = args[1:]
        if rest and rest[0] not in _ALLOWED_REMOTE_QUERIES:
            raise RemoteAccessViolation(
                f"'git remote {rest[0]}' is not allowed; remotes are never edited"
            )

    def _inside_root(self, path: Path) -> bool:
        return path == self.root or self.root in path.parents

    @staticmethod
    def _positionals(args: list[str]) -> list[str]:
        return [a for a in args if not a.startswith("-")]

    # --- environment ---------------------------------------------------------

    def _environment(self) -> dict[str, str]:
        """A minimal env: no user config, no credentials, file protocol only."""
        return {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.root),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ALLOW_PROTOCOL": "file",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "Apron Sandbox",
            "GIT_AUTHOR_EMAIL": "sandbox@apron.invalid",
            "GIT_COMMITTER_NAME": "Apron Sandbox",
            "GIT_COMMITTER_EMAIL": "sandbox@apron.invalid",
        }
