from types import SimpleNamespace

import boto3
import pytest

from app.providers import storage


def test_neon_storage_presigned_upload_uses_private_branch_endpoint(monkeypatch):
    settings = SimpleNamespace(
        aws_access_key_id="neon-access",
        aws_secret_access_key="neon-secret",
        aws_endpoint_url_s3="https://branch.storage.neon.tech",
        aws_region="us-east-2",
        neon_storage_bucket="uploads",
        upload_max_bytes=1000,
    )
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    captured = {}

    class FakeS3:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            captured.update(operation=operation, params=Params, expires=ExpiresIn)
            return "https://signed.test/upload"

    def fake_client(service, **kwargs):
        captured["client"] = {"service": service, **kwargs}
        return FakeS3()

    monkeypatch.setattr(boto3, "client", fake_client)
    url = storage.presigned_upload("user-1", "file-1", "application/pdf", 25)

    assert url == "https://signed.test/upload"
    assert captured["client"]["endpoint_url"] == "https://branch.storage.neon.tech"
    assert captured["client"]["aws_access_key_id"] == "neon-access"
    assert captured["params"]["Bucket"] == "uploads"
    assert captured["params"]["Key"] == "users/user-1/uploads/file-1"
    assert captured["expires"] == 300


def test_neon_storage_rejects_missing_credentials_and_oversize(monkeypatch):
    settings = SimpleNamespace(
        aws_access_key_id=None,
        aws_secret_access_key=None,
        aws_endpoint_url_s3=None,
        aws_region="us-east-2",
        neon_storage_bucket="uploads",
        upload_max_bytes=10,
    )
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    with pytest.raises(storage.StorageUnavailable):
        storage.presigned_upload("user-1", "file-1", "application/pdf", 1)

    settings.aws_access_key_id = "key"
    settings.aws_secret_access_key = "secret"
    settings.aws_endpoint_url_s3 = "https://storage.test"
    with pytest.raises(ValueError, match="size"):
        storage.presigned_upload("user-1", "file-1", "application/pdf", 11)
