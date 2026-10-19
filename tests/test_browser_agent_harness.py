"""Browser Agent Automation & Research Harness.

Verifies the headless browser agent lifecycle, domain/path isolation,
DOM evaluation, search term normalization, and failure/fallback behaviors.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import get_settings
from app.providers.browser_use import (
    _github_search_terms,
    has_no_repository_results,
    is_configured,
    is_repository_url,
    research_with_browser,
)

# ─── 1. Query Boundaries & Configuration Guards ──────────────────────────────


@pytest.mark.asyncio
async def test_browser_agent_query_boundaries():
    """Harness: Browser research query length must strictly be 1..1000 chars."""
    with pytest.raises(ValueError, match="between 1 and 1000 characters"):
        await research_with_browser("")

    with pytest.raises(ValueError, match="between 1 and 1000 characters"):
        await research_with_browser("   ")

    with pytest.raises(ValueError, match="between 1 and 1000 characters"):
        await research_with_browser("a" * 1001)


def test_browser_agent_is_configured_logic(monkeypatch):
    """Harness: is_configured requires browser_use_enabled, dependency, and LLM provider."""
    # When disabled
    monkeypatch.setenv("BROWSER_USE_ENABLED", "false")
    get_settings.cache_clear()
    assert is_configured() is False

    # When enabled but provider is mock (not nebius or openrouter)
    monkeypatch.setenv("BROWSER_USE_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_settings.cache_clear()
    assert is_configured() is False

    # When enabled with nebius and module present
    monkeypatch.setenv("LLM_PROVIDER", "nebius")
    monkeypatch.setenv("NEBIUS_API_KEY", "mock-nebius-key")
    monkeypatch.setenv("NEBIUS_MODEL", "mock-model")
    get_settings.cache_clear()

    with patch("importlib.util.find_spec", return_value=MagicMock()):
        assert is_configured() is True

    # When package browser_use is not installed in environment
    with patch("importlib.util.find_spec", return_value=None):
        assert is_configured() is False


# ─── 2. URL and Search Term Heuristics Harness ───────────────────────────────


def test_is_repository_url_filtering():
    """Harness: filters out GitHub reserved platform paths from repository matches."""
    valid_urls = [
        "https://github.com/tiangolo/fastapi",
        "https://github.com/pydantic/pydantic/",
        "https://github.com/octocat/Hello-World",
    ]
    for url in valid_urls:
        assert is_repository_url(url) is True, f"Expected {url} to be a valid repo URL"

    reserved_urls = [
        "https://github.com/pricing",
        "https://github.com/features",
        "https://github.com/security",
        "https://github.com/about",
        "https://github.com/enterprise",
        "https://github.com/login",
        "https://github.com/orgs",
        "https://github.com/marketplace",
    ]
    for url in reserved_urls:
        assert is_repository_url(url) is False, f"Expected {url} to be filtered out"


def test_github_search_terms_extraction():
    """Harness: extracts search queries and domain-specific hardware accelerators."""
    terms = _github_search_terms("Find a fast API framework for Python web services.")
    assert len(terms) >= 1
    assert "Find a fast API framework" in terms[0]

    # Hardware specialized query expansion
    hw_terms = _github_search_terms(
        "Need ZCU104 FPGA accelerator repo for deep learning inference"
    )
    assert any("zcu104" in t.lower() for t in hw_terms)
    assert any("fpga ai accelerator" in t.lower() for t in hw_terms)


def test_has_no_repository_results_detection():
    """Harness: detects empty search state messages in raw DOM text."""
    empty_dom = "We couldn’t find anything. Your search did not match any repositories."
    assert has_no_repository_results(empty_dom) is True

    valid_dom = "Showing 45 repository results matching pydantic"
    assert has_no_repository_results(valid_dom) is False


# ─── 3. Full Mocked Browser Automation Flow ──────────────────────────────────


@pytest.mark.asyncio
async def test_browser_agent_full_lifecycle_and_extraction(monkeypatch):
    """Harness: mocks Browser and Page to verify DOM evaluate and cleanup in finally block."""
    monkeypatch.setenv("BROWSER_USE_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "nebius")
    monkeypatch.setenv("NEBIUS_API_KEY", "mock-nebius-key")
    monkeypatch.setenv("NEBIUS_MODEL", "mock-model")
    get_settings.cache_clear()

    # Mock evaluate payload for search results page
    search_page_data = {
        "title": "GitHub Search Results",
        "text": "Found top repositories for query",
        "links": [
            {"href": "https://github.com/owner/demo-repo", "text": "demo-repo"},
            {"href": "https://github.com/pricing", "text": "Pricing"},
        ],
    }

    # Mock evaluate payload for repository detail page
    repo_page_data = {
        "title": "owner/demo-repo: A sample repository",
        "url": "https://github.com/owner/demo-repo",
        "text": "README.md: Demo repository showing browser automation.",
    }

    mock_page = AsyncMock()
    mock_page.evaluate.side_effect = [
        json.dumps(search_page_data),
        json.dumps(repo_page_data),
    ]

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page

    fake_browser_mod = MagicMock()
    fake_browser_mod.Browser.return_value = mock_browser

    with (
        patch("importlib.util.find_spec", return_value=MagicMock()),
        patch.dict(sys.modules, {"browser_use": fake_browser_mod}),
    ):
        result = await research_with_browser("Find Python web frameworks")
        assert "result" in result
        assert "owner/demo-repo" in result["result"]
        assert "README.md" in result["result"]

        # Verify browser cleanup was called
        mock_browser.start.assert_awaited_once()
        mock_browser.kill.assert_awaited_once()


@pytest.mark.asyncio
async def test_browser_agent_cleanup_guarantee_on_error(monkeypatch):
    """Harness: browser.kill() must be called even when navigation throws an exception."""
    monkeypatch.setenv("BROWSER_USE_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "nebius")
    monkeypatch.setenv("NEBIUS_API_KEY", "mock-nebius-key")
    monkeypatch.setenv("NEBIUS_MODEL", "mock-model")
    get_settings.cache_clear()

    mock_page = AsyncMock()
    mock_page.goto.side_effect = TimeoutError("Connection timed out to GitHub")

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page

    fake_browser_mod = MagicMock()
    fake_browser_mod.Browser.return_value = mock_browser

    with (
        patch("importlib.util.find_spec", return_value=MagicMock()),
        patch.dict(sys.modules, {"browser_use": fake_browser_mod}),
    ):
        with pytest.raises(TimeoutError):
            await research_with_browser("Test query that will timeout")

        # Cleanup must still occur
        mock_browser.kill.assert_awaited_once()
