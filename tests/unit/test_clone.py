"""Tests for per-worker clones collaborating through the bare repo."""

import pytest

from apron.sandbox.clone import WorkerClone
from apron.sandbox.repo import SandboxRepo


@pytest.fixture
def repo():
    with SandboxRepo.create() as sandbox_repo:
        yield sandbox_repo


def test_clone_lands_under_the_sandbox_root(repo: SandboxRepo):
    clone = WorkerClone.create(repo, "worker-1")
    assert clone.path == repo.root / "clones" / "worker-1"
    assert clone.current_branch() == "main"


def test_branch_commit_push_reaches_the_bare_repo(repo: SandboxRepo):
    clone = WorkerClone.create(repo, "worker-1")
    clone.create_branch("issue/i1")
    (clone.path / "feature.py").write_text("def feature():\n    return 1\n")
    sha = clone.commit_all("Add feature")

    clone.push_branch("issue/i1")

    assert "issue/i1" in repo.branches()
    bare_sha = repo.git.run(
        "rev-parse", "issue/i1", cwd=repo.bare_path
    ).stdout.strip()
    assert bare_sha == sha


def test_two_clones_are_isolated_until_they_push(repo: SandboxRepo):
    first = WorkerClone.create(repo, "worker-1")
    second = WorkerClone.create(repo, "worker-2")

    first.create_branch("issue/i1")
    (first.path / "one.txt").write_text("one\n")
    first.commit_all("Add one")

    # Nothing pushed yet: worker-2 sees no trace of worker-1's work.
    second.fetch()
    assert "issue/i1" not in second.run("branch", "-r").stdout

    first.push_branch("issue/i1")
    second.fetch()
    assert "origin/issue/i1" in second.run("branch", "-r").stdout
    assert not (second.path / "one.txt").exists()


def test_update_main_fast_forwards_from_origin(repo: SandboxRepo):
    writer = WorkerClone.create(repo, "worker-1")
    reader = WorkerClone.create(repo, "worker-2")

    (writer.path / "shared.txt").write_text("v1\n")
    writer.commit_all("Add shared file")
    writer.push_branch("main")

    reader.update_main()
    assert (reader.path / "shared.txt").read_text() == "v1\n"
