import asyncio
import json

from fastapi.testclient import TestClient

from app.integrations import google_api
from app.main import app
from app.persistence.models import IntegrationConnectionRow
from app.persistence.session import SessionLocal


def test_gmail_send_requires_approval_and_revalidates_snapshot(monkeypatch):
    async def add_connection():
        async with SessionLocal() as db:
            db.add(
                IntegrationConnectionRow(
                    id="google-approval-test",
                    user_id="local-user",
                    provider="google",
                    account_email="owner@example.test",
                    scopes=json.dumps(
                        [
                            "https://www.googleapis.com/auth/gmail.compose",
                            "https://www.googleapis.com/auth/gmail.send",
                        ]
                    ),
                    encrypted_credentials="ciphertext",
                    status="connected",
                )
            )
            await db.commit()

    asyncio.run(add_connection())
    expected = {
        "connection_id": "google-approval-test",
        "draft_id": "draft-test",
        "content_hash": "approved-content-hash",
        "recipients": {"to": "professor@example.test", "cc": "", "bcc": ""},
        "subject": "Extension request",
        "body": "Could I have an extension?",
        "thread_id": None,
        "message_id": "message-test",
    }
    sent = []

    async def read_draft(_db, _user, _connection, _draft):
        return {**expected, "content_hash": current_hash[0]}

    async def send_draft(_db, _user, _connection, _draft):
        sent.append("called")
        return {"message_id": "sent-message", "thread_id": "thread-test", "status": "sent"}

    current_hash = [expected["content_hash"]]
    monkeypatch.setattr(google_api, "read_draft", read_draft)
    monkeypatch.setattr(google_api, "send_draft", send_draft)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/approvals",
            json={
                "action": "gmail.send_draft",
                "description": "Send email to professor@example.test: Extension request",
                "arguments": expected,
            },
        )
        assert response.status_code == 201
        approval_id = response.json()["id"]
        assert response.json()["arguments"]["body"] == expected["body"]
        assert client.post(f"/api/v1/approvals/{approval_id}/approve").status_code == 200

        current_hash[0] = "changed-after-approval"
        changed = client.post(f"/api/v1/approved-actions/{approval_id}/execute")
        assert changed.status_code == 409
        assert changed.json()["detail"]["code"] == "approved_payload_changed"
        assert sent == []

        second = client.post(
            "/api/v1/approvals",
            json={
                "action": "gmail.send_draft",
                "description": "Send email to professor@example.test: Extension request",
                "arguments": expected,
            },
        )
        second_id = second.json()["id"]
        assert client.post(f"/api/v1/approvals/{second_id}/approve").status_code == 200
        current_hash[0] = expected["content_hash"]
        result = client.post(f"/api/v1/approved-actions/{second_id}/execute")
        assert result.status_code == 200
        assert result.json()["status"] == "succeeded"
        assert sent == ["called"]
        assert client.post(f"/api/v1/approved-actions/{second_id}/execute").status_code == 200
        assert sent == ["called"]
