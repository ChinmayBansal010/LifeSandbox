"""Private Cloudflare R2 storage via the S3-compatible API."""

from app.core.config import get_settings


class StorageUnavailable(RuntimeError):
    pass


def presigned_upload(user_id: str, file_id: str, mime_type: str, size: int) -> str:
    settings = get_settings()
    if not all(
        (
            settings.r2_account_id,
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_name,
        )
    ):
        raise StorageUnavailable("R2 is not configured")
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

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": f"users/{user_id}/uploads/{file_id}",
            "ContentType": mime_type,
        },
        ExpiresIn=300,
    )
