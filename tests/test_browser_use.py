from fastapi.testclient import TestClient

import app.main as main_module
from app.conversation import graph as graph_module
from app.providers.browser_use import has_no_repository_results, is_repository_url


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
