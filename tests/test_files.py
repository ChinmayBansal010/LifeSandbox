import struct
import zlib

from fastapi.testclient import TestClient

from app.main import app, settings


def _png_1x1():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">II", 1, 1) + b"\x08\x02\x00\x00\x00")
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )


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


def test_png_upload_is_stored_as_ready_image(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "file_storage_dir", str(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/files",
            files={"file": ("diagram.png", _png_1x1(), "image/png")},
        )
        assert response.status_code == 201
        image = response.json()
        assert image["mime_type"] == "image/png"
        assert image["status"] == "ready"
        chat = client.post(
            "/api/v1/chat",
            json={"message": "What is shown?", "attachment_ids": [image["id"]]},
        )
        assert chat.status_code == 422
        assert chat.json()["detail"]["code"] == "invalid_attachment"
        downloaded = client.get(f"/api/v1/files/{image['id']}/download")
        assert downloaded.content == _png_1x1()
