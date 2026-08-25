"""Tests for the GitHub issue task source, using a fake ``gh`` executable."""

import json
import stat
from pathlib import Path

import pytest

from apron.orchestrator.sources import (
    SourceError,
    fetch_issues,
    list_open_issues,
    prompt_from_issues,
)


def fake_gh(tmp_path: Path, script_body: str) -> str:
    path = tmp_path / "fake-gh"
    path.write_text("#!/bin/sh\n" + script_body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


async def test_lists_open_issues_for_the_picker(tmp_path: Path):
    listing = [
        {"number": 37, "title": "Runner profile: Gemini CLI",
         "labels": [{"name": "good first issue"}, {"name": "enhancement"}]},
        {"number": 29, "title": "Cost tracking", "labels": []},
    ]
    executable = fake_gh(tmp_path, f"echo '{json.dumps(listing)}'\n")

    issues = await list_open_issues(tmp_path, executable=executable)
    assert issues == [
        {"number": 37, "title": "Runner profile: Gemini CLI",
         "labels": ["good first issue", "enhancement"]},
        {"number": 29, "title": "Cost tracking", "labels": []},
    ]


async def test_unavailable_source_reports_none(tmp_path: Path):
    # No such executable at all.
    assert await list_open_issues(tmp_path, executable="gh-nope") is None
    # gh exists but fails (e.g. no GitHub remote in this project).
    failing = fake_gh(tmp_path, "echo 'no git remotes' >&2\nexit 1\n")
    assert await list_open_issues(tmp_path, executable=failing) is None


async def test_fetches_full_issues_and_builds_the_prompt(tmp_path: Path):
    issue = {"number": 29, "title": "Cost tracking",
             "body": "Track tokens per issue.", "url": "https://github.com/x/y/issues/29"}
    executable = fake_gh(tmp_path, f"echo '{json.dumps(issue)}'\n")

    fetched = await fetch_issues(tmp_path, [29], executable=executable)
    prompt = prompt_from_issues(fetched)
    assert "Work on this GitHub issue." in prompt
    assert "GitHub issue #29: Cost tracking" in prompt
    assert "Track tokens per issue." in prompt
    assert "Source: https://github.com/x/y/issues/29" in prompt


async def test_fetch_failure_raises(tmp_path: Path):
    failing = fake_gh(tmp_path, "exit 1\n")
    with pytest.raises(SourceError, match="#29"):
        await fetch_issues(tmp_path, [29], executable=failing)


def test_multiple_issues_join_into_one_task():
    prompt = prompt_from_issues(
        [
            {"number": 1, "title": "A", "body": "a", "url": ""},
            {"number": 2, "title": "B", "body": "", "url": ""},
        ]
    )
    assert "Work on these 2 GitHub issues together." in prompt
    assert "GitHub issue #1: A" in prompt
    assert "GitHub issue #2: B" in prompt
    assert "(no description)" in prompt
