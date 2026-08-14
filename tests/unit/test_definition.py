"""Tests for agent definition parsing, validation, and serialization."""

from pathlib import Path

import pytest

from apron.agents.definition import (
    AgentRole,
    AgentSource,
    DefinitionError,
    load_definition,
    parse_definition,
    serialize_definition,
)

FULL = """---
name: reviewer
description: Reviews diffs
role: worker
model: claude-sonnet-5
tools: [read, bash]
---
Review every diff carefully.
"""


def test_parses_a_full_definition():
    definition = parse_definition(FULL)
    assert definition.name == "reviewer"
    assert definition.description == "Reviews diffs"
    assert definition.role is AgentRole.WORKER
    assert definition.model == "claude-sonnet-5"
    assert definition.tools == ("read", "bash")
    assert definition.prompt == "Review every diff carefully."


def test_accepts_claude_code_style_comma_separated_tools():
    text = "---\nname: cc-agent\ntools: Read, Edit, Bash\n---\nDo the work.\n"
    assert parse_definition(text).tools == ("Read", "Edit", "Bash")


def test_role_defaults_to_worker_for_imported_agents():
    text = "---\nname: cc-agent\n---\nDo the work.\n"
    assert parse_definition(text).role is AgentRole.WORKER


def test_unknown_role_is_rejected():
    text = "---\nname: x\nrole: manager\n---\nBody.\n"
    with pytest.raises(DefinitionError, match="unknown role"):
        parse_definition(text)


def test_missing_name_uses_fallback_or_fails():
    text = "---\ndescription: no name\n---\nBody.\n"
    assert parse_definition(text, fallback_name="from-file").name == "from-file"
    with pytest.raises(DefinitionError, match="no 'name'"):
        parse_definition(text)


def test_empty_prompt_body_is_rejected():
    with pytest.raises(DefinitionError, match="empty prompt"):
        parse_definition("---\nname: x\n---\n   \n")


def test_missing_or_unclosed_frontmatter_is_rejected():
    with pytest.raises(DefinitionError, match="must start"):
        parse_definition("just a prompt")
    with pytest.raises(DefinitionError, match="not closed"):
        parse_definition("---\nname: x\nBody with no closing fence")


def test_serialize_round_trips():
    definition = parse_definition(FULL)
    assert parse_definition(serialize_definition(definition)) == definition


def test_load_attaches_source_and_path(tmp_path: Path):
    path = tmp_path / "helper.md"
    path.write_text("---\ndescription: d\n---\nHelp out.\n")
    definition = load_definition(path, source=AgentSource.PROJECT)
    assert definition.name == "helper"  # fallback: filename stem
    assert definition.source is AgentSource.PROJECT
    assert definition.source_path == path


def test_shipped_defaults_are_valid():
    from apron.agents.discovery import SHIPPED_DEFAULTS_DIR

    orchestrator = load_definition(SHIPPED_DEFAULTS_DIR / "orchestrator.md")
    worker = load_definition(SHIPPED_DEFAULTS_DIR / "worker.md")
    assert orchestrator.role is AgentRole.ORCHESTRATOR
    assert worker.role is AgentRole.WORKER
