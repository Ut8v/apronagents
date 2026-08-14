"""Runs the test suite against a candidate merge and reports green or red.

This is the one place besides ``sandbox/git_ops.py`` allowed to spawn a
subprocess: it runs the project's own test command inside the merge clone,
which is not a git operation and never leaves the sandbox directory.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_TAIL_CHARS = 2000


@dataclass(frozen=True)
class TestReport:
    """The verdict on one candidate merge."""

    passed: bool
    log_tail: str = ""


class Tester(Protocol):
    """Anything that can judge a candidate working tree."""

    async def run(self, workdir: Path) -> TestReport: ...


class CommandTester:
    """Runs a configured shell command; exit code zero means green.

    With no command configured every candidate passes, which keeps the tool
    usable on projects without a test suite (the review gate still applies).
    """

    def __init__(self, command: str | None, timeout: float = 600.0) -> None:
        self.command = command
        self.timeout = timeout

    async def run(self, workdir: Path) -> TestReport:
        if not self.command:
            return TestReport(passed=True, log_tail="no test command configured")

        process = await asyncio.create_subprocess_shell(
            self.command,
            cwd=workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return TestReport(
                passed=False,
                log_tail=f"test command timed out after {self.timeout}s",
            )
        return TestReport(
            passed=process.returncode == 0,
            log_tail=output.decode(errors="replace")[-_TAIL_CHARS:],
        )
