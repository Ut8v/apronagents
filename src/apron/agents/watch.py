"""Hot-reloads agent definitions on file change.

A dependency-free mtime poller: it watches the ``agents/`` directories and
fires a callback when any ``*.md`` appears, disappears, or changes, so a
saved edit takes effect on the next issue without restarting the tool.
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Awaitable, Callable

OnChange = Callable[[], None | Awaitable[None]]


class AgentWatcher:
    """Polls agent directories and fires ``on_change`` when they differ."""

    def __init__(
        self,
        directories: list[Path],
        on_change: OnChange,
        interval: float = 1.0,
    ) -> None:
        self.directories = directories
        self.on_change = on_change
        self.interval = interval
        self._running = False
        self._last = self._snapshot()

    def _snapshot(self) -> dict[Path, int]:
        files: dict[Path, int] = {}
        for directory in self.directories:
            if not directory.is_dir():
                continue
            for path in directory.glob("*.md"):
                try:
                    files[path] = path.stat().st_mtime_ns
                except OSError:
                    continue  # deleted between glob and stat
        return files

    async def check(self) -> bool:
        """One poll: fire ``on_change`` if anything moved. Returns whether it did."""
        current = self._snapshot()
        if current == self._last:
            return False
        self._last = current
        result = self.on_change()
        if inspect.isawaitable(result):
            await result
        return True

    async def run(self) -> None:
        """Poll until :meth:`stop` is called."""
        self._running = True
        while self._running:
            await asyncio.sleep(self.interval)
            await self.check()

    def stop(self) -> None:
        self._running = False
