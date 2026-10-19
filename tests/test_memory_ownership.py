from fastapi.testclient import TestClient
from app.core.security import Principal, current_principal
from app.main import app

def test_memory_from_another_user_is_not_readable():
    with TestClient(app) as client:
        created=client.post("/api/v1/memories",json={"content":"Private note for user one","category":"preference","consent":True})
        assert created.status_code == 201
        memory_id=created.json()["id"]
        app.dependency_overrides[current_principal]=lambda: Principal(user_id="different-user")
        try:
            response=client.get(f"/api/v1/memories/{memory_id}")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(current_principal,None)
