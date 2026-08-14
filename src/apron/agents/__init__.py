"""The editable agent-definition and config layer.

Agents are editable files, not code: shipped defaults are the floor, user and
project overlays in ``.apron/`` win over them, and existing Claude Code agents
in ``.claude/`` are discovered read-only. Edits are always copy-on-write into
``.apron/``; the shipped defaults and ``.claude/`` are never mutated.
"""

from apron.agents.definition import (
    AgentDefinition,
    AgentRole,
    AgentSource,
    DefinitionError,
    load_definition,
    parse_definition,
    serialize_definition,
)
from apron.agents.discovery import (
    SHIPPED_DEFAULTS_DIR,
    discover_agents,
    discover_from_settings,
    resolve_for_role,
)
from apron.agents.overlay import OverlayError, delete_override, override_path, save_override
from apron.agents.watch import AgentWatcher

__all__ = [
    "AgentDefinition",
    "AgentRole",
    "AgentSource",
    "AgentWatcher",
    "DefinitionError",
    "OverlayError",
    "SHIPPED_DEFAULTS_DIR",
    "delete_override",
    "discover_agents",
    "discover_from_settings",
    "load_definition",
    "override_path",
    "parse_definition",
    "resolve_for_role",
    "save_override",
    "serialize_definition",
]
