"""Tests for the handoff: the one bridge from sandbox to working directory."""

from pathlib import Path

import pytest

from apron.sandbox.clone import WorkerClone
from apron.sandbox.handoff import handoff
from apron.sandbox.repo import SandboxRepo


@pytest.fixture
def repo():
    with SandboxRepo.create() as sandbox_repo:
        clone = WorkerClone.create(sandbox_repo, "worker-1")
        (clone.path / "pkg").mkdir()
        (clone.path / "pkg" / "module.py").write_text("VALUE = 2\n")
        (clone.path / "README.md").write_text("updated\n")
        clone.commit_all("Finish the task")
        clone.push_branch("main")
        yield sandbox_repo


def test_handoff_copies_the_merged_tree(repo: SandboxRepo, tmp_path: Path):
    target = tmp_path / "project"
    target.mkdir()

    copied = handoff(repo, target)

    assert copied == ["README.md", "pkg/module.py"]
    assert (target / "pkg" / "module.py").read_text() == "VALUE = 2\n"


def test_handoff_overwrites_but_never_deletes(repo: SandboxRepo, tmp_path: Path):
    target = tmp_path / "project"
    target.mkdir()
    (target / "README.md").write_text("stale\n")
    (target / "untracked-notes.txt").write_text("keep me\n")

    handoff(repo, target)

    assert (target / "README.md").read_text() == "updated\n"
    assert (target / "untracked-notes.txt").read_text() == "keep me\n"


def test_handoff_never_touches_the_targets_git(repo: SandboxRepo, tmp_path: Path):
    target = tmp_path / "project"
    (target / ".git").mkdir(parents=True)
    (target / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    copied = handoff(repo, target)

    assert (target / ".git" / "HEAD").read_text() == "ref: refs/heads/main\n"
    assert all(not path.startswith(".git") for path in copied)


def test_handoff_leaves_no_export_residue_in_the_sandbox(repo: SandboxRepo, tmp_path: Path):
    target = tmp_path / "project"
    target.mkdir()
    handoff(repo, target)
    assert not (repo.root / "export").exists()
