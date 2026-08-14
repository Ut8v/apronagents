"""Tests for copy-on-write overlay edits and the read-only .claude boundary."""

from pathlib import Path

import pytest

from apron.agents.definition import AgentDefinition, AgentRole, AgentSource
from apron.agents.discovery import SHIPPED_DEFAULTS_DIR, discover_agents
from apron.agents.overlay import OverlayError, delete_override, save_override


def make_definition(name: str = "worker-default", prompt: str = "Edited.") -> AgentDefinition:
    return AgentDefinition(
        name=name, description="edited", role=AgentRole.WORKER, prompt=prompt
    )


def test_save_writes_into_the_project_overlay(tmp_path: Path):
    apron_dir = tmp_path / ".apron"
    path = save_override(apron_dir, make_definition())
    assert path == apron_dir / "agents" / "worker-default.md"
    assert "Edited." in path.read_text()


def test_saved_override_wins_at_resolution_time(tmp_path: Path):
    apron_dir = tmp_path / ".apron"
    save_override(apron_dir, make_definition(prompt="Overlay prompt."))
    agents = discover_agents(
        user_apron_dir=tmp_path / "none",
        claude_user_dir=tmp_path / "none",
        claude_project_dir=tmp_path / "none",
        project_apron_dir=apron_dir / "agents",
    )
    resolved = agents["worker-default"]
    assert resolved.source is AgentSource.PROJECT
    assert resolved.prompt == "Overlay prompt."


def test_delete_falls_back_to_the_layer_below(tmp_path: Path):
    apron_dir = tmp_path / ".apron"
    save_override(apron_dir, make_definition())
    assert delete_override(apron_dir, "worker-default") is True
    assert delete_override(apron_dir, "worker-default") is False


def test_refuses_to_write_anywhere_under_dot_claude(tmp_path: Path):
    with pytest.raises(OverlayError, match=r"\.claude"):
        save_override(tmp_path / ".claude", make_definition())
    with pytest.raises(OverlayError, match=r"\.claude"):
        save_override(tmp_path / "nested" / ".claude" / "deeper", make_definition())
    with pytest.raises(OverlayError):
        delete_override(tmp_path / ".claude", "worker-default")


def test_refuses_to_write_into_the_package_holding_shipped_defaults():
    with pytest.raises(OverlayError, match="shipped defaults"):
        save_override(SHIPPED_DEFAULTS_DIR, make_definition())
    with pytest.raises(OverlayError, match="shipped defaults"):
        save_override(SHIPPED_DEFAULTS_DIR.parent, make_definition())


def snapshot_tree(root: Path) -> dict[str, tuple[int, str]]:
    return {
        str(p.relative_to(root)): (p.stat().st_mtime_ns, p.read_text())
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_nothing_in_the_agent_layer_ever_writes_to_dot_claude(tmp_path: Path):
    """The invariant test: a full discover-edit-save cycle leaves .claude untouched."""
    claude_user = tmp_path / "home" / ".claude" / "agents"
    claude_project = tmp_path / "project" / ".claude" / "agents"
    for directory, name in ((claude_user, "cc-user-agent"), (claude_project, "cc-project-agent")):
        directory.mkdir(parents=True)
        (directory / f"{name}.md").write_text(
            f"---\nname: {name}\n---\nOriginal prompt.\n"
        )
    before = {
        "user": snapshot_tree(claude_user),
        "project": snapshot_tree(claude_project),
    }

    apron_dir = tmp_path / "project" / ".apron"
    agents = discover_agents(
        user_apron_dir=tmp_path / "home" / ".apron" / "agents",
        claude_user_dir=claude_user,
        claude_project_dir=claude_project,
        project_apron_dir=apron_dir / "agents",
    )
    # Edit an imported Claude Code agent: the copy must land in .apron only.
    imported = agents["cc-project-agent"]
    edited_path = save_override(
        apron_dir,
        AgentDefinition(
            name=imported.name,
            description=imported.description,
            role=imported.role,
            prompt="Edited prompt.",
        ),
    )
    delete_override(apron_dir, "cc-user-agent")

    assert edited_path.is_relative_to(apron_dir)
    assert snapshot_tree(claude_user) == before["user"]
    assert snapshot_tree(claude_project) == before["project"]
