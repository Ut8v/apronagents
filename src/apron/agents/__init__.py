"""The editable agent-definition and config layer.

Agents are editable files, not code: shipped defaults are the floor, user and
project overlays in ``.apron/`` win over them, and existing Claude Code agents
in ``.claude/`` are discovered read-only. Edits are always copy-on-write into
``.apron/``; the shipped defaults and ``.claude/`` are never mutated.
"""
