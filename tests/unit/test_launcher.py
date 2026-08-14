"""Tests for the launcher's boot, wiring, and clean shutdown."""

from pathlib import Path

import pytest

from apron.bus.events import IssueQueued, IssueState
from apron.config import Settings
from apron.launcher import Launcher


def demo_settings(tmp_path: Path) -> Settings:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    (project / "README.md").write_text("demo\n")
    return Settings(
        working_dir=project,
        user_dir=tmp_path / "home",
        runner="demo",
        port=0,  # random free port
        open_browser=False,
    )


@pytest.fixture
async def launcher(tmp_path: Path):
    instance = Launcher(demo_settings(tmp_path))
    await instance.start()
    yield instance
    await instance.stop()


async def test_boot_wires_all_organs(launcher: Launcher):
    assert launcher.repo is not None and launcher.repo.exists
    assert len(launcher.workers) == launcher.settings.worker_count
    assert launcher.controller is not None
    assert launcher._server is not None and launcher._server.started
    # Every worker runs a definition resolved through discovery.
    assert launcher.workers[0].definition.name == "worker-default"


async def test_published_events_land_in_the_store(launcher: Launcher):
    await launcher.bus.publish(
        IssueQueued(issue_id="i1", task_id="t1", title="x", description="y")
    )
    assert launcher.store.issue("i1").state is IssueState.QUEUED


async def test_stop_tears_everything_down(tmp_path: Path):
    instance = Launcher(demo_settings(tmp_path))
    await instance.start()
    sandbox_root = instance.repo.root
    await instance.stop()

    assert not sandbox_root.exists()  # temp dir destroyed on exit
    # After shutdown the bus must not deliver into a closed store.
    await instance.bus.publish(
        IssueQueued(issue_id="i1", task_id="t1", title="x", description="y")
    )
