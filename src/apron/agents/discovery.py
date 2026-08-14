"""Walks the agent resolution chain and returns the resolved agent set.

Ascending precedence (closest wins):

1. shipped defaults (the floor, inside this package)
2. ``~/.apron/agents/`` — the user's own overlay
3. ``~/.claude/agents/`` — Claude Code user agents, read-only
4. ``.claude/agents/`` — Claude Code project agents, read-only
5. ``.apron/agents/`` — the project overlay, where UI edits land

A file that fails to parse is skipped with a warning; it never breaks
discovery of the rest.
"""

from __future__ import annotations

import logging
from pathlib import Path

from apron.agents.definition import (
    AgentDefinition,
    AgentRole,
    AgentSource,
    DefinitionError,
    load_definition,
)
from apron.config import Settings

log = logging.getLogger(__name__)

SHIPPED_DEFAULTS_DIR = Path(__file__).parent / "defaults"

_PRECEDENCE = {
    AgentSource.SHIPPED: 0,
    AgentSource.USER: 1,
    AgentSource.CLAUDE_USER: 2,
    AgentSource.CLAUDE_PROJECT: 3,
    AgentSource.PROJECT: 4,
}


def discover_agents(
    *,
    user_apron_dir: Path,
    claude_user_dir: Path,
    claude_project_dir: Path,
    project_apron_dir: Path,
) -> dict[str, AgentDefinition]:
    """Resolve every agent by name, closest layer winning.

    The arguments are the four ``agents/`` directories; any that do not
    exist are simply skipped, so a fresh clone resolves to the shipped
    defaults alone.
    """
    layers: list[tuple[AgentSource, Path]] = [
        (AgentSource.SHIPPED, SHIPPED_DEFAULTS_DIR),
        (AgentSource.USER, user_apron_dir),
        (AgentSource.CLAUDE_USER, claude_user_dir),
        (AgentSource.CLAUDE_PROJECT, claude_project_dir),
        (AgentSource.PROJECT, project_apron_dir),
    ]
    resolved: dict[str, AgentDefinition] = {}
    for source, directory in layers:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            try:
                definition = load_definition(path, source=source)
            except DefinitionError as error:
                log.warning("skipping agent definition %s: %s", path, error)
                continue
            resolved[definition.name] = definition
    return resolved


def discover_from_settings(settings: Settings) -> dict[str, AgentDefinition]:
    """Discovery with the standard directory layout derived from settings."""
    return discover_agents(
        user_apron_dir=settings.user_apron_dir / "agents",
        claude_user_dir=settings.user_claude_dir / "agents",
        claude_project_dir=settings.project_claude_dir / "agents",
        project_apron_dir=settings.project_apron_dir / "agents",
    )


def resolve_for_role(
    agents: dict[str, AgentDefinition], role: AgentRole
) -> AgentDefinition:
    """The definition to use for ``role``: highest-precedence match wins,
    alphabetical name as the deterministic tie-break."""
    matching = [d for d in agents.values() if d.role is role]
    if not matching:
        raise DefinitionError(f"no agent definition with role {role.value!r}")
    return min(matching, key=lambda d: (-_PRECEDENCE.get(d.source, -1), d.name))
