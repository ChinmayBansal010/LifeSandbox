"""Live Provider Contract Verification Harness.

Validates schemas, payload contracts, and error envelopes for upstream external
providers (Nebius, OpenRouter, Tavily, Mem0).
Includes opt-in live integration verification gated by RUN_LIVE_PROVIDER_TESTS=1.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import get_settings
from app.providers.llm import LLMError, OpenAICompatibleModel
from app.providers.mem0 import search_memories
from app.providers.research import ResearchSource, ResearchUnavailable, research

RUN_LIVE = os.environ.get("RUN_LIVE_PROVIDER_TESTS", "").lower() in {"1", "true", "yes"}


# ─── 1. LLM Provider (Nebius / OpenRouter) Contract Schema ──────────────────


@pytest.mark.asyncio
async def test_openai_compatible_contract_success_schema():
    """Harness: OpenAICompatibleModel strictly parses valid upstream provider response."""
    upstream_json = {
        "id": "chatcmpl-mock-123",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "meta-llama/llama-3.3-70b-instruct",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Consider your long-term liquidity before deciding.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
    }

    mock_response = httpx.Response(200, json=upstream_json, request=httpx.Request("POST", "https://api.test/v1"))

    model = OpenAICompatibleModel(
        provider="nebius",
        base_url="https://api.test/v1",
        api_key="test-key",
        model="meta-llama/llama-3.3-70b-instruct",
        timeout=5.0,
        max_tokens=100,
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        completion = await model.complete([{"role": "user", "content": "What should I do?"}])
        assert completion.provider == "nebius"
        assert completion.model == "meta-llama/llama-3.3-70b-instruct"
        assert "long-term liquidity" in completion.text
        assert completion.tool_calls == []


@pytest.mark.asyncio
async def test_openai_compatible_contract_tool_call_schema():
    """Harness: OpenAICompatibleModel parses upstream function / tool call signatures."""
    upstream_json = {
        "id": "chatcmpl-mock-tool",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "google_calendar_create_event",
                                "arguments": (
                                    '{"title": "Review Lease", '
                                    '"start_time": "2026-10-25T10:00:00Z"}'
                                ),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }

    mock_response = httpx.Response(
        200, json=upstream_json, request=httpx.Request("POST", "https://api.test/v1")
    )
    model = OpenAICompatibleModel(
        provider="nebius",
        base_url="https://api.test/v1",
        api_key="test-key",
        model="meta-llama/llama-3.3-70b-instruct",
        timeout=5.0,
        max_tokens=100,
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        completion = await model.complete([{"role": "user", "content": "Book calendar"}])
        assert len(completion.tool_calls) == 1
        call = completion.tool_calls[0]
        assert call["id"] == "call_123"
        assert call["function"]["name"] == "google_calendar_create_event"


@pytest.mark.asyncio
async def test_openai_compatible_contract_error_envelopes():
    """Harness: upstream HTTP 401, 429, and 500 errors must raise structured LLMError."""
    for error_code in (401, 429, 500):
        mock_response = httpx.Response(
            error_code,
            json={"error": {"message": f"Simulated error {error_code}"}},
            request=httpx.Request("POST", "https://api.test/v1"),
        )
        model = OpenAICompatibleModel(
            provider="openrouter",
            base_url="https://api.test/v1",
            api_key="invalid-key",
            model="mistralai/mistral-small",
            timeout=5.0,
            max_tokens=100,
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(LLMError) as exc_info:
                await model.complete([{"role": "user", "content": "Hello"}])
            assert exc_info.value.provider == "openrouter"
            assert exc_info.value.status_code == error_code


# ─── 2. Search Provider (Tavily) Contract Schema ─────────────────────────────


@pytest.mark.asyncio
async def test_tavily_research_contract_schema(monkeypatch):
    """Harness: Research service correctly maps Tavily API schema into ResearchSource."""
    monkeypatch.setenv("RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-mock-key")
    get_settings.cache_clear()

    upstream_json = {
        "query": "high yield savings rates 2026",
        "results": [
            {
                "title": "Best HYSA Rates of 2026",
                "url": "https://bankrate.com/banking/savings/rates",
                "content": "Current top annual percentage yields hover around 4.8%.",
                "score": 0.98,
            }
        ],
    }

    mock_resp = httpx.Response(200, json=upstream_json, request=httpx.Request("POST", "https://api.tavily.com"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        results = await research("high yield savings rates 2026")
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, ResearchSource)
        assert item.title == "Best HYSA Rates of 2026"
        assert "4.8%" in item.excerpt
        assert item.publisher == "bankrate.com"


@pytest.mark.asyncio
async def test_tavily_research_error_envelope(monkeypatch):
    """Harness: Tavily failure raises clean ResearchUnavailable exception."""
    monkeypatch.setenv("RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-mock-key")
    get_settings.cache_clear()

    mock_resp = httpx.Response(
        403,
        json={"detail": "Quota exceeded"},
        request=httpx.Request("POST", "https://api.tavily.com"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        with pytest.raises(ResearchUnavailable):
            await research("test query")


# ─── 3. Memory Provider (Mem0) Contract Schema ───────────────────────────────


@pytest.mark.asyncio
async def test_mem0_contract_schema(monkeypatch):
    """Harness: mem0 client parses both 'memory' and 'text' key contracts."""
    monkeypatch.setenv("MEM0_API_KEY", "m0-mock-test-key")
    get_settings.cache_clear()

    upstream_json = {
        "results": [
            {"id": "m1", "memory": "Prefers remote work over relocation"},
            {"id": "m2", "text": "Plans to purchase a home in 2027"},
        ]
    }
    mock_resp = httpx.Response(
        200, json=upstream_json, request=httpx.Request("POST", "https://api.mem0.ai")
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        memories = await search_memories(query="career goals", user_id="user-123", limit=5)
        assert len(memories) == 2
        assert "Prefers remote work" in memories[0]
        assert "purchase a home" in memories[1]


# ─── 4. Live Provider Opt-in Contract Verification ───────────────────────────


@pytest.mark.skipif(
    not RUN_LIVE, reason="Live provider verification requires RUN_LIVE_PROVIDER_TESTS=1"
)
@pytest.mark.asyncio
async def test_live_nebius_provider_contract():
    """Live Contract: verify Nebius OpenAI-compatible endpoint responds with valid schema."""
    settings = get_settings()
    if not settings.nebius_api_key:
        pytest.skip("NEBIUS_API_KEY is not configured")

    model = OpenAICompatibleModel(
        provider="nebius",
        base_url=settings.nebius_base_url,
        api_key=settings.nebius_api_key,
        model=settings.nebius_model,
        timeout=15.0,
        max_tokens=10,
    )
    result = await model.complete([{"role": "user", "content": "Respond with the word 'PONG'."}])
    assert result.provider == "nebius"
    assert len(result.text.strip()) > 0


@pytest.mark.skipif(
    not RUN_LIVE, reason="Live provider verification requires RUN_LIVE_PROVIDER_TESTS=1"
)
@pytest.mark.asyncio
async def test_live_openrouter_provider_contract():
    """Live Contract: verify OpenRouter endpoint responds with valid schema."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY is not configured")

    model = OpenAICompatibleModel(
        provider="openrouter",
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        timeout=15.0,
        max_tokens=10,
    )
    result = await model.complete([{"role": "user", "content": "Respond with 'PONG'."}])
    assert result.provider == "openrouter"
    assert len(result.text.strip()) > 0

