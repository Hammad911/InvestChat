"""
MinIO (S3-compatible) object storage client.
"""
from __future__ import annotations

import io
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_client() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def ensure_bucket() -> None:
    """Create the default bucket if it doesn't exist."""
    client = _get_client()
    if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
        client.make_bucket(settings.MINIO_BUCKET_NAME)
        logger.info("minio_bucket_created", bucket=settings.MINIO_BUCKET_NAME)
    else:
        logger.info("minio_bucket_exists", bucket=settings.MINIO_BUCKET_NAME)


def upload_file(
    object_name: str,
    data: BinaryIO,
    length: int,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload a file to MinIO. Returns the object path."""
    client = _get_client()
    client.put_object(
        bucket_name=settings.MINIO_BUCKET_NAME,
        object_name=object_name,
        data=data,
        length=length,
        content_type=content_type,
    )
    logger.info("minio_file_uploaded", object_name=object_name, size=length)
    return object_name


def download_file(object_name: str) -> bytes:
    """Download a file from MinIO. Returns raw bytes."""
    client = _get_client()
    response = client.get_object(settings.MINIO_BUCKET_NAME, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_file(object_name: str) -> None:
    """Delete a file from MinIO."""
    client = _get_client()
    client.remove_object(settings.MINIO_BUCKET_NAME, object_name)
    logger.info("minio_file_deleted", object_name=object_name)


def get_presigned_url(object_name: str, expires_hours: int = 1) -> str:
    """Generate a presigned URL for direct download."""
    from datetime import timedelta

    client = _get_client()
    return client.presigned_get_object(
        settings.MINIO_BUCKET_NAME,
        object_name,
        expires=timedelta(hours=expires_hours),
    )


def check_health() -> bool:
    """Check MinIO connectivity."""
    try:
        client = _get_client()
        if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
            # Attempt to create the bucket if missing
            try:
                client.make_bucket(settings.MINIO_BUCKET_NAME)
            except Exception:
                return False
        return True
    except Exception:
        return False
