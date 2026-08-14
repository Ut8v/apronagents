"""Copy-on-write agent edits, always written to ``.apron/agents/``.

Editing a shipped default or an imported Claude Code agent never mutates the
original: the edited copy lands in the project overlay, which wins at
resolution time. Writing anywhere under ``.claude/`` or into the shipped
defaults is refused outright — that boundary is an invariant, not a default.
"""

from __future__ import annotations

from pathlib import Path

from apron.agents.definition import AgentDefinition, serialize_definition
from apron.agents.discovery import SHIPPED_DEFAULTS_DIR


class OverlayError(Exception):
    """An edit tried to land outside the writable overlay."""


def override_path(project_apron_dir: Path, name: str) -> Path:
    """Where the overlay copy for agent ``name`` lives."""
    return project_apron_dir / "agents" / f"{name}.md"


def save_override(project_apron_dir: Path, definition: AgentDefinition) -> Path:
    """Write ``definition`` into the project overlay and return its path."""
    target = override_path(project_apron_dir, definition.name)
    _assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialize_definition(definition))
    return target


def delete_override(project_apron_dir: Path, name: str) -> bool:
    """Remove an overlay copy, falling resolution back to the layer below.

    Returns whether anything was deleted.
    """
    target = override_path(project_apron_dir, name)
    _assert_writable(target)
    if target.is_file():
        target.unlink()
        return True
    return False


def _assert_writable(target: Path) -> None:
    resolved = target.resolve()
    if ".claude" in resolved.parts:
        raise OverlayError(f"refusing to write into .claude: {resolved}")
    package_dir = SHIPPED_DEFAULTS_DIR.resolve().parents[1]
    if resolved.is_relative_to(package_dir):
        raise OverlayError(
            f"refusing to write into the installed package (shipped defaults): {resolved}"
        )
