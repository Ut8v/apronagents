"""Tests for the audited git wrapper: the no-real-remote invariant lives here."""

from pathlib import Path

import pytest

from apron.sandbox.git_ops import GitOps, GitError, RemoteAccessViolation


@pytest.fixture
def sandbox(tmp_path: Path) -> GitOps:
    return GitOps(tmp_path)


def test_runs_git_inside_the_sandbox(sandbox: GitOps, tmp_path: Path):
    result = sandbox.run("init", "--initial-branch=main", str(tmp_path / "repo"), cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "repo" / ".git").is_dir()


def test_failed_commands_raise_git_error(sandbox: GitOps, tmp_path: Path):
    with pytest.raises(GitError):
        sandbox.run("log", cwd=tmp_path)  # not a repository


def test_rejects_running_outside_the_sandbox(sandbox: GitOps, tmp_path: Path):
    with pytest.raises(RemoteAccessViolation):
        sandbox.run("status", cwd=tmp_path.parent)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/someone/repo.git",
        "http://example.com/repo",
        "ssh://git@github.com/x/y.git",
        "git://example.com/repo.git",
        "git@github.com:someone/repo.git",
    ],
)
def test_rejects_remote_urls_everywhere(sandbox: GitOps, tmp_path: Path, url: str):
    for command in (("clone", url, "dest"), ("push", url, "main"), ("fetch", url)):
        with pytest.raises(RemoteAccessViolation):
            sandbox.run(*command, cwd=tmp_path)


def test_clone_may_not_reach_outside_the_sandbox(sandbox: GitOps, tmp_path: Path):
    with pytest.raises(RemoteAccessViolation):
        sandbox.run("clone", "/somewhere/else/repo.git", "dest", cwd=tmp_path)
    with pytest.raises(RemoteAccessViolation):
        sandbox.run("clone", "origin.git", "../../escape", cwd=tmp_path)


@pytest.mark.parametrize("subcommand", ["push", "fetch", "pull", "ls-remote"])
def test_remote_commands_may_only_address_origin(
    sandbox: GitOps, tmp_path: Path, subcommand: str
):
    with pytest.raises(RemoteAccessViolation):
        sandbox.run(subcommand, "upstream", cwd=tmp_path)
    with pytest.raises(RemoteAccessViolation):
        sandbox.run(subcommand, "/outside/path.git", cwd=tmp_path)


def test_remotes_can_be_listed_but_never_edited(sandbox: GitOps, tmp_path: Path):
    repo = tmp_path / "repo"
    sandbox.run("init", "--initial-branch=main", str(repo), cwd=tmp_path)
    assert sandbox.run("remote", "-v", cwd=repo).returncode == 0
    for mutation in (
        ("remote", "add", "upstream", str(tmp_path / "other.git")),
        ("remote", "set-url", "origin", str(tmp_path / "other.git")),
        ("remote", "rename", "origin", "upstream"),
        ("remote", "remove", "origin"),
    ):
        with pytest.raises(RemoteAccessViolation):
            sandbox.run(*mutation, cwd=repo)


def test_config_and_submodule_are_rejected(sandbox: GitOps, tmp_path: Path):
    with pytest.raises(RemoteAccessViolation):
        sandbox.run("config", "remote.origin.url", "https://x", cwd=tmp_path)
    with pytest.raises(RemoteAccessViolation):
        sandbox.run("submodule", "add", str(tmp_path / "x"), cwd=tmp_path)


@pytest.mark.parametrize(
    "option",
    [
        "-C",
        "--git-dir=/elsewhere",
        "--work-tree=/elsewhere",
        "--upload-pack=/bin/sh",
        "--receive-pack=/bin/sh",
    ],
)
def test_dangerous_options_are_rejected(sandbox: GitOps, tmp_path: Path, option: str):
    with pytest.raises(RemoteAccessViolation):
        sandbox.run("status", option, cwd=tmp_path)


@pytest.mark.parametrize("option", ["-c", "--config", "--config=url.a.insteadOf=b"])
def test_inline_config_is_rejected_wherever_a_remote_is_involved(
    sandbox: GitOps, tmp_path: Path, option: str
):
    # url.*.insteadOf could silently re-point "origin" outside the sandbox.
    with pytest.raises(RemoteAccessViolation):
        sandbox.run("clone", option, "origin.git", "dest", cwd=tmp_path)
    with pytest.raises(RemoteAccessViolation):
        sandbox.run("fetch", option, "origin", cwd=tmp_path)


def test_environment_is_isolated(sandbox: GitOps):
    env = sandbox._environment()
    assert env["GIT_ALLOW_PROTOCOL"] == "file"
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["HOME"] == str(sandbox.root)  # user gitconfig can't leak in
    assert "GIT_CONFIG_NOSYSTEM" in env


def test_subprocess_is_confined_to_audited_modules():
    """Only four modules may spawn processes: the audited git wrapper, the
    tester that runs the project's own test command, the CLI runner that
    drives the user's chosen agent CLI, and the task source that reads
    GitHub issues through ``gh``. None of them runs unaudited git."""
    package_root = Path(__file__).parents[2] / "src" / "apron"
    allowed = {
        package_root / "sandbox" / "git_ops.py",
        package_root / "merge" / "tester.py",
        package_root / "workers" / "cli_runner.py",
        package_root / "orchestrator" / "sources.py",
    }
    offenders = [
        path.relative_to(package_root)
        for path in package_root.rglob("*.py")
        if "subprocess" in path.read_text() and path not in allowed
    ]
    assert offenders == []
