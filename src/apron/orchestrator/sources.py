"""Task sources beyond the dispatch box: real GitHub issues as task prompts.

Reads the project's issue tracker through the user's own ``gh`` CLI —
read-only, no tokens of our own, and no git: this is issue metadata only,
so the sandbox invariant is untouched. When ``gh`` is missing or the
project has no GitHub remote, the whole feature reports unavailable and
the UI simply doesn't offer it.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Sequence

_TIMEOUT = 20.0


class SourceError(RuntimeError):
    """A selected issue could not be fetched."""


async def _gh(working_dir: Path, *args: str, executable: str = "gh") -> str | None:
    """Run one read-only ``gh`` command; None when unavailable or failing."""
    if shutil.which(executable) is None:
        return None
    process = await asyncio.create_subprocess_exec(
        executable,
        *args,
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=_TIMEOUT)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return None
    if process.returncode != 0:
        return None
    return stdout.decode(errors="replace")


async def list_open_issues(
    working_dir: Path, limit: int = 30, executable: str = "gh"
) -> list[dict] | None:
    """Open issues for the picker. None means the source is unavailable
    (no ``gh``, or no GitHub remote); an empty list means none are open."""
    out = await _gh(
        working_dir,
        "issue", "list", "--state", "open", "--limit", str(limit),
        "--json", "number,title,labels",
        executable=executable,
    )
    if out is None:
        return None
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        return None
    return [
        {
            "number": issue["number"],
            "title": issue["title"],
            "labels": [label["name"] for label in issue.get("labels", [])],
        }
        for issue in raw
    ]


async def fetch_issues(
    working_dir: Path, numbers: Sequence[int], executable: str = "gh"
) -> list[dict]:
    """Full title/body/url for the selected issues, in the given order."""
    issues: list[dict] = []
    for number in numbers:
        out = await _gh(
            working_dir,
            "issue", "view", str(number), "--json", "number,title,body,url",
            executable=executable,
        )
        if out is None:
            raise SourceError(f"could not fetch GitHub issue #{number}")
        try:
            issues.append(json.loads(out))
        except json.JSONDecodeError as error:
            raise SourceError(f"unreadable reply for issue #{number}") from error
    return issues


def prompt_from_issues(issues: Sequence[dict]) -> str:
    """Render fetched issues as one task prompt for the planner."""
    sections = []
    for issue in issues:
        body = (issue.get("body") or "").strip() or "(no description)"
        url = issue.get("url", "")
        source = f"\n\nSource: {url}" if url else ""
        sections.append(
            f"GitHub issue #{issue['number']}: {issue['title']}\n\n{body}{source}"
        )
    if len(sections) == 1:
        return f"Work on this GitHub issue.\n\n{sections[0]}"
    joined = "\n\n---\n\n".join(sections)
    return f"Work on these {len(sections)} GitHub issues together.\n\n{joined}"
