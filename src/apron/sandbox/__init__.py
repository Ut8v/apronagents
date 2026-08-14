"""Sandbox git layer: a disposable bare repo in a temp dir acting as a fully
local "fake GitHub", plus per-worker clones and the final handoff.

Nothing in this package ever touches a real remote.
"""
