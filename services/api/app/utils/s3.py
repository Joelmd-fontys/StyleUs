"""AWS S3 helper utilities."""

from __future__ import annotations

from functools import lru_cache

import boto3


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
