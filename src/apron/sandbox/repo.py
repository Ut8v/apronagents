"""Creates the sandbox bare repo in a temp dir and tears it all down on exit.

The bare repo is the "fake GitHub" every worker clone and the merge
controller push to and fetch from. It lives with everything else sandbox-
related under one disposable temp directory, so teardown is a single rmtree.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from apron.sandbox.git_ops import GitOps

# Never dragged into the sandbox when seeding from the user's project.
_IGNORED_SEED_ENTRIES = {
    ".git",
    ".apron",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
}


class SandboxRepo:
    """One disposable sandbox: a temp dir owning a bare repo and its clones."""

    def __init__(self, root: Path, git: GitOps, bare_path: Path) -> None:
        self.root = root
        self.git = git
        self.bare_path = bare_path

    @classmethod
    def create(cls, seed_dir: Path | None = None) -> "SandboxRepo":
        """Make the temp dir and bare repo, seeded with an initial commit.

        With ``seed_dir`` given, the user's project files (minus git state,
        envs, and caches) become the initial commit on ``main``; otherwise
        ``main`` starts from an empty commit so branches always have a base.
        """
        root = Path(tempfile.mkdtemp(prefix="apron-sandbox-")).resolve()
        git = GitOps(root)
        bare_path = root / "origin.git"
        git.run("init", "--bare", "--initial-branch=main", str(bare_path), cwd=root)
        repo = cls(root, git, bare_path)
        repo._seed(seed_dir)
        return repo

    def _seed(self, seed_dir: Path | None) -> None:
        seed_clone = self.root / "seed"
        self.git.run("clone", str(self.bare_path), str(seed_clone), cwd=self.root)
        if seed_dir is not None:
            _copy_project_files(seed_dir, seed_clone)
            self.git.run("add", "-A", cwd=seed_clone)
        message = "Seed sandbox from working directory" if seed_dir else "Initialize sandbox"
        self.git.run("commit", "--allow-empty", "-m", message, cwd=seed_clone)
        self.git.run("push", "origin", "main", cwd=seed_clone)
        shutil.rmtree(seed_clone)

    @property
    def exists(self) -> bool:
        return self.root.is_dir() and self.bare_path.is_dir()

    def branches(self) -> list[str]:
        """Branch names currently in the bare repo."""
        result = self.git.run(
            "for-each-ref", "--format=%(refname:short)", "refs/heads",
            cwd=self.bare_path,
        )
        return [line for line in result.stdout.splitlines() if line]

    def destroy(self) -> None:
        """Remove the whole sandbox. Safe to call more than once."""
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "SandboxRepo":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.destroy()


def _copy_project_files(source: Path, target: Path) -> None:
    for entry in source.iterdir():
        if entry.name in _IGNORED_SEED_ENTRIES:
            continue
        destination = target / entry.name
        if entry.is_dir():
            shutil.copytree(
                entry,
                destination,
                ignore=shutil.ignore_patterns(*_IGNORED_SEED_ENTRIES),
            )
        else:
            shutil.copy2(entry, destination)
