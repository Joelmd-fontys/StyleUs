"""AWS S3 helper utilities."""

from __future__ import annotations

from functools import lru_cache

import boto3
from botocore.exceptions import ClientError


@lru_cache(maxsize=1)
def get_s3_client(region: str):
    return boto3.client("s3", region_name=region)


def generate_presigned_put_url(
    *,
    bucket: str,
    key: str,
    content_type: str,
    region: str,
    expires_in: int = 600,
) -> str:
    client = get_s3_client(region)
    return client.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_in,
    )


def head_object(*, bucket: str, key: str, region: str) -> dict | None:
    """Fetch object metadata from S3, returning None when the object is missing."""
    client = get_s3_client(region)
    try:
        return client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:  # pragma: no cover - boto specific noise
        if exc.response["Error"]["Code"] == "404":
            return None
        raise


def download_object(*, bucket: str, key: str, region: str) -> bytes:
    """Download an object from S3 and return its bytes."""
    client = get_s3_client(region)
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    if isinstance(body, bytes):
        return body
    return bytes(body)


def upload_bytes(
    *,
    bucket: str,
    key: str,
    region: str,
    data: bytes,
    content_type: str,
) -> None:
    """Upload raw bytes to S3."""
    client = get_s3_client(region)
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type, CacheControl="public, max-age=31536000")
