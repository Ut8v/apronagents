"""Tests for the REST API and the websocket feed."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apron.agents.definition import AgentRole
from apron.agents.discovery import discover_agents, resolve_for_role
from apron.bus.bus import EventBus
from apron.bus.events import Event, IssueQueued, ReviewOpened, WorkStarted
from apron.bus.store import StateStore
from apron.config import Mode, Settings
from apron.merge.controller import MergeController
from apron.merge.tester import CommandTester
from apron.sandbox.clone import WorkerClone
from apron.sandbox.repo import SandboxRepo
from apron.server.app import build_app
from apron.server.routes import ServerContext
from apron.workers.runner import FakeRunner
from apron.workers.worker import Worker


@pytest.fixture
def ctx(tmp_path: Path):
    settings = Settings(
        working_dir=tmp_path / "project", user_dir=tmp_path / "home"
    )
    settings.working_dir.mkdir()
    bus = EventBus()
    store = StateStore()
    bus.subscribe(store.record)
    repo = SandboxRepo.create()
    agents = discover_agents(
        user_apron_dir=tmp_path / "none",
        claude_user_dir=tmp_path / "none",
        claude_project_dir=tmp_path / "none",
        project_apron_dir=tmp_path / "none",
    )
    worker = Worker(
        "worker-1",
        resolve_for_role(agents, AgentRole.WORKER),
        repo,
        FakeRunner({}),
        bus,
    )
    controller = MergeController(repo, CommandTester(None), bus, Mode.SUPERVISED)
    yield ServerContext(settings, bus, store, repo, [worker], controller)
    repo.destroy()


@pytest.fixture
def client(ctx: ServerContext):
    with TestClient(build_app(ctx)) as test_client:
        yield test_client


def record_events(ctx: ServerContext) -> list[Event]:
    events: list[Event] = []
    ctx.bus.subscribe(events.append)
    return events


def queue_issue(ctx: ServerContext, issue_id: str = "i1") -> None:
    ctx.store.record(
        IssueQueued(issue_id=issue_id, task_id="t1", title="Add x", description="")
    )


def test_state_reports_mode_issues_and_workers(client, ctx):
    queue_issue(ctx)
    state = client.get("/api/state").json()
    assert state["mode"] == "supervised"
    assert state["issues"][0]["issue_id"] == "i1"
    assert state["workers"][0] == {
        "id": "worker-1",
        "agent_name": "worker-default",
        "agent_source": "shipped",
        "idle": True,
    }


def test_submitting_a_task_publishes_task_received(client, ctx):
    events = record_events(ctx)
    response = client.post("/api/task", json={"prompt": "build the thing"})
    assert response.status_code == 200
    assert events[0].kind == "TaskReceived"
    assert events[0].prompt == "build the thing"
    assert response.json()["task_id"] == events[0].task_id


def test_review_actions_publish_gate_events(client, ctx):
    queue_issue(ctx)
    events = record_events(ctx)
    assert client.post("/api/issues/i1/approve").status_code == 200
    assert client.post(
        "/api/issues/i1/send-back", json={"reason": "too broad"}
    ).status_code == 200
    assert [e.kind for e in events] == ["ReviewApproved", "ChangesRequested"]
    assert events[1].reason == "too broad"
    assert client.post("/api/issues/ghost/approve").status_code == 404


def test_diff_endpoint_shows_the_branch_changes(client, ctx):
    clone = WorkerClone.create(ctx.repo, "worker-1")
    clone.create_branch("issue/i1")
    (clone.path / "feature.py").write_text("VALUE = 1\n")
    clone.commit_all("Add feature")
    clone.push_branch("issue/i1")
    queue_issue(ctx)
    ctx.store.record(WorkStarted(issue_id="i1", worker_id="worker-1", branch="issue/i1"))
    ctx.store.record(
        ReviewOpened(issue_id="i1", worker_id="worker-1", branch="issue/i1")
    )

    payload = client.get("/api/issues/i1/diff").json()
    assert payload["branch"] == "issue/i1"
    assert payload["files"] == [{"status": "A", "path": "feature.py"}]
    assert "+VALUE = 1" in payload["diff"]
    assert client.get("/api/issues/ghost/diff").status_code == 404


def test_agents_can_be_listed_and_edited_through_the_overlay(client, ctx):
    names = {a["name"]: a for a in client.get("/api/agents").json()}
    assert names["worker-default"]["source"] == "shipped"
    assert names["worker-default"]["overridden"] is False

    events = record_events(ctx)
    saved = client.put(
        "/api/agents/worker-default",
        json={"prompt": "Edited prompt.", "role": "worker", "tools": ["read"]},
    ).json()
    assert saved["source"] == "project"
    assert saved["overridden"] is True
    overlay_file = ctx.settings.project_apron_dir / "agents" / "worker-default.md"
    assert "Edited prompt." in overlay_file.read_text()
    assert [e.kind for e in events] == ["AgentDefinitionsReloaded"]

    names = {a["name"]: a for a in client.get("/api/agents").json()}
    assert names["worker-default"]["prompt"] == "Edited prompt."
    assert client.put(
        "/api/agents/worker-default", json={"prompt": "   "}
    ).status_code == 422


def test_mode_toggle_flips_the_controller(client, ctx):
    assert client.post("/api/mode", json={"mode": "autonomous"}).json() == {
        "mode": "autonomous"
    }
    assert ctx.controller.mode is Mode.AUTONOMOUS


def test_websocket_sends_snapshot_then_live_events(client, ctx):
    queue_issue(ctx)
    with client.websocket_connect("/ws") as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["state"]["issues"][0]["issue_id"] == "i1"

        client.post("/api/task", json={"prompt": "go"})
        message = websocket.receive_json()
        assert message["type"] == "event"
        assert message["event"]["kind"] == "TaskReceived"


def test_workspace_reports_merged_and_inflight_changes(client, ctx):
    # Seeded state: nothing merged, nothing in flight.
    baseline = client.get("/api/workspace").json()["files"]
    assert all(f["merged"] is None and f["editing"] == [] for f in baseline)

    # An in-flight branch touching one file.
    clone = WorkerClone.create(ctx.repo, "worker-1")
    clone.create_branch("issue/i1")
    (clone.path / "feature.py").write_text("VALUE = 1\n")
    clone.commit_all("Add feature")
    clone.push_branch("issue/i1")
    files = {f["path"]: f for f in client.get("/api/workspace").json()["files"]}
    assert files["feature.py"]["editing"] == ["i1"]
    assert files["feature.py"]["merged"] is None

    # Merge it: the file flips from in-flight to merged (A), branch drops out.
    clone.update_main()
    clone.run("merge", "--no-ff", "origin/issue/i1", "-m", "Merge issue/i1")
    clone.push_branch("main")
    files = {f["path"]: f for f in client.get("/api/workspace").json()["files"]}
    assert files["feature.py"]["merged"] == "A"
    assert files["feature.py"]["editing"] == []


def test_state_reports_planning_activity(client, ctx):
    from apron.bus.events import PlanningProgress, TaskReceived

    assert client.get("/api/state").json()["planning"] == {
        "active": False,
        "notes": [],
    }
    ctx.store.record(TaskReceived(task_id="t1", prompt="p"))
    ctx.store.record(PlanningProgress(task_id="t1", note="reading the project…"))
    assert client.get("/api/state").json()["planning"] == {
        "active": True,
        "notes": ["reading the project…"],
    }


def test_send_back_carries_line_annotations(client, ctx):
    from apron.bus.events import ChangesRequested

    queue_issue(ctx)
    events = record_events(ctx)
    response = client.post(
        "/api/issues/i1/send-back",
        json={
            "reason": "close, but",
            "annotations": [{"path": "cli.py", "line": 14, "note": "guard None"}],
        },
    )
    assert response.status_code == 200
    [event] = [e for e in events if isinstance(e, ChangesRequested)]
    assert event.reason == "close, but"
    assert event.annotations == ({"path": "cli.py", "line": 14, "note": "guard None"},)


def test_plan_approve_route_publishes_the_edited_plan(client, ctx):
    from apron.bus.events import PlanApproved

    events = record_events(ctx)
    response = client.post(
        "/api/plan/approve",
        json={
            "task_id": "t1",
            "issues": [
                {"id": "a", "title": "A", "description": "d", "depends_on": []}
            ],
        },
    )
    assert response.status_code == 200
    [event] = [e for e in events if isinstance(e, PlanApproved)]
    assert event.issues[0]["title"] == "A"
    assert client.post("/api/plan/approve", json={"task_id": "t1", "issues": []}).status_code == 422


def test_github_issue_import_endpoints(client, ctx, monkeypatch):
    import apron.server.routes as routes
    from apron.bus.events import TaskReceived

    async def fake_list(working_dir):
        return [{"number": 5, "title": "Fix parser", "labels": ["bug"]}]

    async def fake_fetch(working_dir, numbers):
        return [
            {"number": n, "title": "Fix parser", "body": "It crashes.", "url": "u"}
            for n in numbers
        ]

    monkeypatch.setattr(routes, "list_open_issues", fake_list)
    monkeypatch.setattr(routes, "fetch_issues", fake_fetch)

    listing = client.get("/api/github/issues").json()
    assert listing["available"] is True
    assert listing["issues"][0]["number"] == 5

    events = record_events(ctx)
    response = client.post("/api/task/from-issues", json={"numbers": [5]})
    assert response.status_code == 200
    [event] = [e for e in events if isinstance(e, TaskReceived)]
    assert "GitHub issue #5: Fix parser" in event.prompt
    assert "It crashes." in event.prompt
    assert client.post("/api/task/from-issues", json={"numbers": []}).status_code == 422


def test_github_issues_unavailable_without_gh(client, monkeypatch):
    import apron.server.routes as routes

    async def fake_list(working_dir):
        return None

    monkeypatch.setattr(routes, "list_open_issues", fake_list)
    assert client.get("/api/github/issues").json() == {"available": False, "issues": []}
