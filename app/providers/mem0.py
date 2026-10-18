"""Optional Mem0 Platform client for consent-based long-term agent memory."""

import asyncio

from typing import Any

import httpx

from app.core.config import get_settings


def is_configured() -> bool:
    return bool(get_settings().mem0_api_key)


def _client() -> httpx.AsyncClient | None:
    settings = get_settings()
    if not settings.mem0_api_key:
        return None
    return httpx.AsyncClient(
        base_url=settings.mem0_host.rstrip("/"),
        headers={"Authorization": f"Token {settings.mem0_api_key}"},
        timeout=httpx.Timeout(max(settings.mem0_search_timeout_seconds, settings.mem0_add_timeout_seconds)),
    )


async def search_memories(query: str, user_id: str, limit: int = 5) -> list[str]:
    client = _client()
    if client is None:
        return []
    async with client:
        response = await asyncio.wait_for(client.post("/v3/memories/search/", json={"query": query, "filters": {"user_id": user_id}, "top_k": limit}), timeout=get_settings().mem0_search_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    results: Any = payload.get("results", []) if isinstance(payload, dict) else payload
    if not isinstance(results, list):
        return []
    memories = []
    for result in results:
        if isinstance(result, dict):
            content = result.get("memory") or result.get("text")
            if isinstance(content, str) and content.strip():
                memories.append(content.strip())
    return memories[:limit]


async def remember_exchange(user_id: str, user_message: str, assistant_message: str) -> None:
    client = _client()
    if client is None:
        raise RuntimeError("Mem0 is not configured")
    async with client:
        response = await asyncio.wait_for(client.post(
            "/v3/memories/add/",
            json={
                "messages": [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_message},
                ],
                "user_id": user_id,
            },
        ), timeout=get_settings().mem0_add_timeout_seconds)
        response.raise_for_status()
