"""Round trip through the whole sandbox layer: seed a project, work on a
branch in a clone, merge into sandbox main, and hand the result back."""

from pathlib import Path

from apron.sandbox.clone import WorkerClone
from apron.sandbox.handoff import handoff
from apron.sandbox.repo import SandboxRepo


def test_seed_work_merge_and_handoff(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("def run():\n    return 'v1'\n")

    with SandboxRepo.create(seed_dir=project) as repo:
        # A worker implements one issue on its own branch.
        worker = WorkerClone.create(repo, "worker-1")
        worker.create_branch("issue/i1")
        (worker.path / "app.py").write_text("def run():\n    return 'v2'\n")
        (worker.path / "test_app.py").write_text(
            "from app import run\n\ndef test_run():\n    assert run() == 'v2'\n"
        )
        worker.commit_all("Bump run to v2 with a test")
        worker.push_branch("issue/i1")

        # The merge controller merges that branch into sandbox main.
        controller = WorkerClone.create(repo, "merge-controller")
        controller.update_main()
        controller.run("merge", "--no-ff", "origin/issue/i1", "-m", "Merge issue/i1")
        controller.push_branch("main")

        copied = handoff(repo, project)

    assert sorted(copied) == ["app.py", "test_app.py"]
    assert "'v2'" in (project / "app.py").read_text()
    # The sandbox is gone; the project directory is all that remains.
    assert not repo.exists
