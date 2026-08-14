"""The single bridge to reality: copies the final merged tree into the user's
working directory, then stops.

Handoff only ever adds or overwrites files in the target; it never deletes
anything there and never touches the target's own ``.git``. Real git
operations remain the user's alone.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from apron.sandbox.repo import SandboxRepo


def handoff(repo: SandboxRepo, target_dir: Path, branch: str = "main") -> list[str]:
    """Export ``branch`` from the sandbox into ``target_dir``.

    Returns the copied paths, relative to ``target_dir``, sorted.
    """
    export_dir = repo.root / "export"
    if export_dir.exists():
        shutil.rmtree(export_dir)
    repo.git.run(
        "clone", "--branch", branch, str(repo.bare_path), str(export_dir),
        cwd=repo.root,
    )

    copied: list[str] = []
    for source in export_dir.rglob("*"):
        relative = source.relative_to(export_dir)
        if relative.parts[0] == ".git" or source.is_dir():
            continue
        destination = target_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(relative))

    shutil.rmtree(export_dir)
    return sorted(copied)
