import json
from datetime import UTC, datetime

import pytest

from app.conversation.graph import execute_tools
from app.providers.research import ResearchSource
from app.tools.registry import ToolDefinition, ToolRegistry


def test_registry_rejects_duplicates_and_discovers_only_allowlisted_tools():
    registry = ToolRegistry()
    definition = ToolDefinition(
        "example.lookup",
        "Look up a value",
        {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
        "test",
    )
    registry.register(definition)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition)
    assert registry.discover(set()) == []
    assert registry.discover({"example.lookup"})[0]["function"]["name"] == "example.lookup"


def test_registry_validates_unknown_missing_and_malformed_arguments():
    definition = ToolDefinition(
        "example.lookup",
        "Look up a value",
        {
            "type": "object",
            "properties": {"key": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["key"],
        },
        "test",
    )
    assert definition.validate({"key": "abc", "limit": 3})["key"] == "abc"
    for arguments in ({"key": 3}, {"extra": True}, {}):
        with pytest.raises(ValueError):
            definition.validate(arguments)


@pytest.mark.asyncio
async def test_chat_executor_runs_registered_research_and_preserves_real_provenance(monkeypatch):
    async def fake_research(query):
        assert query == "compare open source tools"
        return [
            ResearchSource(
                title="Project Alpha",
                url="https://example.test/alpha",
                excerpt="Source-backed excerpt",
                publisher="example.test",
                retrieved_at=datetime(2026, 10, 19, tzinfo=UTC),
            )
        ]

    monkeypatch.setattr("app.providers.research.research", fake_research)
    result = await execute_tools(
        {
            "message": "compare open source tools",
            "user_id": "test-user",
            "authorized_tools": ["research.search"],
            "tool_calls": [
                {
                    "id": "research-call",
                    "function": {
                        "name": "research.search",
                        "arguments": '{"query":"compare open source tools"}',
                    },
                }
            ],
        }
    )
    tool_message = result["agent_messages"][0]
    payload = json.loads(tool_message["content"])
    assert payload["live"] is True
    assert payload["sources"][0]["url"] == "https://example.test/alpha"
    assert payload["sources"][0]["excerpt"] == "Source-backed excerpt"


@pytest.mark.asyncio
async def test_registered_tool_is_not_executable_when_not_in_request_allowlist():
    result = await execute_tools(
        {
            "authorized_tools": [],
            "tool_calls": [
                {
                    "id": "unallowed-call",
                    "function": {
                        "name": "compare_allocations",
                        "arguments": '{"available_total":1,"unit":"hours","options":[]}',
                    },
                }
            ],
        }
    )
    payload = json.loads(result["agent_messages"][0]["content"])
    assert payload["error"]["code"] == "tool_execution_failed"
