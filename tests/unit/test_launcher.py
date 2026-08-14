"""Tests that the launcher wires the store to the bus."""

from pathlib import Path

from apron.bus.events import IssueQueued, IssueState
from apron.config import Settings
from apron.launcher import Launcher


async def test_published_events_land_in_the_store(tmp_path: Path):
    launcher = Launcher(Settings(working_dir=tmp_path))
    await launcher.start()

    await launcher.bus.publish(
        IssueQueued(issue_id="i1", task_id="t1", title="x", description="y")
    )

    assert launcher.store.issue("i1").state is IssueState.QUEUED
    await launcher.stop()


async def test_stop_detaches_the_store(tmp_path: Path):
    launcher = Launcher(Settings(working_dir=tmp_path))
    await launcher.start()
    await launcher.stop()

    # After shutdown the bus must not deliver into a closed store.
    await launcher.bus.publish(
        IssueQueued(issue_id="i1", task_id="t1", title="x", description="y")
    )
