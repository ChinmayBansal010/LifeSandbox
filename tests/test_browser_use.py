import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.conversation import graph as graph_module
import app.providers.browser_use as browser_use_module
from app.providers.browser_use import (
    has_no_repository_results,
    is_repository_url,
    research_with_browser,
)


def test_github_navigation_url_is_not_accepted_as_repository():
    assert not is_repository_url("https://github.com/features/copilot")
    assert not is_repository_url("https://github.com/login/device")
    assert is_repository_url("https://github.com/octocat/Hello-World")


def test_github_empty_search_is_reported_as_no_repository_results():
    assert has_no_repository_results(
        "Repositories\n0 (0) results\nYour search did not match any repositories"
    )
    assert not has_no_repository_results("Repositories\n3 results\nowner/project")


def test_browser_research_failure_returns_no_unverified_claims(monkeypatch):
    async def fail_search(_query: str):
        raise RuntimeError("GitHub returned no repositories")

    def unexpected_model_call(**_kwargs):
        raise AssertionError("The model must not generate facts after research failure")

    monkeypatch.setattr(graph_module, "research_with_browser", fail_search)
    monkeypatch.setattr(graph_module, "model_for", unexpected_model_call)
    monkeypatch.setattr(main_module, "browser_use_is_configured", lambda: True)
    with TestClient(main_module.app) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Research GitHub projects, licenses, and hardware.", "browse": True},
        )
    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    assert "couldn't complete the live github research" in reply
    assert "don't have verified project, license, or hardware details" in reply


def test_browser_research_repository_page_and_citations_e2e(monkeypatch):
    """Deterministic fixture verifying repository selection, page inspection, and citation."""
    search_page_data = {
        "title": "GitHub Search Results",
        "text": "Showing repository results matching ZCU104 FPGA",
        "links": [
            {"href": "https://github.com/features/copilot", "text": "Copilot"},
            {"href": "https://github.com/login", "text": "Sign in"},
            {"href": "https://github.com/Xilinx/Vitis-AI", "text": "Xilinx/Vitis-AI"},
            {"href": "https://github.com/example/fpga-nn", "text": "example/fpga-nn"},
            {"href": "https://github.com/sample/deep-learning", "text": "sample/deep-learning"},
            {"href": "https://github.com/pricing", "text": "Pricing"},
        ],
    }

    repo_page_data = {
        "title": "Xilinx/Vitis-AI: Development stack for AI inference on Xilinx hardware",
        "url": "https://github.com/Xilinx/Vitis-AI",
        "text": (
            "README.md: Vitis AI is a comprehensive development stack for AI inference on Xilinx "
            "hardware platforms including ZCU104 evaluation boards. License: Apache-2.0 license."
        ),
    }

    visited_urls: list[str] = []

    async def mock_goto(url: str):
        visited_urls.append(url)

    async def mock_evaluate(script: str) -> str:
        current_url = visited_urls[-1] if visited_urls else ""
        if "search?q=" in current_url:
            return json.dumps(search_page_data)
        elif "github.com/Xilinx/Vitis-AI" in current_url:
            return json.dumps(repo_page_data)
        elif "github.com/" in current_url:
            repo_path = current_url.removeprefix("https://github.com/").rstrip("/")
            return json.dumps({
                "title": f"{repo_path}: Open-source project",
                "url": current_url,
                "text": f"README.md: Details for {repo_path}.",
            })
        return "{}"

    mock_page = AsyncMock()
    mock_page.goto.side_effect = mock_goto
    mock_page.evaluate.side_effect = mock_evaluate

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page

    fake_browser_mod = MagicMock()
    fake_browser_mod.Browser.return_value = mock_browser

    monkeypatch.setattr(main_module, "browser_use_is_configured", lambda: True)
    monkeypatch.setattr(browser_use_module, "is_configured", lambda: True)

    with (
        patch.dict(sys.modules, {"browser_use": fake_browser_mod}),
        TestClient(main_module.app) as client,
    ):
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Need ZCU104 FPGA AI accelerator repo for inference",
                "browse": True,
            },
        )

    assert response.status_code == 200
    reply = response.json()["reply"]

    # 1. Fact extraction: project, license, and hardware details
    assert "Vitis-AI" in reply
    assert "Apache-2.0" in reply
    assert "ZCU104" in reply

    # 2. Source citation carrying observed repository URL into final response
    assert "https://github.com/Xilinx/Vitis-AI" in reply
    assert "Sources:" in reply

    # 3. Reserved GitHub paths were rejected and never opened as repository pages
    assert any("search?q=" in u for u in visited_urls)
    assert "https://github.com/Xilinx/Vitis-AI" in visited_urls
    assert not any("features/copilot" in u for u in visited_urls)
    assert not any("/pricing" in u for u in visited_urls)
    assert not any("/login" in u for u in visited_urls)

    # 4. Browser session cleanup guarantee
    mock_browser.start.assert_awaited_once()
    mock_browser.kill.assert_awaited_once()


@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_GITHUB_TEST"),
    reason="Live GitHub verification is opt-in via RUN_LIVE_GITHUB_TEST=1",
)
@pytest.mark.asyncio
async def test_live_github_browser_research_if_configured():
    """Live/manual verification step against real GitHub when environment provides browser."""
    try:
        result = await research_with_browser("ZCU104 FPGA AI accelerator")
        assert "result" in result
        assert "github.com/" in result["result"]
    except Exception as exc:
        # Document the exact environmental blocker (e.g. anti-bot captcha, network isolation)
        pytest.fail(f"Live GitHub verification blocked by environment: {exc}")


def test_capabilities_and_chat_explicit_behavior_when_browser_unconfigured(monkeypatch):
    """When Browser Use is unconfigured, capabilities report false and chat returns 503."""
    monkeypatch.setattr(main_module, "browser_use_is_configured", lambda: False)
    with TestClient(main_module.app) as client:
        cap_resp = client.get("/api/v1/capabilities")
        assert cap_resp.status_code == 200
        assert cap_resp.json()["browser_use_enabled"] is False

        chat_resp = client.post(
            "/api/v1/chat",
            json={"message": "Research GitHub projects", "browse": True},
        )
        assert chat_resp.status_code == 503
        error = chat_resp.json().get("detail", {})
        assert error.get("code") == "browser_use_not_configured"
        assert "disabled or not configured" in error.get("message", "").lower()


def test_capabilities_reports_true_when_browser_use_configured(monkeypatch):
    """When Browser Use is configured, capabilities endpoint accurately reports true."""
    monkeypatch.setattr(main_module, "browser_use_is_configured", lambda: True)
    with TestClient(main_module.app) as client:
        cap_resp = client.get("/api/v1/capabilities")
        assert cap_resp.status_code == 200
        assert cap_resp.json()["browser_use_enabled"] is True


@pytest.mark.asyncio
async def test_browser_research_raises_when_executable_missing(monkeypatch):
    """research_with_browser must fail fast when no browser binary exists."""
    monkeypatch.setattr(browser_use_module, "is_configured", lambda: True)
    monkeypatch.setattr(browser_use_module, "find_browser_executable", lambda: None)
    with pytest.raises(RuntimeError, match="No supported Chromium or Chrome executable found"):
        await research_with_browser("ZCU104 FPGA AI accelerator")
