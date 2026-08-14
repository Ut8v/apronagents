"""Per-worker working clones of the sandbox bare repo.

Each worker (and the merge controller) gets its own clone under the sandbox
root, so agents never share a working tree and all coordination happens
through the bare repo, exactly like colleagues sharing a real remote.
"""

from __future__ import annotations

from pathlib import Path

from apron.sandbox.git_ops import GitOps
from apron.sandbox.repo import SandboxRepo


class WorkerClone:
    """One working clone inside the sandbox, addressed only through origin."""

    def __init__(self, name: str, path: Path, git: GitOps) -> None:
        self.name = name
        self.path = path
        self._git = git

    @classmethod
    def create(cls, repo: SandboxRepo, name: str) -> "WorkerClone":
        path = repo.root / "clones" / name
        path.parent.mkdir(exist_ok=True)
        repo.git.run("clone", str(repo.bare_path), str(path), cwd=repo.root)
        return cls(name, path, repo.git)

    def run(self, *args: str, check: bool = True):
        """Run an audited git command in this clone."""
        return self._git.run(*args, cwd=self.path, check=check)

    # --- everyday moves ------------------------------------------------------

    def create_branch(self, branch: str) -> None:
        self.run("switch", "-c", branch)

    def switch(self, branch: str) -> None:
        self.run("switch", branch)

    def current_branch(self) -> str:
        return self.run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def fetch(self) -> None:
        self.run("fetch", "origin")

    def commit_all(self, message: str) -> str:
        """Stage everything, commit, and return the new commit's sha."""
        self.run("add", "-A")
        self.run("commit", "-m", message)
        return self.run("rev-parse", "HEAD").stdout.strip()

    def push_branch(self, branch: str, force: bool = False) -> None:
        if force:
            self.run("push", "--force", "origin", branch)
        else:
            self.run("push", "origin", branch)

    def update_main(self) -> None:
        """Bring local main up to date with the bare repo."""
        self.fetch()
        self.switch("main")
        self.run("pull", "origin", "main", "--ff-only")
