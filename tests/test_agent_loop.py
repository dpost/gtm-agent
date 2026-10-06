"""The tool-use loop, driven by a scripted fake client. No API calls."""

import inspect
import json
from types import SimpleNamespace

import pytest
from anthropic.types import TextBlock, ToolUseBlock

from lead_brief import config
from lead_brief.agent import BriefError, brief_lead
from lead_brief.tools import TOOL_FUNCTIONS, TOOLS

VALID_BRIEF = {
    "alert_level": "caution",
    "relationship_status": "at_risk_department",
    "related_account_ids": ["ACC-001", "ACC-002"],
    "headline": "Marketing renewal at risk: talk to Riley Chen before calling.",
    "flags": [
        {"type": "renewal_risk", "claim": "Utilization fell to 45%.", "source_ids": ["usage:ACC-002"]},
        {"type": "champion_change", "claim": "Dana Ruiz moves to Operations.", "source_ids": ["transcript:T-0003"]},
    ],
    "summary": "s",
    "call_context_note": "n",
    "recommended_action": "a",
}


class FakeClient:
    """Stands in for anthropic.Anthropic: returns scripted responses and records each request."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []
        self.messages = self

    def create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._responses.pop(0)


def tool_use(block_id, name, tool_input):
    return ToolUseBlock(type="tool_use", id=block_id, name=name, input=tool_input)


def turn(*blocks, stop_reason):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason, stop_details=None)


def final(text):
    return turn(TextBlock(type="text", text=text), stop_reason="end_turn")


def tool_results(request):
    content = request["messages"][-1]["content"]
    return [] if isinstance(content, str) else [b for b in content if b["type"] == "tool_result"]


def test_happy_path_runs_tools_and_returns_brief():
    client = FakeClient([
        turn(tool_use("t1", "search_accounts", {"name": "Pellwick Freight"}), stop_reason="tool_use"),
        turn(
            tool_use("t2", "get_account", {"account_id": "ACC-002"}),
            tool_use("t3", "get_usage", {"account_id": "ACC-002"}),
            stop_reason="tool_use",
        ),
        final(json.dumps(VALID_BRIEF)),
    ])
    brief = brief_lead("L-001", client=client)

    assert brief.relationship_status == "at_risk_department"
    assert len(client.requests) == 3
    first_results = tool_results(client.requests[1])
    assert [r["tool_use_id"] for r in first_results] == ["t1"]
    assert "ACC-002" in first_results[0]["content"]
    second_results = tool_results(client.requests[2])
    assert [r["tool_use_id"] for r in second_results] == ["t2", "t3"]  # parallel calls in one user turn
    assert "OPP-004" in second_results[0]["content"]
    assert "usage:ACC-002" in second_results[1]["content"]
    assert all(r["tool_choice"] == {"type": "auto"} for r in client.requests)


def test_history_is_append_only_and_request_shape_is_stable():
    client = FakeClient([
        turn(tool_use("t1", "find_person", {"name_or_email": "Marcus Oyelaran"}), stop_reason="tool_use"),
        final(json.dumps(VALID_BRIEF)),
    ])
    brief_lead("L-001", client=client)
    first, second = client.requests
    assert second["messages"][: len(first["messages"])] == first["messages"]
    assert first["system"] == second["system"] and first["tools"] == second["tools"]
    assert first["model"] == config.AGENT_MODEL
    assert "crm:lead/L-001" in first["messages"][0]["content"]
    assert config.AS_OF_DATE in first["messages"][0]["content"]


def test_tool_calls_are_capped():
    # Four turns of three parallel calls each: 12 requested, only 10 may run.
    turns = [
        turn(*(tool_use(f"t{i}-{j}", "get_usage", {"account_id": "ACC-002"}) for j in range(3)), stop_reason="tool_use")
        for i in range(4)
    ]
    client = FakeClient([*turns, final(json.dumps(VALID_BRIEF))])
    brief_lead("L-001", client=client)

    results = [r for req in client.requests for r in tool_results(req)]
    assert sum(not r["is_error"] for r in results) == config.MAX_TOOL_CALLS
    assert sum(r["is_error"] for r in results) == 2
    last = client.requests[-1]
    assert last["tool_choice"] == {"type": "none"}
    assert any(b["type"] == "text" and "used all" in b["text"] for b in last["messages"][-1]["content"])


def test_retries_once_on_validation_error():
    client = FakeClient([final("Here is the brief: not json"), final(json.dumps(VALID_BRIEF))])
    brief = brief_lead("L-001", client=client)
    assert brief.alert_level == "caution"
    retry = client.requests[1]
    assert "failed validation" in retry["messages"][-1]["content"]
    assert retry["tool_choice"] == {"type": "none"}


def test_accepts_json_inside_code_fences():
    client = FakeClient([final("```json\n" + json.dumps(VALID_BRIEF) + "\n```")])
    assert brief_lead("L-001", client=client).headline == VALID_BRIEF["headline"]


def test_fails_loudly_after_second_validation_error():
    client = FakeClient([final("not json"), final(json.dumps({**VALID_BRIEF, "alert_level": "loud"}))])
    with pytest.raises(BriefError, match="failed validation twice"):
        brief_lead("L-001", client=client)


def test_refusal_fails_loudly():
    client = FakeClient([turn(stop_reason="refusal")])
    with pytest.raises(BriefError, match="refused"):
        brief_lead("L-001", client=client)


def test_tool_schemas_match_functions():
    assert {t["name"] for t in TOOLS} == set(TOOL_FUNCTIONS)
    for tool in TOOLS:
        params = set(inspect.signature(TOOL_FUNCTIONS[tool["name"]]).parameters)
        assert set(tool["input_schema"]["properties"]) == params
        assert set(tool["input_schema"]["required"]) == params


def test_system_prompt_is_fully_rendered():
    from lead_brief.agent import system_prompt

    prompt = system_prompt()
    assert "{brief_schema}" not in prompt and "{max_tool_calls}" not in prompt
    assert f"at most {config.MAX_TOOL_CALLS} tool calls" in prompt
    assert '"recommended_action"' in prompt  # schema inlined
