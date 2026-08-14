"""Apron Agents: a local multi-agent coding orchestrator.

Tasks are split into small independent issues, worked by agents in an isolated
sandbox git repository, and merged one reviewed chunk at a time. The sandbox
never touches a real remote; the only bridge to reality is the final handoff
into the user's working directory.
"""

__version__ = "0.1.0"
