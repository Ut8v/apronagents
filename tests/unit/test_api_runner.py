"""Tests for the API backend, using a scripted fake Anthropic client."""

import json
from types import SimpleNamespace
from pathlib import Path

import pytest

from apron.agents.definition import AgentDefinition, AgentRole
from apron.orchestrator.planner import PlannedIssue
from apron.workers.api_runner import ApiPlanner, ApiRunner, _resolve

DEFINITION = AgentDefinition(
    name="worker-default",
    description="",
    role=AgentRole.WORKER,
    prompt="You are a careful worker.",
    model="claude-opus-5",
)

ISSUE = PlannedIssue("i1", "Add greeting", "Create greeting.txt")


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_block(block_id, name, tool_input):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def response(stop_reason, content):
    return SimpleNamespace(stop_reason=stop_reason, content=content)


class FakeStream:
    def __init__(self, message):
        self._message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def get_final_message(self):
        return self._message


class FakeClient:
    """Yields one scripted response per request, recording each request."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []
        self.messages = SimpleNamespace(stream=self._stream, create=self._create)

    def _stream(self, **kwargs):
        self.requests.append(kwargs)
        return FakeStream(self._responses.pop(0))

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self._responses.pop(0)


async def test_tool_loop_writes_files_and_returns_the_summary(tmp_path: Path):
    workdir = tmp_path / "clone"
    workdir.mkdir()
    client = FakeClient(
        [
            response("tool_use", [
                tool_block("t1", "list_files", {}),
                tool_block("t2", "write_file", {"path": "greeting.txt", "content": "hi\n"}),
            ]),
            response("end_turn", [text_block("Added greeting.txt.")]),
        ]
    )

    result = await ApiRunner(client=client).run_issue(DEFINITION, ISSUE, workdir)

    assert result.summary == "Added greeting.txt."
    assert (workdir / "greeting.txt").read_text() == "hi\n"
    first, second = client.requests
    assert first["model"] == "claude-opus-5"
    assert first["system"] == "You are a careful worker."
    # Tool results were sent back in a single user message, one per call.
    results = second["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]


async def test_refusals_end_the_issue_gracefully(tmp_path: Path):
    client = FakeClient([response("refusal", [])])
    result = await ApiRunner(client=client).run_issue(DEFINITION, ISSUE, tmp_path)
    assert "declined" in result.summary


def test_paths_are_confined_to_the_clone(tmp_path: Path):
    with pytest.raises(ValueError, match="escapes"):
        _resolve(tmp_path, "../outside.txt")
    with pytest.raises(ValueError, match="off limits"):
        _resolve(tmp_path, ".git/config")
    assert _resolve(tmp_path, "src/module.py") == tmp_path / "src" / "module.py"


async def test_planner_uses_structured_output(tmp_path: Path):
    plan = {
        "issues": [
            {"id": "one", "title": "One", "description": "d", "depends_on": []},
        ]
    }
    client = FakeClient([response("end_turn", [text_block(json.dumps(plan))])])
    planner = ApiPlanner(lambda: DEFINITION, tmp_path, client=client)

    issues = await planner.plan("t1", "do the thing")

    assert issues == [PlannedIssue("one", "One", "d", ())]
    request = client.requests[0]
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert "do the thing" in request["messages"][0]["content"]
