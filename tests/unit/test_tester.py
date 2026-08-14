"""Tests for the candidate-merge tester."""

from pathlib import Path

from apron.merge.tester import CommandTester


async def test_no_command_configured_passes_everything(tmp_path: Path):
    report = await CommandTester(None).run(tmp_path)
    assert report.passed
    assert "no test command" in report.log_tail


async def test_zero_exit_is_green(tmp_path: Path):
    report = await CommandTester("exit 0").run(tmp_path)
    assert report.passed


async def test_nonzero_exit_is_red_with_the_log_tail(tmp_path: Path):
    report = await CommandTester("echo one failure; exit 1").run(tmp_path)
    assert not report.passed
    assert "one failure" in report.log_tail


async def test_command_runs_in_the_candidate_workdir(tmp_path: Path):
    (tmp_path / "expected.txt").write_text("x")
    report = await CommandTester("test -f expected.txt").run(tmp_path)
    assert report.passed


async def test_hung_test_suites_time_out_red(tmp_path: Path):
    report = await CommandTester("sleep 5", timeout=0.2).run(tmp_path)
    assert not report.passed
    assert "timed out" in report.log_tail
