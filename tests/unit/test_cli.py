"""Tests for the command-line dispatch paths."""

from pathlib import Path

from apron.cli import build_parser, main, send_task
from apron.config import Mode, Settings
from apron.launcher import Launcher


def test_start_accepts_a_task_argument():
    args = build_parser().parse_args(
        ["start", "add", "dark", "mode", "--runner", "demo"]
    )
    assert " ".join(args.task) == "add dark mode"
    assert args.runner == "demo"


def test_task_subcommand_parses_prompt_and_port():
    args = build_parser().parse_args(["task", "fix", "the", "bug", "--port", "4700"])
    assert " ".join(args.prompt) == "fix the bug"
    assert args.port == 4700


def test_task_against_nothing_fails_politely(capsys):
    exit_code = main(["task", "hello", "--port", "1"])  # nothing listens on 1
    assert exit_code == 1
    assert "apron start" in capsys.readouterr().out


async def test_send_task_reaches_a_running_apron(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("x\n")
    launcher = Launcher(
        Settings(
            working_dir=project,
            user_dir=tmp_path / "home",
            runner="demo",
            mode=Mode.AUTONOMOUS,  # no plan gate: these test dispatch plumbing
            port=0,
            open_browser=False,
        )
    )
    await launcher.start()
    try:
        port = launcher._server.servers[0].sockets[0].getsockname()[1]
        import asyncio

        task_id = await asyncio.to_thread(send_task, "run the demo", "127.0.0.1", port)
        assert len(task_id) == 8
        # Planning runs in the background so the dispatch returns instantly;
        # wait for the plan to land.
        await _wait_for_issues(launcher)
        assert launcher.store.issues()  # the terminal dispatch became issues
    finally:
        await launcher.stop()


async def test_start_with_initial_task_dispatches_on_boot(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("x\n")
    launcher = Launcher(
        Settings(
            working_dir=project,
            user_dir=tmp_path / "home",
            runner="demo",
            mode=Mode.AUTONOMOUS,  # no plan gate: these test dispatch plumbing
            port=0,
            open_browser=False,
        ),
        initial_task="run the demo",
    )
    await launcher.start()
    try:
        await _wait_for_issues(launcher)
        assert launcher.store.issues()  # the boot task became issues
    finally:
        await launcher.stop()


async def _wait_for_issues(launcher, timeout: float = 5.0) -> None:
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    while not launcher.store.issues():
        if asyncio.get_event_loop().time() > deadline:
            return
        await asyncio.sleep(0.1)


def test_planning_lines_reports_only_new_notes():
    from apron.cli import planning_lines

    lines, seen = planning_lines(0, {"active": True, "notes": ["a", "b"]})
    assert lines == ["  ▸ planner · a", "  ▸ planner · b"]

    lines, seen = planning_lines(seen, {"active": True, "notes": ["a", "b", "c"]})
    assert lines == ["  ▸ planner · c"]

    lines, seen = planning_lines(seen, {"active": False, "notes": []})
    assert lines == []

    # A fresh task starts a fresh note list; the counter must reset with it.
    lines, seen = planning_lines(3, {"active": True, "notes": ["x"]})
    assert lines == ["  ▸ planner · x"]


def test_dashboard_url_shows_localhost_for_loopback(tmp_path: Path):
    from apron.config import Settings

    loop = Settings(working_dir=tmp_path, host="127.0.0.1", port=4650)
    assert loop.dashboard_url == "http://localhost:4650"
    lan = Settings(working_dir=tmp_path, host="192.168.1.20", port=4650)
    assert lan.dashboard_url == "http://192.168.1.20:4650"


def test_task_parses_from_issue_flags():
    args = build_parser().parse_args(["task", "--from-issue", "12", "--from-issue", "37"])
    assert args.from_issue == [12, 37]
    assert args.prompt == []


def test_task_requires_prompt_or_issues_not_both(capsys):
    assert main(["task"]) == 2
    assert main(["task", "do it", "--from-issue", "3"]) == 2
    assert "either a task description or --from-issue" in capsys.readouterr().out


def test_settings_persist_the_journal_under_dot_apron(tmp_path: Path):
    from apron.config import load_settings

    settings = load_settings(working_dir=tmp_path)
    assert settings.db_path == tmp_path.resolve() / ".apron" / "runs.db"


def test_report_lists_runs_and_prints_one(tmp_path: Path, capsys):
    from apron.bus.events import HandoffCompleted, TaskReceived
    from apron.bus.store import StateStore

    db = tmp_path / ".apron" / "runs.db"
    db.parent.mkdir()
    store = StateStore(db)
    store.record(TaskReceived(task_id="abc12345", prompt="add dark mode"))
    store.record(HandoffCompleted(task_id="abc12345", target_dir="/p", files=("a.py",)))
    store.close()

    assert main(["report", "--dir", str(tmp_path)]) == 0
    listing = capsys.readouterr().out
    assert "abc12345" in listing and "completed" in listing and "add dark mode" in listing

    assert main(["report", "abc", "--dir", str(tmp_path)]) == 0
    report = capsys.readouterr().out
    assert report.startswith("# Apron run abc12345")
    assert "add dark mode" in report

    assert main(["report", "zzz", "--dir", str(tmp_path)]) == 1


def test_report_without_history_fails_politely(tmp_path: Path, capsys):
    assert main(["report", "--dir", str(tmp_path)]) == 1
    assert "no run history yet" in capsys.readouterr().out
