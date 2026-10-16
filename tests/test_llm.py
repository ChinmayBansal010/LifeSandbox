import asyncio

import httpx
import pytest

from app.providers.llm import LLMError, OpenAICompatibleModel


class ResponseStub:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://provider.test/chat/completions")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("upstream failure", request=request, response=response)

    def json(self):
        return self.payload


class ClientStub:
    response = None
    delay = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.response


@pytest.mark.asyncio
async def test_provider_success_is_normalized(monkeypatch):
    ClientStub.response = ResponseStub(
        200, {"choices": [{"message": {"content": "A useful reply"}}]}
    )
    monkeypatch.setattr(httpx, "AsyncClient", ClientStub)
    model = OpenAICompatibleModel(
        "openrouter", "https://provider.test/v1", "secret", "model", 3, 10
    )

    result = await model.complete([{"role": "user", "content": "hi"}])

    assert result.text == "A useful reply"
    assert result.provider == "openrouter"


@pytest.mark.asyncio
async def test_provider_status_error_is_typed_without_response_body(monkeypatch):
    ClientStub.response = ResponseStub(429, {"error": {"message": "sensitive upstream detail"}})
    monkeypatch.setattr(httpx, "AsyncClient", ClientStub)
    model = OpenAICompatibleModel(
        "openrouter", "https://provider.test/v1", "secret", "model", 3, 10
    )

    with pytest.raises(LLMError, match="HTTP 429") as caught:
        await model.complete([{"role": "user", "content": "hi"}])

    assert caught.value.status_code == 429
    assert "sensitive upstream detail" not in str(caught.value)


@pytest.mark.asyncio
async def test_all_openrouter_fallback_attempts_share_one_timeout(monkeypatch):
    ClientStub.response = ResponseStub(200, {"choices": [{"message": {"content": "late"}}]})
    ClientStub.delay = 0.1
    monkeypatch.setattr(httpx, "AsyncClient", ClientStub)
    model = OpenAICompatibleModel(
        "openrouter", "https://provider.test/v1", "secret", "model", 0.02, 10, "fallback"
    )

    with pytest.raises(LLMError, match="request timed out"):
        await model.complete([{"role": "user", "content": "hi"}])

    ClientStub.delay = 0
