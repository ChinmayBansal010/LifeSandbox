import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


@dataclass
class Completion:
    text: str
    provider: str
    model: str
    tool_calls: list[dict[str, Any]]


class LLMError(RuntimeError):
    def __init__(self, message: str, *, provider: str, status_code: int | None = None, code: str = "upstream_error", duration_ms: float = 0):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.code = code
        self.stage = "llm_generate"
        self.duration_ms = duration_ms


class ChatModel:
    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> Completion:
        raise NotImplementedError


class MockChatModel(ChatModel):
    async def complete(self, messages, tools=None):
        last = messages[-1]["content"]
        return Completion(
            f"I can help you think this through. You said: {last}\n\n"
            "What matters most to you in this decision?",
            "mock",
            "local-reflection",
            [],
        )


class OpenAICompatibleModel(ChatModel):
    def __init__(
        self,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float,
        max_tokens: int,
        fallback_model: str = "",
    ):
        self.provider, self.base_url, self.api_key, self.model = (
            provider,
            base_url.rstrip("/"),
            api_key,
            model,
        )
        self.timeout, self.max_tokens = timeout, max_tokens
        self.fallback_model = fallback_model

    async def complete(self, messages, tools=None):
        started = time.monotonic()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            timeout = min(self.timeout, get_settings().openrouter_timeout_seconds) if self.provider == "openrouter" else self.timeout
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(timeout=timeout) as client:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }
                    attempts = [self.model]
                    if self.provider == "openrouter" and self.fallback_model:
                        attempts.append(self.fallback_model)
                    else:
                        attempts.append(self.model)
                    deadline = started + timeout
                    for index, requested_model in enumerate(attempts):
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        # Reserve time for a configured fallback instead of allowing a
                        # slow free-tier route to consume the whole request budget.
                        attempt_budget = remaining if index == len(attempts) - 1 else min(45.0, remaining * 0.6)
                        payload["model"] = requested_model
                        try:
                            async with asyncio.timeout(attempt_budget):
                                response = await client.post(
                                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                                )
                        except TimeoutError:
                            if index == len(attempts) - 1:
                                raise
                            continue
                        response.raise_for_status()
                        body = response.json()
                        message = body["choices"][0]["message"]
                        text = message.get("content")
                        tool_calls = message.get("tool_calls") or []
                        if (isinstance(text, str) and text.strip()) or tool_calls:
                            return Completion(
                                text or "",
                                self.provider,
                                body.get("model", requested_model),
                                tool_calls,
                            )
                    raise LLMError(
                        "Provider returned empty content after all configured attempts",
                        provider=self.provider,
                    )
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"{self.provider} returned HTTP {exc.response.status_code}",
                provider=self.provider,
                status_code=exc.response.status_code,
                duration_ms=(time.monotonic() - started) * 1000,
            ) from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise LLMError(f"{self.provider} request timed out", provider=self.provider, code="timeout", duration_ms=(time.monotonic() - started) * 1000) from exc
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(
                f"{self.provider} returned an invalid response", provider=self.provider
            ) from exc


def model_for(provider: str | None = None, model: str | None = None) -> ChatModel:
    s = get_settings()
    provider = provider or s.llm_provider
    if provider == "mock":
        return MockChatModel()
    if provider == "nebius":
        return OpenAICompatibleModel(
            "nebius",
            s.nebius_base_url,
            s.nebius_api_key or "",
            model or s.nebius_model,
            s.openrouter_timeout_seconds,
            s.llm_max_tokens,
        )
    if provider == "openrouter":
        return OpenAICompatibleModel(
            "openrouter",
            s.openrouter_base_url,
            s.openrouter_api_key or "",
            model or s.openrouter_model,
            s.llm_timeout_seconds,
            s.llm_max_tokens,
            s.openrouter_fallback_model,
        )
    raise ValueError(f"Unknown LLM provider: {provider}")
