from fastapi.testclient import TestClient

from app.main import app


def test_memory_search_rejects_blank_query():
    with TestClient(app) as client:
        response = client.get("/api/v1/memories/search", params={"query": "   "})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_search"


def test_memory_search_rejects_zero_limit():
    with TestClient(app) as client:
        response = client.get("/api/v1/memories/search", params={"query": "preference", "limit": 0})
    assert response.status_code == 422


def test_memory_search_rejects_limit_above_twenty():
    with TestClient(app) as client:
        response = client.get("/api/v1/memories/search", params={"query": "preference", "limit": 21})
    assert response.status_code == 422
