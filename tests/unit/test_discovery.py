"""Tests for the agent resolution chain: closest wins, shipped is the floor."""

from pathlib import Path

import pytest

from apron.agents.definition import AgentRole, AgentSource, DefinitionError
from apron.agents.discovery import discover_agents, resolve_for_role


def write_agent(directory: Path, name: str, marker: str, role: str = "worker") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: {marker}\nrole: {role}\n---\n{marker}\n"
    )


@pytest.fixture
def dirs(tmp_path: Path) -> dict[str, Path]:
    return {
        "user_apron_dir": tmp_path / "home" / ".apron" / "agents",
        "claude_user_dir": tmp_path / "home" / ".claude" / "agents",
        "claude_project_dir": tmp_path / "project" / ".claude" / "agents",
        "project_apron_dir": tmp_path / "project" / ".apron" / "agents",
    }


def test_fresh_clone_resolves_to_shipped_defaults(dirs):
    agents = discover_agents(**dirs)  # none of the directories exist yet
    assert {"orchestrator-default", "worker-default"} <= set(agents)
    assert all(a.source is AgentSource.SHIPPED for a in agents.values())


def test_each_layer_overrides_the_one_below(dirs):
    write_agent(dirs["user_apron_dir"], "worker-default", "from user apron")
    assert (
        discover_agents(**dirs)["worker-default"].source is AgentSource.USER
    )

    write_agent(dirs["claude_user_dir"], "worker-default", "from claude user")
    assert (
        discover_agents(**dirs)["worker-default"].source is AgentSource.CLAUDE_USER
    )

    write_agent(dirs["claude_project_dir"], "worker-default", "from claude project")
    assert (
        discover_agents(**dirs)["worker-default"].source is AgentSource.CLAUDE_PROJECT
    )

    write_agent(dirs["project_apron_dir"], "worker-default", "from project apron")
    assert (
        discover_agents(**dirs)["worker-default"].source is AgentSource.PROJECT
    )


def test_claude_code_agents_are_discovered_alongside_defaults(dirs):
    write_agent(dirs["claude_user_dir"], "my-refactorer", "refactors")
    agents = discover_agents(**dirs)
    assert agents["my-refactorer"].source is AgentSource.CLAUDE_USER
    assert "worker-default" in agents  # defaults still present


def test_a_broken_file_is_skipped_not_fatal(dirs):
    dirs["project_apron_dir"].mkdir(parents=True)
    (dirs["project_apron_dir"] / "broken.md").write_text("no frontmatter at all")
    write_agent(dirs["project_apron_dir"], "good", "works")
    agents = discover_agents(**dirs)
    assert "good" in agents
    assert "broken" not in agents


def test_resolve_for_role_prefers_the_closest_definition(dirs):
    write_agent(dirs["project_apron_dir"], "my-planner", "custom", role="orchestrator")
    agents = discover_agents(**dirs)
    assert resolve_for_role(agents, AgentRole.ORCHESTRATOR).name == "my-planner"
    # The shipped default still resolves once the override set has no planner.
    shipped_only = discover_agents(
        **{k: v / "missing" for k, v in dirs.items()}
    )
    assert (
        resolve_for_role(shipped_only, AgentRole.ORCHESTRATOR).name
        == "orchestrator-default"
    )


def test_resolve_for_role_fails_clearly_when_nothing_matches():
    with pytest.raises(DefinitionError, match="no agent definition"):
        resolve_for_role({}, AgentRole.WORKER)
