from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class Completion:
    text: str
    provider: str
    model: str


class LLMError(RuntimeError):
    pass


class ChatModel:
    async def complete(self, messages: list[dict[str, str]]) -> Completion:
        raise NotImplementedError


class MockChatModel(ChatModel):
    async def complete(self, messages):
        last = messages[-1]["content"]
        return Completion(
            f"I can help you think this through. You said: {last}\n\n"
            "What matters most to you in this decision?",
            "mock",
            "local-reflection",
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
    ):
        self.provider, self.base_url, self.api_key, self.model = (
            provider,
            base_url.rstrip("/"),
            api_key,
            model,
        )
        self.timeout, self.max_tokens = timeout, max_tokens

    async def complete(self, messages):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "messages": messages, "max_tokens": self.max_tokens},
                )
                response.raise_for_status()
                body = response.json()
                text = body["choices"][0]["message"]["content"]
                if not isinstance(text, str) or not text.strip():
                    raise LLMError("Provider returned empty content")
                return Completion(text, self.provider, self.model)
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{self.provider} completion failed") from exc


def model_for(provider: str | None = None) -> ChatModel:
    s = get_settings()
    provider = provider or s.llm_provider
    if provider == "mock":
        return MockChatModel()
    if provider == "nebius":
        return OpenAICompatibleModel(
            "nebius",
            s.nebius_base_url,
            s.nebius_api_key or "",
            s.nebius_model,
            s.llm_timeout_seconds,
            s.llm_max_tokens,
        )
    if provider == "openrouter":
        return OpenAICompatibleModel(
            "openrouter",
            s.openrouter_base_url,
            s.openrouter_api_key or "",
            s.openrouter_model,
            s.llm_timeout_seconds,
            s.llm_max_tokens,
        )
    raise ValueError(f"Unknown LLM provider: {provider}")
