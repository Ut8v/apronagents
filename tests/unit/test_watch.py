"""Tests for the agent-definition hot-reload watcher."""

import os
from pathlib import Path

from apron.agents.watch import AgentWatcher


def write_agent(directory: Path, name: str, body: str = "Prompt.") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.md"
    path.write_text(f"---\nname: {name}\n---\n{body}\n")
    return path


async def test_no_change_means_no_callback(tmp_path: Path):
    write_agent(tmp_path, "worker")
    fired = []
    watcher = AgentWatcher([tmp_path], lambda: fired.append(True))
    assert await watcher.check() is False
    assert fired == []


async def test_modification_fires_the_callback(tmp_path: Path):
    path = write_agent(tmp_path, "worker")
    watcher = AgentWatcher([tmp_path], lambda: None)
    os.utime(path, ns=(1, 1))  # force a visible mtime change
    assert await watcher.check() is True
    assert await watcher.check() is False  # settled again


async def test_new_and_deleted_files_are_both_changes(tmp_path: Path):
    watcher = AgentWatcher([tmp_path], lambda: None)
    path = write_agent(tmp_path, "fresh")
    assert await watcher.check() is True
    path.unlink()
    assert await watcher.check() is True


async def test_async_callbacks_are_awaited(tmp_path: Path):
    fired = []

    async def on_change():
        fired.append(True)

    watcher = AgentWatcher([tmp_path], on_change)
    write_agent(tmp_path, "worker")
    await watcher.check()
    assert fired == [True]


async def test_watching_a_missing_directory_is_fine(tmp_path: Path):
    watcher = AgentWatcher([tmp_path / "not-there"], lambda: None)
    assert await watcher.check() is False
