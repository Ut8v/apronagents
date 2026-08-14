"""Parses and validates an agent definition file (frontmatter plus prompt body).

The format is deliberately the same shape Claude Code uses for its subagents:
YAML frontmatter followed by a markdown prompt body. ``role`` is an Apron
addition; a definition without one (typically an imported Claude Code agent)
is treated as a worker.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

import yaml


class DefinitionError(ValueError):
    """An agent definition file could not be parsed or failed validation."""


class AgentRole(StrEnum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"


class AgentSource(StrEnum):
    """Where a definition resolved from, lowest to highest precedence."""

    SHIPPED = "shipped"
    USER = "user"                      # ~/.apron/agents/
    CLAUDE_USER = "claude-user"        # ~/.claude/agents/ (read-only)
    CLAUDE_PROJECT = "claude-project"  # .claude/agents/ (read-only)
    PROJECT = "project"                # .apron/agents/


@dataclass(frozen=True)
class AgentDefinition:
    """One resolved agent: its identity, capabilities, and system prompt."""

    name: str
    description: str
    role: AgentRole
    prompt: str
    model: str | None = None
    tools: tuple[str, ...] = ()
    source: AgentSource | None = None
    source_path: Path | None = None


def parse_definition(text: str, fallback_name: str | None = None) -> AgentDefinition:
    """Parse frontmatter + body into a validated :class:`AgentDefinition`."""
    frontmatter, prompt = _split_frontmatter(text)
    name = frontmatter.get("name") or fallback_name
    if not name:
        raise DefinitionError("definition has no 'name' and no fallback")
    if not prompt.strip():
        raise DefinitionError(f"agent {name!r} has an empty prompt body")

    raw_role = frontmatter.get("role", AgentRole.WORKER)
    try:
        role = AgentRole(raw_role)
    except ValueError:
        raise DefinitionError(f"agent {name!r} has unknown role {raw_role!r}") from None

    return AgentDefinition(
        name=str(name),
        description=str(frontmatter.get("description", "")),
        role=role,
        prompt=prompt.strip(),
        model=frontmatter.get("model"),
        tools=_parse_tools(frontmatter.get("tools"), name),
    )


def load_definition(path: Path, source: AgentSource | None = None) -> AgentDefinition:
    """Load one definition file, using the filename as the fallback name."""
    try:
        text = path.read_text()
    except OSError as error:
        raise DefinitionError(f"cannot read {path}: {error}") from error
    definition = parse_definition(text, fallback_name=path.stem)
    return replace(definition, source=source, source_path=path)


def serialize_definition(definition: AgentDefinition) -> str:
    """Render a definition back to frontmatter + body (source info excluded)."""
    frontmatter: dict[str, object] = {
        "name": definition.name,
        "description": definition.description,
        "role": definition.role.value,
    }
    if definition.model is not None:
        frontmatter["model"] = definition.model
    if definition.tools:
        frontmatter["tools"] = list(definition.tools)
    rendered = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    return f"---\n{rendered}\n---\n{definition.prompt}\n"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise DefinitionError("definition must start with '---' frontmatter")
    try:
        raw_frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError:
        raise DefinitionError("frontmatter is not closed with '---'") from None
    try:
        frontmatter = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError as error:
        raise DefinitionError(f"invalid frontmatter YAML: {error}") from error
    if not isinstance(frontmatter, dict):
        raise DefinitionError("frontmatter must be a YAML mapping")
    return frontmatter, body


def _parse_tools(raw: object, name: str) -> tuple[str, ...]:
    """Accept both a YAML list and Claude Code's comma-separated string."""
    if raw is None:
        return ()
    if isinstance(raw, str):
        return tuple(tool.strip() for tool in raw.split(",") if tool.strip())
    if isinstance(raw, list):
        return tuple(str(tool).strip() for tool in raw)
    raise DefinitionError(f"agent {name!r} has invalid 'tools': {raw!r}")
