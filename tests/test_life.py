import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import Principal, current_principal
from app.jobs.worker import run_due_once
from app.main import app
from app.services import chat as chat_service


def test_memory_policy_recall_correction_and_delete():
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/memories",
            json={
                "content": "For coding I prefer open source tools",
                "category": "preference",
                "consent": True,
            },
        )
        assert created.status_code == 201
        memory_id = created.json()["id"]
        policy = client.get("/api/v1/memory-policy")
        assert policy.status_code == 200
        recalled = client.get("/api/v1/memories").json()["items"]
        assert any("open source" in item["content"] for item in recalled)
        assert client.delete(f"/api/v1/memories/{memory_id}").status_code == 204
        assert all(row["id"] != memory_id for row in client.get("/api/v1/memories").json()["items"])


def test_approved_memory_is_supplied_to_a_later_chat(monkeypatch):
    observed = {}

    async def capture(state):
        observed.update(state)
        return {
            "reply": "I will use open source tools.",
            "intent": "conversation",
            "provider": "mock",
        }

    monkeypatch.setattr(chat_service.conversation_graph, "ainvoke", capture)
    with TestClient(app) as client:
        client.post(
            "/api/v1/memories",
            json={
                "content": "For coding I prefer open source tools",
                "category": "preference",
                "consent": True,
            },
        )
        response = client.post("/api/v1/chat", json={"message": "Suggest a coding workflow"})
    assert response.status_code == 200
    assert any("open source tools" in fact for fact in observed["memories"])


def test_project_task_and_durable_reminder_notification():
    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects", json={"title": "Coursework", "next_action": "submit draft"}
        )
        assert project.status_code == 201
        key = f"task-once-{uuid4()}"
        task = client.post(
            "/api/v1/tasks",
            json={"title": "Submit assignment", "project_id": project.json()["id"]},
            headers={"Idempotency-Key": key},
        )
        assert task.status_code == 201
        again = client.post(
            "/api/v1/tasks",
            json={"title": "Submit assignment", "project_id": project.json()["id"]},
            headers={"Idempotency-Key": key},
        )
        assert again.json()["id"] == task.json()["id"]
        assert (
            client.post(f"/api/v1/tasks/{task.json()['id']}/complete").json()["status"]
            == "completed"
        )

        reminder = client.post(
            "/api/v1/reminders",
            json={
                "text": "Call professor",
                "scheduled_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                "timezone": "Asia/Kolkata",
            },
        )
        assert reminder.status_code == 201
        reminder_id = reminder.json()["id"]
    assert asyncio.run(run_due_once(datetime.now(UTC))) >= 1
    assert asyncio.run(run_due_once(datetime.now(UTC))) == 0
    with TestClient(app) as client:
        assert (
            next(
                row
                for row in client.get("/api/v1/reminders").json()["items"]
                if row["id"] == reminder_id
            )["status"]
            == "delivered"
        )
        job = next(
            row
            for row in client.get("/api/v1/jobs").json()["items"]
            if row["reminder_id"] == reminder_id
        )
        notifications = client.get("/api/v1/notifications").json()["items"]
        assert sum(row["job_id"] == job["id"] for row in notifications) == 1


def test_approval_is_explicit_and_owner_scoped():
    async def owner_one():
        return Principal("owner-one")

    async def owner_two():
        return Principal("owner-two")

    with TestClient(app) as client:
        app.dependency_overrides[current_principal] = owner_one
        proposal = client.post(
            "/api/v1/approvals", json={"action": "test.write", "description": "Write a test file"}
        )
        assert proposal.json()["status"] == "pending"
        approval_id = proposal.json()["id"]
        app.dependency_overrides[current_principal] = owner_two
        assert client.post(f"/api/v1/approvals/{approval_id}/approve").status_code == 404
        app.dependency_overrides[current_principal] = owner_one
        assert client.post(f"/api/v1/approvals/{approval_id}/reject").json()["status"] == "rejected"
        assert client.post(f"/api/v1/approvals/{approval_id}/approve").status_code == 409
    app.dependency_overrides.pop(current_principal, None)
