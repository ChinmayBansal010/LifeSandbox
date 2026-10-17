from fastapi.testclient import TestClient

from app.main import app, settings


def test_local_upload_extract_download_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "file_storage_dir", str(tmp_path))
    with TestClient(app) as client:
        uploaded = client.post(
            "/api/v1/files",
            files={
                "file": (
                    "notes.txt",
                    b"A useful document says the deadline is Friday.",
                    "text/plain",
                )
            },
        )
        assert uploaded.status_code == 201
        record = uploaded.json()
        assert record["status"] == "ready"

        downloaded = client.get(f"/api/v1/files/{record['id']}/download")
        assert downloaded.status_code == 200
        assert b"deadline is Friday" in downloaded.content

        chat = client.post(
            "/api/v1/chat",
            json={"message": "What is the deadline?", "attachment_ids": [record["id"]]},
        )
        assert chat.status_code == 200

        removed = client.delete(f"/api/v1/files/{record['id']}")
        assert removed.status_code == 204
        assert client.get(f"/api/v1/files/{record['id']}/download").status_code == 404


def test_upload_rejects_mislabeled_pdf():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/files",
            files={"file": ("fake.pdf", b"plain text", "application/pdf")},
        )
    assert response.status_code == 400


def test_speech_endpoints_report_disabled_provider():
    with TestClient(app) as client:
        transcription = client.post(
            "/api/v1/audio/transcriptions",
            files={"file": ("recording.webm", b"audio", "audio/webm")},
        )
        synthesis = client.post("/api/v1/audio/speech", json={"text": "Hello"})
    assert transcription.status_code == 503
    assert transcription.json()["detail"]["code"] == "stt_disabled"
    assert synthesis.status_code == 503
    assert synthesis.json()["detail"]["code"] == "tts_disabled"
