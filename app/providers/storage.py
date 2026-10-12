"""Private Neon Object Storage adapter through its S3-compatible API."""

from app.core.config import get_settings


class StorageUnavailable(RuntimeError):
    pass


def presigned_upload(user_id: str, file_id: str, mime_type: str, size: int) -> str:
    settings = get_settings()
    if not all(
        (
            settings.aws_access_key_id,
            settings.aws_secret_access_key,
            settings.aws_endpoint_url_s3,
            settings.neon_storage_bucket,
        )
    ):
        raise StorageUnavailable(
            "Neon Object Storage is not configured; set AWS credentials, endpoint, and bucket"
        )
    if size < 1 or size > settings.upload_max_bytes:
        raise ValueError("Upload size is outside the configured limit")
    if mime_type not in {
        "application/pdf",
        "text/plain",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        raise ValueError("File type is not allowed")
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url_s3,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.neon_storage_bucket,
            "Key": f"users/{user_id}/uploads/{file_id}",
            "ContentType": mime_type,
        },
        ExpiresIn=300,
    )
