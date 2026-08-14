"""Entry point for the ``apron`` command: parse args, hand off to the launcher."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from apron import __version__
from apron.config import Mode, load_settings
from apron.launcher import launch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apron",
        description=(
            "Split a coding task across sandboxed agents and merge their work "
            "one reviewed chunk at a time."
        ),
    )
    parser.add_argument("--version", action="version", version=f"apron {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="boot all organs and open the dashboard")
    start.add_argument(
        "--mode",
        choices=[mode.value for mode in Mode],
        default=None,
        help="supervised gates every merge behind a review; autonomous merges on green tests",
    )
    start.add_argument("--port", type=int, default=None, help="dashboard port")
    start.add_argument("--workers", type=int, default=None, help="number of worker agents")
    start.add_argument(
        "--runner",
        choices=["auto", "claude-code", "codex", "api", "demo"],
        default=None,
        help=(
            "agent backend: the claude CLI (any Claude plan), the codex CLI "
            "(ChatGPT plan), the Anthropic API, or a no-account demo "
            "(default: auto-detect)"
        ),
    )
    start.add_argument(
        "--test-command",
        default=None,
        help="shell command run against every candidate merge (e.g. 'pytest -q')",
    )
    start.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="project working directory (default: current directory)",
    )
    start.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open the dashboard in a browser",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "start":
        settings = load_settings(
            working_dir=args.dir,
            mode=args.mode,
            port=args.port,
            worker_count=args.workers,
            runner=args.runner,
            test_command=args.test_command,
            open_browser=not args.no_browser,
        )
        launch(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
