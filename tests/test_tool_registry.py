import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.conversation.graph import _bounded, execute_tools, select_relevant_tools
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


def test_registry_rejects_unqualified_ids_and_invalid_schemas():
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="namespaced"):
        registry.register(ToolDefinition("lookup", "Lookup", {"type": "object"}, "test"))
    with pytest.raises(ValueError, match="declared properties"):
        registry.register(
            ToolDefinition(
                "example.lookup",
                "Lookup",
                {"type": "object", "properties": {}, "required": ["missing"]},
                "test",
            )
        )


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


def test_registry_recursively_validates_bounds_and_nested_shapes():
    definition = ToolDefinition(
        "example.lookup",
        "Look up a value",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 2, "maxLength": 5},
                "options": {
                    "type": "array",
                    "maxItems": 2,
                    "items": {"type": "integer", "minimum": 1, "maximum": 4},
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "test",
    )
    assert definition.validate({"query": "abc", "options": [1, 4]})["query"] == "abc"
    for arguments in (
        {"query": "x"},
        {"query": "abc", "options": [0]},
        {"query": "abc", "options": [1, 2, 3]},
        {"query": "abc", "unexpected": True},
    ):
        with pytest.raises(ValueError):
            definition.validate(arguments)


def test_request_language_can_select_multiple_relevant_capability_families():
    selected = select_relevant_tools("Search my inbox for the professor's latest reply")
    assert {"gmail.search_messages", "gmail.get_thread", "research.search"}.issubset(selected)
    assert "calendar.list_events" not in selected


@pytest.mark.asyncio
async def test_tool_timeout_cancels_the_pending_operation():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def operation():
        started.set()
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    with pytest.raises(TimeoutError):
        await _bounded(operation(), 0.01)
    assert started.is_set()
    assert cancelled.is_set()


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
