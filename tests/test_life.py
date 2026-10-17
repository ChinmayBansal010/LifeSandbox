import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.conversation import graph as graph_module
from app.core.security import Principal, current_principal
from app.jobs.worker import run_due_once
from app.main import app
from app.providers.llm import Completion
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


def test_corrected_preference_supersedes_previous_value():
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/memories",
            json={"content": "I prefer concise answers", "category": "preference", "consent": True},
        )
        second = client.post(
            "/api/v1/memories",
            json={
                "content": "I prefer detailed answers",
                "category": "preference",
                "consent": True,
            },
        )
        assert first.status_code == second.status_code == 201
        active = client.get("/api/v1/memories/search", params={"query": "detailed answers"})
        assert [row["content"] for row in active.json()["items"]] == ["I prefer detailed answers"]
        all_memories = client.get("/api/v1/memories").json()["items"]
        assert (
            next(row for row in all_memories if row["id"] == first.json()["id"])["status"]
            == "superseded"
        )


def test_editing_memory_without_changing_content_keeps_it_active():
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/memories",
            json={"content": "I prefer short meetings", "category": "preference", "consent": True},
        )
        memory_id = created.json()["id"]
        edited = client.patch(
            f"/api/v1/memories/{memory_id}",
            json={"content": "I prefer short meetings", "category": "preference", "consent": True},
        )
        assert edited.status_code == 200
        assert edited.json()["id"] == memory_id
        assert edited.json()["status"] == "active"


def test_explicit_memory_request_requires_approval_and_is_recalled(monkeypatch):
    observed = {}

    async def capture(state):
        observed.update(state)
        return {
            "reply": "I will remember that preference.",
            "intent": "conversation",
            "provider": "mock",
        }

    monkeypatch.setattr(chat_service.conversation_graph, "ainvoke", capture)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat", json={"message": "Please remember that I prefer concise answers."}
        )
        assert response.status_code == 200
        assert response.json()["memory_request"]["status"] == "pending"
        candidates = client.get("/api/v1/memory-candidates").json()["items"]
        assert len(candidates) == 1
        approved = client.post(f"/api/v1/memory-candidates/{candidates[0]['id']}/approve")
        assert approved.status_code == 200

        second = client.post("/api/v1/chat", json={"message": "How should you format answers?"})
        assert second.status_code == 200
    assert any("concise answers" in memory for memory in observed["memories"])


def test_sensitive_memory_request_is_never_auto_saved(monkeypatch):
    async def capture(_state):
        return {"reply": "Understood.", "intent": "conversation", "provider": "mock"}

    monkeypatch.setattr(chat_service.conversation_graph, "ainvoke", capture)
    with TestClient(app) as client:
        client.put(
            "/api/v1/memory-policy",
            json={
                "enabled": True,
                "auto_categories": ["financial"],
                "hosted_memory_allowed": False,
            },
        )
        response = client.post(
            "/api/v1/chat", json={"message": "Remember that my salary is 1000 per month."}
        )
        assert response.status_code == 200
        assert response.json()["memory_request"]["status"] == "pending"
        memories = client.get("/api/v1/memories").json()["items"]
        assert not any(item["category"] == "financial" for item in memories)


def test_recurring_reminder_persists_delivery_and_next_occurrence():
    scheduled_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/reminders/recurring",
            json={
                "text": "Review weekly plan",
                "scheduled_at": scheduled_at,
                "timezone": "America/New_York",
                "recurrence": "weekly",
                "channel": "in_app",
            },
            headers={"Idempotency-Key": f"weekly-{uuid4()}"},
        )
        assert response.status_code == 201
        reminder_id = response.json()["id"]
        assert response.json()["recurrence"] == "weekly"
        jobs_before = client.get("/api/v1/jobs").json()["items"]
        assert sum(job["reminder_id"] == reminder_id for job in jobs_before) == 1

    assert asyncio.run(run_due_once(datetime.now(UTC))) == 1
    assert asyncio.run(run_due_once(datetime.now(UTC))) == 0
    with TestClient(app) as client:
        jobs = [
            job
            for job in client.get("/api/v1/jobs").json()["items"]
            if job["reminder_id"] == reminder_id
        ]
        assert sorted(job["status"] for job in jobs) == ["queued", "succeeded"]
        notifications = client.get("/api/v1/notifications").json()["items"]
        assert (
            sum(notification["text"] == "Review weekly plan" for notification in notifications) == 1
        )


def test_worker_recovers_stale_running_reminder():
    from app.persistence.models import JobRow, ReminderRow
    from app.persistence.session import SessionLocal

    now = datetime.now(UTC)

    async def create_stale_job():
        async with SessionLocal() as db:
            reminder = ReminderRow(
                user_id="local-user",
                text="Recovered reminder",
                scheduled_at=now - timedelta(minutes=20),
                timezone="UTC",
            )
            db.add(reminder)
            await db.flush()
            job = JobRow(
                user_id="local-user",
                reminder_id=reminder.id,
                scheduled_at=reminder.scheduled_at,
                status="running",
                attempts=1,
                started_at=now - timedelta(minutes=10),
                idempotency_key=f"stale:{reminder.id}",
            )
            db.add(job)
            await db.commit()
            return reminder.id

    reminder_id = asyncio.run(create_stale_job())
    assert asyncio.run(run_due_once(now)) == 1
    with TestClient(app) as client:
        reminder = client.get(f"/api/v1/reminders/{reminder_id}").json()
        assert reminder["status"] == "delivered"


def test_worker_marks_reminder_failed_after_exhausted_stale_lease():
    from app.persistence.models import JobRow, ReminderRow
    from app.persistence.session import SessionLocal

    now = datetime.now(UTC)

    async def create_exhausted_job():
        async with SessionLocal() as db:
            reminder = ReminderRow(
                user_id="local-user",
                text="Exhausted reminder",
                scheduled_at=now - timedelta(hours=1),
                timezone="UTC",
            )
            db.add(reminder)
            await db.flush()
            db.add(
                JobRow(
                    user_id="local-user",
                    reminder_id=reminder.id,
                    scheduled_at=reminder.scheduled_at,
                    status="running",
                    attempts=3,
                    started_at=now - timedelta(minutes=10),
                    idempotency_key=f"exhausted:{reminder.id}",
                )
            )
            await db.commit()
            return reminder.id

    reminder_id = asyncio.run(create_exhausted_job())
    assert asyncio.run(run_due_once(now)) == 0
    with TestClient(app) as client:
        assert client.get(f"/api/v1/reminders/{reminder_id}").json()["status"] == "failed"


def test_approved_task_action_executes_once_and_rejects_unapproved_side_effect():
    with TestClient(app) as client:
        proposal = client.post(
            "/api/v1/approvals",
            json={
                "action": "task.create",
                "description": "Create a follow-up task",
                "arguments": {"title": "Call the supplier"},
            },
        )
        approval_id = proposal.json()["id"]
        execute_path = f"/api/v1/approved-actions/{approval_id}/execute"
        assert client.post(execute_path).status_code == 409
        assert not any(
            task["title"] == "Call the supplier"
            for task in client.get("/api/v1/tasks").json()["items"]
        )
        assert client.post(f"/api/v1/approvals/{approval_id}/approve").status_code == 200
        first = client.post(execute_path)
        second = client.post(execute_path)
        assert first.status_code == second.status_code == 200
        assert first.json()["resource_id"] == second.json()["resource_id"]
        assert (
            sum(
                task["title"] == "Call the supplier"
                for task in client.get("/api/v1/tasks").json()["items"]
            )
            == 1
        )


def test_expired_approval_cannot_execute():
    from app.persistence.models import ApprovalRow
    from app.persistence.session import SessionLocal

    with TestClient(app) as client:
        proposal = client.post(
            "/api/v1/approvals",
            json={
                "action": "task.create",
                "description": "Create task",
                "arguments": {"title": "Too late"},
            },
        )
        approval_id = proposal.json()["id"]
        assert client.post(f"/api/v1/approvals/{approval_id}/approve").status_code == 200

        async def expire():
            async with SessionLocal() as db:
                row = await db.get(ApprovalRow, approval_id)
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                await db.commit()

        asyncio.run(expire())
        response = client.post(f"/api/v1/approved-actions/{approval_id}/execute")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "approval_expired"
        assert not any(
            task["title"] == "Too late" for task in client.get("/api/v1/tasks").json()["items"]
        )


def test_mutated_approval_payload_cannot_execute():
    from app.persistence.models import ApprovalRow
    from app.persistence.session import SessionLocal

    with TestClient(app) as client:
        proposal = client.post(
            "/api/v1/approvals",
            json={
                "action": "task.create",
                "description": "Create task",
                "arguments": {"title": "Original"},
            },
        )
        approval_id = proposal.json()["id"]
        assert client.post(f"/api/v1/approvals/{approval_id}/approve").status_code == 200

        async def mutate():
            async with SessionLocal() as db:
                row = await db.get(ApprovalRow, approval_id)
                row.arguments = '{"title":"Changed"}'
                await db.commit()

        asyncio.run(mutate())
        response = client.post(f"/api/v1/approved-actions/{approval_id}/execute")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "payload_changed"
        assert not any(
            task["title"] == "Changed" for task in client.get("/api/v1/tasks").json()["items"]
        )


def test_memories_projects_tasks_reminders_and_jobs_are_owner_scoped():
    async def owner_one():
        return Principal("owner-one")

    async def owner_two():
        return Principal("owner-two")

    with TestClient(app) as client:
        app.dependency_overrides[current_principal] = owner_one
        project = client.post("/api/v1/projects", json={"title": "Private project"}).json()
        memory = client.post(
            "/api/v1/memories",
            json={"content": "I prefer private notes", "category": "preference", "consent": True},
        ).json()
        linked = client.patch(
            f"/api/v1/memories/{memory['id']}/project",
            json={"project_id": project["id"]},
        )
        task = client.post(
            "/api/v1/tasks", json={"title": "Private task", "project_id": project["id"]}
        ).json()
        reminder = client.post(
            "/api/v1/reminders",
            json={
                "text": "Private reminder",
                "scheduled_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                "timezone": "UTC",
                "task_id": task["id"],
            },
        ).json()
        job = next(
            item
            for item in client.get("/api/v1/jobs").json()["items"]
            if item["reminder_id"] == reminder["id"]
        )
        assert linked.status_code == 200

        app.dependency_overrides[current_principal] = owner_two
        assert client.get(f"/api/v1/memories/{memory['id']}").status_code == 404
        assert (
            client.get("/api/v1/memories/search", params={"query": "private notes"}).json()["items"]
            == []
        )
        assert (
            client.patch(
                f"/api/v1/memories/{memory['id']}/project", json={"project_id": project["id"]}
            ).status_code
            == 404
        )
        assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404
        assert client.post(f"/api/v1/tasks/{task['id']}/cancel").status_code == 404
        assert client.get(f"/api/v1/reminders/{reminder['id']}").status_code == 404
        assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 404
    app.dependency_overrides.pop(current_principal, None)


@pytest.mark.skipif(
    not os.environ.get("LIFESANDBOX_TEST_DATABASE_URL"),
    reason="Set LIFESANDBOX_TEST_DATABASE_URL to run PostgreSQL concurrency coverage",
)
def test_postgres_workers_claim_one_due_job_once():
    from sqlalchemy import func, select

    from app.persistence.models import Base, JobRow, NotificationRow, ReminderRow
    from app.persistence.session import SessionLocal, engine

    now = datetime.now(UTC)
    owner_id = f"pg-worker-test-{uuid4()}"

    async def exercise_workers():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with SessionLocal() as db:
            reminder = ReminderRow(
                user_id=owner_id,
                text="Concurrent worker check",
                scheduled_at=now - timedelta(seconds=1),
                timezone="UTC",
            )
            db.add(reminder)
            await db.flush()
            job = JobRow(
                user_id=owner_id,
                reminder_id=reminder.id,
                scheduled_at=reminder.scheduled_at,
                idempotency_key=f"pg-worker:{reminder.id}",
            )
            db.add(job)
            await db.commit()
            job_id = job.id
        worker_results = await asyncio.gather(run_due_once(now), run_due_once(now))
        async with SessionLocal() as db:
            job = await db.get(JobRow, job_id)
            count = await db.scalar(
                select(func.count())
                .select_from(NotificationRow)
                .where(NotificationRow.job_id == job_id)
            )
        return sum(worker_results), job.status, job.attempts, count

    processed, status, attempts, notification_count = asyncio.run(exercise_workers())
    assert processed >= 1
    assert (status, attempts, notification_count) == ("succeeded", 1, 1)


def test_chat_graph_executes_scoped_task_tool(monkeypatch):
    class ToolModel:
        def __init__(self):
            self.calls = 0

        async def complete(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                return Completion(
                    "",
                    "mock",
                    "test-model",
                    [
                        {
                            "id": "task-call-1",
                            "function": {
                                "name": "create_task",
                                "arguments": '{"title":"Prepare sprint review"}',
                            },
                        }
                    ],
                )
            assert any(message.get("role") == "tool" for message in messages)
            return Completion("Task created.", "mock", "test-model", [])

    model = ToolModel()
    monkeypatch.setattr(graph_module, "model_for", lambda **_kwargs: model)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat", json={"message": "Add a task to prepare sprint review"}
        )
        assert response.status_code == 200
        assert response.json()["reply"] == "Task created."
        tasks = client.get("/api/v1/tasks").json()["items"]
        assert any(task["title"] == "Prepare sprint review" for task in tasks)


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
        second_task = client.post(
            "/api/v1/tasks",
            json={"title": "Review notes", "project_id": project.json()["id"]},
        )
        assert second_task.status_code == 201
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
        persisted_tasks = client.get("/api/v1/tasks").json()["items"]
        assert any(
            row["id"] == task.json()["id"] and row["status"] == "completed"
            for row in persisted_tasks
        )
        assert any(row["id"] == second_task.json()["id"] for row in persisted_tasks)
        job = next(
            row
            for row in client.get("/api/v1/jobs").json()["items"]
            if row["reminder_id"] == reminder_id
        )
        notifications = client.get("/api/v1/notifications").json()["items"]
        assert sum(row["job_id"] == job["id"] for row in notifications) == 1


def test_task_can_start_and_in_progress_filter_returns_it():
    with TestClient(app) as client:
        task = client.post("/api/v1/tasks", json={"title": "In-progress task"}).json()
        started = client.post(f"/api/v1/tasks/{task['id']}/start")
        assert started.status_code == 200
        assert started.json()["status"] == "in_progress"
        active = client.get("/api/v1/tasks", params={"status": "in_progress"}).json()["items"]
        assert any(item["id"] == task["id"] for item in active)
        assert client.post(f"/api/v1/tasks/{task['id']}/complete").json()["status"] == "completed"
        assert client.post(f"/api/v1/tasks/{task['id']}/start").status_code == 409


def test_cancelling_reminder_cancels_queued_job_without_delivery():
    with TestClient(app) as client:
        reminder = client.post(
            "/api/v1/reminders",
            json={
                "text": "Cancelled reminder",
                "scheduled_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
                "timezone": "UTC",
            },
        ).json()
        assert client.delete(f"/api/v1/reminders/{reminder['id']}").json()["status"] == "cancelled"
        job = next(
            row for row in client.get("/api/v1/jobs").json()["items"]
            if row["reminder_id"] == reminder["id"]
        )
        assert job["status"] == "cancelled"
        assert all(
            notification["job_id"] != job["id"]
            for notification in client.get("/api/v1/notifications").json()["items"]
        )


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
