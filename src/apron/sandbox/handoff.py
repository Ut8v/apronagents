"""The single bridge to reality: copies the final merged tree into the user's
working directory, then stops.

Handoff only ever adds or overwrites files in the target; it never deletes
anything there and never touches the target's own ``.git``. Real git
operations remain the user's alone. Alongside the files, a short run log is
written to ``.apron/last-run.md`` so the user's next interactive Claude
session can catch up on what apron did by reading one file.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class RunLogIssue:
    """What the run log records about one merged issue."""

    issue_id: str
    title: str
    summary: str = ""


def write_run_log(
    target_dir: Path,
    task_prompt: str,
    issues: list[RunLogIssue],
    files: list[str],
) -> Path:
    """Write ``.apron/last-run.md`` in the working directory.

    Plain data in, one markdown file out — the catch-up note for whoever
    (or whatever session) looks at this project next.
    """
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Apron run — {stamp}",
        "",
        f"**Task:** {task_prompt}",
        "",
        "## Issues merged",
        "",
    ]
    for issue in issues:
        lines.append(f"- **{issue.issue_id}** — {issue.title}")
        if issue.summary:
            lines.append(f"  - {issue.summary}")
    lines += ["", "## Files delivered", ""]
    lines += [f"- `{name}`" for name in files]
    lines += [
        "",
        "_Written by apron at handoff. If you are an interactive Claude",
        "session picking this project back up, this is what happened while",
        "you were away._",
        "",
    ]
    log_path = target_dir / ".apron" / "last-run.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(lines))
    return log_path
