import asyncio
import re
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
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
        code: str = "upstream_error",
        duration_ms: float = 0,
    ):
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
        system_content = next(
            (m["content"] for m in messages if isinstance(m, dict) and m.get("role") == "system"),
            "",
        )
        if "Browser research results from public webpages" in system_content:
            repo_matches = re.findall(
                r"Repository:\s*(https://github\.com/[^\s\n]+)", system_content
            )
            unique_repos = list(dict.fromkeys(repo_matches))

            findings = []
            title_matches = re.findall(r"Title:\s*(.+)", system_content)
            if title_matches:
                findings.append(f"Project: {title_matches[0].strip()}")

            lic_match = re.search(
                r"(?:license|licensed under)[:\s]+([A-Za-z0-9\.\-]+)",
                system_content,
                re.IGNORECASE,
            )
            if lic_match:
                findings.append(f"License: {lic_match.group(1)}")
            elif "apache-2.0" in system_content.lower() or "apache 2.0" in system_content.lower():
                findings.append("License: Apache-2.0")
            elif "mit" in system_content.lower():
                findings.append("License: MIT")

            if "zcu104" in system_content.lower():
                findings.append("Hardware: ZCU104 FPGA")
            elif "fpga" in system_content.lower():
                findings.append("Hardware: FPGA")

            facts_text = "\n".join(findings) if findings else "Verified repository details found."
            citations_text = "\n".join(f"- Source: {url}" for url in unique_repos)
            sources_section = f"\n\nSources:\n{citations_text}" if unique_repos else ""

            return Completion(
                f"Based on live browser research:\n{facts_text}{sources_section}",
                "mock",
                "local-reflection",
                [],
            )

        last = messages[-1]["content"] if messages else ""
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
        tool_name_map: dict[str, str] = {}
        if tools:
            sanitized_tools = []
            for t in tools:
                if isinstance(t, dict) and t.get("type") == "function" and "function" in t:
                    fn = dict(t["function"])
                    orig_name = fn.get("name", "")
                    sanitized_name = orig_name.replace(".", "__")
                    tool_name_map[sanitized_name] = orig_name
                    fn["name"] = sanitized_name
                    sanitized_tools.append({"type": "function", "function": fn})
                else:
                    sanitized_tools.append(t)
            payload["tools"] = sanitized_tools
            payload["tool_choice"] = "auto"
        try:
            timeout = self.timeout
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(timeout=timeout) as client:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }
                    attempts = [self.model]
                    if (
                        self.provider == "openrouter"
                        and self.fallback_model
                        and self.fallback_model != self.model
                    ):
                        attempts.append(self.fallback_model)
                    deadline = started + timeout
                    for index, requested_model in enumerate(attempts):
                        # Some OpenRouter reasoning models can return HTTP 200 with
                        # reasoning but no user-facing content. Retry that case once
                        # with reasoning disabled, instead of repeating the same call.
                        reasoning_variants = (
                            [False, True] if self.provider == "openrouter" else [False]
                        )
                        for reasoning_disabled in reasoning_variants:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                break
                            # Reserve time for a configured fallback after a slow
                            # primary route, while retaining most of the request budget.
                            attempt_budget = (
                                remaining
                                if index == len(attempts) - 1
                                else min(45.0, remaining * 0.6)
                            )
                            payload["model"] = requested_model
                            if reasoning_disabled:
                                payload["reasoning"] = {"effort": "none"}
                            else:
                                payload.pop("reasoning", None)
                            try:
                                async with asyncio.timeout(attempt_budget):
                                    response = await client.post(
                                        f"{self.base_url}/chat/completions",
                                        headers=headers,
                                        json=payload,
                                    )
                            except TimeoutError:
                                if index == len(attempts) - 1:
                                    raise
                                break
                            response.raise_for_status()
                            body = response.json()
                            message = body["choices"][0]["message"]
                            text = message.get("content")
                            if isinstance(text, list):
                                text = "".join(
                                    part.get("text", "")
                                    for part in text
                                    if isinstance(part, dict) and part.get("type") == "text"
                                )
                            raw_tool_calls = message.get("tool_calls") or []
                            tool_calls = []
                            for call in raw_tool_calls:
                                if isinstance(call, dict) and "function" in call:
                                    call_copy = dict(call)
                                    fn_copy = dict(call["function"])
                                    called_name = fn_copy.get("name", "")
                                    fn_copy["name"] = tool_name_map.get(
                                        called_name, called_name.replace("__", ".")
                                    )
                                    call_copy["function"] = fn_copy
                                    tool_calls.append(call_copy)
                                else:
                                    tool_calls.append(call)
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
            raise LLMError(
                f"{self.provider} request timed out",
                provider=self.provider,
                code="timeout",
                duration_ms=(time.monotonic() - started) * 1000,
            ) from exc
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
            s.openrouter_timeout_seconds,
            s.llm_max_tokens,
            s.openrouter_fallback_model,
        )
    raise ValueError(f"Unknown LLM provider: {provider}")
