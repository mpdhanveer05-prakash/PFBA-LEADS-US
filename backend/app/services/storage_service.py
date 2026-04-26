import io
import logging
from datetime import datetime, timezone

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


def _client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )


def _ensure_bucket(client: Minio) -> None:
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def upload_raw(county_slug: str, apn: str, content: bytes, extension: str = "html") -> str:
    """Upload raw HTML/PDF to MinIO. Returns the S3 key."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"raw/{county_slug}/{apn}/{date_str}/data.{extension}"
    client = _client()
    _ensure_bucket(client)
    client.put_object(
        settings.minio_bucket,
        key,
        data=io.BytesIO(content),
        length=len(content),
        content_type="application/octet-stream",
    )
    logger.debug("Uploaded %s bytes to %s", len(content), key)
    return key


def download_raw(s3_key: str) -> bytes:
    """Download raw content from MinIO by S3 key."""
    client = _client()
    response = client.get_object(settings.minio_bucket, s3_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
