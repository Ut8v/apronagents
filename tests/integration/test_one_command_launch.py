"""The Phase 6 definition of done, minus the browser: one launcher boots all
organs, a task runs end to end through real sandbox git, the final result
lands in the working directory, and the tool stops with the sandbox gone."""

import asyncio

import httpx

from apron.bus.events import TaskReceived
from apron.config import Mode, Settings
from apron.launcher import Launcher


async def test_launch_task_handoff_stop(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("my project\n")
    launcher = Launcher(
        Settings(
            working_dir=project,
            user_dir=tmp_path / "home",
            mode=Mode.AUTONOMOUS,
            runner="demo",
            port=0,
            open_browser=False,
        )
    )

    await launcher.start()
    try:
        # The dashboard is served and reports the booted workers.
        port = launcher._server.servers[0].sockets[0].getsockname()[1]
        async with httpx.AsyncClient() as client:
            state = (await client.get(f"http://127.0.0.1:{port}/api/state")).json()
        assert len(state["workers"]) == launcher.settings.worker_count

        await launcher.bus.publish(TaskReceived(task_id="t1", prompt="run the demo"))
        await asyncio.wait_for(launcher.wait(), timeout=30)
    finally:
        sandbox_root = launcher.repo.root
        await launcher.stop()

    # The handoff is the only bridge to reality: the merged demo files are in
    # the working directory, and the disposable sandbox is gone.
    assert (project / "apron-demo" / "greeting.txt").exists()
    assert (project / "apron-demo" / "farewell.txt").exists()
    assert sorted(launcher.handed_off_files)[-1] == "apron-demo/greeting.txt"
    assert (project / "README.md").read_text() == "my project\n"  # untouched
    assert not sandbox_root.exists()
    assert not (project / ".git").exists()  # no real git was ever created
