"""Entry point for the ``apron`` command: parse args, hand off to the launcher.

Two ways to dispatch a task from the terminal, mirroring the dashboard's
dispatch bar:

- ``apron start "add dark mode"`` boots everything and dispatches immediately
- ``apron task "add dark mode"`` sends a task to an already-running apron
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

from apron import __version__
from apron.config import DEFAULT_HOST, DEFAULT_PORT, Mode, load_settings
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
        "task",
        nargs="*",
        help="optional task to dispatch as soon as apron is up",
    )
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
        "--with-session-context",
        action="store_true",
        help=(
            "summarize your most recent interactive Claude session for this "
            "project and give it to the planner and workers"
        ),
    )
    start.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open the dashboard in a browser",
    )

    task = subparsers.add_parser(
        "task", help="dispatch a task to a running apron from your terminal"
    )
    task.add_argument(
        "prompt", nargs="*", default=[], help="the task description"
    )
    task.add_argument(
        "--from-issue",
        type=int,
        action="append",
        default=[],
        metavar="N",
        help=(
            "dispatch a GitHub issue of this project as the task "
            "(repeatable; combines several issues into one task)"
        ),
    )
    task.add_argument("--port", type=int, default=DEFAULT_PORT, help="apron's dashboard port")
    task.add_argument("--host", default=DEFAULT_HOST, help="apron's host")
    task.add_argument(
        "-f", "--follow",
        action="store_true",
        help="stay attached and narrate the run in this terminal",
    )
    return parser


def send_task(prompt: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    """POST a task to a running apron; returns the task id."""
    request = urllib.request.Request(
        f"http://{host}:{port}/api/task",
        data=json.dumps({"prompt": prompt}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())["task_id"]


def send_task_from_issues(
    numbers: list[int], host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
) -> str:
    """Ask a running apron to dispatch GitHub issues as one task."""
    request = urllib.request.Request(
        f"http://{host}:{port}/api/task/from-issues",
        data=json.dumps({"numbers": numbers}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())["task_id"]


def fetch_state(host: str, port: int) -> dict:
    with urllib.request.urlopen(
        f"http://{host}:{port}/api/state", timeout=10
    ) as response:
        return json.loads(response.read())


def planning_lines(seen: int, planning: dict) -> tuple[list[str], int]:
    """New planner narration since the last poll (pure, for testing)."""
    notes = planning.get("notes", []) if planning.get("active") else []
    if len(notes) < seen:  # a new task started a fresh note list
        seen = 0
    return [f"  ▸ planner · {note}" for note in notes[seen:]], len(notes)


def plan_gate_line(
    announced: str | None, plan: dict | None, url: str
) -> tuple[str | None, str | None]:
    """One narration line the first time a plan shows up at the gate."""
    if plan and plan.get("task_id") != announced:
        line = (
            f"◆ plan proposed: {len(plan.get('issues', []))} issue(s) held at "
            f"the plan gate — review at {url}"
        )
        return line, plan["task_id"]
    return None, announced


def state_changes(previous: dict, issues: list[dict]) -> tuple[list[str], dict]:
    """Diff two state snapshots into narration lines (pure, for testing)."""
    lines: list[str] = []
    current: dict = {}
    for issue in issues:
        issue_id = issue["issue_id"]
        snapshot = (issue["state"], issue.get("last_activity"))
        current[issue_id] = snapshot
        old_state, old_activity = previous.get(issue_id, (None, None))
        if issue["state"] != old_state:
            lines.append(f"{issue_id}: {issue['state']}")
        elif issue["state"] == "in_progress" and snapshot[1] and snapshot[1] != old_activity:
            lines.append(f"  ▸ {issue['worker_id']} · {snapshot[1]}")
    return lines, current


def follow(host: str, port: int) -> None:
    """Poll a running apron and narrate the run until it finishes."""
    previous: dict = {}
    seen_notes = 0
    announced_plan: str | None = None
    shown = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    try:
        while True:
            try:
                state = fetch_state(host, port)
            except (urllib.error.URLError, OSError):
                print("apron stopped — the run is over (handoff done, or shut down)")
                return
            notes, seen_notes = planning_lines(seen_notes, state.get("planning", {}))
            for line in notes:
                print(line, flush=True)
            gate, announced_plan = plan_gate_line(
                announced_plan, state.get("plan_review"), f"http://{shown}:{port}"
            )
            if gate:
                print(gate, flush=True)
            lines, previous = state_changes(previous, state["issues"])
            for line in lines:
                print(line, flush=True)
            issues = state["issues"]
            if issues and all(i["state"] == "merged" for i in issues):
                print("all issues merged — waiting for handoff")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\ndetached — the run continues; reattach with apron task --follow")


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
            with_session_context=args.with_session_context or None,
            open_browser=not args.no_browser,
        )
        launch(settings, initial_task=" ".join(args.task).strip() or None)
        return 0

    if args.command == "task":
        prompt = " ".join(args.prompt).strip()
        if bool(prompt) == bool(args.from_issue):
            print("apron: give either a task description or --from-issue N")
            return 2
        try:
            if args.from_issue:
                task_id = send_task_from_issues(
                    args.from_issue, host=args.host, port=args.port
                )
            else:
                task_id = send_task(prompt, host=args.host, port=args.port)
        except urllib.error.HTTPError as error:
            print(f"apron: {error.read().decode(errors='replace')[:200]}")
            return 1
        except (urllib.error.URLError, OSError):
            print(
                f"apron: nothing is listening on {args.host}:{args.port} — "
                "start one first with `apron start`"
            )
            return 1
        shown = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
        print(f"task {task_id} dispatched — watch it at http://{shown}:{args.port}")
        if args.follow:
            follow(host=args.host, port=args.port)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
