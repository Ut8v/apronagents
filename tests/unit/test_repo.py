"""Tests for the sandbox temp-dir and bare-repo lifecycle."""

from pathlib import Path

from apron.sandbox.repo import SandboxRepo


def test_create_builds_bare_repo_in_a_temp_dir():
    repo = SandboxRepo.create()
    try:
        assert repo.exists
        assert repo.root.name.startswith("apron-sandbox-")
        assert (repo.bare_path / "HEAD").is_file()
        assert repo.branches() == ["main"]
    finally:
        repo.destroy()


def test_destroy_removes_everything():
    repo = SandboxRepo.create()
    root = repo.root
    repo.destroy()
    assert not root.exists()
    repo.destroy()  # calling again is harmless


def test_context_manager_destroys_on_exit():
    with SandboxRepo.create() as repo:
        root = repo.root
        assert repo.exists
    assert not root.exists()


def test_context_manager_destroys_on_exception():
    root: Path | None = None
    try:
        with SandboxRepo.create() as repo:
            root = repo.root
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert root is not None and not root.exists()


def test_seeding_imports_project_files_but_not_git_state(tmp_path: Path):
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "module.py").write_text("VALUE = 1\n")
    (project / "README.md").write_text("hello\n")
    (project / ".git").mkdir()
    (project / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (project / ".venv").mkdir()
    (project / ".venv" / "junk").write_text("x")

    with SandboxRepo.create(seed_dir=project) as repo:
        listing = repo.git.run(
            "ls-tree", "-r", "--name-only", "main", cwd=repo.bare_path
        ).stdout.splitlines()
        assert sorted(listing) == ["README.md", "pkg/module.py"]


def test_unseeded_sandbox_still_has_a_main_to_branch_from():
    with SandboxRepo.create() as repo:
        log = repo.git.run("log", "--oneline", "main", cwd=repo.bare_path).stdout
        assert "Initialize sandbox" in log
